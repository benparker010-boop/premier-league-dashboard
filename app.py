import streamlit as st
import pandas as pd
import requests
import anthropic
import time

st.set_page_config(page_title="Football Data Dashboard", layout="wide")
st.title("⚽ Football Data Dashboard")

PL_URL = "https://api.football-data.org/v4/competitions/PL/standings"
STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"
AI_MODEL = "claude-haiku-4-5-20251001"
PREDICT_MODEL = "claude-sonnet-4-6"


# ===================== Premier League (football-data.org) =====================
@st.cache_data(ttl=600)
def load_pl_table():
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_API_KEY"]}
    r = requests.get(PL_URL, headers=headers, timeout=10)
    r.raise_for_status()
    total = next(s for s in r.json()["standings"] if s["type"] == "TOTAL")
    return pd.DataFrame([{
        "Team": e["team"]["name"], "Played": e["playedGames"], "Won": e["won"],
        "Drawn": e["draw"], "Lost": e["lost"], "GF": e["goalsFor"],
        "GA": e["goalsAgainst"], "Pts": e["points"]} for e in total["table"]])


# ===================== World Cup (TheStatsAPI) =====================
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


@st.cache_data(ttl=600)
def wc_timeline(match_id):
    r = stats_get(f"/football/matches/{match_id}/timeline")
    r.raise_for_status()
    return r.json().get("data", {}).get("events", [])


@st.cache_data(ttl=3600)
def search_player(name):
    r = stats_get("/football/players", {"search": name})
    r.raise_for_status()
    return r.json().get("data", [])


@st.cache_data(ttl=600)
def player_wc_stats(player_id):
    r = stats_get(f"/football/players/{player_id}/stats", {"season_id": WC_SEASON})
    if r.status_code == 404:
        return None                      # player has no World Cup stats
    r.raise_for_status()
    return r.json().get("data", {})


def find_wc_player(name):
    """Return the first search result that actually has World Cup stats."""
    for p in search_player(name)[:3]:
        s = player_wc_stats(p["id"])
        if s:
            return p, s
    return None, None


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


def build_scorers_assists(finished):
    """Tally real goals and assists from every finished match's event timeline."""
    goals, assists = {}, {}
    done = failed = 0
    for m in finished:
        try:
            events = wc_timeline(m["id"])
        except Exception:
            failed += 1
            continue
        done += 1
        for ev in events:
            if ev.get("type") != "goal":
                continue
            scorer = ev.get("player") or {}
            team = (ev.get("team") or {}).get("name", "")
            if scorer.get("name"):
                g = goals.setdefault(scorer["name"],
                                     {"Player": scorer["name"], "Team": team, "Goals": 0})
                g["Goals"] += 1
            # assist may be labelled under one of a few possible keys
            a = (ev.get("assist") or ev.get("assist_player") or
                 ev.get("assisted_by") or ev.get("secondary_player"))
            if isinstance(a, dict) and a.get("name"):
                ad = assists.setdefault(a["name"],
                                        {"Player": a["name"], "Team": team, "Assists": 0})
                ad["Assists"] += 1
    gdf = pd.DataFrame(list(goals.values()))
    adf = pd.DataFrame(list(assists.values()))
    if not gdf.empty:
        gdf = gdf.sort_values("Goals", ascending=False).head(10).reset_index(drop=True)
    if not adf.empty:
        adf = adf.sort_values("Assists", ascending=False).head(10).reset_index(drop=True)
    return gdf, adf, done, failed


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


# ----------------------------------------------------------------------
tab_pl, tab_wc = st.tabs(["🏴 Premier League", "🌍 World Cup 2026"])

# ============================ PREMIER LEAGUE ===========================
with tab_pl:
    st.header("Premier League")
    source = "live"
    try:
        df = load_pl_table()
        if df.empty:
            raise ValueError("empty")
    except Exception:
        source = "sample"
        df = pd.read_csv("sample_league_data.csv")
    df["GD"] = df["GF"] - df["GA"]
    st.caption("🟢 Live data from football-data.org" if source == "live"
               else "🟡 Showing sample data (live source unavailable right now)")
    st.sidebar.header("Premier League controls")
    n = st.sidebar.slider("How many teams to show?", 1, 20, 10)
    metric = st.sidebar.selectbox("Chart this stat:", ["Pts", "GD", "GF"])
    top = df.head(n)
    c1, c2 = st.columns(2)
    c1.metric("Top of the table", df.iloc[0]["Team"], f"{int(df.iloc[0]['Pts'])} pts")
    c2.metric("Goals scored (shown teams)", int(top["GF"].sum()))
    st.subheader(f"Top {n} teams")
    st.dataframe(top, hide_index=True)
    st.subheader(f"{metric} by team")
    st.bar_chart(data=top, x="Team", y=metric)
    st.subheader("🤖 AI Analyst Summary")
    if "pl_summary" not in st.session_state:
        st.session_state.pl_summary = ""
    if st.button("Generate AI Summary", key="pl_ai"):
        try:
            with st.spinner("Asking the AI analyst..."):
                st.session_state.pl_summary = ask_ai(
                    "You are a Premier League analyst. Current table:\n\n"
                    f"{df.to_string(index=False)}\n\nWrite a punchy 3-4 sentence summary. "
                    "Plain English, no bullet points.")
        except Exception as e:
            st.session_state.pl_summary = f"Sorry — couldn't generate a summary. ({e})"
    if st.session_state.pl_summary:
        st.info(st.session_state.pl_summary)

# ============================== WORLD CUP ==============================
with tab_wc:
    st.header("🌍 World Cup 2026")
    st.caption("🟢 Live detailed data from TheStatsAPI")
    try:
        finished = wc_matches("finished")
        upcoming = wc_matches("scheduled")
        wc_ok = True
    except Exception as e:
        wc_ok = False
        st.warning(f"Couldn't load World Cup data right now: {e}")

    if wc_ok:
        team_names = build_team_name_map(finished, upcoming)
        groups = build_group_standings(finished)
        goals = sum((m["score"]["home"] or 0) + (m["score"]["away"] or 0) for m in finished)
        m1, m2, m3 = st.columns(3)
        m1.metric("Groups", len(groups)); m2.metric("Matches played", len(finished))
        m3.metric("Goals scored", goals)

        st.subheader("Group standings (built from results)")
        gnames = sorted(groups.keys())
        for i in range(0, len(gnames), 2):
            cols = st.columns(2)
            for col, g in zip(cols, gnames[i:i + 2]):
                with col:
                    st.markdown(f"**Group {g}**")
                    st.dataframe(groups[g], hide_index=True)

        st.divider()
        st.subheader("🔍 Match stats explorer")
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

        st.divider()
        st.subheader("📊 Team stats (per game)")
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

        # ---------------- Player search & profile ----------------
        st.divider()
        st.subheader("👤 Player search & profile")
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

        # ---------------- Top scorers & assists (from match events) ----------------
        st.divider()
        st.subheader("🥇 Top 10 scorers & assists")
        st.caption("Tallied from real goal events across every finished match.")
        if "scorers" not in st.session_state:
            st.session_state.scorers = None
        if st.button("Build top scorers & assists"):
            with st.spinner("Reading every match's goals..."):
                gdf, adf, done, failed = build_scorers_assists(finished)
                st.session_state.scorers = gdf
                st.session_state.assisters = adf
                st.session_state.scorers_msg = f"Built from {done} matches." + (
                    " Some hit the rate limit — click again in a minute." if failed else "")
        if st.session_state.scorers is not None:
            st.caption(st.session_state.get("scorers_msg", ""))
            gcol, acol = st.columns(2)
            with gcol:
                st.markdown("**Top scorers**")
                if st.session_state.scorers.empty:
                    st.write("No goals tallied yet.")
                else:
                    st.dataframe(st.session_state.scorers, hide_index=True)
            with acol:
                st.markdown("**Top assists**")
                adf = st.session_state.get("assisters")
                if adf is None or adf.empty:
                    st.write("No assist data found in the events feed.")
                else:
                    st.dataframe(adf, hide_index=True)

        # ---------------- AI analysis & predictions ----------------
        st.divider()
        st.subheader("🤖 AI Tournament Analysis & Predictions")
        groups_text = ""
        for g in gnames:
            groups_text += f"\nGroup {g} (only these teams): " + \
                ", ".join(groups[g]["Team"].tolist()) + "\n" + groups[g].to_string(index=False) + "\n"
        team_stats_text = ""
        if st.session_state.wc_team_stats is not None:
            team_stats_text = "\n\nPer-game team stats:\n" + \
                st.session_state.wc_team_stats.to_string(index=False)
        if "wc_analysis" not in st.session_state:
            st.session_state.wc_analysis = ""
        if "wc_prediction" not in st.session_state:
            st.session_state.wc_prediction = ""
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Analyse the tournament", key="wc_analyse"):
                try:
                    with st.spinner("Analysing..."):
                        st.session_state.wc_analysis = ask_ai(
                            "You are an expert analyst covering the 2026 World Cup group stage "
                            "(in progress). Standings:\n" + groups_text + team_stats_text +
                            "\n\nWrite a punchy 4-6 sentence analysis. Use the stats where useful. "
                            "Plain English, no bullet points.")
                except Exception as e:
                    st.session_state.wc_analysis = f"Sorry — couldn't analyse. ({e})"
        with b2:
            if st.button("Predict who advances", key="wc_predict"):
                try:
                    with st.spinner("Predicting (stronger model + real stats)..."):
                        st.session_state.wc_prediction = ask_ai(
                            "You are predicting the 2026 World Cup group stage (in progress).\n\n"
                            "RULES: use ONLY the teams and numbers below; no outside knowledge; "
                            "every team named must be in the group you assign it to.\n\n"
                            "Standings:\n" + groups_text + team_stats_text +
                            "\n\nGo group by group; name a likely winner and runner-up using points, "
                            "goal difference and the per-game stats. Then give one favourite and one "
                            "dark horse from the teams above. End: these are informed predictions, "
                            "not certainties.", model=PREDICT_MODEL, temperature=0.2)
                except Exception as e:
                    st.session_state.wc_prediction = f"Sorry — couldn't predict. ({e})"
        if st.session_state.wc_analysis:
            st.info(st.session_state.wc_analysis)
        if st.session_state.wc_prediction:
            st.success(st.session_state.wc_prediction)
            st.caption("⚠️ AI-generated predictions — informed speculation, not betting advice.")
