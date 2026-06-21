import streamlit as st
import pandas as pd
import requests
import anthropic
import time
import os
import base64
import urllib.parse

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


def _banner_bg(slug):
    """Background for a section banner: images/banners/<slug>.<ext> if present, else dark."""
    for ext, mime in (("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")):
        path = os.path.join("images", "banners", f"{slug}.{ext}")
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return (f"linear-gradient(rgba(6,16,28,0.45), rgba(6,16,28,0.68)), "
                    f"url('data:image/{mime};base64,{b64}')")
    return "#0c1b2e"


def render_banner(title, slug):
    """Centered section title over a slim photo banner (design option 1)."""
    bg = _banner_bg(slug)
    st.markdown(
        f'<div style="background:{bg};background-size:cover;background-position:center;'
        'border-radius:12px;min-height:175px;display:flex;align-items:center;justify-content:center;'
        'text-align:center;padding:20px;margin:2px 0 12px;">'
        '<div style="font-size:34px;font-weight:700;color:#ffffff;'
        f'text-shadow:0 2px 18px rgba(0,0,0,0.9);">{title}</div></div>',
        unsafe_allow_html=True)


LANDING_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"], button, input, select, textarea, h1, h2, h3, h4, h5, h6, p, span, label { font-family: 'Oswald', sans-serif; }
.block-container { padding-top: 0 !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }
[data-testid="stHeaderActionElements"] { display: none; }
h1, h2, h3, h4, h5, h6 { text-decoration: none; border-bottom: none; }
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { color: inherit; text-decoration: none; }
.stApp { background-color: #0e1117 !important; }
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
.launch-title { text-align: center; font-size: 26px; font-weight: 600; margin: 40px 0 4px; padding-top: 10px; color: #ffffff; }
.launch-sub { text-align: center; color: rgba(255,255,255,0.7); font-size: 14px; font-weight: 500; margin: 0 0 22px; }
.launch-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 8px;
  width: 100vw; margin-left: calc(-50vw + 50%); padding: 0 32px; box-sizing: border-box; }
.mcard { position: relative; overflow: hidden; border-radius: 14px; height: 33vh; min-height: 210px;
  display: flex; align-items: flex-end; text-decoration: none;
  background-size: cover; background-position: center; transition: transform .15s; }
.mcard:hover { transform: translateY(-3px); }
.mcard-bar { width: 100%; background: rgba(10,16,28,0.55); backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px); padding: 11px 14px; text-align: center;
  font-size: 16px; font-weight: 600; color: #ffffff; text-shadow: 0 1px 6px rgba(0,0,0,0.7); }
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

MENU_CARDS = [
    ("standings", "Group standings"),
    ("scorers", "Top scorers &amp; assists"),
    ("bracket", "Knockout bracket"),
    ("players", "Player search"),
    ("stats", "Team stats"),
    ("ai", "AI analysis"),
]


def render_menu_cards():
    """The six menu boxes as image-backed cards with a frosted title bar."""
    cards = ""
    for slug, label in MENU_CARDS:
        bg = _banner_bg(slug)
        cards += (f'<a class="mcard" href="?view={slug}" target="_self" '
                  f'style="background:{bg};background-size:cover;background-position:center;">'
                  f'<div class="mcard-bar">{label}</div></a>')
    return ('<div class="launch-title" id="explore">Jump into the data</div>'
            '<div class="launch-sub">Pick a section below to explore</div>'
            f'<div class="launch-grid">{cards}</div>')


def render_home(n_matches, n_goals, n_groups):
    css = LANDING_CSS.replace("__BG__", _hero_background()).replace("__ACCENT__", ACCENT)
    hero = (HERO_HTML.replace("__MATCHES__", str(n_matches))
            .replace("__GOALS__", str(n_goals))
            .replace("__GROUPS__", str(n_groups)))
    st.markdown(f"<style>{css}</style>{hero}{render_menu_cards()}", unsafe_allow_html=True)


def render_menu_page():
    css = LANDING_CSS.replace("__BG__", _hero_background()).replace("__ACCENT__", ACCENT)
    home_link = ('<a href="?view=home" target="_self" style="display:inline-block;'
                 'color:rgba(255,255,255,0.75);text-decoration:none;font-size:15px;font-weight:500;'
                 'margin-bottom:4px;">↑ Back to the front page</a>')
    st.markdown(f"<style>{css}</style>{home_link}{render_menu_cards()}", unsafe_allow_html=True)


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
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"], button, input, select, textarea, h1, h2, h3, h4, h5, h6, p, span, label { font-family: 'Oswald', sans-serif; }
.block-container { padding-top: 1.5rem !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }
[data-testid="stHeaderActionElements"] { display: none; }
h1, h2, h3, h4, h5, h6 { text-decoration: none; border-bottom: none; }
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { color: inherit; text-decoration: none; }
.backlink { display: inline-block; color: #4b5563; text-decoration: none; font-size: 15px;
  font-weight: 500; margin-bottom: 6px; }
.backlink:hover { color: #111827; }
.team-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(165px, 1fr)); gap: 14px;
  width: 100vw; margin-left: calc(-50vw + 50%); padding: 0 32px; box-sizing: border-box; }
.team-card { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 16px 8px;
  background: transparent; border: none; border-radius: 12px;
  text-decoration: none; color: #ffffff; transition: transform .15s, background .15s; }
.team-card:hover { transform: translateY(-3px); background: rgba(255,255,255,0.07); }
.team-name { font-size: 15px; font-weight: 600; text-align: center; color: #ffffff;
  text-shadow: 0 1px 6px rgba(0,0,0,0.6); }
"""


# Country name (lowercased) -> ISO code for flag images (flagcdn.com).
NAME_TO_ISO2 = {
    "afghanistan": "af", "albania": "al", "algeria": "dz", "angola": "ao", "argentina": "ar",
    "armenia": "am", "australia": "au", "austria": "at", "azerbaijan": "az", "bahrain": "bh",
    "bangladesh": "bd", "belarus": "by", "belgium": "be", "benin": "bj", "bolivia": "bo",
    "bosnia and herzegovina": "ba", "botswana": "bw", "brazil": "br", "bulgaria": "bg",
    "burkina faso": "bf", "cameroon": "cm", "canada": "ca", "cape verde": "cv", "cabo verde": "cv",
    "chile": "cl", "china": "cn", "china pr": "cn", "colombia": "co", "comoros": "km", "congo": "cg",
    "dr congo": "cd", "congo dr": "cd", "costa rica": "cr", "croatia": "hr", "cuba": "cu",
    "curacao": "cw", "cyprus": "cy", "czechia": "cz", "czech republic": "cz", "denmark": "dk",
    "ecuador": "ec", "egypt": "eg", "el salvador": "sv", "england": "gb-eng",
    "equatorial guinea": "gq", "estonia": "ee", "finland": "fi", "france": "fr", "gabon": "ga",
    "gambia": "gm", "georgia": "ge", "germany": "de", "ghana": "gh", "greece": "gr",
    "guatemala": "gt", "guinea": "gn", "haiti": "ht", "honduras": "hn", "hungary": "hu",
    "iceland": "is", "india": "in", "indonesia": "id", "iran": "ir", "iraq": "iq", "ireland": "ie",
    "republic of ireland": "ie", "israel": "il", "italy": "it", "ivory coast": "ci",
    "cote d'ivoire": "ci", "côte d'ivoire": "ci", "jamaica": "jm", "japan": "jp", "jordan": "jo",
    "kazakhstan": "kz", "kenya": "ke", "kosovo": "xk", "kuwait": "kw", "latvia": "lv",
    "lebanon": "lb", "libya": "ly", "lithuania": "lt", "luxembourg": "lu", "madagascar": "mg",
    "malaysia": "my", "mali": "ml", "malta": "mt", "mauritania": "mr", "mexico": "mx",
    "moldova": "md", "montenegro": "me", "morocco": "ma", "mozambique": "mz", "namibia": "na",
    "netherlands": "nl", "new zealand": "nz", "nigeria": "ng", "north macedonia": "mk",
    "northern ireland": "gb-nir", "north korea": "kp", "korea dpr": "kp", "norway": "no",
    "oman": "om", "pakistan": "pk", "panama": "pa", "paraguay": "py", "peru": "pe",
    "philippines": "ph", "poland": "pl", "portugal": "pt", "qatar": "qa", "romania": "ro",
    "russia": "ru", "saudi arabia": "sa", "scotland": "gb-sct", "senegal": "sn", "serbia": "rs",
    "sierra leone": "sl", "singapore": "sg", "slovakia": "sk", "slovenia": "si",
    "south africa": "za", "south korea": "kr", "korea republic": "kr", "spain": "es",
    "sudan": "sd", "sweden": "se", "switzerland": "ch", "syria": "sy", "tanzania": "tz",
    "thailand": "th", "togo": "tg", "trinidad and tobago": "tt", "tunisia": "tn", "turkey": "tr",
    "türkiye": "tr", "turkiye": "tr", "uganda": "ug", "ukraine": "ua",
    "united arab emirates": "ae", "united states": "us", "usa": "us", "uruguay": "uy",
    "uzbekistan": "uz", "venezuela": "ve", "vietnam": "vn", "wales": "gb-wls", "zambia": "zm",
    "zimbabwe": "zw",
}


def _flag_img(team, w=26):
    iso = NAME_TO_ISO2.get((team or "").strip().lower())
    if not iso:
        return ""
    src = "w80" if w > 40 else "w40"
    return (f'<img src="https://flagcdn.com/{src}/{iso}.png" alt="" loading="lazy" '
            f'style="width:{w}px;height:auto;border-radius:3px;vertical-align:middle;">')


def _pitch_background_css():
    """Dark page with faint football-pitch markings, for the team grid."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1000 600' "
           "preserveAspectRatio='xMidYMid slice'>"
           "<g fill='none' stroke='white' stroke-opacity='0.09' stroke-width='3'>"
           "<rect x='20' y='20' width='960' height='560'/>"
           "<line x1='500' y1='20' x2='500' y2='580'/>"
           "<circle cx='500' cy='300' r='70'/>"
           "<rect x='20' y='180' width='120' height='240'/>"
           "<rect x='860' y='180' width='120' height='240'/>"
           "<rect x='20' y='250' width='45' height='100'/>"
           "<rect x='935' y='250' width='45' height='100'/></g>"
           "<circle cx='500' cy='300' r='4' fill='white' fill-opacity='0.09'/></svg>")
    uri = "data:image/svg+xml," + urllib.parse.quote(svg)
    return ("<style>.stApp{background-color:#0d1420 !important;"
            f"background-image:url(\"{uri}\");"
            "background-size:cover;background-position:center;background-attachment:fixed;}"
            ".backlink{color:rgba(255,255,255,0.78) !important;}"
            ".backlink:hover{color:#ffffff !important;}</style>")


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
    st.markdown(_pitch_background_css(), unsafe_allow_html=True)
    st.markdown(
        '<div style="margin:8px 0 4px;">'
        '<div style="font-size:38px;font-weight:700;color:#ffffff;letter-spacing:0.05em;'
        'text-transform:uppercase;line-height:1;">Team stats</div>'
        '<div style="width:66px;height:3px;background:#e8b84b;border-radius:2px;margin-top:12px;"></div>'
        '</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:rgba(255,255,255,0.7);font-size:14px;margin:12px 0 16px;">'
                'Pick a country to see its stats.</div>', unsafe_allow_html=True)
    real = build_team_name_map(finished)
    items = sorted(((tid, name) for tid, name in real.items()
                    if NAME_TO_ISO2.get((name or "").strip().lower())),
                   key=lambda kv: kv[1])
    if not items:
        st.write("No teams loaded yet.")
        return
    cards = "".join(
        f'<a class="team-card" href="?view=team&team={tid}" target="_self">'
        f'{_flag_img(name, 56)}<span class="team-name">{name}</span></a>'
        for tid, name in items)
    st.markdown(f'<div class="team-grid">{cards}</div>', unsafe_allow_html=True)


def _ordinal(n):
    return f'{n}{"th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'


def _tile(value, label):
    return (f'<div class="tp-tile"><div class="tp-val">{value}</div>'
            f'<div class="tp-lbl">{label}</div></div>')


TEAM_CSS = """
<style>
.tp-header { display:flex; align-items:center; gap:14px; margin:6px 0 10px; }
.tp-header img { width:62px; height:auto; border-radius:4px; }
.tp-name { font-size:34px; font-weight:700; color:#fff; text-transform:uppercase; letter-spacing:0.04em; line-height:1; }
.tp-meta { font-size:13px; color:rgba(255,255,255,0.65); margin-top:5px; }
.tp-nav { position:sticky; top:0; z-index:5; display:flex; flex-wrap:wrap; gap:8px; padding:10px 0 14px; margin-bottom:6px; background:#0d1420; }
.tp-nav a { font-size:13px; font-weight:600; color:rgba(255,255,255,0.82); text-decoration:none; padding:6px 14px; border:1px solid rgba(255,255,255,0.18); border-radius:20px; transition:all .15s; }
.tp-nav a:hover { background:#e8b84b; color:#0d1420; border-color:#e8b84b; }
.tp-section { margin-bottom:26px; scroll-margin-top:64px; }
.tp-h { display:flex; align-items:center; gap:9px; font-size:17px; font-weight:600; color:#fff; margin-bottom:12px; text-transform:uppercase; letter-spacing:0.03em; }
.tp-h::before { content:""; width:4px; height:18px; background:#e8b84b; border-radius:2px; }
.tp-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(135px,1fr)); gap:12px; }
.tp-tile { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.09); border-radius:10px; padding:14px 10px; text-align:center; }
.tp-val { font-size:24px; font-weight:700; color:#fff; line-height:1.1; }
.tp-lbl { font-size:11px; color:rgba(255,255,255,0.6); text-transform:uppercase; letter-spacing:0.05em; margin-top:5px; }
.tp-pval { font-size:16px; font-weight:600; color:#fff; margin-top:6px; }
.tp-res { display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.05); border-radius:8px; margin-bottom:8px; color:#fff; font-size:14px; }
.tp-w { color:#37b86b; font-weight:700; } .tp-d { color:#e8b84b; font-weight:700; } .tp-l { color:#e24b4a; font-weight:700; }
</style>
"""


def team_page():
    tid = st.query_params.get("team")
    name = team_names.get(tid, "Team")
    st.markdown(_pitch_background_css(), unsafe_allow_html=True)

    keys = ["ball_possession", "expected_goals", "total_shots", "shots_on_target",
            "big_chances", "corner_kicks", "fouls", "yellow_cards", "red_cards",
            "passes", "accurate_passes"]
    agg = {k: 0 for k in keys}
    gp = gf = ga = w = d = l = 0
    results = []
    for m in finished:
        h, a = m["home_team"], m["away_team"]
        if tid not in (h.get("id"), a.get("id")):
            continue
        hs, as_ = m["score"]["home"], m["score"]["away"]
        if hs is None or as_ is None:
            continue
        is_home = h.get("id") == tid
        side = "home" if is_home else "away"
        my, opp = (hs, as_) if is_home else (as_, hs)
        gf += my; ga += opp; gp += 1
        res = "W" if my > opp else ("D" if my == opp else "L")
        if res == "W":
            w += 1
        elif res == "D":
            d += 1
        else:
            l += 1
        results.append((f"{h['name']} {hs}-{as_} {a['name']}", res))
        try:
            ov = wc_match_stats(m["id"]).get("overview", {})
        except Exception:
            ov = {}
        for k in keys:
            agg[k] += stat_val(ov, k, side) or 0

    g = max(gp, 1)
    pass_acc = round(100 * agg["accurate_passes"] / agg["passes"], 1) if agg["passes"] else 0
    grp = pos = None
    for gl in sorted(groups):
        teams_list = groups[gl]["Team"].tolist()
        if name in teams_list:
            grp = gl
            pos = teams_list.index(name) + 1
            break
    meta = f"Group {grp} · {_ordinal(pos)}" if grp else "Group stage"

    gsnap, asnap, _ = load_scorer_snapshot()
    top_sc = top_as = "—"
    if gsnap is not None and not gsnap.empty:
        ts = gsnap[gsnap["Team"] == name]
        if not ts.empty:
            top_sc = f'{ts.iloc[0]["Player"]} ({int(ts.iloc[0]["Goals"])})'
    if asnap is not None and not asnap.empty:
        ta = asnap[asnap["Team"] == name]
        if not ta.empty:
            top_as = f'{ta.iloc[0]["Player"]} ({int(ta.iloc[0]["Assists"])})'

    header = (f'<div class="tp-header">{_flag_img(name, 62)}'
              f'<div><div class="tp-name">{name}</div><div class="tp-meta">{meta}</div></div></div>')
    nav = ('<div class="tp-nav">'
           '<a href="#summary">Summary</a><a href="#attack">Attack</a>'
           '<a href="#possession">Possession</a><a href="#defence">Defence</a>'
           '<a href="#players">Players</a><a href="#results">Results</a></div>')
    summary = ('<div class="tp-section" id="summary"><div class="tp-h">Summary</div><div class="tp-grid">'
               + _tile(gp, "Played") + _tile(f"{w}-{d}-{l}", "W-D-L")
               + _tile(gf, "Goals for") + _tile(ga, "Goals against")
               + _tile(gf - ga, "Goal diff") + _tile(w * 3 + d, "Points") + '</div></div>')
    attack = ('<div class="tp-section" id="attack"><div class="tp-h">Attack</div><div class="tp-grid">'
              + _tile(gf, "Goals") + _tile(round(agg["expected_goals"], 1), "xG")
              + _tile(int(agg["total_shots"]), "Shots") + _tile(int(agg["shots_on_target"]), "On target")
              + _tile(int(agg["big_chances"]), "Big chances") + _tile(int(agg["corner_kicks"]), "Corners")
              + '</div></div>')
    possession = ('<div class="tp-section" id="possession"><div class="tp-h">Possession &amp; passing</div>'
                  '<div class="tp-grid">'
                  + _tile(f'{round(agg["ball_possession"] / g, 1)}%', "Avg possession")
                  + _tile(f"{pass_acc}%", "Pass accuracy")
                  + _tile(int(agg["passes"]), "Passes")
                  + _tile(int(agg["accurate_passes"]), "Accurate") + '</div></div>')
    defence = ('<div class="tp-section" id="defence"><div class="tp-h">Defence &amp; discipline</div>'
               '<div class="tp-grid">'
               + _tile(ga, "Conceded") + _tile(int(agg["fouls"]), "Fouls")
               + _tile(int(agg["yellow_cards"]), "Yellow cards") + _tile(int(agg["red_cards"]), "Red cards")
               + '</div></div>')
    players = ('<div class="tp-section" id="players"><div class="tp-h">Key players</div><div class="tp-grid">'
               f'<div class="tp-tile"><div class="tp-lbl">Top scorer</div><div class="tp-pval">{top_sc}</div></div>'
               f'<div class="tp-tile"><div class="tp-lbl">Top assister</div><div class="tp-pval">{top_as}</div></div>'
               '</div></div>')
    res_rows = "".join(
        f'<div class="tp-res"><span>{mm}</span><span class="tp-{r.lower()}">{r}</span></div>'
        for mm, r in results) or '<div class="tp-res">No finished matches yet</div>'
    resultsec = f'<div class="tp-section" id="results"><div class="tp-h">Results</div>{res_rows}</div>'

    st.markdown(TEAM_CSS + header + nav + summary + attack + possession + defence + players + resultsec,
                unsafe_allow_html=True)


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
    "standings": ("Group standings", section_standings),
    "scorers": ("Top 10 scorers & assists", section_scorers),
    "bracket": ("Knockout stage", section_bracket),
    "players": ("Player search", section_players),
    "stats": ("Team stats", section_stats),
    "ai": ("AI tournament analysis", section_ai),
}

view = st.query_params.get("view", "home")

if view == "menu":
    # The menu page: just the six boxes (the "second page")
    render_menu_page()
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
elif view == "team":
    # An individual team's page, reached from the Team stats flag grid
    st.markdown(f"<style>{BASE_CSS}</style>", unsafe_allow_html=True)
    st.markdown('<a class="backlink" href="?view=stats" target="_self">← Back to teams</a>',
                unsafe_allow_html=True)
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
    else:
        team_page()
elif view in SECTIONS:
    # A section page: back link (to the menu) + just this section's content
    st.markdown(f"<style>{BASE_CSS}</style>", unsafe_allow_html=True)
    st.markdown('<a class="backlink" href="?view=menu" target="_self">← Back to menu</a>',
                unsafe_allow_html=True)
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
    else:
        title, render_fn = SECTIONS[view]
        if view != "stats":
            render_banner(title, view)
        render_fn()
else:
    # Home: full-screen hero + the menu of boxes
    render_home(len(finished), n_goals, len(groups))
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
