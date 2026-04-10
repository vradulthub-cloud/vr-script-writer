#!/usr/bin/env python3
"""
cta_learn.py — LLM-powered CTA treatment classifier

Pulls every title from the Grail sheet, sends each one to Ollama
(dolphin-llama3:8b or llama3.2 as fallback), and saves a treatment +
color-scheme decision to learned_routes.json.

cta_generator.py checks this file first before falling back to keyword scoring.

Usage:
  python3 cta_learn.py                     # classify all unclassified titles
  python3 cta_learn.py --update            # only new titles since last run
  python3 cta_learn.py --title "Some Title"  # classify a single title
  python3 cta_learn.py --show              # print current learned routes
  python3 cta_learn.py --stats             # treatment distribution
"""

import sys, os, re, csv, io, json, time, argparse, urllib.request
from pathlib import Path
from datetime import date

# ── Config ──────────────────────────────────────────────────────────────────
GRAIL_SHEET_ID  = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
OLLAMA_BASE     = "http://localhost:11434"   # tunnelled from Windows PC
LEARNED_FILE    = Path(__file__).parent / "learned_routes.json"
PREFERRED_MODEL = "qwen2.5:7b"
FALLBACK_MODEL  = "dolphin-mistral:latest"

TREATMENTS = [
    "impact", "neon_wire", "editorial", "graffiti", "bubble",
    "cinematic", "block_3d", "script", "retro_rainbow", "chrome",
    "stark", "vintage", "spray_stencil", "liquid_gold", "neon_box",
    "glitch", "holographic", "fire", "ice", "comic",
    "drip", "outline_glow", "movie_title", "glitter", "psychedelic",
]

COLOR_SCHEMES = [
    "fire", "ice", "gold", "silver", "rose", "violet", "cyan",
    "lime", "coral", "amber", "pink", "teal", "sunset", "cream",
]

TREATMENT_DESCRIPTIONS = """
Available text treatments:

impact         — Stacked per-word condensed all-caps, vivid per-word colors, thick outline.
                 Best for: energetic collection titles, action-forward superlatives.
                 Examples: "Best Blondes Doggystyle Vol.1", "Extreme Hospitality", "Raging Balls"

neon_wire      — Wide-tracked all-caps letters, electric neon glow, dark bloom.
                 Best for: night/cyber/tech vibes, anything with pulse/signal energy.
                 Examples: "Sleepless In Seattle", "Peer-to-Peer Penetration Test", "Trending in Austin"

editorial      — Wide letter spacing, thin serif gradient face, decorative rule lines.
                 Best for: luxury/exclusive/sophisticated feel, premium brand tone.
                 Examples: "Executive Discretion", "Fashion Week in Milano", "A Very Private Merger"

graffiti       — Italic shear, marker/condensed font, per-line gradient colors, sharp 3D extrusion.
                 Best for: urban raw energy, street attitude, bold/gritty titles.
                 Examples: "Boss Move in Boise", "Wild Zebra from Odesa", "Blasting a Slav in Bratislava"

bubble         — Chunky rounded letters, thick black outline, alternating vivid flat colors.
                 Best for: playful, fun, cheerful, carefree tone.
                 Examples: "A Whorely Jolly Christmas", "Glorious Morning", "All Inclusive in Bali"

cinematic      — Single wide-tracked line, parallel long shadow, film-title elegance.
                 Best for: location titles ("X in City"), one-liners, travel/globe-trotting feel.
                 Examples: "Dancing in Seoul", "When in Rome", "Midday in Saint Petersburg"

block_3d       — Gradient face, deep extrusion, reliable bold workhorse.
                 Best for: confident assertive titles, mid-energy versatile catch-all.
                 Examples: "Turning Up the Heat in St. Louis", "Muay Thai Knockout in Phuket"

script         — Cursive/brush font, warm gradient fill, thick outline, inner glow shadow.
                 Best for: sensual, romantic, intimate, tender, feminine titles.
                 Examples: "Sensual Aura", "Deep Devotion", "Less Rush More Feel", "A Scented Undressing"

retro_rainbow  — Per-layer hue-cycling extrusion, geometric retro font, pop-art energy.
                 Best for: puns, wordplay, retro vibes, fun double-meaning titles.
                 Examples: "Rave & Misbehave", "Spring Break-ing the Bed", "Vanilla Is a Spice"

chrome         — Liquid-metal chrome gradient, sharp specular highlight, dark shadow.
                 Best for: sleek premium, metallic/sharp/polished titles.
                 Examples: "The Silver Dong", "Clean & Dirty", "Masterstroke in Shenzhen"

stark          — Flat black OR white, no gradient or extrusion, maximum type size.
                 Best for: ultra-minimal 2-4 word raw power titles.
                 Examples: "The Bang", "Wild Ride", "Going Down", "Rubbing It"

vintage        — Warm sepia/cream tones, aged ornamental serif, distressed texture feel.
                 Best for: old-world charm, nostalgic, refined, heritage-adjacent titles.
                 Examples: "Royal Treatment in Ashanti", "The Dutch Tailor of Rotterdam", "Lucky Passage in Liepāja"

spray_stencil  — Raw stencil-cut letterforms, spray overspray edges, urban street art.
                 Best for: raw/gritty/underground energy, attitude-heavy short titles.
                 Examples: "Getting Nasty in Albuquerque", "Backdoor Channeling in Kyiv", "Pain & Gain in Prague"

liquid_gold    — Molten amber/gold pour gradient, warm light, different from silver chrome.
                 Best for: indulgent, opulent, warm-luxury, honey/cream titles.
                 Examples: "Oily Privatization", "Spilling Maple in Toronto", "Whipping Dripping Maple"

neon_box       — Text inside a glowing neon rectangle frame, sign-style.
                 Best for: club/bar/venue energy, nightlife, boxed title treatment.
                 Examples: "Strip View in Vegas", "Mardi Gras in NOLA", "Rave & Misbehave"

glitch         — RGB channel split, horizontal slice corruption, digital scanlines.
                 Best for: cyber/hacker/glitchy/distorted/error-themed titles.
                 Examples: "Signal Lost", "System Failure in Progress", "Pixel Corruption Protocol"

holographic    — Diagonal diagonal rainbow cycling across the text, iridescent prismatic sheen.
                 Best for: ethereal/cosmic/dreamlike/fantasy/celestial titles.
                 Examples: "Crystal Dreams in Oslo", "Aurora Borealis Kiss", "Prismatic Views of Tokyo"

fire           — White-to-orange-to-red burning gradient, multi-layer flame glow, smoke shadow.
                 Best for: hot/burning/scorching/blazing/intense heat titles.
                 Examples: "Body on Fire in Phoenix", "Playing with Fire", "Trial by Fire in Tbilisi"

ice            — White-to-crystal-blue frozen gradient, frost spike edges, cold blue glow.
                 Best for: cold/frozen/winter/arctic/chill titles.
                 Examples: "Breaking the Ice in Helsinki", "Frozen in Reykjavik", "Cold as Ice"

comic          — Very thick black outline, flat vivid color fill, hard angled shadow, pop-art.
                 Best for: energetic/fun/action-packed titles with POW energy, humor, over-the-top.
                 Examples: "Holy Cow!", "Pow Right in the Kisser", "Kapow in Kansas City"

drip           — Vivid flat fill with painted drip trails hanging below letters, street art mess.
                 Best for: melting/dripping/wet/painted/messy/saturated energy titles.
                 Examples: "Let It Drip", "Wet Paint in Warsaw", "Slow Pour in São Paulo"

outline_glow   — Hollow text with only the glowing neon outline visible, completely transparent fill.
                 Best for: ghost/phantom/minimal/overlay/see-through/spectral titles.
                 Examples: "Ghost of a Chance", "Neon Ghost in Nagoya", "The Phantom Stroke"

movie_title    — Wide-tracked uppercase, warm gold-to-red cinematic gradient, deep bevel extrusion.
                 Best for: Hollywood epic/prestige film-title energy, named productions, premieres.
                 Examples: "The Untold Story", "World Premiere Event", "A Legend Returns"

glitter        — Sparkling pastel gradient base with scattered bright sparkle particle highlights.
                 Best for: glamour/diva/feminine/sparkly/luxury/princess titles.
                 Examples: "All That Glitters", "Diamond in the Rough", "Sequin Dreams in Monaco"

psychedelic    — Per-word hue-cycling vivid rainbow, acid-saturated colors, warped retro-3D extrusion.
                 Best for: trippy/acid/festival/surreal/kaleidoscope/mind-bending titles.
                 Examples: "Third Eye Open", "Mind Expanding in Amsterdam", "Color Me Crazy"
"""

# ── Ollama helpers ───────────────────────────────────────────────────────────

def ollama_list_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags",
                                     headers={"User-Agent": "cta-learn/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:
        return []

def ollama_chat(model: str, prompt: str, system: str = "") -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system} if system else None,
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.9},
    }).encode()
    payload = json.dumps({
        "model": model,
        "messages": [m for m in [
            {"role": "system", "content": system} if system else None,
            {"role": "user",   "content": prompt},
        ] if m],
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.9},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "cta-learn/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["message"]["content"]

def pick_model() -> str | None:
    available = ollama_list_models()
    if not available:
        return None
    for m in [PREFERRED_MODEL, FALLBACK_MODEL]:
        if any(m in a for a in available):
            return m
    return available[0]

# ── Classifier ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a professional VR adult content title designer.
Your job: given a scene title, choose the best visual text treatment and color scheme
for a transparent PNG title card used in video trailers.

{TREATMENT_DESCRIPTIONS}

Color schemes available:
fire (red/orange hot), ice (blue/white cool), gold (warm luxurious), silver (neutral metallic),
rose (pink feminine), violet (purple mystical), cyan (neon electric), lime (fresh green),
coral (warm orange), amber (golden honey), pink (soft feminine), teal (aqua cool),
sunset (orange/purple dusk), cream (soft ivory warm)

You MUST respond with valid JSON only — no explanation, no markdown, no extra text.
Format: {{"treatment": "<name>", "color_scheme": "<name>", "reasoning": "<one sentence>"}}"""

def classify_title(title: str, model: str) -> dict | None:
    prompt = f'Scene title: "{title}"\n\nChoose the best treatment and color scheme.'
    try:
        raw = ollama_chat(model, prompt, SYSTEM_PROMPT)
        # Extract JSON from response (model may wrap in markdown)
        match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group())
        t = data.get("treatment", "").lower().strip()
        c = data.get("color_scheme", "").lower().strip()
        r = data.get("reasoning", "").strip()
        if t not in TREATMENTS:
            # Try to find closest match
            for tr in TREATMENTS:
                if tr in t or t in tr:
                    t = tr
                    break
            else:
                return None
        if c not in COLOR_SCHEMES:
            c = "gold"  # safe fallback
        return {"treatment": t, "color_scheme": c, "reasoning": r, "model": model}
    except Exception as e:
        return None

# ── Sheet fetch ──────────────────────────────────────────────────────────────

def fetch_all_titles() -> list[str]:
    url = (f"https://docs.google.com/spreadsheets/d/{GRAIL_SHEET_ID}"
           f"/export?format=csv&gid=0")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = list(csv.reader(io.StringIO(r.read().decode("utf-8"))))
    return [r[3].strip() for r in rows[1:] if len(r) > 3 and r[3].strip()]

# ── Load / save ──────────────────────────────────────────────────────────────

def load_learned() -> dict:
    if LEARNED_FILE.exists():
        try:
            return json.loads(LEARNED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_learned(data: dict):
    LEARNED_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                            encoding="utf-8")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM-powered CTA treatment classifier")
    parser.add_argument("--update",  action="store_true",
                        help="Only classify titles not already in learned_routes.json")
    parser.add_argument("--title",   help="Classify a single title and print result")
    parser.add_argument("--show",    action="store_true", help="Print all learned routes")
    parser.add_argument("--stats",   action="store_true", help="Show treatment distribution")
    parser.add_argument("--reclassify", metavar="TITLE",
                        help="Force re-classify one specific title")
    parser.add_argument("--from-file", metavar="PATH",
                        help="Classify titles from a JSON file with a 'titles' array "
                             "(e.g. adobe_stock_titles.json). Saves to learned_routes.json.")
    args = parser.parse_args()

    learned = load_learned()

    if args.show:
        for title, info in sorted(learned.items()):
            print(f"  [{info['treatment']:14s}] [{info.get('color_scheme','?'):8s}]  {title}")
        print(f"\n{len(learned)} titles classified.")
        return

    if args.stats:
        from collections import Counter
        tc = Counter(v["treatment"] for v in learned.values())
        cc = Counter(v.get("color_scheme","?") for v in learned.values())
        print("\nTreatment distribution:")
        for t, n in tc.most_common():
            bar = "█" * (n * 30 // max(tc.values()))
            print(f"  {t:16s} {n:3d}  {bar}")
        print("\nColor scheme distribution:")
        for c, n in cc.most_common():
            bar = "█" * (n * 30 // max(cc.values()))
            print(f"  {c:10s} {n:3d}  {bar}")
        return

    # Check Ollama connectivity
    model = pick_model()
    if not model:
        print("✗  Cannot reach Ollama at", OLLAMA_BASE)
        print("   Make sure the SSH tunnel is open:")
        print("   ssh -i ~/.ssh/id_ed25519_win -L 11434:127.0.0.1:11434 -N -f andre@100.90.90.68")
        sys.exit(1)
    print(f"✓  Ollama reachable — using model: {model}\n")

    # Single title
    if args.title:
        result = classify_title(args.title, model)
        if result:
            print(json.dumps({args.title: result}, indent=2))
            learned[args.title] = result
            save_learned(learned)
        else:
            print("✗  Classification failed")
        return

    if args.reclassify:
        result = classify_title(args.reclassify, model)
        if result:
            learned[args.reclassify] = result
            save_learned(learned)
            print(f"✓  {args.reclassify} → {result['treatment']} / {result['color_scheme']}")
            print(f"   {result['reasoning']}")
        else:
            print("✗  Classification failed")
        return

    # From-file mode: classify titles from an external JSON file
    if args.from_file:
        src = Path(args.from_file)
        if not src.exists():
            print(f"✗  File not found: {src}")
            sys.exit(1)
        file_titles = json.loads(src.read_text(encoding="utf-8"))
        if isinstance(file_titles, dict):
            file_titles = file_titles.get("titles", [])
        todo = [t for t in file_titles if t not in learned]
        print(f"Loaded {len(file_titles)} titles from {src.name}.")
        print(f"{len(todo)} new titles to classify ({len(learned)} already done).\n")
        ok = 0; failed = []
        for i, title in enumerate(todo, 1):
            sys.stdout.write(f"  [{i:3d}/{len(todo)}] {title[:55]:<55s}  ")
            sys.stdout.flush()
            result = classify_title(title, model)
            if result:
                learned[title] = result
                print(f"→ {result['treatment']:14s} / {result['color_scheme']}")
                ok += 1
                if ok % 10 == 0:
                    save_learned(learned)
            else:
                print("✗ FAILED")
                failed.append(title)
            time.sleep(0.1)
        save_learned(learned)
        print(f"\n✓  Done. {ok}/{len(todo)} classified → {LEARNED_FILE}")
        if failed:
            print(f"   Failed ({len(failed)}): {failed[:5]}")
        return

    # Batch mode: all titles from sheet
    titles = fetch_all_titles()
    print(f"Fetched {len(titles)} titles from Grail sheet.")

    if args.update:
        todo = [t for t in titles if t not in learned]
        print(f"{len(todo)} new titles to classify ({len(learned)} already done).\n")
    else:
        todo = titles
        print(f"Classifying all {len(todo)} titles (use --update to skip existing).\n")

    ok = 0
    failed = []
    for i, title in enumerate(todo, 1):
        sys.stdout.write(f"  [{i:3d}/{len(todo)}] {title[:55]:<55s}  ")
        sys.stdout.flush()
        result = classify_title(title, model)
        if result:
            learned[title] = result
            print(f"→ {result['treatment']:14s} / {result['color_scheme']}")
            ok += 1
            # Save every 10 titles so progress isn't lost on interrupt
            if ok % 10 == 0:
                save_learned(learned)
        else:
            print("✗ FAILED")
            failed.append(title)
        time.sleep(0.1)  # small pause to not hammer the GPU

    save_learned(learned)
    print(f"\n✓  Done. {ok}/{len(todo)} classified → {LEARNED_FILE}")
    if failed:
        print(f"   Failed ({len(failed)}): {failed[:5]}")

if __name__ == "__main__":
    main()
