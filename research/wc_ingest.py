r"""
wc_ingest.py  —  incremental World Cup result store (research only)
------------------------------------------------------------------
Keeps a local cache of finished World Cup matches in footy_model format so the
predictor gets smarter as the tournament plays out — without re-downloading the
whole tournament (and re-spending API quota) every time.

  * The cache is a JSON-lines file, research/wc_matches.jsonl — one finished
    match per line, in the exact dict shape footy_model.Model.update() expects,
    plus a stable `id` and `date` for de-duplication.
  * ingest() asks TheStatsAPI for the current finished-match list (one cheap
    request), then fetches per-match stats ONLY for ids the cache hasn't seen.
    New records are appended; existing ones are never re-fetched or duplicated.
  * load_cache() returns every stored match, oldest first, ready to feed the model.

Run it on a schedule (see TRIGGERING below) and predictions improve automatically
as results land. Safe to run as often as you like — if nothing new finished, it
does one request and appends nothing.

USAGE
  python research/wc_ingest.py            # fetch new finished matches, append to cache
  python research/wc_ingest.py --status   # show what's in the cache, fetch nothing
  python research/wc_ingest.py --rebuild  # re-fetch EVERY match (one stats request
                                          # each) — use after new fields are added
                                          # to match_record (e.g. xG/fouls/possession)

TRIGGERING ON A SCHEDULE (Windows Task Scheduler) — run every 6 hours:
  schtasks /Create /TN "WC ingest" /SC HOURLY /MO 6 ^
    /TR "python \"%CD%\research\wc_ingest.py\"" /ST 00:00
(run that once from the repo root in cmd; see the chat for a PowerShell version.)
"""

import json
import os
import sys

# allow `python research/wc_ingest.py` from the repo root (bare imports below)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:                                   # make accented team names print cleanly on Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from wc_data import finished_matches, match_record, _date

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wc_matches.jsonl")


def load_cache():
    """Every stored finished match, oldest first (footy_model dict shape)."""
    if not os.path.exists(CACHE):
        return []
    out = []
    with open(CACHE, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    out.sort(key=lambda r: r.get("date", ""))
    return out


def _cached_ids():
    return {str(r["id"]) for r in load_cache() if "id" in r}


def ingest(verbose=True):
    """Fetch finished matches and append any not already cached. De-dupes by id.
    Returns (added, total). One list request + one stats request per NEW match."""
    have = _cached_ids()
    ms = finished_matches()
    if not ms:
        if verbose:
            print("[wc_ingest] no finished matches available "
                  "(no STATS_API_KEY, or none played yet).")
        return 0, len(have)

    # only the genuinely new ones, oldest first so the file stays date-ordered
    fresh = sorted((m for m in ms if str(m["id"]) not in have), key=_date)
    if verbose:
        print(f"[wc_ingest] {len(ms)} finished upstream, {len(have)} cached, "
              f"{len(fresh)} new to fetch.")

    added = 0
    with open(CACHE, "a", encoding="utf-8") as fh:
        for m in fresh:
            rec = match_record(m)            # the per-match stats call happens here
            if rec is None:
                continue                     # no final score yet — retry next run
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            added += 1
            if verbose:
                print(f"  + {rec['home']} {rec['fthg']}-{rec['ftag']} {rec['away']}")

    total = len(have) + added
    if verbose:
        print(f"[wc_ingest] appended {added} new match(es); cache now holds {total}.")
    return added, total


def rebuild(verbose=True):
    """Re-fetch every finished match from scratch (one stats request each) and
    atomically replace the cache. Use after match_record gains new fields; the
    old cache is kept as wc_matches.jsonl.bak."""
    ms = finished_matches()
    if not ms:
        print("[wc_ingest] cannot rebuild: no matches from the API (no key?).")
        return 0
    ms.sort(key=_date)
    tmp = CACHE + ".tmp"
    n = 0
    with open(tmp, "w", encoding="utf-8") as fh:
        for m in ms:
            rec = match_record(m)
            if rec is None:
                continue
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            if verbose and n % 10 == 0:
                print(f"  ... {n} matches re-fetched")
    if n == 0:
        os.remove(tmp)
        print("[wc_ingest] rebuild produced nothing; cache left untouched.")
        return 0
    if os.path.exists(CACHE):
        os.replace(CACHE, CACHE + ".bak")
    os.replace(tmp, CACHE)
    print(f"[wc_ingest] rebuilt cache with {n} matches "
          f"(old cache saved as {os.path.basename(CACHE)}.bak).")
    return n


def _status():
    rows = load_cache()
    print(f"Cache: {CACHE}")
    print(f"Stored finished matches: {len(rows)}")
    if rows:
        teams = sorted({r["home"] for r in rows} | {r["away"] for r in rows})
        print(f"First: {rows[0].get('date','?')}   Last: {rows[-1].get('date','?')}")
        print(f"Teams seen ({len(teams)}): {', '.join(teams)}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        _status()
    elif "--rebuild" in sys.argv:
        rebuild()
    else:
        ingest()
