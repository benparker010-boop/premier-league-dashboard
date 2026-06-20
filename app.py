import streamlit as st
import pandas as pd
import requests
import anthropic

# --- Page setup (must be the first Streamlit command) ---
st.set_page_config(page_title="Football Data Dashboard", layout="wide")
st.title("⚽ Football Data Dashboard")

# football-data.org (Premier League)
PL_URL = "https://api.football-data.org/v4/competitions/PL/standings"

# TheStatsAPI (World Cup detailed stats)
STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"

AI_MODEL = "claude-haiku-4-5-20251001"
PREDICT_MODEL = "claude-sonnet-4-6"


# ======================= Premier League data (unchanged) =======================
@st.cache_data(ttl=600)
def load_pl_table():
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_API_KEY"]}
    r = requests.get(PL_URL, headers=headers, timeout=10)
    r.raise_for_status()
    total = next(s for s in r.json()["standings"] if s["type"] == "TOTAL")
    rows = []
    for e in total["table"]:
        rows.append({
            "Team": e["team"]["name"], "Played": e["playedGames"],
            "Won": e["won"], "Drawn": e["draw"], "Lost": e["lost"],
            "GF": e["goalsFor"], "GA": e["goalsAgainst"], "Pts": e["points"],
        })
    return pd.DataFrame(rows)


# ======================= World Cup data (TheStatsAPI) =======================
def stats_headers():
    return {"Authorization": f"Bearer {st.secrets['STATS_API_KEY']}"}


@st.cache_data(ttl=600)
def wc_matches(status):
    r = requests.get(f"{STATS_BASE}/football/matches", headers=stats_headers(),
                     params={"competition_id": WC_COMP, "season_id": WC_SEASON,
                             "status": status, "per_page": 100}, timeout=15)
    r.raise_for_status()
    return r.json().get("data", [])


@st.cache_data(ttl=600)
def wc_match_stats(match_id):
    r = requests.get(f"{STATS_BASE}/football/matches/{match_id}/stats",
                     headers=stats_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("data", {})


def build_group_standings(matches):
    """Compute group tables from finished match results."""
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
        rows = []
        for name, s in teams.items():
            row = dict(s); row["Team"] = name; row["GD"] = s["GF"] - s["GA"]
            rows.append(row)
        df = pd.DataFrame(rows)[["Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]]
        out[g] = df.sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)
    return out


def stat_val(overview, key, side):
    try:
        return overview[key]["all"][side]
    except Exception:
        return None


def overview_to_df(overview, home, away):
    labels = [
        ("Possession %", "ball_possession"), ("Expected goals (xG)", "expected_goals"),
        ("Total shots", "total_shots"), ("Shots on target", "shots_on_target"),
        ("Big chances", "big_chances"), ("Corners", "corner_kicks"),
        ("Fouls", "fouls"), ("Yellow cards", "yellow_cards"),
        ("Red cards", "red_cards"), ("Passes", "passes"),
        ("Accurate passes", "accurate_passes"),
    ]
    rows = []
    for label, key in labels:
        rows.append({"Stat": label, home: stat_val(overview, key, "home"),
                     away: stat_val(overview, key, "away")})
    return pd.DataFrame(rows)


def build_team_stats(finished):
    """Aggregate per-team averages from every finished match's stat sheet."""
    agg = {}
    done, failed = 0, 0
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
            t["poss"] += stat_val(ov, "ball_possession", side) or 0
            t["xg"] += stat_val(ov, "expected_goals", side) or 0
            t["shots"] += stat_val(ov, "total_shots", side) or 0
            t["sot"] += stat_val(ov, "shots_on_target", side) or 0
            t["corners"] += stat_val(ov, "corner_kicks", side) or 0
            t["fouls"] += stat_val(ov, "fouls", side) or 0
            t["yc"] += stat_val(ov, "yellow_cards", side) or 0
            t["big"] += stat_val(ov, "big_chances", side) or 0
    rows = []
    for team, t in agg.items():
        gp = t["GP"] or 1
        rows.append({
            "Team": team, "GP": t["GP"],
            "Avg Poss %": round(t["poss"] / gp, 1),
            "xG/game": round(t["xg"] / gp, 2),
            "Shots/game": round(t["shots"] / gp, 1),
            "SoT/game": round(t["sot"] / gp, 1),
            "Big chances/game": round(t["big"] / gp, 1),
            "Corners/game": round(t["corners"] / gp, 1),
            "Fouls/game": round(t["fouls"] / gp, 1),
            "Yellows/game": round(t["yc"] / gp, 1),
        })
    df = pd.DataFrame(rows).sort_values("xG/game", ascending=False).reset_index(drop=True)
    return df, done, failed


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
    data_source = "live"
    try:
        df = load_pl_table()
        if df.empty:
            raise ValueError("empty")
    except Exception:
        data_source = "sample"
        df = pd.read_csv("sample_league_data.csv")
    df["GD"] = df["GF"] - df["GA"]
    st.caption("🟢 Live data from football-data.org" if data_source == "live"
               else "🟡 Showing sample data (live source unavailable right now)")

    st.sidebar.header("Premier League controls")
    num_teams = st.sidebar.slider("How many teams to show?", 1, 20, 10)
    metric = st.sidebar.selectbox("Chart this stat:", options=["Pts", "GD", "GF"])
    top_teams = df.head(num_teams)
    c1, c2 = st.columns(2)
    c1.metric("Top of the table", df.iloc[0]["Team"], f"{int(df.iloc[0]['Pts'])} pts")
    c2.metric("Goals scored (shown teams)", int(top_teams["GF"].sum()))
    st.subheader(f"Top {num_teams} teams")
    st.dataframe(top_teams, hide_index=True)
    st.subheader(f"{metric} by team")
    st.bar_chart(data=top_teams, x="Team", y=metric)

    st.subheader("🤖 AI Analyst Summary")
    if "pl_summary" not in st.session_state:
        st.session_state.pl_summary = ""
    if st.button("Generate AI Summary", key="pl_ai"):
        try:
            prompt = ("You are a Premier League data analyst. Here is the current table:\n\n"
                      f"{df.to_string(index=False)}\n\nWrite a short, punchy 3-4 sentence "
                      "summary for a dashboard. Plain English, no bullet points.")
            with st.spinner("Asking the AI analyst..."):
                st.session_state.pl_summary = ask_ai(prompt)
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
        groups = build_group_standings(finished)
        total_goals = sum((m["score"]["home"] or 0) + (m["score"]["away"] or 0) for m in finished)
        m1, m2, m3 = st.columns(3)
        m1.metric("Groups", len(groups))
        m2.metric("Matches played", len(finished))
        m3.metric("Goals scored", total_goals)

        # ---- Group standings (computed from results) ----
        st.subheader("Group standings (built from results)")
        gnames = sorted(groups.keys())
        for i in range(0, len(gnames), 2):
            cols = st.columns(2)
            for col, g in zip(cols, gnames[i:i + 2]):
                with col:
                    st.markdown(f"**Group {g}**")
                    st.dataframe(groups[g], hide_index=True)

        # ---- Match stats explorer ----
        st.divider()
        st.subheader("🔍 Match stats explorer")
        st.write("Pick a finished match to see its full stat sheet.")
        labels = {f"{m['home_team']['name']} {m['score']['home']}-{m['score']['away']} "
                  f"{m['away_team']['name']}  ({m['utc_date'][:10]})": m for m in finished}
        if labels:
            choice = st.selectbox("Match:", options=list(labels.keys()))
            m = labels[choice]
            try:
                ov = wc_match_stats(m["id"]).get("overview", {})
                if ov:
                    st.dataframe(overview_to_df(ov, m["home_team"]["name"],
                                                m["away_team"]["name"]), hide_index=True)
                else:
                    st.write("No detailed stats available for this match yet.")
            except Exception as e:
                st.warning(f"Couldn't load that match's stats: {e}")

        # ---- Aggregated team stats ----
        st.divider()
        st.subheader("📊 Team stats (per game, across the tournament)")
        if "wc_team_stats" not in st.session_state:
            st.session_state.wc_team_stats = None
        if st.button("Build team stats from every finished match"):
            with st.spinner("Pulling each match's stat sheet and aggregating..."):
                ts, done, failed = build_team_stats(finished)
                st.session_state.wc_team_stats = ts
                msg = f"Built from {done} matches."
                if failed:
                    msg += f" {failed} couldn't load (rate limit) — click again in a minute to fill them in."
                st.session_state.wc_team_stats_msg = msg
        if st.session_state.wc_team_stats is not None:
            st.caption(st.session_state.get("wc_team_stats_msg", ""))
            st.dataframe(st.session_state.wc_team_stats, hide_index=True)

        # ---- AI analysis & predictions ----
        st.divider()
        st.subheader("🤖 AI Tournament Analysis & Predictions")

        groups_text = ""
        for g in gnames:
            groups_text += f"\nGroup {g} (only these teams): " + \
                ", ".join(groups[g]["Team"].tolist()) + "\n" + \
                groups[g].to_string(index=False) + "\n"

        team_stats_text = ""
        if st.session_state.wc_team_stats is not None:
            team_stats_text = ("\n\nPer-game team stats (real data):\n" +
                               st.session_state.wc_team_stats.to_string(index=False))

        if "wc_analysis" not in st.session_state:
            st.session_state.wc_analysis = ""
        if "wc_prediction" not in st.session_state:
            st.session_state.wc_prediction = ""

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Analyse the tournament", key="wc_analyse"):
                try:
                    prompt = ("You are an expert analyst covering the 2026 World Cup group "
                              "stage (in progress). Group standings:\n" + groups_text +
                              team_stats_text +
                              "\n\nWrite a punchy 4-6 sentence analysis of how it's shaping up: "
                              "standout teams, surprises, tightest groups. Use the stats where "
                              "useful. Plain English, no bullet points.")
                    with st.spinner("Analysing..."):
                        st.session_state.wc_analysis = ask_ai(prompt)
                except Exception as e:
                    st.session_state.wc_analysis = f"Sorry — couldn't analyse. ({e})"
        with b2:
            if st.button("Predict who advances", key="wc_predict"):
                try:
                    prompt = ("You are a football analyst predicting the 2026 World Cup group "
                              "stage (in progress).\n\nSTRICT RULES:\n1. Use ONLY the teams and "
                              "numbers below.\n2. No outside knowledge of reputations.\n3. Every "
                              "team named must appear in the group you assign it to.\n\n"
                              "Group standings:\n" + groups_text + team_stats_text +
                              "\n\nGo through groups in order; for each, name the likely winner "
                              "and runner-up using points, goal difference and the per-game stats "
                              "(xG, shots, possession) where they reveal who is strongest. Then "
                              "name one favourite and one dark horse from the teams above. End by "
                              "noting these are informed predictions, not certainties.")
                    with st.spinner("Predicting (stronger model + real stats)..."):
                        st.session_state.wc_prediction = ask_ai(prompt, model=PREDICT_MODEL,
                                                                temperature=0.2)
                except Exception as e:
                    st.session_state.wc_prediction = f"Sorry — couldn't predict. ({e})"

        if st.session_state.wc_analysis:
            st.info(st.session_state.wc_analysis)
        if st.session_state.wc_prediction:
            st.success(st.session_state.wc_prediction)
            st.caption("⚠️ AI-generated predictions — informed speculation, not betting advice.")
