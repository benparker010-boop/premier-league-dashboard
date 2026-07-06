"""
predict_demo.py  —  full multi-market fair-odds card for a fixture (research only)
----------------------------------------------------------------------------------
Trains the validated model on all available history, then prints — for a fixture —
every market's probability and fair odds off one consistent engine. Where the CSV
carries real bookmaker odds (1X2, O/U 2.5), it also shows the de-vigged market
price, the edge %, and a value flag.

By default it demos the last few fixtures in the data (so real odds exist to
compare). You can also call card(model, home, away) for any pairing.

USAGE:  python research/predict_demo.py research/seasons/
"""

import sys

from footy_model import Model, m_result, m_over, m_btts, m_top_scores, load_matches
from odds_tools import devig_proportional, fair_odds, edge, value_flag

BEST = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)


def _line(label, p, book=None, devig=None):
    fo = fair_odds(p)
    s = f"  {label:18s} {p*100:5.1f}%   fair {fo:5.2f}"
    if book is not None:
        e = edge(p, book)
        flag = "  <== VALUE" if devig is not None and value_flag(p, book, devig) else ""
        s += f"   book {book:5.2f}   edge {e*100:+5.1f}%{flag}"
    return s


def card(model, home, away, odds=None):
    g = model.goal_grid(home, away)
    print(f"\n{'='*60}\n{home}  vs  {away}\n{'='*60}")
    if g is None:
        print("  not enough history for these teams.")
        return
    from calib import cal, cal_result
    res = cal_result(m_result(g))          # Platt-recalibrated for display
    # match result, with book odds if present
    o = (odds or {}).get("1x2_close", {}).get("b365") if odds else None
    dv = devig_proportional(list(o)) if o else [None, None, None]
    print("Match result:")
    for i, lab in enumerate(("Home win", "Draw", "Away win")):
        print(_line(lab, res[i], o[i] if o else None, dv[i]))

    print("Most likely scores:")
    for (i, j), p in m_top_scores(g, 5):
        print(f"  {home[:12]:>12} {i}-{j} {away[:12]:<12}  {p*100:4.1f}%   fair {fair_odds(p):5.2f}")

    print("Total goals:")
    oo = (odds or {}).get("ou25_close", {}).get("b365") if odds else None
    odv = devig_proportional(list(oo)) if oo else [None, None]
    for ln in (1.5, 2.5, 3.5):
        ov = m_over(g, ln)
        if ln == 2.5:
            ov = cal(ov, "ou25")           # calibrator is fitted at the 2.5 line
        book = oo[0] if (oo and ln == 2.5) else None
        dvg = odv[0] if (oo and ln == 2.5) else None
        print(_line(f"Over {ln}", ov, book, dvg))
        print(_line(f"Under {ln}", 1 - ov))

    print("Both teams to score:")
    bt = cal(m_btts(g), "btts")
    print(_line("BTTS - Yes", bt))
    print(_line("BTTS - No", 1 - bt))

    # count markets: expected per team + over/unders at lines near the expectation
    for name, label, lines in (("corners", "Corners", (9.5, 10.5)),
                               ("cards", "Cards / bookings", (3.5, 4.5)),
                               ("shots", "Shots", (22.5, 25.5)),
                               ("sot", "Shots on target", (7.5, 9.5)),
                               ("fouls", "Fouls", (19.5, 22.5))):
        ls = model.count_lambdas(name, home, away)
        if ls is None:
            continue
        grid = model.count_grid(name, home, away)
        print(f"{label}:  expected {home[:12]} {ls[0]:.1f} - {ls[1]:.1f} {away[:12]}")
        for ln in lines:
            print(_line(f"Over {ln}", m_over(grid, ln)))

    ps = model.possession_share(home, away)
    if ps is not None:
        print(f"Possession (unvalidated estimate):  "
              f"{home[:12]} {ps[0]*100:.0f}% - {ps[1]*100:.0f}% {away[:12]}")


def run(folder, demo_n=3):
    data = load_matches(folder)
    model = Model(neutral=False, **BEST)
    # train on all but the last demo_n, then print cards for those (real odds exist)
    for m in data[:-demo_n]:
        model.update(m)
    for m in data[-demo_n:]:
        card(model, m["home"], m["away"], m["odds"])
        print(f"  actual result: {m['home']} {m['fthg']}-{m['ftag']} {m['away']}")
        model.update(m)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
