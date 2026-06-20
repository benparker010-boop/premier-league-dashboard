import streamlit as st
import pandas as pd
import requests
import anthropic

# --- Page setup (must be the first Streamlit command) ---
st.set_page_config(page_title="Football Data Dashboard", layout="wide")
st.title("⚽ Football Data Dashboard")

PL_URL = "https://api.football-data.org/v4/competitions/PL/standings"
WC_STANDINGS_URL = "https://api.football-data.org/v4/competitions/WC/standings"
WC_MATCHES_URL = "https://api.football-data.org/v4/competitions/WC/matches"


# ----------------------------------------------------------------------
# Data-loading functions. Each is cached for 10 minutes so we don't spam
# the API on every click (and stay under the free 10-requests-per-minute cap).
# ----------------------------------------------------------------------

@st.cache_data(ttl=600)
def load_pl_table(api_key):
    headers = {"X-Auth-Token": api_key}
    r = requests.get(PL_URL, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    total = next(s for s in data["standings"] if s["type"] == "TOTAL")
    rows = []
    for e in total["table"]:
        rows.append({
            "Team": e["team"]["name"], "Played": e["playedGames"],
            "Won": e["won"], "Drawn": e["draw"], "Lost": e["lost"],
            "GF": e["goalsFor"], "GA": e["goalsAgainst"], "Pts": e["points"],
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def load_wc_groups(api_key):
    headers = {"X-Auth-Token": api_key}
    r = requests.get(WC_STANDINGS_URL, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    # A group tournament returns one "TOTAL" table per group.
    groups = {}
    for s in data["standings"]:
        if s["type"] != "TOTAL":
            continue
        group_name = s.get("group") or "Table"
        rows = []
        for e in s["table"]:
            rows.append({
                "Team": e["team"]["name"], "P": e["playedGames"],
                "W": e["won"], "D": e["draw"], "L": e["lost"],
                "GF": e["goalsFor"], "GA": e["goalsAgainst"],
                "GD": e["goalDifference"], "Pts": e["points"],
            })
        groups[group_name] = pd.DataFrame(rows)
    return groups


@st.cache_data(ttl=600)
def load_wc_matches(api_key):
    headers = {"X-Auth-Token": api_key}
    r = requests.get(WC_MATCHES_URL, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    results, upcoming = [], []
    total_goals = 0
    for m in data["matches"]:
        home = (m["homeTeam"] or {}).get("name") or "TBD"
        away = (m["awayTeam"] or {}).get("name") or "TBD"
        date = m["utcDate"][:10]
        if m["status"] == "FINISHED":
            hs = m["score"]["fullTime"]["home"]
            a_s = m["score"]["fullTime"]["away"]
            if hs is not None and a_s is not None:
                total_goals += hs + a_s
            results.append({"Date": date, "Result": f"{home} {hs}-{a_s} {away}"})
        elif m["status"] in ("SCHEDULED", "TIMED"):
            upcoming.append({"Date": date, "Fixture": f"{home} vs {away}"})
    results_df = pd.DataFrame(results)
    upcoming_df = pd.DataFrame(upcoming)
    stats = {"played": len(results), "goals": total_goals, "upcoming": len(upcoming)}
    return results_df, upcoming_df, stats


# ----------------------------------------------------------------------
# Two tabs: the original Premier League dashboard, and the new World Cup one
# ----------------------------------------------------------------------
tab_pl, tab_wc = st.tabs(["🏴 Premier League", "🌍 World Cup 2026"])


# ============================ PREMIER LEAGUE ===========================
with tab_pl:
    st.header("Premier League")

    data_source = "live"
    try:
        api_key = st.secrets["FOOTBALL_API_KEY"]
        df = load_pl_table(api_key)
        if df.empty:
            raise ValueError("empty")
    except Exception:
        data_source = "sample"
        df = pd.read_csv("sample_league_data.csv")

    df["GD"] = df["GF"] - df["GA"]

    if data_source == "live":
        st.caption("🟢 Live data from football-data.org")
    else:
        st.caption("🟡 Showing sample data (live source unavailable right now)")

    st.sidebar.header("Premier League controls")
    num_teams = st.sidebar.slider("How many teams to show?", 1, 20, 10)
    metric = st.sidebar.selectbox("Chart this stat:", options=["Pts", "GD", "GF"])
    top_teams = df.head(num_teams)

    leader = df.iloc[0]["Team"]
    top_points = int(df.iloc[0]["Pts"])
    goals_shown = int(top_teams["GF"].sum())
    c1, c2 = st.columns(2)
    c1.metric(label="Top of the table", value=leader, delta=f"{top_points} pts")
    c2.metric(label="Goals scored (shown teams)", value=goals_shown)

    st.subheader(f"Top {num_teams} teams")
    st.dataframe(top_teams, hide_index=True)

    st.subheader(f"{metric} by team")
    st.bar_chart(data=top_teams, x="Team", y=metric)

    st.subheader("🤖 AI Analyst Summary")
    if "pl_summary" not in st.session_state:
        st.session_state.pl_summary = ""
    if st.button("Generate AI Summary", key="pl_ai"):
        try:
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
            prompt = (
                "You are a Premier League data analyst. Here is the current table:\n\n"
                f"{df.to_string(index=False)}\n\n"
                "Write a short, punchy 3-4 sentence summary for a dashboard. "
                "Mention who leads, notable over/under-performers, and the relegation "
                "picture. Plain English, no bullet points."
            )
            with st.spinner("Asking the AI analyst..."):
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001", max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                st.session_state.pl_summary = msg.content[0].text
        except Exception as e:
            st.session_state.pl_summary = f"Sorry — couldn't generate a summary. ({e})"
    if st.session_state.pl_summary:
        st.info(st.session_state.pl_summary)


# ============================== WORLD CUP ==============================
with tab_wc:
    st.header("🌍 World Cup 2026")

    try:
        api_key = st.secrets["FOOTBALL_API_KEY"]
        groups = load_wc_groups(api_key)
        results_df, upcoming_df, stats = load_wc_matches(api_key)
        wc_ok = True
    except Exception as e:
        wc_ok = False
        st.warning(f"Couldn't load World Cup data right now: {e}")

    if wc_ok:
        # Headline tournament numbers
        m1, m2, m3 = st.columns(3)
        m1.metric("Groups", len(groups))
        m2.metric("Matches played", stats["played"])
        m3.metric("Goals scored", stats["goals"])

        # All group tables, laid out two per row
        st.subheader("Group standings (live)")
        group_names = sorted(groups.keys())
        for i in range(0, len(group_names), 2):
            cols = st.columns(2)
            for col, gname in zip(cols, group_names[i:i + 2]):
                with col:
                    st.markdown(f"**{gname.replace('_', ' ').title()}**")
                    st.dataframe(groups[gname], hide_index=True)

        # Results and fixtures side by side
        left, right = st.columns(2)
        with left:
            st.subheader("Recent results")
            if not results_df.empty:
                st.dataframe(results_df.tail(12), hide_index=True)
            else:
                st.write("No finished matches yet.")
        with right:
            st.subheader("Upcoming fixtures")
            if not upcoming_df.empty:
                st.dataframe(upcoming_df.head(12), hide_index=True)
            else:
                st.write("No upcoming fixtures listed.")
