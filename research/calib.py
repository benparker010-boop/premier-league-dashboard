"""
calib.py  —  Platt recalibration layer for displayed probabilities (research only)
----------------------------------------------------------------------------------
The raw model is mildly over-confident (all A < 1). These Platt coefficients
(y ~ sigmoid(A*logit(p) + B)) were fitted walk-forward on all 3,704 predictable
fixtures across the 10 PL seasons with the validated config (k=8, xg_w=0.7,
elo_sup=0.10, rho=0); the approach was holdout-validated in value_backtest.py
(1X2 ECE 0.035 -> 0.006). Applied at the DISPLAY layer only — the score grid
itself stays raw so scorelines remain internally consistent.

Fitted on PL data; applied to WC output too (Platt-on-logit is a mild, robust
squeeze toward the mean — the direction of the correction transfers even if the
exact magnitude is league-specific).

Refit after engine changes:  python research/calib.py research/seasons/
"""

from value_backtest import apply_platt

# market -> (A, B), fitted 2026-07-06 on E0_1415..E0_2324
CAL = {
    "1x2":  (0.9620, -0.0242),
    "ou25": (0.8981, +0.0439),
    "btts": (0.8251, +0.0394),
}


def cal(p, market):
    """Recalibrate one probability for a market ('1x2' | 'ou25' | 'btts')."""
    return apply_platt(p, CAL[market])


def cal_result(probs):
    """Recalibrate the three 1X2 probs and renormalise to sum 1."""
    c = [cal(p, "1x2") for p in probs]
    s = sum(c) or 1.0
    return [x / s for x in c]


if __name__ == "__main__":
    import sys
    from footy_model import Model, m_result, m_over, m_btts, load_matches
    from value_backtest import fit_calibrators

    data = load_matches(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
    model = Model(neutral=False, k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)
    recs = []
    for m in data:
        g = model.goal_grid(m["home"], m["away"])
        if g is not None:
            recs.append({"m": m, "result": m_result(g),
                         "over25": m_over(g, 2.5), "btts": m_btts(g)})
        model.update(m)
    cals = fit_calibrators(recs)
    print(f"fitted on {len(recs)} fixtures — paste into CAL:")
    for k, (A, B) in cals.items():
        print(f'    "{k}":  ({A:.4f}, {B:+.4f}),')
