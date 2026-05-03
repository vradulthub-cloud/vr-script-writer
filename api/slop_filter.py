"""
Slop-filter regex substitutions for scripts and descriptions.

Mirrors `_SLOP_SUBS` from script_writer_app.py — the canonical "banned
phrases" list that replaces AI clichés ("eyes meet", "palpable tension",
"sparks fly", "undeniable chemistry") with prose the editors prefer,
and swaps alcohol/drugs (wine, champagne, whiskey) for on-brand
substitutes (sparkling water, coffee).

Also handles em/en dash collapse and compound-hyphen fixes that Claude
output tends to need.

Apply `post_process()` at save-time (not during streaming) so the user
sees the raw model output live and the cleaned version lands in Sheets.
"""

from __future__ import annotations

import re

# Each entry is (compiled_pattern, replacement). Compiled at module load
# so /scripts/save requests don't pay recompile cost on every call.
_SLOP_SUBS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:their\s+)?eyes?\s+meets?\b", re.I), "she holds his gaze"),
    (re.compile(r"\b(?:their\s+)?eyes?\s+met\b", re.I), "she held his gaze"),
    (re.compile(r"\beyes?\s+locking\b", re.I), "she holds his gaze"),
    (re.compile(r"\beyes?\s+locked\b", re.I), "she held his gaze"),
    (re.compile(r"\bthe air between them\b", re.I), "the quiet between them"),
    (re.compile(r"\bundeniable chemistry\b", re.I), "a pull they've both felt building"),
    (re.compile(r"\bmagnetic attraction\b", re.I), "a pull neither moves to break"),
    (re.compile(r"\bpalpable tension\b", re.I), "a quiet charge in the room"),
    (re.compile(r"\bthe tension is palpable\b", re.I), "the charge in the room is undeniable"),
    (re.compile(r"\bsparks fly\b", re.I), "something shifts between them"),
    (re.compile(r"\belectric tension\b", re.I), "a stillness charged with intent"),
    (re.compile(r"\bsuccumb(s|ed|ing)?\b", re.I), "give in"),
    (re.compile(r"\bsteamy\b", re.I), "charged"),
    (re.compile(r"\bdesires intertwining\b", re.I), "what comes next"),
    (re.compile(r"\bdesires intertwine\b", re.I), "what comes next"),
    (re.compile(r"\bunspoken desire\b", re.I), "what neither has said aloud"),
    (re.compile(r"\bpassion ignites\b", re.I), "the moment breaks open"),
    (re.compile(r"\bunable to resist\b", re.I), "past the point of stopping"),
    (re.compile(r"\bgive in to their desires\b", re.I), "act on it"),
    (re.compile(r"\bcan no longer be contained\b", re.I), "is past the point of stopping"),
    (re.compile(r"\bcharged atmosphere\b", re.I), "the stillness in the room"),
    (re.compile(r"\blonging glances\b", re.I), "the way she watches him"),
    (re.compile(r"\ba bottle of (?:wine|champagne|prosecco)\b", re.I), "a bottle of sparkling water"),
    (re.compile(r"\btwo wine glasses\b", re.I), "two glasses of water"),
    (re.compile(r"\bwine glasses?\b", re.I), "water glasses"),
    (re.compile(r"\bglass(?:es)? of (?:wine|champagne|prosecco)\b", re.I), "glass of water"),
    (re.compile(r"\bchardonnay\b", re.I), "sparkling water"),
    (re.compile(r"\bprosecco\b", re.I), "sparkling water"),
    (re.compile(r"\bchampagne\b", re.I), "sparkling water"),
    (re.compile(r"\bred wine\b", re.I), "herbal tea"),
    (re.compile(r"\bwhite wine\b", re.I), "sparkling water"),
    (re.compile(r"\brosé\b", re.I), "sparkling water"),
    (re.compile(r"\bcocktails?\b", re.I), "coffee"),
    (re.compile(r"\bwhiskey\b", re.I), "coffee"),
    (re.compile(r"\bbourbon\b", re.I), "coffee"),
    (re.compile(r"\bwine rack\b", re.I), "bookshelf"),
    (re.compile(r"\bcooking wine\b", re.I), "cooking broth"),
    (re.compile(r"\bwine\b", re.I), "sparkling water"),
    (re.compile(r"\bbeer\b", re.I), "sparkling water"),
    (re.compile(r"\bliquor\b", re.I), "coffee"),
    (re.compile(r"\brum\b", re.I), "coffee"),
    (re.compile(r"\bgin\b", re.I), "coffee"),
    (re.compile(r"\bvodka\b", re.I), "coffee"),
]


def post_process(raw: str) -> str:
    """
    Apply dash collapse + slop substitutions to the given text.

    - Em/en dashes with surrounding whitespace → single space
    - Numbered compound hyphens (e.g. `8K-30fps`) → space
    - Generic word-word hyphens → space
    - Remaining hyphens → space
    - Run the full `_SLOP_SUBS` regex list
    """
    if not raw:
        return raw
    out = re.sub(r"\s*[\u2014\u2013]\s*", " ", raw)
    out = re.sub(r"(\d+[A-Za-z]?)-(\d)", r"\1 \2", out)
    out = re.sub(r"(\w)-(\w)", r"\1 \2", out)
    out = re.sub(r"-", " ", out)
    for pattern, replacement in _SLOP_SUBS:
        out = pattern.sub(replacement, out)
    return out


def find_slop(raw: str) -> list[str]:
    """
    Return a list of slop phrases present in `raw`.

    Useful for the /scripts/validate endpoint so the UI can surface
    rule violations to the user before they save.
    """
    if not raw:
        return []
    hits: list[str] = []
    for pattern, _ in _SLOP_SUBS:
        m = pattern.search(raw)
        if m:
            hits.append(f"slop: {m.group(0).strip()}")
    return hits
