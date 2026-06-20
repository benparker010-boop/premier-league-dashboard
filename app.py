import streamlit as st
import pandas as pd
import requests

# --- Page setup ---
st.set_page_config(page_title="Premier League Dashboard")
st.title("⚽ Premier League Dashboard")

# The football-data.org endpoint that returns the Premier League table
API_URL = "https://api.football-data.org/v4/competitions/PL/standings"


# This function asks the API for the live table and reshapes it into a tidy table.
# @st.cache_data tells Streamlit: "remember the result for 10 minutes" so we don't
# call the API on every single click (and stay well under the free rate limit).
@st.cache_data(ttl=600)
def load_live_table(api_key):
    headers = {"X-Auth-Token": api_key}
    response = requests.get(API_URL, headers=headers, timeout=10)
    response.raise_for_status()  # if the API said "no", turn that into an error
    data = response.json()

    # The response contains several tables (total / home / away).
    # We want the one labelled "TOTAL" — the full league table.
    total = next(s for s in data["standings"] if s["type"] == "TOTAL")

    # Walk each row of the API's table and pull out the bits we care about,
    # renaming them to match the column names our app already uses.
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
    api_key = st.secrets["FOOTBALL_API_KEY"]   # read the secret we stored
    df = load_live_table(api_key)
    if df.empty:                               # between seasons the table can be empty
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

# --- Controls (these live in the sidebar on the left) ---
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
