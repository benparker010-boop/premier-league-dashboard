"""
build_data.py
-------------
Run this once whenever you want to refresh the top-10 scorers and assists that
show on the website. It pulls every finished World Cup match from TheStatsAPI,
tallies real goals and assists, and writes two small files:

    top_scorers.csv
    top_assists.csv

The website reads those files directly, so the tables appear instantly on every
visit without rebuilding from the API each time.

HOW TO RUN (in the Terminal tab inside PyCharm):
    python build_data.py

Then commit and push the two CSV files to GitHub:
    git add top_scorers.csv top_assists.csv
    git commit -m "Update top scorers and assists snapshot"
    git push

The API key is read from .streamlit/secrets.toml (the same file the app uses) or
from a STATS_API_KEY environment variable.
"""

import os
import time
import requests
import pandas as pd

STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"


def _read_toml(path):
    try:
        import tomllib                  # Python 3.11+
        with open(path, "rb") as f:
            return tomllib.load(f)
    except ModuleNotFoundError:
        import toml                      # older Python (pip install toml)
        with open(path) as f:
            return toml.load(f)


def get_api_key():
    # 1) environment variable
    key = os.environ.get("STATS_API_KEY")
    if key:
        return key
    # 2) the secrets files Streamlit itself reads: project-local first,
    #    then the global one in your user folder (C:\Users\<you>\.streamlit).
    candidates = [
        os.path.join(".streamlit", "secrets.toml"),
        os.path.expanduser(os.path.join("~", ".streamlit", "secrets.toml")),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                data = _read_toml(path)
                if "STATS_API_KEY" in data:
                    print(f"Using API key from {path}")
                    return data["STATS_API_KEY"]
            except Exception as e:
                print(f"  (couldn't read {path}: {e})")
    raise SystemExit(
        "Could not find STATS_API_KEY. Checked the STATS_API_KEY environment "
        "variable and these files:\n  " + "\n  ".join(candidates) +
        "\nMake sure your key is in one of them.")


API_KEY = get_api_key()
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def stats_get(path, params=None, retries=6):
    url = f"{STATS_BASE}{path}"
    last = None
    for i in range(retries):
        last = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if last.status_code != 429:
            return last
        wait = 5 + i * 4          # 5, 9, 13, 17, 21, 25s
        print(f"  rate limited, waiting {wait}s...")
        time.sleep(wait)
    return last


def finished_matches():
    r = stats_get("/football/matches",
                  {"competition_id": WC_COMP, "season_id": WC_SEASON,
                   "status": "finished", "per_page": 100})
    r.raise_for_status()
    return r.json().get("data", [])


def player_stats(match_id):
    """Per-player stat sheet for one match — includes goals and assists."""
    r = stats_get(f"/football/matches/{match_id}/player-stats")
    r.raise_for_status()
    data = r.json().get("data", [])
    return data if isinstance(data, list) else []


def team_name_map(matches):
    """team_id -> national team name, read off the match list."""
    names = {}
    for m in matches:
        for side in ("home_team", "away_team"):
            t = m.get(side) or {}
            if t.get("id") and t.get("name"):
                names[t["id"]] = t["name"]
    return names


def main():
    print("Fetching finished matches...")
    matches = finished_matches()
    print(f"  {len(matches)} finished matches found.")
    names = team_name_map(matches)

    goals, assists = {}, {}
    for i, m in enumerate(matches, 1):
        print(f"  [{i}/{len(matches)}] reading match {m['id']} ...")
        time.sleep(1.5)               # be polite — avoids the rate limiter
        try:
            players = player_stats(m["id"])
        except Exception as e:
            print(f"    skipped ({e})")
            continue
        for p in players:
            name = p.get("player_name")
            if not name:
                continue
            team = names.get(p.get("team_id"), "")
            g = (p.get("shooting") or {}).get("goals", 0) or 0
            a = (p.get("passing") o