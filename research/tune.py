"""
tune.py  —  knob sweeps for ODDS ACCURACY (research only)
---------------------------------------------------------
We've shown the model can't beat the closing line, so this is NOT about value.
It's about making the published odds as accurate as possible (lower Brier, better
calibration, and killing the goals-too-hot bias) for the dashboard predictor.

Sweeps each knob one at a time around the current defaults and reports, walk-forward
over all seasons:
    acc       1X2 outcome accuracy
    Brier     1X2 multiclass Brier (lower = better; main metric)
    ECE       raw 1X2 calibration error (lower = better)
    totbias   mean model P(over 2.5) - actual over-rate (0 = unbiased totals)

USAGE:  python research/tune.py research/seasons/
"""

import sys

from footy_model import Model, m_result, m_over, load_matches
from value_backtest import ece, result_idx

DEFAULTS = dict(k=5.0, xg_w=0.5, elo_sup=0.10, rho=0.08)


def evaluate(data, k, xg_w, elo_sup, rho, xg_meanmatch=True, score_from=0):
    model = Model(k=k, xg_w=xg_w, elo_sup=elo_sup, rho=rho, neutral=False,
                  xg_meanmatch=xg_meanmatch)
    brier = acc = n = 0.0
    res_pairs = []
    over_pred = over_act = 0.0
    for idx, m in enumerate(data):
        g = model.goal_grid(m["home"], m["away"])
        if g is not None and idx >= score_from:
            p, y = m_result(g), result_idx(m)
            brier += sum((p[i] - (1 if i == y else 0)) ** 2 for i in range(3))
            acc += 1 if max(range(3), key=lambda i: p[i]) == y else 0
            for i in range(3):
                res_pairs.append((p[i], 1 if i == y else 0))
            over_pred += m_over(g, 2.5)
            over_act += 1 if (m["fthg"] + m["ftag"]) > 2.5 else 0
            n += 1
        model.update(m)
    return dict(n=int(n), acc=acc / n, brier=brier / n,
                ece=ece(res_pairs), totbias=(over_pred - over_act) / n)


def sweep(data, knob, values):
    print(f"\nSweep {knob}  (others at default {DEFAULTS}):")
    print(f"  {knob:>8s} {'acc':>7s} {'Brier':>7s} {'ECE':>7s} {'totbias':>8s}")
    rows = []
    for v in values:
        kw = dict(DEFAULTS, **{knob: v})
        r = evaluate(data, **kw)
        rows.append((v, r))
    best = min(rows, key=lambda x: x[1]["brier"])[0]
    for v, r in rows:
        mark = "  <- best Brier" if v == best else ""
        print(f"  {v:8.2f} {r['acc']:7.3f} {r['brier']:7.3f} "
              f"{r['ece']:7.3f} {r['totbias']:+8.3f}{mark}")
    return best


if __name__ == "__main__":
    data = load_matches(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")

    print("=" * 60)
    print(f"DEFAULT KNOBS {DEFAULTS}")
    off = evaluate(data, **DEFAULTS, xg_meanmatch=False)
    on = evaluate(data, **DEFAULTS, xg_meanmatch=True)
    print(f"  xG mean-match OFF: acc {off['acc']:.3f}  Brier {off['brier']:.3f}  "
          f"ECE {off['ece']:.3f}  totbias {off['totbias']:+.3f}")
    print(f"  xG mean-match ON : acc {on['acc']:.3f}  Brier {on['brier']:.3f}  "
          f"ECE {on['ece']:.3f}  totbias {on['totbias']:+.3f}")
    base = on
    print("=" * 60)

    best = {}
    best["k"] = sweep(data, "k", [2, 3, 4, 5, 6, 8, 10])
    best["xg_w"] = sweep(data, "xg_w", [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8])
    best["elo_sup"] = sweep(data, "elo_sup", [0.0, 0.05, 0.10, 0.15, 0.20, 0.30])
    best["rho"] = sweep(data, "rho", [-0.05, 0.0, 0.05, 0.08, 0.10, 0.15])

    combo = dict(DEFAULTS, **best)
    r = evaluate(data, **combo)
    print("\n" + "=" * 60)
    print(f"BEST-OF-EACH COMBINED (full-sample) {combo}")
    print(f"  acc {r['acc']:.3f}  Brier {r['brier']:.3f}  "
          f"ECE {r['ece']:.3f}  totbias {r['totbias']:+.3f}")
    print(f"  vs default: Brier {base['brier']:.3f} -> {r['brier']:.3f}  "
          f"({(r['brier']-base['brier']):+.3f}),  "
          f"totbias {base['totbias']:+.3f} -> {r['totbias']:+.3f}")

    # ---- out-of-sample check: re-select knobs on first 60%, score last 40% -- #
    print("\n" + "=" * 60)
    print("OUT-OF-SAMPLE CHECK (select knobs on first 60%, score held-out last 40%)")
    cut = int(len(data) * 0.6)
    train = data[:cut]
    sel = {}
    sel["k"] = min([2, 3, 4, 5, 6, 8, 10],
                   key=lambda v: evaluate(train, **dict(DEFAULTS, k=v))["brier"])
    sel["xg_w"] = min([0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8],
                      key=lambda v: evaluate(train, **dict(DEFAULTS, xg_w=v))["brier"])
    sel["elo_sup"] = min([0.0, 0.05, 0.10, 0.15, 0.20, 0.30],
                         key=lambda v: evaluate(train, **dict(DEFAULTS, elo_sup=v))["brier"])
    sel["rho"] = min([-0.05, 0.0, 0.05, 0.08, 0.10, 0.15],
                     key=lambda v: evaluate(train, **dict(DEFAULTS, rho=v))["brier"])
    tuned = dict(DEFAULTS, **sel)
    d_hold = evaluate(data, **DEFAULTS, score_from=cut)
    t_hold = evaluate(data, **tuned, score_from=cut)
    print(f"  knobs selected on train: {sel}")
    print(f"  HOLDOUT default: acc {d_hold['acc']:.3f}  Brier {d_hold['brier']:.3f}  "
          f"ECE {d_hold['ece']:.3f}  totbias {d_hold['totbias']:+.3f}")
    print(f"  HOLDOUT tuned  : acc {t_hold['acc']:.3f}  Brier {t_hold['brier']:.3f}  "
          f"ECE {t_hold['ece']:.3f}  totbias {t_hold['totbias']:+.3f}")
    print("=" * 60)
