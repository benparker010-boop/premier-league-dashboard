"""
value_backtest.py  —  validation report for the multi-market value finder
--------------------------------------------------------------------------
Walk-forward over the football-data.co.uk season CSVs and answer three honest
questions:

  1. ARE THE PROBABILITIES TRUSTWORTHY?  Reliability table + ECE + Brier, and a
     Platt (logistic) recalibration fit on a training split.
  2. ARE THEY AS SHARP AS THE MARKET?    Model Brier/accuracy vs the de-vigged
     Bet365 and Pinnacle CLOSING lines (the sharpest public estimate).
  3. IS THERE REAL MONEY IN THE DISAGREEMENTS?  Bet every flagged value pick into
     real closing odds; report ROI / P&L vs flat-betting everything.

CALIBRATE-BEFORE-EDGE: edges and value flags are computed from RECALIBRATED
probabilities, not the raw (over-confident) model output, so we don't invent
edges out of mis-calibration. The calibrator is fit on the first `train_frac` of
fixtures and every value number is reported on the unseen holdout only.

Real bookmaker odds in these CSVs exist only for 1X2 and Over/Under 2.5 goals, so
those are the only markets with a money backtest. BTTS is shown calibration-only
(no CSV odds) to prove the no-odds markets are still accurate.

USAGE:  python research/value_backtest.py research/seasons/
"""

import sys
import math

from footy_model import Model, m_result, m_over, m_btts, load_matches
from odds_tools import devig_proportional, value_flag


# --------------------------------------------------------------------------- #
#  Calibration helpers                                                         #
# --------------------------------------------------------------------------- #
def reliability(pairs, bins=10):
    """pairs = [(predicted_prob, outcome 0/1)]. Return per-bin (lo, n, mean_p, freq)."""
    buckets = [[] for _ in range(bins)]
    for p, y in pairs:
        b = min(bins - 1, int(p * bins))
        buckets[b].append((p, y))
    out = []
    for b in range(bins):
        bk = buckets[b]
        if bk:
            mp = sum(p for p, _ in bk) / len(bk)
            fr = sum(y for _, y in bk) / len(bk)
            out.append((b / bins, len(bk), mp, fr))
    return out


def ece(pairs, bins=10):
    """Expected calibration error: avg |predicted - observed|, weighted by bin size."""
    rel = reliability(pairs, bins)
    n = sum(r[1] for r in rel) or 1
    return sum(r[1] * abs(r[2] - r[3]) for r in rel) / n


def print_reliability(title, pairs):
    print(f"\n{title}  (ECE={ece(pairs):.3f}, n={len(pairs)})")
    print(f"  {'prob bin':>10s} {'n':>6s} {'predicted':>10s} {'actual':>8s}")
    for lo, n, mp, fr in reliability(pairs):
        bar = "#" * round(fr * 20)
        print(f"  {lo:>5.1f}-{lo+0.1:>4.1f} {n:6d} {mp:10.3f} {fr:8.3f}  {bar}")


# --------------------------------------------------------------------------- #
#  Platt (logistic) recalibration                                             #
# --------------------------------------------------------------------------- #
def _logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


def _sig(z):
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1 / (1 + math.exp(-z))


def fit_platt(pairs, iters=4000, lr=0.05):
    """Fit y ~ sigmoid(A*logit(p) + B) by gradient descent. Returns (A, B)."""
    A, B = 1.0, 0.0
    n = len(pairs) or 1
    xs = [(_logit(p), y) for p, y in pairs]
    for _ in range(iters):
        gA = gB = 0.0
        for x, y in xs:
            pred = _sig(A * x + B)
            gA += (pred - y) * x
            gB += (pred - y)
        A -= lr * gA / n
        B -= lr * gB / n
    return A, B


def apply_platt(p, ab):
    return _sig(ab[0] * _logit(p) + ab[1])


# ---- per-market calibrated-probability accessors -------------------------- #
def result_idx(m):
    return 0 if m["fthg"] > m["ftag"] else (1 if m["fthg"] == m["ftag"] else 2)


def cal_result(probs, ab):
    """Recalibrate the three 1X2 probs and renormalise back to sum 1."""
    c = [apply_platt(p, ab) for p in probs]
    s = sum(c) or 1.0
    return [x / s for x in c]


def market_probs(rec, market, cals):
    """Return (probs, realised_outcome_index). cals=None -> raw model probs."""
    m = rec["m"]
    if market == "1x2":
        probs = rec["result"] if cals is None else cal_result(rec["result"], cals["1x2"])
        return probs, result_idx(m)
    if market == "ou25":
        over = rec["over25"] if cals is None else apply_platt(rec["over25"], cals["ou25"])
        return [over, 1 - over], (0 if (m["fthg"] + m["ftag"]) > 2.5 else 1)
    raise ValueError(market)


def fit_calibrators(train):
    """Fit one Platt scaler per market on the training fixtures."""
    p1, po, pb = [], [], []
    for r in train:
        m = r["m"]
        y = result_idx(m)
        for i in range(3):
            p1.append((r["result"][i], 1 if i == y else 0))
        po.append((r["over25"], 1 if (m["fthg"] + m["ftag"]) > 2.5 else 0))
        pb.append((r["btts"], 1 if (m["fthg"] >= 1 and m["ftag"] >= 1) else 0))
    return {"1x2": fit_platt(p1), "ou25": fit_platt(po), "btts": fit_platt(pb)}


# --------------------------------------------------------------------------- #
#  Main backtest                                                               #
# --------------------------------------------------------------------------- #
def run(folder, threshold=0.05, k=8, xg_w=0.7, elo_sup=0.10, rho=0.0, train_frac=0.6):
    data = load_matches(folder)
    model = Model(k=k, xg_w=xg_w, elo_sup=elo_sup, rho=rho, neutral=False)

    recs = []
    for m in data:
        g = model.goal_grid(m["home"], m["away"])
        if g is not None:
            recs.append({"m": m, "result": m_result(g),
                         "over25": m_over(g, 2.5), "btts": m_btts(g)})
        model.update(m)

    print("=" * 70)
    print(f"VALIDATION REPORT  -  {len(recs)} predicted fixtures")
    print(f"knobs: k={k}  xg_w={xg_w}  elo_sup={elo_sup}  rho={rho}  "
          f"value threshold={threshold:.0%}")
    print("=" * 70)

    # ---- 1X2 raw calibration + closing-line benchmark (full sample) ------- #
    res_pairs, model_brier, acc = [], 0.0, 0
    for r in recs:
        y, p = result_idx(r["m"]), r["result"]
        for i in range(3):
            res_pairs.append((p[i], 1 if i == y else 0))
        model_brier += sum((p[i] - (1 if i == y else 0)) ** 2 for i in range(3))
        acc += 1 if max(range(3), key=lambda i: p[i]) == y else 0
    model_brier /= len(recs)
    print(f"\n--- MARKET: Match result (1X2) ---")
    print(f"model (raw): accuracy {acc/len(recs):.3f}   Brier {model_brier:.3f}")
    print_reliability("1X2 reliability (raw model)", res_pairs)
    benchmark_lines(recs)

    # ---- fit calibrators on training split -------------------------------- #
    split = int(len(recs) * train_frac)
    train, hold = recs[:split], recs[split:]
    cals = fit_calibrators(train)
    print(f"\nCalibrators fit on first {len(train)} fixtures; "
          f"evaluating value on the held-out last {len(hold)}.")
    print(f"  Platt params:  1X2 {fmt_ab(cals['1x2'])}   "
          f"O/U2.5 {fmt_ab(cals['ou25'])}   BTTS {fmt_ab(cals['btts'])}")

    # ---- holdout calibration: raw vs calibrated --------------------------- #
    calibration_gain(hold, cals)

    # ---- value betting on holdout: bet OPENING odds, measure CLV ---------- #
    print(f"\n--- VALUE BETTING (holdout, bet into Bet365 OPENING odds, edge>{threshold:.0%}) ---")
    print("  Realistic test: take the soft opening price, settle on the result, and")
    print("  measure closing-line value (CLV) against the sharp closing line.")
    print("  CLV-EV = (closing de-vigged prob x opening odds) - 1; >0 means we beat the close.")
    for calibrated in (True, False):
        tag = "calibrated" if calibrated else "raw model "
        print(f"\n  [{tag}]")
        value_report(hold, threshold, cals if calibrated else None)


def fmt_ab(ab):
    return f"(A={ab[0]:.2f},B={ab[1]:+.2f})"


def benchmark_lines(recs):
    """Model 1X2 vs de-vigged Bet365 / Pinnacle CLOSING lines on the same fixtures."""
    print(f"\nClosing-line benchmark (de-vigged), 1X2 Brier + accuracy:")
    for book in ("b365", "pin", "avg"):
        mb = bb = 0.0
        ma = ba = nn = 0
        for r in recs:
            o = r["m"]["odds"]["1x2_close"].get(book)
            if not o:
                continue
            y = result_idx(r["m"])
            mp, bp = r["result"], devig_proportional(list(o))
            mb += sum((mp[i] - (1 if i == y else 0)) ** 2 for i in range(3))
            bb += sum((bp[i] - (1 if i == y else 0)) ** 2 for i in range(3))
            ma += 1 if max(range(3), key=lambda i: mp[i]) == y else 0
            ba += 1 if max(range(3), key=lambda i: bp[i]) == y else 0
            nn += 1
        if nn:
            print(f"  vs {book:5s} (n={nn:4d}): "
                  f"model Brier {mb/nn:.3f} / acc {ma/nn:.3f}   |   "
                  f"line Brier {bb/nn:.3f} / acc {ba/nn:.3f}")


def calibration_gain(hold, cals):
    """Holdout ECE, raw vs calibrated, per market."""
    print(f"\nHoldout calibration (ECE), raw -> calibrated:")
    # 1X2 (pooled outcomes)
    raw1, cal1 = [], []
    for r in hold:
        y, cp = result_idx(r["m"]), cal_result(r["result"], cals["1x2"])
        for i in range(3):
            raw1.append((r["result"][i], 1 if i == y else 0))
            cal1.append((cp[i], 1 if i == y else 0))
    print(f"  1X2   : {ece(raw1):.3f} -> {ece(cal1):.3f}")
    # binary markets
    rawo, calo = [], []
    for r in hold:
        probs, y = market_probs(r, "ou25", None)   # raw over prob, index 0 = over
        over_hit = 1 if y == 0 else 0
        rawo.append((probs[0], over_hit))
        calo.append((apply_platt(probs[0], cals["ou25"]), over_hit))
    print(f"  O/U2.5: {ece(rawo):.3f} -> {ece(calo):.3f}")
    # BTTS (no odds, calibration only)
    rawb, calb = [], []
    for r in hold:
        y = 1 if (r["m"]["fthg"] >= 1 and r["m"]["ftag"] >= 1) else 0
        rawb.append((r["btts"], y))
        calb.append((apply_platt(r["btts"], cals["btts"]), y))
    print(f"  BTTS  : {ece(rawb):.3f} -> {ece(calb):.3f}   (no odds: accuracy proof only)")


def value_report(recs, threshold, cals):
    """Bet flagged picks into Bet365 OPENING odds; settle on result and on CLV.

    Flag uses the OPENING de-vigged line (the soft price, where edges live before
    the market sharpens). CLV-EV uses the CLOSING de-vigged prob as the truth.
    """
    for market, label in (("1x2", "Match result"), ("ou25", "Over/Under 2.5")):
        okey = "1x2" if market == "1x2" else "ou25"
        v_n = v_stake = v_pnl = 0.0
        f_stake = f_pnl = 0.0
        clv_sum = clv_n = beat = 0.0
        for r in recs:
            o_open = r["m"]["odds"][okey + "_open"].get("b365")
            o_close = r["m"]["odds"][okey + "_close"].get("b365")
            if not o_open:
                continue
            probs, y = market_probs(r, market, cals)
            devig_open = devig_proportional(list(o_open))
            devig_close = devig_proportional(list(o_close)) if o_close else None
            for i in range(len(probs)):
                raw = o_open[i]
                won = 1 if i == y else 0
                f_stake += 1
                f_pnl += (raw - 1) if won else -1
                if value_flag(probs[i], raw, devig_open[i], threshold):
                    v_stake += 1
                    v_pnl += (raw - 1) if won else -1
                    v_n += 1
                    if devig_close:
                        clv_sum += devig_close[i] * raw - 1   # beat the close if >0
                        clv_n += 1
                        beat += 1 if raw > o_close[i] else 0
        v_roi = (v_pnl / v_stake * 100) if v_stake else float("nan")
        f_roi = (f_pnl / f_stake * 100) if f_stake else float("nan")
        flag_rate = (v_stake / f_stake * 100) if f_stake else float("nan")
        clv = (clv_sum / clv_n * 100) if clv_n else float("nan")
        beat_pct = (beat / clv_n * 100) if clv_n else float("nan")
        print(f"    {label:15s}: {int(v_n):4d} bets ({flag_rate:3.0f}% flagged)  "
              f"ROI {v_roi:+6.1f}% [flat {f_roi:+5.1f}%]   "
              f"CLV-EV {clv:+5.1f}%  beat-close {beat_pct:3.0f}%")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "research/seasons/"
    run(folder)
