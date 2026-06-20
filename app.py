import streamlit as st
import pandas as pd
import requests
import anthropic

# --- Page setup ---
st.set_page_config(page_title="Premier League Dashboard")
st.title("⚽ Premier League Dashboard")

# The football-data.org endpoint that returns the Premier League table
API_URL = "https://api.football-data.org/v4/competitions/PL/standings"


# Ask the API for the live table and reshape it into a tidy table.
# @st.cache_data tells Streamlit to remember the result for 10 minutes so we
# don't call the API on every click (and stay under the free rate limit).
@st.cache_data(ttl=600)
def load_live_table(api_key):
    headers = {"X-Auth-Token": api_key}
    response = requests.get(API_URL, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    # The response has several tables (total / home / away); we want "TOTAL".
    total = next(s for s in data["standings"] if s["type"] == "TOTAL")

    rows = []
    for entry in total["table"]:
        rows.append({
            "Team": entry["team"]["name"],
            "Played": entry["playedGames"],
            "Won": entry["won"],
            "Drawn": entry["draw"],
            "Lost": entry["lost"],
            "GF": entry["goalsFor"],
            "GA": entry["goalsAgainst"],
            "Pts": entry["points"],
        })
    return pd.DataFrame(rows)


# --- Get the data: try live first, fall back to the sample CSV if anything fails ---
data_source = "live"
try:
    api_key = st.secrets["FOOTBALL_API_KEY"]
    df = load_live_table(api_key)
    if df.empty:
        raise ValueError("Live table is currently empty.")
except Exception:
    data_source = "sample"
    df = pd.read_csv("sample_league_data.csv")

# Goal Difference — calculated the same way for both live and sample data
df["GD"] = df["GF"] - df["GA"]

# A small honest label so viewers know where the numbers came from
if data_source == "live":
    st.caption("🟢 Live data from football-data.org")
else:
    st.caption("🟡 Showing sample data (live source unavailable right now)")

# --- Controls (sidebar) ---
st.sidebar.header("Controls")
num_teams = st.sidebar.slider("How many teams to show?", 1, 20, 10)
metric = st.sidebar.selectbox("Chart this stat:", options=["Pts", "GD", "GF"])

# --- Use the controls to shape the data ---
top_teams = df.head(num_teams)

# --- Headline numbers ---
leader = df.iloc[0]["Team"]
top_points = int(df.iloc[0]["Pts"])
goals_shown = int(top_teams["GF"].sum())

col1, col2 = st.columns(2)
col1.metric(label="Top of the table", value=leader, delta=f"{top_points} pts")
col2.metric(label="Goals scored (shown teams)", value=goals_shown)

# --- Table ---
st.subheader(f"Top {num_teams} teams")
st.dataframe(top_teams)

# --- Chart ---
st.subheader(f"{metric} by team")
st.bar_chart(data=top_teams, x="Team", y=metric)

# --- AI Analyst Summary ---
st.subheader("🤖 AI Analyst Summary")
st.write("Have an AI model read the current table and explain it in plain English.")

# Streamlit reruns the whole script on every click, so we use session_state as a
# little memory box that keeps the summary on screen even after you move a slider.
if "summary" not in st.session_state:
    st.session_state.summary = ""

if st.button("Generate AI Summary"):
    try:
        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

        # Turn the table into plain text the model can read
        table_text = df.to_string(index=False)

        prompt = (
            "You are a Premier League data analyst. Here is the current table:\n\n"
            f"{table_text}\n\n"
            "Write a short, punchy summary in 3-4 sentences for a dashboard. "
            "Mention who leads, any notable over- or under-performers, and the "
            "relegation picture. Plain English, no bullet points."
        )

        with st.spinner("Asking the AI analyst..."):
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            st.session_state.summary = message.content[0].text
    except Exception as e:
        st.session_state.summary = f"Sorry — couldn't generate a summary right now. ({e})"

if st.session_state.summary:
    st.info(st.session_state.summary)
