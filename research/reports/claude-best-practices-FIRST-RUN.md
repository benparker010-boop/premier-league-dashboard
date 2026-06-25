# Claude usage review — `app.py`

_First analysis, generated in-session by Claude Code (web research + code cross-reference)._
_Re-run anytime with `python research/claude_research_agent.py` to refresh against the latest guidance._

All findings are tied to your actual code. Your Claude integration is a single helper,
`ask_ai` (app.py:479–483), called from 4 sites: the match summary (≈1726), the World Cup
analysis (≈2141), the stats Q&A (≈2167), and the knockout bracket prediction (≈2200).

```python
# app.py:479
def ask_ai(prompt, model=AI_MODEL, temperature=1.0):
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    msg = client.messages.create(model=model, max_tokens=700, temperature=temperature,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text
```

---

## P0 — correctness / cost bugs

### P0.1 — `max_tokens=700` truncates the bracket prediction
The bracket prompt (app.py:2190) asks Claude to *"Predict the FULL knockout bracket round by
round: Round of 32, Round of 16, …"*. That's 32 → 16 → 8 → 4 → 2 → 1, i.e. dozens of fixtures
with reasoning. 700 output tokens ≈ 500 words — it will be cut off mid-bracket, and the user
sees a half-finished prediction with no error. `max_tokens` is a hard ceiling the model isn't
aware of, so it just stops.

**Fix:** make `max_tokens` a parameter and raise it where the output is long. For outputs above
~16K, stream (avoids SDK HTTP timeouts); 700 is fine for the short summaries.

```python
def ask_ai(prompt, model=AI_MODEL, temperature=1.0, max_tokens=700):
    msg = _claude().messages.create(model=model, max_tokens=max_tokens,
                                    temperature=temperature,
                                    messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text

# bracket call site (app.py:2200):
st.session_state.ai_bracket = ask_ai(prompt, model=PREDICT_MODEL,
                                     temperature=0.4, max_tokens=4000)
```

### P0.2 — a brand-new client is built on every call
`anthropic.Anthropic(...)` is constructed inside `ask_ai` on every invocation (app.py:480). The
client holds a connection pool; rebuilding it each time throws away keep-alive connections and
adds latency. In Streamlit the right tool is `@st.cache_resource` — it returns a single shared
client across reruns and sessions (the documented singleton pattern for "global resources like
DB connections or model clients"). ([Streamlit caching docs](https://docs.streamlit.io/develop/concepts/architecture/caching))

```python
@st.cache_resource
def _claude():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
```

Then use `_claude()` inside `ask_ai`. (The SDK already auto-retries 429/5xx with backoff, so you
get that for free once the client is reused.)

---

## P1 — clear wins

### P1.1 — instructions belong in `system=`, not the user turn
Every call stuffs the role + rules into the user message (*"You are a football reporter. Using
ONLY these facts…"*). Anthropic's current guidance is a **contract-style system prompt** that
defines the role and what "done" looks like, with the *data* in the user turn — the 2026 pattern
is INSTRUCTIONS / CONTEXT / TASK / OUTPUT-FORMAT as distinct sections.
([Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices))
This separation also improves instruction-following and sets you up for caching (P1.3).

```python
def ask_ai(prompt, system=None, model=AI_MODEL, temperature=1.0, max_tokens=700):
    kwargs = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    return _claude().messages.create(**kwargs).content[0].text

# e.g. match summary:
ask_ai(facts_block,
       system="You are a football reporter. Write a tight 3–4 sentence summary using ONLY "
              "the supplied facts. Never invent anything not in the data.",
       temperature=0.3)
```

### P1.2 — drop `temperature` on the factual calls
The match summary and stats Q&A run at the default `temperature=1.0` (app.py:479) while
explicitly instructing *"use ONLY these facts, don't invent anything."* Temperature 1.0 is
maximum randomness — exactly what you don't want for grounded, factual output where hallucination
is the failure mode. The Q&A already uses `0.2` (good). Use a low temperature (0.2–0.3) for the
summary and analysis too; keep a bit of variety (0.4) only for the bracket. (Both your models —
`claude-sonnet-4-6` and `claude-haiku-4-5` — still accept `temperature`.)

### P1.3 — cache the repeated data context with prompt caching
The World Cup analysis (app.py:2141) and stats Q&A (2161) both prepend the same large
standings + team-stats block on every call. Prompt caching makes a reused prefix ~90% cheaper to
re-read and cuts latency on long prompts, as long as the cached block is ≥1024 tokens and byte-
identical between calls. ([Prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching))
Put the stable data first with a cache breakpoint, the volatile question last:

```python
msg = _claude().messages.create(
    model=AI_MODEL, max_tokens=700, temperature=0.2,
    system=[{"type": "text", "text": INSTRUCTIONS},
            {"type": "text", "text": standings_block,
             "cache_control": {"type": "ephemeral"}}],   # cached prefix
    messages=[{"role": "user", "content": user_question}],  # volatile, not cached
)
```
Verify it's working by checking `msg.usage.cache_read_input_tokens > 0` on the second call. Skip
this for the one-off summaries — caching only pays off when the same prefix is re-read.

### P1.4 — centralise error handling in `ask_ai`
Three of four call sites wrap `ask_ai` in try/except with a friendly message; the match summary
(≈1726) does not, so an API blip there shows a raw Streamlit traceback. Catch the SDK's typed
exceptions once, inside `ask_ai`, and return a clean message — most-specific first
([error codes](https://platform.claude.com/docs/en/api/errors)):

```python
try:
    return _claude().messages.create(**kwargs).content[0].text
except anthropic.RateLimitError:
    return "The AI is busy right now — try again in a moment."
except anthropic.APIStatusError as e:
    return f"Sorry — the AI couldn't respond ({e.status_code})."
```

---

## P2 — features worth adopting

### P2.1 — structured outputs for the bracket / predictions
The bracket is free-form text you then render as-is. Structured outputs (`output_config.format`
with a JSON schema) would let you get a typed bracket back (rounds → fixtures → predicted winner)
and render it in your own pitch/table UI instead of a text blob — far more "premium" and no
parsing guesswork. Supported on `claude-sonnet-4-6`. Flatten the schema (avoid deep nesting) for
reliability. ([Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs))

### P2.2 — model IDs and selection
- `AI_MODEL = "claude-haiku-4-5-20251001"` works, but the bare alias `claude-haiku-4-5` is
  cleaner and avoids pinning to a dated snapshot.
- Haiku 4.5 for the high-volume summaries/Q&A and Sonnet 4.6 for the heavier prediction is a
  sensible cost/quality split — keep it. Only consider `claude-opus-4-8` for the bracket if you
  want maximum reasoning and don't mind the cost.

### P2.3 — `st.cache_data` on the AI text, keyed by inputs
The summaries are deterministic-ish for a given match's facts. Wrapping the AI call result in
`@st.cache_data` (keyed on the facts string) avoids re-paying for identical regenerations when a
user revisits the same match in a session — a direct token saving on top of P1.3.

---

## How "sweep YouTube + the web" fits in
The reusable agent (`research/claude_research_agent.py`) uses Claude's server-side **web search
tool**, so the model runs the searches itself — YouTube videos, blog posts and the official docs
all surface as sources. The system prompt tells it to trust Anthropic's docs over random
tutorials (a lot of LLM YouTube content is stale — wrong model names, deprecated params) and to
flag conflicts. Run it weekly via cron to keep this report fresh as the API evolves.

## Sources
- [Prompt caching — Claude API docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Prompting best practices — Claude API docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Structured outputs — Claude API docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Streamlit caching overview](https://docs.streamlit.io/develop/concepts/architecture/caching)
- [st.cache_resource — Streamlit docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource)
- [API error codes — Claude API docs](https://platform.claude.com/docs/en/api/errors)
