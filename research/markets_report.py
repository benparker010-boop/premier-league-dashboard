"""
markets_report.py  —  calibration of every market (research only)
-----------------------------------------------------------------
The CSVs carry no odds for BTTS / O-U 1.5 / O-U 3.5 / corners / cards, so we
can't money-backtest them — but we CAN prove they're accurate by checking the
model's probabilities against what actually happened. For each market: a
reliability table + ECE, and (for the count markets) the predicted-vs-actual
mean to confirm no systematic bias.

Uses the validated "best" config (xG mean-match on).

USAGE:  python research/markets_report.py research/seasons/
"""

import sys

from footy_model import (Model, m_result, m_over, m_btts, score_grid,
                         load_matches, MAXC, MAXK)
from value_backtest import reliability, ece

BEST = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)


def expected_total(grid):
    return sum((i + j) * grid[i][j]
               for i in range(len(grid)) for j in range(len(grid)))


def print_reliability(title, pairs, extra=""):
    print(f"\n{title}  (ECE={ece(pairs):.3f}, n={len(pairs)}){extra}")
    print(f"  {'prob bin':>10s} {'n':>6s} {'predicted':>10s} {'actual':>8s}")
    for lo, n, mp, fr in reliability(pairs):
        print(f"  {lo:>5.1f}-{lo+0.1:>4.1f} {n:6d} {mp:10.3f} {fr:8.3f}  {'#'*round(fr*20)}")


def run(folder):
    data = load_matches(folder)
    model = Model(neutral=False, **BEST)

    # collectors
    ou15, ou25, ou35, btts = [], [], [], []
    corn_over, card_over = [], []
    corn_pred = corn_act = corn_n = 0.0
    card_pred = card_act = card_n = 0.0

    for m in data:
        g = model.goal_grid(m["home"], m["away"])
        if g is not None:
            tot = m["fthg"] + m["ftag"]
            ou15.append((m_over(g, 1.5), 1 if tot > 1.5 else 0))
            ou25.append((m_over(g, 2.5), 1 if tot > 2.5 else 0))
            ou35.append((m_over(g, 3.5), 1 if tot > 3.5 else 0))
            btts.append((m_btts(g), 1 if (m["fthg"] >= 1 and m["ftag"] >= 1) else 0))

        cg = model.corner_grid(m["home"], m["away"])
        if cg is not None and m["hc"] is not None:
            ac = m["hc"] + m["ac"]
            corn_over.append((m_over(cg, 9.5), 1 if ac > 9.5 else 0))
            corn_pred += expected_total(cg); corn_act += ac; corn_n += 1

        kg = model.card_grid(m["home"], m["away"])
        if kg is not None and None not in (m["hy"], m["ay"], m["hr"], m["ar"]):
            ak = m["hy"] + m["ay"] + m["hr"] + m["ar"]
            card_over.append((m_over(kg, 3.5), 1 if ak > 3.5 else 0))
            card_pred += expected_total(kg); card_act += ak; card_n += 1

        model.update(m)

    print("=" * 70)
    print(f"MARKET CALIBRATION REPORT  (config {BEST}, xG mean-match on)")
    print("=" * 70)

    print("\n### GOAL MARKETS (one shared score grid) ###")
    print_reliability("Over 1.5 goals", ou15)
    print_reliability("Over 2.5 goals", ou25)
    print_reliability("Over 3.5 goals", ou35)
    print_reliability("Both teams to score", btts)

    print("\n### CORNERS (own shrinkage-Poisson grid) ###")
    print(f"  predicted mean total {corn_pred/corn_n:.2f}  vs actual {corn_act/corn_n:.2f}"
          f"  (bias {(corn_pred-corn_act)/corn_n:+.2f}, n={int(corn_n)})")
    print_reliability("Over 9.5 corners", corn_over)

    print("\n### CARDS / bookings (own shrinkage-Poisson grid) ###")
    print(f"  predicted mean total {card_pred/card_n:.2f}  vs actual {card_act/card_n:.2f}"
          f"  (bias {(card_pred-card_act)/card_n:+.2f}, n={int(card_n)})")
    print_reliability("Over 3.5 cards", card_over)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
