"""
markets_report.py  —  calibration of every market (research only)
-----------------------------------------------------------------
The CSVs carry no odds for BTTS / O-U 1.5 / O-U 3.5 / corners / cards / shots /
fouls, so we can't money-backtest them — but we CAN prove they're accurate by
checking the model's probabilities against what actually happened. For each
market: a reliability table + ECE, and (for the count markets) the
predicted-vs-actual mean to confirm no systematic bias, plus per-team MAE
against the naive league-average baseline.

Uses the validated "best" config (xG mean-match on).

USAGE:  python research/markets_report.py research/seasons/
"""

import sys

from footy_model import Model, m_over, m_btts, load_matches
from value_backtest import reliability, ece

BEST = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)

# count market -> (report label, representative over/under line)
COUNT_MARKETS = {
    "corners": ("CORNERS", 9.5),
    "cards":   ("CARDS / bookings", 3.5),
    "shots":   ("TOTAL SHOTS", 24.5),
    "sot":     ("SHOTS ON TARGET", 8.5),
    "fouls":   ("FOULS", 20.5),
}


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

    ou15, ou25, ou35, btts = [], [], [], []
    cm = {name: dict(over=[], pred=0.0, act=0.0, n=0,
                     mae=0.0, mae_naive=0.0, sides=0)
          for name in COUNT_MARKETS}

    for m in data:
        g = model.goal_grid(m["home"], m["away"])
        if g is not None:
            tot = m["fthg"] + m["ftag"]
            ou15.append((m_over(g, 1.5), 1 if tot > 1.5 else 0))
            ou25.append((m_over(g, 2.5), 1 if tot > 2.5 else 0))
            ou35.append((m_over(g, 3.5), 1 if tot > 3.5 else 0))
            btts.append((m_btts(g), 1 if (m["fthg"] >= 1 and m["ftag"] >= 1) else 0))

        for name, (_label, line) in COUNT_MARKETS.items():
            hv, av = Model.COUNTS[name][0](m)
            if hv is None or av is None:
                continue
            ls = model.count_lambdas(name, m["home"], m["away"], ref=m.get("ref"))
            if ls is None:
                continue
            grid = model.count_grid(name, m["home"], m["away"], ref=m.get("ref"))
            c, actual = cm[name], hv + av
            c["over"].append((m_over(grid, line), 1 if actual > line else 0))
            c["pred"] += ls[0] + ls[1]; c["act"] += actual; c["n"] += 1
            # per-team MAE vs the naive "league average" lambda at prediction time
            st = model.cnt[name]
            naive = st["tot"] / (2 * st["n"])
            c["mae"] += abs(ls[0] - hv) + abs(ls[1] - av)
            c["mae_naive"] += abs(naive - hv) + abs(naive - av)
            c["sides"] += 2

        model.update(m)

    print("=" * 70)
    print(f"MARKET CALIBRATION REPORT  (config {BEST}, xG mean-match on)")
    print("=" * 70)

    print("\n### GOAL MARKETS (one shared score grid) ###")
    print_reliability("Over 1.5 goals", ou15)
    print_reliability("Over 2.5 goals", ou25)
    print_reliability("Over 3.5 goals", ou35)
    print_reliability("Both teams to score", btts)

    for name, (label, line) in COUNT_MARKETS.items():
        c = cm[name]
        if not c["n"]:
            print(f"\n### {label}: no data in these CSVs ###")
            continue
        print(f"\n### {label} (own shrinkage-Poisson grid) ###")
        print(f"  predicted mean total {c['pred']/c['n']:.2f}  vs actual "
              f"{c['act']/c['n']:.2f}  (bias {(c['pred']-c['act'])/c['n']:+.2f}, "
              f"n={c['n']})")
        print(f"  per-team MAE {c['mae']/c['sides']:.2f}  vs naive league-average "
              f"{c['mae_naive']/c['sides']:.2f}")
        print_reliability(f"Over {line} {name}", c["over"])


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
