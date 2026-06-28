"""
core.ai — Claude-backed text generation (framework-neutral).

Mirrors app.py's improved ask_ai (system / cache_context prompt-caching split +
graceful error handling) with the Streamlit couplings removed: the
@st.cache_resource client singleton becomes a plain module-level lazy singleton,
and the key comes from core._secrets. Model ids match the app. Callers gate
these (cost) exactly as the UI does today.

    from core.ai import ask_ai, match_summary_prompt
    text = ask_ai("\n".join(facts), system=match_summary_prompt())
"""
import anthropic

from ._secrets import get_secret

AI_MODEL = "claude-haiku-4-5-20251001"      # quick summaries / chatbot
PREDICT_MODEL = "claude-sonnet-4-6"         # heavier reasoning (bracket etc.)

_CLIENT = None


def _claude():
    """Lazily build the Anthropic client once and reuse it (connection-pool reuse)."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))
    return _CLIENT


def ask_ai(prompt, system=None, model=AI_MODEL, temperature=0.3, max_tokens=700,
           cache_context=None):
    """Send a prompt to Claude and return the text.

    system        — role/instructions, kept separate from the data so the model
                    follows them more reliably.
    cache_context — a large, reused context block (e.g. standings) placed in a
                    cached slot so repeated reads are ~90% cheaper (prompt caching).
    Errors are caught here so every feature degrades gracefully.
    """
    sys_blocks = []
    if system:
        sys_blocks.append({"type": "text", "text": system})
    if cache_context:
        sys_blocks.append({"type": "text", "text": cache_context,
                           "cache_control": {"type": "ephemeral"}})
    kwargs = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
              "messages": [{"role": "user", "content": prompt}]}
    if sys_blocks:
        kwargs["system"] = sys_blocks
    try:
        return _claude().messages.create(**kwargs).content[0].text
    except anthropic.RateLimitError:
        return "The AI is busy right now — please try again in a moment."
    except anthropic.APIConnectionError:
        return "Sorry — couldn't reach the AI (network issue). Please try again."
    except anthropic.APIStatusError as e:
        return f"Sorry — the AI couldn't respond right now. ({e.status_code})"


def match_summary_prompt():
    """System instruction for the grounded match summary (facts go in the prompt)."""
    return ("You are a football reporter. Using ONLY the facts provided, write a tight "
            "3-4 sentence summary of this World Cup match. Don't invent anything not in "
            "the data.")
