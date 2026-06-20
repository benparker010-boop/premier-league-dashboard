import streamlit as st
import pandas as pd

# Sets the title shown in the browser tab
st.set_page_config(page_title="Premier League Dashboard")

# A big heading at the top of the app
st.title("⚽ Premier League Dashboard")

# Read the CSV file into a pandas DataFrame (think: a table in memory)
df = pd.read_csv("sample_league_data.csv")

# Create a brand-new column from two existing ones: Goal Difference
df["GD"] = df["GF"] - df["GA"]

# Pull out one headline fact: the team in row 0 (top of the table)
champion = df.iloc[0]["Team"]
top_points = int(df.iloc[0]["Pts"])

# Show that fact as a big "metric" box
st.metric(label="Champions", value=champion, delta=f"{top_points} pts")

# Show the whole table
st.subheader("Final Table")
st.dataframe(df)

# Draw a bar chart: one bar per team, height = points
st.subheader("Points by Team")
st.bar_chart(data=df, x="Team", y="Pts")
