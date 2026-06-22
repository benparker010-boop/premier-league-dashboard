import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import anthropic
import time
import os
import base64
import math
import urllib.parse
from datetime import datetime, date, timezone

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


@st.cache_data(ttl=120)
def match_timeline(match_id):
    """Event timeline for a match (goals, cards, subs, etc.).
    TheStatsAPI wraps the list as {match_id, coverage, events:[...]}, so unwrap it."""
    try:
        r = stats_get(f"/football/matches/{match_id}/timeline")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json().get("data", [])
        if isinstance(data, dict):
            data = data.get("events", [])
        return data if isinstance(data, list) else []
    except Exception:
        return []


@st.cache_data(ttl=600)
def match_lineups(match_id):
    """Confirmed/predicted lineups: formation + starting XI + substitutes per side."""
    try:
        r = stats_get(f"/football/matches/{match_id}/lineups")
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        d = r.json().get("data", {})
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=300)
def match_odds(match_id):
    """Bookmaker odds (1X2 / BTTS / totals). Heavier — fetched on demand, not every view."""
    try:
        r = stats_get(f"/football/matches/{match_id}/odds")
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        d = r.json().get("data", {})
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def wc_live_matches():
    """Matches in progress now. Tries the common status strings the API may use."""
    for s in ("live", "in_play", "inplay", "playing", "in_progress"):
        try:
            data = wc_matches(s)
        except Exception:
            continue
        if data:
            return data
    return []


def _ev_get(d, *keys):
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if v not in (None, ""):
            return v
    return None


def _name_of(v):
    if isinstance(v, dict):
        return v.get("name") or v.get("display_name") or v.get("full_name")
    return v


def _match_dt(m):
    s = _ev_get(m, "datetime", "date", "kickoff", "start_time", "starting_at", "utc_date", "kickoff_time")
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00").replace(" ", "T", 1))
    except Exception:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _match_goal_lines(mid, home_id, away_id):
    """Return {'home': [...], 'away': [...]} goal tuples (minute, scorer, assist, own_goal)."""
    out = {"home": [], "away": []}
    for ev in match_timeline(mid):
        if not isinstance(ev, dict):
            continue
        et = str(_ev_get(ev, "type", "event_type", "event", "code") or "").lower()
        if "goal" not in et and "score" not in et:
            continue
        if "miss" in et or "disallow" in et or "var" in et:
            continue
        own = "own" in et
        minute = _ev_get(ev, "minute", "time", "clock", "elapsed", "min")
        scorer = _name_of(_ev_get(ev, "player_name", "player", "scorer", "scorer_name"))
        assist = _name_of(_ev_get(ev, "assist_name", "assist_player_name", "assist", "assist_player",
                                  "related_player"))
        tid = _ev_get(ev, "team_id", "team")
        if isinstance(tid, dict):
            tid = tid.get("id")
        side = "home" if tid == home_id else ("away" if tid == away_id else "home")
        try:
            mtxt = f"{int(minute)}'"
        except (TypeError, ValueError):
            mtxt = str(minute) if minute else ""
        out[side].append((mtxt, scorer, assist, own))
    return out


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
    ("bracket", "Live scores"),
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
STANDINGS_CSS = """
<style>
.gs-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:16px; }
.gs-card { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:12px 14px; }
.gs-gtitle { font-size:14px; font-weight:600; color:#fff; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px; }
.gs-table { width:100%; border-collapse:collapse; }
.gs-table th { font-size:10px; text-transform:uppercase; letter-spacing:0.04em; color:rgba(255,255,255,0.5); text-align:right; padding:4px 5px; font-weight:600; }
.gs-table th.l, .gs-table td.l { text-align:left; }
.gs-table td { font-size:13px; color:#fff; padding:7px 5px; text-align:right; border-top:1px solid rgba(255,255,255,0.06); }
.gs-table tr.q td:first-child { box-shadow:inset 3px 0 0 #37b86b; }
.gs-table tr.t3 td:first-child { box-shadow:inset 3px 0 0 #e8b84b; }
.gs-pos { color:rgba(255,255,255,0.55); }
.gs-team img { width:22px; border-radius:2px; vertical-align:middle; margin-right:7px; }
.gs-pts { font-weight:700; }
.gs-tag { font-size:9px; background:rgba(55,184,107,0.22); color:#7fe0b0; padding:2px 6px; border-radius:5px; margin-left:7px; vertical-align:middle; letter-spacing:0.04em; }
.ko-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:10px; }
.ko-tie { display:flex; align-items:center; justify-content:space-between; gap:8px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:9px 14px; }
.ko-team { display:flex; align-items:center; gap:7px; font-size:13px; color:#fff; }
.ko-team img { width:22px; border-radius:2px; }
.ko-prov { opacity:0.5; font-style:italic; }
.ko-vs { font-size:11px; color:rgba(255,255,255,0.4); }
.ko-check { color:#37b86b; font-weight:700; }
.gs-legend { font-size:12px; color:rgba(255,255,255,0.6); margin:6px 0 18px; }
</style>
"""


def _glow_background_css():
    return ("<style>.stApp{background:radial-gradient(circle at 22% 12%, #1a2c46 0%, #0a0f18 62%) !important;}"
            ".backlink{color:rgba(255,255,255,0.78) !important;}"
            ".backlink:hover{color:#ffffff !important;}</style>")


def _qualification(df):
    """Clinch status per team from current points: 'won' (1st locked), 'qualified' (top 2 locked), else 'in'."""
    rows = df.to_dict("records")
    out = {}
    for x in rows:
        above = sum(1 for y in rows if y["Team"] != x["Team"]
                    and (y["Pts"] + 3 * (3 - y["P"])) >= x["Pts"])
        out[x["Team"]] = "won" if above == 0 else ("qualified" if above <= 1 else "in")
    return out


def _heading(big, small=None):
    sub = (f'<div style="width:54px;height:3px;background:#e8b84b;border-radius:2px;margin-top:10px;"></div>')
    return (f'<div style="margin:8px 0 4px;"><div style="font-size:{38 if small is None else 26}px;'
            f'font-weight:700;color:#fff;letter-spacing:0.05em;text-transform:uppercase;line-height:1;">'
            f'{big}</div>{sub}</div>')


def _ko_bracket_svg(field):
    """Symmetric knockout bracket as SVG (photo style, dark/gold). R32 slots filled."""
    n = len(field)
    if n < 4:
        return ('<div style="color:rgba(255,255,255,0.7);">'
                'Not enough results yet to project the bracket.</div>')
    half = n // 2
    bw, bh, vp, cg, top = 122, 22, 30, 26, 30
    step = bw + cg

    def round_ys(count):
        ys = [i * vp for i in range(count)]
        rounds = [ys]
        while len(ys) > 1:
            ys = [(ys[2 * i] + ys[2 * i + 1]) / 2 for i in range(len(ys) // 2)]
            rounds.append(ys)
        return rounds

    lr = round_ys(half)
    nL = len(lr)
    total_w = (2 * nL + 1) * step - cg
    height = (half - 1) * vp + bh + top + 24
    labels = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "", "", "", ""]
    P = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {int(total_w)} {int(height)}" '
         f'style="min-width:{int(total_w)}px;font-family:Oswald,sans-serif;">']
    P.append('<defs><filter id="goldglow" x="-60%" y="-60%" width="220%" height="220%">'
             '<feGaussianBlur stdDeviation="2.4" result="b"/><feMerge>'
             '<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')

    def colx(c):
        return c * step

    def side(team_field, is_left):
        for r, ys in enumerate(lr):
            c = r if is_left else (2 * nL - r)
            x = colx(c)
            for idx, y in enumerate(ys):
                yy = y + top
                item = team_field[idx] if (r == 0 and idx < len(team_field)) else None
                nm = (item["name"] if item else "").replace("&", "&amp;")
                tx = x + bw / 2
                ty = yy + bh / 2 + 3.5
                if not nm:
                    P.append(f'<rect x="{x:.0f}" y="{yy:.0f}" width="{bw}" height="{bh}" rx="4" '
                             f'fill="#0f1726" stroke="rgba(232,184,75,0.18)" stroke-width="1"/>')
                elif item.get("confirmed"):
                    P.append(f'<rect x="{x:.0f}" y="{yy:.0f}" width="{bw}" height="{bh}" rx="4" '
                             f'fill="#1a2740" stroke="#f0cf6a" stroke-width="1.8" filter="url(#goldglow)"/>')
                    P.append(f'<text x="{tx:.0f}" y="{ty:.0f}" text-anchor="middle" '
                             f'fill="#ffe9a8" font-size="10" font-weight="600">{nm}</text>')
                else:
                    P.append(f'<rect x="{x:.0f}" y="{yy:.0f}" width="{bw}" height="{bh}" rx="4" '
                             f'fill="#0e1626" stroke="rgba(232,184,75,0.40)" stroke-width="1" '
                             f'stroke-dasharray="3 2"/>')
                    P.append(f'<text x="{tx:.0f}" y="{ty:.0f}" text-anchor="middle" '
                             f'fill="rgba(255,255,255,0.55)" font-size="9.5" font-style="italic">{nm}</text>')
            if r + 1 < nL:
                c2 = (r + 1) if is_left else (2 * nL - (r + 1))
                px = colx(c2)
                for j, py in enumerate(lr[r + 1]):
                    pcy = py + top + bh / 2
                    for child in (2 * j, 2 * j + 1):
                        ccy = ys[child] + top + bh / 2
                        if is_left:
                            x1, mx, x2 = x + bw, (x + bw + px) / 2, px
                        else:
                            x1, mx, x2 = x, (x + px + bw) / 2, px + bw
                        P.append(f'<path d="M{x1:.0f},{ccy:.0f} L{mx:.0f},{ccy:.0f} '
                                 f'L{mx:.0f},{pcy:.0f} L{x2:.0f},{pcy:.0f}" fill="none" '
                                 f'stroke="rgba(232,184,75,0.28)" stroke-width="1"/>')

    side(field[:half], True)
    side(field[half:], False)

    cx = colx(nL)
    cy = lr[-1][0] + top
    midy = cy + (bh + 8) / 2
    fy = lr[-1][0] + top + bh / 2
    P.append(f'<path d="M{colx(nL - 1) + bw:.0f},{fy:.0f} L{cx:.0f},{midy:.0f}" '
             f'stroke="rgba(232,184,75,0.3)" fill="none"/>')
    P.append(f'<path d="M{colx(nL + 1):.0f},{fy:.0f} L{cx + bw:.0f},{midy:.0f}" '
             f'stroke="rgba(232,184,75,0.3)" fill="none"/>')
    P.append(f'<text x="{cx + bw / 2:.0f}" y="{cy - 9:.0f}" text-anchor="middle" fill="#e8b84b" '
             f'font-size="12" letter-spacing="1.5">FINAL</text>')
    P.append(f'<rect x="{cx:.0f}" y="{cy:.0f}" width="{bw}" height="{bh + 8}" rx="5" '
             f'fill="#1c2336" stroke="#e8b84b" stroke-width="1.6"/>')
    P.append(f'<text x="{cx + bw / 2:.0f}" y="{cy + 19:.0f}" text-anchor="middle" fill="#e8b84b" '
             f'font-size="11" letter-spacing="1">🏆 CHAMPION</text>')

    for r in range(nL):
        if labels[r]:
            P.append(f'<text x="{colx(r) + bw / 2:.0f}" y="14" text-anchor="middle" fill="#e8b84b" '
                     f'font-size="9" letter-spacing="0.5">{labels[r]}</text>')
            P.append(f'<text x="{colx(2 * nL - r) + bw / 2:.0f}" y="14" text-anchor="middle" '
                     f'fill="#e8b84b" font-size="9" letter-spacing="0.5">{labels[r]}</text>')
    P.append('</svg>')
    return '<div style="overflow-x:auto;padding-bottom:6px;">' + "".join(P) + '</div>'


def section_standings():
    st.markdown(_glow_background_css(), unsafe_allow_html=True)
    st.markdown(STANDINGS_CSS, unsafe_allow_html=True)
    st.markdown(_heading("Group standings"), unsafe_allow_html=True)
    if not groups:
        st.markdown('<div style="color:rgba(255,255,255,0.7);margin-top:12px;">No group results yet.</div>',
                    unsafe_allow_html=True)
        return

    cards = ""
    for g in sorted(groups):
        df = groups[g]
        rows_html = ""
        for i, r in enumerate(df.to_dict("records")):
            rows_html += (
                f'<tr><td class="l gs-pos">{i + 1}</td>'
                f'<td class="l gs-team">{_flag_img(r["Team"], 22)}{r["Team"]}</td>'
                f'<td>{r["P"]}</td><td>{r["W"]}</td><td>{r["D"]}</td><td>{r["L"]}</td>'
                f'<td>{r["GD"]}</td><td class="gs-pts">{r["Pts"]}</td></tr>')
        cards += (f'<div class="gs-card"><div class="gs-gtitle">Group {g}</div>'
                  '<table class="gs-table"><thead><tr>'
                  '<th class="l">#</th><th class="l">Team</th><th>P</th><th>W</th><th>D</th>'
                  '<th>L</th><th>GD</th><th>Pts</th></tr></thead>'
                  f'<tbody>{rows_html}</tbody></table></div>')
    st.markdown(f'<div class="gs-grid">{cards}</div>', unsafe_allow_html=True)

    st.markdown(_heading("Round of 32", small=True), unsafe_allow_html=True)
    st.markdown('<div class="gs-legend">First knockout round only. '
                '<span style="color:#ffe9a8;">Solid gold = qualified</span> &nbsp;·&nbsp; '
                '<span style="color:rgba(255,255,255,0.55);font-style:italic;">faded = predicted '
                'from current standings</span>.</div>',
                unsafe_allow_html=True)
    q = qualified_from_groups(groups)
    clinch = {}
    for gg in groups:
        for tname, status in _qualification(groups[gg]).items():
            clinch[tname] = status
    for t in q:
        t["confirmed"] = t["pos"] in (1, 2) and clinch.get(t["name"]) in ("won", "qualified")
    teams = sorted(q, key=lambda t: t["key"], reverse=True)
    size = _largest_pow2(len(teams))
    if size < 2:
        st.markdown('<div style="color:rgba(255,255,255,0.7);">Not enough results yet to project the bracket.</div>',
                    unsafe_allow_html=True)
        return
    teams = teams[:size]
    seeds = {i + 1: t for i, t in enumerate(teams)}
    field = [seeds[s] for s in _seed_order(size)]
    st.markdown(_ko_bracket_svg(field), unsafe_allow_html=True)


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


LIVE_CSS = """
<style>
.lv-wrap { display:flex; flex-direction:column; gap:14px; }
.lv-card { background:rgba(255,255,255,0.04); border:1px solid rgba(232,184,75,0.30); border-radius:12px; padding:14px 18px; }
.lv-badge { display:inline-block; font-size:10px; padding:2px 8px; border-radius:5px; letter-spacing:.06em; }
.lv-live { background:#b3261e; color:#fff; }
.lv-ft { background:rgba(255,255,255,0.12); color:rgba(255,255,255,0.85); }
.lv-up { background:rgba(232,184,75,0.18); color:#ffe0a3; }
.lv-top { text-align:center; margin-bottom:10px; }
.lv-row { display:flex; align-items:center; justify-content:space-between; }
.lv-team { display:flex; align-items:center; gap:8px; flex:1; color:#fff; font-size:15px; }
.lv-team.r { justify-content:flex-end; }
.lv-team img { width:26px; border-radius:2px; }
.lv-score { color:#ffe9a8; font-size:26px; font-weight:600; padding:0 16px; white-space:nowrap; }
.lv-goals { display:flex; justify-content:space-between; gap:10px; margin-top:10px; border-top:1px solid rgba(255,255,255,0.08); padding-top:9px; }
.lv-goals .g { font-size:12px; color:rgba(255,255,255,0.78); line-height:1.7; flex:1; }
.lv-goals .g.r { text-align:right; }
.lv-goals .g .a { opacity:.55; }
.lv-sect { color:#e8b84b; font-size:13px; letter-spacing:.06em; text-transform:uppercase; margin:20px 0 2px; }
.lv-link { text-decoration:none; display:block; }
.lv-card { transition:border-color .15s, background .15s; }
.lv-link:hover .lv-card { border-color:#e8b84b; background:rgba(255,255,255,0.08); }
.ms-row { display:flex; align-items:center; justify-content:space-between; margin-top:12px; font-size:13px; }
.ms-row .ms-v { color:#fff; width:60px; }
.ms-row .ms-v.r { text-align:right; }
.ms-row .ms-lab { color:rgba(255,255,255,0.6); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
.ms-bar { display:flex; height:6px; border-radius:3px; overflow:hidden; margin-top:5px; background:rgba(255,255,255,0.08); }
.ms-bar .ms-h { background:#e8b84b; }
.ms-bar .ms-a { background:#5b8fb0; }
.lvr-date { color:#fff; font-size:17px; font-weight:500; border-bottom:1px solid rgba(232,184,75,0.35); padding-bottom:7px; margin:22px 0 2px; scroll-margin-top:75px; }
.lvr-date.today { color:#ffe9a8; }
.lvr { display:flex; align-items:center; padding:9px 6px; border-bottom:1px solid rgba(255,255,255,0.07); text-decoration:none; }
.lvr:hover { background:rgba(255,255,255,0.05); }
.lvr-st { width:62px; flex-shrink:0; font-size:11px; color:rgba(255,255,255,0.55); }
.lvr-st.live { color:#ff5b52; font-weight:600; }
.lvr-st.up { color:#ffe0a3; }
.lvr-tms { flex:1; min-width:0; }
.lvr-tm { display:flex; align-items:center; gap:8px; color:#fff; font-size:14px; }
.lvr-tm.top { margin-bottom:5px; }
.lvr-tm.lose { color:rgba(255,255,255,0.5); }
.lvr-tm img { width:22px; border-radius:2px; flex-shrink:0; }
.lvr-tm span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.lvr-sc { width:26px; flex-shrink:0; text-align:right; color:#ffe9a8; font-size:15px; font-weight:600; line-height:1.55; }
.lvr-sc.up { color:rgba(255,255,255,0.30); font-weight:400; }
</style>
"""


def _goals_col(items, right=False):
    cls = "g r" if right else "g"
    if not items:
        return f'<div class="{cls}" style="opacity:.35;">—</div>'
    rows = []
    for mtxt, scorer, assist, own in items:
        line = (f"{mtxt} " if mtxt else "") + (scorer or "Goal").replace("&", "&amp;")
        if own:
            line += " (OG)"
        if assist:
            line += f' <span class="a">· assist {assist.replace("&", "&amp;")}</span>'
        rows.append(line)
    return f'<div class="{cls}">' + "<br>".join(rows) + "</div>"


def _score_row(m, status, dt, anchor=False):
    """One compact, clickable match row (live-score-site style)."""
    mid = m.get("id")
    home = (m.get("home_team") or {}).get("name", "?")
    away = (m.get("away_team") or {}).get("name", "?")
    hs, a_s = m.get("score", {}).get("home"), m.get("score", {}).get("away")
    if status == "live":
        mins = _ev_get(m, "minute", "clock", "elapsed", "min")
        try:
            st_html = f'<div class="lvr-st live">● {int(mins)}\'</div>'
        except (TypeError, ValueError):
            st_html = '<div class="lvr-st live">● LIVE</div>'
    elif status == "up":
        st_html = f'<div class="lvr-st up">{dt.strftime("%H:%M") if dt else "—"}</div>'
    else:
        st_html = '<div class="lvr-st">FT</div>'
    has_score = hs is not None and a_s is not None
    hcls = acls = ""
    if status == "ft" and has_score:
        if hs > a_s:
            acls = " lose"
        elif a_s > hs:
            hcls = " lose"
    if has_score:
        sc = f'<div class="lvr-sc"><div>{hs}</div><div>{a_s}</div></div>'
    else:
        sc = '<div class="lvr-sc up"><div>–</div><div>–</div></div>'
    aid_attr = ' id="lv-focus"' if anchor else ""
    return (
        f'<a class="lvr"{aid_attr} href="?view=match&match={mid}" target="_self">'
        f'{st_html}'
        '<div class="lvr-tms">'
        f'<div class="lvr-tm top{hcls}">{_flag_img(home, 22)}<span>{home}</span></div>'
        f'<div class="lvr-tm{acls}">{_flag_img(away, 22)}<span>{away}</span></div>'
        '</div>'
        f'{sc}</a>'
    )


def section_bracket():
    st.markdown(_glow_background_css(), unsafe_allow_html=True)
    st.markdown(LIVE_CSS, unsafe_allow_html=True)
    st.markdown(_heading("Live scores"), unsafe_allow_html=True)
    if not wc_ok:
        st.warning("Couldn't load match data right now — try again shortly.")
        return
    if st.button("🔄 Refresh"):
        st.rerun()

    live = wc_live_matches()
    today = date.today()
    live_ids = {str(m.get("id")) for m in live}
    entries = [(m, _match_dt(m), "live") for m in live]
    entries += [(m, _match_dt(m), "ft") for m in finished if str(m.get("id")) not in live_ids]
    entries += [(m, _match_dt(m), "up") for m in upcoming if str(m.get("id")) not in live_ids]

    if not entries:
        st.info("No match data available yet. Live scores will appear here on match days.")
        return

    dated = [e for e in entries if e[1] is not None]
    undated = [e for e in entries if e[1] is None]

    parts = []
    have_today = False
    has_past = False
    focus_set = False
    has_live = any(s == "live" for _, _, s in dated)
    if dated:
        by_day = {}
        for m, dt, status in dated:
            by_day.setdefault(dt.date(), []).append((m, dt, status))
        for d in sorted(by_day):
            rows = sorted(by_day[d], key=lambda e: e[1])
            is_today = (d == today)
            have_today = have_today or is_today
            has_past = has_past or (d < today)
            label = (("Today · " if is_today else "")
                     + f"{d.strftime('%A')} {d.day} {d.strftime('%B')}")
            # Focus anchor: a live match if there is one, otherwise the Today header.
            head_anchor = ""
            if is_today and not has_live and not focus_set:
                head_anchor = ' id="lv-focus"'
                focus_set = True
            cls = "lvr-date today" if is_today else "lvr-date"
            parts.append(f'<div class="{cls}"{head_anchor}>{label}</div>')
            for m, dt, status in rows:
                row_anchor = has_live and not focus_set and status == "live"
                if row_anchor:
                    focus_set = True
                parts.append(_score_row(m, status, dt, anchor=row_anchor))
    if undated:
        parts.append('<div class="lvr-date">Other matches</div>')
        parts += [_score_row(e[0], e[2], e[1]) for e in undated]
    st.markdown("".join(parts), unsafe_allow_html=True)

    if focus_set and has_past:
        components.html(
            "<script>const d=window.parent.document;"
            "function s(){const e=d.getElementById('lv-focus');"
            "if(e){e.scrollIntoView({block:'center'});}}"
            "setTimeout(s,80);setTimeout(s,350);</script>", height=0)

    st.markdown('<div style="margin-top:16px;font-size:12px;color:rgba(255,255,255,0.6);">Tap any match '
                'for full stats, goals and the scorer timeline.</div>', unsafe_allow_html=True)


def _fmt_stat(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        v = int(v) if v.is_integer() else round(v, 2)
    return f"{v}{unit}"


MATCH_STAT_ROWS = [("Possession", "ball_possession", "%"), ("Expected goals (xG)", "expected_goals", ""),
                   ("Total shots", "total_shots", ""), ("Shots on target", "shots_on_target", ""),
                   ("Big chances", "big_chances", ""), ("Goalkeeper saves", "goalkeeper_saves", ""),
                   ("Corners", "corner_kicks", ""), ("Fouls", "fouls", ""),
                   ("Tackles", "tackles", ""), ("Free kicks", "free_kicks", ""),
                   ("Yellow cards", "yellow_cards", ""), ("Red cards", "red_cards", ""),
                   ("Passes", "passes", ""), ("Accurate passes", "accurate_passes", "")]


MATCH_CSS = """
<style>
.md-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; align-items:start; }
@media (max-width:640px){ .md-grid{ grid-template-columns:1fr; } }
.md-muted { color:rgba(255,255,255,0.55); font-size:12px; }
.md-row { display:flex; justify-content:space-between; font-size:12px; color:rgba(255,255,255,0.6); margin-top:3px; }
.sub-h { display:flex; align-items:center; gap:8px; color:#fff; font-weight:600; font-size:15px; margin-bottom:4px; }
.fchip { display:inline-block; background:rgba(232,184,75,0.14); border:1px solid rgba(232,184,75,0.35); border-radius:6px; padding:2px 10px; font-size:12px; color:#e8b84b; font-weight:700; letter-spacing:.04em; }
/* event timeline */
.tl-ev { display:flex; align-items:center; gap:10px; padding:6px 2px; font-size:13px; color:#fff; border-bottom:1px solid rgba(255,255,255,0.05); }
.tl-ev.away { flex-direction:row-reverse; text-align:right; }
.tl-min { min-width:46px; color:#e8b84b; font-weight:700; font-size:12px; }
.tl-ev.away .tl-min { color:#7fb6d6; }
.tl-ic { width:20px; text-align:center; }
.tl-pl { font-weight:600; }
.tl-sub { color:rgba(255,255,255,0.45); font-size:11px; margin-left:6px; }
.tl-ev.away .tl-sub { margin-left:0; margin-right:6px; }
/* lineups */
.xi { list-style:none; padding:0; margin:6px 0 0; }
.xi li { display:flex; align-items:center; gap:9px; padding:5px 0; border-bottom:1px solid rgba(255,255,255,0.06); font-size:13px; color:#fff; }
.xi .num { display:inline-block; min-width:24px; height:22px; line-height:22px; text-align:center; background:rgba(232,184,75,0.16); color:#e8b84b; border-radius:6px; font-size:11px; font-weight:700; }
.xi .pos { margin-left:auto; font-size:10px; color:rgba(255,255,255,0.45); text-transform:uppercase; letter-spacing:.04em; }
/* form pills */
.frm { display:flex; gap:5px; margin-top:6px; flex-wrap:wrap; }
.frm span { width:24px; height:24px; line-height:24px; text-align:center; border-radius:5px; font-size:12px; font-weight:800; }
.frm .w { background:#37b86b; color:#06240f; } .frm .d { background:#e8b84b; color:#332600; } .frm .l { background:#e24b4a; color:#fff; }
.frm-line { font-size:12px; color:rgba(255,255,255,0.7); margin-top:8px; line-height:1.7; }
/* prediction */
.wdl { display:flex; height:30px; border-radius:7px; overflow:hidden; margin:10px 0 2px; font-size:12px; font-weight:800; }
.wdl div { display:flex; align-items:center; justify-content:center; min-width:0; }
.wdl .h { background:#e8b84b; color:#332600; } .wdl .d { background:#5b6b80; color:#fff; } .wdl .a { background:#7fb6d6; color:#08222e; }
/* ratings */
.motm { display:flex; align-items:center; gap:12px; background:linear-gradient(90deg,rgba(232,184,75,0.20),rgba(232,184,75,0.02)); border:1px solid rgba(232,184,75,0.40); border-radius:10px; padding:11px 15px; margin-bottom:6px; }
.motm .rt { margin-left:auto; font-size:23px; font-weight:800; color:#e8b84b; }
.rrow { display:flex; align-items:center; gap:8px; font-size:13px; color:#fff; padding:5px 0; border-bottom:1px solid rgba(255,255,255,0.06); }
.rrow .rt { margin-left:auto; font-weight:800; color:#e8b84b; }
.rrow .ev { color:rgba(255,255,255,0.55); font-size:11px; }
/* ---- premium stats panel ---- */
.sh { padding:17px 22px 19px; }
.sh-legend { display:flex; justify-content:space-between; margin-bottom:16px; }
.sh-legend .th { display:flex; align-items:center; gap:8px; font-weight:700; color:#fff; font-size:14.5px; padding-bottom:7px; }
.sh-legend .th img { border-radius:3px; }
.sh-legend .th.h { border-bottom:2px solid #e8b84b; }
.sh-legend .th.a { border-bottom:2px solid #7fb6d6; }
.sh-poss, .sh-xg { display:grid; grid-template-columns:1fr auto 1fr; align-items:baseline; }
.sh-xg { margin-top:18px; }
.sh-big { font-size:31px; font-weight:800; font-variant-numeric:tabular-nums; line-height:1; }
.sh-big.h { text-align:left; color:#e8b84b; } .sh-big.a { text-align:right; color:#7fb6d6; }
.sh-xv { font-size:21px; font-weight:800; font-variant-numeric:tabular-nums; }
.sh-xv.h { text-align:left; color:#e8b84b; } .sh-xv.a { text-align:right; color:#7fb6d6; }
.sh-mid { font-size:10.5px; letter-spacing:.12em; text-transform:uppercase; color:rgba(255,255,255,0.55); padding:0 16px; align-self:center; white-space:nowrap; }
.sh-bar { display:flex; height:9px; gap:3px; margin:11px 0 2px; }
.sh-bar span { border-radius:99px; min-width:3px; }
.sh-bar .h { background:linear-gradient(90deg,rgba(232,184,75,0.45),#e8b84b); box-shadow:0 0 14px rgba(232,184,75,0.25); }
.sh-bar .a { background:linear-gradient(270deg,rgba(127,182,214,0.45),#5b8fb0); box-shadow:0 0 14px rgba(91,143,176,0.25); }
.cmp { padding:11px 2px; }
.cmp + .cmp { border-top:1px solid rgba(255,255,255,0.06); }
.cmp-top { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; }
.cmp-v { font-size:17px; font-weight:700; font-variant-numeric:tabular-nums; color:rgba(255,255,255,0.45); }
.cmp-v.h { text-align:left; } .cmp-v.a { text-align:right; }
.cmp-v.lead { color:#fff; }
.cmp-lab { font-size:11px; letter-spacing:.07em; text-transform:uppercase; color:rgba(255,255,255,0.5); padding:0 14px; text-align:center; white-space:nowrap; }
.cmp-bar { display:flex; height:5px; gap:3px; margin-top:8px; }
.cmp-bar span { border-radius:99px; min-width:2px; }
.cmp-bar .h { background:linear-gradient(90deg,rgba(232,184,75,0.40),#e8b84b); }
.cmp-bar .a { background:linear-gradient(270deg,rgba(127,182,214,0.40),#5b8fb0); }
.cmp-bar .h.dim, .cmp-bar .a.dim { opacity:.32; }
/* tab chrome */
.stTabs [data-baseweb="tab-list"] { gap:3px; }
.stTabs [data-baseweb="tab"] { height:36px; padding:0 13px; color:rgba(255,255,255,0.55); font-size:12.5px; font-weight:600; letter-spacing:.01em; }
.stTabs [aria-selected="true"] { color:#e8b84b !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color:#e8b84b !important; }
.stTabs [data-baseweb="tab-border"] { background-color:rgba(255,255,255,0.08); }
/* ---- goalscorers in the score header ---- */
.lv-scorers { display:flex; justify-content:space-between; gap:12px; margin-top:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08); }
.lv-scorers .sc { flex:1; font-size:12.5px; color:rgba(255,255,255,0.88); line-height:1.85; }
.lv-scorers .sc.a { text-align:right; }
.lv-scorers .sc .min { color:rgba(255,255,255,0.5); font-weight:600; }
/* ---- formation pitch ---- */
.pteam { display:flex; align-items:center; gap:8px; font-weight:700; font-size:14px; padding:5px 2px; }
.pteam img { border-radius:3px; }
.pteam .fchip { margin-left:4px; }
.pteam.a { color:#bfe0f2; } .pteam.h { color:#f3d489; margin-top:8px; }
.pitch { position:relative; width:100%; padding-bottom:142%; border-radius:12px; overflow:hidden; margin:4px 0;
  background:#11652f;
  background-image:repeating-linear-gradient(180deg, rgba(255,255,255,0.05) 0 70px, rgba(0,0,0,0.05) 70px 140px); }
.pmark { position:absolute; inset:0; width:100%; height:100%; }
.pl { position:absolute; transform:translate(-50%,-50%); width:62px; text-align:center; z-index:2; }
.pl .jersey { width:32px; height:32px; line-height:32px; margin:0 auto; border-radius:50%; font-weight:800; font-size:13px; font-variant-numeric:tabular-nums; box-shadow:0 2px 5px rgba(0,0,0,0.45); }
.pl.h .jersey { background:linear-gradient(160deg,#f0c659,#e0a82f); color:#241803; }
.pl.a .jersey { background:linear-gradient(160deg,#8fc0dd,#5b8fb0); color:#042231; }
.pl .nm { font-size:9.5px; color:#fff; margin-top:3px; line-height:1.1; font-weight:600; text-shadow:0 1px 3px rgba(0,0,0,0.95); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
/* ---- substitutions ---- */
.sub-pair { display:flex; align-items:center; gap:8px; font-size:13px; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.05); }
.sub-pair:last-child { border-bottom:none; }
.sub-min { min-width:38px; color:#e8b84b; font-weight:700; font-size:12px; }
.sub-pair .on { color:#37b86b; font-weight:600; }
.sub-pair .off { color:#e98a88; }
</style>
"""

EVENT_ICON = {"goal": "⚽", "penalty_missed": "❌", "penalty_awarded": "🎯",
              "yellow_card": "🟨", "red_card": "🟥", "substitution": "🔄", "var": "📺"}
EVENT_LABEL = {"penalty_missed": "penalty missed", "penalty_awarded": "penalty won",
               "substitution": "substituted", "var": "VAR check",
               "yellow_card": "yellow card", "red_card": "red card"}


def _section(title):
    st.markdown(f'<div class="lv-sect">{title}</div>', unsafe_allow_html=True)


def _card(html, pad="14px 20px"):
    st.markdown(f'<div class="lv-card" style="padding:{pad};">{html}</div>', unsafe_allow_html=True)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _timeline_html(mid, hid, aid):
    evs = [e for e in match_timeline(mid) if isinstance(e, dict) and e.get("type") in EVENT_ICON]
    if not evs:
        return None
    evs.sort(key=lambda e: e.get("sequence", 0))
    out = []
    for e in evs:
        t = e.get("type")
        tm = e.get("team") or {}
        side = "home" if tm.get("id") == hid else "away"
        mn, ex = e.get("minute"), e.get("extra_time") or 0
        mtxt = (f"{mn}'" + (f"+{ex}" if ex else "")) if mn is not None else ""
        pl = _name_of(e.get("player")) or EVENT_LABEL.get(t, t)
        sub = "" if t == "goal" else f'<span class="tl-sub">{EVENT_LABEL.get(t, t)}</span>'
        out.append(f'<div class="tl-ev {side}"><span class="tl-min">{mtxt}</span>'
                   f'<span class="tl-ic">{EVENT_ICON[t]}</span>'
                   f'<span><span class="tl-pl">{_esc(pl)}</span>{sub}</span></div>')
    return "".join(out)


def _ratings_block(mid, hid, aid, home, away):
    ps = [p for p in match_player_stats(mid) if p.get("rating") and p.get("played")]
    if not ps:
        return None
    ps.sort(key=lambda p: -(p.get("rating") or 0))
    motm = ps[0]
    mt_name = home if motm.get("team_id") == hid else away

    def rrow(p):
        g = (p.get("shooting") or {}).get("goals") or 0
        a = (p.get("passing") or {}).get("assists") or 0
        ev = []
        if g:
            ev.append(f'{g}⚽')
        if a:
            ev.append(f'{a}🅰')
        evs = f'<span class="ev">{" ".join(ev)}</span>' if ev else ""
        return (f'<div class="rrow"><span>{_esc(p.get("player_name", ""))}</span>{evs}'
                f'<span class="rt">{p.get("rating"):.1f}</span></div>')

    motm_html = (f'<div class="motm">{_flag_img(mt_name, 30)}<div>'
                 f'<div style="font-weight:700;color:#fff;">{_esc(motm.get("player_name", ""))}</div>'
                 f'<div class="md-muted">⭐ Player of the match · {_esc(mt_name)}</div></div>'
                 f'<div class="rt">{motm.get("rating"):.1f}</div></div>')
    home_top = [p for p in ps if p.get("team_id") == hid][:6]
    away_top = [p for p in ps if p.get("team_id") == aid][:6]
    cols = (f'<div><div class="sub-h">{_flag_img(home, 22)}{_esc(home)}</div>'
            + "".join(rrow(p) for p in home_top) + '</div>'
            f'<div><div class="sub-h">{_flag_img(away, 22)}{_esc(away)}</div>'
            + "".join(rrow(p) for p in away_top) + '</div>')
    return motm_html + f'<div class="md-grid" style="margin-top:10px;">{cols}</div>'


def _predict_html(home, away):
    try:
        p = predict_fixture(home, away, finished)
    except Exception:
        return None
    pH, pD, pA = p["pA"], p["pD"], p["pB"]
    i, j = p["score"]
    bar = (f'<div class="wdl"><div class="h" style="width:{pH * 100:.0f}%">{pH * 100:.0f}%</div>'
           f'<div class="d" style="width:{pD * 100:.0f}%">{pD * 100:.0f}%</div>'
           f'<div class="a" style="width:{pA * 100:.0f}%">{pA * 100:.0f}%</div></div>')
    labels = (f'<div class="md-row"><span>{_esc(home)} win</span><span>Draw</span>'
              f'<span>{_esc(away)} win</span></div>')
    foot = (f'<div class="md-muted" style="margin-top:10px;">Most likely score '
            f'<b style="color:#fff;">{_esc(home)} {i}–{j} {_esc(away)}</b> · '
            f'expected goals {p["la"]:.2f} – {p["lb"]:.2f}</div>')
    return bar + labels + foot


# Every team stat TheStatsAPI exposes for a match, grouped into tabs. Each entry is
# (label, section, key, kind) where section is a /stats top-level block and kind is
# how to format/scale it: "count" (proportional bar), "pct" (already a %), "float"
# (decimals, e.g. xG). "__passacc__" is derived from passes / accurate_passes.
STAT_GROUPS = [
    ("Shooting", [
        ("Expected goals (xG)", "overview", "expected_goals", "float"),
        ("Total shots", "shots", "total_shots", "count"),
        ("Shots on target", "shots", "shots_on_target", "count"),
        ("Shots off target", "shots", "shots_off_target", "count"),
        ("Blocked shots", "shots", "blocked_shots", "count"),
        ("Shots inside box", "shots", "shots_inside_box", "count"),
        ("Shots outside box", "shots", "shots_outside_box", "count"),
        ("Hit woodwork", "shots", "hit_woodwork", "count"),
        ("Big chances", "overview", "big_chances", "count"),
        ("Big chances missed", "attack", "big_chances_missed", "count"),
    ]),
    ("Passing", [
        ("Possession", "overview", "ball_possession", "pct"),
        ("Passes", "overview", "passes", "count"),
        ("Accurate passes", "overview", "accurate_passes", "count"),
        ("Pass accuracy", "__passacc__", None, "pct"),
        ("Accurate crosses", "passes", "accurate_crosses", "count"),
        ("Accurate long balls", "passes", "accurate_long_balls", "count"),
        ("Final-third entries", "passes", "final_third_entries", "count"),
        ("Touches in box", "attack", "touches_in_penalty_area", "count"),
        ("Throw-ins", "passes", "throw_ins", "count"),
    ]),
    ("Duels & defending", [
        ("Duels won", "duels", "duels_won_percentage", "pct"),
        ("Ground duels won", "duels", "ground_duels_percentage", "pct"),
        ("Aerial duels won", "duels", "aerial_duels_percentage", "pct"),
        ("Dribbles", "duels", "dribbles_percentage", "pct"),
        ("Dispossessed", "duels", "dispossessed", "count"),
        ("Tackles", "defending", "tackles", "count"),
        ("Tackles won", "defending", "tackles_won_percentage", "pct"),
        ("Interceptions", "defending", "interceptions", "count"),
        ("Clearances", "defending", "clearances", "count"),
        ("Ball recoveries", "defending", "ball_recoveries", "count"),
    ]),
    ("Goalkeeping", [
        ("Saves", "goalkeeping", "saves", "count"),
        ("Goals prevented", "goalkeeping", "goals_prevented", "float"),
        ("Goal kicks", "goalkeeping", "goal_kicks", "count"),
        ("High claims", "goalkeeping", "high_claims", "count"),
    ]),
    ("Discipline & set pieces", [
        ("Fouls", "overview", "fouls", "count"),
        ("Fouled in final third", "attack", "fouled_in_final_third", "count"),
        ("Offsides", "attack", "offsides", "count"),
        ("Yellow cards", "overview", "yellow_cards", "count"),
        ("Red cards", "overview", "red_cards", "count"),
        ("Corners", "overview", "corner_kicks", "count"),
        ("Free kicks", "overview", "free_kicks", "count"),
    ]),
]


def _stat_get(full, section, key, side):
    try:
        return full[section][key]["all"][side]
    except Exception:
        return None


def _n(x, pct=False):
    if x is None:
        return "—"
    if isinstance(x, float):
        x = int(x) if float(x).is_integer() else round(x, 2)
    return f"{x}%" if pct else f"{x}"


def _cmp_row(label, hv, av, kind):
    if hv is None and av is None:
        return ""
    try:
        hn = float(hv) if hv is not None else 0.0
        an = float(av) if av is not None else 0.0
    except (TypeError, ValueError):
        hn, an = 0.0, 0.0
    lh = " lead" if hn > an else ""
    la = " lead" if an > hn else ""
    bar = ""
    if hn >= 0 and an >= 0 and (hn + an) > 0:
        hp = hn / (hn + an) * 100
        dh = " dim" if hn < an else ""
        da = " dim" if an < hn else ""
        bar = (f'<div class="cmp-bar"><span class="h{dh}" style="width:{hp:.1f}%"></span>'
               f'<span class="a{da}" style="width:{100 - hp:.1f}%"></span></div>')
    pct = (kind == "pct")
    return (f'<div class="cmp"><div class="cmp-top">'
            f'<span class="cmp-v h{lh}">{_n(hv, pct)}</span>'
            f'<span class="cmp-lab">{label}</span>'
            f'<span class="cmp-v a{la}">{_n(av, pct)}</span></div>{bar}</div>')


def _team_legend(home, away):
    """Slim colour key (home = gold, away = blue) shown above the tabbed panel."""
    return (f'<div class="lv-card" style="padding:13px 20px;"><div class="sh-legend" style="margin:0;">'
            f'<div class="th h">{_flag_img(home, 22)}<span>{_esc(home)}</span></div>'
            f'<div class="th a"><span>{_esc(away)}</span>{_flag_img(away, 22)}</div></div></div>')


def _render_match_centre(mid, hid, aid, home, away):
    """The single tabbed home for BOTH the key-events timeline and every team stat
    (split across category tabs). No separate stats panel / no separate events block."""
    try:
        full = wc_match_stats(mid)
    except Exception:
        full = {}
    tl = _timeline_html(mid, hid, aid)
    has_stats = bool(full.get("overview"))
    if not tl and not has_stats:
        st.caption("No stats or events published for this match yet.")
        return
    st.markdown(_team_legend(home, away), unsafe_allow_html=True)
    tabs = st.tabs(["Key events"] + [g[0] for g in STAT_GROUPS])
    with tabs[0]:
        if tl:
            _card(tl, pad="8px 18px")
        else:
            st.caption("No key events recorded for this match.")
    for tab, (_title, rows) in zip(tabs[1:], STAT_GROUPS):
        with tab:
            html = []
            for label, section, key, kind in rows:
                if section == "__passacc__":
                    hp_, ap_ = _stat_get(full, "overview", "passes", "home"), _stat_get(full, "overview", "passes", "away")
                    ha_, aa_ = _stat_get(full, "overview", "accurate_passes", "home"), _stat_get(full, "overview", "accurate_passes", "away")
                    hv = round(ha_ / hp_ * 100) if hp_ else None
                    av = round(aa_ / ap_ * 100) if ap_ else None
                else:
                    hv, av = _stat_get(full, section, key, "home"), _stat_get(full, section, key, "away")
                html.append(_cmp_row(label, hv, av, kind))
            body = "".join(x for x in html if x)
            if body:
                _card(body, pad="4px 20px 10px")
            else:
                st.caption("Not published for this match.")


def _scorers_strip(g):
    """Goalscorers per side (grouped by player, minutes listed) for the score header."""
    def col(items, right=False):
        cls = "sc a" if right else "sc"
        if not items:
            return f'<div class="{cls}"></div>'
        order, mins = [], {}
        for mtxt, scorer, assist, own in items:
            key = (scorer or "Goal", own)
            if key not in mins:
                mins[key] = []
                order.append(key)
            if mtxt:
                mins[key].append(mtxt)
        lines = []
        for (scorer, own) in order:
            ms = ", ".join(mins[(scorer, own)])
            og = " (OG)" if own else ""
            lines.append(f'⚽ {_esc(scorer)}{og} <span class="min">{ms}</span>')
        return f'<div class="{cls}">' + "<br>".join(lines) + "</div>"
    return f'<div class="lv-scorers">{col(g["home"])}{col(g["away"], right=True)}</div>'


def _short_name(name):
    parts = (name or "").split()
    return parts[-1] if parts else ""


def _formation_rows(side):
    """(goalkeeper, [outfield rows]) for a side, ordered defence -> attack.
    Uses the stated formation when it matches the XI, else falls back to D/M/F counts."""
    xi = (side or {}).get("starting_xi") or []
    if not xi:
        return None, []
    gk = next((p for p in xi if (p.get("position") or "").upper().startswith("G")), xi[0])
    out = [p for p in xi if p is not gk]
    nums = [int(x) for x in (side.get("formation") or "").split("-") if x.strip().isdigit()]
    lines = nums if (nums and sum(nums) == len(out)) else []
    if not lines:
        buckets = {"D": [], "M": [], "F": []}
        for p in out:
            c = (p.get("position") or "M").upper()[:1]
            buckets[c if c in buckets else "M"].append(p)
        out = buckets["D"] + buckets["M"] + buckets["F"]
        lines = [len(buckets[c]) for c in ("D", "M", "F") if buckets[c]]
    if not lines or sum(lines) != len(out):
        lines = [len(out)]
    rows, idx = [], 0
    for n in lines:
        rows.append(out[idx:idx + n])
        idx += n
    return gk, rows


def _pitch_nodes(side, is_home):
    gk, rows = _formation_rows(side)
    if not gk:
        return ""
    allrows = [[gk]] + [r for r in rows if r]
    n = len(allrows)
    nodes = []
    for r, row in enumerate(allrows):
        frac = (r / (n - 1)) if n > 1 else 0.5
        y = (95 - frac * (95 - 54)) if is_home else (5 + frac * (46 - 5))
        m = len(row)
        for i, p in enumerate(row):
            x = (i + 1) / (m + 1) * 100
            num = p.get("jersey_number") or ""
            nm = _esc(_short_name(p.get("name", "")))
            nodes.append(f'<div class="pl {"h" if is_home else "a"}" style="left:{x:.1f}%;top:{y:.1f}%;">'
                         f'<div class="jersey">{num}</div><div class="nm">{nm}</div></div>')
    return "".join(nodes)


PITCH_SVG = ("<svg class='pmark' viewBox='0 0 680 1050' preserveAspectRatio='none' "
             "xmlns='http://www.w3.org/2000/svg'>"
             "<g fill='none' stroke='#ffffff' stroke-opacity='0.22' stroke-width='3'>"
             "<rect x='8' y='8' width='664' height='1034' rx='4'/>"
             "<line x1='8' y1='525' x2='672' y2='525'/><circle cx='340' cy='525' r='95'/>"
             "<rect x='150' y='877' width='380' height='165'/><rect x='250' y='977' width='180' height='65'/>"
             "<rect x='150' y='8' width='380' height='165'/><rect x='250' y='8' width='180' height='65'/></g>"
             "<circle cx='340' cy='525' r='4' fill='#ffffff' fill-opacity='0.3'/></svg>")


def _pitch_html(lu, home, away):
    hs, as_ = (lu or {}).get("home"), (lu or {}).get("away")
    if not ((hs and hs.get("starting_xi")) or (as_ and as_.get("starting_xi"))):
        return None
    af, hf = (as_ or {}).get("formation"), (hs or {}).get("formation")
    top = (f'<div class="pteam a">{_flag_img(away, 20)}<span>{_esc(away)}</span>'
           + (f'<span class="fchip">{_esc(af)}</span>' if af else "") + '</div>')
    bot = (f'<div class="pteam h">{_flag_img(home, 20)}<span>{_esc(home)}</span>'
           + (f'<span class="fchip">{_esc(hf)}</span>' if hf else "") + '</div>')
    pitch = f'<div class="pitch">{PITCH_SVG}{_pitch_nodes(as_, False)}{_pitch_nodes(hs, True)}</div>'
    return top + pitch + bot


def _subs_html(mid, hid, aid, home, away):
    """Who came on for who, from player-stats: a starter's `player_subbed_on` is the
    player who replaced them, at their minutes_played minute."""
    try:
        ps = match_player_stats(mid)
    except Exception:
        ps = []
    if not ps:
        return None
    name = {p.get("player_id"): p.get("player_name") for p in ps}
    pairs = {hid: [], aid: []}
    for p in ps:
        on_id = (p.get("general") or {}).get("player_subbed_on")
        if p.get("started") and on_id and p.get("team_id") in pairs:
            pairs[p["team_id"]].append((p.get("minutes_played") or 0,
                                        p.get("player_name"), name.get(on_id, "—")))
    if not pairs[hid] and not pairs[aid]:
        return None

    def col(tid):
        rows = sorted(pairs[tid], key=lambda x: x[0])
        if not rows:
            return '<div class="md-muted">No substitutions</div>'
        return "".join(f'<div class="sub-pair"><span class="sub-min">{mn}\'</span>'
                       f'<span class="on">▲ {_esc(on)}</span>'
                       f'<span class="md-muted">for</span>'
                       f'<span class="off">▼ {_esc(off)}</span></div>'
                       for mn, off, on in rows)
    return (f'<div class="md-grid">'
            f'<div><div class="sub-h">{_flag_img(home, 20)}{_esc(home)}</div>{col(hid)}</div>'
            f'<div><div class="sub-h">{_flag_img(away, 20)}{_esc(away)}</div>{col(aid)}</div></div>')


def match_page():
    mid = st.query_params.get("match")
    st.markdown(_glow_background_css(), unsafe_allow_html=True)
    st.markdown(LIVE_CSS, unsafe_allow_html=True)
    st.markdown(MATCH_CSS, unsafe_allow_html=True)
    pool = {}
    try:
        for mm in wc_live_matches():
            pool[str(mm.get("id"))] = ("live", mm)
    except Exception:
        pass
    for mm in finished:
        pool.setdefault(str(mm.get("id")), ("ft", mm))
    for mm in upcoming:
        pool.setdefault(str(mm.get("id")), ("up", mm))
    entry = pool.get(str(mid))
    if not entry:
        st.warning("Couldn't find that match.")
        return
    state, m = entry
    home = (m.get("home_team") or {}).get("name", "?")
    away = (m.get("away_team") or {}).get("name", "?")
    hid = (m.get("home_team") or {}).get("id")
    aid = (m.get("away_team") or {}).get("id")
    hs, a_s = m.get("score", {}).get("home"), m.get("score", {}).get("away")
    dt = _match_dt(m)
    if state == "live":
        mins = _ev_get(m, "minute", "clock", "elapsed", "min")
        try:
            badge = f'<span class="lv-badge lv-live">● LIVE {int(mins)}\'</span>'
        except (TypeError, ValueError):
            badge = '<span class="lv-badge lv-live">● LIVE</span>'
    elif state == "ft":
        badge = f'<span class="lv-badge lv-ft">FULL TIME{(" · " + dt.strftime("%d %b")) if dt else ""}</span>'
    else:
        badge = f'<span class="lv-badge lv-up">{dt.strftime("%d %b · %H:%M") if dt else "UPCOMING"}</span>'
    grp = m.get("group_label")
    score = f"{hs} – {a_s}" if hs is not None and a_s is not None else "vs"
    # Goalscorers live in the score header itself (no separate goals block).
    scorers = ""
    if state in ("live", "ft"):
        g = _match_goal_lines(mid, hid, aid)
        if g["home"] or g["away"]:
            scorers = _scorers_strip(g)
    st.markdown(
        '<div class="lv-card" style="padding:20px 22px;">'
        f'<div class="lv-top">{badge}{(" · Group " + grp) if grp else ""}</div>'
        '<div class="lv-row">'
        f'<div class="lv-team">{_flag_img(home, 34)}<span style="font-size:19px;">{home}</span></div>'
        f'<div class="lv-score" style="font-size:34px;">{score}</div>'
        f'<div class="lv-team r"><span style="font-size:19px;">{away}</span>{_flag_img(away, 34)}</div>'
        '</div>' + scorers + '</div>', unsafe_allow_html=True)

    # ---- Stats & events: one tabbed panel (played matches) ----
    if state in ("live", "ft"):
        _render_match_centre(mid, hid, aid, home, away)

        # Player ratings & MOTM — heavier (extra API call), so gated behind a button.
        _section("Player ratings & Man of the Match")
        rk = f"show_rt_{mid}"
        if st.button("Show player ratings", key=f"btn_rt_{mid}"):
            st.session_state[rk] = True
        if st.session_state.get(rk):
            rb = _ratings_block(mid, hid, aid, home, away)
            if rb:
                _card(rb)
            else:
                st.caption("Player ratings not published for this match.")
        else:
            st.caption("Tap to load per-player ratings (rating, goals, assists) and the top performer.")
    else:
        when = dt.strftime("%A %d %B, %H:%M") if dt else "a time to be confirmed"
        st.info(f"This match hasn't kicked off yet — scheduled for {when}. "
                "The model prediction and line-ups are below; the score, stats and "
                "event timeline will appear here once it's under way.")

    # ---- Model prediction (pure compute, no API) ----
    pred = _predict_html(home, away)
    if pred:
        _section("Model prediction" if state == "up" else "Pre-match model prediction")
        _card(pred)

    # ---- Line-ups: formation pitch view + substitutions ----
    lu = {}
    try:
        lu = match_lineups(mid)
    except Exception:
        lu = {}
    pitch = _pitch_html(lu, home, away)
    if pitch:
        _section("Confirmed line-ups" if lu.get("confirmed") else "Predicted line-ups")
        st.markdown(f'<div class="lv-card" style="padding:14px 14px 10px;">{pitch}</div>',
                    unsafe_allow_html=True)
        subs = _subs_html(mid, hid, aid, home, away) if state in ("live", "ft") else None
        if subs:
            _card(f'<div class="sub-h" style="margin-bottom:10px;">Substitutions</div>{subs}')
    else:
        _section("Line-ups")
        st.caption("Line-ups not published yet for this match.")

    # ---- AI match summary — gated (token cost) ----
    _section("AI match summary")
    ak = f"ai_sum_{mid}"
    if st.button("Generate AI summary", key=f"btn_ai_{mid}"):
        facts = [f"{home} vs {away}", f"Status: {state}", f"Score: {home} {hs}–{a_s} {away}"
                 if hs is not None else "Not played yet"]
        try:
            ov2 = wc_match_stats(mid).get("overview", {}) if state in ("live", "ft") else {}
        except Exception:
            ov2 = {}
        for lab, key, _u in MATCH_STAT_ROWS:
            hv, av = stat_val(ov2, key, "home"), stat_val(ov2, key, "away")
            if hv is not None or av is not None:
                facts.append(f"{lab}: {hv} vs {av}")
        try:
            with st.spinner("Writing summary..."):
                st.session_state[ak] = ask_ai(
                    "You are a football reporter. Using ONLY these facts, write a tight 3-4 sentence "
                    "summary of this World Cup match. Don't invent anything not in the data.\n\n"
                    + "\n".join(facts), temperature=0.3)
        except Exception as e:
            st.session_state[ak] = f"Couldn't generate a summary right now. ({e})"
    if st.session_state.get(ak):
        st.info(st.session_state[ak])
    else:
        st.caption("Tap for a short AI-written recap/preview based on this match's data.")


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


def _tiles(pairs):
    """Render a tile grid, skipping any (value, label) whose value is None."""
    cells = "".join(_tile(v, lbl) for v, lbl in pairs if v is not None)
    return f'<div class="tp-grid">{cells}</div>'


def _pct(num, den):
    return round(100 * num / den, 1) if den else None


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

    OV = ["ball_possession", "expected_goals", "total_shots", "shots_on_target", "big_chances",
          "corner_kicks", "fouls", "yellow_cards", "red_cards", "passes", "accurate_passes", "offsides"]
    PL = {"key_passes": ("passing", "key_passes"), "total_crosses": ("passing", "total_crosses"),
          "accurate_crosses": ("passing", "accurate_crosses"),
          "total_long_balls": ("passing", "total_long_balls"),
          "accurate_long_balls": ("passing", "accurate_long_balls"),
          "big_chances_created": ("shooting", "big_chances_created"),
          "expected_assists": ("shooting", "expected_assists"),
          "duel_won": ("duels", "duel_won"), "duel_lost": ("duels", "duel_lost"),
          "aerial_won": ("duels", "aerial_won"), "tackles": ("defending", "tackles"),
          "interceptions": ("defending", "interceptions"), "clearances": ("defending", "clearances"),
          "blocks": ("defending", "blocks")}
    ov = {k: 0.0 for k in OV}; ovp = {k: False for k in OV}
    pl = {k: 0.0 for k in PL}; plp = {k: False for k in PL}
    xga = 0.0; rating_sum = 0.0; minutes = 0
    gp = gf = ga = w = d = l = cs = 0
    matches = []
    for m in finished:
        h, a = m["home_team"], m["away_team"]
        if tid not in (h.get("id"), a.get("id")):
            continue
        hs, as_ = m["score"]["home"], m["score"]["away"]
        if hs is None or as_ is None:
            continue
        is_home = h.get("id") == tid
        side, opp_side = ("home", "away") if is_home else ("away", "home")
        my, conceded = (hs, as_) if is_home else (as_, hs)
        gp += 1; gf += my; ga += conceded
        if conceded == 0:
            cs += 1
        res = "W" if my > conceded else ("D" if my == conceded else "L")
        if res == "W":
            w += 1
        elif res == "D":
            d += 1
        else:
            l += 1
        matches.append({"date": m.get("utc_date", ""),
                        "label": f"{h['name']} {hs}-{as_} {a['name']}", "res": res})
        try:
            o = wc_match_stats(m["id"]).get("overview", {})
        except Exception:
            o = {}
        for k in OV:
            v = stat_val(o, k, side)
            if v is not None:
                ov[k] += v; ovp[k] = True
        xv = stat_val(o, "expected_goals", opp_side)
        if xv is not None:
            xga += xv
        try:
            players = match_player_stats(m["id"])
        except Exception:
            players = []
        for p in players:
            if p.get("team_id") != tid:
                continue
            for fld, (blk, key) in PL.items():
                v = (p.get(blk) or {}).get(key)
                if v is not None:
                    pl[fld] += v; plp[fld] = True
            r, mn = p.get("rating"), p.get("minutes_played") or 0
            try:
                if r is not None:
                    rating_sum += float(r) * mn; minutes += mn
            except (TypeError, ValueError):
                pass

    matches.sort(key=lambda x: x["date"])
    g = max(gp, 1)
    points = w * 3 + d
    avg_poss = f'{round(ov["ball_possession"] / g, 1)}%' if ovp["ball_possession"] else None
    pa = _pct(ov["accurate_passes"], ov["passes"]) if ovp["passes"] else None
    sa = _pct(ov["shots_on_target"], ov["total_shots"]) if ovp["total_shots"] else None
    conv = _pct(gf, ov["total_shots"]) if ovp["total_shots"] else None
    ca = _pct(pl["accurate_crosses"], pl["total_crosses"]) if plp["total_crosses"] else None
    la = _pct(pl["accurate_long_balls"], pl["total_long_balls"]) if plp["total_long_balls"] else None
    dw = _pct(pl["duel_won"], pl["duel_won"] + pl["duel_lost"]) if (plp["duel_won"] or plp["duel_lost"]) else None
    avg_rating = round(rating_sum / minutes, 2) if minutes else None

    grp = pos = None
    for gl in sorted(groups):
        tl = groups[gl]["Team"].tolist()
        if name in tl:
            grp = gl; pos = tl.index(name) + 1; break
    meta = f"Group {grp} · {_ordinal(pos)}" if grp else "Group stage"
    form_html = " ".join(f'<span class="tp-{x["res"].lower()}">{x["res"]}</span>'
                         for x in matches[-5:]) or "—"

    def num(flag, value):
        return value if flag else None

    header = (f'<div class="tp-header">{_flag_img(name, 62)}'
              f'<div><div class="tp-name">{name}</div><div class="tp-meta">{meta}</div></div></div>')
    nav = ('<div class="tp-nav">'
           '<a href="#summary">Summary</a><a href="#attack">Attack</a>'
           '<a href="#passing">Passing</a><a href="#defence">Defence</a>'
           '<a href="#discipline">Discipline</a><a href="#results">Results</a></div>')

    summary = ('<div class="tp-section" id="summary"><div class="tp-h">Summary</div>' + _tiles([
        (gp, "Played"), (f"{w}-{d}-{l}", "W-D-L"), (points, "Points"),
        (round(points / g, 2), "Points/game"), (gf, "Goals for"), (ga, "Goals against"),
        (gf - ga, "Goal diff"), (cs, "Clean sheets"), (avg_rating, "Avg rating"),
        (form_html, "Form (last 5)")]) + '</div>')
    attack = ('<div class="tp-section" id="attack"><div class="tp-h">Attack</div>' + _tiles([
        (gf, "Goals"), (round(gf / g, 2), "Goals/game"),
        (num(ovp["expected_goals"], round(ov["expected_goals"], 1)), "xG"),
        (num(ovp["total_shots"], int(ov["total_shots"])), "Shots"),
        (num(ovp["shots_on_target"], int(ov["shots_on_target"])), "On target"),
        (f"{sa}%" if sa is not None else None, "Shot accuracy"),
        (f"{conv}%" if conv is not None else None, "Conversion"),
        (num(ovp["big_chances"], int(ov["big_chances"])), "Big chances"),
        (num(plp["expected_assists"], round(pl["expected_assists"], 1)), "xA")]) + '</div>')
    passing = ('<div class="tp-section" id="passing"><div class="tp-h">Possession &amp; passing</div>' + _tiles([
        (avg_poss, "Avg possession"), (f"{pa}%" if pa is not None else None, "Pass accuracy"),
        (num(ovp["passes"], round(ov["passes"] / g)), "Passes/game"),
        (num(plp["key_passes"], int(pl["key_passes"])), "Key passes"),
        (f"{ca}%" if ca is not None else None, "Cross accuracy"),
        (f"{la}%" if la is not None else None, "Long-ball accuracy")]) + '</div>')
    defence = ('<div class="tp-section" id="defence"><div class="tp-h">Defence</div>' + _tiles([
        (ga, "Conceded"), (round(ga / g, 2), "Conceded/game"), (cs, "Clean sheets"),
        (round(xga, 1) if xga else None, "xG against"),
        (num(plp["tackles"], int(pl["tackles"])), "Tackles"),
        (num(plp["interceptions"], int(pl["interceptions"])), "Interceptions"),
        (num(plp["clearances"], int(pl["clearances"])), "Clearances"),
        (f"{dw}%" if dw is not None else None, "Duels won"),
        (num(plp["aerial_won"], int(pl["aerial_won"])), "Aerials won")]) + '</div>')
    discipline = ('<div class="tp-section" id="discipline"><div class="tp-h">Discipline &amp; set pieces</div>' + _tiles([
        (num(ovp["fouls"], round(ov["fouls"] / g, 1)), "Fouls/game"),
        (num(ovp["yellow_cards"], int(ov["yellow_cards"])), "Yellow cards"),
        (num(ovp["red_cards"], int(ov["red_cards"])), "Red cards"),
        (num(ovp["offsides"], int(ov["offsides"])), "Offsides"),
        (num(ovp["corner_kicks"], int(ov["corner_kicks"])), "Corners")]) + '</div>')
    res_rows = "".join(
        f'<div class="tp-res"><span>{x["label"]}</span>'
        f'<span class="tp-{x["res"].lower()}">{x["res"]}</span></div>'
        for x in matches) or '<div class="tp-res">No finished matches yet</div>'
    resultsec = f'<div class="tp-section" id="results"><div class="tp-h">Results</div>{res_rows}</div>'

    st.markdown(TEAM_CSS + header + nav + summary + attack + passing + defence + discipline + resultsec,
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


# ===================== Statistical match predictor =====================
# Poisson attack/defence model (Dixon-Coles family). Each team gets an attacking
# and defensive strength relative to the tournament average; expected goals for a
# fixture combine the two. Shrinkage pulls weak-sample teams toward the average —
# essential when teams have played only ~3 games. Backtested on real PL data.
def _pois_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _poisson_outcome(lh, la, mx=10):
    ph = [_pois_pmf(i, lh) for i in range(mx + 1)]
    pa = [_pois_pmf(i, la) for i in range(mx + 1)]
    H = D = Aw = 0.0
    for i in range(mx + 1):
        for j in range(mx + 1):
            p = ph[i] * pa[j]
            if i > j:
                H += p
            elif i == j:
                D += p
            else:
                Aw += p
    return H, D, Aw


def _goal_rates(finished):
    F, A, G, tot, n = {}, {}, {}, 0, 0
    for m in finished:
        hs, as_ = m["score"]["home"], m["score"]["away"]
        if hs is None or as_ is None:
            continue
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        F[h] = F.get(h, 0) + hs; A[h] = A.get(h, 0) + as_
        F[a] = F.get(a, 0) + as_; A[a] = A.get(a, 0) + hs
        G[h] = G.get(h, 0) + 1; G[a] = G.get(a, 0) + 1
        tot += hs + as_; n += 1
    league = tot / (2 * n) if n else 1.3
    return F, A, G, league


def _str_factor(team, sums, G, league, k=5.0):
    g = G.get(team, 0)
    if g == 0 or league <= 0:
        return 1.0
    raw = (sums.get(team, 0) / g) / league
    w = g / (g + k)                      # shrink toward league average for small samples
    return w * raw + (1 - w) * 1.0


def _elo_ratings(finished):
    """Rolling Elo from results (neutral venue). Gives a strength prior beyond a few games."""
    elo = {}
    for m in finished:
        hs, as_ = m["score"]["home"], m["score"]["away"]
        if hs is None or as_ is None:
            continue
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)
        gd = abs(hs - as_)
        mult = math.log(gd + 1) + 1
        sc = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        exp = 1 / (1 + 10 ** (-(eh - ea) / 400))
        chg = 20 * mult * (sc - exp)
        elo[h] = eh + chg
        elo[a] = ea - chg
    return elo


def _elo_probs(d):
    e = 1 / (1 + 10 ** (-d / 400))
    pd_ = 0.30 * math.exp(-((e - 0.5) ** 2) / 0.10)
    pH, pA = max(0.0, e - pd_ / 2), max(0.0, 1 - e - pd_ / 2)
    s = pH + pd_ + pA
    return pH / s, pd_ / s, pA / s


def _xg_rates(name, finished):
    """Aggregate a team's xG for and against from its finished-match stat sheets."""
    xf = xa = g = 0.0
    for m in finished:
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        if name not in (h, a):
            continue
        try:
            ov = wc_match_stats(m["id"]).get("overview", {})
        except Exception:
            continue
        side, opp = ("home", "away") if name == h else ("away", "home")
        xfg, xag = stat_val(ov, "expected_goals", side), stat_val(ov, "expected_goals", opp)
        if xfg is None or xag is None:
            continue
        xf += xfg; xa += xag; g += 1
    return xf, xa, g


def predict_fixture(a, b, finished, k=5.0, pen_a=0.0, pen_b=0.0, elo_w=0.4):
    """Neutral-venue prediction: goals + xG blend + Elo prior + opponent adjustment + injury penalties."""
    F, A, G, league = _goal_rates(finished)
    elo = _elo_ratings(finished)
    att_a = _str_factor(a, F, G, league, k) * (1 - pen_a)
    att_b = _str_factor(b, F, G, league, k) * (1 - pen_b)
    la = max(0.05, league * att_a * _str_factor(b, A, G, league, k))
    lb = max(0.05, league * att_b * _str_factor(a, A, G, league, k))
    # Blend in xG-based strengths — the biggest validated accuracy gain in backtesting.
    xfa, xaa, gxa = _xg_rates(a, finished)
    xfb, xab, gxb = _xg_rates(b, finished)
    if gxa >= 2 and gxb >= 2 and league > 0:
        def xfac(total, g_):
            w = g_ / (g_ + k)
            return w * ((total / g_) / league) + (1 - w)
        la = 0.5 * la + 0.5 * max(0.05, league * xfac(xfa, gxa) * (1 - pen_a) * xfac(xab, gxb))
        lb = 0.5 * lb + 0.5 * max(0.05, league * xfac(xfb, gxb) * (1 - pen_b) * xfac(xaa, gxa))
    sup = (elo.get(a, 1500.0) - elo.get(b, 1500.0)) / 400.0          # opponent-strength adjustment
    la = max(0.05, la * 10 ** (0.10 * sup))
    lb = max(0.05, lb * 10 ** (-0.10 * sup))
    pH, pD, pA = _poisson_outcome(la, lb)
    eH, eD, eA = _elo_probs(elo.get(a, 1500.0) - elo.get(b, 1500.0))
    pAf = elo_w * eH + (1 - elo_w) * pH
    pDf = elo_w * eD + (1 - elo_w) * pD
    pBf = elo_w * eA + (1 - elo_w) * pA
    s = pAf + pDf + pBf
    best, bestp = (0, 0), -1.0
    for i in range(8):
        for j in range(8):
            p = _pois_pmf(i, la) * _pois_pmf(j, lb)
            if p > bestp:
                bestp, best = p, (i, j)
    return {"la": la, "lb": lb, "pA": pAf / s, "pD": pDf / s, "pB": pBf / s, "score": best,
            "eloA": elo.get(a, 1500.0), "eloB": elo.get(b, 1500.0)}


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
               "Round-of-32 projection lives under Group standings.)")
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

    # ---- 4. Statistical match predictor (Poisson attack/defence model) ----
    st.divider()
    st.subheader("📊 Statistical match predictor")
    st.caption("Poisson attack/defence model with shrinkage, plus an Elo rating prior and "
               "opponent-strength adjustment. Backtested on real Premier League data. Use the sliders to "
               "dock a team's attack for key injuries/suspensions.")
    names = sorted({m["home_team"]["name"] for m in finished} |
                   {m["away_team"]["name"] for m in finished})
    if len(names) < 2:
        st.write("Not enough finished matches yet to model team strengths.")
    else:
        pc1, pc2 = st.columns(2)
        ta = pc1.selectbox("Team A", names, key="pred_a")
        tb = pc2.selectbox("Team B", names, index=min(1, len(names) - 1), key="pred_b")
        ia = pc1.slider("Team A injury impact (attack −%)", 0, 40, 0, key="inj_a")
        ib = pc2.slider("Team B injury impact (attack −%)", 0, 40, 0, key="inj_b")
        if st.button("Predict match"):
            if ta == tb:
                st.warning("Pick two different teams.")
            else:
                r = predict_fixture(ta, tb, finished, pen_a=ia / 100, pen_b=ib / 100)
                m1, m2, m3 = st.columns(3)
                m1.metric(f"{ta} win", f"{r['pA'] * 100:.0f}%")
                m2.metric("Draw", f"{r['pD'] * 100:.0f}%")
                m3.metric(f"{tb} win", f"{r['pB'] * 100:.0f}%")
                st.markdown(f"**Expected goals:** {ta} {r['la']:.2f} – {r['lb']:.2f} {tb}  ·  "
                            f"**Most likely score:** {ta} {r['score'][0]}–{r['score'][1]} {tb}")
                st.caption(f"Elo rating: {ta} {r['eloA']:.0f} · {tb} {r['eloB']:.0f}. "
                           "Model output — not betting advice.")


SECTIONS = {
    "standings": ("Group standings", section_standings),
    "scorers": ("Top 10 scorers & assists", section_scorers),
    "bracket": ("Live scores", section_bracket),
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
elif view == "match":
    # A single match's detail page, reached from the Live scores cards
    st.markdown(f"<style>{BASE_CSS}</style>", unsafe_allow_html=True)
    st.markdown('<a class="backlink" href="?view=bracket" target="_self">← Back to live scores</a>',
                unsafe_allow_html=True)
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
    else:
        match_page()
elif view in SECTIONS:
    # A section page: back link (to the menu) + just this section's content
    st.markdown(f"<style>{BASE_CSS}</style>", unsafe_allow_html=True)
    st.markdown('<a class="backlink" href="?view=menu" target="_self">← Back to menu</a>',
                unsafe_allow_html=True)
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
    else:
        title, render_fn = SECTIONS[view]
        if view not in ("stats", "standings"):
            render_banner(title, view)
        render_fn()
else:
    # Home: full-screen hero + the menu of boxes
    render_home(len(finished), n_goals, len(groups))
    if not wc_ok:
        st.warning(f"Couldn't load World Cup data right now: {wc_err}")
