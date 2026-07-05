"""
build_data.py — generate the PARKER front end's real data files.

Pulls live 2026 World Cup data from TheStatsAPI and runs our own model
(core/predict.py) to produce champion odds, bracket win probabilities and
projected scorelines. Writes plain JSON (public football data — no secrets)
into web/public/data/, which the React app fetches at runtime.

    STATS_API_KEY=... python web/scripts/build_data.py

The key is read from the STATS_API_KEY env var, or (for local dev) from
.streamlit/secrets.toml. It is NEVER written into the output or committed.
Raw API responses are cached under web/scripts/.cache/ so re-runs are fast.
"""
import os
import sys
import json
import time
import hashlib
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research"))

from core.predict import build_model, predict  # noqa: E402

STATS_BASE = "https://api.thestatsapi.com/api"
WC_COMP = "comp_6107"
WC_SEASON = "sn_118868"
OUT_DIR = os.path.join(ROOT, "web", "public", "data")
CACHE_DIR = os.path.join(ROOT, "web", "scripts", ".cache")
N_SIMS = 20000
LAB_MATCHES = 12  # number of recent finished matches to build full Match Lab detail for


def load_key():
    key = os.environ.get("STATS_API_KEY")
    if key:
        return key
    secrets = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets):
        try:
            import tomllib
            with open(secrets, "rb") as fh:
                return tomllib.load(fh).get("STATS_API_KEY")
        except Exception:
            pass
    raise SystemExit("STATS_API_KEY not set (env or .streamlit/secrets.toml)")


KEY = load_key()
HEADERS = {"Authorization": f"Bearer {KEY}"}


# ---------------------------------------------------------------- team lookup
# FIFA 3-letter codes for the 48 teams in this tournament.
CODES = {
    "Algeria": "ALG", "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Belgium": "BEL", "Bosnia & Herzegovina": "BIH", "Brazil": "BRA", "Canada": "CAN",
    "Cape Verde": "CPV", "Colombia": "COL", "Croatia": "CRO", "Curaçao": "CUW",
    "Czechia": "CZE", "Côte d'Ivoire": "CIV", "DR Congo": "COD", "Ecuador": "ECU",
    "Egypt": "EGY", "England": "ENG", "France": "FRA", "Germany": "GER", "Ghana": "GHA",
    "Haiti": "HAI", "Iran": "IRN", "Iraq": "IRQ", "Japan": "JPN", "Jordan": "JOR",
    "Mexico": "MEX", "Morocco": "MAR", "Netherlands": "NED", "New Zealand": "NZL",
    "Norway": "NOR", "Panama": "PAN", "Paraguay": "PAR", "Portugal": "POR",
    "Qatar": "QAT", "Saudi Arabia": "KSA", "Scotland": "SCO", "Senegal": "SEN",
    "South Africa": "RSA", "South Korea": "KOR", "Spain": "ESP", "Sweden": "SWE",
    "Switzerland": "SUI", "Tunisia": "TUN", "Türkiye": "TUR", "USA": "USA",
    "Uruguay": "URU", "Uzbekistan": "UZB",
}
# Secondary accent palette (spec) rotated across teams for a stable colour each.
PALETTE = ["#5b8cff", "#5ec8e0", "#e8475e", "#f5c451", "#ef7d52", "#1faf6b",
           "#2ecc71", "#c3cfdc", "#9d5fb5"]
_color_cache = {}


def code_of(name):
    if name in CODES:
        return CODES[name]
    # placeholder (W95/L101) or unknown — derive
    clean = "".join(c for c in name.upper() if c.isalnum())
    return clean[:3] if clean else "???"


def color_of(name):
    if name not in _color_cache:
        idx = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % len(PALETTE)
        _color_cache[name] = PALETTE[idx]
    return _color_cache[name]


def is_placeholder(name):
    return bool(name) and (name[0] in "WL") and name[1:].isdigit()


# ---------------------------------------------------------------- cached HTTP
def _cache_path(path):
    h = hashlib.md5(path.encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE_DIR, h + ".json")


def api(path, params=None, cache=True, retries=4):
    key = path + ("?" + json.dumps(params, sort_keys=True) if params else "")
    cp = _cache_path(key)
    if cache and os.path.exists(cp):
        with open(cp, encoding="utf-8") as fh:
            return json.load(fh)
    last = None
    for i in range(retries):
        last = requests.get(STATS_BASE + path, headers=HEADERS, params=params, timeout=20)
        if last.status_code == 429:
            wait = int(last.headers.get("Retry-After", 3 + i * 3))
            time.sleep(min(wait, 10))
            continue
        break
    if last.status_code == 404:
        data = {}
    else:
        last.raise_for_status()
        data = last.json().get("data", [])
    if cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    return data


def matches(status):
    return api("/football/matches", {"competition_id": WC_COMP, "season_id": WC_SEASON,
                                     "status": status, "per_page": 100})


def match_detail(mid):
    d = api(f"/football/matches/{mid}")
    return d if isinstance(d, dict) else {}


def venue_of(mid):
    d = match_detail(mid)
    v = d.get("venue") or {}
    ref = d.get("referee") or {}
    return {"venue": v.get("name") or "—", "city": v.get("city") or "",
            "ref": (ref.get("name") if isinstance(ref, dict) else ref) or "—"}


# ---------------------------------------------------------------- date helpers
def parse_dt(m):
    s = m.get("utc_date") or m.get("datetime") or m.get("date")
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def fmt_date(dt):
    return f"{dt.day} {dt.strftime('%b %Y')}" if dt else "—"


def fmt_daydate(dt):
    return f"{dt.strftime('%a')}, {dt.strftime('%b')} {dt.day}" if dt else "—"


def fmt_time(dt):
    if not dt:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%H:%M UTC")


# ---------------------------------------------------------------- model
print("Training model on cached WC results…")
MODEL = build_model()
KNOWN = set(MODEL.G)
_pred_cache = {}


def matchup(home, away):
    """Model win probabilities + most likely scoreline for a neutral fixture."""
    ckey = (home, away)
    if ckey in _pred_cache:
        return _pred_cache[ckey]
    try:
        p = predict(home, away, model=MODEL)
    except Exception:
        p = {"available": False}
    if not p.get("available"):
        out = {"pHome": 0.5, "pAway": 0.5, "score": [1, 1]}
    else:
        ph = p["result"]["home_win"] + p["result"]["draw"] / 2
        pa = p["result"]["away_win"] + p["result"]["draw"] / 2
        tot = ph + pa or 1
        # Scoreline consistent with the pick: most likely score in which the
        # favoured side wins (the unconditional mode is ~always 1-1 in football,
        # which contradicts a card that names a predicted winner).
        fav_home = ph >= pa
        win_score = p.get("scoreline_home_win") if fav_home else p.get("scoreline_away_win")
        out = {"pHome": ph / tot, "pAway": pa / tot,
               "score": win_score or p.get("scoreline") or [1, 1]}
    _pred_cache[ckey] = out
    return out


def team_obj(name):
    return {"code": code_of(name), "name": name, "color": color_of(name)}


# ================================================================= build
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    fin = matches("finished")
    sched = matches("scheduled")
    print(f"Fetched {len(fin)} finished, {len(sched)} scheduled matches.")
    all_matches = fin + sched

    groups_json = build_groups(fin)
    fixtures_json = build_fixtures(all_matches)
    predictions_json = build_predictions(fin, sched)
    players_json = build_players(fin)
    lab_json = build_match_lab(fin)

    for fname, payload in [
        ("groups.json", groups_json),
        ("fixtures.json", fixtures_json),
        ("predictions.json", predictions_json),
        ("players.json", players_json),
        ("matches.json", lab_json),
    ]:
        with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        print(f"  wrote {fname}")
    print("Done.")


# ---------------------------------------------------------------- groups
def build_groups(fin):
    groups = {}
    for m in fin:
        g = m.get("group_label")
        if not g:
            continue
        hs, a_s = m["score"].get("home"), m["score"].get("away")
        if hs is None or a_s is None:
            continue
        home, away = m["home_team"]["name"], m["away_team"]["name"]
        gd = groups.setdefault(g, {})
        for t in (home, away):
            gd.setdefault(t, {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0})
        gd[home]["p"] += 1; gd[away]["p"] += 1
        gd[home]["gf"] += hs; gd[home]["ga"] += a_s
        gd[away]["gf"] += a_s; gd[away]["ga"] += hs
        if hs > a_s:
            gd[home]["w"] += 1; gd[home]["pts"] += 3; gd[away]["l"] += 1
        elif a_s > hs:
            gd[away]["w"] += 1; gd[away]["pts"] += 3; gd[home]["l"] += 1
        else:
            gd[home]["d"] += 1; gd[away]["d"] += 1
            gd[home]["pts"] += 1; gd[away]["pts"] += 1
    out = []
    for g in sorted(groups):
        rows = []
        for name, s in groups[g].items():
            rows.append(dict(s, name=name, gd=s["gf"] - s["ga"]))
        rows.sort(key=lambda r: (r["pts"], r["gd"], r["gf"]), reverse=True)
        teams = []
        for i, r in enumerate(rows):
            teams.append({
                "code": code_of(r["name"]), "color": color_of(r["name"]), "name": r["name"],
                "p": r["p"], "w": r["w"], "d": r["d"], "l": r["l"],
                "gd": r["gd"], "pts": r["pts"],
                "qual": "q1" if i == 0 else "q2" if i == 1 else "x",
            })
        out.append({"name": g, "teams": teams})
    return out


# ---------------------------------------------------------------- fixtures
ROUND_LABEL = {"round_of_32": "ROUND OF 32", "round_of_16": "ROUND OF 16",
               "quarter_final": "QUARTER-FINAL", "semi_final": "SEMI-FINAL", "final": "FINAL"}


def round_label(m):
    g = m.get("group_label")
    if g:
        return f"GROUP {g}"
    return ROUND_LABEL.get(m.get("stage_name"), "KNOCKOUT")


def build_fixtures(all_matches):
    rows = []
    for m in all_matches:
        if is_placeholder(m["home_team"]["name"]) or is_placeholder(m["away_team"]["name"]):
            continue
        dt = parse_dt(m)
        done = m.get("status") == "finished"
        sc = m["score"]
        rows.append({
            "round": round_label(m),
            "date": fmt_date(dt),
            "ts": dt.timestamp() if dt else 0,
            "hCode": code_of(m["home_team"]["name"]), "hCol": color_of(m["home_team"]["name"]),
            "aCode": code_of(m["away_team"]["name"]), "aCol": color_of(m["away_team"]["name"]),
            "sh": sc.get("home") if done else None,
            "sa": sc.get("away") if done else None,
            "status": "done" if done else "upcoming",
            "matchId": m["id"],
            "group": bool(m.get("group_label")),
        })
    rows.sort(key=lambda r: r["ts"])
    return rows


# ---------------------------------------------------------------- predictions
def build_predictions(fin, sched):
    r16 = [m for m in (fin + sched) if m.get("stage_name") == "round_of_16"]
    r16.sort(key=lambda m: (parse_dt(m).timestamp() if parse_dt(m) else 0, m["id"]))

    def advancing(m):
        """The team that goes through: real winner if played, else model favourite."""
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        if m.get("status") == "finished":
            w = m["score"].get("winner")
            return h if w == "home" else a
        mu = matchup(h, a)
        return h if mu["pHome"] >= mu["pAway"] else a

    # ---- R16 cards ----
    r16_cards = []
    for m in r16:
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        done = m.get("status") == "finished"
        mu = matchup(h, a)
        fav_home = mu["pHome"] >= mu["pAway"]
        r16_cards.append({
            "home": team_obj(h), "away": team_obj(a),
            "done": done,
            "sh": m["score"].get("home") if done else None,
            "sa": m["score"].get("away") if done else None,
            "winner": ("home" if m["score"].get("winner") == "home" else "away") if done else None,
            "favHome": fav_home,
            "prob": round((mu["pHome"] if fav_home else mu["pAway"]) * 100),
            "projScore": mu["score"],
            "tier": "result" if done else "confirmed",
        })

    # ---- projected QF / SF / F over the R16 winners (Parker's path) ----
    def project_round(entrants):
        cards, winners = [], []
        for i in range(0, len(entrants), 2):
            h, a = entrants[i], entrants[i + 1]
            mu = matchup(h, a)
            fav_home = mu["pHome"] >= mu["pAway"]
            cards.append({
                "home": team_obj(h), "away": team_obj(a), "done": False,
                "sh": None, "sa": None, "winner": None, "favHome": fav_home,
                "prob": round((mu["pHome"] if fav_home else mu["pAway"]) * 100),
                "projScore": mu["score"], "tier": "projected",
            })
            winners.append(h if fav_home else a)
        return cards, winners

    r16_adv = [advancing(m) for m in r16]
    qf_cards, qf_w = project_round(r16_adv)
    sf_cards, sf_w = project_round(qf_w)
    final_cards, champ_w = project_round(sf_w)
    final_card = final_cards[0] if final_cards else None
    if final_card:
        final_card["champion"] = champ_w[0] if champ_w else None

    champions = monte_carlo(r16)

    # ---- next match / last result ----
    upcoming = [m for m in sched if not is_placeholder(m["home_team"]["name"])
                and not is_placeholder(m["away_team"]["name"]) and parse_dt(m)]
    upcoming.sort(key=lambda m: parse_dt(m).timestamp())
    next_match = None
    if upcoming:
        m = upcoming[0]
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        mu = matchup(h, a)
        fav_home = mu["pHome"] >= mu["pAway"]
        v = venue_of(m["id"])
        next_match = {
            "round": round_label(m), "date": fmt_daydate(parse_dt(m)), "time": fmt_time(parse_dt(m)),
            "venue": f"{v['venue']}, {v['city']}" if v["city"] else v["venue"],
            "home": team_obj(h), "away": team_obj(a),
            "favCode": code_of(h if fav_home else a),
            "prob": round((mu["pHome"] if fav_home else mu["pAway"]) * 100),
            "probHome": round(mu["pHome"] * 100),
        }

    done_matches = [m for m in fin if parse_dt(m)]
    done_matches.sort(key=lambda m: parse_dt(m).timestamp(), reverse=True)
    last_match = None
    if done_matches:
        m = done_matches[0]
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        v = venue_of(m["id"])
        last_match = {
            "round": round_label(m), "date": fmt_daydate(parse_dt(m)),
            "venue": f"{v['venue']}, {v['city']}" if v["city"] else v["venue"],
            "home": team_obj(h), "away": team_obj(a),
            "sh": m["score"].get("home"), "sa": m["score"].get("away"),
            "scorers": scorers_line(m["id"], m["home_team"]["id"], m["away_team"]["id"]),
        }

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "modelVersion": "v2.6",
        "champions": champions,
        "bracket": {"r16": r16_cards, "qf": qf_cards, "sf": sf_cards, "final": final_card},
        "nextMatch": next_match,
        "lastMatch": last_match,
    }


def monte_carlo(r16):
    """Simulate the knockout tree N times; tally champions → title odds."""
    import random
    rng = random.Random(42)
    fixtures = []
    for m in r16:
        h, a = m["home_team"]["name"], m["away_team"]["name"]
        done = m.get("status") == "finished"
        w = None
        if done:
            w = h if m["score"].get("winner") == "home" else a
        fixtures.append((h, a, w))
    counts = {}
    for _ in range(N_SIMS):
        round_teams = []
        for h, a, w in fixtures:
            if w is not None:
                round_teams.append(w)
            else:
                mu = matchup(h, a)
                round_teams.append(h if rng.random() < mu["pHome"] else a)
        while len(round_teams) > 1:
            nxt = []
            for i in range(0, len(round_teams), 2):
                h, a = round_teams[i], round_teams[i + 1]
                mu = matchup(h, a)
                nxt.append(h if rng.random() < mu["pHome"] else a)
            round_teams = nxt
        champ = round_teams[0]
        counts[champ] = counts.get(champ, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for name, c in ranked[:6]:
        out.append({"code": code_of(name), "name": name, "color": color_of(name),
                    "v": round(c / N_SIMS * 100, 1)})
    return out


# ---------------------------------------------------------------- scorers line
def timeline(mid):
    data = api(f"/football/matches/{mid}/timeline")
    if isinstance(data, dict):
        data = data.get("events", [])
    return data if isinstance(data, list) else []


def scorers_line(mid, home_id, away_id):
    home_g, away_g = [], []
    for ev in timeline(mid):
        t = str(ev.get("type") or "").lower()
        if "goal" not in t and "scored" not in t:
            continue
        if "miss" in t or "disallow" in t or "saved" in t:
            continue
        minute = ev.get("minute")
        player = ev.get("player")
        if isinstance(player, dict):
            player = player.get("name")
        tid = ev.get("team")
        if isinstance(tid, dict):
            tid = tid.get("id")
        txt = f"{player} {minute}'" if player else ""
        if not txt:
            continue
        (home_g if tid == home_id else away_g).append(txt)
    parts = " · ".join(home_g) if home_g else ""
    if away_g:
        parts = (parts + " · " if parts else "") + " · ".join(away_g)
    return parts


# ---------------------------------------------------------------- players
def dig(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


def build_players(fin):
    agg = {}
    finished_ids = [m["id"] for m in fin]
    for mid in finished_ids:
        ps = api(f"/football/matches/{mid}/player-stats")
        if not isinstance(ps, list):
            continue
        for p in ps:
            pid = p.get("player_id")
            if not pid:
                continue
            rec = agg.setdefault(pid, {"name": p.get("player_name"), "team_id": p.get("team_id"),
                                       "goals": 0, "assists": 0, "xg": 0.0, "yc": 0})
            sh = p.get("shooting") or {}
            gen = p.get("general") or {}
            pas = p.get("passing") or {}
            rec["goals"] += dig(sh, "goals") or 0
            rec["xg"] += dig(sh, "expected_goals") or 0.0
            rec["yc"] += dig(gen, "yellow_cards") or 0
            rec["assists"] += dig(pas, "assists", "goal_assist") or 0
    # team_id -> name
    tid_name = {}
    for m in fin:
        tid_name[m["home_team"]["id"]] = m["home_team"]["name"]
        tid_name[m["away_team"]["id"]] = m["away_team"]["name"]
    players = []
    for rec in agg.values():
        nation = tid_name.get(rec["team_id"], "")
        if not nation or not rec["name"]:
            continue
        players.append({
            "name": rec["name"], "code": code_of(nation), "color": color_of(nation),
            "nation": nation, "goals": rec["goals"], "assists": rec["assists"],
            "xg": round(rec["xg"], 1), "yc": rec["yc"],
        })
    players.sort(key=lambda p: (p["goals"], p["xg"]), reverse=True)
    totals = {
        "goals": sum(p["goals"] for p in players),
        "xg": round(sum(p["xg"] for p in players), 1),
        "assists": sum(p["assists"] for p in players),
        "tracked": len(players),
    }
    print(f"  players: {len(players)} tracked, top scorer "
          f"{players[0]['name']} {players[0]['goals']}g" if players else "  players: none")
    return {"players": players, "totals": totals}


# ---------------------------------------------------------------- match lab
def ov(stats, key, side):
    node = (stats.get("overview") or {}).get(key) or {}
    allv = node.get("all") or {}
    return allv.get(side)


def build_match_lab(fin):
    cand = [m for m in fin if m.get("xg_available")]
    cand.sort(key=lambda m: parse_dt(m).timestamp() if parse_dt(m) else 0, reverse=True)
    cand = cand[:LAB_MATCHES]
    out = []
    for m in cand:
        mid = m["id"]
        stats = api(f"/football/matches/{mid}/stats")
        if not isinstance(stats, dict) or not stats.get("overview"):
            continue
        h, a = m["home_team"], m["away_team"]
        sc = m["score"]

        def pair(key):
            return [ov(stats, key, "home"), ov(stats, key, "away")]

        shots_node = stats.get("shots") or {}
        stat_block = {
            "possession": pair("ball_possession"),
            "xg": pair("expected_goals"),
            "shots": pair("total_shots"),
            "sot": pair("shots_on_target"),
            "big": pair("big_chances"),
            "corners": pair("corners"),
            "passes": pair("passes"),
            "passAcc": pair("pass_accuracy"),
            "fouls": pair("fouls"),
            "yellow": pair("yellow_cards"),
        }
        events = build_timeline(mid, h["id"], a["id"])
        shots = build_shots(mid, h["id"])
        lineups = build_lineups(mid)
        v = venue_of(mid)
        out.append({
            "id": mid,
            "home": {"code": code_of(h["name"]), "name": h["name"], "color": color_of(h["name"])},
            "away": {"code": code_of(a["name"]), "name": a["name"], "color": color_of(a["name"])},
            "score": [sc.get("home"), sc.get("away")],
            "round": round_label(m),
            "date": fmt_date(parse_dt(m)),
            "venue": v["venue"], "city": v["city"], "ref": v["ref"],
            "stats": stat_block,
            "timeline": events,
            "shots": shots,
            "lineups": lineups,
        })
    return out


SHOT_OUTCOME = {"goal": "g", "save": "s", "miss": "o", "block": "b"}


def build_shots(mid, home_id):
    out = []
    data = api(f"/football/matches/{mid}/shotmap")
    if not isinstance(data, list):
        return out
    for s in data:
        res = str(s.get("result") or "").lower()
        outcome = SHOT_OUTCOME.get(res)
        if not outcome:
            outcome = "s" if s.get("is_on_target") else "b" if s.get("is_blocked_shot") else "o"
        out.append({
            "team": "home" if s.get("team_id") == home_id else "away",
            "player": s.get("player_name"),
            "xg": round(s.get("expected_goals") or 0.0, 2),
            "outcome": outcome,
            "x": s.get("x"), "y": s.get("y"), "min": s.get("minute"),
        })
    return out


def pos_group(code):
    c = str(code or "").upper()[:1]
    if c == "G":
        return "gk"
    if c == "D":
        return "def"
    if c in ("F", "S", "W", "A"):
        return "fwd"
    return "mid"


def build_lineups(mid):
    data = api(f"/football/matches/{mid}/lineups")
    if not isinstance(data, dict):
        return {}
    out = {}
    for side in ("home", "away"):
        node = data.get(side) or {}
        xi = []
        for p in node.get("starting_xi") or []:
            xi.append({"name": p.get("name"), "pos": pos_group(p.get("position")),
                       "num": p.get("jersey_number")})
        subs = [p.get("name") for p in (node.get("substitutes") or [])][:8]
        out[side] = {"formation": node.get("formation"), "xi": xi, "subs": subs}
    return out


def build_timeline(mid, home_id, away_id):
    out = []
    for ev in timeline(mid):
        t = str(ev.get("type") or "").lower()
        kind = None
        if ("goal" in t or "scored" in t) and "miss" not in t and "disallow" not in t:
            kind = "g"
        elif "yellow" in t:
            kind = "y"
        elif "red" in t:
            kind = "r"
        if not kind:
            continue
        player = ev.get("player")
        if isinstance(player, dict):
            player = player.get("name")
        assist = ev.get("assist") or ev.get("related_player")
        if isinstance(assist, dict):
            assist = assist.get("name")
        tid = ev.get("team")
        if isinstance(tid, dict):
            tid = tid.get("id")
        out.append({
            "min": ev.get("minute"), "type": kind,
            "team": "home" if tid == home_id else "away",
            "player": player, "assist": assist,
        })
    return out


if __name__ == "__main__":
    main()
