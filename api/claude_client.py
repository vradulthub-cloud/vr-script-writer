"""
Thin Claude API wrapper for single-shot completions.

Used as the preferred backend for title generation (dolphin3 on Ollama is
uncensored but weaker at creative wordplay; Claude produces better titles).

Raises RuntimeError on any failure so callers can fall through to Ollama.
Content-policy refusals also raise RuntimeError so the fallback fires.
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)

# Model used for short creative tasks (titles, SEO snippets).
# Haiku 4.5 is fast and cheap; upgrade to Sonnet for heavier tasks.
_MODEL = "claude-haiku-4-5-20251001"


def claude_generate(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 60,
    temperature: float = 0.8,
) -> str:
    """
    Single-shot completion via Claude API.

    Raises RuntimeError on:
      - missing ANTHROPIC_API_KEY
      - network / API errors
      - content-policy refusal (stop_reason == "content_filter" or empty response)

    Callers should wrap in try/except RuntimeError and fall back to Ollama.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed")

    client = anthropic.Anthropic(api_key=api_key)

    messages: list[dict] = [{"role": "user", "content": prompt}]
    kwargs: dict = {
        "model": _MODEL,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    try:
        response = client.messages.create(**kwargs)
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API error: {exc}") from exc

    if response.stop_reason == "content_filter":
        raise RuntimeError("Claude content-policy refusal — falling back to Ollama")

    text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()

    if not text:
        raise RuntimeError("Claude returned empty response")

    return text
