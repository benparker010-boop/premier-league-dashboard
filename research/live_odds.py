"""
live_odds.py  —  The Odds API client for live World Cup odds (research only)
----------------------------------------------------------------------------
Pulls real bookmaker odds for live fixtures so the value finder can compare the
model's fair odds against the market. The key is read from
.streamlit/secrets.toml (never hard-coded, never committed).

STATUS: STUB until a key is provided. With no key it prints setup instructions
and returns None, so nothing downstream crashes.

HOW TO GET A KEY (free):
  1. Sign up at https://the-odds-api.com  (free tier = 500 requests/month).
  2. Add to .streamlit/secrets.toml:
         ODDS_API_KEY = "your_key_here"
  3. Run:  python research/live_odds.py --live

The free tier covers h2h (1X2) and totals (over/under). BTTS / corners / cards
need a paid tier or a different provider; the model still produces fair odds for
them — there's just no live market to compare against yet.
"""

import os
import sys

API = "https://api.the-odds-api.com/v4"
# The Odds API sport keys (change as the tournament's key goes live):
SPORT_WC = "soccer_fifa_world_cup"


PLACEHOLDER = "PASTE_YOUR_KEY_HERE"


def _read_secret(name):
    """Read a key from .streamlit/secrets.toml without importing streamlit.
    Treats an unset/placeholder value as missing."""
    path = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
    val = None
    if not os.path.exists(path):
        return None
    try:
        import tomllib
        with open(path, "rb") as fh:
            val = tomllib.load(fh).get(name)
    except Exception:
        # minimal fallback parser: KEY = "value"
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip().startswith(name):
                    parts = ln.split("=", 1)
                    if len(parts) == 2:
                        val = parts[1].strip().strip('"').strip("'")
                        break
    if not val or val == PLACEHOLDER:
        return None
    return val


def fetch_odds(sport=SPORT_WC, regions="uk,eu", markets="h2h,totals"):
    """Return the API's list of fixtures-with-odds, or None if no key / no network."""
    key = _read_secret("ODDS_API_KEY")
    if not key:
        print(_setup_message())
        return None
    try:
        import requests
    except ImportError:
        print("requests not installed — `pip install -r requirements.txt`.")
        return None
    url = f"{API}/sports/{sport}/odds/"
    params = dict(apiKey=key, regions=regions, markets=markets, oddsFormat="decimal")
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        print(f"Odds API error {r.status_code}: {r.text[:200]}")
        return None
    print(f"Fetched {len(r.json())} fixtures.  "
          f"Quota: used {r.headers.get('x-requests-used','?')}, "
          f"remaining {r.headers.get('x-requests-remaining','?')}.")
    return r.json()


def best_h2h(fixture):
    """Best (highest) decimal price for home/draw/away across all books in a fixture."""
    best = {}
    for bk in fixture.get("bookmakers", []):
        for mk in bk.get("markets", []):
            if mk["key"] != "h2h":
                continue
            for oc in mk["outcomes"]:
                best[oc["name"]] = max(best.get(oc["name"], 0), oc["price"])
    return best


def _setup_message():
    return (
        "\n[live_odds] No ODDS_API_KEY found - running as a stub.\n"
        "  Get a free key at https://the-odds-api.com (500 req/month),\n"
        "  then add to .streamlit/secrets.toml:\n"
        '      ODDS_API_KEY = "your_key_here"\n'
        "  and re-run with --live.\n"
    )


if __name__ == "__main__":
    if "--live" in sys.argv:
        data = fetch_odds()
        if data:
            for fx in data[:5]:
                print(f"\n{fx['home_team']} vs {fx['away_team']}  ({fx['commence_time']})")
                print("  best H2H:", best_h2h(fx))
    else:
        print(_setup_message())
        print("Run with --live once a key is set to pull real fixtures.")
