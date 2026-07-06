"""
footy_model.py  —  multi-market match model (research only, nothing live)
-------------------------------------------------------------------------
Builds ONE score grid per fixture so every goal-based market is internally
consistent:

    shrinkage Poisson lambdas
      + xG-proxy blend (validated)
      + Elo folded in as a supremacy shift on the lambdas (not bolted on at the
        1X2 level — that is the only way result / scoreline / O/U / BTTS can all
        come off a single grid)
      + Dixon-Coles low-score correction (fixes 0-0 / 1-0 / 0-1 / 1-1)

Corners, cards, shots, shots on target and fouls get their own shrinkage-Poisson
grids (opponent-adjusted: a team's rate is blended with what its opponent tends
to concede). Possession is a two-sided share model (live data only — the CSVs
don't carry it).

The `Model` class is stateful and updated walk-forward (no look-ahead): you feed
it finished matches in date order and ask it to predict the next one. The same
class can later drive app.py's live predictor once validated.

Pure standard library, matching footy_backtest.py — no numpy/pandas needed.
"""

import math
import csv
import glob
import os
import sys

MAXG = 10        # goals score-grid dimension
MAXC = 20        # corners grid dimension
MAXK = 12        # cards grid dimension
MAXS = 35        # shots grid dimension (per team; PL max ~30-ish)
MAXT = 20        # shots-on-target grid dimension
MAXF = 30        # fouls grid dimension
HOME_ELO = 60.0  # home-advantage bonus in Elo points (PL backtest; 0 for neutral)


# --------------------------------------------------------------------------- #
#  Data loading (extends footy_backtest's loader with odds + corners + cards)  #
# --------------------------------------------------------------------------- #
def _f(row, key):
    """Parse a float cell, or None if missing/blank/non-numeric."""
    v = row.get(key, "")
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_matches(folder):
    """Return matches as dicts in file order (football-data is date-sorted)."""
    rows, files = [], sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        sys.exit(f"No CSV files in {folder}")
    for f in files:
        with open(f, newline="", encoding="latin-1") as fh:
            for r in csv.DictReader(fh):
                m = _parse_row(r)
                if m:
                    rows.append(m)
    print(f"Loaded {len(rows)} matches from {len(files)} file(s).\n")
    return rows


def _parse_row(r):
    try:
        m = dict(
            home=r["HomeTeam"], away=r["AwayTeam"],
            fthg=int(float(r["FTHG"])), ftag=int(float(r["FTAG"])),
            hs=int(float(r["HS"])), as_=int(float(r["AS"])),
            hst=int(float(r["HST"])), ast=int(float(r["AST"])),
        )
    except (ValueError, KeyError, TypeError):
        return None
    # corners / cards / fouls are optional — keep the match even if absent
    m["hc"], m["ac"] = _f(r, "HC"), _f(r, "AC")
    m["hy"], m["ay"] = _f(r, "HY"), _f(r, "AY")
    m["hr"], m["ar"] = _f(r, "HR"), _f(r, "AR")
    m["hf"], m["af"] = _f(r, "HF"), _f(r, "AF")
    # possession % is not in football-data CSVs; live sources (wc_data) supply it
    m["hp"], m["ap"] = _f(r, "HP"), _f(r, "AP")
    m["ref"] = (r.get("Referee") or "").strip() or None
    # Keep OPENING and CLOSING odds separate: you bet into the opening/soft price
    # and the closing line (esp. Pinnacle) is the sharp benchmark for CLV.
    m["odds"] = {
        "1x2_open": {
            "b365": _triple(r, "B365H", "B365D", "B365A"),
            "pin":  _triple(r, "PSH", "PSD", "PSA"),
            "avg":  _triple(r, "AvgH", "AvgD", "AvgA"),
        },
        "1x2_close": {
            "b365": _triple(r, "B365CH", "B365CD", "B365CA"),
            "pin":  _triple(r, "PSCH", "PSCD", "PSCA"),
            "avg":  _triple(r, "AvgCH", "AvgCD", "AvgCA"),
        },
        "ou25_open": {
            "b365": _pair(r, "B365>2.5", "B365<2.5"),
            "pin":  _pair(r, "P>2.5", "P<2.5"),
            "avg":  _pair(r, "Avg>2.5", "Avg<2.5"),
        },
        "ou25_close": {
            "b365": _pair(r, "B365C>2.5", "B365C<2.5"),
            "pin":  _pair(r, "PC>2.5", "PC<2.5"),
            "avg":  _pair(r, "AvgC>2.5", "AvgC<2.5"),
        },
    }
    return m


def load_matches_by_season(folder):
    """Like load_matches, but returns [(season_name, [matches])] one per CSV file,
    so callers can reset or re-prime the model at season boundaries."""
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        sys.exit(f"No CSV files in {folder}")
    seasons = []
    for f in files:
        rows = []
        with open(f, newline="", encoding="latin-1") as fh:
            for r in csv.DictReader(fh):
                m = _parse_row(r)
                if m:
                    rows.append(m)
        if rows:
            seasons.append((os.path.splitext(os.path.basename(f))[0], rows))
    return seasons


def _triple(r, a, b, c):
    x, y, z = _f(r, a), _f(r, b), _f(r, c)
    return (x, y, z) if x and y and z else None


def _pair(r, a, b):
    x, y = _f(r, a), _f(r, b)
    return (x, y) if x and y else None


# --------------------------------------------------------------------------- #
#  Poisson / Dixon-Coles score grid                                           #
# --------------------------------------------------------------------------- #
def pois_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def nb_pmf(k, lam, r):
    """Negative binomial with mean lam and dispersion r (variance lam + lam^2/r).
    r -> infinity recovers Poisson; smaller r = fatter tails. Count stats (shots,
    corners, fouls) are over-dispersed vs Poisson, so their O/U tails need this."""
    return math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
                    + r * math.log(r / (r + lam)) + k * math.log(lam / (r + lam)))


def count_score_grid(la, lb, mx, r=None):
    """Independent joint grid for a count market: NB marginals when a dispersion
    r is given, else Poisson. (No Dixon-Coles here — that's goals-specific.)"""
    pmf = (lambda k, lam: nb_pmf(k, lam, r)) if r else pois_pmf
    ph = [pmf(i, la) for i in range(mx + 1)]
    pa = [pmf(j, lb) for j in range(mx + 1)]
    g = [[ph[i] * pa[j] for j in range(mx + 1)] for i in range(mx + 1)]
    s = sum(sum(row) for row in g)
    return [[v / s for v in row] for row in g]


def _dc_tau(i, j, la, lb, rho):
    """Dixon-Coles dependency term — only touches the four lowest scores."""
    if i == 0 and j == 0:
        return 1.0 - la * lb * rho
    if i == 0 and j == 1:
        return 1.0 + la * rho
    if i == 1 and j == 0:
        return 1.0 + lb * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_grid(la, lb, rho=0.0, mx=MAXG):
    """Joint P(home=i, away=j) grid, Dixon-Coles-corrected and renormalised."""
    g = [[pois_pmf(i, la) * pois_pmf(j, lb) * _dc_tau(i, j, la, lb, rho)
          for j in range(mx + 1)] for i in range(mx + 1)]
    s = sum(sum(row) for row in g)
    return [[v / s for v in row] for row in g]


# ---- market readers: every goal market comes off the one grid -------------- #
def m_result(g):
    """(home win, draw, away win)."""
    H = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i > j)
    D = sum(g[i][i] for i in range(len(g)))
    A = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i < j)
    return [H, D, A]


def m_over(g, line):
    """P(total goals > line). Use half-lines (1.5/2.5/3.5)."""
    need = math.ceil(line)            # 2.5 -> total >= 3
    p = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i + j >= need)
    return p


def m_btts(g):
    """P(both teams score)."""
    return sum(g[i][j] for i in range(1, len(g)) for j in range(1, len(g)))


def m_top_scores(g, n=5):
    cells = [((i, j), g[i][j]) for i in range(len(g)) for j in range(len(g))]
    cells.sort(key=lambda x: -x[1])
    return cells[:n]


def m_total_over(grid, line):
    """P(total > line) for a single-total grid (corners/cards): grid[i][j] joint."""
    return m_over(grid, line)


# --------------------------------------------------------------------------- #
#  Rolling, walk-forward model state                                          #
# --------------------------------------------------------------------------- #
class Model:
    """
    Accumulates team strengths from finished matches and predicts the next
    fixture. Knobs (set once, tuned by sweep in tune.py):
        k        shrinkage constant (pulls small samples to league average)
        xg_w     weight on the xG-proxy lambdas (0..1)
        elo_sup  how strongly an Elo gap shifts the goal lambdas
        rho      Dixon-Coles low-score correction
        min_g    games a team needs before we trust its prediction
        neutral  True = no home advantage (World Cup); False = PL home/away
    """

    def __init__(self, k=5.0, xg_w=0.5, elo_sup=0.10, rho=0.08, min_g=4, neutral=False,
                 xg_meanmatch=True, disp=None):
        self.k, self.xg_w, self.elo_sup = k, xg_w, elo_sup
        self.rho, self.min_g, self.neutral = rho, min_g, neutral
        # per-market NB dispersion (None = Poisson); defaults tuned by disp_tune.py
        self.disp = dict(self.DISP) if disp is None else dict(disp)
        # mean-match the xG-proxy lambdas to the goals scale: the proxy carries
        # the right *relative* strengths but over-states the goal level, so we let
        # goals set the scale and xG only tilt attack/defence. Kills the totals bias.
        self.xg_meanmatch = xg_meanmatch
        # goals + xG-proxy attack/defence accumulators
        self.Fg, self.Adg, self.Fx, self.Adx, self.G = {}, {}, {}, {}, {}
        self.totg = self.hsg = self.asg = 0.0
        self.totx = self.hsx = self.asx = 0.0
        # generic count markets (for + against + games, plus league totals):
        # corners, cards, shots, shots on target, fouls — one shrinkage-Poisson
        # grid each, all driven by the same accumulator shape.
        self.cnt = {name: dict(F={}, A={}, G={}, tot=0.0, n=0)
                    for name in self.COUNTS}
        # possession share (0..1) — sum of shares and games with possession data
        self.Pf, self.Pg = {}, {}
        # referee strictness: {market: {ref: [total in ref's games, games]}}
        self.ref = {"cards": {}, "fouls": {}}
        # pseudo-games shrinking a ref toward league average (ref_backtest.py:
        # holdout Brier cards 0.168->0.167, fouls 0.186->0.183)
        self.ref_k = {"cards": 40.0, "fouls": 20.0}
        self.n = 0
        self.elo = {}
        # tournament host advantage: teams in `hosts` get `host_elo` bonus Elo
        # when they are the designated home side (venue in their country).
        # Applied in both prediction and Elo ingestion so ratings don't double-
        # count home wins. Validated for WC 2026 in wc_priors.py.
        self.hosts, self.host_elo = set(), 0.0

    # per-market NB dispersion r (None = plain Poisson), tuned by disp_tune.py:
    # selected on the first 60% of 10 PL seasons, confirmed on the 40% holdout.
    # Cards and SOT showed no holdout gain from NB, so they stay Poisson.
    DISP = {"corners": 20.0, "cards": None, "shots": 40.0,
            "sot": None, "fouls": 40.0}

    # count market -> ((home value, away value) extractor, grid dimension)
    COUNTS = {
        "corners": (lambda m: (m["hc"], m["ac"]), MAXC),
        "cards":   (lambda m: (None, None) if None in (m["hy"], m["ay"], m["hr"], m["ar"])
                    else (m["hy"] + m["hr"], m["ay"] + m["ar"]), MAXK),
        "shots":   (lambda m: (m["hs"], m["as_"]), MAXS),
        "sot":     (lambda m: (m["hst"], m["ast"]), MAXT),
        "fouls":   (lambda m: (m.get("hf"), m.get("af")), MAXF),
    }

    # ---- helpers ---------------------------------------------------------- #
    def _bonus(self, h):
        """Elo bonus for the designated home side: league home advantage, plus
        the tournament host bonus when the home team is playing in its country."""
        b = 0.0 if self.neutral else HOME_ELO
        if h in self.hosts:
            b += self.host_elo
        return b

    def _xgproxy(self, hsh, ash, hst, ast):
        return (0.34 * hst + 0.043 * (hsh - hst),
                0.34 * ast + 0.043 * (ash - ast))

    def _lambdas(self, F, Ad, tot, hs, as_, h, a):
        avg = tot / (2 * self.n)
        if self.neutral:
            hf = 1.0
        else:
            hf = max(0.6, min(1.6, (hs / self.n) / (as_ / self.n))) if as_ > 0 else 1.0

        def fac(t, d):
            g = self.G[t]
            raw = (d[t] / g) / avg if avg > 0 and g > 0 else 1.0
            w = g / (g + self.k)
            return w * raw + (1 - w)

        lh = avg * fac(h, F) * fac(a, Ad) * math.sqrt(hf)
        la = avg * fac(a, F) * fac(h, Ad) / math.sqrt(hf)
        return lh, la

    def goal_lambdas(self, h, a):
        """Expected goals (home, away) for a fixture, or None if too little data."""
        if self.n == 0 or self.G.get(h, 0) < self.min_g or self.G.get(a, 0) < self.min_g:
            return None
        lh, la = self._lambdas(self.Fg, self.Adg, self.totg, self.hsg, self.asg, h, a)
        if self.xg_w > 0:
            lhx, lax = self._lambdas(self.Fx, self.Adx, self.totx, self.hsx, self.asx, h, a)
            if self.xg_meanmatch and self.totx > 0:
                s = self.totg / self.totx          # rescale xG units to goals units
                lhx, lax = lhx * s, lax * s
            lh = (1 - self.xg_w) * lh + self.xg_w * lhx
            la = (1 - self.xg_w) * la + self.xg_w * lax
        # fold Elo in as a supremacy shift so the single grid is Elo-aware
        bonus = self._bonus(h)
        sup = (self.elo.get(h, 1500.0) - self.elo.get(a, 1500.0) + bonus) / 400.0
        lh = max(0.05, lh * 10 ** (self.elo_sup * sup))
        la = max(0.05, la * 10 ** (-self.elo_sup * sup))
        return lh, la

    def goal_grid(self, h, a):
        ls = self.goal_lambdas(h, a)
        if ls is None:
            return None
        return score_grid(ls[0], ls[1], rho=self.rho, mx=MAXG)

    def ref_factor(self, name, ref):
        """Referee strictness multiplier for cards/fouls: the ref's per-game
        total vs league average, shrunk toward 1.0 by ref_k pseudo-games."""
        if ref is None or name not in self.ref:
            return 1.0
        c = self.cnt[name]
        if c["n"] == 0:
            return 1.0
        tot, g = self.ref[name].get(ref, (0.0, 0))
        if g == 0:
            return 1.0
        league = c["tot"] / c["n"]                    # per game (both teams)
        raw = (tot / g) / league if league > 0 else 1.0
        k = self.ref_k[name] if isinstance(self.ref_k, dict) else self.ref_k
        w = g / (g + k)
        return w * raw + (1 - w)

    def count_lambdas(self, name, h, a, ref=None):
        """Expected (home, away) counts for a market ('corners', 'cards', 'shots',
        'sot', 'fouls') via opponent-adjusted shrinkage Poisson, or None if either
        team hasn't logged min_g games with that stat. For cards/fouls, pass the
        appointed referee to fold in their strictness."""
        c = self.cnt[name]
        Cf, Ca, Cg, ctot, cn = c["F"], c["A"], c["G"], c["tot"], c["n"]
        if cn == 0 or Cg.get(h, 0) < self.min_g or Cg.get(a, 0) < self.min_g:
            return None
        avg = ctot / (2 * cn)              # league average per team per game

        def fac(t, d):
            g = Cg[t]
            raw = (d[t] / g) / avg if avg > 0 and g > 0 else 1.0
            w = g / (g + self.k)
            return w * raw + (1 - w)

        rf = self.ref_factor(name, ref)
        lh = max(0.05, avg * fac(h, Cf) * fac(a, Ca) * rf)
        la = max(0.05, avg * fac(a, Cf) * fac(h, Ca) * rf)
        return lh, la

    def count_grid(self, name, h, a, ref=None):
        """Joint (home, away) count grid for any count market, or None. Uses
        negative-binomial marginals with the market's validated dispersion."""
        ls = self.count_lambdas(name, h, a, ref=ref)
        return None if ls is None else count_score_grid(
            ls[0], ls[1], mx=self.COUNTS[name][1], r=self.disp.get(name))

    def corner_grid(self, h, a):
        return self.count_grid("corners", h, a)

    def card_grid(self, h, a):
        return self.count_grid("cards", h, a)

    def shots_grid(self, h, a):
        return self.count_grid("shots", h, a)

    def sot_grid(self, h, a):
        return self.count_grid("sot", h, a)

    def fouls_grid(self, h, a):
        return self.count_grid("fouls", h, a)

    def possession_share(self, h, a):
        """Expected possession split (home, away) as fractions summing to 1, or
        None without enough data. Each team's mean share is shrunk toward 0.5,
        then the two are combined Bradley-Terry style (log-odds addition), which
        keeps the pair consistent: strong-vs-weak widens, strong-vs-strong ~50/50.

        NOT backtested — football-data CSVs carry no possession, so this is
        validated live (wc_data supplies ball_possession) rather than offline."""
        gh, ga = self.Pg.get(h, 0), self.Pg.get(a, 0)
        if gh < self.min_g or ga < self.min_g:
            return None

        def rating(t, g):
            mean = self.Pf[t] / g
            w = g / (g + self.k)
            return 0.5 + w * (mean - 0.5)

        rh, ra = rating(h, gh), rating(a, ga)
        ph = rh * (1 - ra) / (rh * (1 - ra) + (1 - rh) * ra)
        return ph, 1 - ph

    # ---- priors: seed the model before any real matches -------------------- #
    def strengths(self):
        """Per-team raw attack/defence factors vs league average (goals-based),
        plus games seen. Used to hand one season's final state to the next
        season's prior. Includes any pseudo-games from an injected prior."""
        out = {}
        if self.n == 0:
            return out
        avg = self.totg / (2 * self.n)
        for t, g in self.G.items():
            if g <= 0 or avg <= 0:
                continue
            out[t] = dict(games=g,
                          att=(self.Fg.get(t, 0.0) / g) / avg,
                          deff=(self.Adg.get(t, 0.0) / g) / avg)
        return out

    def inject_prior(self, priors, elo=None, g0=6.0, league_avg=1.35,
                     xg_ratio=1.0, home_factor=1.35):
        """Seed pseudo-observations before real matches (Bayesian pseudo-counts).

        Each team starts as if it had already played `g0` games at its prior
        strength; real results then wash the prior out at exactly the rate the
        shrinkage machinery already uses (rate = (g0*prior + real) / (g0 + n)).
        Because the prior lives in the accumulators, prediction math is untouched
        and the min_g gate opens immediately — the whole point for tournaments.

        priors      {team: {"att": float, "deff": float}} strength vs league avg
        elo         {team: rating} starting Elo (e.g. carried over / world Elo)
        g0          prior weight in pseudo-games per team
        league_avg  goals per team per game to anchor the pseudo-counts
        xg_ratio    xG-units-per-goal scale (prev totx/totg); 1.0 if unknown
        home_factor prior home/away goals ratio (ignored for neutral venues)
        """
        if priors:
            n_t = len(priors)
            # normalise so factors average 1.0 — keeps the pseudo league average
            # at league_avg regardless of how the caller scaled the strengths
            sa = sum(p["att"] for p in priors.values()) / n_t or 1.0
            sd = sum(p["deff"] for p in priors.values()) / n_t or 1.0
            for t, p in priors.items():
                att, deff = p["att"] / sa, p["deff"] / sd
                self.Fg[t] = self.Fg.get(t, 0.0) + g0 * att * league_avg
                self.Adg[t] = self.Adg.get(t, 0.0) + g0 * deff * league_avg
                self.Fx[t] = self.Fx.get(t, 0.0) + g0 * att * league_avg * xg_ratio
                self.Adx[t] = self.Adx.get(t, 0.0) + g0 * deff * league_avg * xg_ratio
                self.G[t] = self.G.get(t, 0) + g0
            add = g0 * n_t * league_avg          # total pseudo goals injected
            hf = 1.0 if self.neutral else home_factor
            self.totg += add
            self.hsg += add * hf / (1 + hf); self.asg += add / (1 + hf)
            self.totx += add * xg_ratio
            self.hsx += add * xg_ratio * hf / (1 + hf)
            self.asx += add * xg_ratio / (1 + hf)
            self.n += g0 * n_t / 2.0
        if elo:
            for t, r in elo.items():
                self.elo[t] = r

    # ---- ingest one finished match (call AFTER predicting it) ------------- #
    def update(self, m):
        h, a = m["home"], m["away"]
        gh, ga = m["fthg"], m["ftag"]
        eh, ea = self.elo.get(h, 1500.0), self.elo.get(a, 1500.0)

        # goals + xG strengths: real xG when the source provides it (live WC
        # data), else the shots-based proxy (the CSVs carry no xG)
        if m.get("hxg") is not None and m.get("axg") is not None:
            xh, xa = m["hxg"], m["axg"]
        else:
            xh, xa = self._xgproxy(m["hs"], m["as_"], m["hst"], m["ast"])
        self.Fg[h] = self.Fg.get(h, 0) + gh; self.Adg[h] = self.Adg.get(h, 0) + ga
        self.Fg[a] = self.Fg.get(a, 0) + ga; self.Adg[a] = self.Adg.get(a, 0) + gh
        self.Fx[h] = self.Fx.get(h, 0) + xh; self.Adx[h] = self.Adx.get(h, 0) + xa
        self.Fx[a] = self.Fx.get(a, 0) + xa; self.Adx[a] = self.Adx.get(a, 0) + xh
        self.totg += gh + ga; self.hsg += gh; self.asg += ga
        self.totx += xh + xa; self.hsx += xh; self.asx += xa
        self.G[h] = self.G.get(h, 0) + 1; self.G[a] = self.G.get(a, 0) + 1

        # count markets: corners, cards, shots, shots on target, fouls
        for name, (extract, _mx) in self.COUNTS.items():
            hv, av = extract(m)
            if hv is None or av is None:
                continue
            c = self.cnt[name]
            F, A, G = c["F"], c["A"], c["G"]
            F[h] = F.get(h, 0) + hv; A[h] = A.get(h, 0) + av
            F[a] = F.get(a, 0) + av; A[a] = A.get(a, 0) + hv
            G[h] = G.get(h, 0) + 1; G[a] = G.get(a, 0) + 1
            c["tot"] += hv + av; c["n"] += 1

        # referee strictness accumulators (cards / fouls per referee game)
        r = m.get("ref")
        if r:
            for name in self.ref:
                hv, av = self.COUNTS[name][0](m)
                if hv is None or av is None:
                    continue
                tot, g = self.ref[name].get(r, (0.0, 0))
                self.ref[name][r] = (tot + hv + av, g + 1)

        # possession share (live sources only; normalise in case it isn't 100)
        hp, ap = m.get("hp"), m.get("ap")
        if hp is not None and ap is not None and hp + ap > 0:
            sh = hp / (hp + ap)
            self.Pf[h] = self.Pf.get(h, 0.0) + sh
            self.Pf[a] = self.Pf.get(a, 0.0) + (1 - sh)
            self.Pg[h] = self.Pg.get(h, 0) + 1; self.Pg[a] = self.Pg.get(a, 0) + 1

        # Elo update (margin-weighted)
        gd = abs(gh - ga); mult = math.log(gd + 1) + 1
        sc = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        exp = 1 / (1 + 10 ** (-(eh - ea + self._bonus(h)) / 400))
        chg = 20 * mult * (sc - exp)
        self.elo[h] = eh + chg; self.elo[a] = ea - chg
        self.n += 1
