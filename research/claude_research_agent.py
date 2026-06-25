#!/usr/bin/env python3
"""
Claude research agent
=====================

Sweeps the web (YouTube transcripts, blogs, Anthropic docs, forum posts) for
current best practices on building with the Claude API, then cross-references
what it finds against this project's own source code and writes a prioritised,
actionable report to ``research/reports/``.

It uses Claude's *server-side web search tool*, so the model itself runs the
searches and reads the sources — you do not need a YouTube API key or a
scraper. YouTube videos surface as ordinary web-search results (the model reads
titles, descriptions and any indexed transcript text). Because a lot of "how to
use Claude" content online is outdated, the system prompt tells the model to
trust authoritative Anthropic guidance over random tutorials and to flag advice
that conflicts with the official docs.

Run it
------
    # one-off: point it at the file that calls Claude
    export ANTHROPIC_API_KEY=...        # or it will read .streamlit/secrets.toml
    python research/claude_research_agent.py --file app.py

    # weekly, unattended (example cron line):
    #   0 9 * * 1  cd /path/to/repo && python research/claude_research_agent.py >> research/agent.log 2>&1

The report is plain markdown; open it or paste sections back to Claude Code to
apply the suggestions.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import pathlib
import re
import sys

import anthropic

# --- defaults -----------------------------------------------------------------

# Opus 4.8 is the most capable model and supports the dynamic-filtering web
# search tool. Swap to "claude-sonnet-4-6" to cut cost (also web-search capable).
DEFAULT_MODEL = "claude-opus-4-8"

# The web-search tool version with built-in dynamic filtering. Requires
# Opus 4.6+/4.7/4.8 or Sonnet 4.6. (Older models need "web_search_20250305".)
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "research" / "reports"

SYSTEM_PROMPT = """\
You are a senior engineer who specialises in building production applications on
the Claude API (the Anthropic Python SDK) and in Streamlit data apps.

Your job: research the CURRENT best practices for using Claude well, then review
the provided source code and produce a concrete, prioritised improvement report.

Research rules:
- Use the web_search tool to find recent (this year) guidance: Anthropic's own
  docs and engineering blog, reputable YouTube tutorials, conference talks, and
  practitioner write-ups. Search several distinct angles (prompt engineering,
  cost/prompt caching, model selection, streaming, structured outputs, error
  handling, Streamlit + LLM patterns).
- A LOT of online content is out of date. When a tutorial conflicts with
  Anthropic's official documentation, trust the docs and SAY the tutorial is
  stale. Never recommend deprecated parameters or non-existent model IDs.
- Prefer primary sources. Cite the URL for every non-obvious claim.

Report rules:
- Tie every recommendation to a specific line/function in the provided code.
- Prioritise: P0 (correctness/cost bug), P1 (clear win), P2 (nice to have).
- For each item give: what, why (with a source link), and a minimal code diff or
  snippet showing the change.
- Cover these areas: (1) Claude API usage, (2) prompt engineering quality,
  (3) Claude features not yet used that would help, (4) general Streamlit/web
  app best practices.
- End with a short "Sources" list of the most useful links you found.
Output GitHub-flavoured markdown only.
"""


def _load_api_key() -> str:
    """Prefer the env var; fall back to .streamlit/secrets.toml so this matches
    how the Streamlit app authenticates."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    secrets = REPO_ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        m = re.search(r'^\s*ANTHROPIC_API_KEY\s*=\s*["\']([^"\']+)["\']',
                      secrets.read_text(), re.MULTILINE)
        if m:
            return m.group(1)
    sys.exit("No API key found. Set ANTHROPIC_API_KEY or add it to "
             ".streamlit/secrets.toml")


def _read_target(file_arg: str) -> tuple[str, str]:
    path = (REPO_ROOT / file_arg).resolve()
    if not path.exists():
        sys.exit(f"Target file not found: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    # Keep the request bounded; the call sites we care about are easy to find.
    if len(text) > 60_000:
        text = text[:60_000] + "\n\n# … (truncated for the research request) …\n"
    return str(path.relative_to(REPO_ROOT)), text


def run(model: str, effort: str, file_arg: str, extra: str) -> pathlib.Path:
    client = anthropic.Anthropic(api_key=_load_api_key())
    rel_path, source = _read_target(file_arg)

    user_msg = (
        f"Project: a Streamlit football analytics dashboard that calls the "
        f"Claude API. Review the file `{rel_path}` below and research current "
        f"best practices, then write the improvement report.\n"
        f"{('Extra focus: ' + extra) if extra else ''}\n\n"
        f"```python\n{source}\n```"
    )

    print(f"Researching with {model} (effort={effort}); reviewing {rel_path} …",
          file=sys.stderr)

    messages = [{"role": "user", "content": user_msg}]
    final = None
    # Server-tool loops can pause (stop_reason="pause_turn"); resume until done.
    for _ in range(6):
        with client.messages.stream(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
            final = stream.get_final_message()
        if final.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": final.content})
    print()  # newline after streamed output

    report = "".join(b.text for b in final.content if b.type == "text")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = REPORTS_DIR / f"claude-best-practices-{stamp}.md"
    header = (f"# Claude usage review — {rel_path}\n\n"
              f"_Generated {stamp} by research/claude_research_agent.py "
              f"using {model}._\n\n---\n\n")
    out.write_text(header + report, encoding="utf-8")

    u = final.usage
    print(f"\nSaved: {out.relative_to(REPO_ROOT)}", file=sys.stderr)
    print(f"Tokens — in:{u.input_tokens} out:{u.output_tokens} "
          f"(cache read:{getattr(u, 'cache_read_input_tokens', 0)})",
          file=sys.stderr)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", default="app.py",
                   help="Source file to review (relative to repo root).")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Claude model ID (default: {DEFAULT_MODEL}).")
    p.add_argument("--effort", default="high",
                   choices=["low", "medium", "high", "xhigh", "max"],
                   help="Reasoning effort (default: high).")
    p.add_argument("--focus", default="",
                   help="Optional extra focus to emphasise in the review.")
    args = p.parse_args()
    run(args.model, args.effort, args.file, args.focus)


if __name__ == "__main__":
    main()
