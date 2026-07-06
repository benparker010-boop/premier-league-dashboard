"""
replay.py  —  re-play a real season and grade every prediction (research only)
------------------------------------------------------------------------------
Walk-forward replay of one season with the full validated stack (priors, xG
mean-matching, Elo supremacy, Dixon-Coles, NB count dispersion). For every match
the model predicts — using ONLY matches played before it — the result, the most
likely scoreline, and every stat market, then grades itself against what
actually happened.

History: all earlier seasons are chained with the validated prior mechanism
(reset each season, seed with last season's regressed strengths + Elo), and the
target season starts from the previous season's prior, exactly like a live
deployment would.

Baselines keep it honest: 'naive' always picks the majority outcome seen in the
earlier seasons (e.g. home win, over 9.5 corners) and uses league-average
expected values — the score to beat.

USAGE:  python research/replay.py research/seasons/ [season_name]
        (default season: the most recent CSV, e.g. E0_2324)
"""

import sys

from footy_model import (Model, m_result, m_over, m_btts, m_top_scores,
                         load_matches_by_season)
from prior_backtest import build_priors, KNOBS
from value_backtest import result_idx

G0, CARRY, ELO_CARRY = 10.0, 0.9, 0.9   # validated prior config

# binary stat markets to grade: (label, market, line)
LINES = [("Over 2.5 goals", "goals", 2.5), ("BTTS", "btts", None),
         ("Over 9.5 corners", "corners", 9.5), ("Over 3.5 cards", "cards", 3.5),
         ("Over 24.5 shots", "shots", 24.5), ("Over 8.5 SOT", "sot", 8.5),
         ("Over 20.5 fouls", "fouls", 20.5)]

# expected-value stats to grade with MAE: (label, market or 'goals')
MAES = [("Goals", "goals"), ("Shots", "shots"), ("Shots on target", "sot"),
        ("Corners", "corners"), ("Cards", "cards"), ("Fouls", "fouls")]


def actual_total(m, market):
    if market == "goals":
        return m["fthg"] + m["ftag"]
    hv, av = Model.COUNTS[market][0](m)
    return None if hv is None or av is None else hv + av


def actual_sides(m, market):
    if market == "goals":
        return m["fthg"], m["ftag"]
    return Model.COUNTS[market][0](m)


def run(folder, target=None):
    seasons = load_matches_by_season(folder)
    names = [n for n, _ in seasons]
    target = target or names[-1]
    ti = names.index(target)

    # ---- chain history up to the target season with the prior mechanism ---- #
    prev = None
    for si in range(ti):
        model = Model(neutral=False, **KNOBS)
        if prev is not None:
            teams = {m["home"] for m in seasons[si][1]} | {m["away"] for m in seasons[si][1]}
            pri, elo, lavg, xgr, hf = build_priors(prev, teams, CARRY, ELO_CARRY)
            model.inject_prior(pri, elo=elo, g0=G0, league_avg=lavg,
                               xg_ratio=xgr, home_factor=hf)
        for m in seasons[si][1]:
            model.update(m)
        prev = model

    # naive baselines from the earlier seasons: majority pick per binary market,
    # league-average expected values per stat
    hist = [m for si in range(ti) for m in seasons[si][1]]
    naive_pick, naive_lam = {}, {}
    res_counts = [0, 0, 0]
    for m in hist:
        res_counts[result_idx(m)] += 1
    naive_res = max(range(3), key=lambda i: res_counts[i])
    for label, market, line in LINES:
        if market == "btts":
            hits = sum(1 for m in hist if m["fthg"] >= 1 and m["ftag"] >= 1)
            naive_pick[label] = 1 if hits / len(hist) > 0.5 else 0
        else:
            tots = [t for t in (actual_total(m, market) for m in hist) if t is not None]
            naive_pick[label] = 1 if sum(1 for t in tots if t > line) / len(tots) > 0.5 else 0
    for label, market in MAES:
        tots = [t for t in (actual_total(m, market) for m in hist) if t is not None]
        naive_lam[label] = sum(tots) / len(tots) / 2.0     # per team per game

    # ---- replay the target season ------------------------------------------ #
    matches = seasons[ti][1]
    model = Model(neutral=False, **KNOBS)
    teams = {m["home"] for m in matches} | {m["away"] for m in matches}
    pri, elo, lavg, xgr, hf = build_priors(prev, teams, CARRY, ELO_CARRY)
    model.inject_prior(pri, elo=elo, g0=G0, league_avg=lavg,
                       xg_ratio=xgr, home_factor=hf)

    res_hit = res_n = 0
    naive_res_hit = 0
    score_hit = score_n = 0
    bin_hit = {lab: [0, 0] for lab, _, _ in LINES}      # model [hits, n]
    bin_naive = {lab: 0 for lab, _, _ in LINES}
    mae = {lab: [0.0, 0.0, 0] for lab, _ in MAES}       # model, naive, sides
    samples = []

    for mi, m in enumerate(matches):
        g = model.goal_grid(m["home"], m["away"])
        if g is not None:
            y = result_idx(m)
            probs = m_result(g)
            pick = max(range(3), key=lambda i: probs[i])
            res_hit += pick == y; res_n += 1
            naive_res_hit += naive_res == y
            (bi, bj), _p = m_top_scores(g, 1)[0]
            score_hit += (bi, bj) == (m["fthg"], m["ftag"]); score_n += 1

            for lab, market, line in LINES:
                if market == "btts":
                    p = m_btts(g)
                    act = 1 if (m["fthg"] >= 1 and m["ftag"] >= 1) else 0
                elif (act := actual_total(m, market)) is None:
                    continue
                elif market == "goals":
                    p = m_over(g, line)
                else:
                    cg = model.count_grid(market, m["home"], m["away"])
                    if cg is None:
                        continue
                    p = m_over(cg, line)
                hit = act if market == "btts" else (1 if act > line else 0)
                bin_hit[lab][0] += (1 if p > 0.5 else 0) == hit
                bin_hit[lab][1] += 1
                bin_naive[lab] += naive_pick[lab] == hit

            for lab, market in MAES:
                sides = actual_sides(m, market)
                if sides is None or None in sides:
                    continue
                ls = (model.goal_lambdas(m["home"], m["away"]) if market == "goals"
                      else model.count_lambdas(market, m["home"], m["away"]))
                if ls is None:
                    continue
                mae[lab][0] += abs(ls[0] - sides[0]) + abs(ls[1] - sides[1])
                mae[lab][1] += abs(naive_lam[lab] - sides[0]) + abs(naive_lam[lab] - sides[1])
                mae[lab][2] += 2

            if mi % (len(matches) // 6) == 0 and len(samples) < 6:
                el = model.goal_lambdas(m["home"], m["away"])
                sh = model.count_lambdas("shots", m["home"], m["away"])
                co = model.count_lambdas("corners", m["home"], m["away"])
                samples.append((m, probs, (bi, bj), el, sh, co))
        model.update(m)

    # ---- report ------------------------------------------------------------- #
    print("=" * 74)
    print(f"SEASON REPLAY — {target}  ({res_n} matches predicted, walk-forward, "
          f"priors from {names[ti-1]})")
    print("=" * 74)

    print("\nSample match cards (predicted before kickoff vs actual):")
    for m, probs, best, el, sh, co in samples:
        print(f"\n  {m['home']} vs {m['away']}   actual {m['fthg']}-{m['ftag']}")
        print(f"    result H/D/A {probs[0]:.0%}/{probs[1]:.0%}/{probs[2]:.0%}   "
              f"pick {best[0]}-{best[1]}   xGoals {el[0]:.2f}-{el[1]:.2f}")
        if sh and co:
            hv, av = Model.COUNTS['shots'][0](m)
            hc, ac = Model.COUNTS['corners'][0](m)
            print(f"    shots {sh[0]:.1f}-{sh[1]:.1f} (actual {hv:.0f}-{av:.0f})   "
                  f"corners {co[0]:.1f}-{co[1]:.1f} (actual {hc:.0f}-{ac:.0f})")

    print(f"\nSCORECARD — picks correct (model vs always-pick-majority naive):")
    print(f"  {'market':22s} {'model':>8s} {'naive':>8s} {'n':>6s}")
    print(f"  {'Match result (H/D/A)':22s} {res_hit/res_n:8.1%} "
          f"{naive_res_hit/res_n:8.1%} {res_n:6d}")
    print(f"  {'Exact scoreline':22s} {score_hit/score_n:8.1%} {'':>8s} {score_n:6d}")
    for lab, _, _ in LINES:
        h, n = bin_hit[lab]
        if n:
            print(f"  {lab:22s} {h/n:8.1%} {bin_naive[lab]/n:8.1%} {n:6d}")

    print(f"\nEXPECTED VALUES — per-team mean absolute error (lower = better):")
    print(f"  {'stat':22s} {'model':>8s} {'naive':>8s}")
    for lab, _ in MAES:
        s, nv, n = mae[lab]
        if n:
            print(f"  {lab:22s} {s/n:8.2f} {nv/n:8.2f}")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "research/seasons/"
    run(folder, sys.argv[2] if len(sys.argv) > 2 else None)
