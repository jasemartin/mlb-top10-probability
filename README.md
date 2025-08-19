# MLB Daily Top 10 — Statcast Only

Auto-generates a daily Top 10 board for:
- Hit probability
- HR probability
- 1+/2+/3+ total bases
- Pitcher 6+ strikeouts

Built from MLB schedule, probables, active rosters, and Statcast rolling features, with optional Statcast-derived BvP blending.

## Features

- Rolling Statcast features for batters and pitchers
- Ballpark multipliers for HR/hit and K environment
- Optional opponent K% vs hand input
- BvP blending from Statcast (AB-aware weighting; small barrel bump for notable HR history)
- Streamlit UI with date-based auto slate

## Setup

### Requirements

See `requirements.txt`:
- pandas
- numpy
- pybaseball
- streamlit
- requests
- pyarrow

Install:
```bash
pip install -r requirements.txt
```

Optional: set up a virtual environment.

### Run

```bash
streamlit run app.py
```

In the sidebar:
- Select lookback window (rolling days)
- Choose ballpark multipliers for HR/hit and strikeouts
- Optionally set opponent K% vs hand (league avg ~0.22)
- Choose the slate date and click "Generate Top 10"

## Data sources

- MLB StatsAPI for schedule, probables, and active rosters
- Statcast via `pybaseball` for batter/pitcher rolling windows and BvP pulls

`pybaseball` local caching is enabled in `fetch_data.py` to reduce repeat network calls.

## BvP blending

- Caches BvP summaries in `data/bvp_cache.parquet` (auto-created).
- Weighting:
  - If AB ≥ 12 vs the probable pitcher, weight = 0.5.
  - Otherwise weight scales with PA and caps at `max_weight` (default 0.4).
- Blend:
  - AVG -> `b_xba`
  - wOBA -> `b_xwoba`
- Optional barrel-rate bump when there's notable HR history vs the pitcher.

## Notes

- Basic timeouts are used for StatsAPI calls.
- Code is resilient to partial/missing API fields.
- If you see "No results for that date", verify schedule availability for the chosen day.

## Roadmap ideas

- Add simple retries/backoff for network calls
- Persist Statcast rolling windows locally for faster boot
- Export Top 10 sections to CSV
- Unit tests for baseline rules and feature blending