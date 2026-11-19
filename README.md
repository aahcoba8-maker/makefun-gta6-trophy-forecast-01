# GTA VI Trophy Rarity Forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/aahcoba8-maker/makefun-gta6-trophy-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/aahcoba8-maker/makefun-gta6-trophy-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A deterministic Python 3.13 forecaster for Exophase earn-rate quantiles across all 55 PlayStation 5 trophies. It reads each case from `MAKEFUN_INPUT_DIR` (default `/input`) and writes compact forecasts to `MAKEFUN_OUTPUT_DIR` (default `/output`).

The forecast separates trophy earners `E` from tracked players `N`: it forecasts each factor and then computes the earn rate as `100 × E / N`. That captures refresh-time dilution when the tracked-player pool grows faster than trophy earners.

History is collapsed to distinct page states before fitting. Repeated reads of an unchanged page do not count as independent observations; a state begins when the player count or any trophy rate changes.

Calibration constants follow the contest specification:

- A default player-growth slope of `1.03` matches the observed roughly 6.06× tracked-player increase over 4.7 hours.
- With one earners observation, growth is limited to 15% over 4.7 hours, matching typical trophy growth during the frozen launch page.
- Logit uncertainty starts at `0.65 × sqrt(horizon in days)` to widen forecasts over longer horizons.
- The uncertainty floor `0.05`, refresh additions `0.05`/`0.12`, and low-count term `0.12/sqrt(E)` preserve uncertainty when observations are sparse or stale.

---

<sub>Entered on [make.fun](https://make.fun/?ref=gh9tewpq&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
