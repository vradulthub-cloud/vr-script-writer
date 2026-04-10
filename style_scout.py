#!/usr/bin/env python3
"""
style_scout.py — Autonomous Adobe Stock visual style discovery and treatment generator.

Pipeline:
  1. fetch   — scrape Adobe Stock template thumbnails + metadata via browser session
  2. analyze — download thumbs, run llava vision analysis, save style observations
  3. generate — LLM writes new render_X() functions for novel unseen styles
  4. integrate — test + merge approved functions into cta_generator.py
  5. loop    — runs all steps in sequence (fetch→analyze→generate→integrate)

Usage:
  python3 style_scout.py fetch [--keywords "neon text,chrome,glitch"] [--pages 3]
  python3 style_scout.py analyze [--limit 80] [--vision llava:7b]
  python3 style_scout.py generate [--count 5] [--coder qwen2.5:14b]
  python3 style_scout.py integrate [--dry-run]
  python3 style_scout.py loop [--rounds 2]

Requires:
  - SSH tunnel to Windows Ollama: ssh -i ~/.ssh/id_ed25519_win -L 11434:127.0.0.1:11434 -N -f andre@100.90.90.68
  - llava:7b installed on Windows  (ollama pull llava:7b)
  - qwen2.5-coder:14b installed on Windows (ollama pull qwen2.5-coder:14b)
  - requests, Pillow, numpy (already installed for cta_generator)
"""

import argparse, base64, hashlib, json, os, random, re, subprocess, sys, textwrap, time
import urllib.request
from pathlib import Path

import requests
from PIL import Image

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR      = Path(__file__).parent
TEMPLATES_FILE  = SCRIPT_DIR / "stock_templates.json"
ANALYSIS_FILE   = SCRIPT_DIR / "style_analysis.json"
PENDING_FILE    = SCRIPT_DIR / "pending_treatments.json"
THUMBS_DIR      = SCRIPT_DIR / "stock_thumbs"
THUMBS_DIR.mkdir(exist_ok=True)
CTA_FILE        = SCRIPT_DIR / "cta_generator.py"

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE    = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
VISION_MODEL   = "llava:7b"
CODER_MODEL    = "qwen2.5-coder:14b"

# ── Adobe Stock search keywords ───────────────────────────────────────────────
DEFAULT_KEYWORDS = [
    "text effect photoshop", "neon text effect", "chrome text effect",
    "glitch text effect",    "retro text effect", "gold text effect",
    "3d text effect",        "grunge text effect","watercolor text effect",
    "holographic text",      "fire text effect",  "ice text effect",
    "vintage text effect",   "comic text effect", "marble text effect",
    "smoke text effect",     "rainbow text effect","metallic text effect",
    "neon sign text",        "graffiti text",     "liquid text effect",
    "glitter text effect",   "horror text effect","sci-fi text effect",
    "spray paint text",      "stamp text effect", "pixel art text",
    "foil text effect",      "sand text effect",  "electric text effect",
]

# ── Treatments already in the library (auto-updated by integrate) ─────────────
def get_existing_treatments() -> set:
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import importlib
        if 'cta_generator' in sys.modules:
            importlib.reload(sys.modules['cta_generator'])
        import cta_generator
        return set(cta_generator.TREATMENTS.keys())
    except Exception as e:
        print(f"  [warn] Could not load cta_generator treatments: {e}")
        return set()


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — FETCH
# ═══════════════════════════════════════════════════════════════════════════════

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://stock.adobe.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

def _parse_blob(html: str) -> list:
    """Extract template records from Adobe Stock search HTML (schema.org microdata structure)."""
    templates = []
    seen = set()
    # Primary: data-content-id + itemprop="name" + itemprop="thumbnailUrl" in same block
    pat = re.compile(
        r'data-content-id="(\d+)"[\s\S]{0,800}?'
        r'itemprop="name"\s+content="([^"]+)"[\s\S]{0,400}?'
        r'itemprop="thumbnailUrl"\s+content="([^"]+)"'
    )
    for m in pat.finditer(html):
        cid, title, thumb = m.group(1), m.group(2), m.group(3)
        if cid not in seen and thumb and title:
            seen.add(cid)
            templates.append({"id": cid, "title": title, "thumb_url": thumb})

    # Fallback: legacy JS JSON blob
    if not templates:
        for m in re.finditer(r'"(\d{7,12})"\s*:\s*(\{[^}{]{80,3000}\})', html):
            try:
                obj = json.loads(m.group(2))
            except Exception:
                continue
            thumb = obj.get("content_thumb_large_url") or obj.get("content_thumb_extra_large_url")
            title = obj.get("title", "")
            cid = str(obj.get("content_id", m.group(1)))
            if thumb and title and cid not in seen:
                seen.add(cid)
                templates.append({"id": cid, "title": title, "thumb_url": thumb,
                                   "author": obj.get("author", "")})
    return templates


def fetch_keyword(keyword: str, pages: int = 3, session: requests.Session = None) -> list:
    """Fetch template metadata for a keyword across N pages."""
    if session is None:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)

    kw_enc = urllib.parse.quote_plus(keyword) if hasattr(urllib, 'parse') else keyword.replace(' ','+')
    templates = []
    seen_ids  = set()

    for page in range(1, pages + 1):
        url = (
            f"https://stock.adobe.com/search/templates"
            f"?filters%5Bcontent_type%3Atemplate%5D=1"
            f"&k={kw_enc}&limit=100&search_page={page}"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                print(f"    [{keyword} p{page}] HTTP {resp.status_code} — skipping")
                break
            page_templates = _parse_blob(resp.text)
            new = [t for t in page_templates if t["id"] not in seen_ids]
            seen_ids.update(t["id"] for t in new)
            templates.extend(new)
            print(f"    [{keyword} p{page}] +{len(new)} templates (total {len(templates)})")
            if not new:
                break
            time.sleep(random.uniform(5, 9))
        except Exception as e:
            print(f"    [{keyword} p{page}] error: {e}")
            break

    return templates


def cmd_fetch(args):
    """Fetch Adobe Stock template metadata and save to stock_templates.json."""
    import urllib.parse

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] \
               if args.keywords else DEFAULT_KEYWORDS
    pages    = args.pages

    print(f"Fetching {len(keywords)} keywords × {pages} pages …")

    # Load existing so we don't lose prior data
    existing = {}
    if TEMPLATES_FILE.exists():
        for t in json.loads(TEMPLATES_FILE.read_text()):
            existing[t["id"]] = t

    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    for kw in keywords:
        print(f"  keyword: {kw}")
        new = fetch_keyword(kw, pages, session)
        for t in new:
            existing[t["id"]] = t
        time.sleep(random.uniform(8, 15))

    all_templates = list(existing.values())
    TEMPLATES_FILE.write_text(json.dumps(all_templates, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(all_templates)} templates → {TEMPLATES_FILE}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — ANALYZE (vision)
# ═══════════════════════════════════════════════════════════════════════════════

VISION_PROMPT = """You are a graphic design analyst. Look at this text effect / typography template thumbnail.

Describe the visual treatment in structured JSON with these exact fields:

{
  "effect_name": "short slug like neon_outline or burnt_parchment",
  "primary_effect": "the dominant visual treatment in 5-10 words",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "gradient_direction": "top-to-bottom | diagonal | radial | none",
  "font_style": "serif | sans | script | display | decorative | condensed | slab",
  "outline_style": "none | thin | thick | double | glow",
  "shadow_type": "none | drop | inner | long | hard",
  "texture": "none | grain | grunge | metallic | paper | fabric | stone | digital",
  "glow": "none | soft | hard | multi-layer | bloom",
  "special_fx": ["list", "of", "effects", "like", "rgb_split", "scanlines", "drips"],
  "3d_depth": "none | subtle | medium | extreme",
  "mood": "dark | light | bold | subtle | retro | futuristic | organic | industrial",
  "novelty_score": 0-10,
  "description": "2-sentence description of how to recreate this in PIL/NumPy"
}

Respond with ONLY valid JSON, no markdown.
"""

def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def analyze_thumbnail(template: dict, vision_model: str = VISION_MODEL) -> dict | None:
    """Send a thumbnail to llava and get a structured style observation."""
    tid   = str(template["id"])
    thumb = THUMBS_DIR / f"{tid}.jpg"

    # Download if needed
    if not thumb.exists():
        try:
            r = requests.get(template["thumb_url"], timeout=15,
                             headers={"User-Agent": BROWSER_HEADERS["User-Agent"]})
            if r.status_code == 200:
                thumb.write_bytes(r.content)
            else:
                print(f"    [{tid}] download HTTP {r.status_code}")
                return None
        except Exception as e:
            print(f"    [{tid}] download error: {e}")
            return None

    # Resize to keep payload small (llava works fine at 512px)
    try:
        img = Image.open(thumb).convert("RGB")
        img.thumbnail((512, 512), Image.LANCZOS)
        buf_path = THUMBS_DIR / f"{tid}_sm.jpg"
        img.save(buf_path, "JPEG", quality=85)
        img_b64 = _encode_image(buf_path)
    except Exception as e:
        print(f"    [{tid}] image error: {e}")
        return None

    # Call Ollama llava
    payload = {
        "model": vision_model,
        "prompt": VISION_PROMPT,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 600},
    }
    try:
        resp = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=90)
        resp.raise_for_status()
        text = resp.json().get("response", "")
    except Exception as e:
        print(f"    [{tid}] vision error: {e}")
        return None

    # Extract JSON from response
    m = re.search(r'\{[\s\S]+\}', text)
    if not m:
        return None
    try:
        obs = json.loads(m.group(0))
    except Exception:
        return None

    obs["source_id"]    = tid
    obs["source_title"] = template.get("title", "")
    obs["thumb_url"]    = template.get("thumb_url", "")
    return obs


def cmd_analyze(args):
    """Download thumbnails and run vision analysis on each."""
    if not TEMPLATES_FILE.exists():
        print("No stock_templates.json found. Run: python3 style_scout.py fetch")
        return

    templates = json.loads(TEMPLATES_FILE.read_text())
    limit = args.limit or len(templates)
    templates = templates[:limit]

    # Load existing analyses
    existing = {}
    if ANALYSIS_FILE.exists():
        for obs in json.loads(ANALYSIS_FILE.read_text()):
            existing[obs.get("source_id")] = obs

    vision_model = args.vision or VISION_MODEL
    print(f"Analyzing {len(templates)} templates with {vision_model} …")
    print(f"  (Ollama at {OLLAMA_BASE})")

    new_count = 0
    for i, tmpl in enumerate(templates):
        tid = str(tmpl["id"])
        if tid in existing:
            continue  # already analyzed

        print(f"  [{i+1}/{len(templates)}] {tmpl['title'][:50]}")
        obs = analyze_thumbnail(tmpl, vision_model)
        if obs:
            existing[tid] = obs
            new_count += 1
            print(f"    → {obs.get('primary_effect','?')} | novelty={obs.get('novelty_score','?')}")

        # Checkpoint every 10
        if new_count % 10 == 0 and new_count > 0:
            ANALYSIS_FILE.write_text(json.dumps(list(existing.values()), indent=2))

    ANALYSIS_FILE.write_text(json.dumps(list(existing.values()), indent=2))
    print(f"\nAnalyzed {new_count} new templates → {ANALYSIS_FILE}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — GENERATE (code)
# ═══════════════════════════════════════════════════════════════════════════════

CODEGEN_SYSTEM = """You are an expert Python graphics programmer who writes PIL/NumPy text effect renderers.
You will be given a style observation from Adobe Stock and must write a new render function for cta_generator.py.

AVAILABLE HELPERS (already imported, do NOT redefine):
- make_mask(ln, font, pad=14) → Image "L" — renders text as alpha mask
- wide_track_mask(ln, font, spacing, pad=14) → Image "L" — wide letter-spaced mask
- colorize(mask, stops) → RGBA — vertical gradient fill (stops = list of RGB tuples)
- flat_color(mask, rgb, alpha=255) → RGBA — solid color fill
- dilate(mask, px) → Image "L" — expand mask by px pixels (for stroke/glow base)
- extrude(mask, depth, angle_deg, top_color, bottom_color) → RGBA — 3D extrusion
- glow_layer(mask, rgb, radii=[(r,a),...]) → RGBA — soft bloom layers
- drop_shadow(mask, ox, oy, blur=12, alpha=150) → RGBA — drop shadow
- highlight(mask, strength=0.45) → RGBA — top white specular shimmer
- composite(*layers, size) → RGBA — alpha-composite all layers bottom-to-top
- F(role, size, rng=None) → ImageFont — picks font by role ('heavy','condensed','elegant','script','marker','retro','tech','rounded')
- wrap_chars(title, max_chars) → list of str — wraps title into lines
- VIVID_BANKS — list of color palettes, each is list of RGB tuples
- ImageDraw, ImageFilter — PIL modules, already imported
- np — numpy, already imported
- colorsys — already imported
- rng — random.Random instance passed in

RULES:
1. Signature: def render_X(title: str, rng: random.Random) -> Image.Image
2. Must return an RGBA Image.
3. NEVER hardcode canvas size. Always derive size from make_mask(): mask = make_mask(title, font); W, H = mask.size
4. composite() REQUIRES the keyword arg size=: composite(layer1, layer2, size=(W,H))
5. Do NOT define inner helper functions — use only the helpers listed above.
6. Do NOT use ImageFilter.Kernel() — use ImageFilter.GaussianBlur(r) instead.
7. No imports inside the function — everything is already available.
8. Name must be render_ + short_descriptive_snake_case.
9. Output ONLY the Python function definition, no markdown, no explanation.

MINIMAL WORKING TEMPLATE (follow this pattern):
def render_example(title: str, rng: random.Random) -> Image.Image:
    font = F('heavy', 120, rng=rng)
    mask = make_mask(title, font)
    W, H = mask.size
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    layer1 = colorize(mask, [(255, 100, 0), (255, 200, 0)])
    layer2 = glow_layer(mask, (255, 80, 0), [(14, 180)])
    return composite(bg, layer2, layer1, size=(W, H))
"""

CODEGEN_PROMPT_TEMPLATE = """Create a new render function based on this Adobe Stock style observation.

EXISTING TREATMENTS TO AVOID DUPLICATING:
{existing_list}

STYLE OBSERVATION:
{observation}

Write a visually UNIQUE render_X() function that captures this style. Be creative with the implementation.
Output ONLY the Python function definition."""


def generate_render_function(obs: dict, coder_model: str, existing: set) -> tuple[str, str] | None:
    """Ask the LLM to write a render function for this style. Returns (name, code) or None."""
    existing_list = "\n".join(f"  - {t}" for t in sorted(existing))
    obs_str = json.dumps({k: v for k, v in obs.items()
                          if k not in ("source_id","source_title","thumb_url")}, indent=2)

    prompt = CODEGEN_PROMPT_TEMPLATE.format(
        existing_list=existing_list,
        observation=obs_str,
    )

    payload = {
        "model": coder_model,
        "system": CODEGEN_SYSTEM,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.4, "num_predict": 1800},
    }
    try:
        resp = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=180)
        resp.raise_for_status()
        code = resp.json().get("response", "")
    except Exception as e:
        print(f"    [codegen] error: {e}")
        return None

    # Extract function name
    m = re.search(r'def (render_\w+)\(', code)
    if not m:
        print("    [codegen] no function found in response")
        return None
    name = m.group(1).replace("render_", "")   # strip prefix for TREATMENTS key
    # Clean: keep only from 'def render_...' onward
    start = code.index(m.group(0))
    code  = code[start:].strip()
    # Strip any trailing markdown
    code  = re.split(r'\n```', code)[0].strip()

    return name, code


def validate_render(name: str, code: str) -> str | None:
    """
    Try to exec the render function in cta_generator's context and render a test title.
    Returns error string if failed, None if passed.
    """
    test_script = textwrap.dedent(f"""
import sys, random
sys.path.insert(0, '{SCRIPT_DIR}')
import cta_generator as _cg
_globals = dict(vars(_cg))
_exec_code = {repr(code)}
exec(_exec_code, _globals)
fn = _globals.get('render_{name}')
if fn is None:
    raise RuntimeError('Function render_{name} not found after exec')
img = fn('Test Title Night', random.Random(42))
assert img.mode == 'RGBA', f'Expected RGBA, got {{img.mode}}'
assert img.width > 50 and img.height > 20, f'Image too small: {{img.size}}'
print('OK', img.size)
""")
    try:
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return (result.stderr or result.stdout).strip()[:400]
        return None
    except subprocess.TimeoutExpired:
        return "Timeout"
    except Exception as e:
        return str(e)


def _cluster_novel(observations: list, existing: set, min_novelty: int = 5) -> list:
    """Pick observations that represent styles NOT already in the library, deduped."""
    # Filter by novelty score
    novel = [o for o in observations
             if o.get("novelty_score", 0) >= min_novelty
             and o.get("effect_name", "").replace("-","_") not in existing]

    # Deduplicate by effect_name
    seen_effects = set()
    unique = []
    for o in sorted(novel, key=lambda x: -x.get("novelty_score", 0)):
        ename = o.get("effect_name", "")[:20]
        if ename and ename not in seen_effects:
            seen_effects.add(ename)
            unique.append(o)

    return unique


def cmd_generate(args):
    """Generate render functions for novel styles found in style_analysis.json."""
    if not ANALYSIS_FILE.exists():
        print("No style_analysis.json. Run: python3 style_scout.py analyze")
        return

    observations = json.loads(ANALYSIS_FILE.read_text())
    existing     = get_existing_treatments()
    coder_model  = args.coder or CODER_MODEL
    count        = args.count or 5

    novel = _cluster_novel(observations, existing)
    print(f"Found {len(novel)} novel styles (from {len(observations)} observations)")
    print(f"Generating up to {count} render functions with {coder_model} …\n")

    # Load pending
    pending = {}
    if PENDING_FILE.exists():
        pending = json.loads(PENDING_FILE.read_text())

    generated = 0
    for obs in novel[:count * 3]:  # try 3× candidates to hit the count target
        if generated >= count:
            break
        src = obs.get("source_title", "?")[:40]
        eff = obs.get("primary_effect", "?")
        print(f"  [{generated+1}] {eff} (from: {src})")

        result = generate_render_function(obs, coder_model, existing)
        if not result:
            continue
        name, code = result
        print(f"    → render_{name}()")

        err = validate_render(name, code)
        if err:
            print(f"    ✗ validation failed: {err[:120]}")
            continue

        print(f"    ✓ passes validation")
        pending[name] = {
            "code":          code,
            "source_obs":    obs,
            "generated_at":  time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        generated += 1
        existing.add(name)   # don't generate duplicates in same run

    PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False))
    print(f"\nGenerated {generated} functions → {PENDING_FILE}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — INTEGRATE
# ═══════════════════════════════════════════════════════════════════════════════

TREATMENTS_ANCHOR = '# ── Treatment registry ────────────────────────────────────────────────────────'
KEYWORD_ANCHOR    = '# ── Keyword routing ───────────────────────────────────────────────────────────'

def _build_keywords_from_obs(name: str, obs: dict) -> list:
    """Auto-generate keyword routing hints from the style observation."""
    kws = []
    eff = obs.get("primary_effect","").lower()
    fx  = [f.lower() for f in obs.get("special_fx", [])]
    mood = obs.get("mood","").lower()
    texture = obs.get("texture","").lower()

    kws.extend(eff.split())
    kws.extend(fx)
    if mood: kws.append(mood)
    if texture and texture != "none": kws.append(texture)
    # Deduplicate, strip short words
    kws = list(dict.fromkeys(k for k in kws if len(k) > 3))[:20]
    return kws


def cmd_integrate(args):
    """Test pending functions and inject approved ones into cta_generator.py."""
    if not PENDING_FILE.exists():
        print("No pending_treatments.json. Run: python3 style_scout.py generate")
        return

    pending = json.loads(PENDING_FILE.read_text())
    if not pending:
        print("No pending treatments to integrate.")
        return

    cta_src = CTA_FILE.read_text(encoding="utf-8")
    existing = get_existing_treatments()
    integrated = []

    for name, entry in list(pending.items()):
        code = entry["code"]
        obs  = entry.get("source_obs", {})

        if name in existing:
            print(f"  skip {name} — already in library")
            continue

        print(f"  integrating render_{name}() …")
        if args.dry_run:
            print(f"    [dry-run] would add render_{name}")
            continue

        # Re-validate
        err = validate_render(name, code)
        if err:
            print(f"    ✗ validation error: {err[:120]}")
            continue

        # 1. Insert render function before the registry anchor
        code_block = f"\n\n{code}\n"
        cta_src = cta_src.replace(
            TREATMENTS_ANCHOR,
            code_block + TREATMENTS_ANCHOR
        )

        # 2. Add to TREATMENTS dict (find last entry before closing brace)
        m = re.search(r'(    "(\w+)":\s+render_\w+,?\n)\}', cta_src[-3000:])
        insert_after = f'    "{name}": render_{name},\n'
        # Find last treatment entry and append after it
        last_entry_pat = re.compile(r'(\s+"[^"]+"\s*:\s*render_\w+,?\n)(\})', re.MULTILINE)
        cta_src = last_entry_pat.sub(
            lambda mo: mo.group(1) + insert_after + mo.group(2),
            cta_src, count=1
        )

        # 3. Add keyword routing (append before closing } of KEYWORD_TREATMENT)
        kws = _build_keywords_from_obs(name, obs)
        kw_block = (
            f'    "{name}": [\n'
            + f'        ' + ', '.join(f'"{k}"' for k in kws) + ',\n'
            + f'    ],\n'
        )
        # Insert before last } of KEYWORD_TREATMENT block
        kw_close = re.compile(r'(\n\})\n\n# Phrase-level')
        cta_src = kw_close.sub(
            lambda mo: '\n' + kw_block + mo.group(0).lstrip('\n'),
            cta_src, count=1
        )

        CTA_FILE.write_text(cta_src, encoding="utf-8")
        integrated.append(name)
        existing.add(name)
        print(f"    ✓ render_{name} integrated")

    # Remove integrated from pending
    if not args.dry_run:
        for name in integrated:
            pending.pop(name, None)
        PENDING_FILE.write_text(json.dumps(pending, indent=2))

    print(f"\nIntegrated {len(integrated)} treatments.")
    if integrated:
        print("  Run: python3 cta_generator.py <title> to test")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_loop(args):
    """Run the full pipeline in sequence: fetch → analyze → generate → integrate."""
    rounds = args.rounds or 1
    for r in range(rounds):
        print(f"\n{'='*60}")
        print(f"  ROUND {r+1}/{rounds}")
        print(f"{'='*60}")

        # Rotate through keyword sets so we explore new territory
        offset = r * 5
        kw_slice = DEFAULT_KEYWORDS[offset % len(DEFAULT_KEYWORDS):]
        kw_slice = kw_slice[:8]

        fetch_args   = argparse.Namespace(keywords=",".join(kw_slice), pages=2)
        analyze_args = argparse.Namespace(limit=60, vision=args.vision or VISION_MODEL)
        generate_args= argparse.Namespace(count=4, coder=args.coder or CODER_MODEL)
        integrate_args=argparse.Namespace(dry_run=False)

        cmd_fetch(fetch_args)
        cmd_analyze(analyze_args)
        cmd_generate(generate_args)
        cmd_integrate(integrate_args)

    print("\nLoop complete.")


# ═══════════════════════════════════════════════════════════════════════════════
# BONUS — SHOW STATS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_stats(_args):
    existing = get_existing_treatments()
    print(f"Treatments in library: {len(existing)}")
    for t in sorted(existing): print(f"  {t}")

    if TEMPLATES_FILE.exists():
        t = json.loads(TEMPLATES_FILE.read_text())
        print(f"\nStock templates fetched: {len(t)}")

    if ANALYSIS_FILE.exists():
        a = json.loads(ANALYSIS_FILE.read_text())
        print(f"Style observations:      {len(a)}")
        effects = {}
        for obs in a:
            e = obs.get("primary_effect","?")[:40]
            effects[e] = effects.get(e, 0) + 1
        print("\nTop 15 observed effects:")
        for eff, cnt in sorted(effects.items(), key=lambda x: -x[1])[:15]:
            print(f"  {cnt:3d}×  {eff}")

    if PENDING_FILE.exists():
        p = json.loads(PENDING_FILE.read_text())
        print(f"\nPending (unintegrated): {len(p)}")
        for n in p: print(f"  render_{n}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Adobe Stock style scout → cta_generator treatment pipeline")
    sub = ap.add_subparsers(dest="cmd")

    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("--keywords", help="Comma-separated keywords (default: built-in list)")
    p_fetch.add_argument("--pages", type=int, default=2, help="Pages per keyword (default 2)")

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("--limit", type=int, help="Max templates to analyze")
    p_analyze.add_argument("--vision", default=VISION_MODEL, help="Ollama vision model")

    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--count", type=int, default=5)
    p_gen.add_argument("--coder", default=CODER_MODEL)

    p_int = sub.add_parser("integrate")
    p_int.add_argument("--dry-run", action="store_true")

    p_loop = sub.add_parser("loop")
    p_loop.add_argument("--rounds", type=int, default=1)
    p_loop.add_argument("--vision", default=VISION_MODEL)
    p_loop.add_argument("--coder", default=CODER_MODEL)

    sub.add_parser("stats")

    args = ap.parse_args()
    {
        "fetch":    cmd_fetch,
        "analyze":  cmd_analyze,
        "generate": cmd_generate,
        "integrate":cmd_integrate,
        "loop":     cmd_loop,
        "stats":    cmd_stats,
    }.get(args.cmd, lambda _: ap.print_help())(args)


if __name__ == "__main__":
    main()
