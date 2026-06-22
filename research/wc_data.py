"""
wc_data.py  —  pull finished World Cup matches from TheStatsAPI (research only)
------------------------------------------------------------------------------
Mirrors app.py's data layer (without streamlit) so the research model can be fed
real tournament form. Converts each finished match into the same dict shape that
footy_model.Model.update() expects (goals, shots, corners, cards), so the
validated engine prices live internationals with no changes.

Key read from .streamlit/secrets.toml as STATS_API_KEY. With no key, returns []
so callers degrade gracefully to market-only mode.
"""

import time
import requests

from live_odds import _read_secret

STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"

# Odds-API team name -> TheStatsAPI name, for the few that differ. Extend as needed
# (printed warnings below will tell you which names failed to match).
NAME_ALIASES = {
    "usa": "United States", "united states of america": "United States",
    "south korea": "Korea Republic", "north korea": "Korea DPR",
    "iran": "IR Iran", "ivory coast": "Côte d'Ivoire",
    "czech republic": "Czechia", "bosnia & herzegovina": "Bosnia and Herzegovina",
    "dr congo": "Congo DR", "cape verde": "Cabo Verde",
}


def _headers():
    key = _read_secret("STATS_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else None


def _get(path, params=None, retries=3):
    h = _headers()
    if h is None:
        return None
    url = f"{STATS_BASE}{path}"
    for i in range(retries):
        r = requests.get(url, headers=h, params=params, timeout=15)
        if r.status_code != 429:
            r.raise_for_status()
            return r.json().get("data", None)
        try:
            wait = int(r.headers.get("Retry-After", 3 + i * 3))
        except (TypeError, ValueError):
            wait = 3 + i * 3
        time.sleep(min(wait, 8))
    raise RuntimeError("TheStatsAPI rate limit reached; wait ~60s and retry.")


def _date(m):
    for k in ("datetime", "date", "kickoff", "start_time", "starting_at",
              "utc_date", "kickoff_time"):
        v = m.get(k) if isinstance(m, dict) else None
        if v:
            return str(v)
    return ""


def _sv(ov, key, side):
    try:
        return ov[key]["all"][side]
    except Exception:
        return None


def finished_matches():
    data = _get("/football/matches",
                {"competition_id": WC_COMP, "season_id": WC_SEASON,
                 "status": "finished", "per_page": 100})
    return data or []


def match_record(m):
    """One finished API match -> footy_model-format dict (with id + date), or None
    if it has no final score yet. Fetches that match's stats overview. This is the
    single source of truth for the record shape, shared by the live path and the
    cache ingester (wc_ingest) so they never drift."""
    hs, as_ = m["score"]["home"], m["score"]["away"]
    if hs is None or as_ is None:
        return None
    try:
        ov = _get(f"/football/matches/{m['id']}/stats")
        ov = (ov or {}).get("overview", {})
    except Exception:
        ov = {}
    return dict(
        id=str(m["id"]), date=_date(m),
        home=m["home_team"]["name"], away=m["away_team"]["name"],
        fthg=int(hs), ftag=int(as_),
        hs=_sv(ov, "total_shots", "home") or 0,
        as_=_sv(ov, "total_shots", "away") or 0,
        hst=_sv(ov, "shots_on_target", "home") or 0,
        ast=_sv(ov, "shots_on_target", "away") or 0,
        hc=_sv(ov, "corner_kicks", "home"), ac=_sv(ov, "corner_kicks", "away"),
        hy=_sv(ov, "yellow_cards", "home"), ay=_sv(ov, "yellow_cards", "away"),
        hr=_sv(ov, "red_cards", "home"), ar=_sv(ov, "red_cards", "away"),
    )


def to_model_matches(verbose=True):
    """Finished WC matches as footy_model-format dicts, oldest first.

    Pulls live every call (slow: one stats request per match). For repeated use,
    prefer the cached path in wc_ingest.load_cache(), which only fetches matches
    it hasn't seen before."""
    ms = finished_matches()
    if not ms:
        if verbose:
            print("[wc_data] no finished matches (no key, or none played yet).")
        return []
    ms.sort(key=_date)
    out = [r for r in (match_record(m) for m in ms) if r is not None]
    if verbose:
        print(f"[wc_data] pulled {len(out)} finished WC matches.")
    return out


def resolve(name, known):
    """Map an Odds-API team name to a name the model knows."""
    if name in known:
        return name
    alias = NAME_ALIASES.get(name.lower())
    if alias and alias in known:
        return alias
    low = {k.lower(): k for k in known}
    if name.lower() in low:
        return low[name.lower()]
    return None


if __name__ == "__main__":
    ms = to_model_matches()
    teams = sorted({m["home"] for m in ms} | {m["away"] for m in ms})
    print(f"teams seen ({len(teams)}): {', '.join(teams)}")
