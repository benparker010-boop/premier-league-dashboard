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
