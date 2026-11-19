#!/usr/bin/env python3
"""Deterministic, horizon-adaptive GTA VI trophy earn-rate forecaster."""
import json
import math
import os
from datetime import datetime
from statistics import NormalDist, median

DEFAULT_Z = (-1.645, -0.674, 0.0, 0.674, 1.645)

def epoch(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

def safe_exp(value):
    return math.exp(min(700.0, max(-700.0, value)))

def slope_ols(xs, ys):
    xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - xm) ** 2 for x in xs)
    return sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / den if den else None

def distinct_states(history):
    states = []
    for read in history:
        if (not states or read["players_tracked"] != states[-1]["N"]
                or read["rates"] != states[-1]["rates"]):
            states.append({"time": epoch(read["at"]), "N": read["players_tracked"],
                           "rates": read["rates"]})
    return states

def forecast(case):
    trophies = case.get("trophies", [])
    levels = case.get("levels", [0.05, 0.25, 0.5, 0.75, 0.95])
    zs = DEFAULT_Z if levels == [0.05, 0.25, 0.5, 0.75, 0.95] else [NormalDist().inv_cdf(float(p)) for p in levels]
    states = distinct_states(case.get("history", []))
    if not states:
        return {"trophies": [{"id": t["id"], "q": [1, 1, 1, 1, 1]} for t in trophies]}

    t0, target = states[0]["time"], epoch(case["target"])
    us = [(s["time"] - t0) / 3600.0 for s in states]
    U = (target - t0) / 3600.0
    d = max(0.0, float(case.get("horizon_minutes", 0)) / 1440.0)
    has_growth_pair = any(
        states[i]["N"] != states[j]["N"] and states[i]["time"] != states[j]["time"]
        for i in range(len(states)) for j in range(i + 1, len(states))
    )
    if has_growth_pair:
        fit = slope_ols([math.log1p(max(0.0, u)) for u in us], [math.log(max(float(s["N"]), 1e-12)) for s in states])
        b = min(3.0, max(0.0, fit)) if fit is not None else 1.03
    else:
        b = 1.03
    Nlast = float(states[-1]["N"])
    predicted_n = safe_exp(math.log(max(Nlast, 1e-12)) + b * (math.log1p(max(0.0, U)) - math.log1p(max(0.0, us[-1]))))
    NT = min(50.0 * Nlast, max(Nlast, predicted_n))

    records = []
    for i, trophy in enumerate(trophies):
        observations = []
        for j, state in enumerate(states):
            rates = state["rates"]
            rate = rates[i] if i < len(rates) else None
            if rate is not None:
                e = float(rate) / 100.0 * float(state["N"])
                observations.append((j, us[j], e, float(rate)))
        fitted = None
        if len(observations) >= 2 and len({o[1] for o in observations}) >= 2:
            xs = [math.log1p(max(0.0, o[1])) for o in observations]
            ys = [math.log(max(o[2], 0.25)) for o in observations]
            pair_slopes = [(ys[k] - ys[j]) / (xs[k] - xs[j])
                           for j in range(len(xs)) for k in range(j + 1, len(xs)) if xs[k] != xs[j]]
            if pair_slopes:
                fitted = {"slope": median(pair_slopes), "obs": observations, "xs": xs, "ys": ys}
        records.append({"trophy": trophy, "obs": observations, "fit": fitted})

    all_slopes = [r["fit"]["slope"] for r in records if r["fit"] is not None]
    for record in records:
        fit = record["fit"]
        if fit is None:
            continue
        tier_slopes = [r["fit"]["slope"] for r in records
                       if r["fit"] is not None and r["trophy"].get("tier") == record["trophy"].get("tier")]
        group = median(tier_slopes) if len(tier_slopes) >= 3 else median(all_slopes) if all_slopes else 0.0
        last_e = record["obs"][-1][2]
        w = min(1.0, last_e / 4.0)
        fit["shrunk"] = min(b + 1.5, max(-0.2, w * fit["slope"] + (1.0 - w) * group))

    output = []
    for record in records:
        trophy, obs, fit = record["trophy"], record["obs"], record["fit"]
        unobserved = not obs
        universal = False
        if unobserved:
            ET = 0.5
            last_e, last_rate, u_last = 0.5, None, us[-1]
        else:
            _, u_last, last_e, last_rate = obs[-1]
            universal = last_e >= 0.999 * Nlast
            if universal:
                ET = NT
            elif fit is not None:
                ET = safe_exp(math.log(max(last_e, 0.25)) + fit["shrunk"] *
                              (math.log1p(max(0.0, U)) - math.log1p(max(0.0, u_last))))
            else:
                age = max(0.0, U - u_last)
                ET = last_e * (1.0 + 0.15 * min(1.0, age / 4.7))
            if not universal:
                ET = min(NT, max(0.95 * last_e, ET))
        m = min(99.99, max(0.01, 100.0 * ET / NT))
        if not universal:
            m = min(95.0, m)
        if universal and last_rate is not None and last_rate >= 99.99:
            output.append({"id": trophy["id"], "q": [100, 100, 100, 100, 100]})
            continue

        resid = 0.0
        if fit is not None and len(obs) >= 3:
            slope = fit["shrunk"]
            last_x, last_y = fit["xs"][-1], fit["ys"][-1]
            residuals = [y - (last_y + slope * (x - last_x)) for x, y in zip(fit["xs"], fit["ys"])]
            resid = min(0.6, 1.4826 * median([abs(x) for x in residuals]))
        age_last = max(0.0, U - us[-1])
        refresh = 0.12 if len(states) == 1 or age_last > 1.0 else 0.05 if age_last > 0.25 else 0.0
        small = 0.08 if unobserved else min(0.08, 0.12 / math.sqrt(max(ET, 1.0)))
        sigma = math.sqrt((0.65 * math.sqrt(d)) ** 2 + resid ** 2 + refresh ** 2 + small ** 2 + (0.3 ** 2 if unobserved else 0.0))
        sigma = min(1.9, max(0.05, sigma))
        logit = math.log(m / (100.0 - m))
        qs = []
        for z in zs:
            value = 100.0 / (1.0 + safe_exp(-(logit + float(z) * sigma)))
            rounded = math.floor(value * 10000.0 + 0.5) / 10000.0
            rounded = min(100.0, max(0.0, rounded))
            qs.append(int(rounded) if rounded.is_integer() else rounded)
        for k in range(1, len(qs)):
            qs[k] = max(qs[k], qs[k - 1])
        output.append({"id": trophy["id"], "q": qs})
    return {"trophies": output}

def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(output_dir, exist_ok=True)
    for filename in sorted(name for name in os.listdir(input_dir) if name.endswith(".in")):
        with open(os.path.join(input_dir, filename), encoding="utf-8") as source:
            case = json.load(source)
        result = forecast(case)
        target = os.path.join(output_dir, filename[:-3] + ".out")
        with open(target, "w", encoding="utf-8", newline="\n") as dest:
            dest.write(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
