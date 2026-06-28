"""
core.predict — fixture predictions as structured data (no UI, no HTML).

Unifies on the validated, backtested engine in research/footy_model.py (the
multi-market Dixon-Coles / shrinkage-Poisson + xG + Elo model) rather than the
simpler inline copy in app.py. Trains on the live World Cup result cache that
wc_ingest.py keeps fresh (research/wc_matches.jsonl) and returns a plain dict a
front-end can render however it likes.

    from core.predict import predict, known_teams
    p = predict("France", "Iraq")          # -> dict (see `predict` docstring)
"""
import os
import sys
import json

_RESEARCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research")
if _RESEARCH not in sys.path:
    sys.path.insert(0, _RESEARCH)

from footy_model import Model, m_result, m_over, m_btts, m_top_scores  # noqa: E402
from wc_data import resolve  # noqa: E402  (name-alias resolver)

CACHE = os.path.join(_RESEARCH, "wc_matches.jsonl")
# Validated knobs (same as predict_fixture_live.py / live_value.py).
BEST = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)


def load_cache():
    """Finished WC matches (footy_model dict shape), oldest first."""
    if not os.path.exists(CACHE):
        return []
    out = []
    with open(CACHE, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    out.sort(key=lambda r: r.get("date", ""))
    return out


def build_model(min_games=2, matches=None):
    """Train the neutral-venue WC model on the cached results."""
    model = Model(neutral=True, min_g=min_games, **BEST)
    for mm in (matches if matches is not None else load_cache()):
        model.update(mm)
    return model


def known_teams(model=None):
    """Team names the model currently has data for (sorted)."""
    model = model or build_model()
    return sorted(model.G)


def predict(home, away, min_games=2, model=None):
    """Predict a neutral-venue fixture.

    Returns a dict:
      {
        home, away, available: bool, reason: str|None,
        result:   {home_win, draw, away_win},        # probabilities (0..1)
        expected_goals: {home, away},                # model lambdas
        scoreline: [i, j],                           # most likely score
        top_scorelines: [{score:[i,j], prob}, ...],  # top 5
        totals:   {"over_1.5","over_2.5","over_3.5"}, # P(total > line)
        btts:     float,                             # P(both teams score)
        elo:      {home, away},
        games:    {home, away},                      # sample sizes
      }
    `available` is False (with a reason) when a side has < min_games played.
    """
    model = model or build_model(min_games=min_games)
    known = set(model.G)
    h, a = resolve(home, known), resolve(away, known)
    base = {"home": home, "away": away, "available": False, "reason": None}
    if not h or not a:
        miss = [t for t, r in ((home, h), (away, a)) if not r]
        base["reason"] = f"unknown team(s): {', '.join(miss)}"
        return base

    grid = model.goal_grid(h, a)
    if grid is None:
        gh, ga = model.G.get(h, 0), model.G.get(a, 0)
        base["reason"] = (f"not enough data (need >= {min_games} games; "
                          f"{home}={gh}, {away}={ga})")
        base["games"] = {"home": gh, "away": ga}
        return base

    la, lb = model.goal_lambdas(h, a)
    pH, pD, pA = m_result(grid)
    tops = [{"score": [i, j], "prob": p} for (i, j), p in m_top_scores(grid, 5)]
    return {
        "home": home, "away": away, "available": True, "reason": None,
        "result": {"home_win": pH, "draw": pD, "away_win": pA},
        "expected_goals": {"home": la, "away": lb},
        "scoreline": list(tops[0]["score"]) if tops else None,
        "top_scorelines": tops,
        "totals": {f"over_{ln}": m_over(grid, ln) for ln in (1.5, 2.5, 3.5)},
        "btts": m_btts(grid),
        "elo": {"home": model.elo.get(h, 1500.0), "away": model.elo.get(a, 1500.0)},
        "games": {"home": model.G.get(h, 0), "away": model.G.get(a, 0)},
    }
