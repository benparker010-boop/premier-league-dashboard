"""
TheStatsAPI connection test.

What this does, in plain English:
  1. Asks you to paste your API key (so the key is NEVER saved in this file).
  2. Checks the key works by looking up the World Cup competition.
  3. Finds the current World Cup season.
  4. Pulls a few matches and PRINTS the exact shape of the data,
     so we can see precisely which stat fields are available.

You do NOT need to understand this code. Just run it and send me what it prints.
"""

import requests
import json

BASE_URL = "https://api.thestatsapi.com/api"

# Ask for the key at runtime so it never lives inside this file.
api_key = input("Paste your TheStatsAPI key, then press Enter: ").strip()
headers = {"Authorization": f"Bearer {api_key}"}


def call(path, params=None):
    """Make one GET request and return the parsed JSON (or raise a clear error)."""
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f"  -> {url}  [HTTP {r.status_code}]")
    if r.status_code == 401:
        raise SystemExit("\n❌ The key was rejected (401). Double-check you copied it correctly.")
    r.raise_for_status()
    return r.json()


print("\n--- Step 1: confirm the key works by finding the World Cup ---")
comps = call("/football/competitions", {"search": "world cup"})
print(json.dumps(comps, indent=2)[:1500])

# The World Cup competition id (their docs list comp_6107; we confirm above)
competition_id = "comp_6107"

print("\n--- Step 2: find the available seasons for that competition ---")
seasons = call(f"/football/competitions/{competition_id}/seasons")
print(json.dumps(seasons, indent=2)[:1500])

# Try to grab the most recent season id automatically from the response.
season_id = None
try:
    season_list = seasons.get("data", seasons)
    if isinstance(season_list, list) and season_list:
        # take the last entry as a guess at the current season
        season_id = season_list[-1].get("id") or season_list[-1].get("season_id")
except Exception:
    pass
print(f"\nBest-guess current season_id: {season_id}")

print("\n--- Step 3: pull a few matches and show their FULL structure ---")
if season_id:
    matches = call("/football/matches", {
        "competition_id": competition_id,
        "season_id": season_id,
        "per_page": 3,
    })
    print(json.dumps(matches, indent=2)[:4000])
else:
    print("Couldn't auto-detect a season id — paste me the Step 2 output and I'll grab it.")

print("\n✅ Done. Copy everything above and paste it back to me.")
