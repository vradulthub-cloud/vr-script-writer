#!/usr/bin/env python3
"""
VR Production Script Writer Agent
Usage:
  python3 script_writer.py
  Then enter: Studio, [Destination,] Type, Female, Male
  Examples:
    VRHush, BG, Jane Doe, John Smith
    FPVR, Paris France, BGCP, Jane Doe, John Smith
"""

import anthropic
import re
import sys

# ── Ollama config ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL    = "vr-scriptwriter"

def get_ollama_client():
    """Return an OpenAI-compatible client pointed at the local Ollama instance."""
    from openai import OpenAI
    return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

# ── Research cache (in-memory, per process) ───────────────────────────────────
_research_cache: dict = {}

def cache_get(key: str) -> str | None:
    return _research_cache.get(key.lower().strip())

def cache_set(key: str, value: str) -> None:
    _research_cache[key.lower().strip()] = value

def research_scene_trends(female: str, ollama_client=None, model: str | None = None) -> str:
    """Ask Ollama to summarize a performer's on-screen persona and physical look.
    Returns a plain-text research summary, or empty string on failure.
    Saves result to in-memory cache."""
    client = ollama_client or get_ollama_client()
    model  = model or OLLAMA_MODEL
    prompt = (
        f"Briefly summarize {female}'s on-screen persona for a VR film director. "
        f"Cover: body type, hair, notable tattoos or piercings, typical role archetype "
        f"(e.g. submissive, dominant, girl-next-door, playful), and any signature style. "
        f"Keep it under 120 words. Plain text only, no headers."
    )
    try:
        resp = client.chat.completions.create(
            model=model, max_tokens=200, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        result = (resp.choices[0].message.content or "").strip()
        if result:
            cache_set(female, result)
        return result
    except Exception:
        return ""

# ── Script validation ─────────────────────────────────────────────────────────
_BANNED_CONTENT = [
    (re.compile(r'\b(?:wine|beer|liquor|whiskey|bourbon|vodka|rum|gin|champagne|prosecco|ros[eé]|cocktail|alcohol)\b', re.I),
     "Contains banned alcohol reference"),
    (re.compile(r'\b(?:chok(?:e|ing|ed)|strangulat(?:e|ion))\b', re.I),
     "Contains banned choking reference"),
    (re.compile(r'\b(?:drug|cocaine|heroin|weed|marijuana|cannabis|molly|ecstasy)\b', re.I),
     "Contains banned drug reference"),
    (re.compile(r'\b(?:incest|step-?(?:mom|dad|sister|brother|son|daughter|sibling))\b', re.I),
     "Contains banned incest reference"),
]

_REQUIRED_FIELDS = [
    ("theme",          "Missing THEME section"),
    ("plot",           "Missing PLOT section"),
    ("shoot_location", "Missing SHOOT LOCATION section"),
    ("wardrobe_female","Missing WARDROBE - FEMALE section"),
]

def validate_script(fields: dict, female: str = "", male: str = "") -> list[str]:
    """Return a list of rule violation strings. Empty list = pass."""
    violations = []

    # Required sections
    for key, msg in _REQUIRED_FIELDS:
        if not fields.get(key, "").strip():
            violations.append(msg)

    # Banned content check across all text fields
    all_text = " ".join(fields.get(k, "") for k in
                        ("theme", "plot", "set_design", "props", "wardrobe_female", "wardrobe_male"))
    for pattern, msg in _BANNED_CONTENT:
        if pattern.search(all_text):
            violations.append(msg)

    # Male talent name check — should not appear as a named character (POV = "you")
    if male and male.strip():
        male_first = male.strip().split()[0]
        if len(male_first) > 2 and re.search(r'\b' + re.escape(male_first) + r'\b', all_text, re.I):
            violations.append(f"Male talent '{male_first}' named in script — POV talent should be 'you'")

    return violations

SYSTEM_PROMPT = """You are a professional VR adult film script writer for two studios: VRHush (VRH) and FuckPassVR (FPVR). Your writing is cinematic, intimate, and director-ready — rich with physical detail, emotional texture, and clear stage direction without dialogue cues.

---

## STUDIOS

### VRHush (VRH)
Two formats — vary between them:
1. **Fantasy Scenario**: A grounded, believable situation that brings two people together naturally. Examples: parent-teacher conference, office coworker tension, babysitter who has a thing for her employer, returning from a concert for a one-night stand, a real estate showing that turns personal, a personal trainer session, a massage therapist who goes further, etc. The scenario must explain WHY they are together and WHAT happened before the scene begins.
2. **Pornstar Experience**: The female model breaks the 4th wall. She addresses the viewer directly — seducing them, playing into their fantasies, referencing who she is and what she knows they want. Fine-tune this format to the specific model's personality, look, and on-screen archetype.

VRHush does NOT include a travel/passport component.

### FuckPassVR (FPVR)
Always travel-themed. The male talent (whose POV the viewer occupies) is traveling through a new city or country. The female model is either from that location or was there when their paths crossed. The plot gives them a reason to connect — something rooted in the place, the moment, or a shared circumstance. After they make love, she stamps his passport with the new destination.

The destination should influence the scene naturally: how she dresses, what draws them together, the ambiance, the cultural texture of the moment. The travel connection doesn't need to be heavy-handed — a light touch is more effective.

---

## OUTPUT FORMAT

Use EXACTLY these section headers — they are parsed by software to write to a database. Do not rename, reorder, or omit any section.

THEME: [One punchy sentence or title. e.g. "The Lucy Lotus Experience" or "Goth Convention / Try-On Haul"]

PLOT:
[Paragraph 1 — Setup]

[Paragraph 2 — Seduction]

[Paragraph 3 — Intimacy]

SHOOT LOCATION: [One room name + shooting direction if relevant]

SET DESIGN: [Specific, practical room dressing — tapestries, lighting, furniture, accent pieces]

PROPS: [Bulleted list of specific props and any tapestries]

WARDROBE - FEMALE: [Full outfit description]

WARDROBE - MALE: [Full outfit description]

---

## ROOMS AVAILABLE

- **Entryway**: Large room with bookshelves, leather furniture, and strong set-creation potential. Harder to move props in/out, but excellent space for elaborate dressing.
- **Dining Room**: Bright room with a kitchen table and large textured accent wall. Good for daytime energy or professional scenarios.
- **Kitchen**: Tight but functional. Only use when the plot specifically calls for it.
- **Living Room**: Two shooting directions. Toward the sliding glass door: bright, airy, modern. Toward the garage wall: more dim, moody, cinematic. Large TV moves easily.
- **Bedroom 1**: Massive room with lots of room to stage. Master bathroom includes a large glassed-in custom tiled shower — usable.
- **Bedroom 2**: Large room with a dramatic accent wall. Two distinct looks depending on the wall you face. Second bathroom with glassed-in custom tiled shower.
- **Bedroom 3**: Smallest room. Single filming direction only — bed must remain in frame. Use sparingly for a different look.
- **The Office**: Ship-lapped accent wall opposite a computer setup. Film toward the accent wall. Easy to re-theme with decor.
- **Outside**: Backyard with pool. Las Vegas climate makes it limiting. Intro/establishing shots only — no explicit content outside.

**VR Filming Constraints:**
- 180-degree capture — everything must be staged in front of the camera
- Camera does not move mid-scene; only repositioned on cut
- All POV from the male model's perspective
- Female model stays within 3 feet of camera to maintain intimacy; if she moves farther, it's brief and she returns

---

## SCENE RULES

- 45-minute scene, two performers only — no extras
- Filmed entirely at the studio shoot location
- Scene opens with seduction; the balance is sex
- DO NOT write dialogue lines or quote what characters say
- DO NOT include: rape, incest, alcohol (wine/beer/liquor), drugs, choking
- DO NOT set scenes outside the listed rooms or locations

**BG Scene**: Standard boy/girl scene. Can end with handjob, facial, oral finish, or pull-out.
**BGCP / CP / Creampie Scene**: Ends with the male talent cumming inside the female model. The intimacy of this must be emotionally present in the plot — it should feel like a natural, meaningful escalation, not a tagged-on ending.

---

## MODEL RESEARCH

Before writing, search the web for the female model's name to gather:
- Body type, build, and measurements
- Tattoos and distinctive physical features
- Hair color, style, and look
- On-screen persona — what kinds of roles does she typically play?
- Overall vibe and archetype (girl-next-door, dominant, submissive, playful, intense, etc.)

Use this research to shape the plot, her characterization in the scene, and her wardrobe. Reference her physical attributes naturally — don't list them like a data sheet, but let them inform how she moves, what she wears, and how the scene is staged. A model with heavy tattoos might play edgier. A petite model might use proximity and eye contact differently. Let the real person inform the fictional character.

---

## TONE & CRAFT

Write like a cinematic short film, not a checklist. The best plots feel specific — they have a world, a reason, a moment. The seduction should feel inevitable but not rushed. The intimacy should feel personal, not generic.

Every script should be different. Rotate rooms, vary scenario types, find new angles on familiar situations. The goal is that a director and two performers can walk into a room, read this, and know exactly what world they're inhabiting."""

# NaughtyJOI uses a fixed plot template — no AI generation needed.
# Performer-specific details (name, look, wardrobe) are filled in at shoot time.
NJOI_STATIC_PLOT = """She walks in like she owns the room — unhurried, eyes locked on the camera. She already knows why you're here. She settles in front of you, makes herself comfortable, and tells you exactly how this is going to go. Her voice is calm, deliberate. She's done this before and she likes watching you try to keep up.

She builds you slow. Instructions come one at a time — start here, stop there, wait for her. She strips down at her own pace, not yours, letting each reveal land before moving to the next. When you rush she notices. When you obey she rewards you with a little more. The rhythm is entirely hers and she's not in a hurry.

When she's ready she starts the countdown. Ten, nine, eight — her voice drops. She watches the camera with the focus of someone who knows exactly what they're doing to you. She brings you both to the edge at the same time, and when she hits zero she means it."""


def parse_input(raw: str) -> dict | None:
    """Parse comma-separated input into structured fields."""
    parts = [p.strip() for p in raw.split(",")]

    if len(parts) < 4:
        return None

    studio_raw = parts[0].upper()

    # Ignore certain studio prefixes
    for prefix in ["VRA", "VRALLURE", "NJOI", "NAUGHTYJOI"]:
        if studio_raw.startswith(prefix):
            return None

    # Normalize studio name
    if studio_raw in ["VRHUSH", "VRH", "VRHUSH"]:
        studio = "VRHush"
        if len(parts) < 4:
            return None
        scene_type = parts[1]
        female = parts[2]
        male = parts[3]
        destination = None
    elif studio_raw in ["FPVR", "FUCKPASSVR", "FUCKPASS"]:
        studio = "FuckPassVR"
        if len(parts) < 5:
            return None
        destination = parts[1]
        scene_type = parts[2]
        female = parts[3]
        male = parts[4]
    else:
        # Try to handle partial matches
        if "HUSH" in studio_raw:
            studio = "VRHush"
            scene_type = parts[1]
            female = parts[2]
            male = parts[3]
            destination = None
        elif "PASS" in studio_raw or "FPVR" in studio_raw:
            studio = "FuckPassVR"
            if len(parts) < 5:
                return None
            destination = parts[1]
            scene_type = parts[2]
            female = parts[3]
            male = parts[4]
        else:
            return None

    # Normalize scene type
    scene_type_upper = scene_type.upper().replace(" ", "")
    if "CP" in scene_type_upper or "CREAMPIE" in scene_type_upper:
        scene_type_normalized = "BGCP"
    else:
        scene_type_normalized = "BG"

    return {
        "studio": studio,
        "destination": destination,
        "scene_type": scene_type_normalized,
        "female": female.strip(),
        "male": male.strip(),
    }


def build_prompt(parsed: dict) -> str:
    studio = parsed["studio"]
    scene_type = parsed["scene_type"]
    female = parsed["female"]
    male = parsed["male"]
    destination = parsed.get("destination")
    theme_hint = parsed.get("theme_hint")

    prompt_parts = [
        f"Please write a complete VR production script for the following shoot:",
        f"",
        f"- **Studio**: {studio}",
    ]

    if destination:
        prompt_parts.append(f"- **Destination**: {destination}")

    prompt_parts += [
        f"- **Scene Type**: {scene_type}",
        f"- **Female Talent**: {female}",
        f"- **Male Talent**: {male}",
        f"",
        f"First, research {female} online to understand her appearance, body type, tattoos, typical on-screen persona, and the roles she commonly plays. Use this research to inform the plot, wardrobe, and set design.",
        f"",
        f"Then produce the full script with all required sections: One-Sentence Summary, Plot (three paragraphs), Shoot Location, Set Design, Prop Recommendations, and Wardrobe.",
    ]

    if theme_hint:
        prompt_parts.append(
            f"\nDirector's note — use this as the creative direction for the scene: {theme_hint}"
        )

    if studio == "FuckPassVR" and destination:
        prompt_parts.append(
            f"\nRemember: This is a FuckPassVR scene set in {destination}. The male POV character is traveling there. After they make love, she stamps his passport. The destination should influence the plot, her persona, and/or wardrobe."
        )

    if scene_type == "BGCP":
        prompt_parts.append(
            "\nThis is a BGCP (Creampie) scene. The plot must reflect the heightened intimacy of this ending — make it feel special and meaningful. The female model should convey why this level of connection is significant."
        )

    return "\n".join(prompt_parts)


def generate_script(parsed: dict):
    """Call Claude with web search to research the model and generate the script."""
    client = anthropic.Anthropic()

    prompt = build_prompt(parsed)

    print(f"\n{'='*60}")
    print(f"Generating script for {parsed['studio']} — {parsed['female']} & {parsed['male']}")
    if parsed.get('destination'):
        print(f"Destination: {parsed['destination']}")
    print(f"Scene Type: {parsed['scene_type']}")
    print(f"{'='*60}\n")
    print("Researching model and writing script...\n")

    # Use streaming with web search tool for model research
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=[
            {"type": "web_search_20260209", "name": "web_search"},
        ],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print(f"\n\n{'='*60}\n")


def main():
    print("VR Production Script Writer")
    print("="*60)
    print("Input format:")
    print("  VRHush:    Studio, Type, Female, Male")
    print("  FuckPassVR: Studio, Destination, Type, Female, Male")
    print("  Type: BG or BGCP (creampie)")
    print("  Type 'quit' to exit")
    print("="*60)

    while True:
        try:
            raw = input("\nEnter shoot details: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if raw.lower() in ("quit", "exit", "q"):
            print("Exiting.")
            break

        if not raw:
            continue

        # Check for ignored prefixes at the line level
        raw_upper = raw.upper()
        ignored = ["VRA,", "VRALLURE,", "NJOI,", "NAUGHTYJOI,"]
        if any(raw_upper.startswith(p) for p in ignored):
            print("Skipping ignored studio prefix.")
            continue

        parsed = parse_input(raw)
        if not parsed:
            print("Could not parse input. Please check the format and try again.")
            print("  VRHush:    VRHush, BG, Jane Doe, John Smith")
            print("  FuckPassVR: FPVR, Paris France, BGCP, Jane Doe, John Smith")
            continue

        generate_script(parsed)


if __name__ == "__main__":
    main()
