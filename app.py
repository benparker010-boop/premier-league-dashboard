import streamlit as st
import pandas as pd
import requests
import anthropic
import time
import os
import base64

st.set_page_config(page_title="World Cup 2026 Analytics", layout="wide")

STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"
AI_MODEL = "claude-haiku-4-5-20251001"
PREDICT_MODEL = "claude-sonnet-4-6"

# Snapshot files (committed to the repo) so the scorer/assist tables are
# shown instantly on every visit without rebuilding from the API each time.
SCORERS_CSV = "top_scorers.csv"
ASSISTS_CSV = "top_assists.csv"

# Hero accent colour for the title numbers / scroll cue. Change to suit the
# background photo: gold "#e8b84b", green "#37b86b", or white "#ffffff".
ACCENT = "#e8b84b"


# ===================== Data layer (TheStatsAPI) =====================
def stats_headers():
    return {"Authorization": f"Bearer {st.secrets['STATS_API_KEY']}"}


class RateLimited(Exception):
    pass


def stats_get(path, params=None, retries=3):
    """GET from TheStatsAPI; if rate-limited (429), wait and retry a few times."""
    url = f"{STATS_BASE}{path}"
    last = None
    for i in range(retries):
        last = requests.get(url, headers=stats_headers(), params=params, timeout=15)
        if last.status_code != 429:
            return last
        try:
            wait = int(last.headers.get("Retry-After", 3 + i * 3))
        except (TypeError, ValueError):
            wait = 3 + i * 3
        time.sleep(min(wait, 8))
    raise RateLimited("TheStatsAPI rate limit reached. Wait about a minute and try again.")


@st.cache_data(ttl=600)
def wc_matches(status):
    r = stats_get("/football/matches",
                  {"competition_id": WC_COMP, "season_id": WC_SEASON,
                   "status": status, "per_page": 100})
    r.raise_for_status()
    return r.json().get("data", [])


@st.cache_data(ttl=600)
def wc_match_stats(match_id):
    r = stats_get(f"/football/matches/{match_id}/stats")
    r.raise_for_status()
    return r.json().get("data", {})


@st.cache_data(ttl=3600)
def search_player(name):
    r = stats_get("/football/players", {"search": name})
    r.raise_for_status()
    return r.json().get("data", [])


@st.cache_data(ttl=600)
def player_wc_stats(player_id):
    r = stats_get(f"/football/players/{player_id}/stats", {"season_id": WC_SEASON})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("data", {})


@st.cache_data(ttl=1800)
def match_player_stats(match_id):
    """Per-player stat sheet for one match — includes goals and assists."""
    r = stats_get(f"/football/matches/{match_id}/player-stats")
    r.raise_for_status()
    data = r.json().get("data", [])
    return data if isinstance(data, list) else []


def build_team_name_map(*match_lists):
    m = {}
    for lst in match_lists:
        for mt in lst:
            for side in ("home_team", "away_team"):
                t = mt.get(side) or {}
                if t.get("id") and t.get("name"):
                    m[t["id"]] = t["name"]
    return m


def build_group_standings(matches):
    groups = {}
    for m in matches:
        g = m.get("group_label")
        hs, a_s = m["score"]["home"], m["score"]["away"]
        if not g or hs is None or a_s is None:
            continue
        home, away = m["home_team"]["name"], m["away_team"]["name"]
        gd = groups.setdefault(g, {})
        for t in (home, away):
            gd.setdefault(t, {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0})
        gd[home]["P"] += 1; gd[away]["P"] += 1
        gd[home]["GF"] += hs; gd[home]["GA"] += a_s
        gd[away]["GF"] += a_s; gd[away]["GA"] += hs
        if hs > a_s:
            gd[home]["W"] += 1; gd[home]["Pts"] += 3; gd[away]["L"] += 1
        elif a_s > hs:
            gd[away]["W"] += 1; gd[away]["Pts"] += 3; gd[home]["L"] += 1
        else:
            gd[home]["D"] += 1; gd[away]["D"] += 1
            gd[home]["Pts"] += 1; gd[away]["Pts"] += 1
    out = {}
    for g, teams in groups.items():
        rows = [dict(s, Team=n, GD=s["GF"] - s["GA"]) for n, s in teams.items()]
        df = pd.DataFrame(rows)[["Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]]
        out[g] = df.sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)
    return out


# ============== Deterministic tournament simulator (no AI) ==============
ROUND_NAMES = {32: "Round of 32", 16: "Round of 16", 8: "Quarter-finals",
               4: "Semi-finals", 2: "Final"}


def _strength(row):
    return (int(row["Pts"]), int(row["GD"]), int(row["GF"]))


def group_predictions(groups):
    rows = []
    for g in sorted(groups):
        df = groups[g]
        rows.append({
            "Group": g,
            "Predicted Winner": df.iloc[0]["Team"] if len(df) >= 1 else "—",
            "Pts (W)": int(df.iloc[0]["Pts"]) if len(df) >= 1 else 0,
            "Runner-up": df.iloc[1]["Team"] if len(df) >= 2 else "—",
            "Pts (R)": int(df.iloc[1]["Pts"]) if len(df) >= 2 else 0,
        })
    return pd.DataFrame(rows)


def qualified_from_groups(groups):
    winners, runners, thirds = [], [], []
    for g in sorted(groups):
        df = groups[g]
        if len(df) >= 1:
            r = df.iloc[0]; winners.append(dict(name=r["Team"], group=g, pos=1, key=_strength(r)))
        if len(df) >= 2:
            r = df.iloc[1]; runners.append(dict(name=r["Team"], group=g, pos=2, key=_strength(r)))
        if len(df) >= 3:
            r = df.iloc[2]; thirds.append(dict(name=r["Team"], group=g, pos=3, key=_strength(r)))
    thirds.sort(key=lambda t: t["key"], reverse=True)
    return winners + runners + thirds[:8]


def _largest_pow2(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


def _seed_order(n):
    order = [1, 2]
    while len(order) < n:
        m = len(order) * 2
        new = []
        for s in order:
            new += [s, m + 1 - s]
        order = new
    return order


def _play(a, b):
    if a["key"] > b["key"]:
        return a
    if b["key"] > a["key"]:
        return b
    return a if a["name"] < b["name"] else b


def simulate_bracket(qualified):
    teams = sorted(qualified, key=lambda t: t["key"], reverse=True)
    size = _largest_pow2(len(teams))
    if size < 2:
        return [], None
    teams = teams[:size]
    seeds = {i + 1: t for i, t in enumerate(teams)}
    field = [seeds[s] for s in _seed_order(size)]
    rounds = []
    while len(field) > 1:
        rname = ROUND_NAMES.get(len(field), f"Round of {len(field)}")
        matches, nxt = [], []
        for i in range(0, len(field), 2):
            a, b = field[i], field[i + 1]
            w = _play(a, b)
            matches.append({"Home": f"{a['name']} ({a['group']}{a['pos']})",
                            "Away": f"{b['name']} ({b['group']}{b['pos']})",
                            "Advances": w["name"]})
            nxt.append(w)
        rounds.append((rname, pd.DataFrame(matches)))
        field = nxt
    return rounds, field[0]["name"]


def render_bracket(rounds, champion):
    cols = st.columns(len(rounds) + 1)
    for col, (rname, rdf) in zip(cols, rounds):
        with col:
            st.markdown(f"**{rname}**")
            for _, mt in rdf.iterrows():
                a, b, w = mt["Home"], mt["Away"], mt["Advances"]
                a_disp = f"<b>{a} ✅</b>" if a.split(" (")[0] == w else a
                b_disp = f"<b>{b} ✅</b>" if b.split(" (")[0] == w else b
                st.markdown(
                    "<div style='border:1px solid #555;border-radius:6px;padding:6px 8px;"
                    "margin-bottom:8px;font-size:0.8rem;line-height:1.4'>"
                    f"{a_disp}<br>{b_disp}</div>", unsafe_allow_html=True)
    with cols[-1]:
        st.markdown("**Champion**")
        st.markdown(
            "<div style='border:2px solid gold;border-radius:8px;padding:12px 10px;"
            "text-align:center;font-weight:bold;font-size:0.95rem'>"
            f"🏆<br>{champion}</div>", unsafe_allow_html=True)


# ----------------- Top scorers & assists (snapshot + live) -----------------
def build_scorers_assists(match_ids):
    goals, assists = {}, {}
    done = failed = 0
    names = st.session_state.get("_team_names", {})
    for mid in match_ids:
        try:
            players = match_player_stats(mid)
        except Exception:
            failed += 1
            continue
        done += 1
        for p in players:
            name = p.get("player_name")
            if not name:
                continue
            team = names.get(p.get("team_id"), "")
            g = (p.get("shooting") or {}).get("goals", 0) or 0
            a = (p.get("passing") or {}).get("assists", 0) or 0
            if g:
                row = goals.setdefault(name, {"Player": name, "Team": team, "Goals": 0})
                row["Goals"] += g
            if a:
                row = assists.setdefault(name, {"Player": name, "Team": team, "Assists": 0})
                row["Assists"] += a
    gdf = pd.DataFrame(list(goals.values()))
    adf = pd.DataFrame(list(assists.values()))
    if not gdf.empty:
        gdf = gdf.sort_values("Goals", ascending=False).head(10).reset_index(drop=True)
    if not adf.empty:
        adf = adf.sort_values("Assists", ascending=False).head(10).reset_index(drop=True)
    return gdf, adf, done, failed


def load_scorer_snapshot():
    g = a = None
    stamp = None
    try:
        g = pd.read_csv(SCORERS_CSV)
        stamp = time.strftime("%d %b %Y", time.localtime(os.path.getmtime(SCORERS_CSV)))
    except Exception:
        pass
    try:
        a = pd.read_csv(ASSISTS_CSV)
    except Exception:
        pass
    return g, a, stamp


# ===================== Match / team / player helpers =====================
def stat_val(overview, key, side):
    try:
        return overview[key]["all"][side]
    except Exception:
        return None


def overview_to_df(overview, home, away):
    labels = [("Possession %", "ball_possession"), ("Expected goals (xG)", "expected_goals"),
              ("Total shots", "total_shots"), ("Shots on target", "shots_on_target"),
              ("Big chances", "big_chances"), ("Corners", "corner_kicks"),
              ("Fouls", "fouls"), ("Yellow cards", "yellow_cards"),
              ("Red cards", "red_cards"), ("Passes", "passes"),
              ("Accurate passes", "accurate_passes")]
    return pd.DataFrame([{"Stat": lab, home: stat_val(overview, k, "home"),
                          away: stat_val(overview, k, "away")} for lab, k in labels])


def build_team_stats(finished):
    agg = {}
    done = failed = 0
    for m in finished:
        try:
            ov = wc_match_stats(m["id"]).get("overview", {})
        except Exception:
            failed += 1
            continue
        if not ov:
            continue
        done += 1
        for side, team in (("home", m["home_team"]["name"]), ("away", m["away_team"]["name"])):
            t = agg.setdefault(team, {"GP": 0, "poss": 0, "xg": 0.0, "shots": 0,
                                      "sot": 0, "corners": 0, "fouls": 0, "yc": 0, "big": 0})
            t["GP"] += 1
            for k, sk in [("poss", "ball_possession"), ("xg", "expected_goals"),
                          ("shots", "total_shots"), ("sot", "shots_on_target"),
                          ("corners", "corner_kicks"), ("fouls", "fouls"),
                          ("yc", "yellow_cards"), ("big", "big_chances")]:
                t[k] += stat_val(ov, sk, side) or 0
    rows = []
    for team, t in agg.items():
        gp = t["GP"] or 1
        rows.append({"Team": team, "GP": t["GP"], "Avg Poss %": round(t["poss"] / gp, 1),
                     "xG/game": round(t["xg"] / gp, 2), "Shots/game": round(t["shots"] / gp, 1),
                     "SoT/game": round(t["sot"] / gp, 1), "Big chances/game": round(t["big"] / gp, 1),
                     "Corners/game": round(t["corners"] / gp, 1), "Fouls/game": round(t["fouls"] / gp, 1),
                     "Yellows/game": round(t["yc"] / gp, 1)})
    return pd.DataFrame(rows).sort_values("xG/game", ascending=False).reset_index(drop=True), done, failed


def cat_df(d):
    return pd.DataFrame([{"Stat": k.replace("_", " ").title(), "Value": v} for k, v in d.items()])


def render_profile(player, stats, team_names):
    nat_team = team_names.get(stats.get("team_id"), player.get("nationality", ""))
    st.markdown(f"### {player['name']}  ·  {nat_team}")
    st.caption(f"Position {stats.get('position', '?')}  ·  "
               f"{player.get('nationality', '?')}  ·  Age {player.get('age', '?')}")
    a, b, c, d = st.columns(4)
    a.metric("Goals", stats.get("scoring", {}).get("goals", 0))
    b.metric("Assists", stats.get("scoring", {}).get("assists", 0))
    c.metric("Rating", stats.get("rating", "—"))
    d.metric("Minutes", stats.get("minutes_played", 0))
    for title, key in [("Scoring", "scoring"), ("Shooting", "shooting"), ("Passing", "passing"),
                       ("Defending", "defending"), ("Duels", "duels"), ("Discipline", "discipline")]:
        block = stats.get(key)
        if block:
            st.markdown(f"**{title}**")
            st.dataframe(cat_df(block), hide_index=True)


def ask_ai(prompt, model=AI_MODEL, temperature=1.0):
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    msg = client.messages.create(model=model, max_tokens=700, temperature=temperature,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text


# ===================== Landing page (hero + launcher) =====================
def _hero_background():
    """Return a CSS 'background' value: the photo if present, else solid dark."""
    for ext, mime in (("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")):
        path = os.path.join("images", f"hero.{ext}")
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return (f"linear-gradient(rgba(6,16,28,0.55), rgba(6,16,28,0.80)), "
                    f"url('data:image/{mime};base64,{b64}')")
    return "#0c1b2e"


LANDING_CSS = """
.block-container { padding-top: 0 !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }
.hero {
  position: relative;
  width: 100vw; margin-left: calc(-50vw + 50%);
  min-height: 100vh;
  background: __BG__;
  background-size: cover; background-position: center;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 44px 20px; gap: 16px;
}
.hero-kicker { font-size: 14px; letter-spacing: 0.18em; font-weight: 500; color: #ffffff; text-shadow: 0 2px 14px rgba(0,0,0,0.85); }
.hero-title { font-size: 56px; font-weight: 700; color: #ffffff !important; line-height: 1.05; margin: 0; text-shadow: 0 3px 22px rgba(0,0,0,0.9); }
.hero-sub { font-size: 18px; color: #f2f4f7; max-width: 580px; margin: 0; text-shadow: 0 2px 16px rgba(0,0,0,0.85); }
.hero-stats { display: flex; gap: 48px; margin-top: 16px; }
.hero-stats .num { font-size: 40px; font-weight: 700; color: __ACCENT__; line-height: 1; text-shadow: 0 2px 16px rgba(0,0,0,0.75); }
.hero-stats .lbl { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #eaedf2; margin-top: 5px; text-shadow: 0 1px 12px rgba(0,0,0,0.85); }
.hero-cue { margin-top: 26px; font-size: 13px; color: #ffffff; text-decoration: none; cursor: pointer; display: inline-block; text-shadow: 0 2px 14px rgba(0,0,0,0.85); }
.hero-cue:hover { opacity: 0.75; }
.hero-cue .chev { display: block; font-size: 28px; animation: bob 1.6s infinite; }
@keyframes bob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(8px); } }
.launch-title { text-align: center; font-size: 24px; font-weight: 600; margin: 44px 0 4px; padding-top: 10px; }
.launch-sub { text-align: center; color: #374151; font-size: 14px; font-weight: 500; margin: 0 0 22px; }
.launch-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 8px; }
.launch-card { display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 28px 14px; border: 1px solid rgba(0,0,0,0.10); border-radius: 14px;
  text-decoration: none; color: inherit; background: #ffffff; transition: transform .15s, border-color .15s; }
.launch-card:hover { transform: translateY(-3px); border-color: rgba(0,0,0,0.28); }
.launch-card .ic { font-size: 30px; line-height: 1; }
.launch-card .nm { font-size: 15px; font-weight: 600; color: #111827; }
.launch-card .ds { font-size: 12px; color: #4b5563; text-align: center; }
@media (max-width: 700px) { .launch-grid { grid-template-columns: 1fr; } .hero-title { font-size: 34px; } }
"""

HERO_HTML = """
<div class="hero">
  <div class="hero-kicker">CANADA · MEXICO · USA</div>
  <div class="hero-title">World Cup 2026 Analytics</div>
  <p class="hero-sub">Live tournament data, top scorers, team stats and a full knockout simulator — built in Python.</p>
  <div class="hero-stats">
    <div><div class="num">__MATCHES__</div><div class="lbl">matches</div></div>
    <div><div class="num">__GOALS__</div><div class="lbl">goals</div></div>
    <div><div class="num">__GROUPS__</div><div class="lbl">groups</div></div>
  </div>
  <a class="hero-cue" href="#explore">scroll to explore<span class="chev">⌄</span></a>
</div>
"""

MENU_HTML = """
<div class="launch-title" id="explore">Jump into the data</div>
<div class="launch-sub">Pick a section below to explore</div>
<div class="launch-grid">
  <a class="launch-card" href="?view=standings" target="_self"><span class="ic">📊</span><span class="nm">Group standings</span><span class="ds">Live tables for every group</span></a>
  <a class="launch-card" href="?view=scorers" target="_self"><span class="ic">⚽</span><span class="nm">Top scorers &amp; assists</span><span class="ds">Tournament top tens</span></a>
  <a class="launch-card" href="?view=bracket" target="_self"><span class="ic">🏆</span><span class="nm">Knockout bracket</span><span class="ds">Full simulated bracket</span></a>
  <a class="launch-card" href="?view=players" target="_self"><span class="ic">🔍</span><span class="nm">Player search</span><span class="ds">Profiles &amp; stats</span></a>
  <a class="launch-card" href="?view=stats" target="_self"><span class="ic">📈</span><span class="nm">Team stats</span><span class="ds">Per-game performance</span></a>
  <a class="launch-card" href="?view=ai" target="_self"><span class="ic">🤖</span><span class="nm">AI analysis</span><span class="ds">Auto tournament summary</span></a>
</div>
"""


def render_home(n_matches, n_goals, n_groups):
    css = LANDING_CSS.replace("__BG__", _hero_background()).replace("__ACCENT__", ACCENT)
    hero = (HERO_HTML.replace("__MATCHES__", str(n_matches))
            .replace("__GOALS__", str(n_goals))
            .replace("__GROUPS__", str(n_groups)))
    st.markdown(f"<style>{css}</style>{hero}{MENU_HTML}", unsafe_allow_html=True)


def render_menu_page():
    css = LANDING_CSS.replace("__BG__", _hero_background()).replace("__ACCENT__", ACCENT)
    home_link = ('<a href="?view=home" target="_self" style="display:inline-block;'
                 'color:#4b5563;text-decoration:none;font-size:15px;font-weight:500;'
                 'margin-bottom:4px;">↑ Back to the front page</a>')
    st.markdown(f"<style>{css}</style>{home_link}{MENU_HTML}", unsafe_allow_html=True)


# ============================== APP BODY ==============================
try:
    finished = wc_matches("finished")
    upcoming = wc_matches("scheduled")
    wc_ok = True
except Exception as e:
    finished, upcoming, wc_ok = [], [], False
    wc_err = e

groups = build_group_standings(finished) if wc_ok else {}
team_names = build_team_name_map(finished, upcoming) if wc_ok else {}
st.session_state["_team_names"] = team_names
n_goals = sum((m["score"]["home"] or 0) + (m["score"]["away"] or 0) for m in finished)

gnames = sorted(groups.keys())

BASE_CSS = """
.block-container { padding-top: 1.5rem !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }
.backlink { display: inline-block; color: #4b5563; text-decoration: none; font-size: 15px;
  font-weight: 500; margin-bottom: 6px; }
.backlink:hover { color: #111827; }
"""


# Country name -> ISO code for flag images (flagcdn.com). Covers likely 2026 teams.
NAME_TO_ISO2 = {
    "Argentina": "ar", "Australia": "au", "Austria": "at", "Belgium": "be", "Bolivia": "bo",
    "Brazil": "br", "Cameroon": "cm", "Canada": "ca", "Cape Verde": "cv", "Chile": "cl",
    "Colombia": "co", "Costa Rica": "cr", "Croatia": "hr", "Curacao": "cw", "Czechia": "cz",
    "Czech Republic": "cz", "Denmark": "dk", "DR Congo": "cd", "Ecuador": "ec", "Egypt": "eg",
    "El Salvador": "sv", "England": "gb-eng", "France": "fr", "Germany": "de", "Ghana": "gh",
    "Greece": "gr", "Guatemala": "gt", "Haiti": "ht", "Honduras": "hn", "Hungary": "hu",
    "Iceland": "is", "Iran": "ir", "Iraq": "iq", "Ireland": "ie", "Republic of Ireland": "ie",
    "Italy": "it", "Ivory Coast": "ci", "Jamaica": "jm", "Japan": "jp", "Jordan": "jo",
    "Kazakhstan": "kz", "Korea Republic": "kr", "South Korea": "kr", "Mali": "ml", "Mexico": "mx",
    "Morocco": "ma", "Netherlands": "nl", "New Zealand": "nz", "Nigeria": "ng", "North Macedonia": "mk",
    "Northern Ireland": "gb-nir", "Norway": "no", "Oman": "om", "Panama": "pa", "Paraguay": "py",
    "Peru": "pe", "Poland": "pl", "Portugal": "pt", "Qatar": "qa", "Romania": "ro", "Russia": "ru",
    "Saudi Arabia": "sa", "Scotland": "gb-sct", "Senegal": "sn", "Serbia": "rs", "Slovakia": "sk",
    "Slovenia": "si", "South Africa": "za", "Spain": "es", "Sweden": "se", "Switzerland": "ch",
    "Trinidad and Tobago": "tt", "Tunisia": "tn", "Turkey": "tr", "Ukraine": "ua",
    "United States": "us", "USA": "us", "Uruguay": "uy", "Uzbekistan": "uz", "Venezuela": "ve",
    "Wales": "gb-wls", "Algeria": "dz", "Bahrain": "bh", "China": "cn", "India": "in",
    "Indonesia": "id", "Thailand": "th", "Vietnam": "vn", "United Arab Emirates": "ae",
}


def _flag_img(team):
    iso = NAME_TO_ISO2.get(team)
    if not iso:
        return ""
    return (f'<img src="https://flagcdn.com/w40/{iso}.png" alt="" loading="lazy" '
            'style="width:26px;height:auto;border-radius:2px;margin-right:8px;vertical-align:middle;">')


# ----------------------------- Section pages -----------------------------
def section_standings():
    st.caption("Live tables built from every finished match.")
    for i in range(0, len(gnames), 2):
        cols = st.columns(2)
        for col, g in zip(cols, gnames[i:i + 2]):
            with col:
                st.markdown(f"**Group {g}**")
                st.dataframe(groups[g], hide_index=True)


def section_scorers():
    gsnap, asnap, stamp = load_scorer_snapshot()
    gdf = st.session_state.get("scorers_live", gsnap)
    adf = st.session_state.get("assisters_live", asnap)
    if "scorers_live" in st.session_state:
        st.caption("🟢 Refreshed live from match data just now.")
    elif stamp:
        st.caption(f"📁 Snapshot built {stamp}. Press refresh for the very latest.")
    else:
        st.caption("No snapshot found yet — press refresh to build it from live match data.")
    gcol, acol = st.columns(2)
    with gcol:
        st.markdown("**Top scorers**")
        if gdf is None or gdf.empty:
            st.write("No goal data available.")
        else:
            st.dataframe(gdf, hide_index=True)
    with acol:
        st.markdown("**Top assists**")
        if adf is None or adf.empty:
            st.write("No assist data available.")
        else:
            st.dataframe(adf, hide_index=True)
    if st.button("🔄 Refresh from live results"):
        with st.spinner("Reading every finished match..."):
            lg, la, done, failed = build_scorers_assists([m["id"] for m in finished])
            st.session_state.scorers_live = lg
            st.session_state.assisters_live = la
        if failed:
            st.warning(f"Built from {done} matches; {failed} hit the rate limit — try again in a minute.")
        st.rerun()


def section_bracket():
    st.subheader("Group winner predictions")
    st.caption("From the current standings — winner and runner-up of each group.")
    if groups:
        st.dataframe(group_predictions(groups), hide_index=True)
    else:
        st.write("No group results yet.")
    st.subheader("Simulated knockout bracket")
    st.caption("Deterministic simulation: the 32 qualifiers (top 2 of each group + 8 best third-placed "
               "teams) are seeded by points, goal difference and goals scored, then every tie is decided "
               "by the stronger record. No AI, no randomness.")
    qualified = qualified_from_groups(groups)
    rounds, champion = simulate_bracket(qualified)
    if not rounds:
        st.info("Not enough completed group games yet to build the bracket. It will appear automatically "
                "once more results are in.")
    else:
        st.write(f"Seeding **{len(rounds[0][1]) * 2}** qualified teams into the bracket.")
        render_bracket(rounds, champion)
        st.success(f"🏆 Simulated champion: **{champion}**")
        st.caption("⚠️ A mechanical simulation from current form — not a real prediction.")


def section_players():
    q = st.text_input("Type a player's name and press Search")
    if st.button("Search player"):
        try:
            st.session_state.player_results = search_player(q) if q.strip() else []
        except Exception as e:
            st.session_state.player_results = []
            if "rate limit" in str(e).lower() or "429" in str(e):
                st.warning("⏳ Hit TheStatsAPI's per-minute limit — wait ~60 seconds and try again.")
            else:
                st.warning(f"Search failed: {e}")
    results = st.session_state.get("player_results", [])
    if results:
        opts = {f"{p['name']} — {p.get('nationality', '?')} ({p.get('position', '?')})": p
                for p in results}
        pick = st.selectbox("Pick the player:", list(opts.keys()))
        p = opts[pick]
        try:
            s = player_wc_stats(p["id"])
            if s:
                render_profile(p, s, team_names)
            else:
                st.info(f"{p['name']} has no recorded stats in the 2026 World Cup.")
        except Exception as e:
            st.warning(f"Couldn't load stats: {e}")


def section_stats():
    st.subheader("Teams")
    teams = sorted(set(team_names.values()))
    if teams:
        cards = "".join(
            '<div style="display:flex;align-items:center;gap:6px;padding:9px 12px;'
            'border:1px solid rgba(0,0,0,0.12);border-radius:10px;background:#ffffff;">'
            f'{_flag_img(t)}<span style="font-size:14px;font-weight:500;color:#111827;">{t}</span></div>'
            for t in teams)
        st.markdown(
            '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));'
            f'gap:10px;margin-bottom:14px;">{cards}</div>', unsafe_allow_html=True)
    else:
        st.write("No teams loaded yet.")

    st.divider()
    st.subheader("Per-game team stats")
    if "wc_team_stats" not in st.session_state:
        st.session_state.wc_team_stats = None
    if st.button("Build team stats from every finished match"):
        with st.spinner("Aggregating every match's stat sheet..."):
            ts, done, failed = build_team_stats(finished)
            st.session_state.wc_team_stats = ts
            st.session_state.wc_team_msg = f"Built from {done} matches." + (
                f" {failed} hit the rate limit — click again in a minute." if failed else "")
    if st.session_state.wc_team_stats is not None:
        st.caption(st.session_state.get("wc_team_msg", ""))
        st.dataframe(st.session_state.wc_team_stats, hide_index=True)
    st.subheader("Match stats explorer")
    labels = {f"{m['home_team']['name']} {m['score']['home']}-{m['score']['away']} "
              f"{m['away_team']['name']} ({m['utc_date'][:10]})": m for m in finished}
    if labels:
        choice = st.selectbox("Pick a finished match:", list(labels.keys()))
        m = labels[choice]
        try:
            ov = wc_match_stats(m["id"]).get("overview", {})
            if ov:
                st.dataframe(overview_to_df(ov, m["home_team"]["name"],
                                            m["away_team"]["name"]), hide_index=True)
            else:
                st.write("No detailed stats for this match yet.")
        except Exception as e:
            st.warning(f"Couldn't load that match's stats: {e}")


def _stats_context():
    """Bundle every stat we have into one text block for the AI to reason over."""
    parts = []
    for g in gnames:
        parts.append(f"Group {g} standings:\n" + groups[g].to_string(index=False))
    gsnap, asnap, _ = load_scorer_snapshot()
    if gsnap is not None and not gsnap.empty:
        parts.append("Top scorers:\n" + gsnap.to_string(index=False))
    if asnap is not None and not asnap.empty:
        parts.append("Top assists:\n" + asnap.to_string(index=False))
    if st.session_state.get("wc_team_stats") is not None:
        parts.append("Per-game team stats:\n" + st.session_state.wc_team_stats.to_string(index=False))
    return "\n\n".join(parts)


def section_ai():
    groups_text = ""
    for g in gnames:
        groups_text += f"\nGroup {g} (only these teams): " + \
            ", ".join(groups[g]["Team"].tolist()) + "\n" + groups[g].to_string(index=False) + "\n"
    team_stats_text = ""
    if st.session_state.get("wc_team_stats") is not None:
        team_stats_text = "\n\nPer-game team stats:\n" + st.session_state.wc_team_stats.to_string(index=False)

    # ---- 1. Auto tournament summary ----
    st.subheader("Tournament summary")
    if "wc_analysis" not in st.session_state:
        st.session_state.wc_analysis = ""
    if st.button("Analyse the tournament"):
        try:
            with st.spinner("Analysing..."):
                st.session_state.wc_analysis = ask_ai(
                    "You are an expert analyst covering the 2026 World Cup group stage (in progress). "
                    "Standings:\n" + groups_text + team_stats_text +
                    "\n\nWrite a punchy 4-6 sentence analysis. Use the stats where useful. "
                    "Plain English, no bullet points.")
        except Exception as e:
            st.session_state.wc_analysis = f"Sorry — couldn't analyse. ({e})"
    if st.session_state.wc_analysis:
        st.info(st.session_state.wc_analysis)

    # ---- 2. Ask-the-stats chatbot ----
    st.divider()
    st.subheader("💬 Ask the stats chatbot")
    st.caption("Ask anything about the tournament data — standings, scorers, team stats. It answers "
               "only from the live data, and will tell you if a stat isn't tracked.")
    uq = st.text_input("Your question",
                       placeholder="e.g. Which group has scored the most goals?")
    if st.button("Ask"):
        if uq.strip():
            with st.spinner("Thinking..."):
                prompt = ("You are a World Cup 2026 stats assistant. Answer the user's question using "
                          "ONLY the data below. If the answer isn't in the data (for example a stat "
                          "like tackles that isn't tracked here), say you don't have that stat rather "
                          "than guessing. Be concise and specific.\n\nDATA:\n" + _stats_context() +
                          "\n\nQUESTION: " + uq)
                try:
                    ans = ask_ai(prompt, temperature=0.2)
                except Exception as e:
                    ans = f"Sorry — couldn't answer right now. ({e})"
            st.session_state.chat_q = uq
            st.session_state.chat_answer = ans
    if st.session_state.get("chat_answer"):
        st.markdown(f"**You asked:** {st.session_state.get('chat_q', '')}")
        st.info(st.session_state.chat_answer)

    # ---- 3. AI predicted knockout bracket with scores ----
    st.divider()
    st.subheader("🔮 AI predicted knockout bracket")
    st.caption("The AI's own prediction of every knockout tie and scoreline. (The number-based "
               "simulation lives in the Knockout bracket section.)")
    if st.button("Predict the bracket with scores"):
        qualified = qualified_from_groups(groups)
        rounds, _ = simulate_bracket(qualified)
        if not rounds:
            st.session_state.ai_bracket = ("Not enough completed group games yet to seed a bracket — "
                                           "check back once more results are in.")
        else:
            r32 = rounds[0][1]
            fixtures = "\n".join(f"{r['Home']} vs {r['Away']}" for _, r in r32.iterrows())
            prompt = ("You are predicting the 2026 World Cup knockout stage. Below are the first-round "
                      "fixtures, seeded from current standings:\n" + fixtures +
                      "\n\nPredict the FULL knockout bracket round by round: Round of 32, Round of 16, "
                      "Quarter-finals, Semi-finals, then the Final. For every match give a predicted "
                      "scoreline and put the winner in **bold**, and carry the winners forward "
                      "consistently between rounds. Use ONLY the teams above. Format as markdown with "
                      "a heading per round and one line per match like '**Brazil** 2-1 Mexico'. End "
                      "with a line: 'Predicted champion: <team>'.")
            with st.spinner("Predicting the bracket..."):
                try:
                    st.session_state.ai_bracket = ask_ai(prompt, model=PREDICT_MODEL, temperature=0.4)
                except Exception as e:
                    st.session_state.ai_bracket = f"Sorry — couldn't predict. ({e})"
    if st.session_state.get("ai_bracket"):
        st.markdown(st.session_state.ai_bracket)
        st.caption("⚠️ AI-generated predictions — informed speculation, not betting advice.")


SECTIONS = {
    "standings": ("📊 Group standings", section_standings),
    "scorers": ("⚽ Top 10 scorers & assists", section_scorers),
    "bracket": ("🏆 Knockout stage", section_bracket),
    "players": ("🔍 Player search", section_players),
    "stats": ("📈 Team stats & match explorer", section_stats),
    "ai": ("🤖 AI tournament analysis", section_ai),
}

view = st.query_params.get("view", "home")

if view == "menu":
    # The menu page: just the six boxes (the "second page")
    render_menu_page()
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
elif view in SECTIONS:
    # A section page: back link (to the menu) + just this section's content
    st.markdown(f"<style>{BASE_CSS}</style>", unsafe_allow_html=True)
    st.markdown('<a class="backlink" href="?view=menu" target="_self">← Back to menu</a>',
                unsafe_allow_html=True)
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
    else:
        title, render_fn = SECTIONS[view]
        st.header(title)
        render_fn()
else:
    # Home: full-screen hero + the menu of boxes
    render_home(len(finished), n_goals, len(groups))
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
