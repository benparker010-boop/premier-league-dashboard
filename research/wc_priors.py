"""
wc_priors.py  —  pre-tournament priors for the World Cup model (research only)
------------------------------------------------------------------------------
The live WC predictor was cold-start: every team began at Elo 1500 and league-
average strength, so early predictions were mostly shrinkage. This module seeds
the model with PRE-TOURNAMENT World Football Elo Ratings via the pseudo-count
prior mechanism validated on 10 PL seasons (see methodology.md).

Data: wc2026_elo.tsv, fetched 2026-07-05 from eloratings.net/2026_World_Cup.tsv.
Column 4 is the current rating, the final column the rating change during this
tournament — so pre-tournament = rating − change, which keeps the prior free of
look-ahead and lets the cached tournament matches double as a validation set.

Attack/defence prior factors are derived from each team's Elo gap to the field
average:  att = 10^(+s·Δ/400),  deff = 10^(−s·Δ/400).  `s` is tuned by the
validation replay below (run this file directly); the model's elo_sup shift
also uses the seeded Elo, so s only needs to carry the part Elo doesn't.

USAGE
  python research/wc_priors.py          # validation replay: cold vs seeded
  from wc_priors import seed; seed(model)   # in a live script, after Model()
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from footy_model import Model

TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wc2026_elo.tsv")

# eloratings.net team code -> TheStatsAPI team name (the names in the WC cache)
CODE_TEAM = {
    "ES": "Spain", "AR": "Argentina", "FR": "France", "EN": "England",
    "PT": "Portugal", "CO": "Colombia", "BR": "Brazil", "NO": "Norway",
    "NL": "Netherlands", "MX": "Mexico", "CH": "Switzerland", "MA": "Morocco",
    "BE": "Belgium", "DE": "Germany", "JP": "Japan", "HR": "Croatia",
    "EC": "Ecuador", "TR": "Türkiye", "UY": "Uruguay", "AT": "Austria",
    "SN": "Senegal", "PY": "Paraguay", "US": "USA", "AU": "Australia",
    "IR": "Iran", "DZ": "Algeria", "EG": "Egypt", "SQ": "Scotland",
    "SE": "Sweden", "CA": "Canada", "CI": "Côte d'Ivoire", "KR": "South Korea",
    "CD": "DR Congo", "CZ": "Czechia", "PA": "Panama", "UZ": "Uzbekistan",
    "JO": "Jordan", "CV": "Cape Verde", "BA": "Bosnia & Herzegovina",
    "SA": "Saudi Arabia", "GH": "Ghana", "TN": "Tunisia", "IQ": "Iraq",
    "ZA": "South Africa", "NZ": "New Zealand", "HT": "Haiti",
    "CW": "Curaçao", "QA": "Qatar",
}

S_DEFAULT = 0.30      # Elo->strength coupling, checked by the replay below
G0 = 10.0             # prior weight in pseudo-games (validated on PL seasons)
LEAGUE_AVG = 1.30     # neutral prior for goals per team per game (WC-typical)


def _num(x):
    return float(x.replace("−", "-").replace("+", ""))


def pre_tournament_elo(path=TSV):
    """{team name: pre-tournament Elo} for the 48 qualified teams."""
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 5:
                continue
            team = CODE_TEAM.get(c[2])
            if team is None:
                print(f"[wc_priors] unknown code {c[2]!r} — extend CODE_TEAM")
                continue
            out[team] = _num(c[3]) - _num(c[-1])
    return out


def build(teams=None, s=S_DEFAULT):
    """(priors, elo) for Model.inject_prior. `teams` restricts/validates the
    name set (e.g. the teams present in the match cache)."""
    elo = pre_tournament_elo()
    if teams is not None:
        missing = set(teams) - set(elo)
        if missing:
            print(f"[wc_priors] no prior for: {sorted(missing)}")
        elo = {t: r for t, r in elo.items() if t in teams}
    mean = sum(elo.values()) / len(elo)
    priors = {t: dict(att=10 ** (s * (r - mean) / 400),
                      deff=10 ** (-s * (r - mean) / 400))
              for t, r in elo.items()}
    return priors, elo


def seed(model, teams=None, s=S_DEFAULT, g0=G0):
    """Inject the pre-tournament prior into a fresh (neutral) Model."""
    priors, elo = build(teams, s)
    model.inject_prior(priors, elo=elo, g0=g0, league_avg=LEAGUE_AVG,
                       xg_ratio=1.0)
    return model


# --------------------------------------------------------------------------- #
#  Validation: replay the tournament so far, cold-start vs prior-seeded        #
# --------------------------------------------------------------------------- #
HOSTS = {"USA", "Mexico", "Canada"}
# +100 Elo when a host is the designated home side: the replay sweep improves
# monotonically through +150 but rests on only 9 host home games, so we adopt
# the historical host-advantage standard (~100) instead of the grid edge.
HOST_ELO = 100.0


def _replay(matches, seeded, s=S_DEFAULT, min_g=2, host_elo=None):
    from footy_model import m_result
    from predict_demo import BEST
    from value_backtest import result_idx
    model = Model(neutral=True, min_g=min_g, **BEST)
    model.hosts = HOSTS
    model.host_elo = HOST_ELO if host_elo is None else host_elo
    if seeded:
        teams = {m["home"] for m in matches} | {m["away"] for m in matches}
        seed(model, teams, s=s)
    preds = {}
    for i, m in enumerate(matches):
        g = model.goal_grid(m["home"], m["away"])
        if g is not None:
            preds[i] = (m_result(g), result_idx(m))
        model.update(m)
    return preds


def _score(preds, ids):
    from value_backtest import ece
    ids = [i for i in ids if i in preds]
    if not ids:
        return dict(n=0)
    acc = brier = 0.0
    pairs = []
    for i in ids:
        p, y = preds[i]
        brier += sum((p[j] - (1 if j == y else 0)) ** 2 for j in range(3))
        acc += 1 if max(range(3), key=lambda j: p[j]) == y else 0
        pairs += [(p[j], 1 if j == y else 0) for j in range(3)]
    return dict(n=len(ids), acc=acc / len(ids), brier=brier / len(ids), ece=ece(pairs))


def main():
    from wc_ingest import load_cache
    matches = load_cache()
    if not matches:
        sys.exit("WC cache empty — run wc_ingest.py first.")
    print(f"Validation replay over {len(matches)} finished WC matches "
          f"(walk-forward, min_g=2 for the cold model):\n")
    cold = _replay(matches, seeded=False)
    common = set(cold)
    print(f"  {'model':28s} {'n':>4s} {'acc':>7s} {'Brier':>7s} {'ECE':>7s}")
    r = _score(cold, common)
    print(f"  {'cold start (live today)':28s} {r['n']:4d} {r['acc']:7.3f} "
          f"{r['brier']:7.3f} {r['ece']:7.3f}")
    for s in (0.0, 0.15, 0.30, 0.45):
        p = _replay(matches, seeded=True, s=s)
        r = _score(p, common)
        a = _score(p, set(p))
        print(f"  {f'seeded s={s:.2f} (common)':28s} {r['n']:4d} {r['acc']:7.3f} "
              f"{r['brier']:7.3f} {r['ece']:7.3f}   "
              f"[all {a['n']}: acc {a['acc']:.3f} Brier {a['brier']:.3f}]")
    print("\n  'common' = the fixtures the cold model can also predict; the "
          "seeded model\n  additionally prices every earlier fixture "
          "(the [all ...] figures).")

    print(f"\nHost-advantage sweep (seeded s={S_DEFAULT}, bonus Elo when "
          f"USA/Mexico/Canada\nare the designated home side; "
          f"host home games so far shown as n_host):")
    n_host = sum(1 for m in matches if m["home"] in HOSTS)
    print(f"  n_host = {n_host} of {len(matches)}")
    for h_elo in (0.0, 50.0, 100.0, 150.0):
        p = _replay(matches, seeded=True, host_elo=h_elo)
        a = _score(p, set(p))
        ho = _score(p, {i for i, m in enumerate(matches) if m["home"] in HOSTS})
        print(f"  bonus {h_elo:5.0f}:  all {a['n']}: acc {a['acc']:.3f} "
              f"Brier {a['brier']:.3f}   host games: acc {ho['acc']:.3f} "
              f"Brier {ho['brier']:.3f}")


if __name__ == "__main__":
    main()
