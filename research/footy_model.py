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

Corners and cards get their own shrinkage-Poisson grids.

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
    # corners / cards are optional — keep the match even if absent
    m["hc"], m["ac"] = _f(r, "HC"), _f(r, "AC")
    m["hy"], m["ay"] = _f(r, "HY"), _f(r, "AY")
    m["hr"], m["ar"] = _f(r, "HR"), _f(r, "AR")
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
                 xg_meanmatch=True):
        self.k, self.xg_w, self.elo_sup = k, xg_w, elo_sup
        self.rho, self.min_g, self.neutral = rho, min_g, neutral
        # mean-match the xG-proxy lambdas to the goals scale: the proxy carries
        # the right *relative* strengths but over-states the goal level, so we let
        # goals set the scale and xG only tilt attack/defence. Kills the totals bias.
        self.xg_meanmatch = xg_meanmatch
        # goals + xG-proxy attack/defence accumulators
        self.Fg, self.Adg, self.Fx, self.Adx, self.G = {}, {}, {}, {}, {}
        self.totg = self.hsg = self.asg = 0.0
        self.totx = self.hsx = self.asx = 0.0
        # corners / cards accumulators (for + against, plus games seen)
        self.Cf, self.Ca, self.Cg = {}, {}, {}
        self.Kf, self.Ka, self.Kg = {}, {}, {}
        self.ctot = self.ktot = 0.0
        self.cn = self.kn = 0
        self.n = 0
        self.elo = {}

    # ---- helpers ---------------------------------------------------------- #
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
        bonus = 0.0 if self.neutral else HOME_ELO
        sup = (self.elo.get(h, 1500.0) - self.elo.get(a, 1500.0) + bonus) / 400.0
        lh = max(0.05, lh * 10 ** (self.elo_sup * sup))
        la = max(0.05, la * 10 ** (-self.elo_sup * sup))
        return lh, la

    def goal_grid(self, h, a):
        ls = self.goal_lambdas(h, a)
        if ls is None:
            return None
        return score_grid(ls[0], ls[1], rho=self.rho, mx=MAXG)

    def _count_lambdas(self, Cf, Ca, Cg, ctot, cn, h, a, mx):
        """Generic shrinkage-Poisson for a per-team count market (corners/cards)."""
        if cn == 0 or Cg.get(h, 0) < self.min_g or Cg.get(a, 0) < self.min_g:
            return None
        avg = ctot / (2 * cn)              # league average per team per game

        def fac(t, d):
            g = Cg[t]
            raw = (d[t] / g) / avg if avg > 0 and g > 0 else 1.0
            w = g / (g + self.k)
            return w * raw + (1 - w)

        lh = max(0.05, avg * fac(h, Cf) * fac(a, Ca))
        la = max(0.05, avg * fac(a, Cf) * fac(h, Ca))
        return lh, la

    def corner_grid(self, h, a):
        ls = self._count_lambdas(self.Cf, self.Ca, self.Cg, self.ctot, self.cn, h, a, MAXC)
        return None if ls is None else score_grid(ls[0], ls[1], rho=0.0, mx=MAXC)

    def card_grid(self, h, a):
        ls = self._count_lambdas(self.Kf, self.Ka, self.Kg, self.ktot, self.kn, h, a, MAXK)
        return None if ls is None else score_grid(ls[0], ls[1], rho=0.0, mx=MAXK)

    # ---- ingest one finished match (call AFTER predicting it) ------------- #
    def update(self, m):
        h, a = m["home"], m["away"]
        gh, ga = m["fthg"], m["ftag"]
        eh, ea = self.elo.get(h, 1500.0), self.elo.get(a, 1500.0)

        # goals + xG-proxy strengths
        xh, xa = self._xgproxy(m["hs"], m["as_"], m["hst"], m["ast"])
        self.Fg[h] = self.Fg.get(h, 0) + gh; self.Adg[h] = self.Adg.get(h, 0) + ga
        self.Fg[a] = self.Fg.get(a, 0) + ga; self.Adg[a] = self.Adg.get(a, 0) + gh
        self.Fx[h] = self.Fx.get(h, 0) + xh; self.Adx[h] = self.Adx.get(h, 0) + xa
        self.Fx[a] = self.Fx.get(a, 0) + xa; self.Adx[a] = self.Adx.get(a, 0) + xh
        self.totg += gh + ga; self.hsg += gh; self.asg += ga
        self.totx += xh + xa; self.hsx += xh; self.asx += xa
        self.G[h] = self.G.get(h, 0) + 1; self.G[a] = self.G.get(a, 0) + 1

        # corners
        if m["hc"] is not None and m["ac"] is not None:
            hc, ac = m["hc"], m["ac"]
            self.Cf[h] = self.Cf.get(h, 0) + hc; self.Ca[h] = self.Ca.get(h, 0) + ac
            self.Cf[a] = self.Cf.get(a, 0) + ac; self.Ca[a] = self.Ca.get(a, 0) + hc
            self.Cg[h] = self.Cg.get(h, 0) + 1; self.Cg[a] = self.Cg.get(a, 0) + 1
            self.ctot += hc + ac; self.cn += 1

        # cards (count yellows + reds as bookings)
        if None not in (m["hy"], m["ay"], m["hr"], m["ar"]):
            hk, ak = m["hy"] + m["hr"], m["ay"] + m["ar"]
            self.Kf[h] = self.Kf.get(h, 0) + hk; self.Ka[h] = self.Ka.get(h, 0) + ak
            self.Kf[a] = self.Kf.get(a, 0) + ak; self.Ka[a] = self.Ka.get(a, 0) + hk
            self.Kg[h] = self.Kg.get(h, 0) + 1; self.Kg[a] = self.Kg.get(a, 0) + 1
            self.ktot += hk + ak; self.kn += 1

        # Elo update (margin-weighted)
        gd = abs(gh - ga); mult = math.log(gd + 1) + 1
        sc = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        bonus = 0.0 if self.neutral else HOME_ELO
        exp = 1 / (1 + 10 ** (-(eh - ea + bonus) / 400))
        chg = 20 * mult * (sc - exp)
        self.elo[h] = eh + chg; self.elo[a] = ea - chg
        self.n += 1
