# Football Analytics Web App — Design Brief & Context

> Paste this whole document into a fresh Claude conversation when you want help improving the app's design. It describes the real, current state of the app so suggestions build on what exists rather than starting from scratch. After pasting, ask for whatever you need — e.g. *"suggest a more premium visual treatment for the match-detail page"*, *"give me the CSS"*, *"mock up a mobile layout"*, or *"audit my colour system for consistency"*.

---

## 1. What the app is

A **World Cup 2026 analytics dashboard** — a live tournament data site with a statistical match predictor baked in. It shows live scores, group standings, top scorers/assists, team and player pages, a knockout-bracket simulator, AI-written analysis, and rich match-detail pages with a formation pitch view and a Poisson-based model prediction.

- **Who it's for:** football fans browsing tournament data, and recruiters/hiring managers viewing it as a **portfolio piece** for a business/data-analyst role. So it needs to look credible and polished — "a real product", not a class project.
- **Tone/benchmark:** modern sports-stats apps — **FotMob / Sofascore** — clean, data-dense, dark, premium.

---

## 2. Tech stack & hard constraints

A designer/Claude must work within these — they shape what's feasible.

- **Streamlit (Python), single-file app (`app.py`, ~2,300 lines).** Deployed on **Streamlit Community Cloud** (free tier: ~1 GB RAM, the app sleeps when idle and wakes on visit).
- **All styling is injected CSS + inline HTML.** There is no React/Vue/Tailwind. UI is built by `st.markdown('<style>…</style>')` blocks and HTML strings rendered with `unsafe_allow_html=True`. Custom components = hand-written HTML/CSS, occasionally a tiny `components.html()` JS snippet.
- **Restyling Streamlit's own widgets is limited and fragile.** Buttons, selectboxes, text inputs and tab internals can only be reached via CSS targeting `data-testid="…"` / `data-baseweb="…"` selectors, which can break when Streamlit updates. Prefer custom HTML components over fighting native widgets.
- **Navigation is query-param based with full-page reloads**, not a single-page app. Links look like `?view=match&match=<id>` and use `target="_self"`. There are **no client-side route transitions/animations**.
- **Performance matters.** All API data is cached with `st.cache_data` (TTLs 120–1800s). Designs must not require heavy per-render work or large uncached payloads.
- **No new paid dependencies, ideally no new dependencies at all.** Current deps: `streamlit`, `pandas`, `requests`, `anthropic`. External assets in use: **Google Fonts** (Oswald) via CDN, **flagcdn.com** for country flags, committed hero/banner images in `/images`.
- Data sources: TheStatsAPI (live match data; keyed) and the Anthropic API (AI summaries; gated behind buttons to control cost).

---

## 3. Current design system

### 3.1 Colour palette (actual hex values in use)

**Brand / accent — gold** (the signature colour, by far the most-used):
- `#e8b84b` — **primary accent / "home" team colour / brand gold** (borders, labels, active states, headings underline)
- `#c8941f` — deeper gold (Streamlit theme `primaryColor`)
- Gold gradient (home jerseys, bars): `#f0c659 → #e0a82f`; also `#caa23f`, `#f0cf6a`
- Light gold text accents: `#ffe9a8`, `#ffe0a3`, `#f3d489`

**Secondary — "away" team blue:**
- `#7fb6d6` and `#5b8fb0` (core away colour)
- Lighter: `#8fc0dd`, `#bfe0f2`; jersey text on blue: `#042231`

**Dark surfaces / backgrounds:**
- `#0d1420` — main dark navy app background
- Page "glow" gradient (data pages): `radial-gradient(circle at 22% 12%, #1a2c46 0%, #0a0f18 62%)`
- Other darks in gradients: `#0c1b2e`, `#0a0f18`, `#1c2336`, `#1a2c46`
- **Cards:** background `rgba(255,255,255,0.04)`, border either `rgba(232,184,75,0.30)` (gold, for match/score cards) or `rgba(255,255,255,0.08)` (neutral), radius `12px`
- Pitch green (formation view): base `#11652f` with subtle mowing stripes

**Text:**
- Primary `#ffffff`; muted tiers `rgba(255,255,255,0.6)`, `0.55`, `0.45`

**Semantic:**
- Win / qualified / positive: `#37b86b` (green), light `#7fe0b0`
- Loss / red card / danger: `#e24b4a`, soft `#e98a88`
- Live indicator: `#ff5b52`; live badge fill `#b3261e`

### 3.2 Typography

- **Oswald** (Google Fonts, weights 300–700) applied globally to everything. It's a condensed, slightly industrial sans — gives the sporty/broadcast feel. Headings are typically **uppercase, 700 weight, letter-spaced**.
- Numeric figures use `font-variant-numeric: tabular-nums` so stat columns align.
- Rough scale in use: hero title 56px; section headings 26–38px; card titles 14–19px; stat values 17–31px; labels 10–13px uppercase.

### 3.3 Theme config note (a real inconsistency to be aware of)

`.streamlit/config.toml` sets a **light** base theme:
```toml
[theme]
base = "light"
primaryColor = "#c8941f"
backgroundColor = "#f6f7f9"
secondaryBackgroundColor = "#ffffff"
textColor = "#1a2230"
font = "sans serif"
```
…but the app then **overrides surfaces to dark** with injected CSS on every page. The net effect is a dark UI, but some Streamlit-native chrome/widgets can still inherit light styling. Unifying this (e.g. moving to a proper dark base theme) is a legitimate cleanup.

### 3.4 Layout patterns

- **Wide layout** (`layout="wide"`). Streamlit's default chrome is hidden (`#MainMenu`, `footer`, top header all `display:none`).
- **Per-page backgrounds:** home uses a full-bleed hero photo; data pages use the radial "glow" gradient; the team grid uses faint SVG pitch markings over `#0d1420`.
- **Card-based** content on translucent panels with gold/neutral borders, 12px radius.
- **Section headings:** a custom `_heading()` (uppercase Oswald + a short gold underline bar) and small `.lv-sect` gold uppercase labels above blocks.
- Responsive touches exist (`@media (max-width:700px)` collapses the menu grid; `640px` collapses two-column match grids) but the app is **desktop-first**.

### 3.5 Notable custom components (build on these, don't reinvent)

- **`.lv-card`** — the core surface: translucent white card, gold border, 12px radius. Used for score header, match cards, panels.
- **Score-row list (`.lvr`)** — compact, date-grouped live-score rows (status/teams/score), clickable to the match page.
- **Stat comparison bars (`.cmp` / `.cmp-bar`, older `.ms-bar`)** — side-by-side home-vs-away rows: left value (gold), centred uppercase label, right value (blue), plus a split progress bar; the **leading side is brightened, the trailing side dimmed**. This is the workhorse of the stats UI.
- **Tabbed stats panel** — styled `st.tabs` (gold active underline) holding the match-centre categories.
- **Formation pitch view (`.pitch`)** — an SVG-marked, subtly-striped green pitch with **absolutely-positioned jersey nodes** (gold gradient = home at the bottom, blue gradient = away at the top), each showing shirt number + surname, laid out by parsed formation lines (GK → defence → midfield → attack).
- **Substitutions list** — `▲ ON` (green) / `▼ OFF` (red) pairs with the minute.
- **Group standings tables (`.gs-table`)** — qualification markers via coloured left edges (green = through, gold = playoff/3rd).
- **Knockout bracket** — rendered as SVG.
- **Hero + menu cards** — home hero with gold stat counters; 6 image-backed menu cards with a frosted title bar.
- **Flags** — `flagcdn.com` images keyed by a country→ISO map.

---

## 4. Page / route map

Query-param routing on a single Streamlit app (`?view=…`):

| Route | What it shows |
|---|---|
| `home` (default) | Full-bleed hero (title, tagline, gold stat counters) + the menu cards. |
| `menu` | The six image-backed section cards. |
| `standings` | Group tables with qualification colour-coding + a deterministic Round-of-32 projection. |
| `scorers` | Top 10 scorers & assists. |
| `bracket` ("Live scores") | Date-grouped live/finished/upcoming score rows; each links to a match page. |
| `players` | Player search → player profile cards. |
| `stats` ("Team stats") | Flag grid of teams → team page. |
| `ai` | AI tournament analysis + an AI-predicted bracket (gated, button-triggered). |
| `team` (`&team=<id>`) | Individual team page (form, stats, etc.). |
| `match` (`&match=<id>`) | **Rich match-detail page — see below.** |

### 4.1 Match-detail page — current structure (the flagship page)

1. **Score header card** — status badge (LIVE / FULL TIME / kickoff time), both flags, the scoreline, and **goalscorers with minutes shown directly under the score**.
2. **Team colour legend** — a slim key: home = gold, away = blue (so the comparison bars read correctly).
3. **Tabbed "match centre"** — one tab strip is the single home for **events + stats**:
   - **Key events** (first tab): a two-sided timeline (home left/gold, away right/blue) of goals, cards, subs, penalties, VAR with minutes and icons.
   - **Shooting · Passing · Duels & defending · Goalkeeping · Discipline & set pieces**: ~45 team stats as the comparison bars (possession, xG, shots breakdown, big chances, pass accuracy, crosses, long balls, duels %, tackles, interceptions, clearances, recoveries, saves, goals prevented, offsides, cards, corners, etc.).
4. **Player ratings & Man of the Match** — gated behind a button (extra API call); top performer + per-team rating lists with goals/assists.
5. **Model prediction card** — the in-house Poisson model: a Win/Draw/Win % bar, most-likely scoreline, and expected goals.
6. **Line-ups** — the **formation pitch view** (both XIs positioned by formation) + the **substitutions** list (▲ on / ▼ off, with minute).
7. **AI match summary** — gated button; a short Claude-written recap/preview from the match's own data.

---

## 5. Enhancement goals (where design help is wanted)

Concrete areas to improve — prioritise visual polish and a more premium, consistent feel:

1. **Premium visual lift.** Make it feel like a paid product. Better use of depth (shadows, subtle gradients, glassmorphism done tastefully), refined spacing rhythm, micro-typographic hierarchy. The match-detail page and live-scores list are the highest-traffic surfaces.
2. **Colour-system consistency.** The palette grew organically (many near-duplicate golds/blues). Help consolidate into a tight, named token set (e.g. `--gold-500`, `--blue-500`, surface/border/text tiers) and apply it consistently. Resolve the **light-base-theme vs dark-CSS** mismatch.
3. **Mobile responsiveness.** It's desktop-first; the match-detail page (especially the formation pitch, tabs, and two-column grids) needs a deliberate mobile layout. Recruiters often open links on a phone.
4. **The formation pitch** could be more premium — better jersey nodes, clearer name legibility on green, optional team-colour theming, smarter spacing so names don't collide on crowded lines.
5. **Stat comparison bars** — refine the visual language (leader emphasis, animated fills on load, optional sparkbars/iconography) without losing scannability.
6. **Empty / loading / error states.** Make "not played yet", rate-limit notices, and gated-button placeholders look intentional and on-brand.
7. **Navigation & wayfinding.** Because it's full-page-reload routing, the back-links and section entry points carry a lot of weight; they could be more elegant and consistent across pages.
8. **Home & menu** — the hero and six cards set the first impression; worth a polish pass for a stronger "wow".

---

## 6. How to use this brief with Claude

Good asks once you've pasted this in:
- "Propose a refined, consolidated colour-token system from my current palette, with hex values and where to apply each."
- "Redesign the match-detail score header (with goalscorers) — give me the HTML + CSS I can drop into a Streamlit `st.markdown(..., unsafe_allow_html=True)` block."
- "Give me a mobile-first responsive treatment for the formation pitch and the tabbed stats panel."
- "Audit my design for FotMob/Sofascore-level polish and list the 10 highest-impact, lowest-effort changes."
- "Show me a tasteful loading/skeleton state for the live-scores list that works within Streamlit's constraints."

**When giving CSS, remember the constraints in §2:** it must work as injected `<style>` + inline HTML inside Streamlit (no build step, no JS framework, minimal reliance on Streamlit's internal `data-testid` selectors), stay performant, and add no paid dependencies.
