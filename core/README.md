# `core/` — framework-neutral brains (Parker-redesign foundation)

This package holds the **data + model + AI "brains"** of the app with **no
Streamlit dependency**, so the upcoming Parker front-end can call them whether we
rebuild natively in Streamlit (Option A) or decouple into an API + JS app
(Option B). See `../design_brief.md` and the migration plan in the chat history.

> **Nothing here is wired into the running app yet.** `app.py` is untouched and
> still serves the live site with its own copies. This package is the additive
> Step 0 ("extract the brains") so the old UI can later be replaced safely. The
> recovery snapshot for the pre-redesign app is the git tag
> **`pre-parker-redesign`** / branch **`backup/pre-parker-redesign`** (commit
> `b21de8b`).

## Modules

| Module | What it exposes |
|---|---|
| `core.data` | TheStatsAPI client, Streamlit-free. Cached fetchers (TTLs mirror `app.py`): `matches(status)`, `match_stats`, `match_timeline`, `match_lineups`, `match_player_stats`, `match_odds`, `search_player`, `player_stats`, plus `live_matches()/finished()/upcoming()`. `@st.cache_data` → in-process `ttl_cache`; `st.secrets` → `get_secret`. |
| `core.predict` | `predict(home, away) -> dict` (W/D/W, expected goals, top scorelines, totals, BTTS). Trained on the live cache `research/wc_matches.jsonl` using the **validated** engine `research/footy_model.Model` (Dixon-Coles + shrinkage Poisson + xG + Elo). Also `build_model()`, `known_teams()`. |
| `core.ai` | `ask_ai(prompt, model=…)` (Claude haiku/sonnet) + `match_summary_prompt(facts)`. Same models/keys as `app.py`. |
| `core._secrets` | `get_secret(name)` — env var first, then `.streamlit/secrets.toml`. |

## Usage

```python
from core import data, predict, ai

predict.predict("Brazil", "Spain")          # structured prediction dict
data.match_stats("mt_986262946")            # full /stats payload
ai.ask_ai(ai.match_summary_prompt([...]))   # needs ANTHROPIC_API_KEY
```

Run from the repo root (so `core` and `research/` are importable), e.g.
`PYTHONPATH=. python your_script.py`.

## Keep vs replace (the migration seam)

- **KEEP (here / `research/`):** the data client, the predictor engine, the AI
  helpers, the deterministic tournament logic, `wc_ingest` + its scheduled task.
- **REPLACE (in `app.py`):** all CSS, the `?view=` router, and every
  `render_*` / `section_*` / `*_html` presentation function. The brains compute;
  the UI renders — the redesign swaps only the rendering side.

## Secrets

- `STATS_API_KEY` — required for `core.data` (present locally).
- `ANTHROPIC_API_KEY` — required for `core.ai`; currently set on Streamlit Cloud
  only, **not** in the local `secrets.toml`, so AI calls fail locally (same as
  `app.py`). Add it locally, or set the env var, to exercise AI off-cloud.

## Status (verified)

`core.data` (live API, all endpoints) and `core.predict` (48 teams; e.g. Brazil
vs Spain ≈ 34/25/42, xG 1.33–1.51) are verified working. `core.ai` imports and
builds correctly; a live call needs `ANTHROPIC_API_KEY` available locally.
