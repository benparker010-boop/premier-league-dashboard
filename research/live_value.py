"""
live_value.py  —  live odds value finder (research only)
--------------------------------------------------------
Pulls real bookmaker odds via The Odds API and turns them into a usable card:

  * de-vigs each market to the bookmaker's true (margin-free) probabilities,
  * shows the overround (margin) and the BEST price per outcome across all books,
  * if a model price function is supplied, computes edge % and flags value
    (edge = model_prob x best_price - 1, confirmed against the de-vigged price).

Runnable today (with a key) in MARKET-ONLY mode — that already de-vigs live odds
and surfaces the best line per outcome. To produce model-vs-market VALUE picks for
the World Cup it needs a team-strength source for international sides (the app's
TheStatsAPI form, i.e. the app.py integration) — `price_fn` is the plug point.

USAGE:
  python research/live_value.py --sports          # list available sport keys
  python research/live_value.py --live            # market-only card for the WC
  python research/live_value.py --live --sport soccer_epl
"""

import sys

from live_odds import fetch_odds, _read_secret, API, SPORT_WC
from odds_tools import devig_proportional, edge, fair_odds

BEST = dict(k=8, xg_w=0.7, elo_sup=0.10, rho=0.0)


def build_wc_price_fn():
    """Feed real WC form into the validated model and return a price function
    price(home, away) -> {home: pH, 'Draw': pD, away: pA}, or None if no data."""
    from wc_data import to_model_matches, resolve
    from footy_model import Model, m_result
    matches = to_model_matches()
    if not matches:
        return None, 0
    model = Model(neutral=True, min_g=2, **BEST)   # neutral venue, small WC samples
    for m in matches:
        model.update(m)
    known = set(model.G)

    def price(home, away):
        h, a = resolve(home, known), resolve(away, known)
        if not h or not a:
            return None
        g = model.goal_grid(h, a)
        if g is None:
            return None
        pH, pD, pA = m_result(g)
        return {home: pH, "Draw": pD, away: pA}

    return price, len(matches)


def list_sports():
    """Print available sport keys (does NOT cost a quota request)."""
    key = _read_secret("ODDS_API_KEY")
    if not key:
        from live_odds import _setup_message
        print(_setup_message())
        return
    import requests
    r = requests.get(f"{API}/sports/", params=dict(apiKey=key), timeout=20)
    if r.status_code != 200:
        print(f"Odds API error {r.status_code}: {r.text[:200]}")
        return
    for s in r.json():
        if s.get("group") == "Soccer":
            print(f"  {s['key']:34s} {s['title']}  {'(active)' if s.get('active') else ''}")


def all_prices(fixture, market_key):
    """Per outcome: list of (price, book_title) across every book quoting it."""
    out = {}
    for bk in fixture.get("bookmakers", []):
        for mk in bk.get("markets", []):
            if mk["key"] != market_key:
                continue
            for oc in mk["outcomes"]:
                out.setdefault(oc["name"], []).append((oc["price"], bk["title"]))
    return out


def consensus(fixture, names, market_key="h2h"):
    """Market's true (margin-free) estimate per outcome, plus the typical single-book
    margin and the best bettable price. Consensus = de-vig of the mean implied prob
    across books (robust); margin = average per-book overround."""
    quotes = all_prices(fixture, market_key)
    if any(n not in quotes for n in names):
        return None
    # mean implied prob per outcome -> de-vig to consensus fair probs
    mean_imp = [sum(1 / p for p, _ in quotes[n]) / len(quotes[n]) for n in names]
    s = sum(mean_imp)
    fair = [m / s for m in mean_imp]
    best = [max(quotes[n], key=lambda x: x[0]) for n in names]   # (price, book)
    # average single-book margin (only books quoting all outcomes)
    by_book = {}
    for n in names:
        for p, bk in quotes[n]:
            by_book.setdefault(bk, {})[n] = p
    margins = [sum(1 / d[n] for n in names) - 1 for d in by_book.values()
               if all(n in d for n in names)]
    avg_margin = sum(margins) / len(margins) if margins else float("nan")
    return fair, best, avg_margin


def card(fx, price_fn=None, threshold=0.05):
    home, away = fx["home_team"], fx["away_team"]
    print(f"\n{'='*70}\n{home}  vs  {away}\n{'='*70}")
    names = [home, away, "Draw"]
    c = consensus(fx, names)
    if c is None:
        print("  incomplete h2h odds.")
        return
    fair, best, avg_margin = c
    model = price_fn(home, away) if price_fn else None
    print(f"Match result   (avg book margin {avg_margin*100:.1f}%):")
    for n, mfair, (price, book) in zip(names, fair, best):
        # model-free line-shop edge: best price vs market consensus truth
        shop = mfair * price - 1
        shop_tag = f"  shop-edge {shop*100:+5.1f}%" if shop > threshold else ""
        line = (f"  {n:22s} consensus {mfair*100:4.1f}% (fair {1/mfair:5.2f})   "
                f"best {price:5.2f} ({book:<12s}){shop_tag}")
        if model and n in model:
            mp = model[n]
            e = edge(mp, price)
            flag = "  <== VALUE" if (e > threshold and mp > mfair) else ""
            line += f"   model {mp*100:4.1f}% edge {e*100:+5.1f}%{flag}"
        print(line)


def run(sport, price_fn=None):
    data = fetch_odds(sport=sport, regions="uk,eu", markets="h2h")
    if not data:
        return
    for fx in data:
        card(fx, price_fn)


if __name__ == "__main__":
    if "--sports" in sys.argv:
        list_sports()
    elif "--live" in sys.argv:
        sport = SPORT_WC
        if "--sport" in sys.argv:
            sport = sys.argv[sys.argv.index("--sport") + 1]
        price_fn = None
        if "--model" in sys.argv:           # model-vs-market value (needs STATS_API_KEY)
            price_fn, n = build_wc_price_fn()
            if price_fn:
                print(f"Model built from {n} finished WC matches.\n")
            else:
                print("No WC form available (set STATS_API_KEY) - market-only mode.\n")
        run(sport, price_fn=price_fn)
    else:
        print(__doc__)
