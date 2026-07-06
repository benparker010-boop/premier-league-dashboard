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


def build_model(min_games, prior=True, refresh=True):
    """Train the validated WC model on the finished matches. By default the
    cache is refreshed LIVE first (one list request; per-match stats fetched
    only for games the cache hasn't seen), so every answer reflects results up
    to the minute — offline/keyless it just falls back to the cache. The model
    is seeded with pre-tournament Elo priors (wc_priors) — validated on the
    tournament so far: Brier 0.59 -> 0.48 vs cold start."""
    if refresh:
        try:
            added, _total = ingest(verbose=False)
            if added:
                print(f"[predict] live refresh: {added} newly finished "
                      f"match(es) ingested.")
        except Exception as e:
            print(f"[predict] live refresh unavailable ({e}); using cache.")
    matches = load_cache()
    if not matches:
        print("[predict] cache empty — running a first ingest "
              "(fetches per-match stats, ~1 min)...\n")
        ingest()
        matches = load_cache()
    model = Model(neutral=True, min_g=min_games, **BEST)   # neutral venue
    from wc_priors import HOSTS, HOST_ELO
    model.hosts, model.host_elo = HOSTS, HOST_ELO   # hosts get home advantage
    if prior:
        from wc_priors import seed
        teams = {m["home"] for m in matches} | {m["away"] for m in matches}
        seed(model, teams)
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
    ap.add_argument("--no-prior", action="store_true",
                    help="skip the pre-tournament Elo prior (cold start)")
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the live data refresh; predict from the cache only")
    args = ap.parse_args()

    model, n = build_model(args.min_games, prior=not args.no_prior,
                           refresh=not args.no_refresh)
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
        from footy_model import m_result
        from calib import cal_result
        _live_odds(h, a, cal_result(m_result(model.goal_grid(h, a))))


def _live_odds(home, away, model_probs=None):
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
    if model_probs is not None:
        # market order is (home, away, draw); model probs are (H, D, A)
        from odds_tools import blend, BLEND_MARKET_W
        mp = [model_probs[0], model_probs[2], model_probs[1]]
        fb = blend(mp, fair)
        print(f"Blended final probabilities (market w={BLEND_MARKET_W:.0%} — "
              f"the sharpest displayed estimate):")
        for nm, p in zip(names, fb):
            print(f"  {nm:22s} {p * 100:4.1f}%")


if __name__ == "__main__":
    main()
