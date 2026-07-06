"""
disp_tune.py  —  negative-binomial dispersion tuning for count markets (research only)
--------------------------------------------------------------------------------------
Real shot/corner/foul counts are OVER-DISPERSED vs Poisson (variance > mean), so
pure-Poisson over/under probabilities are too confident at high and low lines —
visible as tail miscalibration in markets_report.py. The negative binomial adds
one dispersion knob r per market (variance = lam + lam^2/r; r=inf is Poisson).

This sweeps r per market, walk-forward over all seasons, scoring each candidate
on a POOL of over/under lines (not just the headline line, so the tails count).
Selection on the first 60% of fixtures by pooled Brier; the last 40% is the
holdout that decides whether the winner generalises. The model's expected counts
(lambdas) don't depend on r, so we run the model once and sweep r over the
cached lambdas.

USAGE:  python research/disp_tune.py research/seasons/
"""

import sys

from footy_model import Model, nb_pmf, pois_pmf, load_matches
from value_backtest import ece

KNOBS = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)

LINES = {
    "corners": (7.5, 9.5, 11.5, 13.5),
    "cards":   (1.5, 3.5, 5.5),
    "shots":   (19.5, 23.5, 27.5, 31.5),
    "sot":     (5.5, 8.5, 11.5),
    "fouls":   (16.5, 20.5, 24.5),
}
R_GRID = (3.0, 5.0, 8.0, 12.0, 20.0, 40.0, None)   # None = Poisson


def collect(data):
    """One walk-forward pass; per market cache (lam_home, lam_away, actual total)."""
    model = Model(neutral=False, **KNOBS)
    obs = {name: [] for name in LINES}
    for m in data:
        for name in LINES:
            hv, av = Model.COUNTS[name][0](m)
            if hv is None or av is None:
                continue
            ls = model.count_lambdas(name, m["home"], m["away"])
            if ls is not None:
                obs[name].append((ls[0], ls[1], hv + av))
        model.update(m)
    return obs


def over_probs(la, lb, r, lines):
    """P(home+away > line) for each line, via exact convolution up to the
    largest line (deeper tail mass is 'over' by definition)."""
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


def pooled(obs_slice, r, lines):
    """(Brier, ECE) pooled across all lines for one market slice."""
    pairs = []
    for la, lb, actual in obs_slice:
        ps = over_probs(la, lb, r, lines)
        for line, p in ps.items():
            pairs.append((p, 1 if actual > line else 0))
    brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs)
    return brier, ece(pairs)


def run(folder):
    data = load_matches(folder)
    obs = collect(data)

    print("=" * 72)
    print(f"NB DISPERSION SWEEP  (config {KNOBS}; select on first 60% by pooled "
          f"Brier,\n confirm on last 40% holdout; r=Poisson means no NB)")
    print("=" * 72)
    chosen = {}
    for name, lines in LINES.items():
        o = obs[name]
        cut = int(len(o) * 0.6)
        train, hold = o[:cut], o[cut:]
        print(f"\n--- {name.upper()}  (n={len(o)}, lines {lines}) ---")
        print(f"  {'r':>8s} {'train Brier':>12s} {'train ECE':>10s}")
        best_r, best_b = None, 1e9
        for r in R_GRID:
            b, e = pooled(train, r, lines)
            tag = "Poisson" if r is None else f"{r:g}"
            mark = ""
            if b < best_b:
                best_r, best_b, mark = r, b, "  <- best"
            print(f"  {tag:>8s} {b:12.4f} {e:10.4f}{mark}")
        hb_p, he_p = pooled(hold, None, lines)
        hb_b, he_b = pooled(hold, best_r, lines)
        tag = "Poisson" if best_r is None else f"r={best_r:g}"
        print(f"  HOLDOUT: Poisson Brier {hb_p:.4f} / ECE {he_p:.4f}   "
              f"vs {tag} Brier {hb_b:.4f} / ECE {he_b:.4f}")
        chosen[name] = best_r
    print("\n" + "=" * 72)
    print("SELECTED DISPERSIONS (paste into Model.DISP if holdout confirms):")
    print("  " + repr(chosen))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
