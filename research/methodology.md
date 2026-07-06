# Statistical Match Predictor — Methodology & Results

A model that predicts football match stats and outcomes, built for the World Cup 2026 dashboard and validated against real Premier League data. This documents how it works, how it was tested, what it scored, and its limits.

## What it does

Given two teams, it predicts:

- expected goals for each side,
- the most likely scoreline,
- win / draw / win probabilities.

It's live in the app under **AI analysis → Statistical match predictor**.

## Why this model (and not a neural network)

Football match prediction is a small-data, high-noise problem — at the World Cup a team plays only three group games. Deep neural nets need thousands of examples and overfit badly here. The professional standard for this task is a **Poisson attack/defence model** (the Dixon–Coles family), which is exactly what bookmakers and analysts use. It's interpretable, robust on tiny samples, and well-calibrated.

## How it works

Each team gets two strengths, measured relative to the tournament average:

- **Attack** = how many goals it scores per game ÷ league average.
- **Defence** = how many it concedes per game ÷ league average.

Expected goals for a fixture combine them:

```
expected_goals(A) = league_avg × attack(A) × defence(B)
expected_goals(B) = league_avg × attack(B) × defence(A)
```

Those two numbers feed a **Poisson distribution** over scorelines, which gives the probability of every result and hence win/draw/win.

### The key ingredient: shrinkage

With only a few games, a team that happened to score 4 once looks unstoppable. So each strength is **shrunk toward the league average**, weighted by how many games the team has played:

```
strength = w × (team rate) + (1 − w) × 1.0,   where w = games / (games + k)
```

A team with 3 games is pulled strongly toward average; a team with 20 games is trusted. This is the single most important feature for the World Cup, where samples are tiny.

## How it was validated

I pulled **real 2023-24 Premier League match data** (goals, shots, shots on target, corners) and ran a **walk-forward backtest**: for each match, the model predicted using *only the games played before it*, then I compared to what actually happened. This is the honest way to test a predictor — no peeking at the future.

### Results (real PL matches)

| Version | Goals MAE | Shots MAE | Outcome accuracy | Brier score |
|---|---|---|---|---|
| No shrinkage | 1.10 | 4.18 | 50% | 0.602 |
| **Shrinkage k=4** | **1.01** | **3.91** | **52%** | **0.589** |
| Shrinkage k=8 | 1.00 | 3.99 | 54% | 0.598 |
| Naive baseline | 1.06 | 4.55 | — | 0.674 |

Reading this:

- **MAE** = average error. The model predicts goals to within ~1.0 and shots within ~3.9 per team — beating the "just guess the league average" baseline.
- **Outcome accuracy** ~52-54% across three outcomes (random is 33%).
- **Brier score** 0.589 vs 0.674 baseline — lower is better; this is a real, measurable improvement in probability quality.
- **Shrinkage clearly helped** — that's the model *learning* the right amount to trust small samples. This is exactly what makes it suitable for a 3-game World Cup group stage.

The sample here is small (≈48 predictable matches), so treat the exact numbers as indicative. To get robust figures, run the backtest harness below on several full seasons.

## How to run the full backtest yourself

I've included `footy_backtest.py`. It reads football-data.co.uk season CSVs and runs the same walk-forward test on thousands of matches.

1. Download a few season files (free) from `https://www.football-data.co.uk/englandm.php` — the "Premier League" CSVs (e.g. 2021-22, 2022-23, 2023-24). Save them in a folder, e.g. `seasons/`.
2. Run: `python footy_backtest.py seasons/` (in the Terminal tab inside PyCharm).
3. It prints MAE, accuracy and Brier across all the matches, and compares shrinkage settings.

## Upgrades tested — across three real seasons

I implemented every backtestable upgrade and ran a feature ablation across **three full Premier League seasons** (2021-22, 2022-23, 2023-24; 116 predictable matches after each team had played a few games):

| Model | Outcome accuracy | Brier | Goals MAE |
|---|---|---|---|
| Base (shrinkage, goals) | 44.8% | 0.633 | 1.01 |
| + recency weighting | 41.4% | 0.631 | 1.00 |
| **+ xG-style signal (shots-based)** | **50.0%** | **0.617** | 1.13 |
| + Elo prior | 45.7% | 0.624 | 1.01 |
| + opponent-strength adjustment | 46.6% | 0.637 | 1.02 |
| All combined | 46.6% | 0.615 | 0.96 |
| Naive base-rate (guess) | — | 0.664 | — |

What the bigger sample showed:

- The **xG-style signal is the clear winner** — accuracy 44.8% → 50.0%, and the best probability quality (Brier) on its own. This matches the analytics consensus that xG predicts better than raw goals.
- **Recency weighting actually hurt** (41.4%) — it over-weights tiny early-season samples — so it was dropped.
- **Elo** and **opponent adjustment** gave only small/mixed gains.
- Every variant beat the naive baseline (Brier 0.664), confirming real skill.

### What went into the live predictor

Based on these results the app's predictor now uses: the shrinkage Poisson model **blended with an xG-based strength** (using the app's real xG, which should beat the shots proxy), a small **Elo prior**, an **opponent-strength adjustment**, and a manual **injury-impact slider** per team. Recency was tested and deliberately left out because it lowered accuracy.

## Honest limitations

- It models **goals** directly (opponent-adjusted). The same engine extends to shots, possession, xG, etc., but those need each team's *conceded* stats aggregated too — a straightforward next step if you want them in the predictor.
- It uses **current-tournament form only**. It doesn't yet blend in pre-tournament team ratings (e.g. world ranking), which would help early on when samples are tiny. That's the most promising upgrade.
- World Cup games are **neutral-venue**, so no home advantage is applied (correct for the tournament; the PL backtest does include it).
- It's a model, not a crystal ball — football is genuinely high-variance. Treat outputs as informed probabilities, not certainties.

## Sensible next steps

1. Blend in a **prior rating** (FIFA ranking or Elo) so early-tournament predictions aren't purely 3-game noise.
2. Extend the opponent-adjusted model to **shots, xG, possession and cards** (needs conceded-stat aggregation).
3. Add **Dixon–Coles low-score correction** (improves 0-0 / 1-0 / 1-1 probabilities specifically).
4. Run the **full multi-season backtest** to tune the shrinkage `k` precisely.

---

# Multi-market model & value finder (research build, not yet live)

This extends the single-outcome predictor into a **multi-market model** that prices
result, scoreline, totals, BTTS, corners and cards, plus an **odds-comparison
("value finder")** tool. Built and validated entirely in `research/`; nothing here
has been deployed to `app.py`. Validated on **10 Premier League seasons
(2014-15 … 2023-24, 3,800 matches)**.

### Files
- `footy_model.py` — the engine. One **score grid** per fixture (shrinkage Poisson
  + xG blend + Elo folded in as a supremacy shift + Dixon–Coles) so result /
  scoreline / O-U / BTTS are all internally consistent. Separate shrinkage-Poisson
  grids for corners and cards.
- `odds_tools.py` — implied prob, **margin removal (de-vig)**, fair odds, edge, flag.
- `value_backtest.py` — calibration, closing-line benchmark, value-bet ROI + CLV.
- `tune.py` — knob sweeps (k, xg_w, elo_sup, rho) with an out-of-sample check.
- `markets_report.py` — calibration of every market against real outcomes.
- `predict_demo.py` — per-fixture fair-odds card (prob / fair odds / book / edge / flag).
- `live_odds.py` — The Odds API client for live World Cup odds (stub until a key is set).

### Key model improvement: xG mean-matching
The shots-based xG proxy carries good *relative* strength but **over-states the goal
level**, which biased every totals/BTTS market high (model said 65% overs when
reality was 56%). Fix: let **goals set the scale** and xG only tilt attack/defence
(rescale the xG lambdas by `total_goals / total_xg`). Result on 10 seasons:

| | Accuracy | Brier | ECE | Totals bias |
|---|---|---|---|---|
| xG mean-match OFF | 0.540 | 0.578 | 0.039 | **+0.097** |
| **xG mean-match ON** | 0.540 | **0.575** | **0.023** | **−0.007** |

No accuracy cost, better Brier and calibration, and the totals bias is gone.

### Validated config
`k=8, xg_w=0.7, elo_sup=0.10, rho=0.0, xG mean-match on`. Tuning gains are modest on
Brier (a flat optimum) but real on calibration; an out-of-sample check (knobs chosen
on the first 60% of seasons, scored on the last 40%) confirms they generalise.

### Calibration — every market is trustworthy
Reliability ECE (lower = better; 0 = perfect) on 10 seasons:

| Market | ECE | | Market | ECE |
|---|---|---|---|---|
| Over 1.5 | 0.016 | | BTTS | 0.008 |
| Over 2.5 | 0.012 | | Over 9.5 corners | 0.048 |
| Over 3.5 | 0.014 | | Over 3.5 cards | 0.031 |

Corners and cards are unbiased on the mean (predicted vs actual totals within 0.1).

### The honest finding: no edge vs the closing line
The value finder works, and it says there is **no genuine value** in EPL match-result
or O-U 2.5 against the bookmaker **closing line**:

- The model is **less sharp than the closing line** (model 1X2 Brier ~0.575 vs
  de-vigged closing ~0.564). The closing line — especially Pinnacle — is the hardest
  estimate in sport to beat.
- Betting flagged picks into **opening** odds and measuring **closing-line value
  (CLV)** — the proper, low-noise test of foresight — gives **negative CLV** (~−4 to
  −5%); our picks beat the close only ~40% of the time.
- A naive flat-ROI backtest looked near-break-even on one market, but CLV exposed
  those as bad bets that merely landed. **Always judge value by CLV, not flat ROI.**

Calibration (Platt logistic recalibration, fit on a training split) makes the
probabilities trustworthy (1X2 holdout ECE 0.035 → 0.006) but **cannot manufacture
an edge that isn't there**.

### What this means
- The model is excellent for **accurate, well-calibrated odds** across many markets —
  valuable for the dashboard's predictor display.
- For finding genuine **value**, the efficient EPL goal markets are a dead end. Real
  value, if anywhere, lives in **softer markets** — corners, cards, BTTS, and the
  **live World Cup odds** (via The Odds API), where books are less efficient.

### Remaining next steps
1. Validate the model against **live World Cup odds** once an Odds API key is set.
2. Tighten the **corners** over/under calibration (slightly over-confident at high lines).
3. If desired, port the validated engine (esp. xG mean-matching + Dixon–Coles) into
   `app.py`'s `predict_fixture` — **pending Ben's go-ahead**.

---

# Pre-tournament priors (validated — the cold-start fix)

The live predictor is **cold-start**: it knows only current-tournament form, so
early predictions are noise and fixtures where a team has under `min_g` games
can't be predicted at all. This upgrade seeds each team with a **prior rating**
before a ball is kicked, implemented as **Bayesian pseudo-counts**
(`Model.inject_prior` in `footy_model.py`): each team starts as if it had already
played `g0` games at its prior strength, and real results wash the prior out at
exactly the rate the shrinkage machinery already uses. Prediction math is
untouched, and the `min_g` gate opens from game 1.

## How it was tested (`prior_backtest.py`)

On the 10 PL seasons, "last season's final strength + Elo (regressed, promoted
teams get a below-average default)" plays the role of the pre-tournament rating.
Three variants, identical validated knobs, walk-forward, scored on seasons 2–10:

| Variant (3,057 common fixtures) | Accuracy | Brier | ECE |
|---|---|---|---|
| A — continuous (old backtest behaviour) | 0.541 | 0.572 | 0.015 |
| B — cold start each season (= live predictor today) | 0.546 | 0.576 | 0.009 |
| **C — cold start + priors** | **0.548** | **0.569** | **0.008** |

- **Early window** (teams' first 0–5 games — the group-stage analog): priors cut
  the cold-start Brier **0.611 → 0.581**, fully recovering the accuracy of a model
  carrying 10 years of history.
- **Coverage**: +363 fixtures (+12%) that the cold-start model could not predict
  at all, priced at Brier 0.587 vs 0.657 for naive base rates.
- **Holdout check**: knobs selected on seasons 2–6 confirm on unseen seasons 7–10
  (C Brier 0.576 vs B 0.581, ECE 0.007).

## Validated config

`g0=10, carry=0.9, elo_carry=0.9` — a flat optimum across g0 10–14 and
carry/elo_carry 0.9–1.0; beyond g0≈20 the prior overstays its welcome. Strengths
carry almost unregressed because `strengths()` already includes the model's own
smoothing.

## Applying it to the World Cup

There is no "last season", so seed from public pre-tournament ratings:

1. **Elo**: World Football Elo Ratings (eloratings.net) map directly onto
   `inject_prior(elo=...)` — same 1500-centred scale.
2. **Attack/defence factors**: derive from the Elo gap to the field average
   (e.g. `att = 10^(s·Δelo/400)`, `deff = 10^(−s·Δelo/400)` with s tuned so the
   implied goal supremacy matches historical international results), or from
   qualifying-stage goals data.
3. Keep `g0≈10`: after the 3 group games the prior still carries ~77% weight —
   correct, because 3 games carry almost no signal — and it fades through the
   knockout rounds.

**Implemented and validated on WC 2026** (`wc_priors.py`, seeded by default in
`predict_fixture_live.py`; `--no-prior` reverts). Pre-tournament Elo comes from
eloratings.net (snapshot `wc2026_elo.tsv`, reconstructed as current rating minus
in-tournament change, so it is look-ahead-free); attack/defence factors are
`10^(±s·Δelo/400)` with `s=0.30` (best calibration in the sweep). Walk-forward
replay of the 91 tournament matches played so far:

| | n | Accuracy | Brier |
|---|---|---|---|
| Cold start (old behaviour) | 43 | 0.558 | 0.590 |
| **Prior-seeded, same fixtures** | 43 | **0.628** | **0.478** |
| Prior-seeded, ALL matches | **91** | 0.604 | 0.538 |

Priors also double coverage: the cold model couldn't price the first two rounds
of group games at all.

---

# Stat markets: shots, shots on target, fouls, possession

The count-market machinery (previously corners + cards only) is now generic
(`Model.COUNTS` / `count_grid()` in `footy_model.py`): **shots**, **shots on
target** and **fouls** each get their own opponent-adjusted shrinkage-Poisson
grid, so per-team expected values and any over/under line come off the same
engine. `wc_data.py` now also pulls fouls and possession from TheStatsAPI.

## Validation (10 PL seasons, walk-forward — `markets_report.py`)

| Market | Mean bias | Per-team MAE | vs naive MAE | O/U line ECE |
|---|---|---|---|---|
| Total shots | −0.11 | **3.83** | 4.39 | 0.026 (O24.5) |
| Shots on target | −0.23 | **1.81** | 1.99 | 0.038 (O8.5) |
| Fouls | +0.19 | **2.71** | 2.79 | 0.015 (O20.5) |
| Corners | +0.09 | 2.24 | 2.38 | 0.036 (O9.5) |
| Cards (unchanged) | −0.00 | 1.03 | 1.05 | 0.031 (O3.5) |

All unbiased on the mean and all beat the naive league-average baseline. Shots
carry the most team signal (13% MAE improvement); fouls the least (they're
mostly referee/game-state noise — expectations are honest but flat).

## Negative-binomial dispersion (validated — fixes the tail over-confidence)

Real shot/corner/foul counts are over-dispersed vs Poisson (variance > mean), so
pure-Poisson over/unders were too confident at high and low lines. Count grids
now use **negative-binomial marginals** with one dispersion knob `r` per market
(`Model.DISP`; variance = λ + λ²/r; r=∞ is Poisson). Tuned in `disp_tune.py`
across a pool of lines per market, selected on the first 60% of fixtures,
confirmed on the 40% holdout:

- **Adopted**: corners r=20, shots r=40, fouls r=40 — holdout ECE at the
  headline lines improved to the table above (corners 0.048→0.036, shots
  0.040→0.026, fouls 0.023→0.015), with small Brier gains too.
- **Rejected honestly**: cards (train win did not generalise to the holdout) and
  shots on target (Poisson already optimal) stay Poisson.
- Goals are untouched — they are well-modelled by Poisson + Dixon–Coles.

## Possession

`Model.possession_share(h, a)` predicts the possession split: each team's mean
share is shrunk toward 50%, then combined Bradley-Terry style (log-odds), so
strong-vs-weak widens and strong-vs-strong stays near 50/50. **Not backtested**
— football-data CSVs carry no possession — so treat it as a sensible display
estimate until enough World Cup matches accumulate to check it against
(`wc_data` now records `hp`/`ap`).

---

# July 2026 upgrade batch (all validated before adoption)

1. **Platt recalibration at the display layer** (`calib.py`, applied in the
   fixture card). Coefficients fitted on all 3,704 PL fixtures: 1X2 A=0.96,
   O/U2.5 A=0.90, BTTS A=0.83 — the model was mildly over-confident everywhere.
   Approach holdout-validated earlier (1X2 ECE 0.035→0.006).
2. **Market blend** (`blend_tune.py`, helper in `odds_tools.blend`). Against the
   de-vigged EPL closing consensus the market alone is near-optimal (holdout
   Brier 0.5510 at w=1.0 vs 0.5707 model-only); adopted **w=0.9 market share**
   for live odds (softer/earlier than a closing line). Shown as "blended final
   probabilities" in `predict_fixture_live --odds`.
3. **Host advantage** (+100 Elo when USA/Mexico/Canada are the designated home
   side; `Model.hosts`/`host_elo`, applied in prediction AND Elo ingestion).
   Replay sweep improves host-game Brier 0.506→0.480 at +100, but only 9 host
   home games exist — +100 is the historical standard, not a fitted optimum.
4. **Referee strictness factor** for cards/fouls (`Model.ref_factor`,
   `ref_backtest.py`). Referee announced pre-match = legitimate walk-forward
   info. Holdout: cards Brier 0.1683→0.1670, fouls 0.1857→0.1827 (both with
   better ECE and MAE). Shrinkage `ref_k`: cards 40, fouls 20. The main
   calibration report now uses it.
5. **Real xG for the WC** (cache rebuilt via `wc_ingest --rebuild`; all 91
   matches now carry xG, fouls, possession). `Model.update` prefers real xG
   over the shots proxy. WC replay improved again: all-91 Brier 0.538→0.533,
   accuracy 60.4%→61.5%.
6. **Knockout advance tool** (`wc_sim.py`): scheduled fixtures with calibrated
   W/D/W plus P(advance) = P(win 90') + P(draw)·P(win ET/pens), where the
   ET/pens leg carries half the Elo edge (shootouts are near-random).
7. **Daily auto-ingest**: a scheduled task runs `wc_ingest.py` every morning at
   08:00, so the cache (and therefore every prediction) refreshes itself.
