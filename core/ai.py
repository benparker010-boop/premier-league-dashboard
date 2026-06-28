"""
core.ai — Claude-backed text generation (framework-neutral).

Extracted from app.py's ask_ai / AI features with the Streamlit coupling removed
(key comes from core._secrets). Model ids match the current app. Callers are
expected to gate these (cost) exactly as the UI does today.

    from core.ai import ask_ai, match_summary_prompt
    text = ask_ai(match_summary_prompt(facts))
"""
import anthropic

from ._secrets import get_secret

AI_MODEL = "claude-haiku-4-5-20251001"      # quick summaries / chatbot
PREDICT_MODEL = "claude-sonnet-4-6"         # heavier reasoning (bracket etc.)


def _client():
    return anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))


def ask_ai(prompt, model=AI_MODEL, temperature=1.0, max_tokens=700):
    """Single-turn completion. Raises on API error (callers handle/gate)."""
    msg = _client().messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def match_summary_prompt(facts):
    """Build the grounded match-summary prompt from a list of fact strings."""
    return ("You are a football reporter. Using ONLY these facts, write a tight "
            "3-4 sentence summary of this World Cup match. Don't invent anything "
            "not in the data.\n\n" + "\n".join(facts))
