"""
prior_backtest.py  —  do pre-tournament priors improve predictability? (research only)
--------------------------------------------------------------------------------------
The live World Cup predictor is COLD-START: it knows only current-tournament form,
so its early predictions are mostly noise. methodology.md flags "blend in a prior
rating" as the most promising upgrade. This script tests that upgrade honestly on
the 10 PL seasons, where "last season's final strength" plays the role of the
pre-tournament rating.

Three variants, identical knobs (the validated k=8, xg_w=0.7, elo_sup=0.10, rho=0):

  A  continuous  one model fed all seasons in a row (the existing backtests'
                 behaviour — teams keep 10 years of accumulated strength)
  B  cold start  fresh model every season, no priors — this is how the live WC
                 predictor actually works today
  C  prior       fresh model every season, seeded with last season's regressed
                 strengths + Elo via Model.inject_prior (pseudo-counts). Promoted
                 teams get a below-average default and inherit the mean regressed
                 Elo of the teams they replaced.

Scored walk-forward on seasons 2-10 (season 1 has no prior and is identical for
all variants). Reported on the fixtures ALL variants can predict, then broken out
by how many real games the teams have played (the "early season" window is the
World Cup group-stage analog), then C's extra coverage (fixtures B cannot predict
at all) against a naive base-rate baseline. Ends with a g0/carry sweep selected on
the first half of the data and confirmed on the held-out second half.

USAGE:  python research/prior_backtest.py research/seasons/
"""

import sys

from footy_model import Model, m_result, load_matches_by_season
from value_backtest import ece, result_idx

KNOBS = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)

# Promoted-side prior: newly promoted teams score less and concede more than the
# PL average (long-run averages are roughly 0.85x / 1.10x).
PROMO_ATT, PROMO_DEF = 0.85, 1.10


# --------------------------------------------------------------------------- #
#  Prior construction: last season's final state -> this season's seed         #
# --------------------------------------------------------------------------- #
def build_priors(prev, teams_now, carry, elo_carry):
    """Regress last season's strengths/Elo toward the mean and map them onto
    this season's team list. Returns (priors, elo, league_avg, xg_ratio, hf)."""
    s = prev.strengths()
    prev_elo = prev.elo
    departed = [t for t in prev_elo if t not in teams_now]
    if departed:
        promo_elo = sum(1500 + elo_carry * (prev_elo[t] - 1500)
                        for t in departed) / len(departed)
    else:
        promo_elo = 1450.0
    pri, elo = {}, {}
    for t in teams_now:
        if t in s and s[t]["games"] >= 15:
            pri[t] = dict(att=1 + carry * (s[t]["att"] - 1),
                          deff=1 + carry * (s[t]["deff"] - 1))
        else:
            pri[t] = dict(att=PROMO_ATT, deff=PROMO_DEF)
        elo[t] = (1500 + elo_carry * (prev_elo[t] - 1500)) if t in prev_elo else promo_elo
    league_avg = prev.totg / (2 * prev.n) if prev.n else 1.35
    xg_ratio = prev.totx / prev.totg if prev.totg else 1.0
    hf = prev.hsg / prev.asg if prev.asg else 1.35
    return pri, elo, league_avg, xg_ratio, hf


# --------------------------------------------------------------------------- #
#  Walk-forward run of one variant                                             #
# --------------------------------------------------------------------------- #
def run_variant(seasons, mode, g0=6.0, carry=0.7, elo_carry=0.7, knobs=KNOBS):
    """mode: 'continuous' | 'reset' | 'prior'.
    Returns {(season_idx, match_idx): (1x2 probs, outcome_idx, min_real_games)}."""
    preds, model, prev = {}, None, None
    for si, (_name, matches) in enumerate(seasons):
        if mode == "continuous":
            model = model or Model(neutral=False, **knobs)
        else:
            model = Model(neutral=False, **knobs)
            if mode == "prior" and prev is not None:
                teams_now = {m["home"] for m in matches} | {m["away"] for m in matches}
                pri, elo, lavg, xgr, hf = build_priors(prev, teams_now, carry, elo_carry)
                model.inject_prior(pri, elo=elo, g0=g0, league_avg=lavg,
                                   xg_ratio=xgr, home_factor=hf)
        realg = {}  # real games this season (pseudo-games excluded) for bucketing
        for mi, m in enumerate(matches):
            gmin = min(realg.get(m["home"], 0), realg.get(m["away"], 0))
            g = model.goal_grid(m["home"], m["away"])
            if g is not None:
                preds[(si, mi)] = (m_result(g), result_idx(m), gmin)
            model.update(m)
            realg[m["home"]] = realg.get(m["home"], 0) + 1
            realg[m["away"]] = realg.get(m["away"], 0) + 1
        prev = model
    return preds


def naive_preds(seasons):
    """Base-rate H/D/A frequencies from all completed seasons — the 'no model'
    floor for fixtures the cold-start model can't price at all."""
    preds, counts = {}, [0, 0, 0]
    for si, (_name, matches) in enumerate(seasons):
        tot = sum(counts)
        rates = [c / tot for c in counts] if tot else None
        for mi, m in enumerate(matches):
            if rates:
                preds[(si, mi)] = (rates, result_idx(m), 0)
        for m in matches:
            counts[result_idx(m)] += 1
    return preds


# --------------------------------------------------------------------------- #
#  Scoring                                                                     #
# --------------------------------------------------------------------------- #
def score(preds, ids):
    ids = [i for i in ids if i in preds]
    if not ids:
        return dict(n=0, acc=float("nan"), brier=float("nan"), ece=float("nan"))
    acc = brier = 0.0
    pairs = []
    for i in ids:
        p, y, _ = preds[i]
        brier += sum((p[j] - (1 if j == y else 0)) ** 2 for j in range(3))
        acc += 1 if max(range(3), key=lambda j: p[j]) == y else 0
        pairs += [(p[j], 1 if j == y else 0) for j in range(3)]
    n = len(ids)
    return dict(n=n, acc=acc / n, brier=brier / n, ece=ece(pairs))


def row(tag, r):
    print(f"  {tag:24s} n={r['n']:5d}  acc {r['acc']:.3f}  "
          f"Brier {r['brier']:.3f}  ECE {r['ece']:.3f}")


# --------------------------------------------------------------------------- #
#  Report                                                                      #
# --------------------------------------------------------------------------- #
def run(folder, g0=10.0, carry=0.9, elo_carry=0.9):
    # defaults = validated plateau: sweeps (incl. an extended g0 4..28, carry
    # 0.5..1.1, elo_carry 0.6..1.0 pass) put the optimum at g0 10-14 with
    # carry/elo_carry ~0.9-1.0; beyond g0=20 the prior overstays and Brier decays.
    seasons = load_matches_by_season(folder)
    print(f"{len(seasons)} seasons: {seasons[0][0]} .. {seasons[-1][0]}")

    A = run_variant(seasons, "continuous")
    B = run_variant(seasons, "reset")
    C = run_variant(seasons, "prior", g0=g0, carry=carry, elo_carry=elo_carry)
    N = naive_preds(seasons)

    scored = lambda P, si_min=1: {i for i in P if i[0] >= si_min}
    common = scored(A) & scored(B) & scored(C)

    print("\n" + "=" * 74)
    print(f"HEAD-TO-HEAD  (seasons 2+, fixtures every variant can predict, "
          f"g0={g0} carry={carry} elo_carry={elo_carry})")
    print("=" * 74)
    row("A continuous (status quo)", score(A, common))
    row("B cold start (= live WC)", score(B, common))
    row("C cold start + priors", score(C, common))

    print("\nBy real games played this season (min of the two teams):")
    for lo, hi, label in ((0, 5, "early  0-5"), (6, 15, "mid    6-15"), (16, 99, "late  16+")):
        ids = {i for i in common if lo <= C[i][2] <= hi}
        if not ids:
            continue
        print(f"  [{label}]")
        row("    A continuous", score(A, ids))
        row("    B cold start", score(B, ids))
        row("    C + priors", score(C, ids))

    extra = scored(C) - scored(B)
    print(f"\nEXTRA COVERAGE — {len(extra)} early fixtures B cannot predict at all "
          f"(each team's first games):")
    row("C + priors", score(C, extra))
    row("naive base rates", score(N, extra))
    cov_b, cov_c = len(scored(B)), len(scored(C))
    print(f"  coverage seasons 2+: B {cov_b} -> C {cov_c} fixtures "
          f"(+{cov_c - cov_b}, +{(cov_c - cov_b) / cov_b:.0%})")

    # ---- knob sweep with a season-level holdout ---------------------------- #
    half = 1 + (len(seasons) - 1) // 2          # seasons 2..half train, rest holdout
    train_ids = lambda P: {i for i in P if 1 <= i[0] <= half}
    hold_ids = lambda P: {i for i in P if i[0] > half}
    print("\n" + "=" * 74)
    print(f"SWEEP g0/carry/elo_carry — selected on seasons 2..{half + 1}, "
          f"confirmed on seasons {half + 2}..{len(seasons)}")
    print("=" * 74)
    best, best_brier = None, 1e9
    print(f"  {'g0':>4s} {'carry':>6s} {'e_car':>6s} {'train Brier':>12s} {'train acc':>10s}")
    for g0s in (4.0, 6.0, 8.0, 10.0):
        for cs in (0.5, 0.7, 0.9):
            for es in (0.6, 0.8):
                P = run_variant(seasons, "prior", g0=g0s, carry=cs, elo_carry=es)
                r = score(P, train_ids(P))
                mark = ""
                if r["brier"] < best_brier:
                    best, best_brier, mark = (g0s, cs, es), r["brier"], "  <- best"
                print(f"  {g0s:4.0f} {cs:6.1f} {es:6.1f} {r['brier']:12.4f} "
                      f"{r['acc']:10.3f}{mark}")
    g0b, cb, eb = best
    Cb = run_variant(seasons, "prior", g0=g0b, carry=cb, elo_carry=eb)
    hold_common = hold_ids(A) & hold_ids(B) & hold_ids(Cb)
    print(f"\nHOLDOUT (seasons {half + 2}..{len(seasons)}, common fixtures) with "
          f"selected g0={g0b} carry={cb} elo_carry={eb}:")
    row("A continuous", score(A, hold_common))
    row("B cold start", score(B, hold_common))
    row("C tuned priors", score(Cb, hold_common))
    hold_extra = hold_ids(Cb) - hold_ids(B)
    print(f"\nHoldout extra coverage ({len(hold_extra)} fixtures):")
    row("C tuned priors", score(Cb, hold_extra))
    row("naive base rates", score(N, hold_extra))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "research/seasons/")
