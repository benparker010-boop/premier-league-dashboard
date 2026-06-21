import streamlit as st
import pandas as pd
import requests
import anthropic
import time
import os

st.set_page_config(page_title="Football Data Dashboard", layout="wide")
st.title("⚽ Football Data Dashboard")

PL_URL = "https://api.football-data.org/v4/competitions/PL/standings"
STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"
AI_MODEL = "claude-haiku-4-5-20251001"
PREDICT_MODEL = "claude-sonnet-4-6"

# Snapshot files (committed to the repo) so the scorer/assist tables are
# shown instantly on every visit without rebuilding from the API each time.
SCORERS_CSV = "top_scorers.csv"
ASSISTS_CSV = "top_assists.csv"


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


# ============== Deterministic tournament simulator (no AI) ==============
# Each team's strength is a plain tuple read off the current group table:
# (Points, Goal difference, Goals for). The team with the higher tuple wins;
# ties break on alphabetical name so the result is always the same.
ROUND_NAMES = {32: "Round of 32", 16: "Round of 16", 8: "Quarter-finals",
               4: "Semi-finals", 2: "Final"}


def _strength(row):
    return (int(row["Pts"]), int(row["GD"]), int(row["GF"]))


def group_predictions(groups):
    """One row per group: predicted winner and runner-up from current standings."""
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
    """Top 2 of every group + the 8 best third-placed teams = up to 32 teams."""
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
    """Standard knockout seeding so the strongest sides only meet late."""
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
    return a if a["name"] < b["name"] else b   # deterministic tie-break


def render_bracket(rounds, champion):
    """Draw the rounds left-to-right as a visual bracket of match cards."""
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


def simulate_bracket(qualified):
    """Seed the qualified teams by strength and play out every round.
    Returns (rounds, champion) where rounds = list of (name, [match dicts])."""
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


# ----------------- Top scorers & assists (snapshot + live) -----------------
def build_scorers_assists(match_ids):
    """Tally real goals and assists from each finished match's event timeline."""
    goals, assists = {}, {}
    done = failed = 0
    for mid in match_ids:
        try:
            events = wc_timeline(mid)
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


def load_scorer_snapshot():
    """Read the pre-built top-10 tables committed to the repo (instant)."""
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


# ===================== Other helpers (unchanged) =====================
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

        # ---------------- Top scorers & assists (always shown) ----------------
        st.divider()
        st.subheader("🥇 Top 10 scorers & assists")
        gsnap, asnap, stamp = load_scorer_snapshot()
        gdf = st.session_state.get("scorers_live", gsnap)
        adf = st.session_state.get("assisters_live", asnap)
        if "scorers_live" in st.session_state:
            st.caption("🟢 Refreshed live from match events just now.")
        elif stamp:
            st.caption(f"📁 Snapshot from committed data (built {stamp}). "
                       "Press refresh to pull the very latest from live match events.")
        else:
            st.caption("No snapshot found yet — press refresh to build it from live match events.")
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
            with st.spinner("Reading every finished match's goals..."):
                lg, la, done, failed = build_scorers_assists([m["id"] for m in finished])
                st.session_state.scorers_live = lg
                st.session_state.assisters_live = la
            if failed:
                st.warning(f"Built from {done} matches; {failed} hit the rate limit — try again in a minute.")
            st.rerun()

        # ---------------- Group winner predictions (no AI) ----------------
        st.divider()
        st.subheader("🔮 Group winner predictions")
        st.caption("Based purely on the current standings — winner and runner-up of each group.")
        if groups:
            st.dataframe(group_predictions(groups), hide_index=True)
        else:
            st.write("No group results yet.")

        # ---------------- Full knockout bracket simulation (no AI) ----------------
        st.divider()
        st.subheader("🏆 Simulated knockout bracket")
        st.caption("A deterministic simulation: the 32 qualifiers (top 2 of each group + 8 best "
                   "third-placed teams) are seeded by points, goal difference and goals scored, "
                   "then every tie is decided by the stronger record. No AI, no randomness.")
        qualified = qualified_from_groups(groups)
        rounds, champion = simulate_bracket(qualified)
        if not rounds:
            st.info("Not enough completed group games yet to build a 16/32-team bracket. "
                    "The bracket will appear automatically once more results are in.")
        else:
            st.write(f"Seeding **{len(rounds[0][1]) * 2}** qualified teams into the bracket.")
            render_bracket(rounds, champion)
            st.success(f"🏆 Simulated champion: **{champion}**")
            st.caption("⚠️ A mechanical simulation from current form — not a real prediction.")

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

        # ---------------- AI analysis (predictions now handled above) ----------------
        st.divider()
        st.subheader("🤖 AI Tournament Analysis")
        groups_text = ""
        for g in gnames:
            groups_text += f"\nGroup {g} (only these teams): " + \
                ", ".join(groups[g]["Team"].tolist()) + "\n" + groups[g].to_string(index=False) + "\n"
        team_stats_text = ""
        if st.session_state.wc_team_stats is not None:
            tea