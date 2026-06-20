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

# We use Haiku 4.5 (cheap + fast). For deeper, pricier analysis you could later
# swap the model string below to "claude-sonnet-4-6".
AI_MODEL = "claude-haiku-4-5-20251001"


# ----------------------------------------------------------------------
# Data-loading functions, each cached for 10 minutes to respect the
# free API's 10-requests-per-minute limit.
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
    stats = {"played": len(results), "goals": total_goals, "upcoming": len(upcoming)}
    return pd.DataFrame(results), pd.DataFrame(upcoming), stats


def ask_ai(prompt):
    """Send a prompt to Claude and return the text reply."""
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=AI_MODEL, max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def groups_to_text(groups):
    """Turn all the group tables into one block of text for the AI to read."""
    text = ""
    for gname in sorted(groups.keys()):
        text += f"\n{gname.replace('_', ' ').title()}:\n"
        text += groups[gname].to_string(index=False) + "\n"
    return text


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
    st.caption("🟢 Live data from football-data.org" if data_source == "live"
               else "🟡 Showing sample data (live source unavailable right now)")

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
            prompt = (
                "You are a Premier League data analyst. Here is the current table:\n\n"
                f"{df.to_string(index=False)}\n\n"
                "Write a short, punchy 3-4 sentence summary for a dashboard. "
                "Mention who leads, notable over/under-performers, and the relegation "
                "picture. Plain English, no bullet points."
            )
            with st.spinner("Asking the AI analyst..."):
                st.session_state.pl_summary = ask_ai(prompt)
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
        m1, m2, m3 = st.columns(3)
        m1.metric("Groups", len(groups))
        m2.metric("Matches played", stats["played"])
        m3.metric("Goals scored", stats["goals"])

        st.subheader("Group standings (live)")
        group_names = sorted(groups.keys())
        for i in range(0, len(group_names), 2):
            cols = st.columns(2)
            for col, gname in zip(cols, group_names[i:i + 2]):
                with col:
                    st.markdown(f"**{gname.replace('_', ' ').title()}**")
                    st.dataframe(groups[gname], hide_index=True)

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

        # ---------------- AI features for the World Cup ----------------
        st.divider()
        st.subheader("🤖 AI Tournament Analysis & Predictions")

        groups_text = groups_to_text(groups)
        recent_text = results_df.tail(20).to_string(index=False) if not results_df.empty else "None yet."
        upcoming_text = upcoming_df.head(20).to_string(index=False) if not upcoming_df.empty else "None listed."

        if "wc_analysis" not in st.session_state:
            st.session_state.wc_analysis = ""
        if "wc_prediction" not in st.session_state:
            st.session_state.wc_prediction = ""

        b1, b2 = st.columns(2)

        with b1:
            if st.button("Analyse the tournament", key="wc_analyse"):
                try:
                    prompt = (
                        "You are an expert football analyst covering the 2026 World Cup "
                        "(48 teams, 12 groups, group stage in progress). "
                        "Current group standings:\n" + groups_text +
                        "\n\nRecent results:\n" + recent_text +
                        "\n\nWrite a punchy 4-6 sentence analysis of how the tournament is "
                        "shaping up: standout teams, surprises, and which groups look "
                        "tightest. Plain English, no bullet points."
                    )
                    with st.spinner("Analysing..."):
                        st.session_state.wc_analysis = ask_ai(prompt)
                except Exception as e:
                    st.session_state.wc_analysis = f"Sorry — couldn't analyse right now. ({e})"

        with b2:
            if st.button("Predict who advances", key="wc_predict"):
                try:
                    prompt = (
                        "You are a football analyst making informed predictions for the "
                        "2026 World Cup group stage (still in progress). "
                        "Current standings:\n" + groups_text +
                        "\n\nUpcoming fixtures:\n" + upcoming_text +
                        "\n\nBased on form and current standings, predict which teams look "
                        "most likely to top their groups and advance, then name one overall "
                        "tournament favourite and one dark horse. Be concise (5-7 sentences). "
                        "Make clear these are informed predictions, not certainties."
                    )
                    with st.spinner("Predicting..."):
                        st.session_state.wc_prediction = ask_ai(prompt)
                except Exception as e:
                    st.session_state.wc_prediction = f"Sorry — couldn't predict right now. ({e})"

        if st.session_state.wc_analysis:
            st.info(st.session_state.wc_analysis)
        if st.session_state.wc_prediction:
            st.success(st.session_state.wc_prediction)
            st.caption("⚠️ AI-generated predictions — informed speculation for fun, not betting advice.")
