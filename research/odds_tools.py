"""
odds_tools.py  —  odds <-> probability plumbing for the value finder
--------------------------------------------------------------------
Two distinct jobs, kept separate on purpose:

  * To judge whether the model genuinely DISAGREES with the market, compare the
    model's probability against the bookmaker's MARGIN-FREE (de-vigged) implied
    probability. Raw implied probs sum to >100% (the overround / "vig"), so
    comparing against them invents edges that aren't there.

  * To judge the VALUE of an actual bet, use the RAW offered odds — that's what
    you'd really get paid:  edge = model_prob * raw_odds - 1.

A bet clears the bar only when the model beats the de-vigged market price AND the
raw odds give positive expected value. Using raw odds for the edge is the
stricter, correct EV test; the de-vig is reported alongside for transparency.
"""


def implied(odds):
    """Raw implied probability of a single decimal price."""
    return 1.0 / odds


def overround(odds_list):
    """Bookmaker margin: how far the raw implied probs sum above 100%."""
    return sum(1.0 / o for o in odds_list) - 1.0


def devig_proportional(odds_list):
    """
    Remove the margin proportionally (the standard, transparent method): scale
    raw implied probs so they sum to 1. Good enough for low-margin closing lines
    (esp. Pinnacle). Shin's method is a possible upgrade for softer books.
    """
    imp = [1.0 / o for o in odds_list]
    s = sum(imp)
    return [i / s for i in imp]


def fair_odds(p):
    """Model probability -> fair decimal odds."""
    return float("inf") if p <= 0 else 1.0 / p


def edge(model_p, raw_odds):
    """Expected value per unit staked, at the odds you'd actually be paid."""
    return model_p * raw_odds - 1.0


def value_flag(model_p, raw_odds, devig_p, threshold=0.05):
    """
    A genuine value bet: positive EV beyond `threshold` AND the model's prob
    exceeds the market's margin-free estimate (so the edge isn't just vig).
    """
    return edge(model_p, raw_odds) > threshold and model_p > devig_p


# The market is sharper than the model (blend_tune.py: at the EPL closing line
# the de-vigged consensus alone is near-optimal). When live odds exist, the most
# accurate displayed probability leans heavily on them; the model share hedges
# against soft/early lines (live WC odds are not a closing line).
BLEND_MARKET_W = 0.9


def blend(model_probs, market_probs, w=BLEND_MARKET_W):
    """w*market + (1-w)*model, renormalised."""
    p = [w * b + (1 - w) * m for m, b in zip(model_probs, market_probs)]
    s = sum(p) or 1.0
    return [x / s for x in p]
