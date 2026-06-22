"""
footy_backtest.py  (v2 — feature ablation)
------------------------------------------
Walk-forward backtest of the match predictor on real football-data.co.uk CSVs,
testing each upgrade so you can see which actually improve out-of-sample accuracy
at scale: shrinkage, recency weighting, an xG-proxy signal, an Elo prior, and
opponent-strength adjustment.

USAGE (Terminal tab inside PyCharm):
    1. Download season CSVs from https://www.football-data.co.uk/englandm.php
       (the "Premier League" links). Put them all in one folder, e.g. seasons/
    2. python footy_backtest.py seasons/
"""

import sys
import os
import glob
import math
import csv


def load(folder):
    rows, files = [], sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        sys.exit(f"No CSV files in {folder}")
    for f in files:
        with open(f, newline="", encoding="latin-1") as fh:
            for r in csv.DictReader(fh):
                try:
                    rows.append((r["HomeTeam"], r["AwayTeam"], int(float(r["FTHG"])),
                                 int(float(r["FTAG"])), int(float(r["HS"])), int(float(r["AS"])),
                                 int(float(r["HST"])), int(float(r["AST"]))))
                except (ValueError, KeyError):
                    continue
    print(f"Loaded {len(rows)} matches from {len(files)} file(s).\n")
    return rows


def pmf(k, l):
    return math.exp(-l) * l ** k / math.factorial(k)


def outcome(lh, la, mx=10):
    ph = [pmf(i, lh) for i in range(mx + 1)]
    pa = [pmf(i, la) for i in range(mx + 1)]
    H = D = A = 0.0
    for i in range(mx + 1):
        for j in range(mx + 1):
            p = ph[i] * pa[j]
            if i > j:
                H += p
            elif i == j:
                D += p
            else:
                A += p
    return [H, D, A]


def elo_probs(d):
    e = 1 / (1 + 10 ** (-d / 400))
    pd_ = 0.30 * math.exp(-((e - 0.5) ** 2) / 0.10)
    pH, pA = max(0.0, e - pd_ / 2), max(0.0, 1 - e - pd_ / 2)
    s = pH + pd_ + pA
    return [pH / s, pd_ / s, pA / s]


def run(data, xg_w=0.0, recency=0.0, use_elo=0.0, opp_adj=False, k=5.0, min_g=4):
    # Two parallel strength accumulators — goals and an xG-proxy from shots — so we can
    # blend their lambdas exactly like app.py's predict_fixture does (weight xg_w on xG).
    Fg, Adg, Fx, Adx, G = {}, {}, {}, {}, {}
    totg = hsg = asg = totx = hsx = asx = 0.0
    n = 0
    elo = {}
    acc = tot_o = 0
    briers, gmae, base_b = [], [], []
    rate = [0, 0, 0]

    def xgproxy(hsh, ash, hst, ast):
        return (0.34 * hst + 0.043 * (hsh - hst), 0.34 * ast + 0.043 * (ash - ast))

    for m in data:
        h, a = m[0], m[1]
        gh, ga = G.get(h, 0), G.get(a, 0)
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)
        if n > 0 and gh >= min_g and ga >= min_g:
            def lambdas(F, Ad, tot, hs, as_):
                avg = tot / (2 * n)
                hf = max(0.6, min(1.6, (hs / n) / (as_ / n))) if as_ > 0 else 1.0

                def fac(t, d):
                    g = G[t]
                    raw = (d[t] / g) / avg if avg > 0 and g > 0 else 1.0
                    w = g / (g + k)
                    return w * raw + (1 - w)

                return (avg * fac(h, F) * fac(a, Ad) * math.sqrt(hf),
                        avg * fac(a, F) * fac(h, Ad) / math.sqrt(hf))

            lh, la = lambdas(Fg, Adg, totg, hsg, asg)
            if xg_w > 0:                                   # blend xG-proxy lambdas on top
                lhx, lax = lambdas(Fx, Adx, totx, hsx, asx)
                lh = (1 - xg_w) * lh + xg_w * lhx
                la = (1 - xg_w) * la + xg_w * lax
            if opp_adj:
                sup = (eh - ea + 60) / 400.0
                lh *= 10 ** (0.10 * sup)
                la *= 10 ** (-0.10 * sup)
            lh, la = max(.05, lh), max(.05, la)
            pP = outcome(lh, la)
            p = [use_elo * elo_probs(eh - ea + 60)[i] + (1 - use_elo) * pP[i] for i in range(3)] if use_elo > 0 else pP
            res = 0 if m[2] > m[3] else (1 if m[2] == m[3] else 2)
            if max(range(3), key=lambda i: p[i]) == res:
                acc += 1
            tot_o += 1
            briers.append(sum((p[i] - (1 if i == res else 0)) ** 2 for i in range(3)))
            gmae += [abs(lh - m[2]), abs(la - m[3])]
            tr = sum(rate) or 1
            bp = [rate[0] / tr, rate[1] / tr, rate[2] / tr]
            base_b.append(sum((bp[i] - (1 if i == res else 0)) ** 2 for i in range(3)))
        if recency > 0:
            for d in (Fg, Adg, Fx, Adx):
                for t in d:
                    d[t] *= recency
            totg *= recency; hsg *= recency; asg *= recency
            totx *= recency; hsx *= recency; asx *= recency
        gh_, ga_ = m[2], m[3]                              # goals signal
        xh, xa = xgproxy(*m[4:])                           # xG-proxy signal
        Fg[h] = Fg.get(h, 0) + gh_; Adg[h] = Adg.get(h, 0) + ga_
        Fg[a] = Fg.get(a, 0) + ga_; Adg[a] = Adg.get(a, 0) + gh_
        Fx[h] = Fx.get(h, 0) + xh; Adx[h] = Adx.get(h, 0) + xa
        Fx[a] = Fx.get(a, 0) + xa; Adx[a] = Adx.get(a, 0) + xh
        totg += gh_ + ga_; hsg += gh_; asg += ga_
        totx += xh + xa; hsx += xh; asx += xa
        gd = abs(m[2] - m[3]); mult = math.log(gd + 1) + 1
        sc = 1.0 if m[2] > m[3] else (0.5 if m[2] == m[3] else 0.0)
        exp = 1 / (1 + 10 ** (-(eh - ea + 60) / 400))
        chg = 20 * mult * (sc - exp)
        elo[h] = eh + chg; elo[a] = ea - chg
        G[h] = gh + 1; G[a] = ga + 1; n += 1
        rate[0 if m[2] > m[3] else (1 if m[2] == m[3] else 2)] += 1

    mean = lambda x: sum(x) / len(x) if x else float("nan")
    return tot_o, acc / tot_o, mean(briers), mean(gmae), mean(base_b)


if __name__ == "__main__":
    data = load(sys.argv[1] if len(sys.argv) > 1 else ".")
    configs = [
        ("base (shrinkage, goals)", dict()),
        ("+ recency weighting", dict(recency=0.985)),
        ("+ xG blend (w=0.5, app)", dict(xg_w=0.5)),
        ("+ Elo blend (w=0.4)", dict(use_elo=0.4)),
        ("+ opponent adjustment", dict(opp_adj=True)),
        ("ALL combined", dict(xg_w=0.5, recency=0.985, use_elo=0.4, opp_adj=True)),
    ]
    print(f"{'config':32s} {'n':>5s} {'acc':>7s} {'brier':>7s} {'gMAE':>6s}")
    base_b = 0
    for name, kw in configs:
        n, acc, br, gm, base_b = run(data, **kw)
        print(f"{name:32s} {n:5d} {acc:7.3f} {br:7.3f} {gm:6.3f}")
    print(f"{'(naive base-rate Brier)':32s} {'':5s} {'':7s} {base_b:7.3f}")

    # Elo-blend weight sweep: find the optimum mix of Elo prior vs Poisson model.
    print(f"\nElo-blend weight sweep (xG off):")
    print(f"{'use_elo':32s} {'n':>5s} {'acc':>7s} {'brier':>7s} {'gMAE':>6s}")
    for w in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        n, acc, br, gm, _ = run(data, use_elo=w)
        print(f"{('  w = %.1f' % w):32s} {n:5d} {acc:7.3f} {br:7.3f} {gm:6.3f}")

    # xG-mix weight sweep, held at the chosen Elo weight (as the live app combines them).
    print(f"\nxG-mix weight sweep (Elo w=0.4):")
    print(f"{'xg_w':32s} {'n':>5s} {'acc':>7s} {'brier':>7s} {'gMAE':>6s}")
    for w in (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
        n, acc, br, gm, _ = run(data, xg_w=w, use_elo=0.4)
        print(f"{('  xg_w = %.1f' % w):32s} {n:5d} {acc:7.3f} {br:7.3f} {gm:6.3f}")
