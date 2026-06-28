"""
core — framework-neutral "brains" for the World Cup app.

The data layer, the validated match predictor, and the Claude AI helpers, with
no Streamlit dependency, so a new front-end (Parker redesign — Streamlit-native
or a decoupled API + JS app) can call them directly. The current Streamlit
app.py is untouched and keeps its own copies until the UI is migrated.

Modules:
  core.data     — TheStatsAPI client (cached fetchers: matches, stats, timeline,
                  lineups, player-stats, odds, player search/stats; live/finished/upcoming)
  core.predict  — predict(home, away) -> structured dict, off research/footy_model.Model
  core.ai       — ask_ai(...) + prompt builders (Claude haiku/sonnet)
  core._secrets — get_secret(): env var, then .streamlit/secrets.toml
"""
from . import data, predict, ai, _secrets  # noqa: F401

__all__ = ["data", "predict", "ai", "_secrets"]
