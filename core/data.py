"""
core.data — TheStatsAPI client (framework-neutral).

This is the production data layer extracted from app.py with its Streamlit
couplings removed: `@st.cache_data` -> a tiny in-process TTL cache, and
`st.secrets` -> core._secrets.get_secret. The function set and TTLs match
app.py so a new front-end gets identical data behaviour. No streamlit import.

The current Streamlit app keeps its own copy for now; this module exists so the
new UI (or an API server) can call the same endpoints without Streamlit.
"""
import time
import functools
import requests

from ._secrets import get_secret

STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"


class RateLimited(Exception):
    pass


def ttl_cache(ttl):
    """Minimal time-based memoiser keyed on the call args (positional + kwargs)."""
    def deco(fn):
        store = {}

        @functools.wraps(fn)
        def wrap(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            hit = store.get(key)
            if hit and hit[1] > now:
                return hit[0]
            val = fn(*args, **kwargs)
            store[key] = (val, now + ttl)
            return val
        wrap.cache_clear = store.clear
        return wrap
    return deco


def _headers():
    key = get_secret("STATS_API_KEY")
    return {"Authorization": f"Bearer {key}"}


def stats_get(path, params=None, retries=3):
    """GET from TheStatsAPI; on 429 (rate limit) wait and retry a few times."""
    url = f"{STATS_BASE}{path}"
    last = None
    for i in range(retries):
        last = requests.get(url, headers=_headers(), params=params, timeout=15)
        if last.status_code != 429:
            return last
        try:
            wait = int(last.headers.get("Retry-After", 3 + i * 3))
        except (TypeError, ValueError):
            wait = 3 + i * 3
        time.sleep(min(wait, 8))
    raise RateLimited("TheStatsAPI rate limit reached. Wait ~1 min and retry.")


# ---- cached endpoints (TTLs mirror app.py) -------------------------------- #
@ttl_cache(600)
def matches(status):
    r = stats_get("/football/matches",
                  {"competition_id": WC_COMP, "season_id": WC_SEASON,
                   "status": status, "per_page": 100})
    r.raise_for_status()
    return r.json().get("data", [])


@ttl_cache(600)
def match_stats(match_id):
    r = stats_get(f"/football/matches/{match_id}/stats")
    r.raise_for_status()
    return r.json().get("data", {})


@ttl_cache(120)
def match_timeline(match_id):
    """Event list; the API wraps it as {match_id, coverage, events:[...]}."""
    try:
        r = stats_get(f"/football/matches/{match_id}/timeline")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json().get("data", [])
        if isinstance(data, dict):
            data = data.get("events", [])
        return data if isinstance(data, list) else []
    except Exception:
        return []


@ttl_cache(600)
def match_lineups(match_id):
    try:
        r = stats_get(f"/football/matches/{match_id}/lineups")
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        d = r.json().get("data", {})
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


@ttl_cache(1800)
def match_player_stats(match_id):
    r = stats_get(f"/football/matches/{match_id}/player-stats")
    r.raise_for_status()
    data = r.json().get("data", [])
    return data if isinstance(data, list) else []


@ttl_cache(300)
def match_odds(match_id):
    try:
        r = stats_get(f"/football/matches/{match_id}/odds")
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        d = r.json().get("data", {})
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


@ttl_cache(3600)
def search_player(name):
    r = stats_get("/football/players", {"search": name})
    r.raise_for_status()
    return r.json().get("data", [])


@ttl_cache(600)
def player_stats(player_id):
    r = stats_get(f"/football/players/{player_id}/stats", {"season_id": WC_SEASON})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("data", {})


def live_matches():
    """Matches in progress now (tries the status strings the API may use)."""
    for s in ("live", "in_play", "inplay", "playing", "in_progress"):
        try:
            data = matches(s)
        except Exception:
            continue
        if data:
            return data
    return []


def finished():
    return matches("finished")


def upcoming():
    return matches("scheduled")
