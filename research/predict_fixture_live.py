"""
predict_fixture_live.py  —  on-demand World Cup fixture card (research only)
---------------------------------------------------------------------------
Print a full prediction for ANY World Cup pairing off the validated model:
match result (W/D/W), most likely scorelines, totals, BTTS, corners, cards —
all from one consistent score grid (footy_model), trained on real tournament
form pulled by wc_ingest.

It reads the local cache (research/wc_matches.jsonl). If the cache is empty it
bootstraps itself by running one ingest first. So predictions get sharper every
time wc_ingest picks up new results — no code changes needed.

USAGE
  python research/predict_fixture_live.py "France" "Iraq"
  python research/predict_fixture_live.py "Brazil" "Spain" --odds        # add live market
  python research/predict_fixture_live.py "France" "Iraq" --min-games 1  # force early estimate
  python research/predict_fixture_live.py --teams                        # list known teams

NOTES
  * Neutral venue (World Cup) and the validated BEST params are used throughout.
  * By default a team needs >=2 finished matches before the model will trust it
    (--min-games changes that). With fewer games the model abstains rather than
    guessing — lower the bar only if you accept a low-confidence number.
  * --odds pulls live bookmaker prices (costs one Odds-API request).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:                                   # make accented team names print cleanly on Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from footy_model import Model
from predict_demo import card, BEST    # reuse the exact multi-market pretty-printer
from wc_data import resolve
from wc_ingest import load_cache, ingest


def build_model(min_games):
    """Train the validated WC model on the cached finished matches."""
    matches = load_cache()
    if not matches:
        print("[predict] cache empty — running a first ingest "
              "(fetches per-match stats, ~1 min)...\n")
        ingest()
        matches = load_cache()
    model = Model(neutral=True, min_g=min_games, **BEST)   # neutral venue
    for m in matches:
        model.update(m)
    return model, len(matches)


def main():
    ap = argparse.ArgumentParser(description="On-demand World Cup fixture prediction.")
    ap.add_argument("home", nargs="?", help='team A, e.g. "France"')
    ap.add_argument("away", nargs="?", help='team B, e.g. "Iraq"')
    ap.add_argument("--min-games", type=int, default=2,
                    help="games each team needs before the model will predict (default 2)")
    ap.add_argument("--odds", action="store_true",
                    help="also pull live bookmaker odds (one Odds-API request)")
    ap.add_argument("--teams", action="store_true",
                    help="list the teams the model currently knows, then exit")
    args = ap.parse_args()

    model, n = build_model(args.min_games)
    known = sorted(model.G)
    print(f"Model built from {n} finished WC matches; {len(known)} teams known.\n")

    if args.teams or not (args.home and args.away):
        print("Known teams:\n  " + "\n  ".join(known))
        if not args.teams:
            print('\nGive two teams, e.g.:  python research/predict_fixture_live.py '
                  '"France" "Iraq"')
        return

    h, a = resolve(args.home, set(known)), resolve(args.away, set(known))
    if not h or not a:
        miss = [orig for orig, r in ((args.home, h), (args.away, a)) if not r]
        print(f"Could not match: {', '.join(miss)}. Run with --teams to see valid names.")
        return

    for side in (h, a):
        print(f"  {side:18s} games={model.G.get(side, 0):>2}  "
              f"Elo={model.elo.get(side, 1500):6.1f}")

    if model.goal_grid(h, a) is None:
        print(f"\nModel abstains: one or both teams have < {args.min_games} finished "
              f"matches. Re-run later, or add --min-games 1 for a low-confidence estimate.")
        return

    ls = model.goal_lambdas(h, a)
    print(f"\nExpected goals:  {h} {ls[0]:.2f}  -  {ls[1]:.2f} {a}")
    card(model, h, a)                  # result, scorelines, totals, BTTS, corners, cards

    if args.odds:
        _live_odds(h, a)


def _live_odds(home, away):
    """Best-effort live market consensus for the fixture (de-vigged)."""
    try:
        from live_odds import fetch_odds, SPORT_WC
        from live_value import consensus
    except Exception as e:
        print(f"\nLive market: unavailable ({e}).")
        return
    data = fetch_odds(sport=SPORT_WC, regions="uk,eu", markets="h2h") or []
    key = (home + away).lower()
    fx = next((f for f in data
               if all(t in (f["home_team"] + f["away_team"]).lower()
                      for t in (home.lower().split()[0], away.lower().split()[0]))), None)
    if not fx:
        print("\nLive market: this fixture isn't currently listed by the odds API.")
        return
    names = [fx["home_team"], fx["away_team"], "Draw"]
    c = consensus(fx, names)
    if not c:
        print("\nLive market: incomplete odds for this fixture.")
        return
    fair, best, margin = c
    print(f"\nLive market (avg book margin {margin * 100:.1f}%):")
    for nm, mf, (price, book) in zip(names, fair, best):
        print(f"  {nm:22s} consensus {mf * 100:4.1f}%   best {price:5.2f} ({book})")


if __name__ == "__main__":
    main()
