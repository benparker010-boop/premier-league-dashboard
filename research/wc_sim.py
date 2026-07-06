"""
wc_sim.py  —  advance probabilities for upcoming knockout ties (research only)
------------------------------------------------------------------------------
Fetches the scheduled World Cup fixtures and, for each knockout tie, prints the
full-strength engine's 90-minute result probabilities (Platt-calibrated) plus
P(advance) — because in a knockout a draw isn't an outcome, it's extra time and
penalties.

P(advance) = P(win in 90) + P(draw in 90) x P(win ET/pens), where the ET/pens
leg is a compressed coin-flip tilted by Elo (half the 90-minute Elo expectancy
edge — shootouts are much closer to random than open play).

USAGE:  python research/wc_sim.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from calib import cal_result
from footy_model import m_result
from predict_fixture_live import build_model
from wc_data import _get, _date, resolve, WC_COMP, WC_SEASON


def upcoming_matches():
    """Scheduled (not finished) WC fixtures, soonest first."""
    data = _get("/football/matches",
                {"competition_id": WC_COMP, "season_id": WC_SEASON,
                 "per_page": 100})
    if not data:
        return []
    out = [m for m in data
           if (m.get("score") or {}).get("home") is None
           or str(m.get("status", "")).lower() in ("scheduled", "notstarted", "upcoming")]
    out.sort(key=_date)
    return out


def advance_prob(model, h, a):
    """(pH, pD, pA, P(h advances)) for a knockout tie, or None if unpredictable."""
    g = model.goal_grid(h, a)
    if g is None:
        return None
    pH, pD, pA = cal_result(m_result(g))
    d = (model.elo.get(h, 1500.0) - model.elo.get(a, 1500.0) + model._bonus(h))
    e90 = 1 / (1 + 10 ** (-d / 400))
    pens_h = 0.5 + (e90 - 0.5) * 0.5        # ET/pens: half the open-play edge
    return pH, pD, pA, pH + pD * pens_h


def main():
    model, n = build_model(min_games=2)
    print(f"Model: {n} finished matches, priors + host advantage on.\n")
    ms = upcoming_matches()
    if not ms:
        print("No scheduled fixtures from the API (no key, or none listed).")
        return
    known = set(model.G)
    print(f"{'date':16s} {'fixture':42s} {'W/D/W':>17s} {'P(advance)':>11s}")
    for m in ms:
        hn = (m.get("home_team") or {}).get("name", "?")
        an = (m.get("away_team") or {}).get("name", "?")
        h, a = resolve(hn, known), resolve(an, known)
        date = _date(m)[:16]
        if not h or not a:
            print(f"{date:16s} {hn} vs {an}   (teams not yet decided/known)")
            continue
        r = advance_prob(model, h, a)
        if r is None:
            print(f"{date:16s} {h} vs {a}   (not enough data)")
            continue
        pH, pD, pA, adv = r
        print(f"{date:16s} {h + ' vs ' + a:42s} "
              f"{pH:5.0%}/{pD:4.0%}/{pA:4.0%} {adv:10.0%}")
    print("\nP(advance) = P(win 90') + P(draw) x P(win ET/pens); "
          "read as the home-listed side's chance of going through.")


if __name__ == "__main__":
    main()
