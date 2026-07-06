"""
blend_tune.py  —  how much market to mix into the model? (research only)
------------------------------------------------------------------------
value_backtest.py proved the de-vigged market consensus is sharper than the
model (1X2 Brier ~0.564 vs ~0.575). So when odds exist, the most accurate
displayed probability is a BLEND:  p = w*market + (1-w)*model. This tunes w
walk-forward on the PL seasons against the de-vigged closing consensus (the
'avg' columns — the closest analog to the live multi-book consensus the WC
pipeline pulls from The Odds API), selects on the first 60% of fixtures, and
confirms on the 40% holdout. Model probs are Platt-calibrated first (calib.py),
matching how they are displayed.

USAGE:  python research/blend_tune.py research/seasons/
"""

import sys

from footy_model import Model, m_result, m_over, m_btts, load_matches
from odds_tools import devig_proportional
from value_backtest import ece, result_idx
from calib import cal_result

KNOBS = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)


def collect(data):
    """Walk-forward: (calibrated model 1X2, de-vigged closing consensus, outcome)."""
    model = Model(neutral=False, **KNOBS)
    recs = []
    for m in data:
        g = model.goal_grid(m["home"], m["away"])
        o = m["odds"]["1x2_close"].get("avg")
        if g is not None and o:
            recs.append((cal_result(m_result(g)),
                         devig_proportional(list(o)), result_idx(m)))
        model.update(m)
    return recs


def score(recs, w):
    brier = acc = 0.0
    pairs = []
    for mp, bp, y in recs:
        p = [w * bp[i] + (1 - w) * mp[i] for i in range(3)]
        brier += sum((p[i] - (1 if i == y else 0)) ** 2 for i in range(3))
        acc += 1 if max(range(3), key=lambda i: p[i]) == y else 0
        pairs += [(p[i], 1 if i == y else 0) for i in range(3)]
    n = len(recs)
    return dict(brier=brier / n, acc=acc / n, ece=ece(pairs))


def run(folder):
    recs = collect(load_matches(folder))
    cut = int(len(recs) * 0.6)
    train, hold = recs[:cut], recs[cut:]
    print(f"{len(recs)} fixtures with closing consensus odds "
          f"(train {len(train)}, holdout {len(hold)})\n")
    print(f"  {'w (market share)':>16s} {'train Brier':>12s} {'hold Brier':>11s} "
          f"{'hold acc':>9s} {'hold ECE':>9s}")
    best_w, best_b = 0.0, 1e9
    for wi in range(11):
        w = wi / 10
        t = score(train, w)
        h = score(hold, w)
        mark = ""
        if t["brier"] < best_b:
            best_w, best_b, mark = w, t["brier"], "  <- best train"
        print(f"  {w:16.1f} {t['brier']:12.4f} {h['brier']:11.4f} "
              f"{h['acc']:9.3f} {h['ece']:9.4f}{mark}")
    h0, hb = score(hold, 0.0), score(hold, best_w)
    print(f"\nHOLDOUT: model-only Brier {h0['brier']:.4f}  ->  blend w={best_w:.1f} "
          f"Brier {hb['brier']:.4f}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
