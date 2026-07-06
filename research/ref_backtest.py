"""
ref_backtest.py  —  does the referee factor improve cards/fouls? (research only)
--------------------------------------------------------------------------------
Referee strictness is a large, known driver of card counts, and the referee is
announced before kickoff — legitimate walk-forward information (the Referee
column in the football-data CSVs). This tests folding a shrunk referee factor
(Model.ref_factor) into the cards and fouls lambdas.

Metrics per market, with vs without the referee: per-team MAE, and pooled
Brier/ECE over a set of over/under lines. ref_k (pseudo-games shrinking a ref
toward league average) is swept; selection on the first 60% of fixtures,
holdout on the last 40%.

USAGE:  python research/ref_backtest.py research/seasons/
"""

import sys

from footy_model import Model, load_matches, nb_pmf, pois_pmf
from value_backtest import ece

KNOBS = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)
LINES = {"cards": (1.5, 3.5, 5.5), "fouls": (16.5, 20.5, 24.5)}


def collect(data, ref_k):
    """Walk-forward: per market, (lam_h, lam_w, ref-factored lams, actuals)."""
    model = Model(neutral=False, **KNOBS)
    model.ref_k = ref_k
    obs = {name: [] for name in LINES}
    for m in data:
        for name in LINES:
            hv, av = Model.COUNTS[name][0](m)
            if hv is None or av is None:
                continue
            base = model.count_lambdas(name, m["home"], m["away"])
            wref = model.count_lambdas(name, m["home"], m["away"], ref=m.get("ref"))
            if base is not None:
                obs[name].append((base, wref, (hv, av)))
        model.update(m)
    return obs


def over_probs(la, lb, r, lines):
    lmax = int(max(lines))
    pmf = (lambda k, lam: nb_pmf(k, lam, r)) if r else pois_pmf
    ph = [pmf(i, la) for i in range(lmax + 1)]
    pa = [pmf(j, lb) for j in range(lmax + 1)]
    tot = [sum(ph[i] * pa[k - i] for i in range(k + 1)) for k in range(lmax + 1)]
    cum = []
    c = 0.0
    for t in tot:
        c += t
        cum.append(c)
    return {line: 1.0 - cum[int(line)] for line in lines}


def evaluate(slice_, name, use_ref):
    disp = Model.DISP[name]
    pairs, mae, sides = [], 0.0, 0
    for base, wref, (hv, av) in slice_:
        ls = wref if use_ref else base
        for line, p in over_probs(ls[0], ls[1], disp, LINES[name]).items():
            pairs.append((p, 1 if hv + av > line else 0))
        mae += abs(ls[0] - hv) + abs(ls[1] - av)
        sides += 2
    brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs)
    return dict(brier=brier, ece=ece(pairs), mae=mae / sides)


def run(folder):
    data = load_matches(folder)
    n_ref = sum(1 for m in data if m.get("ref"))
    print(f"{n_ref}/{len(data)} matches carry a referee name.\n")
    print(f"  {'market':8s} {'ref_k':>6s} {'':10s} {'train Brier':>12s} "
          f"{'hold Brier':>11s} {'hold ECE':>9s} {'hold MAE':>9s}")
    for name in LINES:
        best_k, best_b, cache = None, 1e9, {}
        for ref_k in (10.0, 20.0, 40.0, 80.0):
            obs = collect(data, ref_k)[name]
            cut = int(len(obs) * 0.6)
            t = evaluate(obs[:cut], name, use_ref=True)
            h = evaluate(obs[cut:], name, use_ref=True)
            cache[ref_k] = (obs, h)
            mark = ""
            if t["brier"] < best_b:
                best_k, best_b, mark = ref_k, t["brier"], "  <- best"
            print(f"  {name:8s} {ref_k:6.0f} {'with ref':10s} {t['brier']:12.4f} "
                  f"{h['brier']:11.4f} {h['ece']:9.4f} {h['mae']:9.3f}{mark}")
        obs, _h = cache[best_k]
        cut = int(len(obs) * 0.6)
        h0 = evaluate(obs[cut:], name, use_ref=False)
        hb = evaluate(obs[cut:], name, use_ref=True)
        print(f"  {name:8s} {'':6s} {'NO ref':10s} {'':12s} {h0['brier']:11.4f} "
              f"{h0['ece']:9.4f} {h0['mae']:9.3f}")
        print(f"  -> {name}: holdout Brier {h0['brier']:.4f} -> {hb['brier']:.4f}, "
              f"MAE {h0['mae']:.3f} -> {hb['mae']:.3f} at ref_k={best_k:g}\n")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
