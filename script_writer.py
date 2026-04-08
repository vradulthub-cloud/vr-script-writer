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
import sys

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
