import io
import os
import re
import time
import requests as _requests
import streamlit as st
from script_writer import (
    SYSTEM_PROMPT, build_prompt, NJOI_STATIC_PLOT,
    validate_script, get_ollama_client, OLLAMA_BASE_URL, OLLAMA_MODEL,
    research_scene_trends,
)

# ── Title refinement helper ────────────────────────────────────────────────────
def _refine_treatment(treatment_name: str, png_bytes: bytes, prompt: str, title: str, seed: int):
    """Apply user style prompt to an existing rendered treatment.
    Fast path: PIL color/brightness transforms for simple keywords.
    Slow path: Ollama rewrites the treatment function for complex requests.
    """
    import re, inspect, requests as _req, random, io, types
    from PIL import Image, ImageEnhance, ImageFilter
    import numpy as np

    prompt_l = prompt.lower().strip()
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    r_ch, g_ch, b_ch, a_ch = img.split()

    # ── Fast path: keyword transforms ─────────────────────────────────────────
    handled = False

    # Brightness
    if any(w in prompt_l for w in ["darker", "dark", "dim"]):
        rgb = Image.merge("RGB", (r_ch, g_ch, b_ch))
        rgb = ImageEnhance.Brightness(rgb).enhance(0.65)
        img = Image.merge("RGBA", (*rgb.split(), a_ch))
        handled = True
    elif any(w in prompt_l for w in ["brighter", "lighter", "light", "bright"]):
        rgb = Image.merge("RGB", (r_ch, g_ch, b_ch))
        rgb = ImageEnhance.Brightness(rgb).enhance(1.45)
        img = Image.merge("RGBA", (*rgb.split(), a_ch))
        handled = True

    # Saturation
    if any(w in prompt_l for w in ["vivid", "vibrant", "saturate", "saturated", "pop"]):
        rgb = Image.merge("RGB", (r_ch, g_ch, b_ch))
        rgb = ImageEnhance.Color(rgb).enhance(1.8)
        img = Image.merge("RGBA", (*rgb.split(), a_ch))
        r_ch, g_ch, b_ch, a_ch = img.split()
        handled = True
    elif any(w in prompt_l for w in ["muted", "desaturate", "faded", "washed"]):
        rgb = Image.merge("RGB", (r_ch, g_ch, b_ch))
        rgb = ImageEnhance.Color(rgb).enhance(0.35)
        img = Image.merge("RGBA", (*rgb.split(), a_ch))
        r_ch, g_ch, b_ch, a_ch = img.split()
        handled = True

    # Color tint
    COLOR_MAP = {
        "gold": (255, 200, 20), "golden": (255, 200, 20),
        "red": (255, 30, 30), "crimson": (180, 0, 30),
        "blue": (30, 100, 255), "electric blue": (0, 160, 255),
        "green": (0, 210, 60), "lime": (120, 255, 0),
        "purple": (160, 0, 255), "violet": (140, 0, 220),
        "pink": (255, 60, 180), "hot pink": (255, 20, 150),
        "orange": (255, 120, 0), "amber": (255, 160, 0),
        "cyan": (0, 220, 255), "teal": (0, 180, 180),
        "silver": (200, 205, 215), "white": (255, 255, 255),
        "black": (20, 20, 20), "yellow": (255, 230, 0),
        "rose": (255, 100, 120), "magenta": (255, 0, 200),
    }
    for color_name, tint_rgb in COLOR_MAP.items():
        if color_name in prompt_l:
            arr = np.array(img).astype(np.float32)
            alpha = arr[:, :, 3:4] / 255.0
            tint = np.array(tint_rgb, dtype=np.float32)
            strength = 0.55
            arr[:, :, :3] = arr[:, :, :3] * (1 - strength * alpha) + tint * strength * alpha
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
            handled = True
            break

    if handled:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), treatment_name + "_refined"

    # ── Slow path: Ollama rewrites the function ────────────────────────────────
    # Strip any _refined suffix to get the original treatment name
    _base_name = re.sub(r"_(ai_)?refined$", "", treatment_name)
    fn = _cta.TREATMENTS.get(_base_name)
    if not fn:
        return None, None
    try:
        source = inspect.getsource(fn)
    except Exception:
        return None, None

    system = """You modify Python PIL graphic treatment functions based on user style requests.
Rules: keep the same function signature, keep transparent RGBA output, use rng for randomization.
Output ONLY the modified Python function — no markdown, no explanation."""

    user_msg = f"""Current function:
{source}

User wants: "{prompt}"

Rewrite the function applying these changes. Function name must stay the same."""

    try:
        resp = _req.post("http://localhost:11434/api/generate", json={
            "model": "qwen2.5:14b",
            "prompt": system + "\n\n" + user_msg,
            "stream": False,
            "options": {"temperature": 0.5, "num_predict": 1400}
        }, timeout=90)
        code = resp.json().get("response", "")
    except Exception:
        return None, None

    # Strip markdown fences
    import re as _re
    code = _re.sub(r"```python\s*", "", code)
    code = _re.sub(r"```\s*", "", code)
    m = _re.search(r"def\s+render_\w+\b", code)
    if not m:
        return None, None
    code = code[m.start():]
    nxt = _re.search(r"\ndef\s+\w", code[5:])
    if nxt:
        code = code[:nxt.start() + 5]

    # Execute the modified function in cta_generator's namespace
    try:
        ns = vars(_cta).copy()
        exec(compile(code, "<refined>", "exec"), ns)
        fn_name = _re.search(r"def\s+(render_\w+)\b", code).group(1)
        refined_fn = ns[fn_name]
        rng = random.Random(seed)
        out_img = refined_fn(title, rng)
        buf = io.BytesIO()
        out_img.save(buf, format="PNG")
        return buf.getvalue(), treatment_name + "_ai_refined"
    except Exception:
        return None, None

try:
    from call_sheet import get_budget_tabs, get_shoot_dates, generate_call_sheet, reload_script_cache
    HAS_CALL_SHEET = True
except ImportError:
    HAS_CALL_SHEET = False

from sheets_integration import (
    get_spreadsheet, month_tabs,
    rows_needing_scripts, write_script, parse_script_text,
    find_row_for_shoot, mark_talent_for_regen,
    STATUS_REGEN,
    COL_DATE, COL_STUDIO, COL_LOCATION, COL_SCENE,
    COL_FEMALE, COL_MALE, COL_PLOT, COL_THEME,
    COL_TITLE,
)

# ── Auto title generation ─────────────────────────────────────────────────────
_TITLE_GEN_SYSTEMS = {
    "VRHush": """You are a creative title writer for VRHush, a premium VR adult content studio.
Generate exactly ONE scene title. Rules:
- 2-3 words ONLY (never more than 3)
- Clever double-entendres, wordplay, or innuendo preferred
- Should hint at the scene's theme/action without being too literal
- Catchy, memorable, punchy — think movie title energy
- No performer names in the title
- No generic titles like "Hot Sex" or "Getting Laid"

Recent VRH titles for style reference: Heat By Design, Born To Breed, Under Her Spell, Intimate Renderings, Risqué Renter, Content Cutie, She Blooms on Command, Nailing the Interview, Kneading Your Pudding, Stretching Her Limits, The Honeymooners, Artists in Love

Respond with ONLY the title — no quotes, no explanation.""",

    "FuckPassVR": """You are a creative title writer for FuckPassVR, a premium VR adult travel/adventure content studio.
Generate exactly ONE scene title. Rules:
- 2-5 words (can be longer than VRH, more narrative)
- Travel/destination themes when applicable
- Clever wordplay, double-entendres preferred
- Should hint at the scene's theme or location
- No performer names in the title

Recent FPVR titles for style reference: The Grind Finale, Eager Beaver, Deep Devotion, Dirty Bunny Dancing, Reserved For Your Eyes, Pressing Dripping Matters, Fully Seated Affair, Fucking Like The Bulls, The Night is Young, Behind the Curtain, The Bouncing Layover

Respond with ONLY the title — no quotes, no explanation.""",

    "VRAllure": """You are a creative title writer for VRAllure, a premium VR solo/intimate content studio.
Generate exactly ONE scene title. Rules:
- 2-3 words ONLY
- Sensual, intimate, soft tone
- Suggestive but elegant — not crass
- Should hint at the solo/intimate nature
- No performer names in the title

Recent VRA titles for style reference: Sweet Surrender, Rise and Grind, Always on Top, Between the Sheets, A Swift Release, Potent Curves, The Wettest Seduction, Unhurried & Undressed, She Came to Play, Hovering With Intent

Respond with ONLY the title — no quotes, no explanation.""",

    "NaughtyJOI": """You are a creative title writer for NaughtyJOI, a premium VR JOI (jerk-off instruction) studio.
Generate a PAIRED title: "[Name] [action phrase]" then "[Name] then [contrasting action phrase]"
- First title: soft/teasing action (e.g. "draws you near", "sets the pace")
- Second title: intense/dominant contrasting action (e.g. "then sets you free", "then dares you to keep up")
- Use the performer's first name only

Recent NJOI titles: Lulu Chu builds you up / Lulu Chu then lets you fall, River Lynn starts with soft encouragement / River Lynn then strips away every ounce of your self-control

Respond with ONLY the two titles separated by a newline — no quotes, no explanation.""",
}


def _generate_title(studio, female, theme, plot, description=""):
    """Generate a scene title using Claude based on script content."""
    _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not _claude_key:
        return None

    # Map app studio names to system prompt keys
    _studio_map = {"VRHush": "VRHush", "FuckPassVR": "FuckPassVR",
                   "VRAllure": "VRAllure", "NaughtyJOI": "NaughtyJOI"}
    _sys = _TITLE_GEN_SYSTEMS.get(_studio_map.get(studio, "VRHush"), _TITLE_GEN_SYSTEMS["VRHush"])

    _user = f"""Generate a title for this scene:

Performer: {female}
Theme: {theme}
Plot summary: {plot[:500] if plot else 'N/A'}
{f'Description: {description[:300]}' if description else ''}

Generate the title now."""

    try:
        import anthropic as _anth
        _ac = _anth.Anthropic(api_key=_claude_key)
        _resp = _ac.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            system=_sys,
            messages=[{"role": "user", "content": _user}]
        )
        return _resp.content[0].text.strip().strip('"').strip("'")
    except Exception:
        return None


def _write_title_to_grail(studio, scene_num, title):
    """Write a generated title to the Grail spreadsheet."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            os.path.join(os.path.dirname(__file__), "service_account.json"),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        gc = gspread.authorize(creds)
        _GRAIL_ID = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
        sh = gc.open_by_key(_GRAIL_ID)
        # Map studio to Grail tab
        _tab_map = {"VRHush": "VRH", "FuckPassVR": "FPVR", "VRAllure": "VRA", "NaughtyJOI": "NNJOI"}
        tab = _tab_map.get(studio, "VRH")
        ws = sh.worksheet(tab)
        # Find row by scene number (col B = index 1)
        cells = ws.col_values(2)  # col B = scene numbers
        for i, val in enumerate(cells):
            if val.strip() == str(scene_num).strip():
                ws.update_cell(i + 1, 4, title)  # col D = title
                return True, f"Saved '{title}' → {tab} row {i + 1}"
        return False, f"Scene #{scene_num} not found in {tab}"
    except Exception as e:
        return False, f"Error: {e}"


def _write_title_to_scripts_sheet(ws_title, row_idx, title):
    """Write a generated title to the Scripts sheet (col K)."""
    try:
        ws = get_spreadsheet().worksheet(ws_title)
        ws.update_cell(row_idx, COL_TITLE + 1, title)  # COL_TITLE is 0-indexed, update_cell is 1-indexed
        return True
    except Exception as e:
        return False


# Models that are NOT for script writing — hidden from the script model picker
_NON_SCRIPT_MODELS = {"llava:7b", "llava", "qwen2.5-coder:14b", "qwen2.5-coder:7b",
                      "nomic-embed-text:latest", "nomic-embed-text"}

# Human-friendly labels for known models
_MODEL_LABELS = {
    "vr-scriptwriter":       "VR Script Writer  ★ recommended",
    "vr-scriptwriter:latest":"VR Script Writer  ★ recommended",
    "qwen2.5:14b":           "Qwen 2.5 14B  — general fallback",
    "qwen2.5:7b":            "Qwen 2.5 7B  — general (fast)",
    "dolphin-llama3:8b":     "Dolphin LLaMA3 8B  — fast",
    "dolphin-mistral:latest":"Dolphin Mistral  — fast",
    "llama3.2:latest":       "LLaMA 3.2  — general",
    "llama3.1:latest":       "LLaMA 3.1  — general",
}

@st.cache_data(ttl=300)
def _list_ollama_models() -> tuple[list[str], list[str]]:
    """Return (raw_ids, display_labels) for script-writing models only."""
    try:
        base  = OLLAMA_BASE_URL.replace("/v1", "")
        resp  = _requests.get(f"{base}/api/tags", timeout=3)
        all_m = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        all_m = ["vr-scriptwriter", OLLAMA_MODEL]
    script_models = [m for m in all_m if m not in _NON_SCRIPT_MODELS]
    if not script_models:
        script_models = [OLLAMA_MODEL]
    labels = [_MODEL_LABELS.get(m, m) for m in script_models]
    return script_models, labels

@st.cache_data
def _checkerboard_bg(w: int, h: int, sq: int = 16):
    """Build a checkerboard RGBA image, cached by (w, h)."""
    import numpy as np
    arr = np.full((h, w, 4), (40, 40, 45, 255), dtype=np.uint8)
    for y in range(0, h, sq):
        for x in range(0, w, sq):
            if (x // sq + y // sq) % 2 == 0:
                arr[y:y+sq, x:x+sq] = (55, 55, 60, 255)
    from PIL import Image as _Img
    return _Img.fromarray(arr, "RGBA")

st.set_page_config(page_title="Eclatech Hub", page_icon="🎬", layout="wide")


# ── Global CSS (cached — avoids re-rendering on every rerun) ─────────────────
@st.cache_data
def _global_css():
    return """<style>
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"]  { display: none !important; }
.main .block-container {
    max-width: 100% !important;
    padding-top: 0.6rem !important;
    padding-bottom: 1rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }
[data-testid="stHorizontalBlock"] { gap: 0.6rem !important; }
.stCaptionContainer p { color: #aaa !important; }
.sh { font-size:0.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
      color:#6b7280; border-bottom:1px solid #1f293744; padding-bottom:3px; margin:12px 0 6px; }
</style>"""
st.markdown(_global_css(), unsafe_allow_html=True)

# ── Authentication Gate ───────────────────────────────────────────────────────
from auth_config import get_user_permissions, get_allowed_tabs, is_admin

if not st.user.is_logged_in:
    st.markdown(
        "<div style='text-align:center; margin-top:120px'>"
        "<span style='font-size:2.2rem;font-weight:800;letter-spacing:-.02em;"
        "color:#f3f4f6'>Eclatech Hub</span>"
        "<p style='color:#9ca3af; margin:24px 0 32px; font-size:1rem'>"
        "Sign in with your Google account to continue.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    _lc1, _lc2, _lc3 = st.columns([1, 1, 1])
    with _lc2:
        if st.button("🔑 Sign in with Google", use_container_width=True):
            st.login()
    st.stop()

_auth_email = st.user.email.lower()
_auth_user = get_user_permissions(_auth_email)

if _auth_user is None:
    st.markdown(
        "<div style='text-align:center; margin-top:120px'>"
        "<span style='font-size:1.5rem;font-weight:700;color:#ef4444'>Access Denied</span>"
        f"<p style='color:#9ca3af; margin:20px 0'>{st.user.email} is not authorized.</p>"
        "<p style='color:#6b7280'>Contact Drew for access.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    _dc1, _dc2, _dc3 = st.columns([1, 1, 1])
    with _dc2:
        if st.button("Sign out", use_container_width=True):
            st.logout()
    st.stop()

_user_name = _auth_user["name"]
_user_is_admin = is_admin(_auth_user)
_user_allowed_tabs = get_allowed_tabs(_auth_user)

# ── Header with user info ─────────────────────────────────────────────────────
_hdr1, _hdr2 = st.columns([5, 1])
with _hdr1:
    st.markdown(
        "<div style='margin:0 0 10px'>"
        "<span style='font-size:1.3rem;font-weight:800;letter-spacing:-.02em;"
        f"color:#f3f4f6'>Eclatech Hub</span>"
        f"<span style='font-size:0.8rem;color:#6b7280;margin-left:12px'>Hi, {_user_name}</span>"
        "</div>",
        unsafe_allow_html=True)
with _hdr2:
    if st.button("Sign out", key="logout_btn"):
        st.logout()

# ── Slop phrase substitutions (compiled once at module level) ─────────────────
_SLOP_SUBS = [
    (re.compile(r'\b(?:their\s+)?eyes?\s+meets?\b', re.I), "she holds his gaze"),
    (re.compile(r'\b(?:their\s+)?eyes?\s+met\b',   re.I), "she held his gaze"),
    (re.compile(r'\beyes?\s+locking\b',             re.I), "she holds his gaze"),
    (re.compile(r'\beyes?\s+locked\b',              re.I), "she held his gaze"),
    (re.compile(r'\bthe air between them\b',     re.I), "the quiet between them"),
    (re.compile(r'\bundeniable chemistry\b',     re.I), "a pull they've both felt building"),
    (re.compile(r'\bmagnetic attraction\b',      re.I), "a pull neither moves to break"),
    (re.compile(r'\bpalpable tension\b',         re.I), "a quiet charge in the room"),
    (re.compile(r'\bthe tension is palpable\b',  re.I), "the charge in the room is undeniable"),
    (re.compile(r'\bsparks fly\b',               re.I), "something shifts between them"),
    (re.compile(r'\belectric tension\b',         re.I), "a stillness charged with intent"),
    (re.compile(r'\bsuccumb(s|ed|ing)?\b',       re.I), "give in"),
    (re.compile(r'\bsteamy\b',                   re.I), "charged"),
    (re.compile(r'\bdesires intertwining\b',     re.I), "what comes next"),
    (re.compile(r'\bdesires intertwine\b',       re.I), "what comes next"),
    (re.compile(r'\bunspoken desire\b',          re.I), "what neither has said aloud"),
    (re.compile(r'\bpassion ignites\b',          re.I), "the moment breaks open"),
    (re.compile(r'\bunable to resist\b',         re.I), "past the point of stopping"),
    (re.compile(r'\bgive in to their desires\b', re.I), "act on it"),
    (re.compile(r'\bcan no longer be contained\b', re.I), "is past the point of stopping"),
    (re.compile(r'\bcharged atmosphere\b',       re.I), "the stillness in the room"),
    (re.compile(r'\blonging glances\b',          re.I), "the way she watches him"),
    (re.compile(r'\ba bottle of (?:wine|champagne|prosecco)\b', re.I), "a bottle of sparkling water"),
    (re.compile(r'\btwo wine glasses\b',          re.I), "two glasses of water"),
    (re.compile(r'\bwine glasses?\b',             re.I), "water glasses"),
    (re.compile(r'\bglass(?:es)? of (?:wine|champagne|prosecco)\b', re.I), "glass of water"),
    (re.compile(r'\bchardonnay\b',                re.I), "sparkling water"),
    (re.compile(r'\bprosecco\b',                  re.I), "sparkling water"),
    (re.compile(r'\bchampagne\b',                 re.I), "sparkling water"),
    (re.compile(r'\bred wine\b',                  re.I), "herbal tea"),
    (re.compile(r'\bwhite wine\b',                re.I), "sparkling water"),
    (re.compile(r'\brosé\b',                      re.I), "sparkling water"),
    (re.compile(r'\bcocktails?\b',                re.I), "coffee"),
    (re.compile(r'\bwhiskey\b',                   re.I), "coffee"),
    (re.compile(r'\bbourbon\b',                   re.I), "coffee"),
    (re.compile(r'\bwine rack\b',                 re.I), "bookshelf"),
    (re.compile(r'\bcooking wine\b',              re.I), "cooking broth"),
    (re.compile(r'\bwine\b',                      re.I), "sparkling water"),
    (re.compile(r'\bbeer\b',                      re.I), "sparkling water"),
    (re.compile(r'\bliquor\b',                    re.I), "coffee"),
    (re.compile(r'\brum\b',                       re.I), "coffee"),
    (re.compile(r'\bgin\b',                       re.I), "coffee"),
    (re.compile(r'\bvodka\b',                     re.I), "coffee"),
]

# ── Shared Description Config (used by Missing tab + Description tab) ────────
_DESC_STUDIO_CONFIG = {
    "FPVR": {"name": "FuckPassVR", "cta": "Watch {pronoun} on FuckPassVR now.", "prefix": "FPVR"},
    "VRH":  {"name": "VRHush",     "cta": "Taste {pronoun} on VRHush now.",     "prefix": "VRH"},
    "VRA":  {"name": "VRAllure",   "cta": "Watch {pronoun} on VRAllure now.",   "prefix": "VRA"},
    "NJOI": {"name": "NJOI",       "cta": "Watch {pronoun} on NJOI now.",       "prefix": "NJOI"},
}

_FPVR_CATEGORIES = [
    "8K", "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
    "Body Cumshot", "Brunette", "Compilation", "Creampie", "Cum on Tits",
    "Curvy", "Ebony", "Facial Cumshot", "Hairy Pussy", "Handjob", "Latina",
    "MILF", "Natural Tits", "Petite", "Redhead", "Small Tits", "Threesome",
]

def _cat_slug(name):
    """'Big Ass' → 'big-ass'"""
    return name.lower().replace(" ", "-")

_STUDIO_DOMAINS = {
    "FPVR": "www.fuckpassvr.com",
    "VRH": "www.vrhush.com",
    "VRA": "www.vrallure.com",
    "NJOI": "www.naughtyjoi.com",
}

def _category_url(studio, cat_name):
    """Build category URL: https://domain/category/{slug}-vr-porn"""
    domain = _STUDIO_DOMAINS.get(studio, _STUDIO_DOMAINS["FPVR"])
    return f"https://{domain}/category/{_cat_slug(cat_name)}-vr-porn"

def _tag_url(studio, tag_name):
    """Build tag URL: https://domain/destination/tag/{slug}/"""
    domain = _STUDIO_DOMAINS.get(studio, _STUDIO_DOMAINS["FPVR"])
    slug = tag_name.lower().replace("'", "").replace(" ", "-")
    return f"https://{domain}/destination/tag/{slug}/"

def _cats_as_html(studio, cats_csv):
    """Convert comma-separated categories to HTML links."""
    cats = [c.strip() for c in cats_csv.split(",") if c.strip()]
    links = [f'<a href="{_category_url(studio, c)}">{c}</a>' for c in cats]
    return ", ".join(links)

def _tags_as_html(studio, tags_csv):
    """Convert comma-separated tags to HTML links."""
    tags = [t.strip() for t in tags_csv.split(",") if t.strip()]
    links = [f'<a href="{_tag_url(studio, t)}">{t}</a>' for t in tags]
    return ", ".join(links)

_FPVR_CATEGORY_URLS = {
    "8K": "https://www.fuckpassvr.com/category/8k-vr-porn",
    "Anal": "https://www.fuckpassvr.com/category/anal-vr-porn",
    "Asian": "https://www.fuckpassvr.com/category/asian-vr-porn",
    "Big Ass": "https://www.fuckpassvr.com/category/big-ass-vr-porn",
    "Big Tits": "https://www.fuckpassvr.com/category/big-tits-vr-porn",
    "Blonde": "https://www.fuckpassvr.com/category/blonde-vr-porn",
    "Blowjob": "https://www.fuckpassvr.com/category/blowjob-vr-porn",
    "Body Cumshot": "https://www.fuckpassvr.com/category/body-cumshot-vr-porn",
    "Brunette": "https://www.fuckpassvr.com/category/brunette-vr-porn",
    "Compilation": "https://www.fuckpassvr.com/category/compilation-vr-porn",
    "Creampie": "https://www.fuckpassvr.com/category/creampie-vr-porn",
    "Cum on Tits": "https://www.fuckpassvr.com/category/cum-on-tits-vr-porn",
    "Curvy": "https://www.fuckpassvr.com/category/curvy-vr-porn",
    "Ebony": "https://www.fuckpassvr.com/category/ebony-vr-porn",
    "Facial Cumshot": "https://www.fuckpassvr.com/category/facial-cumshot-vr-porn",
    "Hairy Pussy": "https://www.fuckpassvr.com/category/hairy-pussy-vr-porn",
    "Handjob": "https://www.fuckpassvr.com/category/handjob-vr-porn",
    "Latina": "https://www.fuckpassvr.com/category/latina-vr-porn",
    "MILF": "https://www.fuckpassvr.com/category/milf-vr-porn",
    "Natural Tits": "https://www.fuckpassvr.com/category/natural-tits-vr-porn",
    "Petite": "https://www.fuckpassvr.com/category/petite-vr-porn",
    "Redhead": "https://www.fuckpassvr.com/category/redhead-vr-porn",
    "Small Tits": "https://www.fuckpassvr.com/category/small-tits-vr-porn",
    "Threesome": "https://www.fuckpassvr.com/category/threesome-vr-porn",
}

_FPVR_TAGS = "8K, African, American, Anal Creampie, Analized, Arab, Argentinian, Asia, Asian, Ass, Ass Bounce, Ass Eating, Ass Fucking, Ass to Mouth, Ass Worship, Athletic, ATM, Australian, Average, Babe, Bald Pussy, Ball Sucking, Bangkok, Beauty Pageant, Belarusian, Belgian, Belgium, Berlin, Big Boobs, Big Fake Tits, Big Natural Tits, Big Oiled Tits, Black, Black Eyes, Blonde, Blue Eyes, Boobjob, Braces, Brazilian, British, Brown Eyes, Brunette, Brunette Fuck, Budapest, Bush, Butt Fuck, Butt Plug, Canadian, Caucasian, Chair Grind, Chile, Chilean, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Colombian, Columbian, Compilation, Cooking, Cowgirl, Creampie, Croatian, Cuban, Cum Eating, Cum in Mouth, Cum In Pussy, Cum on Ass, Cum on Face, Cum Play, Cum Swallow, Cumplay, Czech, Czech Republic, Dancing, Deep Anal, Deep Throat, Deep Throating, Deepthroat, Dick Sucking, Doggy, Doggy Style, Doggystyle, Dutch, Eating Ass, Ebony Babe, Escort, Euro Babe, European, Face Fucking, Face in Camera, Facefuck, Facial, Fake Tits, Farmer's Daughter, FFM porn, Filipina, Filipino, Finger Play, Fingering, Finnish, Fishnet Stockings, Foot Job, Footjob, Freckles, French, German, GFE, Glasses, Green Eyes, Grey Eyes, Grinding, Hair Pulling, Hairy Pussy, Hand Job, Hazel Eyes, Hispanic, Hot Tub, Humping, Hungarian, Intimate, Italian, Italy, Japanese, Jerk to Pop, Jizz Shot, Kenyan, Kissing, Landing Strip, Lap Dance, Latin, Latin Pussy, Latvian, Lingerie, Long Hair, Long Legs, Maid, Maltese, Massage, Massage Oil, Masseuse, Masturbation, Mexican, Mexico, Middle Eastern, Milf Porn, Missionary, Moldovan, Natural Boobs, Natural Tits, Navel Piercing, Nipple Piercing, Nipple Piercings, Nipple Play, Oil, Oil Massage, Oiled Tits, Oral Creampie, Panty Sniffing, Peruvian, Petite, PHAT Ass, Pierce Nipples, Pierced Clit, Pierced Nipples, Pierced Pussy, Pole Dancing, Polish, POV, POV BJ, Puerto Rican, Pull Out Cumshot, Pullout Cumshot, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy to Mouth, Pussy Worship, Redhead, Reverse Cowgirl, Rimjob, Roller Skates, Russian, Saudi, Saudi Arabian, Secretary, Septum Piercing, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Sexy Redheads, Shaved, Shaved Pussy, Short Skirt, Sixty-nine, Slim, Sloppy Blowjob, Slovakian, Small Boobs, Small Natural Tits, South America, Spanish, Squirter, Standing Doggy, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Sucking Tits, Swallow, Syrian, Tall, Tattoo, Tattooed, Tattoos, Tease, Thailand, Tight Ass, Titjob, Tits in Face, Titty Fuck, Titty Sucking, Tittyjob, Toys, Trimmed, Trimmed Pussy, True 8K, Turkish, Turkish Babe, Twerking, Ukraine, Ukrainian, United States, Venezuelan, Vibrator, Wrestling"

_VRH_CATEGORIES = [
    "8K", "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
    "Body Cumshot", "Brunette", "Compilation", "Creampie", "Cum in Mouth",
    "Cum on Tits", "Cumshot", "Curvy", "Ebony", "Facial Cumshot",
    "Hairy Pussy", "Handjob", "Hardcore", "Latina", "MILF", "Natural Tits",
    "Oral Creampie", "Petite", "Redhead", "Shaved Pussy", "Small Tits",
    "Threesome",
]
_VRH_TAGS = "8K, American, Anal, Analized, Arab, Asian, Ass, Ass Bounce, Ass Fucking, Ass Worship, Ass to Mouth, Athletic, ATM, Average, Bald Pussy, Ball Sucking, Big Boobs, Big Fake Tits, Big Natural Tits, Black, Blue Eyes, Brazilian, Brown Eyes, Brunette Fuck, Bush, Butt Fuck, Butt Plug, Canadian, Caucasian, Chair Grind, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Compilation, Cowgirl, Creampie, Cuban, Cum Eating, Cum in Mouth, Cum In Pussy, Cum on Ass, Cum on Face, Cum on Tits, Cum Play, Cum Swallow, Czech, Dancing, Deep Anal, Deep Throat, Deepthroat, Dick Sucking, Doggy Style, Doggystyle, Dutch, Ebony, Escort, Euro Babe, European, Facial, Fake Tits, Filipina, Filipino, Fingering, Fishnet Stockings, Footjob, Freckles, GFE, Glasses, Green Eyes, Grey Eyes, Hairy Pussy, Hazel Eyes, Hispanic, Intimate, Italian, Japanese, Jerk to Pop, Kissing, Landing Strip, Latin, Lingerie, Maltese, Massage, Massage Oil, Masseuse, Masturbation, Middle Eastern, Milf Porn, Missionary, Natural Boobs, Natural Tits, Navel Piercing, Oral Creampie, PHAT Ass, POV, POV BJ, Pierced Clit, Pierced Nipples, Polish, Pull Out Cumshot, Pullout Cumshot, Puerto Rican, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy Worship, Reverse Cowgirl, Rimjob, Roleplay, Romanian, Russian, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Shaved, Shaved Pussy, Short Skirt, Sixty-nine, Slim, Slovakian, Small Boobs, Small Natural Tits, Spanish, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Syrian, Tattoos, Threesome, Tight Ass, Titjob, Tits in Face, Titty Fuck, Titty Sucking, Tittyjob, Toys, Trimmed, Trimmed Pussy, True 8K, Twerking, Ukrainian, Vibrator"

_VRA_CATEGORIES = [
    "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
    "Brunette", "Compilation", "Curvy", "Ebony", "Hairy Pussy", "Handjob",
    "Latina", "Masturbation", "MILF", "Natural Tits", "Petite", "Redhead",
    "Sex Toys", "Shaved Pussy", "Small Tits",
]
_VRA_TAGS = "8K, American, Anal, Arab, Asian, Ass, Ass Bounce, Ass Spread, Ass Worship, Athletic, Australian, Average, Bald Pussy, Big Boobs, Big Fake Tits, Big Natural Tits, Black, Blue Eyes, Brazilian, Brown Eyes, Brunette Fuck, Bush, Butt Plug, Canadian, Caucasian, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Colombian, Compilation, Cowgirl, Creampie, Cuban, Curvy, Dancing, Deep Anal, Dick Sucking, Dildo Penetration, Doggy Style, Ebony, Euro Babe, European, Fake Tits, Filipina, Filipino, Fingering, Fishnet Stockings, Footjob, French, GFE, Glasses, Green Eyes, Grey Eyes, Hairy Pussy, Hazel Eyes, Intimate, Italian, Japanese, Jerk Off Instructions, Ken Doll, Kissing, Landing Strip, Latin, Latina, Lingerie, Maltese, Masturbation, Middle Eastern, Milf Porn, Missionary, Mongolian, Natural Boobs, Natural Tits, Navel Piercing, Outdoors, PHAT Ass, POV, POV BJ, Pierced Clit, Pierced Nipples, Polish, Puerto Rican, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy Worship, Pussylick, Reverse Cowgirl, Russian, Saudi, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Shaved, Shaved Pussy, Sixty-nine, Slim, Small Boobs, Small Natural Tits, Solo, Spanish, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Syrian, Tattoos, Teens, Tight Ass, Titjob, Titty Fuck, Toys, Trimmed, Trimmed Pussy, True 8K, Twerking, Vibrator, Voyeur"

# Unified lookup for all studios
_STUDIO_CATEGORIES = {"FPVR": _FPVR_CATEGORIES, "VRH": _VRH_CATEGORIES, "VRA": _VRA_CATEGORIES}
_STUDIO_TAGS = {"FPVR": _FPVR_TAGS, "VRH": _VRH_TAGS, "VRA": _VRA_TAGS}

# ── Full system prompts per studio ────────────────────────────────────────────
_DESC_SYSTEMS_FULL = {}

_DESC_SYSTEMS_FULL["FPVR"] = """# PERSONALITY:
You are an expert adult copywriter specializing in crafting sexual, filthy, and deeply arousing scene descriptions for a Virtual Reality (VR) porn site called FuckPassVR. Your writing blends raw sexual energy with emotional depth and sensory immersion to create content that transports users into hyper-realistic, intimate encounters, making them feel as though they are part of the action. Your descriptions are optimized for search engines with a focus on VR adult content, captivating both human users and search algorithms.

# MAIN GOAL
The goal is to generate a sexually engaging and SEO optimized scene descriptions.

# WRITING STANDARDS:
1. Use active voice and powerful, visceral verbs to convey action and desire (e.g., "thrust," "devour," "crave"), enhancing the user's sense of agency in the VR space.
2. Incorporate erotic figurative language (metaphors, similes, personification) to elevate raw acts into poetic seduction, tailored for VR immersion (e.g., "her gaze pierces through the virtual haze, pulling you into her world").
4. Vary sentence structure for rhythmic intensity—short, sharp sentences for urgency; longer, flowing ones for sensual exploration—mimicking the ebb and flow of a VR encounter.
5. Focus on "show don't tell" to reveal desire through actions, physical reactions, and sensory cues, intensifying the first-person VR perspective (e.g., "your pulse races as her fingers graze your virtual skin").
6. Use language that feels authentic to the heat of the moment—raw, dirty, or tender as the scene demands—while weaving in VR-focused SEO-friendly terms naturally (e.g., "dive into a steamy VR sex fantasy with untamed passion").
7. Avoid any dialogue or spoken words, focusing solely on descriptive narration, internal user thoughts, and physical expressions to convey emotion and intent within the VR environment.
8. Maintain a seductive, provocative narrative voice that aligns with the tone of the work, whether raw and filthy or sensual and poetic, ensuring brand consistency for VR site SEO.
9. Balance raw eroticism with marketability, tailoring content to target VR porn audiences and optimizing for high-traffic VR adult keywords.

# EXAMPLES:
1. Ebony VR Porn: Chicago's Finest Gets Down and Dirty!
Is having a sultry ebony goddess grinding her big ass right in your face while performing a private dance one of your ultimate fantasies? Well, get ready because we've finally secured the queen of Chicago's underground scene - Ameena Green - for an exclusive VR porn experience that'll have you gripping your headset from start to finish! And trust us, this isn't just any private dance. This ebony VR porn masterpiece will show you exactly why Ameena's reputation for turning successful businessmen into drooling messes is well-earned. The moment she locks eyes with you in that exclusive club, you know you're in for a night that'll ruin all other VR experiences! Watch in stunning 8K VR as this chocolate goddess works her magic, those natural tits bouncing while she teases you with moves that should be illegal. Her wicked smile and seductive whispers are just the beginning - wait until you see what happens when the private room curtain closes and this cum-hungry queen shows you what she really does for her favorite clients!

Creampie VR Porn: When Private Dances Turn Extra Nasty!
How wild does it get? Let's just say that this creampie VR porn scene pushes boundaries you didn't even know existed! Inside this members-only paradise, Ameena transforms from sophisticated dancer to insatiable cock queen. Watch as she drops to her knees, treating your dick to a POV BJ that'll have you seeing stars. But that's just the warm-up! This ebony VR goddess takes control, mounting you in reverse cowgirl and working that hairy pussy on your cock like she's trying to earn a lifetime membership to your wallet. From intense standing missionary against the velvet walls to savage doggy style action that has her big ass clapping, every position proves why she's Chicago's best-kept secret. And when this cum-hungry goddess begs for you to flood her pussy? Well, let's just say resistance is futile! So grab your VR headset and dive into this exclusive ebony VR experience. After all, we're talking about the kind of private dance that makes every dollar spent in that club worth it - especially when it ends with Ameena's pussy dripping with your hot load! Don't miss out on the nastiest night Chicago has to offer!

2. Rouge Rendezvous: When Success Meets Seduction in Lyon
While we all know that celebrating a big business deal usually involves expensive champagne and fancy dinners, your colleagues in Lyon have something far more exciting in mind! In this big tits VR masterpiece, you'll find yourself in the city's most exclusive gentlemen's club, where the mesmerizing Anissa Kate is about to turn your victory celebration into an unforgettable private encounter. This French goddess, with her natural boobs and devilish smile, isn't your typical dancer - she's an artist of seduction who performs purely for the thrill of it. Watch in stunning 8K VR as she transforms your private dance into an intimate confession of desire. The moment she drops to her knees, it's clear this is no ordinary lap dance - her POV BJ skills prove she's mastered more than just stage moves, her skilled mouth and expert hands working in perfect harmony to drive you absolutely wild.

From Private Show to Passionate Creampie VR Porn
Inside this steamy creampie VR porn scene, you'll experience why French women have such a legendary reputation! Anissa takes complete control, mounting you in reverse cowgirl with an ass bounce that would make Paris proud. Her big tits sway hypnotically as she grinds against you, each movement building more intensity than the last. From deep standing missionary against the club's velvet walls to wild cowgirl rides that test the furniture's durability, every position showcases why she's Europe's most sought-after VR porn star. The passion reaches its peak in an intense doggy style session before she begs for that final cum in pussy finish. And trust us - when Anissa Kate demands a creampie, you don't say no! So grab your VR headset and prepare for the kind of private dance that makes every euro spent in Lyon worth it. After all, some business celebrations are better kept private, especially when they involve a French goddess who knows exactly how to make your success feel even sweeter!

3. Miami Heat: When Blonde VR Porn Dreams Ignite
Even though FuckPassVR specializes in creating mind-blowing virtual reality experiences, sometimes the hottest scenes come from the most unexpected situations. What does this mean for you? Well, you're about to discover how crashing on your old friend's couch in Miami turns into an unforgettable encounter with the stunning Thea Summers, a sexy blonde who's been harboring secret desires since your school days! Welcome to Tropic Like It's Hot - our latest 8K VR porn video that proves sometimes the best laid plans are the ones that aren't planned at all. After a night of vivid dreams about you, Thea brings you morning coffee only to find you sleeping naked on her couch. Watch as she seizes the moment, her small tits and toned body on display as she treats you to a POV BJ that'll make you forget all about that coffee getting cold.

Tropical Paradise: A Sizzling VR Porn Video Fantasy
This blonde VR porn scene explodes with raw passion as Thea takes control, mounting you reverse cowgirl with an ass bounce that defies gravity. Her sexy body becomes a work of art in motion as she spins around to face you, riding cowgirl style with an intensity that matches Miami's heat. The standing missionary position proves this fit beauty can handle whatever you give her, but it's when she gets on all fours that things really heat up. Watch her shaved pussy take every inch in doggy style before the intimate close-up missionary gives you the perfect view of what's to come. The grand finale sees her back on top, working you in cowgirl position until you flood her needy pussy with a hot load, leaving her dripping and satisfied. Who knew getting crashing on the couch could lead to such a wild ride? Let Thea Summers show you why sometimes the best plans are no plans at all in this stunning 8K VR porn experience.

4. Sinister Touches: When Yoga Meets Raw Desire in 8K VR Porn
Do we have any fitness enthusiasts among our VR porn viewers - or more precisely, someone who's dreamed of their yoga instructor taking things to the next level? Well, get ready because Maya Sinn is about to show you positions that definitely aren't in any traditional yoga manual. In this 8K VR porn scene, what starts as a typical training session quickly evolves into something far more enticing when your FuckPassVR passport catches Maya's attention. This European beauty might have started the day as your instructor, but she's about to become your personal sexual guru, trading meditation for pure, raw pleasure. Watch as she drops to her knees, taking your throbbing cock deep in her skilled mouth while incorporating that yoga ball in ways its manufacturers never intended, her POV BJ skills proving that flexibility isn't just for downward dog.

Hardcore Positions: A Cumshot VR Porn Masterclass
The real workout begins as Maya moves through positions that would make any yogi blush. She gets on all fours, that tight pussy begging to be filled as you pound her doggy style on the massage table. This cumshot VR porn scene showcases every inch of her sexual prowess as she takes you deep in missionary before mounting you in both cowgirl positions, her small tits bouncing with each thrust. The standing missionary proves this flexible vixen can handle an intense pounding, her shaved pussy gripping your cock until you're ready to explode. For the grand finale, Maya drops to her knees one last time, eager to earn her facial cumshot VR reward. Her pretty face becomes your canvas as you paint it with cum, proving some workouts are better done naked. Time to grab your VR headset and discover why this cum on face finish makes Sinister Touches an unforgettable session.

5. Your Ultimate Power Fantasy Awaits with Gizelle Blanco
Think we'd skip the billionaire's debauchery dream? Not a chance! At FuckPassVR, we turn boardroom triumphs into brunette VR porn paradise. Strap on your headset and become that tycoon celebrating Hawaii's biggest deal. Hidden behind velvet ropes in Hilo's most exclusive club, VR porn star Gizelle Blanco awaits - a raven-haired bombshell with big boobs that defy gravity and a big ass that rewrites temptation. Her pink lingerie glistens under moody lights as she whispers, "This private dance will ruin you for anyone else." Watch her electric striptease unravel, feel her skin under your roaming hands, then gasp as she drops to her knees. Her POV BJ engulfs your cock: sloppy dick sucking, throat-deep hunger, and eyes locked on yours like you're her last meal.

Cum-Worthy Finale in Jaw-Dropping 8K
This sexy brunette doesn't tease - she conquers. Mounting you in cowgirl, she rides hard, big boobs bouncing in your face while moans echo off soundproof walls. Then she spins, showcasing hypnotic reverse cowgirl action - that legendary ass bounce taunting you with every thrust. Against the stripper pole, standing missionary turns primal as she claws your back, taking reckless pumps. Doggystyle on all four on the chair? Her back arches, ass high, taking every punishing drive. When missionary shatters her into screaming orgasms, Gizelle makes gets you on the edge. The last cowgirl ride, makes you errupt on command! Kneeling before you, she strokes your cock until volcanic jizz shot erupts across her big, inviting tits - blasts of cum cascading over perfect curves in crystal 8K VR porn videos. This is how deals get sealed. Claim your filthy reward now! ONLY on FuckPassVR!"""

_DESC_SYSTEMS_FULL["VRH"] = """# PERSONALITY:
You are an expert adult copywriter specializing in crafting punchy, high-impact scene descriptions for VRHush, a premium VR porn studio. Your writing is raw, kinetic, and wastes zero words. Every sentence pushes the action forward. No scene-setting, no backstory - you drop the reader straight into the heat.

# MAIN GOAL
Generate a short, punchy, action-packed scene description optimized for VRHush's brand style.

# WRITING STANDARDS:
1. Single paragraph only. 100-140 words. No subheadings. No bold titles.
2. Open with the female performer doing something physical - no backstory, no "imagine," no setup.
3. Move through positions fast, one sentence each maximum.
4. Visceral, kinetic language: bouncing, slamming, gripping, moaning, dripping.
5. 2nd-person POV ("you") throughout. The male talent IS the viewer - NEVER refer to the male by name.
6. Mention wardrobe only if notable (lingerie, stockings, etc.).
7. Close with a one-liner: "[descriptor] in [resolution] VR porn. [CTA]"
8. Do NOT invent positions not in the plot.
9. No asterisks, bullet points, or markdown formatting.
10. No dialogue.
11. CRITICAL: In BG scenes, the male talent is YOU (the POV). Only the female performer gets named.

# EXAMPLES:
1. Kenzie Anne drops to her knees the second you walk through the door, wrapping those glossy lips around your cock like she's been starving for it. This blonde bombshell doesn't waste time - she's deepthroating you with sloppy, wet precision before climbing on top for a reverse cowgirl ride that puts her perfect ass on full display. She spins around, tits bouncing in your face as she grinds in cowgirl, then bends over the couch for doggy that has her screaming into the cushions. Standing missionary pins her against the wall, every thrust harder than the last. She finishes on her back in missionary, legs spread wide, taking every inch until you pull out and paint her stomach with a thick load. Pure filth in 8K VR porn. Taste her on VRHush now.

2. Liz Jordan's tight body is already on display when she peels off that lace set and drops into your lap. Her mouth finds your cock instantly - wet, messy, and eager. She mounts you reverse cowgirl, ass clapping with every bounce, then flips around for cowgirl with those perky tits pressed against you. Standing missionary has her pinned, moaning with each deep stroke. She gets on all fours for doggy, back arched, taking it hard and fast. The finale hits in missionary - her legs locked around you as you empty inside her with a deep creampie that leaves her trembling. Raw, unfiltered heat in 8K VR porn. Taste her on VRHush now.

3. Freya Parker greets you wearing nothing but a mischievous grin, and within seconds she's on her knees worshipping your cock with that signature sloppy enthusiasm. This petite stunner mounts up reverse cowgirl, her tiny frame bouncing impossibly fast on your shaft. Cowgirl brings those natural small tits right to your face as she rides with desperate urgency. She braces against the headboard for standing missionary, each thrust making her gasp. Doggy on the bed has her gripping the sheets, ass up, taking every punishing stroke. Missionary wraps it up - legs wide, eyes locked on yours as you pull out and blast a thick load across her pretty face. Unforgettable in 8K VR porn. Taste her on VRHush now."""

_DESC_SYSTEMS_FULL["VRA"] = """# PERSONALITY:
You are a sensual copywriter for VRAllure, a premium VR studio specializing in intimate solo and softcore content. Your writing is warm, tender, and deeply sensory - like a whispered confession. You focus on breath, touch, closeness, eye contact, and the electricity of being watched.

# MAIN GOAL
Generate a short, intimate, sensory-rich scene description for VRAllure's solo/intimate style.

# WRITING STANDARDS:
1. Single paragraph only. 60-90 words. No subheadings.
2. Intimate, whisper-close tone - not aggressive, not crude.
3. Focus on sensation: skin warmth, breath, fingertips, fabric, light.
4. These are typically solo/masturbation scenes - honor that intimacy.
5. 2nd-person POV ("you") - the viewer is a silent, invited observer.
6. Mention toys/props if in the plot.
7. Close with: "This [resolution] VR experience from VRAllure [sensory closing]."
8. Do NOT invent acts not in the plot.
9. No asterisks, bullet points, or markdown formatting.
10. No dialogue.

# EXAMPLES:
1. Skylar Vox settles onto silk sheets, sunlight tracing the curve of her waist as her fingers drift across her stomach. She takes her time, exploring herself with slow, deliberate touches - eyes half-closed, lips parting with each exhale. Her back arches as her hand slides between her thighs, hips rolling gently against her own rhythm. Every breath deepens, every movement more purposeful, until her whole body tightens and releases in a wave of quiet bliss. This 8K VR experience from VRAllure pulls you close enough to feel the warmth radiating from her skin. Watch her on VRAllure now.

2. Eliza Ibarra stretches across the bed in sheer white, letting the fabric pool around her hips as she starts to touch. Her fingertips trace circles on her inner thigh before slipping beneath the lace. The rhythm is unhurried - a slow burn that builds in the rise and fall of her chest. A vibrator hums softly as she presses it lower, her body responding with a shiver that travels from her toes to her parted lips. This 8K VR experience from VRAllure is pure intimacy captured in crystalline detail. Watch her on VRAllure now.

3. Lily Larimar lies back on the daybed, golden hour light pooling across her bare shoulders. She peels away a silk robe with no hurry, revealing her petite frame inch by inch. Her fingers find themselves, tracing slow paths across her small tits before dipping lower. Eyes flutter closed as her touch becomes more insistent, hips lifting gently off the cushion. The room is quiet except for the soft sounds of her breathing growing faster. This 8K VR experience from VRAllure lets you witness every shiver, every sigh. Watch her on VRAllure now."""

_DESC_SYSTEMS_FULL["NJOI"] = """# PERSONALITY:
You are a bold, teasing copywriter for NaughtyJOI (NJOI), a VR studio specializing in jerk-off instruction content. Your writing captures the push-pull dynamic of JOI - the performer talks directly to the viewer, guiding, teasing, commanding. You balance playfulness with intensity and always include at least one short performer quote.

# MAIN GOAL
Generate a short, JOI-focused scene description that captures the tease-build-release rhythm.

# WRITING STANDARDS:
1. Single paragraph only. 60-90 words. No subheadings.
2. Must include at least one short performer quote in double quotes.
3. JOI rhythm: tease, build, countdown, release.
4. Describe what she's wearing and removing.
5. Mention her voice, eye contact, and how she controls you.
6. 2nd-person POV ("you") throughout.
7. Playful, teasing, commanding tone.
8. Close with the studio CTA.
9. Do NOT invent acts not in the plot.
10. No asterisks, bullet points, or markdown.

# EXAMPLES:
1. Lulu Chu appears in a cropped tank and tiny shorts, eyes locked on yours with a knowing smile. She peels the tank away slowly, revealing her small natural tits as she whispers, "You don't get to touch - not yet." Her hand slides into her shorts, teasing herself while she counts you down, each number making you grip tighter. The shorts come off, and she spreads her legs wide, matching your pace stroke for stroke. "Faster," she commands, and you obey. The release hits like a wave when she finally says the word. Watch her on NJOI now.

2. River Lynn greets you in black lace, twirling for you before settling into the chair with her legs crossed. She uncrosses them slowly, giving you a peek before pulling back. "Think you can keep up?" She unclasps her bra, letting it fall as she begins to touch, guiding your rhythm with her voice. Faster, slower, stop - she controls every stroke. When the lace panties finally come off and she starts her countdown from ten, every second feels electric. Watch her on NJOI now.

3. Hazel Moore walks in wearing an oversized button-down, nothing underneath. She undoes each button like she's unwrapping a gift for you, maintaining eye contact the entire time. "I want you to go slow," she says, settling onto the bed and letting her hands wander. She mirrors your movements, building intensity until her breathing gets ragged. The countdown starts at five - short, urgent, breathless. When she hits zero, you both let go at the same time. Watch her on NJOI now."""


# ── Compilation system prompts (different style per studio) ───────────────────
_DESC_SYSTEMS_COMPILATION = {}

_DESC_SYSTEMS_COMPILATION["FPVR"] = """# PERSONALITY:
You are an expert adult copywriter for FuckPassVR writing compilation/best-of scene descriptions. Compilations are promotional "greatest hits" — you sell the CATEGORY, not a single narrative.

# WRITING STANDARDS:
1. Two paragraphs with bold subheadings. 200-300 words total.
2. Paragraph 1: Hook the category with a bold thesis. Name the series brand ("FuckPassVR Best [X] Adventures Volume [N]"). Sell the TYPE of performers collectively — archetypes, not individual stories. Superlative-heavy, promotional tone.
3. Paragraph 2: Tease what viewers will experience — the variety, the intensity, the production quality in 8K VR. Reference the number of performers. Build excitement for the collection without walking through individual scenes.
4. NEVER describe specific positions or scene-by-scene action. This is a highlight reel, not a walkthrough.
5. Reference 8K VR porn naturally. End with the studio CTA.
6. No dialogue, no asterisks, no bullet points.

# EXAMPLES:
1. **Best American Blonde Adventures: Your Ultimate Fantasy Lineup**
Think blondes have more fun? In 8K VR porn, they absolutely do — and FuckPassVR Best American Blonde Adventures Volume 1 is here to prove it. This compilation brings together the hottest blonde bombshells from across the United States, each one more irresistible than the last. From sun-kissed California babes to fiery East Coast stunners, every performer in this lineup was hand-picked to deliver the kind of raw, uninhibited passion that makes FuckPassVR the gold standard in virtual reality adult entertainment.

**8K VR Porn Blondes Who Redefine the Fantasy**
Whether your type is a petite spinner with a wicked smile or a curvy goddess who takes control, this compilation has your dream blonde waiting. Every encounter is captured in crystal-clear 8K, putting you inches away from the action as these American beauties work through an unforgettable range of positions and finishes. This isn't just a collection — it's the definitive blonde experience in VR porn. Watch them on FuckPassVR now."""

_DESC_SYSTEMS_COMPILATION["VRH"] = """# PERSONALITY:
You are an expert adult copywriter for VRHush writing compilation/best-of descriptions. VRHush compilations do a rapid per-performer walkthrough of highlights.

# WRITING STANDARDS:
1. Single paragraph. 120-180 words (longer than regular VRH, shorter than FPVR).
2. Open with a punchy hook for the category.
3. Walk through each performer with ONE sentence each — name + their standout moment/position.
4. Keep the kinetic VRH energy: fast, visceral, no fluff.
5. Close with: "[category descriptor] in 8K VR porn. [CTA]"
6. No asterisks, bullet points, or markdown.

# EXAMPLES:
1. The best curvy girls on VRHush, stacked into one relentless 8K VR compilation. Anissa Kate's teasing blowjob and reverse cowgirl ride kick off the action with those legendary natural tits bouncing in your face. Kitana Montana then takes over with intense standing missionary that puts her thick curves on full display. Mona Azar drops to her knees for a sloppy deepthroat before mounting you cowgirl, her big ass slamming down with every thrust. Karla Kush delivers a tight doggy session followed by a messy facial that leaves her grinning. Natasha Nice wraps it up with a slow-building ride that ends in the thickest creampie of the set. Five performers, five different flavors of curves — all captured in stunning 8K VR porn. Taste them on VRHush now."""

_DESC_SYSTEMS_COMPILATION["VRA"] = """# PERSONALITY:
You are a sensual copywriter for VRAllure writing compilation/best-of descriptions. Keep the intimate VRA tone but applied to a collection.

# WRITING STANDARDS:
1. Single paragraph. 80-120 words.
2. Sell the mood and sensation of the collection — breath, warmth, closeness across multiple performers.
3. Name each performer with one sensory detail each.
4. Close with the VRA-style ending.
5. No asterisks, bullet points, or markdown."""

_DESC_SYSTEMS_COMPILATION["NJOI"] = """# PERSONALITY:
You are a teasing copywriter for NaughtyJOI writing compilation/best-of descriptions.

# WRITING STANDARDS:
1. Single paragraph. 80-120 words.
2. Tease the variety of JOI styles — different voices, different commands, different paces.
3. Name each performer with their signature move or quote.
4. Build the tease-release rhythm across the whole collection.
5. Close with the NJOI CTA.
6. No asterisks, bullet points, or markdown."""


def _is_compilation(title):
    """Check if a scene title indicates a compilation."""
    if not title:
        return False
    return bool(re.search(r'\bVol\.?\s*\d|\bVolume\b|\bBest\s+Of\b|\bBest\s+\w|\bCompilation\b', title, re.I))


def _parse_desc_output(text):
    """Parse generated description into paragraphs + meta fields."""
    result = {"paragraphs": [], "meta_title": "", "meta_description": "", "raw": text}
    lines = text.strip().split("\n")

    current_title = ""
    current_body_lines = []
    in_meta = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for meta fields (handles: "Meta Title:", "**Meta Title:**", "**Meta Title: **" etc.)
        _clean_lower = stripped.replace("*", "").replace("#", "").strip().lower()
        if _clean_lower.startswith("meta title"):
            # Save any pending paragraph
            if current_title or current_body_lines:
                result["paragraphs"].append({
                    "title": current_title,
                    "body": " ".join(current_body_lines).strip()
                })
                current_title = ""
                current_body_lines = []
            _mt_val = stripped.replace("*", "").strip()
            if ":" in _mt_val:
                _mt_val = _mt_val.split(":", 1)[1].strip()
            result["meta_title"] = _mt_val.strip('"').strip("'")
            in_meta = True
            continue
        if _clean_lower.startswith("meta description"):
            _md_val = stripped.replace("*", "").strip()
            if ":" in _md_val:
                _md_val = _md_val.split(":", 1)[1].strip()
            result["meta_description"] = _md_val.strip('"').strip("'")
            in_meta = True
            continue
        if in_meta:
            # Additional meta content on next line
            if not result["meta_description"]:
                result["meta_description"] = stripped
            continue

        in_meta = False

        # Check if line is a bold title (common patterns: **Title**, or short line followed by paragraph)
        is_title = False
        clean = stripped.strip("*").strip()
        if stripped.startswith("**") and stripped.endswith("**"):
            is_title = True
            clean = stripped.strip("*").strip()
        elif len(stripped) < 80 and not stripped.endswith(".") and not stripped.endswith("!") and len(stripped.split()) < 12:
            # Short line that doesn't end with period - likely a title
            # But only if we already have a paragraph or it's the first line
            if not current_body_lines:
                is_title = True
                clean = stripped

        if is_title:
            # Save previous paragraph if exists
            if current_title or current_body_lines:
                result["paragraphs"].append({
                    "title": current_title,
                    "body": " ".join(current_body_lines).strip()
                })
                current_body_lines = []
            current_title = clean
        else:
            current_body_lines.append(stripped)

    # Save last paragraph
    if current_title or current_body_lines:
        result["paragraphs"].append({
            "title": current_title,
            "body": " ".join(current_body_lines).strip()
        })

    # Post-processing: extract meta fields embedded inline in paragraph bodies
    import re as _re_parse
    for _p in result["paragraphs"]:
        _body = _p["body"]
        # Look for **Meta Title:** or Meta Title: inline
        _mt_match = _re_parse.search(r'[\u2014\-—]*\s*\*{0,2}Meta\s*Title:?\*{0,2}\s*[:\s]*(.+?)(?:\*{0,2}Meta\s*Desc|\Z)', _body, _re_parse.IGNORECASE)
        if _mt_match and not result["meta_title"]:
            _mt_raw = _mt_match.group(1).strip().rstrip("*").strip().strip('"').strip("'")
            result["meta_title"] = _mt_raw
        _md_match = _re_parse.search(r'\*{0,2}Meta\s*Description:?\*{0,2}\s*[:\s]*(.+)', _body, _re_parse.IGNORECASE)
        if _md_match and not result["meta_description"]:
            result["meta_description"] = _md_match.group(1).strip().rstrip("*").strip().strip('"').strip("'")
        # Remove meta fields from body text
        _body_clean = _re_parse.sub(r'[\u2014\-—]*\s*\*{0,2}Meta\s*Title:?\*{0,2}\s*[:\s]*.+?(?=\*{0,2}Meta\s*Desc|\Z)', '', _body, flags=_re_parse.IGNORECASE)
        _body_clean = _re_parse.sub(r'\*{0,2}Meta\s*Description:?\*{0,2}\s*[:\s]*.+', '', _body_clean, flags=_re_parse.IGNORECASE)
        _p["body"] = _body_clean.strip().rstrip("—").rstrip("-").strip()

    return result


def _reassemble_desc(parsed):
    """Reassemble parsed description back into text."""
    parts = []
    for p in parsed.get("paragraphs", []):
        if p["title"]:
            parts.append(f"**{p['title']}**")
        parts.append(p["body"])
        parts.append("")
    if parsed.get("meta_title"):
        parts.append(f'Meta Title: "{parsed["meta_title"]}"')
    if parsed.get("meta_description"):
        parts.append(f"Meta Description: {parsed['meta_description']}")
    return "\n".join(parts).strip()


def _build_scene_prompt(studio, cfg, title, female, male, plot, categories, model_props, sex_positions, target_keywords, resolution, wardrobe):
    """Build the full scene prompt for description generation. Studio-aware structure."""
    female_names = [n.strip() for n in female.split(",") if n.strip()]
    male_names = [n.strip() for n in male.split(",") if n.strip()]
    pronoun = "her" if not male_names else "them"
    cta = cfg["cta"].format(pronoun=pronoun)

    # POV rule: in BG scenes, male talent IS the viewer ("you") — never refer to male by name
    if male_names:
        pov_rule = f"""CRITICAL POV RULE: This is a VR porn scene shot from the male's point of view. The male talent ({', '.join(male_names)}) IS the viewer — he is "you". NEVER refer to the male talent by name or as a third person. The viewer IS the male. Only refer to the female performer(s) by name."""
        model_line = ", ".join(female_names) + f" (with you as the POV)"
    else:
        pov_rule = "This is a solo scene. The viewer watches as a silent, intimate observer."
        model_line = ", ".join(female_names) if female_names else "Unknown"

    # ── Studio-specific structure instructions ───────────────────────────────
    if studio == "FPVR":
        structure = f"""Structure: Create two paragraphs, each with a bolded, enticing title.
Paragraph 1 (The Reveal): Focus on the story setup, the surprise entrance/encounter, and the initial intimate contact. Build anticipation.
Paragraph 2 (The Fantasy): Describe the core VR experience. Chronologically flow through the key sex acts, emphasizing the visceral, close-up details that {resolution} VR provides. Build to the intense finish.
Word Count: 350-400 words total.

Output Format:
Paragraph 1 Title: [Bolded, Engaging Title Here]
Paragraph 1: [Final polished text]
Paragraph 2 Title: [Bolded, Engaging Title Here]
Paragraph 2: [Final polished text]
Meta Title: "{title or 'Scene Title'} VR Porn | {cfg['name']}"
Meta Description: (160 chars max) [Compelling description with primary keyword and CTA]"""

    elif studio == "VRH":
        structure = f"""Structure: Single paragraph only. 100-140 words. NO subheadings, NO bold titles.
Open with the performer doing something physical — no backstory, no "imagine," no setup.
Move through positions fast, one sentence each maximum.
Visceral, kinetic language: bouncing, slamming, gripping, moaning, dripping.
Close with a one-liner format: "[descriptor] in {resolution} VR porn. {cta}"
Word Count: 100-140 words. Single paragraph.

Output Format:
[Single paragraph — no title, no subheadings]
Meta Title: "{title or 'Scene Title'} VR Porn | {cfg['name']}"
Meta Description: (160 chars max) [Compelling description]"""

    elif studio == "VRA":
        structure = f"""Structure: Single paragraph only. 60-90 words. NO subheadings, NO bold titles.
Intimate, whisper-close tone — not aggressive. Focus on sensation: skin, warmth, breath, fingertips.
Close with: "This {resolution} VR experience from VRAllure [sensory closing]. {cta}"
Word Count: 60-90 words. Single paragraph.

Output Format:
[Single paragraph — no title, no subheadings]
Meta Title: "{title or 'Scene Title'} VR Porn | {cfg['name']}"
Meta Description: (160 chars max) [Compelling description]"""

    elif studio == "NJOI":
        structure = f"""Structure: Single paragraph only. 60-90 words. NO subheadings, NO bold titles.
JOI rhythm: tease, build, countdown, release. Must include at least one short performer quote in double quotes.
Describe what she's wearing and removing. Mention her voice, eye contact, and how she controls you.
Close with the CTA: "{cta}"
Word Count: 60-90 words. Single paragraph.

Output Format:
[Single paragraph — no title, no subheadings]
Meta Title: "{title or 'Scene Title'} VR Porn | {cfg['name']}"
Meta Description: (160 chars max) [Compelling description]"""

    else:
        structure = f"""Structure: Single paragraph, 100-150 words.
Word Count: 100-150 words.
End with: "{cta}"

Output Format:
[Single paragraph]
Meta Title: "{title or 'Scene Title'} VR Porn | {cfg['name']}"
Meta Description: (160 chars max)"""

    prompt = f"""Role: You are a senior copywriter for {cfg['name']}.

{pov_rule}

Core Scene Data:
Scene Title: {title or 'Untitled'}
Model: {model_line}
Plot: {plot}
Categories: {categories}
Model Properties: {model_props or 'N/A'}
Target Keywords: {target_keywords or f'{resolution} VR porn, {cfg["name"]}'}
Sex positions: {sex_positions or 'See plot above'}{f'''
Wardrobe: {wardrobe}''' if wardrobe else ''}

Writing Instructions:
Tone & Perspective: 2nd-person POV ("You") throughout. Intensely immersive.
SEO: Naturally integrate the target keywords. The site name "{cfg['name']}" must appear at least once.
Do NOT invent positions or acts not described in the plot/sex positions.
No asterisks, bullet points, or markdown formatting in the description body.

{structure}

Write the description now."""

    return prompt


# ── Main tabs (dynamic based on user permissions) ────────────────────────────
_visible_tabs = _user_allowed_tabs  # list of (key, label) tuples
if _visible_tabs:
    _tab_objs = st.tabs([label for _, label in _visible_tabs])
    _tab_map = {key: obj for (key, _), obj in zip(_visible_tabs, _tab_objs)}
else:
    _tab_map = {}
    st.info("No tabs available for your account. Contact Drew for access.")
# Use a no-op container for tabs the user can't see — the `with` block still
# executes syntactically but we immediately skip its body with a flag check.
_noop = st.container()
tab_missing = _tab_map.get("Missing", _noop)
tab_tickets = _tab_map.get("Tickets", _noop)
tab_research = _tab_map.get("Model Research", _noop)
tab_scripts = _tab_map.get("Scripts", _noop)
tab_callsheet = _tab_map.get("Call Sheets", _noop)
tab_titles = _tab_map.get("Titles", _noop)
tab_desc = _tab_map.get("Descriptions", _noop)
tab_comp = _tab_map.get("Compilations", _noop)
_has_tab = _tab_map.__contains__

# ── TAB 1: Scripts (Manual + From Sheet, single + batch) ─────────────────────
with tab_scripts:
    if _has_tab("Scripts"):
        # ── Mode toggle ───────────────────────────────────────────────────────────
        mode = st.segmented_control("", ["✏️ Manual", "📋 From Sheet"], default="✏️ Manual",
                                    key="sc_mode", label_visibility="collapsed")

        # ─────────────────────────────────────────────────────────────────────────
        # Shared generation helpers (used by both modes)
        # ─────────────────────────────────────────────────────────────────────────
        # _SLOP_SUBS is defined at module level (above tabs) to avoid recompiling 45 regexes every rerun

        def _post_process(raw):
            raw = re.sub(r'\s*[\u2014\u2013]\s*', ' ', raw)
            raw = re.sub(r'(\d+[A-Za-z]?)-(\d)', r'\1 \2', raw)
            raw = re.sub(r'(\w)-(\w)', r'\1 \2', raw)
            raw = re.sub(r'-', ' ', raw)
            # Replace banned slop phrases with better prose equivalents
            for pattern, replacement in _SLOP_SUBS:
                raw = pattern.sub(replacement, raw)
            return raw

        def _parse_and_validate(raw, female="", male=""):
            pt = raw if re.search(r'(?i)^THEME\s*:', raw.lstrip()) else "THEME: " + raw
            f = parse_script_text(pt)
            v = validate_script(f, female=female, male=male)
            return f, v


        def _build_parsed(studio, female, male, scene_type_val, destination, theme_hint):
            is_vra  = studio == "VRAllure"
            is_njoi = studio == "NaughtyJOI"
            if is_vra:
                return {"studio": "VRAllure", "female": female,
                        "vra_scene_type": scene_type_val,
                        "theme_hint": theme_hint or None}, scene_type_val
            if is_njoi:
                return {"studio": "NaughtyJOI", "female": female}, "JOI"
            scene_norm = "BGCP" if scene_type_val and ("CP" in scene_type_val.upper() or "CREAMPIE" in scene_type_val.upper()) else "BG"
            return {
                "studio": studio,
                "destination": (destination or "").strip() or None,
                "scene_type": scene_norm,
                "female": female,
                "male": male or "",
                "theme_hint": theme_hint or None,
            }, scene_norm

        def _do_save(ws_target, row_target, fields):
            write_script(ws_target, row_target,
                         theme=fields.get("theme", ""),
                         plot=fields.get("plot", ""),
                         wardrobe_female=fields.get("wardrobe_female", ""),
                         wardrobe_male=fields.get("wardrobe_male", ""),
                         set_design=fields.get("set_design", ""),
                         props=fields.get("props", ""))
            # Bust the row + sorted cache for the saved month so the ✓ column updates
            _saved_month = ws_target.title if ws_target else ""
            for _k in list(st.session_state.keys()):
                if _k in (f"sc_rows_{_saved_month}", f"sc_sorted_{_saved_month}"):
                    del st.session_state[_k]

        # ─────────────────────────────────────────────────────────────────────────
        # Result display (single script) — shared by both modes
        # ─────────────────────────────────────────────────────────────────────────
        def _show_single_result():
            if "last_script" not in st.session_state:
                return
            _s             = st.session_state["last_script"]
            full_text      = _s["full_text"]
            fields         = _s["fields"]
            violations     = _s["violations"]
            parsed         = _s["parsed"]
            _saved_studio  = _s["studio"]
            _saved_female  = _s["female"]
            _saved_male    = _s["male"]
            _saved_research= _s["research_context"]
            _saved_ws_title= _s["ws_title"]
            _saved_row_idx = _s["row_idx"]
            _saved_scene   = _s["scene_norm"]

            st.divider()

            # ── Status banner ─────────────────────────────────────────────────────
            if violations:
                st.warning(f"{len(violations)} rule violation(s) — review before saving", icon="⚠️")
            else:
                st.success("All rules passed", icon="✅")

            # ── Script summary card ───────────────────────────────────────────────
            _dest_line = (f"<tr><td style='color:#888;padding:2px 12px 2px 0;font-size:0.82rem'>✈️ Destination</td>"
                          f"<td style='font-size:0.88rem'>{fields['destination']}</td></tr>"
                          if fields.get("destination") else "")
            _male_w    = fields.get("wardrobe_male", "")
            _male_line = (f"<tr><td style='color:#888;padding:2px 12px 2px 0;font-size:0.82rem'>👔 Male</td>"
                          f"<td style='font-size:0.88rem'>{_male_w}</td></tr>"
                          if _male_w else "")
            st.markdown(
                f"<div style='background:#111827;border-radius:8px;padding:12px 16px;margin:6px 0'>"
                f"<table style='border-collapse:collapse;width:100%'>"
                f"{_dest_line}"
                f"<tr><td style='color:#888;padding:2px 12px 2px 0;font-size:0.82rem'>🎭 Theme</td>"
                f"<td style='font-size:0.88rem;font-weight:600'>{fields.get('theme','—')}</td></tr>"
                f"<tr><td style='color:#888;padding:2px 12px 2px 0;font-size:0.82rem'>👗 Female</td>"
                f"<td style='font-size:0.88rem'>{fields.get('wardrobe_female','—')}</td></tr>"
                f"{_male_line}"
                f"</table></div>",
                unsafe_allow_html=True
            )

            # ── Plot (editable) ────────────────────────────────────────────────────
            _plot_text = fields.get("plot", "")
            if _plot_text:
                _edited_plot = st.text_area(
                    "Plot", value=_plot_text, height=130,
                    key="sc_plot_edit", label_visibility="collapsed",
                )
                # Keep edited version in sync so Accept & Save uses it
                _s["fields"]["plot"] = _edited_plot
                st.session_state["last_script"] = _s

            # ── Set / Props inline ─────────────────────────────────────────────────
            _set  = fields.get("set_design", "")
            _prop = fields.get("props", "")
            if _set or _prop:
                _sp_parts = []
                if _set:  _sp_parts.append(f"<b style='color:#888'>Set</b> {_set}")
                if _prop: _sp_parts.append(f"<b style='color:#888'>Props</b> {_prop}")
                st.markdown(
                    f"<p style='font-size:0.82rem;color:#bbb;margin:6px 0'>"
                    + " &nbsp;·&nbsp; ".join(_sp_parts) + "</p>",
                    unsafe_allow_html=True)

            if violations:
                with st.expander("⚠️ Rule violations", expanded=True):
                    for v in violations:
                        st.markdown(f"- 🔴 {v}")

            _dl_col, _ = st.columns([1, 3])
            with _dl_col:
                st.download_button("⬇️ Download", data=full_text,
                                   file_name=f"{_saved_studio}_{_saved_female.replace(' ','_')}_{_saved_scene}.txt",
                                   mime="text/plain")

            # ── Title generation ──────────────────────────────────────────────────
            _tc1, _tc2, _tc3 = st.columns([2, 4, 1])
            with _tc1:
                if st.button("🏷️ Generate Title", use_container_width=True, key="sc_gen_title"):
                    with st.spinner("Generating title…"):
                        _gen_title = _generate_title(
                            _saved_studio, _saved_female,
                            fields.get("theme", ""), fields.get("plot", ""))
                        if _gen_title:
                            st.session_state["generated_title"] = _gen_title
            with _tc2:
                _cur_title = st.text_input("Title", value=st.session_state.get("generated_title", ""),
                                           key="sc_title_edit", label_visibility="collapsed",
                                           placeholder="Generated title appears here…")
            with _tc3:
                if _cur_title and st.button("💾 Save", use_container_width=True, key="sc_save_title"):
                    # Save to Scripts sheet
                    if _saved_ws_title and _saved_row_idx:
                        _write_title_to_scripts_sheet(_saved_ws_title, _saved_row_idx, _cur_title)
                        st.success(f"Title saved: {_cur_title}")
                        st.session_state["generated_title"] = _cur_title

            st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
            _a1, _a2, _a3 = st.columns([2, 2, 3])
            with _a1:
                if st.button("✅ Accept & Save", use_container_width=True, type="primary", key="sc_accept"):
                    saved = False
                    try:
                        if _saved_ws_title and _saved_row_idx:
                            _ws = get_spreadsheet().worksheet(_saved_ws_title)
                            _do_save(_ws, _saved_row_idx, fields)
                            st.success(f"Saved → {_saved_ws_title}, row {_saved_row_idx}")
                            saved = True
                        else:
                            ws_found, row_idx = find_row_for_shoot(_saved_female, _saved_studio)
                            if ws_found and row_idx:
                                _do_save(ws_found, row_idx, fields)
                                st.success(f"Saved → {ws_found.title}, row {row_idx}")
                                saved = True
                            else:
                                st.info("No matching row — not saved to sheet.")
                    except Exception as _e:
                        st.error(f"Save failed: {_e}")
                    try:
                        from training_data import save_accepted
                        save_accepted(_saved_studio, parsed, fields, _saved_research)
                    except Exception as _te:
                        st.warning(f"Training data not saved: {_te}")
                    if saved:
                        del st.session_state["last_script"]
                        st.rerun()
            with _a2:
                feedback = st.text_input("Director's note", placeholder="What to change…",
                                         key="sc_regen_feedback", label_visibility="collapsed")
                if feedback:
                    st.session_state["director_note_override"] = feedback
            with _a3:
                if st.button("↩ Regenerate", use_container_width=True, key="sc_reject"):
                    try:
                        from training_data import save_rejected
                        save_rejected(_saved_studio, parsed, fields, feedback=feedback or "")
                    except Exception as _te:
                        st.warning(f"Training data not saved: {_te}")
                    del st.session_state["last_script"]
                    st.rerun()

        # ─────────────────────────────────────────────────────────────────────────
        # Shared: generate a script (non-streaming) — used by both single & batch
        # ─────────────────────────────────────────────────────────────────────────
        def _generate_script_core(parsed, female, male, research_context=""):
            """Generate a script via Claude or Ollama. Returns (full_text, fields, violations)."""
            prompt = build_prompt(parsed, research_context=research_context)
            full_text = ""
            _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if _claude_key:
                import anthropic as _anthropic
                _ac = _anthropic.Anthropic(api_key=_claude_key)
                _resp = _ac.messages.create(
                    model="claude-sonnet-4-6", max_tokens=600,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                full_text = _resp.content[0].text or ""
            else:
                _ollama = get_ollama_client()
                _model = st.session_state.get("selected_model", OLLAMA_MODEL)
                _resp = _ollama.chat.completions.create(
                    model=_model, max_tokens=800, temperature=0.82,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ], stream=False,
                )
                full_text = _resp.choices[0].message.content or ""
            full_text = _post_process(full_text)
            fields, violations = _parse_and_validate(full_text, female=female, male=male)
            return full_text, fields, violations

        # ─────────────────────────────────────────────────────────────────────────
        # Core: research + stream + store result (single mode with streaming UI)
        # ─────────────────────────────────────────────────────────────────────────
        def _run_single_generation(parsed, studio, female, male, scene_norm,
                                    selected_ws, selected_row_idx, theme_hint):
            is_njoi = studio == "NaughtyJOI"

            if is_njoi:
                st.markdown(f"**NaughtyJOI Plot:**\n\n{NJOI_STATIC_PLOT}")
                try:
                    if selected_ws and selected_row_idx:
                        write_script(selected_ws, selected_row_idx, theme="JOI",
                                     plot=NJOI_STATIC_PLOT, wardrobe_female="", wardrobe_male="")
                        st.success(f"✅ Saved → {selected_ws.title}, row {selected_row_idx}")
                    else:
                        ws_f, row_f = find_row_for_shoot(female, studio)
                        if ws_f and row_f:
                            write_script(ws_f, row_f, theme="JOI",
                                         plot=NJOI_STATIC_PLOT, wardrobe_female="", wardrobe_male="")
                except Exception as _e:
                    st.warning(f"Could not save: {_e}")
                return

            ollama       = get_ollama_client()
            model        = st.session_state.get("selected_model", OLLAMA_MODEL)
            output_area  = st.empty()
            full_text    = ""

            # Research step
            research_context = ""
            _was_cached = False
            with st.spinner(f"Researching {female}…"):
                from script_writer import cache_get
                research_context = cache_get(female.strip()) or ""
                if research_context:
                    _was_cached = True
                else:
                    research_context = research_scene_trends(female.strip(), ollama_client=ollama, model=model) or ""

            if research_context:
                _cache_label = "📊 Platform Research (cached)" if _was_cached else "📊 Platform Research"
                with st.expander(_cache_label, expanded=False):
                    st.text(research_context)
            else:
                st.caption(f"ℹ️ No research found for {female} — writing without.")

            # Build banned scenario list from recent plots
            _recent_themes  = st.session_state.get("recent_themes", [])
            _recent_plots   = st.session_state.get("recent_plots", [])
            _banned_keywords = set()
            _SCENARIO_KEYWORDS = {
                "neighbor": ["neighbor", "across the hall", "apartment complex", "moving in", "grocery bags", "boxes scattered"],
                "gym":      ["gym", "personal trainer", "workout", "resistance bands", "exercise equipment"],
                "office":   ["office", "coworker", "boss", "boardroom"],
                "massage":  ["massage therapist", "massage therapy", "spa therapist", "massage table"],
            }
            for _plot in _recent_plots[-4:]:
                _plot_lower = _plot.lower()
                for _concept, _keys in _SCENARIO_KEYWORDS.items():
                    if any(_k in _plot_lower for _k in _keys):
                        _banned_keywords.add(_concept)

            # Permanently overused scenarios — always banned regardless of session history
            _banned_keywords.add("neighbor")
            _banned_keywords.add("gym")
            _banned_keywords.add("massage")
            _banned_keywords.add("art")

            _avoid_hint = "STRICTLY BANNED — do NOT write any version of these scenarios:\n"
            _avoid_hint += f"- BANNED SCENARIO TYPES: {', '.join(sorted(_banned_keywords))}\n"
            _avoid_hint += "  (neighbor/moving-in, gym/personal trainer, massage/spa, art/gallery = ALWAYS banned)\n"
            if _recent_themes:
                _avoid_hint += f"- BANNED THEME TITLES (already used): {', '.join(_recent_themes[-5:])}\n"
            _avoid_hint += "You MUST pick a completely different scenario type — something with a real job, skill, or service relationship.\n"

            # Inject banned list INTO the parsed dict so build_prompt places it
            # BEFORE the final "Start your response with THEME:" instruction.
            existing_hint = parsed.get("theme_hint") or ""
            parsed["theme_hint"] = (_avoid_hint + ("\n" + existing_hint if existing_hint else "")).strip()

            prompt = build_prompt(parsed, research_context=research_context)

            with st.spinner(f"Writing script…"):
                try:
                    import anthropic as _anthropic
                    _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
                    if _claude_key:
                        # Use Claude Sonnet for writing quality — research already done by Ollama above
                        _ac = _anthropic.Anthropic(api_key=_claude_key)
                        with _ac.messages.stream(
                            model="claude-sonnet-4-6",
                            max_tokens=600,
                            system=SYSTEM_PROMPT,
                            messages=[{"role": "user", "content": prompt}],
                        ) as _stream:
                            for _chunk in _stream.text_stream:
                                full_text += _chunk
                                output_area.markdown(full_text)
                    else:
                        # Fallback to Ollama if no Claude key
                        stream = ollama.chat.completions.create(
                            model=model, max_tokens=800, temperature=0.82,
                            messages=[
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user",   "content": prompt},
                            ],
                            stream=True,
                        )
                        for chunk in stream:
                            delta = chunk.choices[0].delta.content or ""
                            full_text += delta
                            output_area.markdown(full_text)
                except Exception as api_err:
                    st.error(f"Generation error: {api_err}")
                    return

            full_text = _post_process(full_text)
            output_area.empty()  # Clear streaming text — formatted result shown below
            fields, violations = _parse_and_validate(full_text, female=female, male=male)

            # Track recent themes + plots to avoid repeats
            _theme = fields.get("theme", "").strip()
            _plot  = fields.get("plot",  "").strip()
            if _theme:
                _rt = st.session_state.get("recent_themes", [])
                _rt.append(_theme)
                st.session_state["recent_themes"] = _rt[-6:]
            if _plot:
                _rp = st.session_state.get("recent_plots", [])
                _rp.append(_plot)
                st.session_state["recent_plots"] = _rp[-6:]

            st.session_state["last_script"] = {
                "full_text": full_text, "fields": fields, "violations": violations,
                "parsed": parsed, "studio": studio, "female": female, "male": male or "",
                "research_context": research_context,
                "ws_title": selected_ws.title if selected_ws else None,
                "row_idx": selected_row_idx, "scene_norm": scene_norm,
            }

        # =========================================================================
        # MANUAL MODE
        # =========================================================================
        if mode == "✏️ Manual":
            # ── Studio + Scene Type ───────────────────────────────────────────────
            _sa, _sb = st.columns([3, 1])
            with _sa:
                studio = st.pills("Studio", ["VRHush", "FuckPassVR", "VRAllure", "NaughtyJOI"],
                                  selection_mode="single", default="VRHush", key="sc_studio")
            studio = studio or "VRHush"

            destination    = None
            scene_type_val = None
            male           = None

            with _sb:
                if studio == "VRAllure":
                    scene_type_val = st.pills("Scene Type", ["Waking Up", "Pornstar Experience"],
                                              selection_mode="single", default="Waking Up", key="sc_type_vra")
                    scene_type_val = scene_type_val or "Waking Up"
                elif studio == "NaughtyJOI":
                    scene_type_val = "JOI"
                    st.caption("JOI — fixed plot")
                elif studio == "FuckPassVR":
                    destination = st.text_input("Destination", placeholder="e.g. Paris, France",
                                                key="sc_dest", label_visibility="collapsed")
                else:
                    _raw = st.pills("Scene Type", ["BG", "BGCP"],
                                    selection_mode="single", default="BG", key="sc_type_bg")
                    _raw = _raw or "BG"
                    scene_type_val = "BGCP" if "BGCP" in _raw else "BG"

            # ── Talent ────────────────────────────────────────────────────────────
            if studio in ("VRAllure", "NaughtyJOI"):
                female = st.text_input("Female Talent", placeholder="e.g. Lucy Lotus", key="sc_female_solo")
            else:
                _fc, _mc = st.columns(2)
                with _fc:
                    female = st.text_input("Female Talent", placeholder="e.g. Lucy Lotus", key="sc_female")
                with _mc:
                    male = st.text_input("Male Talent", placeholder="e.g. Danny Steele", key="sc_male")

            # ── Director's note + Generate on same row ────────────────────────────
            _default_note = st.session_state.pop("director_note_override", "")
            _nc, _bc = st.columns([5, 1])
            with _nc:
                theme_hint = st.text_input("Director's Note", value=_default_note,
                                           placeholder="e.g. They meet at a hotel bar…",
                                           key="sc_note")
            with _bc:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                _gen_clicked = st.button("Generate", type="primary",
                                         use_container_width=True, key="sc_manual_gen")

            if _gen_clicked:
                errors = []
                if not (female or "").strip():
                    errors.append("Female talent is required.")
                if studio not in ("VRAllure", "NaughtyJOI") and not (male or "").strip():
                    errors.append("Male talent is required.")
                for e in errors:
                    st.error(e)
                if not errors:
                    parsed, scene_norm = _build_parsed(
                        studio, female.strip(), (male or "").strip(),
                        scene_type_val, destination, theme_hint.strip() or None,
                    )
                    _run_single_generation(parsed, studio, female.strip(), (male or "").strip(),
                                           scene_norm, None, None, theme_hint)

            _show_single_result()

            # System Check — developer only
            with st.expander("⚙️ Developer Tools", expanded=False):
                if st.button("Run System Check", key="sc_selfcheck"):
                    _sc_model = st.session_state.get("selected_model", OLLAMA_MODEL)
                    try:
                        _base = OLLAMA_BASE_URL.replace("/v1", "")
                        _resp = _requests.get(f"{_base}/api/tags", timeout=4)
                        _avail = [m["name"] for m in _resp.json().get("models", [])]
                        if _sc_model in _avail:
                            st.caption(f"Ollama: **{_sc_model}** loaded")
                        else:
                            st.caption(f"Ollama: **{_sc_model}** not found — available: {', '.join(_avail[:4])}")
                    except Exception as _e:
                        st.caption(f"Ollama unreachable: {_e}")
                    try:
                        _sh2 = get_spreadsheet()
                        _tabs2 = month_tabs(_sh2)
                        st.caption(f"Sheet: connected — {len(_tabs2)} tab(s)")
                    except Exception as _e:
                        st.caption(f"Sheet error: {_e}")

        # =========================================================================
        # FROM SHEET MODE
        # =========================================================================
        else:
            # ── Control bar: month + filter + refresh ─────────────────────────────
            _cc1, _cc2, _cc3, _cc4 = st.columns([2, 4, 1, 1])

            # Load tab list once, cache in session_state
            if "sc_tab_list" not in st.session_state:
                try:
                    sh = get_spreadsheet()
                    _all_tabs = month_tabs(sh)
                    st.session_state["sc_tab_list"]  = _all_tabs
                    st.session_state["sc_tab_names"] = [ws.title for ws in _all_tabs]
                except Exception as _e:
                    st.error(f"Could not connect to sheet: {_e}")

            _all_tabs  = st.session_state.get("sc_tab_list",  [])
            _tab_names = st.session_state.get("sc_tab_names", [])

            with _cc1:
                _chosen_month = st.selectbox("Month", _tab_names, key="sc_month",
                                             label_visibility="collapsed") if _tab_names else None
            with _cc2:
                _ftext = st.text_input("Filter", placeholder="Filter by name, studio, scene…",
                                       key="sc_filter", label_visibility="collapsed")
            with _cc3:
                if st.button("↺", key="sc_refresh_tabs", use_container_width=True,
                             help="Refresh sheet tabs"):
                    try:
                        sh = get_spreadsheet()
                        _all_tabs = month_tabs(sh)
                        st.session_state["sc_tab_list"]  = _all_tabs
                        st.session_state["sc_tab_names"] = [ws.title for ws in _all_tabs]
                        for _k in list(st.session_state.keys()):
                            if _k.startswith("sc_rows_"):
                                del st.session_state[_k]
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Refresh failed: {_e}")

            with _cc4:
                with st.popover("Regen"):
                    _regen_name = st.text_input("Talent name", placeholder="e.g. Lucy Lotus",
                                                key="sc_regen_talent")
                    if st.button("Mark for Regen", key="sc_regen_btn", use_container_width=True):
                        if _regen_name.strip():
                            _marked = mark_talent_for_regen(_regen_name.strip())
                            if _marked:
                                st.success(f"Marked {len(_marked)} row(s).")
                            else:
                                st.warning("No rows found.")
                        else:
                            st.error("Enter a name.")

            if not _chosen_month:
                st.info("No sheet tabs found — check connection.")
            else:
                _ws = next((t for t in _all_tabs if t.title == _chosen_month), None)
                if _ws:
                    # Only fetch rows when the month changes — cache to avoid API quota hits
                    _row_cache_key = f"sc_rows_{_chosen_month}"
                    if _row_cache_key not in st.session_state:
                        with st.spinner("Loading sheet…"):
                            try:
                                st.session_state[_row_cache_key] = _ws.get_all_values()
                            except Exception as _e:
                                st.error(f"Could not load rows: {_e}")
                                st.session_state[_row_cache_key] = []
                    _all_rows = st.session_state[_row_cache_key]

                    # Process + sort once per month (cached), then filter per keystroke
                    _sorted_cache_key = f"sc_sorted_{_chosen_month}"
                    if _sorted_cache_key not in st.session_state:
                        _scene_opts_sorted = []
                        for _i, _row in enumerate(_all_rows[1:], start=2):
                            while len(_row) <= max(COL_STUDIO, COL_FEMALE, COL_SCENE, COL_MALE, COL_LOCATION, COL_DATE, COL_PLOT):
                                _row.append("")
                            _s = _row[COL_STUDIO].strip()
                            _f = _row[COL_FEMALE].strip()
                            if not _s or not _f:
                                continue
                            _m      = _row[COL_MALE].strip()
                            _sc     = _row[COL_SCENE].strip()
                            _loc    = _row[COL_LOCATION].strip()
                            _dt     = _row[COL_DATE].strip()
                            _pltxt  = _row[COL_PLOT].strip()
                            _thtxt  = _row[COL_THEME].strip() if len(_row) > COL_THEME else ""
                            _titxt  = _row[COL_TITLE].strip() if len(_row) > COL_TITLE else ""
                            _hp     = bool(_pltxt)
                            _scene_opts_sorted.append({
                                "Select": False,
                                "✓": "✓" if _hp else "",
                                "Female": _f, "Male": _m, "Studio": _s,
                                "Scene": _sc, "Date": _dt,
                                "_row_idx": _i, "_studio": _s, "_female": _f,
                                "_male": _m, "_scene": _sc, "_loc": _loc, "_hp": _hp,
                                "_plot": _pltxt, "_theme": _thtxt, "_title": _titxt,
                            })
                        from datetime import datetime as _dt_sort2
                        def _date_sort_key(o):
                            d = o.get("Date", "").strip()
                            for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y"):
                                try:
                                    return (_dt_sort2.strptime(d, fmt), o["Female"].lower())
                                except ValueError:
                                    continue
                            return (_dt_sort2.max, o["Female"].lower())
                        _scene_opts_sorted.sort(key=_date_sort_key)
                        st.session_state[_sorted_cache_key] = _scene_opts_sorted

                    _scene_opts = st.session_state[_sorted_cache_key]

                    # Apply filter (lightweight — only runs the list comprehension)
                    if _ftext.strip():
                        _q = _ftext.strip().lower()
                        _scene_opts = [o for o in _scene_opts
                                       if _q in f"{o['Female']} {o['Studio']} {o['Scene']} {o['Date']}".lower()]

                    if not _scene_opts:
                        st.info("No scenes found — try a different filter or month.")
                    else:
                        # ── Stats bar + batch toggle ──────────────────────────────
                        _total   = len(_scene_opts)
                        _done    = sum(1 for o in _scene_opts if o["_hp"])
                        _pending = _total - _done
                        _pct     = int(_done / _total * 100) if _total else 0
                        _sb1, _sb2 = st.columns([5, 1])
                        with _sb1:
                            st.markdown(
                                f"<div style='background:#111827;border-radius:6px;padding:6px 12px;margin:4px 0;"
                                f"display:flex;align-items:center;gap:14px'>"
                                f"<div style='flex:1;height:4px;background:#1f2937;border-radius:2px;overflow:hidden'>"
                                f"<div style='width:{_pct}%;height:100%;background:#4caf50;border-radius:2px'></div></div>"
                                f"<span style='color:#ddd;font-size:0.8rem;white-space:nowrap'>"
                                f"<b>{_done}</b><span style='color:#666'>/{_total}</span> scripted"
                                f"</span></div>",
                                unsafe_allow_html=True
                            )
                        with _sb2:
                            _batch_mode = st.toggle("Batch", key="sc_batch_toggle", value=False)

                        # Clear selection when filter/month changes
                        _state_sig = f"{_chosen_month}|{_ftext}"
                        if st.session_state.get("sc_state_sig") != _state_sig:
                            st.session_state["sc_state_sig"]   = _state_sig
                            st.session_state["sc_selected_idx"] = None
                            for _k in list(st.session_state.keys()):
                                if _k.startswith("sc_chk_"):
                                    del st.session_state[_k]

                        # ── Scene card list ───────────────────────────────────────
                        _sel_idx = st.session_state.get("sc_selected_idx")

                        for _ci, _opt in enumerate(_scene_opts):
                            _is_sel  = (_sel_idx == _ci)
                            _card_bg = "#1c2e1c" if _opt["_hp"] else "#2a2314"
                            _border  = "#4caf50" if _opt["_hp"] else "#ff9800"
                            _sel_bg  = "#1a2a3a"
                            if _is_sel:
                                _card_bg, _border = _sel_bg, "#4a9eff"

                            _male_part  = (f"<span style='color:#888;font-size:0.85rem'> · {_opt['Male']}</span>"
                                           if _opt.get("Male") else "")
                            _scene_part = (f"<span style='background:#1e2d40;border-radius:3px;"
                                           f"padding:1px 7px;font-size:0.78rem;margin-left:6px'>{_opt['Scene']}</span>"
                                           if _opt.get("Scene") else "")
                            _done_badge      = "&nbsp;&nbsp;<span style='color:#4caf50;font-size:0.8rem'>✓ scripted</span>" if _opt["_hp"] else ""
                            _done_badge_mini = "&nbsp;&nbsp;<span style='color:#4caf50;font-size:0.8rem'>✓</span>" if _opt["_hp"] else ""
                            _studio_pill = (f"<span style='background:#1e3a5f;border-radius:3px;padding:1px 7px;"
                                            f"font-size:0.78rem;margin-left:8px'>{_opt['Studio']}</span>")
                            _date_span   = (f"<span style='color:#999;font-size:0.78rem;width:55px;"
                                            f"display:inline-block'>{_opt['Date']}</span>")
                            _name_span   = f"<b style='font-size:0.95rem'>{_opt['Female']}</b>"
                            _card_inner  = f"{_date_span}{_name_span}{_male_part}{_studio_pill}{_scene_part}"
                            # For scripted rows: show theme + title snippet as a second line
                            _theme_line = ""
                            if _opt["_hp"]:
                                _th = _opt.get("_theme", "")
                                _ti = _opt.get("_title", "")
                                _parts2 = []
                                if _th: _parts2.append(f"<span style='color:#6ee7b7'>{_th}</span>")
                                if _ti: _parts2.append(f"<span style='color:#9ca3af;font-style:italic'>{_ti}</span>")
                                if _parts2:
                                    _theme_line = f"<div style='font-size:0.72rem;margin-top:3px;padding-left:55px'>{'&nbsp;·&nbsp;'.join(_parts2)}</div>"

                            if _batch_mode:
                                _cb_col, _card_col = st.columns([1, 14])
                                with _cb_col:
                                    st.checkbox("", key=f"sc_chk_{_ci}", label_visibility="collapsed")
                                with _card_col:
                                    st.markdown(
                                        f"<div style='background:{_card_bg};border-left:3px solid {_border};"
                                        f"border-radius:5px;padding:7px 12px;margin:1px 0'>"
                                        f"{_card_inner}{_done_badge}{_theme_line}</div>",
                                        unsafe_allow_html=True
                                    )
                            else:
                                _card_col, _btn_col = st.columns([8, 3])
                                with _card_col:
                                    st.markdown(
                                        f"<div style='background:{_card_bg};border-left:3px solid {_border};"
                                        f"border-radius:5px;padding:7px 12px;margin:1px 0'>"
                                        f"{_card_inner}{_done_badge_mini}{_theme_line}</div>",
                                        unsafe_allow_html=True
                                    )
                                with _btn_col:
                                    _blabel = "▼ Selected" if _is_sel else ("View / Edit" if _opt["_hp"] else "Generate →")
                                    if st.button(_blabel, key=f"sc_sel_{_ci}",
                                                 use_container_width=True,
                                                 type="primary" if _is_sel else "secondary"):
                                        if _is_sel:
                                            st.session_state["sc_selected_idx"] = None
                                        else:
                                            st.session_state["sc_selected_idx"] = _ci
                                        st.rerun()

                        # ── Action panel ──────────────────────────────────────────
                        if _batch_mode:
                            _sel_rows = [_scene_opts[_ci] for _ci in range(len(_scene_opts))
                                         if st.session_state.get(f"sc_chk_{_ci}", False)]
                            _n = len(_sel_rows)
                            _dry = st.checkbox("Dry run (preview only, don't write to sheet)", value=False, key="sc_dry")
                        else:
                            _sel_idx = st.session_state.get("sc_selected_idx")
                            if _sel_idx is not None and _sel_idx < len(_scene_opts):
                                _ch = _scene_opts[_sel_idx]
                                st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

                                # ── If scripted and no fresh result yet, show existing content ──
                                if _ch["_hp"] and "last_script" not in st.session_state:
                                    _ex_plot  = _ch.get("_plot", "")
                                    _ex_theme = _ch.get("_theme", "")
                                    _ex_title = _ch.get("_title", "")
                                    if _ex_theme:
                                        st.caption(f"**Theme:** {_ex_theme}" + (f"  ·  **Title:** {_ex_title}" if _ex_title else ""))
                                    _edited_existing = st.text_area(
                                        "Existing script — edit and save, or regenerate below",
                                        value=_ex_plot, height=160,
                                        key=f"sc_existing_{_sel_idx}",
                                        label_visibility="visible",
                                    )
                                    _sa1, _sa2 = st.columns(2)
                                    with _sa1:
                                        if st.button("💾 Save edits", key="sc_save_existing", use_container_width=True, type="primary"):
                                            try:
                                                _ws.update_cell(_ch["_row_idx"], COL_PLOT + 1, _edited_existing)
                                                st.success("Saved to sheet")
                                                del st.session_state[f"sc_rows_{_chosen_month}"]
                                                st.rerun()
                                            except Exception as _se:
                                                st.error(f"Save failed: {_se}")
                                    with _sa2:
                                        st.markdown("")  # spacer
                                    st.divider()

                                _default_note = st.session_state.pop("director_note_override", "")
                                _note = st.text_area("Director's note (optional)", value=_default_note,
                                                     placeholder="e.g. They meet at a hotel bar…",
                                                     height=70, key="sc_sheet_note")
                                _gen_label = "Regenerate Script" if _ch["_hp"] else "Generate Script"
                                if st.button(_gen_label, type="primary" if not _ch["_hp"] else "secondary",
                                             use_container_width=True, key="sc_sheet_single"):
                                    _parsed, _snorm = _build_parsed(
                                        _ch["_studio"], _ch["_female"], _ch["_male"],
                                        _ch["_scene"], _ch["_loc"], _note.strip() or None,
                                    )
                                    _run_single_generation(
                                        _parsed, _ch["_studio"], _ch["_female"], _ch["_male"],
                                        _snorm, _ws, _ch["_row_idx"], _note,
                                    )
                                _show_single_result()
                            else:
                                _show_single_result()
                            _sel_rows = []
                            _n = 0

                        # ── Batch generate ────────────────────────────────────────
                        if _batch_mode:
                            _dry = st.session_state.get("sc_dry", False)
                            if st.button(f"Generate {_n} Scripts", type="primary",
                                         use_container_width=True, key="sc_batch_gen",
                                         disabled=(_n == 0)):
                                _ollama  = get_ollama_client()
                                _bmodel  = st.session_state.get("selected_model", OLLAMA_MODEL)
                                _prog    = st.progress(0)
                                _results = []

                                for _bi, _row in enumerate(_sel_rows):
                                    _bstudio = _row["_studio"]
                                    _bfemale = _row["_female"]
                                    _bmale   = _row["_male"]
                                    _bloc    = _row["_loc"]
                                    _bscene  = _row["_scene"]
                                    _blow    = _bstudio.lower()

                                    if _dry:
                                        _prog.progress((_bi + 1) / _n)
                                        _results.append({"label": f"{_bfemale} ({_bstudio})", "dry_run": True})
                                        continue

                                    if _blow in ("naughtyjoi", "njoi"):
                                        write_script(_ws, _row["_row_idx"], theme="JOI",
                                                     plot=NJOI_STATIC_PLOT, wardrobe_female="", wardrobe_male="")
                                        _results.append({"label": f"{_bfemale} (NaughtyJOI)",
                                                         "auto_saved": True, "ws": _ws, "row_idx": _row["_row_idx"]})
                                        _prog.progress((_bi + 1) / _n)
                                        continue

                                    if _blow in ("vrallure", "vra"):
                                        _bvra = "Pornstar Experience" if "pornstar" in _bscene.lower() else \
                                                "Waking Up" if "waking" in _bscene.lower() else None
                                        _bparsed = {"studio": "VRAllure", "female": _bfemale, "vra_scene_type": _bvra}
                                        _bsnorm  = _bvra or "VRAllure"
                                    else:
                                        _bsnorm  = "BGCP" if "CP" in _bscene.upper() or "CREAMPIE" in _bscene.upper() else "BG"
                                        _bparsed = {"studio": _bstudio, "destination": _bloc or None,
                                                    "scene_type": _bsnorm, "female": _bfemale, "male": _bmale}

                                    with st.spinner(f"Writing: {_bfemale}…"):
                                        from script_writer import cache_get
                                        _brc = cache_get(_bfemale.strip()) or ""
                                        _btext, _bfields, _bviols = _generate_script_core(
                                            _bparsed, _bfemale, _bmale, research_context=_brc
                                        )

                                    _results.append({
                                        "label": f"{_bfemale} — {_bstudio}",
                                        "ws": _ws, "row_idx": _row["_row_idx"],
                                        "parsed": _bparsed, "fields": _bfields,
                                        "full_text": _btext, "research": "",
                                        "violations": _bviols,
                                    })
                                    _prog.progress((_bi + 1) / _n)

                                st.session_state["batch_results"]   = _results
                                st.session_state["batch_decisions"] = {}
                                st.rerun()

                            # ── Batch review queue ────────────────────────────────
                            if st.session_state.get("batch_results"):
                                _bresults   = st.session_state["batch_results"]
                                _bdecisions = st.session_state.setdefault("batch_decisions", {})

                                # Find the single next pending script
                                _next_idx = next(
                                    (j for j, r in enumerate(_bresults)
                                     if not r.get("auto_saved") and not r.get("dry_run")
                                     and j not in _bdecisions), None)
                                _total_reviewable = sum(1 for r in _bresults
                                                        if not r.get("auto_saved") and not r.get("dry_run"))
                                _reviewed = sum(1 for i, r in enumerate(_bresults)
                                                if not r.get("auto_saved") and not r.get("dry_run")
                                                and i in _bdecisions)

                                st.divider()

                                # Progress strip (CSS dots)
                                _dot = lambda c: f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{c};margin:0 2px'></span>"
                                _prog_dots = ""
                                for _pi, _pr in enumerate(_bresults):
                                    if _pr.get("auto_saved"):  _prog_dots += _dot("#22c55e")
                                    elif _pr.get("dry_run"):   _prog_dots += _dot("#374151")
                                    elif _pi in _bdecisions:
                                        _prog_dots += _dot("#22c55e" if _bdecisions[_pi] == "accepted" else "#ef4444")
                                    elif _pi == _next_idx:     _prog_dots += _dot("#3b82f6")
                                    else:                      _prog_dots += _dot("#1f2937")
                                st.markdown(
                                    f"<div style='display:flex;align-items:center;gap:8px;margin:0 0 8px'>"
                                    f"<div>{_prog_dots}</div>"
                                    f"<span style='font-size:0.8rem;color:#aaa'>"
                                    f"<b style='color:#ddd'>{_reviewed}</b>/{_total_reviewable} reviewed</span></div>",
                                    unsafe_allow_html=True)

                                if _next_idx is None:
                                    st.success("All scripts reviewed.", icon="✅")
                                    if st.button("Clear results", key="sc_batch_clear"):
                                        del st.session_state["batch_results"]
                                        del st.session_state["batch_decisions"]
                                        st.rerun()
                                else:
                                    _bi2  = _next_idx
                                    _bres = _bresults[_bi2]
                                    _bf   = _bres["fields"]
                                    _bv   = _bres["violations"]

                                    # Compact script card
                                    st.markdown(
                                        f"<div style='background:#111827;border-radius:8px;"
                                        f"padding:12px 16px;border-left:3px solid "
                                        f"{'#f59e0b' if _bv else '#22c55e'}'>"
                                        f"<span style='font-size:1.05rem;font-weight:700'>{_bres['label']}</span>"
                                        f"<span style='color:#888;margin-left:10px;font-size:0.85rem'>"
                                        f"{_bf.get('theme','')}</span><br>"
                                        f"<span style='color:#aaa;font-size:0.82rem'>"
                                        f"👗 {_bf.get('wardrobe_female','—')}</span>"
                                        + (f"&emsp;<span style='color:#aaa;font-size:0.82rem'>"
                                           f"👔 {_bf.get('wardrobe_male','')}</span>"
                                           if _bf.get('wardrobe_male') else "")
                                        + f"</div>",
                                        unsafe_allow_html=True)

                                    if _bv:
                                        st.warning(" · ".join(_bv), icon="⚠️")

                                    st.text_area("Plot", value=_bf.get("plot", ""),
                                                 height=90, key=f"sc_plot_{_bi2}", disabled=True)

                                    _bca, _bcb = st.columns(2)
                                    with _bca:
                                        if st.button("👍 Accept & Save", key=f"sc_acc_{_bi2}",
                                                     use_container_width=True, type="primary"):
                                            try:
                                                _do_save(_bres["ws"], _bres["row_idx"], _bf)
                                                try:
                                                    from training_data import save_accepted
                                                    save_accepted(_bres["parsed"]["studio"],
                                                                  _bres["parsed"], _bf, _bres["research"])
                                                except Exception as _te:
                                                    st.warning(f"Training data not saved: {_te}")
                                                _bdecisions[_bi2] = "accepted"
                                                st.session_state["batch_decisions"] = _bdecisions
                                                st.rerun()
                                            except Exception as _e:
                                                st.error(f"Save failed: {_e}")
                                    with _bcb:
                                        if st.button("👎 Skip", key=f"sc_skip_{_bi2}",
                                                     use_container_width=True):
                                            try:
                                                from training_data import save_rejected
                                                save_rejected(_bres["parsed"]["studio"],
                                                              _bres["parsed"], _bf)
                                            except Exception:
                                                pass
                                            _bdecisions[_bi2] = "rejected"
                                            st.session_state["batch_decisions"] = _bdecisions
                                            st.rerun()

    # ── TAB 2 (was TAB 3): Call Sheets

    # ── TAB 3: Call Sheets ────────────────────────────────────────────────────────
with tab_callsheet:
    if _has_tab("Call Sheets"):

        if not HAS_CALL_SHEET:
            st.error("call_sheet.py not found — check deployment.")
        else:
            _cs1, _cs2, _cs3 = st.columns([3, 2, 1])
            with _cs1:
                if "cs_budget_tabs" not in st.session_state:
                    try:
                        st.session_state["cs_budget_tabs"] = get_budget_tabs()
                    except Exception as e:
                        st.session_state["cs_budget_tabs"] = []
                        st.error(f"Could not read Shoot Budgets sheet: {e}")
                budget_tabs = st.session_state["cs_budget_tabs"]
                selected_month = st.selectbox("Month", budget_tabs, key="cs_month",
                                              label_visibility="collapsed") if budget_tabs else None
            with _cs2:
                _cs_gen_all = st.button(f"Generate All for {selected_month or '...'}", key="cs_all",
                                        type="primary", use_container_width=True) if selected_month else False
            with _cs3:
                door_code = st.text_input("🔑 Door Code", value="1322", key="cs_door")

            if selected_month:
                _sd_cache_key = f"cs_shoot_dates_{selected_month}"
                if _sd_cache_key not in st.session_state:
                    with st.spinner("Loading shoot dates..."):
                        try:
                            st.session_state[_sd_cache_key] = get_shoot_dates(tab_name=selected_month)
                        except Exception as e:
                            st.session_state[_sd_cache_key] = {}
                            st.error(f"Could not read shoot dates: {e}")
                shoot_dates = st.session_state[_sd_cache_key]

                if not shoot_dates:
                    st.info("No shoots found for this month.")
                else:
                    st.caption(f"{len(shoot_dates)} shoot date(s) found")

                    if _cs_gen_all:
                        results, errors = [], []
                        reload_script_cache()
                        prog = st.progress(0, text="Generating...")
                        date_keys = sorted(shoot_dates.keys())
                        for i, date_key in enumerate(date_keys):
                            scenes = shoot_dates[date_key]
                            prog.progress((i) / len(date_keys), text=f"Generating {date_key}...")
                            try:
                                result = generate_call_sheet(date_key, scenes, door_code=door_code)
                                results.append(result)
                            except Exception as e:
                                errors.append((date_key, str(e)))
                        prog.progress(1.0, text="Done!")
                        for r in results:
                            st.success(f"✅ [{r['title']}]({r['doc_url']})")
                        for date_key, err in errors:
                            st.error(f"❌ {date_key}: {err}")

                    st.divider()
                    for date_key in sorted(shoot_dates.keys()):
                        scenes = shoot_dates[date_key]
                        dt = scenes[0]["date_dt"]
                        date_label = dt.strftime("%B {day}, %Y").replace("{day}", str(dt.day))
                        females = list(dict.fromkeys(s["female"] for s in scenes if s["female"]))
                        studios = list(dict.fromkeys(s["studio"] for s in scenes if s["studio"]))
                        types   = list(dict.fromkeys(s["type"]   for s in scenes if s["type"]))

                        with st.expander(f"**{date_label}** — {', '.join(females)} | {', '.join(studios)} | {', '.join(types)}"):
                            # Scene table
                            scene_rows = [{"Studio": s["studio"], "Type": s["type"], "Female": s["female"], "Male": s["male"], "Agency": s["agency"]} for s in scenes]
                            import pandas as _pd
                            st.dataframe(_pd.DataFrame(scene_rows), use_container_width=True, hide_index=True)

                            if st.button(f"Generate Call Sheet", key=f"cs_{date_key}", type="primary"):
                                with st.spinner("Creating Google Doc..."):
                                    try:
                                        reload_script_cache()
                                        result = generate_call_sheet(date_key, scenes, door_code=door_code)
                                        st.success("Call sheet created!")
                                        st.markdown(f"**[Open in Google Docs]({result['doc_url']})**")
                                        st.caption(result["title"])
                                    except Exception as e:
                                        st.error(f"Failed: {e}")
                                        import traceback
                                        st.code(traceback.format_exc())


    # ── TAB 4: Titles ─────────────────────────────────────────────────────────────
with tab_titles:
    if _has_tab("Titles"):

        try:
            import cta_generator as _cta
            HAS_CTA = True
        except ImportError as _cta_err:
            HAS_CTA = False
            st.error(f"cta_generator.py not found — copy it to the project folder. ({_cta_err})")

        if HAS_CTA:
            # ── Engine + title on one row ─────────────────────────────────────────
            _te1, _te2 = st.columns([1, 3])
            with _te1:
                _engine = st.segmented_control("Engine", ["☁️ Cloud", "🖥️ Local"],
                                               default="☁️ Cloud", key="ti_engine",
                                               label_visibility="collapsed")
                _engine = _engine or "☁️ Cloud"
            _use_cloud = _engine == "☁️ Cloud"
            with _te2:
                _ti_title = st.text_input(
                    "Title text",
                    placeholder="e.g. Forbidden Fantasy, Neon Nights, Gold Rush",
                    key="ti_title",
                )
            if _use_cloud:
                st.caption("☁️ **Cloud** — Ideogram V3 via fal.ai · photorealistic AI text · ~$0.03/image · 5–15s")
            else:
                st.caption("🖥️ **Local** — PIL graphic treatments · instant & free · 690+ styles")

            if _use_cloud:
                # Cloud mode — style picker
                try:
                    import cloud_renderer as _cr
                    _cloud_styles = list(_cr.CLOUD_STYLES.keys())
                except Exception:
                    _cloud_styles = []

                col_style, col_n = st.columns([3, 1])
                with col_style:
                    _cloud_style_mode = st.radio(
                        "Style",
                        ["🔀 Random mix", "🎨 Pick one"],
                        horizontal=True,
                        key="ti_cloud_style_mode",
                        label_visibility="collapsed",
                    )
                with col_n:
                    _ti_n = st.number_input("Variations", min_value=1, max_value=20, value=6, key="ti_n_cloud")

                if _cloud_style_mode == "🎨 Pick one" and _cloud_styles:
                    _picked_style = st.selectbox("Style", _cloud_styles, key="ti_cloud_pick")
                else:
                    _picked_style = None

                if st.button("Generate Title PNGs", type="primary", use_container_width=True, key="ti_gen_cloud"):
                    if not _ti_title.strip():
                        st.error("Enter a title first.")
                    elif not _cloud_styles:
                        st.error("cloud_renderer.py not found or FAL_KEY not set.")
                    else:
                        import random
                        _n = int(_ti_n)
                        _base_seed = random.randint(1, 99999)
                        if _cloud_style_mode == "🔀 Random mix":
                            # Sample styles, wrap around if requesting more than available
                            _shuffled = _cloud_styles.copy()
                            random.shuffle(_shuffled)
                            _style_pool = [_shuffled[i % len(_shuffled)] for i in range(_n)]
                        else:
                            _style_pool = [_picked_style] * _n

                        _imgs_out = []
                        _prog = st.progress(0, text=f"Rendering {_n} styles in parallel…")
                        import concurrent.futures
                        _done_count = 0

                        def _render_one_cloud(_ci_sk):
                            _ci, _sk = _ci_sk
                            return (_ci, _sk, _cr.render_cloud(
                                _ti_title.strip(), _sk,
                                seed=_base_seed + _ci * 137
                            ))

                        with concurrent.futures.ThreadPoolExecutor(max_workers=min(_n, 4)) as _ex:
                            _futs = {_ex.submit(_render_one_cloud, (_ci, _sk)): _sk
                                     for _ci, _sk in enumerate(_style_pool)}
                            for _fut in concurrent.futures.as_completed(_futs):
                                _done_count += 1
                                try:
                                    _ci, _sk, _png = _fut.result()
                                    if _png:
                                        _imgs_out.append((_sk, _png))
                                except Exception as _ce:
                                    st.warning(f"{_futs[_fut]}: {_ce}")
                                _prog.progress(_done_count / _n, text=f"Done {_done_count}/{_n}…")
                        _prog.progress(1.0, text=f"Done! {len(_imgs_out)}/{_n} rendered.")

                        st.session_state["ti_imgs"]  = _imgs_out
                        st.session_state["ti_label"] = _ti_title.strip()
                        st.session_state["ti_seed_used"] = 0

            else:
                # Local PIL mode
                col_mode, col_n, col_seed = st.columns([3, 1, 1])
                with col_mode:
                    _ti_mode = st.radio(
                        "Mode",
                        ["🔀 Random mix", "🎯 Auto-match keywords", "🎨 Pick one"],
                        horizontal=True,
                        key="ti_mode",
                        label_visibility="collapsed",
                    )
                with col_n:
                    _ti_n = st.number_input("Variations", min_value=1, max_value=12, value=6, key="ti_n")
                with col_seed:
                    _ti_seed = st.number_input(
                        "Seed", min_value=0, max_value=999999, value=0, key="ti_seed",
                        help="0 = new random seed each time",
                    )

                if _ti_mode == "🎨 Pick one":
                    _all_treatments = sorted(_cta.TREATMENTS.keys())
                    _feat_treatments = sorted(getattr(_cta, "FEATURED_TREATMENTS", _cta.TREATMENTS).keys())
                    _tp1, _tp2 = st.columns([3, 1])
                    with _tp1:
                        _ti_filt = st.text_input("🔍 Filter treatments", placeholder="e.g. gold, neon, chrome…",
                                                  key="ti_filt", label_visibility="collapsed")
                    with _tp2:
                        _feat_only = st.toggle("Featured only", value=True, key="ti_feat_only")
                    _pool_to_show = _feat_treatments if _feat_only else _all_treatments
                    if _ti_filt.strip():
                        _pool_to_show = [t for t in _pool_to_show if _ti_filt.lower() in t.lower()]
                    if _pool_to_show:
                        _ti_treatment = st.selectbox(
                            f"Treatment — {len(_pool_to_show)} shown"
                            + (f" of {len(_feat_treatments)} featured" if _feat_only else f" of {len(_all_treatments)} total"),
                            _pool_to_show, key="ti_treatment",
                        )
                        if _feat_only and not _ti_filt.strip():
                            st.caption(f"{len(_feat_treatments)} featured treatments · toggle off to browse all {len(_all_treatments)}")
                    else:
                        st.caption(f"No treatments match '{_ti_filt}' — try a shorter keyword")
                        _ti_treatment = _all_treatments[0] if _all_treatments else None
                else:
                    _ti_treatment = None

                if st.button("Generate Title PNGs", type="primary", use_container_width=True, key="ti_gen"):
                    if not _ti_title.strip():
                        st.error("Enter a title first.")
                    else:
                        import random, io

                        _seed = _ti_seed if _ti_seed > 0 else random.randint(1, 999999)
                        _n    = int(_ti_n)
                        _feat = list(getattr(_cta, "FEATURED_TREATMENTS", _cta.TREATMENTS).keys())
                        _keys = list(_cta.TREATMENTS.keys())

                        if _ti_mode == "🔀 Random mix":
                            _rng0 = random.Random(_seed)
                            _pool = [_rng0.choice(_feat) for _ in range(_n)]
                        elif _ti_mode == "🎯 Auto-match keywords":
                            _kw = _ti_title.lower()
                            _matched = next(
                                (v for k, v in _cta.KEYWORD_TREATMENT.items() if k in _kw),
                                None,
                            )
                            if _matched and _matched in _cta.TREATMENTS:
                                _pool = [_matched] * _n
                                st.caption(f"Matched keyword to treatment: {_matched}")
                            else:
                                _rng0 = random.Random(_seed)
                                _pool = [_rng0.choice(_keys) for _ in range(_n)]
                                st.caption("No keyword match — using random treatments")
                        else:
                            _pool = [_ti_treatment] * _n

                        _imgs_out = []
                        with st.spinner("Rendering..."):
                            for _i, _treatment in enumerate(_pool):
                                try:
                                    _rng_i = random.Random(_seed + _i * 1000)
                                    _img   = _cta.TREATMENTS[_treatment](_ti_title.strip(), _rng_i)
                                    # Sharpen for crisp output
                                    from PIL import ImageFilter as _IF
                                    _img = _img.filter(_IF.UnsharpMask(radius=1.5, percent=60, threshold=2))
                                    _buf   = io.BytesIO()
                                    _img.save(_buf, format="PNG")
                                    _imgs_out.append((_treatment, _buf.getvalue()))
                                except Exception as _ex:
                                    st.warning(f"Treatment '{_treatment}' failed: {_ex}")

                        st.session_state["ti_imgs"]  = _imgs_out
                        st.session_state["ti_label"] = _ti_title.strip()
                        st.session_state["ti_seed_used"] = _seed

            if st.session_state.get("ti_imgs"):
                _label = st.session_state.get("ti_label", "title")
                st.divider()
                _cols = st.columns(3)
                for _i, (_treatment, _png) in enumerate(st.session_state["ti_imgs"]):
                    with _cols[_i % 3]:
                        # Show on checkerboard so transparency is visible
                        try:
                            from PIL import Image as _PILImg
                            _ti_img = _PILImg.open(io.BytesIO(_png)).convert("RGBA")
                            _tw, _th = _ti_img.size
                            _checker = _checkerboard_bg(_tw, _th).copy()
                            _checker = _PILImg.alpha_composite(_checker, _ti_img)
                            _prev_buf = io.BytesIO()
                            _checker.save(_prev_buf, format="PNG")
                            st.image(_prev_buf.getvalue(), use_container_width=True)
                        except Exception:
                            st.image(_png, use_container_width=True)
                        st.download_button(
                            f"⬇ {_treatment}",
                            data=_png,
                            file_name=f"{_label.replace(' ', '_')}_{_treatment}.png",
                            mime="image/png",
                            key=f"ti_dl_{_i}",
                            use_container_width=True,
                        )
                        _ref_prompt = st.text_input(
                            "Refine",
                            placeholder="e.g. gold, darker, glow…",
                            key=f"ti_ref_{_i}",
                            label_visibility="collapsed",
                        )
                        if st.button("Apply", key=f"ti_apply_{_i}", use_container_width=True):
                            if _ref_prompt.strip():
                                with st.spinner("Applying..."):
                                    _seed_used = st.session_state.get("ti_seed_used", 42)
                                    _new_png, _new_name = _refine_treatment(
                                        _treatment, _png, _ref_prompt.strip(),
                                        st.session_state.get("ti_label", "title"),
                                        _seed_used + _i * 1000
                                    )
                                if _new_png:
                                    _imgs_list = list(st.session_state["ti_imgs"])
                                    _imgs_list[_i] = (_new_name, _new_png)
                                    st.session_state["ti_imgs"] = _imgs_list
                                    st.rerun()
                                else:
                                    st.warning("Could not apply — try simpler keywords.")

        # ── Model Name Generator ─────────────────────────────────────────────────
        st.divider()
        st.markdown('<p class="sh">Model Name Generator</p>', unsafe_allow_html=True)
        _mn_c1, _mn_c2, _mn_c3 = st.columns([2, 4, 2])
        with _mn_c1:
            _mn_studio = st.selectbox("Studio", ["VRA", "VRH"], key="mn_studio")
        with _mn_c2:
            _mn_name = st.text_input("Model name", placeholder="e.g. Emma Rosie", key="mn_name")
        with _mn_c3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            _mn_go = st.button("Generate", type="primary", use_container_width=True, key="mn_gen")

        if _mn_go:
            if not _mn_name.strip():
                st.error("Enter a model name.")
            else:
                with st.spinner("Rendering model name…"):
                    try:
                        _mn_png = _cta.generate_model_name_png(_mn_name.strip(), _mn_studio)
                        st.session_state["mn_png"] = _mn_png
                        st.session_state["mn_label"] = _mn_name.strip()
                        st.session_state["mn_studio_used"] = _mn_studio
                    except Exception as _mn_ex:
                        st.error(f"Render failed: {_mn_ex}")

        if st.session_state.get("mn_png"):
            _mn_label = st.session_state.get("mn_label", "model")
            _mn_studio_u = st.session_state.get("mn_studio_used", "VRH")
            _mn_png_data = st.session_state["mn_png"]
            st.image(_mn_png_data, use_container_width=True)

            _mn_safe = _mn_label.replace(" ", "")
            st.download_button(
                f"Download {_mn_studio_u} — {_mn_label}",
                data=_mn_png_data,
                file_name=f"{_mn_studio_u}-{_mn_safe}.png",
                mime="image/png",
                key="mn_dl",
                use_container_width=True,
            )

    # ── TAB 5: Missing Items ─────────────────────────────────────────────────────
with tab_missing:
    if _has_tab("Missing"):
        st.subheader("⚠️ Missing Items")

        _GRAIL_ID_M = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
        _STUDIO_TABS_M = {"VRH": "VRHush", "FPVR": "FuckPassVR", "VRA": "VRAllure", "NNJOI": "NaughtyJOI"}

        _STUDIO_CONFIG_M = {
            "VRH": {"name": "VRHush", "cta": "Taste {pronoun} on VRHush now."},
            "FPVR": {"name": "FuckPassVR", "cta": "Watch {pronoun} on FuckPassVR now."},
            "VRA": {"name": "VRAllure", "cta": "Watch {pronoun} on VRAllure now."},
            "NNJOI": {"name": "NJOI", "cta": "Watch {pronoun} on NJOI now."},
        }

        def _check_missing():
            """Pull last 5 scenes per studio from Grail + Scripts + MEGA scan."""
            _ck = "_missing_data"
            _tsk = "_missing_data_ts"
            _now = time.time()
            if _ck in st.session_state and _now - st.session_state.get(_tsk, 0) < 600:
                return st.session_state[_ck]
            import gspread as _gs, json as _json
            from google.oauth2.service_account import Credentials as _Creds
            from datetime import date as _date
            _creds = _Creds.from_service_account_file(
                os.path.join(os.path.dirname(__file__), "service_account.json"),
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            _gc = _gs.authorize(_creds)
            _grail = _gc.open_by_key(_GRAIL_ID_M)
            _scripts_sh = _gc.open_by_key("1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ")

            # Build lookup of (studio_lower, female_lower) → {plot, theme, script_title}
            # Build lookup of (studio_lower, female_lower) → {plot, theme, script_title}
            # Check current month + previous month to catch recent shoots
            _plot_lookup = {}
            _studio_map_scripts = {
                "FuckPassVR": "FPVR", "FuckpassVR": "FPVR", "fuckpassvr": "FPVR",
                "VRHush": "VRH", "vrhush": "VRH",
                "VRAllure": "VRA", "vrallure": "VRA",
                "NaughtyJOI": "NJOI", "naughtyjoi": "NJOI",
            }
            try:
                _today = _date.today()
                _months_to_check = [_today.strftime("%B %Y")]
                _prev = _today.replace(day=1) - __import__('datetime').timedelta(days=1)
                _months_to_check.append(_prev.strftime("%B %Y"))

                for _month_name in _months_to_check:
                    try:
                        _scripts_ws = _scripts_sh.worksheet(_month_name)
                        _script_rows = _scripts_ws.get_all_values()
                        for _sr in _script_rows[1:]:
                            _studio_raw = _sr[1].strip() if len(_sr) > 1 else ""
                            _fem = _sr[4].strip() if len(_sr) > 4 else ""
                            _theme = _sr[6].strip() if len(_sr) > 6 else ""
                            _plot = _sr[9].strip() if len(_sr) > 9 else ""
                            _stitle = _sr[10].strip() if len(_sr) > 10 else ""
                            if _fem:
                                _scode = _studio_map_scripts.get(_studio_raw, _studio_raw.upper())
                                _key = f"{_scode}|{_fem.lower()}"
                                _data = {"plot": _plot, "theme": _theme, "script_title": _stitle}
                                if _plot:
                                    _plot_lookup[_key] = _data
                                _plot_lookup[_fem.lower()] = _data
                    except Exception:
                        pass
            except Exception:
                pass

            # Load MEGA scan for asset checks
            _mega_lookup = {}
            _scan_date = ""
            try:
                _scan_path = os.path.join(os.path.dirname(__file__), "mega_scan.json")
                if os.path.exists(_scan_path):
                    with open(_scan_path) as _f:
                        _scan = _json.load(_f)
                    _scan_date = _scan.get("scanned_at", "")[:10]
                    for _s in _scan.get("scenes", []):
                        _sid = _s.get("scene_id", _s.get("id", ""))
                        _mega_lookup[_sid] = _s
            except Exception:
                pass

            results = {"_plot_lookup": _plot_lookup, "_scan_date": _scan_date}
            for _tab, _studio_name in _STUDIO_TABS_M.items():
                try:
                    _ws = _grail.worksheet(_tab)
                    _all = _ws.get_all_values()
                    _data_rows = [(i, r) for i, r in enumerate(_all[1:], start=2)
                                  if len(r) > 1 and r[1].strip()]
                    _last5 = _data_rows[-5:]

                    scenes = []
                    for _row_num, _r in _last5:
                        _site_code = _r[0].strip().upper() if _r[0] else _tab
                        _scene_num = _r[1].strip() if len(_r) > 1 else ""
                        _sid = f"{_site_code}{_scene_num}"
                        _release_date = _r[2].strip() if len(_r) > 2 else ""
                        _title = _r[3].strip() if len(_r) > 3 else ""
                        _performers = _r[4].strip() if len(_r) > 4 else ""
                        _cats = _r[5].strip() if len(_r) > 5 else ""
                        _tags = _r[6].strip() if len(_r) > 6 else ""
                        _female = _performers.split(",")[0].strip() if _performers else ""

                        # Check Scripts sheet — try studio+female first, then female only
                        _script_data = _plot_lookup.get(f"{_tab}|{_female.lower()}",
                                       _plot_lookup.get(_female.lower(), {}))
                        _has_plot = bool(_script_data.get("plot"))

                        # Check MEGA scan for assets
                        _mega_entry = None
                        for _try_id in [_sid, _sid.lower(), f"{_tab}{_scene_num}", f"{_tab.lower()}{_scene_num}"]:
                            if _try_id in _mega_lookup:
                                _mega_entry = _mega_lookup[_try_id]
                                break
                        if _mega_entry is None and _scene_num:
                            _padded = _scene_num.zfill(4)
                            for _try_id in [f"{_site_code}{_padded}", f"{_tab}{_padded}",
                                            f"{_site_code.lower()}{_padded}", f"{_tab.lower()}{_padded}"]:
                                if _try_id in _mega_lookup:
                                    _mega_entry = _mega_lookup[_try_id]
                                    break
                        _has_desc = _mega_entry.get("has_description", False) if _mega_entry else None
                        _has_videos = _mega_entry.get("has_videos") if _mega_entry else None
                        _has_thumbnail = _mega_entry.get("has_thumbnail") if _mega_entry else None
                        _has_photos = _mega_entry.get("has_photos") if _mega_entry else None
                        _has_storyboard = _mega_entry.get("has_storyboard") if _mega_entry else None
                        _video_count = _mega_entry.get("video_count", 0) if _mega_entry else 0
                        _storyboard_count = _mega_entry.get("storyboard_count", 0) if _mega_entry else 0

                        missing = []
                        if not _title:
                            missing.append("title")
                        if not _cats:
                            missing.append("categories")
                        if not _tags:
                            missing.append("tags")
                        if _mega_entry is None or _mega_entry.get("no_folder"):
                            # No MEGA folder found at all
                            missing.append("folder")
                        else:
                            if not _has_desc:
                                missing.append("description")
                            if not _has_videos:
                                missing.append("videos")
                            if not _has_thumbnail:
                                missing.append("thumbnail")
                            if not _has_photos:
                                missing.append("photos")
                            if not _has_storyboard:
                                missing.append("storyboard")

                        scenes.append({
                            "row": _row_num, "sid": _sid, "scene_num": _scene_num,
                            "female": _female, "performers": _performers,
                            "title": _title, "cats": _cats, "tags": _tags,
                            "release_date": _release_date,
                            "has_plot": _has_plot, "has_desc": _has_desc,
                            "has_videos": _has_videos, "has_thumbnail": _has_thumbnail,
                            "has_photos": _has_photos, "has_storyboard": _has_storyboard,
                            "video_count": _video_count, "storyboard_count": _storyboard_count,
                            "theme": _script_data.get("theme", ""),
                            "plot": _script_data.get("plot", ""),
                            "missing": missing, "tab": _tab,
                        })
                    results[_tab] = {"studio": _studio_name, "scenes": scenes}
                except Exception as _e:
                    results[_tab] = {"studio": _studio_name, "scenes": [], "error": str(_e)}
            st.session_state[_ck] = results
            st.session_state[_tsk] = _now
            return results

        # Auto-populate, cached by Streamlit
        try:
            _mdata = _check_missing()
        except Exception as _scan_err:
            st.error(f"Could not scan: {_scan_err}")
            _mdata = {}
        _scan_dt = _mdata.get("_scan_date", "")

        _mr1, _mr2, _mr3 = st.columns([4, 1, 1])
        with _mr1:
            if _scan_dt:
                st.caption(f"_MEGA last scanned: {_scan_dt}_")
            else:
                st.caption("_No MEGA scan data — click Refresh MEGA to scan_")
        with _mr2:
            if st.button("🔄 Rescan Grail", key="missing_rescan", use_container_width=True,
                          help="Re-reads Grail + Scripts sheets for title/plot status"):
                st.session_state.pop("_missing_data", None); st.session_state.pop("_missing_data_ts", None)
                st.rerun()
        with _mr3:
            _mega_refresh = st.button("📡 Refresh MEGA", key="missing_mega_refresh", use_container_width=True,
                                       help="Scans MEGA folders for assets (Description, Videos, Photos, etc.)")

        if _mega_refresh:
            import subprocess as _sp_mr

            # Collect all scene IDs shown in the Missing tab
            _all_sids = []
            for _tk, _info in _mdata.items():
                if _tk.startswith("_"):
                    continue
                for _sc in _info.get("scenes", []):
                    _padded = re.sub(r'([A-Za-z]+)(\d+)', lambda m: m.group(1).upper() + m.group(2).zfill(4), _sc["sid"])
                    _all_sids.append({"studio": _tk, "scene_id": _padded})

            # Write request file for the worker
            import json as _json_mr
            _req_path = os.path.join(os.path.dirname(__file__), "mega_scan_request.json")
            with open(_req_path, "w") as _f_req:
                _json_mr.dump({"scenes": _all_sids}, _f_req)

            # Trigger pre-registered "MEGAScan" scheduled task (runs as andre user)
            with st.spinner(f"Scanning {len(_all_sids)} scenes on MEGA…"):
                try:
                    _sp_mr.run(["schtasks", "/run", "/tn", "MEGAScan"],
                               capture_output=True, text=True, timeout=10)

                    # Poll for completion (request file disappears when worker finishes)
                    _waited = 0
                    while os.path.exists(_req_path) and _waited < 30:
                        time.sleep(1)
                        _waited += 1

                    if not os.path.exists(_req_path):
                        _scan_path_mr = os.path.join(os.path.dirname(__file__), "mega_scan.json")
                        with open(_scan_path_mr) as _f_scan:
                            _updated = _json_mr.load(_f_scan)
                        st.success(f"✅ MEGA scan updated — {len(_updated.get('scenes', []))} scenes as of {_updated.get('scanned_at', '')[:19]}")
                    else:
                        st.warning("Scan still running — click Rescan Grail in a few seconds to see results")
                except Exception as _te:
                    st.error(f"Could not run MEGA scan: {_te}")

                st.session_state.pop("_missing_data", None)
                st.session_state.pop("_missing_data_ts", None)
                st.rerun()

        # ── Handle pending generation triggers (from previous rerun) ─────────────
        _gen_title_trigger = st.session_state.pop("_gen_title_trigger", None)
        if _gen_title_trigger:
            _gt_sid = _gen_title_trigger["sid"]
            _gt_studio = _gen_title_trigger["studio"]
            _gt_female = _gen_title_trigger["female"]
            _gt_theme = _gen_title_trigger.get("theme", "")
            _gt_plot = _gen_title_trigger.get("plot", "")
            with st.spinner(f"Generating title for {_gt_sid}…"):
                _gen = _generate_title(_gt_studio, _gt_female, _gt_theme, _gt_plot)
            if _gen:
                st.session_state[f"tin_{_gt_sid}"] = _gen
            else:
                st.session_state[f"tin_{_gt_sid}"] = "⚠️ Generation failed"
            st.session_state["_expand_sid"] = _gt_sid

        _gen_desc_trigger = st.session_state.pop("_gen_desc_trigger", None)
        if _gen_desc_trigger:
            _gd_sid = _gen_desc_trigger["sid"]
            _gd_tab = _gen_desc_trigger["tab"]
            _gd_data = _gen_desc_trigger
            _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if _claude_key:
                _desc_key_t = "NJOI" if _gd_tab == "NNJOI" else _gd_tab
                # Use compilation prompt if title indicates a compilation
                _gd_title = _gd_data.get("title", "")
                if _is_compilation(_gd_title):
                    _desc_sys = _DESC_SYSTEMS_COMPILATION.get(_desc_key_t, _DESC_SYSTEMS_FULL.get(_desc_key_t, ""))
                else:
                    _desc_sys = _DESC_SYSTEMS_FULL.get(_desc_key_t, _DESC_SYSTEMS_FULL.get("VRH", ""))
                _d_cfg = _DESC_STUDIO_CONFIG.get(_desc_key_t, _DESC_STUDIO_CONFIG.get("VRH", {}))
                _d_prompt = _build_scene_prompt(
                    _desc_key_t, _d_cfg,
                    title=_gd_data.get("title", "Untitled"),
                    female=_gd_data.get("female", ""),
                    male=_gd_data.get("male", ""),
                    plot=_gd_data.get("plot", "N/A"),
                    categories=_gd_data.get("cats", ""),
                    model_props="", sex_positions="", target_keywords="",
                    resolution="8K", wardrobe="",
                )
                with st.spinner(f"Generating description for {_gd_sid}…"):
                    try:
                        import anthropic as _anth_t
                        _bac = _anth_t.Anthropic(api_key=_claude_key)
                        _bm = _bac.messages.create(
                            model="claude-sonnet-4-6", max_tokens=1200,
                            system=_desc_sys,
                            messages=[{"role": "user", "content": _d_prompt}])
                        st.session_state[f"mdesc_{_gd_sid}"] = _bm.content[0].text.strip()
                    except Exception as _de:
                        st.session_state[f"mdesc_{_gd_sid}"] = f"⚠️ Failed: {_de}"
                st.session_state["_expand_sid"] = _gd_sid

        _total_missing = 0
        _total_scenes = 0

        # Parse release dates for sorting (soonest first = highest priority)
        from datetime import datetime as _dt_sort
        def _parse_release(d):
            if not d:
                return _dt_sort(2099, 1, 1)
            for _fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
                try:
                    return _dt_sort.strptime(d.strip(), _fmt)
                except ValueError:
                    continue
            return _dt_sort(2099, 1, 1)

        def _rel_short(d):
            if not d:
                return ""
            for _fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
                try:
                    _o = _dt_sort.strptime(d.strip(), _fmt)
                    return _o.strftime("%b ") + str(_o.day)
                except ValueError:
                    continue
            return d

        def _asset_row(has_desc, has_videos, video_count, has_thumb, has_photos, has_storyboard, storyboard_count):
            """Single emoji status line for all MEGA assets."""
            def _icon(val, count=None):
                if val is True:
                    return ("✅" + (f" ×{count}" if count else ""))
                elif val is False:
                    return "❌"
                return "—"
            parts = [
                f"Desc {_icon(has_desc)}",
                f"Videos {_icon(has_videos, video_count)}",
                f"Thumb {_icon(has_thumb)}",
                f"Photos {_icon(has_photos)}",
                f"Storyboard {_icon(has_storyboard, storyboard_count)}",
            ]
            return "  ·  ".join(parts)

        def _build_docx_common(talent_ln, title_val, tags, cats, desc_text, studio="FPVR"):
            try:
                return _build_docx(talent_ln, title_val, tags, cats, desc_text, studio=studio)
            except Exception:
                return None

        def _render_desc_section(_sid, _sid_pad, _sc, _tab_key, _is_missing):
            """Shared description UI for both missing and complete scenes."""
            _btn_label = "✨ Generate Description" if _is_missing else "✨ Regenerate"
            _btn_type  = "primary" if _is_missing else "secondary"
            _desc_key  = f"mdesc_{_sid}"

            def _on_gen(_sid=_sid, _tab_key=_tab_key, _sc=_sc):
                st.session_state["_gen_desc_trigger"] = {
                    "sid": _sid, "tab": _tab_key,
                    "title": _sc['title'] or 'Untitled',
                    "female": _sc['female'],
                    "male": _sc['performers'].split(",", 1)[1].strip() if "," in _sc['performers'] else "",
                    "plot": _sc.get('plot', 'N/A'),
                    "cats": _sc['cats'],
                }
                st.session_state["_expand_sid"] = _sid
            st.button(_btn_label, key=f"gen_d_{_sid}", use_container_width=True,
                      type=_btn_type, on_click=_on_gen)

            if _desc_key in st.session_state:
                _desc_text = st.text_area("desc", value=st.session_state[_desc_key],
                                          key=f"dta_{_sid}", height=260, label_visibility="collapsed")
                _female_names = [n.strip() for n in _sc['female'].split(",") if n.strip()]
                _male_names_d = [n.strip() for n in (_sc['performers'].split(",")[1:]) if n.strip()] if "," in _sc['performers'] else []
                _talent_ln = ", ".join(_female_names + _male_names_d)
                _f_slug = _female_names[0].replace(" ", "") if _female_names else "Unknown"
                _m_slug = ("-" + _male_names_d[0].replace(" ", "")) if _male_names_d else ""
                _fn_base = f"{_sid_pad}-{_f_slug}{_m_slug}"
                _title_for_doc = _sc.get('title') or st.session_state.get(f"tin_{_sid}", "") or "Untitled"
                _m_studio = _tab_key if _tab_key != "NNJOI" else "NJOI"
                _docx_data = _build_docx_common(_talent_ln, _title_for_doc, _sc.get('tags',''), _sc.get('cats',''), _desc_text, studio=_m_studio)

                # Build .txt with HTML-linked categories and tags
                _txt_parts_m = [_talent_ln, f"Title: {_title_for_doc}",
                                f"Tags: {_tags_as_html(_m_studio, _sc.get('tags',''))}",
                                f"Categories: {_cats_as_html(_m_studio, _sc.get('cats',''))}",
                                "", _desc_text]
                _full_txt_m = "\n".join(_txt_parts_m)

                _dd1, _dd2, _dd3 = st.columns(3)
                with _dd1:
                    st.download_button("⬇ .txt", data=_full_txt_m, file_name=f"{_fn_base}.txt",
                                       mime="text/plain", key=f"dl_d_{_sid}", use_container_width=True)
                with _dd2:
                    if _docx_data:
                        st.download_button("⬇ .docx", data=_docx_data, file_name=f"{_fn_base}.docx",
                                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           key=f"dl_dx_{_sid}", use_container_width=True)
                with _dd3:
                    # MEGA description save disabled — descriptions managed manually
                    st.caption("_Save to MEGA disabled_")

        # ── Global summary strip ──────────────────────────────────────────────────
        _all_scenes_flat = [s for k, v in _mdata.items() if not k.startswith("_")
                            for s in v.get("scenes", [])]
        _total_scenes = len(_all_scenes_flat)
        _type_counts = {}
        for _s in _all_scenes_flat:
            for _m in _s.get("missing", []):
                _type_counts[_m] = _type_counts.get(_m, 0) + 1
        _total_missing = sum(1 for s in _all_scenes_flat if s["missing"])

        if _type_counts:
            _sm_cols = st.columns(len(_type_counts) + 1)
            _sm_cols[0].metric("Total Missing", _total_missing)
            for _i, (_k, _v) in enumerate(sorted(_type_counts.items())):
                _sm_cols[_i + 1].metric(_k.title(), _v)
        else:
            st.success(f"✅ All {_total_scenes} recent scenes complete across all studios")
        st.divider()

        for _tab_key, _info in _mdata.items():
            if _tab_key.startswith("_"):
                continue
            _studio_nm = _info["studio"]
            _scenes = _info.get("scenes", [])

            if _info.get("error"):
                st.error(f"**{_studio_nm}**: {_info['error']}")
                continue

            # Sort scenes by release date (soonest first)
            _scenes_sorted = sorted(_scenes, key=lambda s: _parse_release(s.get("release_date", "")))
            _missing_count = sum(1 for s in _scenes_sorted if s["missing"])

            # Studio section header
            _sh1, _sh2 = st.columns([5, 1])
            with _sh1:
                if _missing_count == 0:
                    st.markdown(f"#### ✅ {_studio_nm}")
                else:
                    _breakdown = "  ·  ".join(f"**{v}** {k}" for k, v in sorted(
                        {_m: sum(1 for s in _scenes_sorted if _m in s["missing"])
                         for _m in set(m for s in _scenes_sorted for m in s["missing"])}.items()))
                    st.markdown(f"#### 🔴 {_studio_nm} — {_missing_count}/{len(_scenes_sorted)} scenes — {_breakdown}")
            with _sh2:
                pass

            for _sc in _scenes_sorted:
                _sid = _sc["sid"]
                _fem = _sc["female"]
                _miss = _sc["missing"]
                _rel = _sc.get("release_date", "")
                _sid_pad = re.sub(r'([A-Za-z]+)(\d+)', lambda m: m.group(1) + m.group(2).zfill(4), _sid)
                _is_comp = bool(re.search(r'\bVol\.?\s*\d|\bVolume\b|\bBest\s+Of\b|\bCompilation\b', _sc.get('title', '') or '', re.I))
                _comp_tag = " · COMP" if _is_comp else ""
                _expand_this = st.session_state.get("_expand_sid") == _sid
                _rshort = _rel_short(_rel)
                _date_str = (f" · {_rshort}" if _rshort else "")

                if _miss:
                    _miss_str = ", ".join(_miss)
                    _exp_label = f"🔴 {_sid_pad}{_comp_tag} · {_fem}{_date_str} — {_miss_str}"
                    with st.expander(_exp_label, expanded=_expand_this):
                        # ── Performers + date ───────────────────────────────────
                        _pi1, _pi2 = st.columns([4, 1])
                        with _pi1:
                            st.markdown(f"**{_sc['performers']}**")
                        with _pi2:
                            if _rel:
                                st.caption(_rel)

                        # ── MEGA asset grid ─────────────────────────────────────
                        st.caption(_asset_row(_sc.get('has_desc'), _sc.get('has_videos'), _sc.get('video_count'), _sc.get('has_thumbnail'), _sc.get('has_photos'), _sc.get('has_storyboard'), _sc.get('storyboard_count')))

                        # ── Create MEGA folder if none exists ──────────────────
                        if "folder" in _miss:
                            _cf1, _cf2 = st.columns([1, 3])
                            with _cf1:
                                def _on_create_folder(_sid=_sid, _tab_key=_tab_key):
                                    st.session_state[f"_create_mega_{_sid}"] = True
                                    st.session_state["_expand_sid"] = _sid
                                st.button("📁 Create MEGA Folder", key=f"mk_mega_{_sid}",
                                          type="secondary", use_container_width=True,
                                          on_click=_on_create_folder)
                            with _cf2:
                                st.caption(f"Creates {_sid_pad}/ with Description, Legal, Photos, Storyboard, Video Thumbnail, Videos")
                            if st.session_state.pop(f"_create_mega_{_sid}", False):
                                _stu_map_create = {"VRH": "VRH", "FPVR": "FPVR", "VRA": "VRA", "NNJOI": "NJOI"}
                                _create_studio = _stu_map_create.get(_tab_key, _tab_key)
                                with st.spinner(f"Creating {_sid_pad} on MEGA…"):
                                    try:
                                        import comp_tools as _ct_mk
                                        _mk_path = _ct_mk.create_mega_folder(_sid_pad)
                                        st.success(f"✅ Created `{_mk_path}`")
                                        # Invalidate missing cache so next rescan picks it up
                                        st.session_state.pop("_missing_data", None)
                                        st.session_state.pop("_missing_data_ts", None)
                                    except Exception as _mke:
                                        st.error(f"Failed to create folder: {_mke}")

                        # ── Grail status ────────────────────────────────────────
                        _gp = []
                        _title_val = _sc.get('title', '')
                        _gp.append(f"{'✅' if _title_val else '❌'} Title" + (f": *{_title_val}*" if _title_val else ""))
                        _gp.append(f"{'✅' if _sc['cats'] else '❌'} Cats")
                        _gp.append(f"{'✅' if _sc['tags'] else '❌'} Tags")
                        st.caption("  ·  ".join(_gp))

                        # ── Actions ─────────────────────────────────────────────
                        if "title" in _miss:
                            st.divider()
                            st.markdown("**🏷️ Title**")
                            _tc1, _tc2, _tc3 = st.columns([2, 4, 1])
                            with _tc1:
                                def _on_gen_title(_sid=_sid, _studio=_studio_nm, _fem=_fem, _theme=_sc.get("theme",""), _plot=_sc.get("plot","")):
                                    st.session_state["_gen_title_trigger"] = {"sid": _sid, "studio": _studio, "female": _fem, "theme": _theme, "plot": _plot}
                                    st.session_state["_expand_sid"] = _sid
                                st.button("✨ Generate", key=f"gen_t_{_sid}", use_container_width=True, type="primary", on_click=_on_gen_title)
                            with _tc2:
                                _tv = st.text_input("t", key=f"tin_{_sid}", label_visibility="collapsed", placeholder="Generated title appears here…")
                            with _tc3:
                                if _tv and st.button("💾", key=f"sv_t_{_sid}", use_container_width=True):
                                    _ok, _msg = _write_title_to_grail(_studio_nm, _sc["scene_num"], _tv)
                                    if _ok:
                                        st.success(_msg)
                                        st.session_state.pop("_missing_data", None); st.session_state.pop("_missing_data_ts", None)
                                        st.rerun()
                                    else:
                                        st.error(_msg)

                        if "description" in _miss:
                            st.divider()
                            st.markdown("**📝 Description**")
                            _render_desc_section(_sid, _sid_pad, _sc, _tab_key, _is_missing=True)

                else:
                    # ── Complete scenes — collapsed, show update options when opened ──
                    _exp_label = f"✅ {_sid_pad}{_comp_tag} · {_fem}{_date_str}"
                    with st.expander(_exp_label, expanded=_expand_this):
                        _pi1, _pi2 = st.columns([4, 1])
                        with _pi1:
                            st.markdown(f"**{_sc['performers']}**")
                        with _pi2:
                            if _rel:
                                st.caption(_rel)

                        st.caption(_asset_row(_sc.get('has_desc'), _sc.get('has_videos'), _sc.get('video_count'), _sc.get('has_thumbnail'), _sc.get('has_photos'), _sc.get('has_storyboard'), _sc.get('storyboard_count')))

                        _gp = []
                        _title_val = _sc.get('title', '')
                        _gp.append(f"{'✅' if _title_val else '❌'} Title" + (f": *{_title_val}*" if _title_val else ""))
                        _gp.append(f"{'✅' if _sc['cats'] else '❌'} Cats")
                        _gp.append(f"{'✅' if _sc['tags'] else '❌'} Tags")
                        st.caption("  ·  ".join(_gp))

                        # ── Title update ──────────────────────────────────────────
                        st.divider()
                        st.markdown("**🏷️ Title**")
                        _tc1, _tc2, _tc3 = st.columns([2, 4, 1])
                        with _tc1:
                            def _on_gen_title_c(_sid=_sid, _studio=_studio_nm, _fem=_fem, _theme=_sc.get("theme",""), _plot=_sc.get("plot","")):
                                st.session_state["_gen_title_trigger"] = {"sid": _sid, "studio": _studio, "female": _fem, "theme": _theme, "plot": _plot}
                                st.session_state["_expand_sid"] = _sid
                            st.button("✨ Generate", key=f"gen_t_{_sid}", use_container_width=True, type="primary", on_click=_on_gen_title_c)
                        with _tc2:
                            if f"tin_{_sid}" not in st.session_state and _sc.get("title"):
                                st.session_state[f"tin_{_sid}"] = _sc["title"]
                            _tv = st.text_input("t", key=f"tin_{_sid}", label_visibility="collapsed", placeholder="Title…")
                        with _tc3:
                            if _tv and st.button("💾", key=f"sv_t_{_sid}", use_container_width=True):
                                _ok, _msg = _write_title_to_grail(_studio_nm, _sc["scene_num"], _tv)
                                if _ok:
                                    st.success(_msg)
                                    st.session_state.pop("_missing_data", None); st.session_state.pop("_missing_data_ts", None)
                                    st.rerun()
                                else:
                                    st.error(_msg)

                        # ── Description update ────────────────────────────────────
                        st.markdown("**📝 Description**")
                        _render_desc_section(_sid, _sid_pad, _sc, _tab_key, _is_missing=False)

            st.divider()


    # ── TAB 6: Model Research ─────────────────────────────────────────────────────
with tab_research:
    if _has_tab("Model Research"):
        try:
            from model_research_tab import lookup_model_profile
            _HAS_RESEARCH = True
        except ImportError as _re_err:
            _HAS_RESEARCH = False
            st.error(f"model_research_tab.py not found. ({_re_err})")

        if _HAS_RESEARCH:
            from model_research_tab import fetch_trending_models, fetch_photo_bytes, fetch_performer_photo_url
            try:
                from booking_history import get_booking_history, compute_opportunity_score, get_competitor_scenes
                _HAS_BK_HIST = True
            except ImportError:
                _HAS_BK_HIST = False

            # ── Load trending (disk-cached 6h) ────────────────────────────────────
            if "mr_trending" not in st.session_state:
                with st.spinner("Loading trending models…"):
                    st.session_state["mr_trending"] = fetch_trending_models(10)
            _trending = st.session_state.get("mr_trending", [])

            # ── Fetch portrait headshots for trending models (separate from listing thumbnails)
            if "mr_trending_photos_v1" not in st.session_state and _trending:
                with st.spinner("Loading trending headshots…"):
                    import concurrent.futures as _cf
                    _tnames = [_tm["name"] for _tm in _trending]
                    with _cf.ThreadPoolExecutor(max_workers=5) as _ex:
                        _tfuts = {n: _ex.submit(fetch_performer_photo_url, n) for n in _tnames}
                        _tphotos = {}
                        for n, fut in _tfuts.items():
                            try:
                                _tphotos[n] = fut.result(timeout=10)
                            except Exception:
                                _tphotos[n] = None
                st.session_state["mr_trending_photos_v1"] = _tphotos
            _trending_photos = st.session_state.get("mr_trending_photos_v1", {})

            # ── Priority Outreach list ─────────────────────────────────────────────
            _PRIORITY = [
                {"name": "Leah Gotti",       "agency": "Invision Models",   "mo": None},
                {"name": "Alex Blake",        "agency": "Hussie Models",     "mo": None},
                {"name": "Melissa Stratton",  "agency": "Hussie Models",     "mo": None},
                {"name": "Kenzie Reeves",     "agency": "East Coast Talent", "mo": None},
                {"name": "Kali Roses",        "agency": "The Model Service", "mo": None},
                {"name": "Haley Reed",        "agency": "ATMLA",             "mo": None},
                {"name": "Karma RX",          "agency": "ATMLA",             "mo": None},
                {"name": "Cory Chase",        "agency": "ATMLA",             "mo": None},
                {"name": "Valentina Nappi",   "agency": "Speigler",          "mo": None},
                {"name": "Karlee Grey",       "agency": "ATMLA",             "mo": 104},
            ]

            # Pre-fetch priority photos server-side once per session (v3: VRPorn/SLR, no Babepedia)
            if "mr_priority_photos_v3" not in st.session_state:
                with st.spinner("Loading priority photos…"):
                    import concurrent.futures as _cf
                    with _cf.ThreadPoolExecutor(max_workers=5) as _ex:
                        _futs = {_pm["name"]: _ex.submit(fetch_performer_photo_url, _pm["name"]) for _pm in _PRIORITY}
                        _pp = {}
                        for name, fut in _futs.items():
                            try:
                                _pp[name] = fut.result(timeout=10)
                            except Exception:
                                _pp[name] = None
                st.session_state["mr_priority_photos_v3"] = _pp
            _priority_photos = st.session_state["mr_priority_photos_v3"]

            # Handle card click BEFORE widget renders (can't set widget key after instantiation)
            _mr_auto_name = None
            if "mr_priority_load" in st.session_state:
                _mr_auto_name = st.session_state.pop("mr_priority_load")
                st.session_state["mr_name"] = _mr_auto_name  # set before widget renders

            # ── Search bar — compact two-column ───────────────────────────────────
            _col_search, _col_btn = st.columns([7, 1])
            with _col_search:
                _mr_name = st.text_input(
                    "Performer name",
                    placeholder="Search any performer…",
                    key="mr_name",
                    label_visibility="collapsed",
                )
            with _col_btn:
                _mr_search = st.button("Search", type="primary", use_container_width=True, key="mr_search")
            _mr_refresh = False  # exposed inside profile via refresh button

            _should_search = (_mr_search and _mr_name.strip()) or bool(_mr_auto_name)
            _search_name   = (_mr_auto_name or _mr_name.strip()) if _mr_auto_name else _mr_name.strip()

            if _should_search and _search_name:
                st.session_state["mr_profile"] = None
                st.session_state["mr_query"]   = _search_name
                with st.spinner(f"Fetching data for {_search_name}…"):
                    _profile = lookup_model_profile(_search_name, force_refresh=False)
                st.session_state["mr_profile"] = _profile

            _profile = st.session_state.get("mr_profile")

            # ── Helper: render one model card ──────────────────────────────────────
            import base64 as _b64

            def _model_card(col, name, photo_src, stat_line, btn_key, score=None):
                """Card: photo fills the card, name+stat as gradient overlay, minimal View button."""
                _img_style = ("width:100%;height:195px;object-fit:cover;"
                              "object-position:50% 15%;display:block;border-radius:8px 8px 0 0")
                if isinstance(photo_src, bytes) and photo_src:
                    _b64_str = _b64.b64encode(photo_src).decode()
                    _media = f"<img src='data:image/jpeg;base64,{_b64_str}' style='{_img_style}'>"
                elif isinstance(photo_src, str) and photo_src:
                    _media = f"<img src='{photo_src}' style='{_img_style}'>"
                else:
                    _initials = "".join(w[0].upper() for w in name.split()[:2])
                    _media = (
                        f"<div style='height:195px;background:#161d2e;display:flex;"
                        f"align-items:center;justify-content:center;font-size:1.8rem;"
                        f"font-weight:700;color:#2e4060;border-radius:8px 8px 0 0'>{_initials}</div>"
                    )
                if score is not None:
                    _sc_bg = "#22c55e" if score >= 70 else ("#f59e0b" if score >= 50 else "#6b7280")
                    _score_overlay = (
                        f"<div style='position:absolute;top:6px;right:6px;background:{_sc_bg};"
                        f"border-radius:12px;padding:2px 7px;font-size:0.65rem;font-weight:700;"
                        f"color:#fff'>{score}</div>"
                    )
                else:
                    _score_overlay = ""
                with col:
                    st.markdown(
                        f"<div style='border-radius:8px;overflow:hidden;background:#0f1520;"
                        f"margin-bottom:3px'>"
                        f"<div style='position:relative'>"
                        f"{_media}{_score_overlay}"
                        f"<div style='position:absolute;bottom:0;left:0;right:0;"
                        f"background:linear-gradient(transparent,rgba(0,0,0,0.82));padding:24px 8px 7px'>"
                        f"<div style='font-size:0.8rem;font-weight:700;color:#f3f4f6;"
                        f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{name}</div>"
                        f"<div style='font-size:0.72rem;color:#d1d5db;margin-top:1px;"
                        f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{stat_line}</div>"
                        f"</div></div></div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("View", key=btn_key, use_container_width=True):
                        st.session_state["mr_priority_load"] = name
                        st.rerun()

            # ── If profile loaded: show profile. Otherwise: show card grid. ────────
            if _profile:
                _back_c, _ref_c = st.columns([8, 1])
                with _back_c:
                    if st.button("← Back to list", key="mr_back"):
                        st.session_state.pop("mr_profile", None)
                        st.session_state.pop("mr_query", None)
                        st.rerun()
                with _ref_c:
                    if st.button("🔄 Refresh", key="mr_force_refresh", use_container_width=True, help="Force re-fetch all data"):
                        with st.spinner("Refreshing…"):
                            _refreshed = lookup_model_profile(_profile.get("name",""), force_refresh=True)
                        st.session_state["mr_profile"] = _refreshed
                        st.rerun()
            else:
                # ── Section header row: label + refresh icon ────────────────────
                _sh1, _sh2 = st.columns([11, 1])
                with _sh1:
                    st.markdown(
                        "<span style='font-size:0.7rem;font-weight:700;letter-spacing:.08em;"
                        "color:#f59e0b;text-transform:uppercase'>🔥 Trending Now</span>",
                        unsafe_allow_html=True)
                with _sh2:
                    if st.button("↺", key="mr_refresh_trending", help="Refresh both sections"):
                        st.session_state.pop("mr_trending", None)
                        st.session_state.pop("mr_trending_photos_v1", None)
                        st.session_state.pop("mr_priority_photos_v3", None)
                        try:
                            import pathlib
                            pathlib.Path(
                                os.path.join(os.path.dirname(__file__), "research_cache_v2", "_trending_models.json")
                            ).unlink(missing_ok=True)
                        except Exception:
                            pass
                        st.rerun()

                # ── Trending grid ─────────────────────────────────────────────
                if _trending:
                    for _trow in [_trending[:5], _trending[5:10]]:
                        if not _trow:
                            continue
                        _tcols = st.columns(5, gap="small")
                        for _ti, _tm in enumerate(_trow):
                            if _ti >= 5:
                                break
                            _tname  = _tm["name"]
                            _tphoto = _trending_photos.get(_tname) or _tm.get("photo_url") or None
                            _tplat  = _tm.get("platform", "")
                            _tsc    = _tm.get("scenes", "")
                            _tfol   = _tm.get("followers", "")
                            _parts  = [p for p in [_tplat, (_tsc + " scenes") if _tsc else "", _tfol] if p]
                            _stat_line = " · ".join(_parts)
                            _model_card(_tcols[_ti], _tname, _tphoto, _stat_line,
                                        f"tr_{_tname.replace(' ', '_')}")
                else:
                    st.caption("Could not load trending models — check connection or click ↺.")

                # ── Priority header ───────────────────────────────────────────
                st.markdown(
                    "<div style='margin-top:18px'>"
                    "<span style='font-size:0.7rem;font-weight:700;letter-spacing:.08em;"
                    "color:#22c55e;text-transform:uppercase'>⭐ Priority Outreach</span>"
                    "</div>",
                    unsafe_allow_html=True)

                # ── Priority grid ─────────────────────────────────────────────
                for _prow in [_PRIORITY[:5], _PRIORITY[5:]]:
                    _pcols = st.columns(5, gap="small")
                    for _pi, _pm in enumerate(_prow):
                        _pname = _pm["name"]
                        _pbytes = _priority_photos.get(_pname)
                        _mo     = _pm["mo"]
                        _mo_str = "Never booked" if _mo is None else (f"{_mo} mo ago")
                        _stat_line = f"{_pm['agency']} · {_mo_str}"
                        _pscore = compute_opportunity_score(_pname, {}) if _HAS_BK_HIST else None
                        _model_card(_pcols[_pi], _pname, _pbytes, _stat_line,
                                    f"pr_{_pname.replace(' ', '_')}", score=_pscore)

            if _profile:
                _bio     = _profile.get("bio", {})
                _about   = _profile.get("about", "")
                _booking = _profile.get("booking", {})
                _slr     = _profile.get("slr", [])
                _vrp     = _profile.get("vrp", [])
                _ddg     = _profile.get("ddg_bio", "")
                _photo   = _profile.get("photo_url", "")
                _name    = _profile.get("name", "")

                _bk_agency = _booking.get("agency", "") if _booking else ""
                _bk_data   = _booking.get("data", {}) if _booking else {}
                _rank_raw  = _bk_data.get("rank", "").strip()
                _RANK_BADGE = {
                    "great":    ("🟢", "Great",    "#1a4a1a"),
                    "good":     ("🔵", "Good",     "#0d2d4a"),
                    "moderate": ("🟡", "Moderate", "#4a3d00"),
                    "poor":     ("🔴", "Poor",     "#4a0d0d"),
                }
                _rank_info = _RANK_BADGE.get(_rank_raw.lower())

                # ── Calculate age from birthday ───────────────────────────────────
                def _calc_age(bday_str: str) -> str:
                    if not bday_str:
                        return ""
                    import re as _re2
                    from datetime import datetime as _dt, date as _date
                    # Strip ordinals: 4th → 4, 1st → 1, etc.
                    cleaned = _re2.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', bday_str, flags=_re2.I)
                    for fmt in ("%A %d of %B %Y", "%d of %B %Y", "%B %d %Y",
                                "%B %d, %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y"):
                        try:
                            bd = _dt.strptime(cleaned.strip(), fmt).date()
                            today = _date.today()
                            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                            return str(age) if 18 <= age <= 80 else ""
                        except ValueError:
                            continue
                    return ""

                _bday_str = _bio.get("birthday", "") or _bk_data.get("born", "")
                _age_str  = _calc_age(_bday_str)

                # ── Booking history data (computed once, used in header) ──────────
                _hist = get_booking_history(_name) if _HAS_BK_HIST else None
                _h_total = 0; _last_fmt = ""; _rate_str = ""; _studios_str = ""
                if _hist:
                    _h_total = _hist.get("total_bookings", 0)
                    _h_last  = _hist.get("last_date", "")
                    _h_avg   = _hist.get("avg_rate")
                    _h_trend = _hist.get("rate_trend", "")
                    try:
                        from datetime import datetime as _dt2
                        _ld = _dt2.fromisoformat(_h_last)
                        _mo_ago = int((_dt2.now() - _ld).days / 30.44)
                        _last_fmt = f"{_ld.strftime('%b %Y')} ({_mo_ago} mo ago)"
                    except Exception:
                        _last_fmt = _h_last
                    _trend_icon = {"up": "↑", "down": "↓", "stable": "→"}.get(_h_trend, "")
                    _rate_str = f"${_h_avg:,}" if _h_avg else "—"
                    if _trend_icon:
                        _rate_str += f" {_trend_icon}"
                    _studios_str = " · ".join(
                        f"{s} ({n}×)" for s, n in
                        sorted(_hist.get("studios", {}).items(), key=lambda x: -x[1])
                    )

                # ── Profile header: photo | name/agency/info | booking history ──
                _hc_photo, _hc_info, _hc_booking = st.columns([2, 4, 4])

                with _hc_photo:
                    if _photo:
                        try:
                            st.image(_photo, use_container_width=True)
                        except Exception:
                            pass

                with _hc_info:
                    # Name + age + rank badge
                    _age_badge = f" <span style='font-size:1rem;color:#aaa'>{_age_str}</span>" if _age_str else ""
                    _rank_badge_html = ""
                    if _rank_info:
                        _ri_icon, _ri_label, _ri_bg = _rank_info
                        _rank_badge_html = (f" <span style='background:{_ri_bg};border-radius:4px;"
                                            f"padding:2px 9px;font-size:0.8rem;font-weight:600'>"
                                            f"{_ri_icon} {_ri_label}</span>")
                    st.markdown(
                        f"<div style='font-size:1.6rem;font-weight:700;line-height:1.3;margin-bottom:6px'>"
                        f"{_name}{_age_badge}{_rank_badge_html}</div>",
                        unsafe_allow_html=True)

                    # Agency + profile links
                    if _bk_agency:
                        _agency_url    = _booking.get("agency_url", "")
                        _model_slr_url = _bk_data.get("slr_profile_url", "")
                        _model_vrp_url = _bk_data.get("vrp_profile_url", "")
                        _agency_label  = f"[{_bk_agency}]({_agency_url})" if _agency_url else _bk_agency
                        _plinks = []
                        if _model_slr_url: _plinks.append(f"[SLR]({_model_slr_url})")
                        if _model_vrp_url: _plinks.append(f"[VRPorn]({_model_vrp_url})")
                        _pstr = "  ·  " + "  ·  ".join(_plinks) if _plinks else ""
                        st.markdown(f"{_agency_label}{_pstr}")
                    else:
                        st.caption("Not in booking sheet")

                    # Rate + status + location
                    _info_parts = []
                    _avg_rate_h = _bk_data.get("avg rate", "")
                    _status_h   = _bk_data.get("status", "")
                    _loc_h      = _bk_data.get("location", "")
                    if _avg_rate_h: _info_parts.append(f"💰 {_avg_rate_h}")
                    if _status_h:   _info_parts.append(_status_h)
                    if _loc_h:      _info_parts.append(f"📍 {_loc_h}")
                    if _info_parts:
                        st.caption("  ·  ".join(_info_parts))

                    # Available for tags
                    _avail_h = _bk_data.get("available for", "")
                    if _avail_h:
                        _tags_html = " ".join(
                            f"<span style='background:#1e3a5f;border-radius:4px;padding:2px 7px;"
                            f"font-size:0.75rem;margin:2px;display:inline-block'>{t.strip()}</span>"
                            for t in _avail_h.split(",") if t.strip()
                        )
                        st.markdown(_tags_html, unsafe_allow_html=True)

                with _hc_booking:
                    if _hist:
                        st.markdown(
                            f"<div style='background:#0d1f12;border:1px solid #1a3d24;border-radius:8px;"
                            f"padding:12px 14px'>"
                            f"<div style='color:#4ade80;font-size:1.4rem;font-weight:700'>{_h_total}× booked</div>"
                            f"<div style='color:#d1d5db;font-size:0.82rem;margin-top:5px'>Last: {_last_fmt}</div>"
                            f"<div style='color:#d1d5db;font-size:0.82rem'>Rate: {_rate_str}</div>"
                            f"<div style='color:#9ca3af;font-size:0.75rem;margin-top:5px'>{_studios_str}</div>"
                            f"</div>",
                            unsafe_allow_html=True)
                    elif _HAS_BK_HIST:
                        st.markdown(
                            "<div style='background:#1a0e0e;border:1px solid #3d1a1a;border-radius:8px;"
                            "padding:12px 14px'>"
                            "<span style='color:#f87171;font-size:0.88rem'>🔴 Never booked with your studio</span>"
                            "</div>",
                            unsafe_allow_html=True)

                st.divider()

                # ── AI Booking Brief ───────────────────────────────────────────────
                _brief_key = f"booking_brief_{_name.replace(' ','_')}"
                with st.expander("✦ Generate Booking Brief", expanded=False):
                    if st.button("Generate", key=f"gen_brief_{_name.replace(' ','_')}"):
                        _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
                        if _claude_key:
                            import anthropic as _anth
                            # Build context from all available data
                            _ctx_parts = [f"Performer: {_name}"]
                            if _rank_raw: _ctx_parts.append(f"Booking rank: {_rank_raw}")
                            if _bk_agency: _ctx_parts.append(f"Agency: {_bk_agency}")
                            _slr_f = _bk_data.get("slr followers",""); _slr_sc = _bk_data.get("slr scenes","")
                            _vrp_f = _bk_data.get("vrp followers",""); _vrp_v = _bk_data.get("vrp views","")
                            if _slr_f: _ctx_parts.append(f"SLR followers: {_slr_f}")
                            if _slr_sc: _ctx_parts.append(f"SLR scenes: {_slr_sc}")
                            if _vrp_f: _ctx_parts.append(f"VRPorn followers: {_vrp_f}")
                            if _vrp_v: _ctx_parts.append(f"VRPorn views: {_vrp_v}")
                            _avail = _bk_data.get("available for","")
                            if _avail: _ctx_parts.append(f"Available for: {_avail}")
                            _avg_rate = _bk_data.get("avg rate","")
                            if _avg_rate: _ctx_parts.append(f"Avg rate: {_avg_rate}")
                            if _hist:
                                _ctx_parts.append(f"Booked with our studio: {_hist['total_bookings']} times")
                                _ctx_parts.append(f"Last booked: {_hist.get('last_date','')}")
                                _ctx_parts.append(f"Average rate paid: ${_hist.get('avg_rate','N/A')}")
                                _ctx_parts.append(f"Rate trend: {_hist.get('rate_trend','unknown')}")
                            else:
                                _ctx_parts.append("Never booked with our studio")
                            if _age_str: _ctx_parts.append(f"Age: {_age_str}")

                            _brief_prompt = (
                                "You are a talent booking advisor for a VR adult content studio. "
                                "Based on the data below, write a concise 3-sentence booking brief. "
                                "Cover: (1) her current market standing and platform performance, "
                                "(2) your studio's history with her and what that means, "
                                "(3) a clear recommendation — Book Now / Re-book / Monitor / Pass — with one-line reason.\n\n"
                                + "\n".join(_ctx_parts)
                            )
                            try:
                                _bac = _anth.Anthropic(api_key=_claude_key)
                                _bm = _bac.messages.create(
                                    model="claude-sonnet-4-6",
                                    max_tokens=300,
                                    messages=[{"role": "user", "content": _brief_prompt}]
                                )
                                st.session_state[_brief_key] = _bm.content[0].text
                            except Exception as _be:
                                st.session_state[_brief_key] = f"Error: {_be}"
                        else:
                            st.session_state[_brief_key] = "No ANTHROPIC_API_KEY set."

                    _brief_text = st.session_state.get(_brief_key, "")
                    if _brief_text:
                        st.markdown(
                            f"<div style='background:#0d1117;border-radius:6px;padding:12px 14px;"
                            f"font-size:0.88rem;line-height:1.6;color:#e2e8f0'>{_brief_text}</div>",
                            unsafe_allow_html=True
                        )

                # ── Wide two-column layout ────────────────────────────────────────
                _col_bio, _col_scenes = st.columns([5, 7])

                with _col_bio:

                    # ── Notes (prominent warning) ─────────────────────────────────
                    _notes = _bk_data.get("notes", "")
                    if _notes:
                        st.warning(f"**Notes:** {_notes}", icon="⚠️")

                    # ── Compact stats table ───────────────────────────────────────
                    def _stat_row(icon, label, value):
                        return (f"<tr><td style='color:#888;padding:3px 10px 3px 0;"
                                f"white-space:nowrap;font-size:0.85rem'>{icon} {label}</td>"
                                f"<td style='font-weight:600;font-size:0.9rem'>{value}</td></tr>")

                    if _bk_agency:
                        # Booking stats
                        _bk_rows = []
                        for _k, _icon, _lbl in [
                            ("avg rate",         "💰", "Rate"),
                            ("bookings",         "📋", "Bookings"),
                            ("last booked date", "📅", "Last Booked"),
                            ("location",         "📍", "Location"),
                            ("status",           "✅", "Status"),
                        ]:
                            _v = _bk_data.get(_k, "")
                            if _v:
                                _bk_rows.append(_stat_row(_icon, _lbl, _v))

                        # Platform stats (skip zeros)
                        _plat_rows = []
                        for _k, _icon, _lbl in [
                            ("slr followers", "👥", "SLR Followers"),
                            ("slr scenes",    "🎬", "SLR Scenes"),
                            ("slr views",     "👁",  "SLR Views"),
                            ("vrp followers", "👥", "VRP Followers"),
                            ("vrp views",     "👁",  "VRP Views"),
                            ("povr views",    "👁",  "POVR Views"),
                        ]:
                            _v = _bk_data.get(_k, "")
                            if _v and _v not in ("0", ""):
                                _plat_rows.append(_stat_row(_icon, _lbl, _v))

                        # Social (skip zeros)
                        _soc_rows = []
                        for _k, _icon, _lbl in [
                            ("onlyfans",  "🔞", "OnlyFans"),
                            ("twitter",   "𝕏",  "Twitter"),
                            ("instagram", "📸", "Instagram"),
                        ]:
                            _v = _bk_data.get(_k, "")
                            if _v and _v not in ("0", ""):
                                _soc_rows.append(_stat_row(_icon, _lbl, _v))

                        all_rows = _bk_rows
                        if _plat_rows:
                            all_rows += [f"<tr><td colspan='2' style='padding-top:8px;"
                                         f"color:#888;font-size:0.75rem;text-transform:uppercase;"
                                         f"letter-spacing:.05em'>Platform</td></tr>"] + _plat_rows
                        if _soc_rows:
                            all_rows += [f"<tr><td colspan='2' style='padding-top:8px;"
                                         f"color:#888;font-size:0.75rem;text-transform:uppercase;"
                                         f"letter-spacing:.05em'>Social</td></tr>"] + _soc_rows

                        if all_rows:
                            st.markdown(
                                f"<table style='border-collapse:collapse;width:100%'>"
                                + "".join(all_rows) + "</table>",
                                unsafe_allow_html=True
                            )


                    # ── Physical stats ────────────────────────────────────────────
                    _BIO_KEYS = [
                        (None,             "birthday",    "Born"),
                        (None,             "birthplace",  "Birthplace"),
                        (None,             "nationality", "Nationality"),
                        (None,             "ethnicity",   "Ethnicity"),
                        ("height",         "height",      "Height"),
                        ("weight",         "weight",      "Weight"),
                        ("measurements",   "measurements","Measurements"),
                        (None,             "bra/cup size","Bra / Cup"),
                        ("hair",           "hair",        "Hair"),
                        ("eyes",           "eyes",        "Eyes"),
                        ("natural breasts","boobs",       "Natural Breasts"),
                        ("tattoos",        None,          "Tattoos"),
                        ("shoe size",      None,          "Shoe Size"),
                        (None,             "years active","Years Active"),
                    ]
                    _seen = set()
                    _bio_rows = []
                    for _bk_key, _bio_key, _label in _BIO_KEYS:
                        if _label in _seen:
                            continue
                        _val = (_bk_data.get(_bk_key) if _bk_key else "") or \
                               (_bio.get(_bio_key) if _bio_key else "")
                        if _val:
                            _bio_rows.append({"": _label, " ": _val})
                            _seen.add(_label)

                    if _bio_rows:
                        _phys_html = (
                            "<p style='color:#888;font-size:0.75rem;text-transform:uppercase;"
                            "letter-spacing:.05em;margin:10px 0 4px'>Physical Stats</p>"
                            "<table style='border-collapse:collapse;width:100%'>"
                            + "".join(_stat_row("", r[""], r[" "]) for r in _bio_rows)
                            + "</table>"
                        )
                        st.markdown(_phys_html, unsafe_allow_html=True)

                    # About / bio blurb
                    if _about:
                        st.markdown(
                            f"<p style='font-size:0.85rem;color:#bbb;line-height:1.5;"
                            f"margin-top:8px'>{_about}</p>",
                            unsafe_allow_html=True
                        )
                    elif _ddg and not _bio_rows:
                        st.markdown(
                            f"<p style='font-size:0.85rem;color:#bbb;line-height:1.5;"
                            f"margin-top:8px'>{_ddg[:400]}</p>",
                            unsafe_allow_html=True
                        )

                    # Source links (subtle, at bottom)
                    _sources = _profile.get("_sources", [])
                    if _sources:
                        st.caption("Sources: " + " · ".join(
                            f"[{_sn}]({_su})" for _sn, _su in _sources
                        ))

                # ── Scenes column ─────────────────────────────────────────────────
                with _col_scenes:
                    _slr_label = f"SexLikeReal ({len(_slr)})" if _slr else "SexLikeReal"
                    _vrp_label = f"VRPorn ({len(_vrp)})"      if _vrp else "VRPorn"
                    _stab_slr, _stab_vrp = st.tabs([_slr_label, _vrp_label])

                    def _render_scenes(scenes, platform_name, base_url=""):
                        if not scenes:
                            st.info(f"No {platform_name} scenes found.", icon="🎬")
                            return
                        for _sc in scenes:
                            _sc_title    = _sc.get("title", "")
                            _sc_date     = _sc.get("date", "")
                            _sc_studio   = _sc.get("studio", "")
                            _sc_url      = _sc.get("url", "")
                            _sc_thumb    = _sc.get("thumb", "")
                            _sc_views    = _sc.get("views", "")
                            _sc_likes    = _sc.get("likes", "")
                            _sc_comments = _sc.get("comments", "")
                            _sc_duration = _sc.get("duration", "")
                            if not _sc_title:
                                continue
                            if _sc_url and not _sc_url.startswith("http") and base_url:
                                _sc_url = base_url + _sc_url

                            # Card-style container
                            with st.container(border=True):
                                _tc, _ic = st.columns([2, 5])
                                with _tc:
                                    if _sc_thumb:
                                        try:
                                            st.image(_sc_thumb, use_container_width=True)
                                        except Exception:
                                            pass
                                with _ic:
                                    if _sc_url:
                                        st.markdown(f"**[{_sc_title}]({_sc_url})**")
                                    else:
                                        st.markdown(f"**{_sc_title}**")
                                    # Meta: studio · date · duration
                                    _meta = []
                                    if _sc_studio:   _meta.append(f"🎬 {_sc_studio}")
                                    if _sc_date:     _meta.append(f"📅 {_sc_date}")
                                    if _sc_duration: _meta.append(f"⏱️ {_sc_duration}")
                                    if _meta:
                                        st.caption("  ·  ".join(_meta))
                                    # Stats: views · likes · comments
                                    _stats = []
                                    if _sc_views:    _stats.append(f"👁 {_sc_views}")
                                    if _sc_likes:    _stats.append(f"❤️ {_sc_likes}")
                                    if _sc_comments: _stats.append(f"💬 {_sc_comments}")
                                    if _stats:
                                        st.caption("  ·  ".join(_stats))

                    with _stab_slr:
                        _render_scenes(_slr, "SLR", "https://sexlikereal.com")

                    with _stab_vrp:
                        _render_scenes(_vrp, "VRPorn", "https://vrporn.com")

                    # ── Competitor Activity ────────────────────────────────────────
                    _all_scenes = _slr + _vrp
                    _competitor_scenes = get_competitor_scenes(_all_scenes) if _HAS_BK_HIST else []
                    if _competitor_scenes:
                        st.markdown(
                            "<p style='color:#888;font-size:0.72rem;text-transform:uppercase;"
                            "letter-spacing:.05em;margin:14px 0 6px'>Competitor Activity</p>",
                            unsafe_allow_html=True
                        )
                        for _cs in _competitor_scenes:
                            _cs_date = _cs.get("date","")
                            _cs_title = _cs.get("title","")
                            _cs_studio = _cs.get("studio","")
                            _cs_label = f"**{_cs_studio}** · {_cs_date}"
                            if _cs_title:
                                _cs_label += f" — _{_cs_title[:50]}_"
                            st.caption(_cs_label)


    # ── TAB 6: Description Generator ──────────────────────────────────────────────
with tab_desc:
    if _has_tab("Descriptions"):

        # ── Helper: build .docx bytes ───────────────────────────────────────────────
        @st.cache_data
        def _build_docx(talent_line, title, tags, categories, writeup, meta_title="", meta_desc="", studio="FPVR"):
            """Return bytes of a formatted .docx matching the studio template."""
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
            import io

            doc = Document()
            for p in doc.paragraphs:
                p._element.getparent().remove(p._element)

            style = doc.styles['Normal']
            style.font.name = 'Arial'
            style.font.size = Pt(10)

            def _add_hyperlink(paragraph, text, url):
                """Add a clickable hyperlink to a paragraph."""
                part = paragraph.part
                r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
                hyperlink = OxmlElement('w:hyperlink')
                hyperlink.set(qn('r:id'), r_id)
                run_el = OxmlElement('w:r')
                rPr = OxmlElement('w:rPr')
                c = OxmlElement('w:color')
                c.set(qn('w:val'), '0563C1')
                rPr.append(c)
                u = OxmlElement('w:u')
                u.set(qn('w:val'), 'single')
                rPr.append(u)
                run_el.append(rPr)
                txt = OxmlElement('w:t')
                txt.text = text
                txt.set(qn('xml:space'), 'preserve')
                run_el.append(txt)
                hyperlink.append(run_el)
                paragraph._element.append(hyperlink)

            def _add_line(bold_prefix, normal_text=""):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                if bold_prefix:
                    run = p.add_run(bold_prefix)
                    run.bold = True
                if normal_text:
                    p.add_run(normal_text)
                return p

            def _add_linked_line(bold_prefix, items_csv, url_fn):
                """Add a line with bold prefix and comma-separated hyperlinked items."""
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(bold_prefix)
                run.bold = True
                items = [i.strip() for i in items_csv.split(",") if i.strip()]
                for idx, item in enumerate(items):
                    url = url_fn(studio, item)
                    _add_hyperlink(p, item, url)
                    if idx < len(items) - 1:
                        p.add_run(", ")
                return p

            _add_line(talent_line)
            _add_line("Title: ", title)
            _add_linked_line("Tags: ", tags, _tag_url)
            _add_linked_line("Categories: ", categories, _category_url)
            _add_line("Write-up:")
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.add_run(writeup)
            if meta_title:
                _add_line("")
                _add_line("Meta Title: ", meta_title)
            if meta_desc:
                _add_line("Meta Description: ", meta_desc)

            buf = io.BytesIO()
            doc.save(buf)
            return buf.getvalue()

        def _name_slug(full_name: str) -> str:
            """'First Last' → 'FirstLast'"""
            return full_name.strip().replace(" ", "")

        # ── Batch: Find Missing Descriptions ────────────────────────────────────────
        _SCAN_PATH = os.path.join(os.path.dirname(__file__), "mega_scan.json")

        def _find_scene_data(scene_id: str) -> dict:
            import time, sys
            cache_key = f"_scene_cache_{scene_id}"
            cache_ts_key = f"_scene_cache_ts_{scene_id}"
            now = time.time()
            if cache_key in st.session_state:
                age = now - st.session_state.get(cache_ts_key, 0)
                if age < 300:
                    return st.session_state[cache_key]
            result = {"female": "", "male": "", "title": "", "tags": "", "categories": "", "plot": ""}
            try:
                _sheets_mod_path = os.path.dirname(__file__)
                if _sheets_mod_path not in sys.path:
                    sys.path.insert(0, _sheets_mod_path)
                import sheets_integration as _si
                import re as _re
                _m = _re.match(r'^([A-Za-z]+)(\d+)$', scene_id.strip())
                if not _m:
                    return result
                _scene_studio = _m.group(1).upper()
                _scene_num = int(_m.group(2))
                _scene_num_padded = f"{_scene_num:04d}"
                _scene_full = f"{_scene_studio}{_scene_num_padded}"
                sh = _si.get_spreadsheet()
                for ws in _si.month_tabs(sh):
                    rows = ws.get_all_values()
                    for row in rows[1:]:
                        row = _si._pad(row, 13)
                        _col_studio = row[_si.COL_STUDIO].strip().upper()
                        _col_scene  = row[_si.COL_SCENE].strip()
                        _constructed = f"{_col_studio}{_col_scene.zfill(4)}" if _col_scene.isdigit() else _col_scene.upper()
                        if _constructed == _scene_full or _col_scene.upper() == _scene_full:
                            result["female"]     = row[_si.COL_FEMALE].strip()
                            result["male"]       = row[_si.COL_MALE].strip()
                            result["plot"]       = row[_si.COL_PLOT].strip()
                            result["title"]      = row[10].strip() if len(row) > 10 else ""
                            result["tags"]       = ""
                            result["categories"] = ""
                            st.session_state[cache_key] = result
                            st.session_state[cache_ts_key] = now
                            return result
            except Exception as _e:
                st.warning(f"Sheet lookup failed for {scene_id}: {_e}")
            st.session_state[cache_key] = result
            st.session_state[cache_ts_key] = now
            return result

        _STUDIO_COLORS = {"FPVR": "#3b82f6", "VRH": "#8b5cf6", "VRA": "#ec4899", "NJOI": "#f97316"}
        _GRAIL_ID  = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
        _GRAIL_TAB = {"FPVR": "FPVR", "VRH": "VRH", "VRA": "VRA", "NJOI": "NNJOI"}

        def _batch_prefetch(scene_list: list) -> dict:
            import time, sys, re as _re5
            _ck  = "_desc_batch_names"
            _tsk = "_desc_batch_names_ts"
            _now = time.time()
            if _ck in st.session_state and _now - st.session_state.get(_tsk, 0) < 600:
                return st.session_state[_ck]
            out = {sc["scene_id"]: {"title": "", "categories": "", "tags": "", "plot": ""}
                   for sc in scene_list}
            try:
                _sp = os.path.dirname(__file__)
                if _sp not in sys.path:
                    sys.path.insert(0, _sp)
                import sheets_integration as _si
                import gspread
                from google.oauth2.service_account import Credentials
                _creds = Credentials.from_service_account_file(
                    os.path.join(os.path.dirname(__file__), "service_account.json"),
                    scopes=["https://www.googleapis.com/auth/spreadsheets"])
                _gc = gspread.authorize(_creds)
                _grail_sh = _gc.open_by_key(_GRAIL_ID)
                _by_tab = {}
                for sc in scene_list:
                    _tab = _GRAIL_TAB.get(sc["studio"], sc["studio"])
                    _m   = _re5.match(r'^[A-Za-z]+(\d+)$', sc["scene_id"])
                    if _m:
                        _by_tab.setdefault(_tab, []).append((sc["scene_id"], int(_m.group(1))))
                for _tab, _entries in _by_tab.items():
                    try:
                        _ws   = _grail_sh.worksheet(_tab)
                        _rows = _ws.get_all_values()
                        _id_map = {int(r[1]): r for r in _rows[1:] if len(r) > 1 and r[1].isdigit()}
                        for _sid, _num in _entries:
                            _r = _id_map.get(_num)
                            if _r:
                                out[_sid]["title"]      = _r[3].strip() if len(_r) > 3 else ""
                                out[_sid]["categories"] = _r[5].strip() if len(_r) > 5 else ""
                                out[_sid]["tags"]       = _r[6].strip() if len(_r) > 6 else ""
                    except Exception as _gpf:
                        st.warning(f"Could not load Grail data: {_gpf}")
                _female_map = {}
                for sc in scene_list:
                    _f = sc.get("female", "").strip().lower()
                    if _f and _f not in _female_map:
                        _female_map[_f] = sc["scene_id"]
                _scripts_sh = _gc.open_by_key(_si.SHEET_ID)
                for _ws in _si.month_tabs(_scripts_sh):
                    _rows = _ws.get_all_values()
                    for _row in _rows[1:]:
                        _row = _si._pad(_row, 13)
                        _rf   = _row[_si.COL_FEMALE].strip().lower()
                        _plot = _row[_si.COL_PLOT].strip()
                        if _plot and _rf in _female_map:
                            _sid = _female_map[_rf]
                            if not out[_sid].get("plot"):
                                out[_sid]["plot"] = _plot
            except Exception:
                pass
            st.session_state[_ck]  = out
            st.session_state[_tsk] = _now
            return out

        # Load scan data once
        import json as _json
        if "scan_data" not in st.session_state:
            try:
                with open(_SCAN_PATH, "r", encoding="utf-8") as _f:
                    st.session_state["scan_data"] = _json.load(_f)
            except Exception:
                st.session_state["scan_data"] = None
        _scan_data = st.session_state["scan_data"]
        _missing_scenes = []
        if _scan_data:
            _missing_scenes = [s for s in _scan_data.get("scenes", []) if not s.get("has_description", True)]
        _names_cache = _batch_prefetch(_missing_scenes) if _missing_scenes else {}

        # Handle card load clicks BEFORE widgets render
        if "desc_load_trigger" in st.session_state:
            _trigger    = st.session_state.pop("desc_load_trigger")
            _scene_id_t = _trigger["scene_id"]
            _studio_t   = _trigger["studio"]
            import re as _re3
            _nm3 = _re3.match(r'^[A-Za-z]+(\d+)$', _scene_id_t)
            st.session_state["d_studio"]    = _studio_t
            st.session_state["d_scene_num"] = int(_nm3.group(1)) if _nm3 else 1
            _scan_entry = next((s for s in _missing_scenes if s["scene_id"] == _scene_id_t), {})
            _sheet_data = _names_cache.get(_scene_id_t, {})
            _female_t   = _trigger.get("female") or _scan_entry.get("female", "")
            _male_t     = _trigger.get("male")   or _scan_entry.get("male", "")
            if _female_t:                         st.session_state["d_female"] = _female_t
            if _male_t:                           st.session_state["d_male"]   = _male_t
            if _sheet_data.get("title"):          st.session_state["d_title"]  = _sheet_data["title"]
            if _sheet_data.get("plot"):           st.session_state["d_plot"]   = _sheet_data["plot"]
            if _sheet_data.get("categories"):     st.session_state["d_cats"]   = _sheet_data["categories"]
            if _sheet_data.get("tags"):           st.session_state["d_tags"]   = _sheet_data["tags"]
            st.session_state["desc_active_scene"] = _scene_id_t
            st.session_state["_desc_auto_gen"]    = True
            st.session_state.pop("d_parsed", None)
            st.session_state.pop("d_writeup", None)
            st.session_state.pop("d_writeup_edit", None)
            st.session_state.pop("_desc_saved_mega", None)

        # ── TWO COLUMN LAYOUT ───────────────────────────────────────────────────────
        _col_q, _col_f = st.columns([1, 3], gap="medium")

        # ── LEFT: Batch Queue ───────────────────────────────────────────────────────
        with _col_q:
            if _scan_data:
                _scan_ts = _scan_data.get("scanned_at", "")[:10]
                _has_cnt = len(_scan_data.get("scenes", [])) - len(_missing_scenes)
                st.markdown(
                    f"<div style='margin-bottom:12px'>"
                    f"<div style='font-size:0.9rem;font-weight:700;color:#f3f4f6'>"
                    f"Missing <span style='background:#374151;color:#9ca3af;font-size:0.65rem;"
                    f"padding:2px 8px;border-radius:10px;margin-left:4px'>{len(_missing_scenes)}</span></div>"
                    f"<div style='color:#4b5563;font-size:0.65rem;margin-top:2px'>"
                    f"Scanned {_scan_ts} · {_has_cnt} complete</div></div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown("<div style='font-weight:700;color:#f3f4f6;margin-bottom:6px'>Queue</div>",
                            unsafe_allow_html=True)
                st.caption("No scan file. Run `scan_mega.py` on Mac.")

            _active_scene = st.session_state.get("desc_active_scene", "")
            from itertools import groupby as _groupby
            _sorted_scenes = sorted(_missing_scenes, key=lambda x: x["studio"])
            for _stu, _grp_iter in _groupby(_sorted_scenes, key=lambda x: x["studio"]):
                _grp = list(_grp_iter)
                _sc = _STUDIO_COLORS.get(_stu, "#6b7280")
                st.markdown(
                    f"<div style='color:{_sc};font-size:0.62rem;font-weight:700;letter-spacing:.1em;"
                    f"text-transform:uppercase;margin:8px 0 4px 0;border-bottom:1px solid {_sc}33;"
                    f"padding-bottom:3px'>{_stu} ({len(_grp)})</div>",
                    unsafe_allow_html=True
                )
                for _ms in _grp:
                    _ms_id     = _ms["scene_id"]
                    _is_active = (_ms_id == _active_scene)
                    _female    = _ms.get("female", "")
                    _male      = _ms.get("male", "")
                    _talent_display = _female or "—"
                    if _male:
                        _talent_display += f" / {_male}"
                    _grail_d   = _names_cache.get(_ms_id, {})
                    _has_plot  = bool(_grail_d.get("plot"))
                    _has_title = bool(_grail_d.get("title"))
                    _ready_dot = "🟢" if (_has_plot and _has_title) else ("🟡" if _has_plot else "🔴")
                    _btn_label = f"{_ready_dot} {_ms_id} · {_talent_display}"
                    if st.button(_btn_label, key=f"load_{_ms_id}", use_container_width=True,
                                 type="primary" if _is_active else "secondary"):
                        st.session_state["desc_load_trigger"] = {
                            "scene_id": _ms_id, "studio": _stu,
                            "female": _ms.get("female", ""), "male": _ms.get("male", ""),
                        }
                        st.rerun()
                    _meta_parts = []
                    if _has_title:  _meta_parts.append("title ✓")
                    if _has_plot:   _meta_parts.append("plot ✓")
                    if not _meta_parts: _meta_parts.append("no sheet data")
                    st.caption("  ·  ".join(_meta_parts))

        # ── RIGHT: Form + Output ────────────────────────────────────────────────────
        with _col_f:

            _active_scene = st.session_state.get("desc_active_scene", "")
            if _active_scene:
                _ac_color = _STUDIO_COLORS.get(st.session_state.get("d_studio", ""), "#6b7280")
                st.markdown(
                    f"<div style='display:inline-block;background:{_ac_color}18;border:1px solid {_ac_color}40;"
                    f"color:{_ac_color};font-size:0.75rem;font-weight:700;padding:2px 10px;"
                    f"border-radius:10px;margin-bottom:8px'>Editing: {_active_scene}</div>",
                    unsafe_allow_html=True
                )

            # ── Form ──────────────────────────────────────────────────────────────
            _da, _db, _dc = st.columns([3, 2, 2])
            with _da:
                _d_studio = st.selectbox("Studio", list(_DESC_STUDIO_CONFIG.keys()), key="d_studio")
            with _db:
                if "d_scene_num" not in st.session_state:
                    st.session_state["d_scene_num"] = 1
                _d_scene_num = st.number_input("Scene #", min_value=1, max_value=9999,
                                                step=1, key="d_scene_num")
            with _dc:
                _d_res = st.selectbox("Resolution", ["8K", "6K", "4K"], key="d_res")

            _de, _df = st.columns(2)
            with _de:
                _d_female = st.text_input("Female Talent(s)", placeholder="First Last, First Last", key="d_female")
            with _df:
                _d_male = st.text_input("Male Talent(s)", placeholder="First Last (blank = solo)", key="d_male")

            _d_title = st.text_input("Scene Title", key="d_title")

            # Categories — multiselect from approved list per studio
            _dg, _dh = st.columns(2)
            with _dg:
                _studio_cats = _STUDIO_CATEGORIES.get(_d_studio)
                if _studio_cats:
                    _d_cats_list = st.multiselect("Categories", _studio_cats,
                                                   default=[c.strip() for c in st.session_state.get("d_cats", "").split(",") if c.strip() in _studio_cats] if st.session_state.get("d_cats") else [],
                                                   key="d_cats_ms")
                    _d_cats = ", ".join(_d_cats_list)
                else:
                    _d_cats = st.text_input("Categories", placeholder="8K, Brunette, Natural Tits…", key="d_cats")
            with _dh:
                _d_tags = st.text_input("Tags", placeholder="Sexy Brunette, POV, Cowgirl, Creampie…", key="d_tags")

            _d_plot = st.text_area("Scene Plot / Setup", placeholder="Paste the scene plot here…",
                                    height=100, key="d_plot")

            # ── Advanced / optional fields ─────────────────────────────────────────
            _adv_expanded = bool(
                st.session_state.get("d_model_props") or st.session_state.get("d_sex_pos") or
                st.session_state.get("d_wardrobe")   or st.session_state.get("d_target_kw")
            )
            with st.expander("📝 Advanced Details (optional)", expanded=_adv_expanded):
                _di, _dj = st.columns(2)
                with _di:
                    _d_model_props = st.text_input("Model Properties",
                                                    placeholder="Long dark hair, big natural tits, smackable ass",
                                                    key="d_model_props")
                with _dj:
                    _d_target_kw = st.text_input("Target Keywords",
                                                  placeholder=f"{_d_studio} VR porn, 8K VR porn",
                                                  key="d_target_kw")
                _d_wardrobe = st.text_input("Wardrobe", placeholder="White lace lingerie, black stockings",
                                             key="d_wardrobe")
                _d_sex_pos = st.text_area("Sex Positions (detailed)", placeholder="She drops to her knees for a BJ, then reverse cowgirl, cowgirl, doggy, missionary. Finishes with a creampie.",
                                           height=80, key="d_sex_pos")
                _studio_tags_ref = _STUDIO_TAGS.get(_d_studio)
                if _studio_tags_ref:
                    with st.expander(f"Approved {_d_studio} Tags Reference", expanded=False):
                        st.caption(_studio_tags_ref)

            # Generate / Regenerate buttons
            _d_gen_c, _d_reg_c = st.columns([1, 1])
            with _d_gen_c:
                _d_generate = st.button("Generate", type="primary",
                                         use_container_width=True, key="d_generate")
            with _d_reg_c:
                _d_regen = st.button("Regenerate All", use_container_width=True, key="d_regen",
                                      disabled=("d_parsed" not in st.session_state))

            _auto_gen = st.session_state.pop("_desc_auto_gen", False)

            # ── Generation logic ───────────────────────────────────────────────────
            if (_d_generate or _d_regen or _auto_gen) and _d_plot.strip():  # _d_regen2 triggers via rerun
                _d_cfg = _DESC_STUDIO_CONFIG[_d_studio]
                if _is_compilation(_d_title):
                    _studio_system = _DESC_SYSTEMS_COMPILATION.get(_d_studio, _DESC_SYSTEMS_FULL.get(_d_studio, ""))
                else:
                    _studio_system = _DESC_SYSTEMS_FULL.get(_d_studio, _DESC_SYSTEMS_FULL["VRH"])

                _user_prompt = _build_scene_prompt(
                    _d_studio, _d_cfg,
                    title=_d_title,
                    female=_d_female,
                    male=_d_male,
                    plot=_d_plot,
                    categories=_d_cats,
                    model_props=_d_model_props,
                    sex_positions=_d_sex_pos,
                    target_keywords=_d_target_kw,
                    resolution=_d_res,
                    wardrobe=st.session_state.get("d_wardrobe", ""),
                )

                _max_tok = 1200 if _d_studio == "FPVR" else 600

                _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if _claude_key:
                    import anthropic as _anth
                    with st.spinner("Generating description…"):
                        try:
                            _bac = _anth.Anthropic(api_key=_claude_key)
                            _bm  = _bac.messages.create(
                                model="claude-sonnet-4-6",
                                max_tokens=_max_tok,
                                system=_studio_system,
                                messages=[{"role": "user", "content": _user_prompt}]
                            )
                            _raw_text = _bm.content[0].text.strip()
                            st.session_state["d_writeup"] = _raw_text
                            st.session_state["d_parsed"] = _parse_desc_output(_raw_text)
                            st.session_state.pop("d_editing_para", None)
                        except Exception as _de2:
                            st.error(f"Generation failed: {_de2}")
                else:
                    st.warning("ANTHROPIC_API_KEY not set.")

            # ── Output: Inline paragraph editing ───────────────────────────────────
            if "d_parsed" in st.session_state:
                _parsed = st.session_state["d_parsed"]
                _d_cfg2    = _DESC_STUDIO_CONFIG[_d_studio]
                _f_names   = [n.strip() for n in _d_female.split(",") if n.strip()]
                _m_names   = [n.strip() for n in _d_male.split(",") if n.strip()]
                _talent_ln = ", ".join(_f_names + _m_names)
                _scene_id  = f"{_d_cfg2['prefix']}{int(_d_scene_num):04d}"
                _f_slug    = _name_slug(_f_names[0]) if _f_names else "Unknown"
                _m_slug    = ("-" + _name_slug(_m_names[0])) if _m_names else ""
                _filename_base = f"{_scene_id}-{_f_slug}{_m_slug}"

                st.divider()
                _out_hdr, _out_regen = st.columns([4, 1])
                with _out_hdr:
                    st.markdown(f"<div class='sh'>📄 Output — <code style='font-size:0.75rem'>{_filename_base}</code></div>",
                                unsafe_allow_html=True)
                with _out_regen:
                    _d_regen2 = st.button("↺ Regen All", key="d_regen2", use_container_width=True)
                if _d_regen2:
                    st.session_state.pop("d_parsed", None)
                    st.session_state["_desc_auto_gen"] = True
                    st.rerun()

                # ── Paragraphs with click-to-edit ─────────────────────────────────
                _editing = st.session_state.get("d_editing_para", None)

                for _pi, _para in enumerate(_parsed.get("paragraphs", [])):
                    _p_title = _para.get("title", "")
                    _p_body  = _para.get("body", "")

                    if _editing == _pi:
                        # ── EDIT MODE ──────────────────────────────────────────
                        if _p_title:
                            _new_title = st.text_input(f"Title", value=_p_title, key=f"d_pt_{_pi}")
                        _new_body = st.text_area(f"Paragraph {_pi + 1}", value=_p_body,
                                                  height=150, key=f"d_pb_{_pi}")
                        _ec1, _ec2, _ec3 = st.columns([1, 1, 1])
                        with _ec1:
                            if st.button("Save Edit", key=f"d_save_{_pi}", use_container_width=True, type="primary"):
                                _parsed["paragraphs"][_pi]["body"] = _new_body
                                if _p_title:
                                    _parsed["paragraphs"][_pi]["title"] = _new_title
                                st.session_state["d_parsed"] = _parsed
                                st.session_state["d_writeup"] = _reassemble_desc(_parsed)
                                st.session_state.pop("d_editing_para", None)
                                st.rerun()
                        with _ec2:
                            if st.button("Regenerate", key=f"d_regen_p_{_pi}", use_container_width=True):
                                _claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
                                if _claude_key:
                                    import anthropic as _anth_r
                                    _regen_prompt = f"""Rewrite ONLY this paragraph (paragraph {_pi + 1}) of the scene description.
Keep the same style, tone, and flow as the rest of the description.

Current paragraph title: {_p_title}
Current paragraph text: {_p_body}

Scene context:
- Studio: {_DESC_STUDIO_CONFIG[_d_studio]['name']}
- Performer: {_d_female}
- Title: {_d_title}
- Plot: {_d_plot[:300]}

Rewrite this paragraph now. Output ONLY the paragraph text (no title, no meta fields). Keep similar length."""
                                _studio_system = _DESC_SYSTEMS_FULL.get(_d_studio, _DESC_SYSTEMS_FULL["VRH"])
                                with st.spinner(f"Regenerating paragraph {_pi + 1}…"):
                                    try:
                                        _bac_r = _anth_r.Anthropic(api_key=_claude_key)
                                        _bm_r = _bac_r.messages.create(
                                            model="claude-sonnet-4-6", max_tokens=500,
                                            system=_studio_system,
                                            messages=[{"role": "user", "content": _regen_prompt}])
                                        _parsed["paragraphs"][_pi]["body"] = _bm_r.content[0].text.strip()
                                        st.session_state["d_parsed"] = _parsed
                                        st.session_state["d_writeup"] = _reassemble_desc(_parsed)
                                        st.rerun()
                                    except Exception as _re2:
                                        st.error(f"Regeneration failed: {_re2}")
                    with _ec3:
                        if st.button("Cancel", key=f"d_cancel_{_pi}", use_container_width=True):
                            st.session_state.pop("d_editing_para", None)
                            st.rerun()
                else:
                    # ── READ MODE — ✏️ button inline with title ───────────────
                    _r_lbl, _r_btn = st.columns([6, 1])
                    with _r_lbl:
                        if _p_title:
                            st.markdown(f"**{_p_title}**")
                    with _r_btn:
                        if st.button("✏️", key=f"d_edit_{_pi}", help="Edit this paragraph"):
                            st.session_state["d_editing_para"] = _pi
                            st.rerun()
                    st.markdown(
                        f"<div style='background:#111827;border:1px solid #1f2937;border-radius:8px;"
                        f"padding:12px 16px;margin-bottom:8px'>"
                        f"<div style='color:#d1d5db;font-size:0.82rem;line-height:1.6'>{_p_body}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                st.divider()

                # ── SEO fields (for website publishing) ────────────────────────
                st.markdown("<div class='sh'>SEO — Website Meta Tags</div>", unsafe_allow_html=True)
                st.caption("These go on the website when the scene is published — the title tag and Google search snippet.")
                _meta_t = st.text_input("SEO Page Title (browser tab / Google result title)", value=_parsed.get("meta_title", ""),
                                         key="d_meta_title")
                _meta_d = st.text_input("SEO Description (Google search snippet, max 160 chars)",
                                         value=_parsed.get("meta_description", ""),
                                         key="d_meta_desc", max_chars=200)
                _md_len = len(_meta_d)
                _md_color = "#22c55e" if _md_len <= 160 else "#ef4444"
                st.markdown(f"<span style='color:{_md_color};font-size:0.7rem'>{_md_len}/160 chars</span>",
                            unsafe_allow_html=True)

                # Update parsed with edited meta fields
                if _meta_t != _parsed.get("meta_title", ""):
                    _parsed["meta_title"] = _meta_t
                    st.session_state["d_parsed"] = _parsed
                if _meta_d != _parsed.get("meta_description", ""):
                    _parsed["meta_description"] = _meta_d
                    st.session_state["d_parsed"] = _parsed

                st.divider()

                # ── Assemble final text for download ──────────────────────────────
                _final_text = _reassemble_desc(_parsed)

                # Build .txt with HTML-linked categories and tags
                _txt_parts = []
                _txt_parts.append(_talent_ln)
                _txt_parts.append(f"Title: {_d_title}")
                _txt_parts.append(f"Tags: {_tags_as_html(_d_studio, _d_tags)}")
                _txt_parts.append(f"Categories: {_cats_as_html(_d_studio, _d_cats)}")
                _txt_parts.append("")
                _txt_parts.append(_final_text)
                _full_txt = "\n".join(_txt_parts)

                # ── Save to MEGA + Download buttons ───────────────────────────────
                try:
                    _docx_bytes_out = _build_docx(_talent_ln, _d_title, _d_tags,
                                                   _d_cats, _final_text, _meta_t, _meta_d,
                                                   studio=_d_studio)
                except Exception:
                    _docx_bytes_out = None

                _dl1, _dl2, _dl3 = st.columns(3)
                with _dl1:
                    _d_tab_key = {"FPVR": "FPVR", "VRH": "VRH", "VRA": "VRA", "NJOI": "NNJOI"}.get(_d_studio, _d_studio)
                    def _on_save_desc_mega(_sid=_scene_id, _fn=_filename_base, _txt=_full_txt,
                                           _docx=_docx_bytes_out, _tab_key=_d_tab_key):
                        _stage = os.path.join(os.path.dirname(__file__), "mega_staging")
                        os.makedirs(_stage, exist_ok=True)
                        _scene_dir = os.path.join(_stage, _tab_key, _sid, "Description")
                        os.makedirs(_scene_dir, exist_ok=True)
                        with open(os.path.join(_scene_dir, f"{_fn}.txt"), "w", encoding="utf-8") as _f:
                            _f.write(_txt)
                        if _docx:
                            with open(os.path.join(_scene_dir, f"{_fn}.docx"), "wb") as _f:
                                _f.write(_docx)
                        import json as _json_save2
                        _scan_path2 = os.path.join(os.path.dirname(__file__), "mega_scan.json")
                        try:
                            with open(_scan_path2, "r", encoding="utf-8") as _sf:
                                _scan2 = _json_save2.load(_sf)
                            _sid_pad2 = re.sub(r'^([A-Za-z]+)(\d+)$', lambda m: m.group(1) + m.group(2).zfill(4), _sid)
                            for _s2 in _scan2.get("scenes", []):
                                if _s2.get("scene_id") in (_sid, _sid_pad2):
                                    _s2["has_description"] = True
                                    break
                            with open(_scan_path2, "w", encoding="utf-8") as _sf:
                                _json_save2.dump(_scan2, _sf, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        st.session_state.pop("_missing_data", None)
                        st.session_state.pop("_missing_data_ts", None)
                        st.session_state.pop("scan_data", None)
                        st.session_state["_desc_saved_mega"] = True
                    # MEGA description save disabled — descriptions managed manually
                    st.caption("_Save to MEGA disabled_")
                with _dl2:
                    if _docx_bytes_out:
                        st.download_button("⬇ Download .docx", data=_docx_bytes_out,
                                           file_name=f"{_filename_base}.docx",
                                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           use_container_width=True, key="d_dl_docx")
                    else:
                        st.error("docx build failed")
                with _dl3:
                    st.download_button("⬇ Download .txt", data=_full_txt.encode("utf-8"),
                                       file_name=f"{_filename_base}.txt",
                                       mime="text/plain",
                                       use_container_width=True, key="d_dl_txt")

    # ── TAB 7: Compilations ───────────────────────────────────────────────────────
with tab_comp:
    if _has_tab("Compilations"):
        import sys as _sys2, json as _json_c
        _SW_DIR = os.path.dirname(__file__)  # comp_tools.py lives alongside script_writer_app.py
        if _SW_DIR not in _sys2.path:
            _sys2.path.insert(0, _SW_DIR)

        _COMP_STUDIO_COLORS = {"FPVR": "#3b82f6", "VRH": "#8b5cf6", "VRA": "#ec4899", "NJOI": "#f97316"}

        @st.fragment
        def _comp_fragment():

            # ── Studio selector ────────────────────────────────────────────────────────
            _comp_studios = ["FPVR", "VRH", "VRA"]
            _comp_studio = st.segmented_control(
                "Studio", _comp_studios, default="VRH", key="comp_studio",
                label_visibility="collapsed"
            ) or "VRH"
            _cs_color = _COMP_STUDIO_COLORS.get(_comp_studio, "#6b7280")

            st.divider()

            # ── Load Grail scenes (Streamlit-cached, shared across all sessions) ─────
            @st.cache_data(ttl=3600, show_spinner=False)
            def _load_grail_cached(studio):
                import comp_tools as _ct
                return _ct.load_grail_scenes(studio)

            @st.cache_data(ttl=1800, show_spinner=False)
            def _load_existing_comps_cached(studio):
                import comp_tools as _ct_ec
                return _ct_ec.load_existing_comps(studio)

            # ── Two panels: Generate | Existing ───────────────────────────────────────
            _cp_gen, _cp_exist = st.tabs(["✨ Generate New Comp", "📋 Existing Comps"])

            # ── GENERATE PANEL ─────────────────────────────────────────────────────────
            with _cp_gen:

                # ── Step 1: Suggest ideas ──────────────────────────────────────────────
                st.markdown("<div class='sh'>💡 SUGGEST IDEAS</div>", unsafe_allow_html=True)
                _suggest_col, _n_col = st.columns([3, 1])
                with _suggest_col:
                    _suggest_btn = st.button(
                        f"💡 Suggest new {_comp_studio} comp ideas",
                        type="primary", use_container_width=True, key="comp_suggest_btn"
                    )
                with _n_col:
                    _comp_n_ideas = st.number_input("# ideas", min_value=3, max_value=10, value=6, key="comp_n_ideas")

                if _suggest_btn:
                    _claude_key_c = os.environ.get("ANTHROPIC_API_KEY", "")
                    if not _claude_key_c:
                        st.error("ANTHROPIC_API_KEY not set.")
                    else:
                        with st.spinner(f"Researching existing {_comp_studio} comps + Grail catalogue…"):
                            _grail_for_suggest = _load_grail_cached(_comp_studio)
                            _exist_for_suggest = _load_existing_comps_cached(_comp_studio)
                        if _grail_for_suggest:
                            with st.spinner("Analysing gaps and generating ideas…"):
                                try:
                                    import comp_tools as _ct_sug
                                    _ideas = _ct_sug.suggest_comp_ideas(
                                        _comp_studio, _claude_key_c,
                                        n_ideas=int(_comp_n_ideas),
                                        grail_scenes=_grail_for_suggest,
                                        existing_comps=_exist_for_suggest,
                                    )
                                    st.session_state["comp_ideas"]        = _ideas
                                    st.session_state["comp_ideas_studio"] = _comp_studio
                                except Exception as _ie:
                                    st.error(f"Idea generation failed: {_ie}")

                # ── Show idea cards ────────────────────────────────────────────────────
                if "comp_ideas" in st.session_state and st.session_state.get("comp_ideas_studio") == _comp_studio:
                    _ideas = st.session_state["comp_ideas"]
                    st.markdown("<div class='sh'>💡 Suggested Ideas — click one to build it</div>",
                                unsafe_allow_html=True)

                    _idea_cols = st.columns(3)
                    for _ii, _idea in enumerate(_ideas):
                        with _idea_cols[_ii % 3]:
                            _avail = _idea.get("available_count", 0)
                            _vol   = _idea.get("vol", 1)
                            _vol_badge = f"Vol.{_vol}" if _vol > 1 else "New"
                            _vol_color = "#f59e0b" if _vol > 1 else "#22c55e"
                            st.markdown(
                                f"<div style='background:#111827;border:1px solid #1f2937;border-radius:8px;"
                                f"padding:12px 16px;margin-bottom:8px'>"
                                f"<div style='font-weight:700;font-size:0.82rem;color:#f3f4f6;margin-bottom:4px'>"
                                f"{_idea['title']}</div>"
                                f"<div style='font-size:0.68rem;color:#6b7280'>"
                                f"<span style='background:{_vol_color}20;color:{_vol_color};font-size:0.6rem;"
                                f"padding:1px 6px;border-radius:8px;margin-right:4px'>{_vol_badge}</span>"
                                f"~{_avail} scenes available</div>"
                                f"<div style='font-size:0.7rem;color:#9ca3af;margin-top:6px'>{_idea.get('rationale','')[:100]}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if st.button("Select →", key=f"comp_idea_{_ii}", use_container_width=True):
                                st.session_state["comp_theme_prefill"]    = _idea.get("theme", _idea["title"])
                                st.session_state["comp_cands_prefill"]    = _idea.get("candidate_ids", [])
                                st.session_state["comp_title_prefill"]    = _idea["title"]
                                st.session_state["comp_auto_build"]       = True
                                st.session_state.pop("comp_result", None)
                                st.rerun()

                    st.divider()

                # ── Step 2: Theme input (pre-filled if idea was selected) ─────────────
                _theme_default = st.session_state.pop("comp_theme_prefill", "")
                _cands_default = st.session_state.pop("comp_cands_prefill", [])
                _title_default = st.session_state.pop("comp_title_prefill", "")
                if _theme_default:
                    st.session_state["comp_theme"]        = _theme_default
                    st.session_state["comp_cands_hidden"]  = _cands_default
                    st.session_state["comp_title_default"] = _title_default

                st.markdown("<div class='sh'>🎬 BUILD SCENE LIST</div>", unsafe_allow_html=True)
                _cg1, _cg2 = st.columns([3, 1])
                with _cg1:
                    _comp_theme = st.text_input(
                        "Theme / category",
                        placeholder="e.g. Cowgirl, Creampie, Blonde, Blowjob…",
                        key="comp_theme"
                    )
                with _cg2:
                    _comp_n = st.number_input("# of scenes", min_value=5, max_value=15, value=8, key="comp_n")

                _cg_btn = st.button("✨ Build scene list", type="primary",
                                     use_container_width=True, key="comp_gen_btn")

                # Auto-build if user selected an idea card
                _auto_build = st.session_state.pop("comp_auto_build", False)
                if _cg_btn or _auto_build:
                    # On auto-build the widget may not have the prefilled value yet —
                    # fall back to session_state key set during prefill
                    _theme_to_use = _comp_theme.strip() or st.session_state.get("comp_theme", "").strip()
                    if not _theme_to_use:
                        st.error("Enter a theme first.")
                    else:
                        _claude_key_c = os.environ.get("ANTHROPIC_API_KEY", "")
                        if not _claude_key_c:
                            st.error("ANTHROPIC_API_KEY not set.")
                        else:
                            with st.spinner(f"Loading {_comp_studio} Grail data…"):
                                _grail_scenes = _load_grail_cached(_comp_studio)
                                _exist_scenes = _load_existing_comps_cached(_comp_studio)
                            if _grail_scenes:
                                with st.spinner(f"Selecting best {_comp_n} scenes for '{_theme_to_use}'…"):
                                    try:
                                        import comp_tools as _ct2
                                        _result = _ct2.generate_comp_with_ai(
                                            _comp_studio, _theme_to_use, int(_comp_n),
                                            _claude_key_c, _grail_scenes,
                                            existing_comps=_exist_scenes,
                                            preferred_ids=st.session_state.get("comp_cands_hidden", []),
                                        )
                                        if _title_def := st.session_state.get("comp_title_default"):
                                            _result["comp_title"] = _title_def
                                            st.session_state.pop("comp_title_default", None)
                                        st.session_state["comp_result"]        = _result
                                        st.session_state["comp_result_studio"] = _comp_studio
                                        st.session_state.pop("comp_cands_hidden", None)
                                    except Exception as _ce:
                                        st.error(f"Generation failed: {_ce}")

                # ── Show result ────────────────────────────────────────────────────────
                if "comp_result" in st.session_state:
                    _res = st.session_state["comp_result"]
                    _res_studio = st.session_state.get("comp_result_studio", _comp_studio)

                    st.divider()
                    _rt1, _rt2 = st.columns([4, 1])
                    with _rt1:
                        _comp_title_edit = st.text_input(
                            "Compilation title", value=_res.get("comp_title", ""),
                            key="comp_title_edit"
                        )
                    with _rt2:
                        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                        _comp_clear = st.button("✕ Clear", key="comp_clear")
                        if _comp_clear:
                            st.session_state.pop("comp_result", None)
                            st.rerun()

                    st.markdown(
                        f"<div class='sh'>📽 SCENE LIST"
                        f"<span style='background:{_cs_color}20;color:{_cs_color};font-size:0.6rem;"
                        f"padding:1px 8px;border-radius:8px;margin-left:8px;text-transform:none;"
                        f"letter-spacing:normal;font-weight:600'>{len(_res['scenes'])} scenes</span></div>",
                        unsafe_allow_html=True)

                    # Column headers
                    _ha, _hb, _hc, _hd = st.columns([1.5, 3, 2.5, 1])
                    _ha.markdown("<span style='font-size:0.65rem;color:#6b7280;font-weight:600'>GRAIL #</span>", unsafe_allow_html=True)
                    _hb.markdown("<span style='font-size:0.65rem;color:#6b7280;font-weight:600'>SCENE TITLE</span>", unsafe_allow_html=True)
                    _hc.markdown("<span style='font-size:0.65rem;color:#6b7280;font-weight:600'>PERFORMERS</span>", unsafe_allow_html=True)
                    _hd.markdown("", unsafe_allow_html=True)

                    # Editable scene table
                    _scene_rows = _res.get("scenes", [])
                    _edited_scenes = []
                    for _si, _sc in enumerate(_scene_rows):
                        _sa, _sb, _sc_col, _sd = st.columns([1.5, 3, 2.5, 1])
                        with _sa:
                            _gid = st.text_input("Grail #", value=_sc.get("grail_id",""),
                                                  key=f"comp_gid_{_si}", label_visibility="collapsed")
                        with _sb:
                            _title = st.text_input("Title", value=_sc.get("title",""),
                                                    key=f"comp_ttl_{_si}", label_visibility="collapsed")
                        with _sc_col:
                            _cast = st.text_input("Performers", value=_sc.get("cast",""),
                                                   key=f"comp_cast_{_si}", label_visibility="collapsed")
                        with _sd:
                            _remove = st.button("✕", key=f"comp_rm_{_si}")
                        if not _remove:
                            _edited_scenes.append({
                                "grail_id": _gid, "title": _title, "cast": _cast,
                                "slr_link": _sc.get("slr_link",""),
                            })

                    st.markdown("<div class='sh'>💾 ACTIONS</div>", unsafe_allow_html=True)

                    # Save buttons row
                    _sv1, _sv2 = st.columns(2)
                    with _sv1:
                        _save_sheet_btn = st.button("💾 Save to Planning Sheet", type="primary",
                                                     use_container_width=True, key="comp_save_sheet")
                    with _sv2:
                        _save_grail_btn = st.button("📋 Add to Grail Sheet", type="secondary",
                                                     use_container_width=True, key="comp_save_grail")

                    if _save_sheet_btn and _edited_scenes:
                        try:
                            import comp_tools as _ct3
                            _cell = _ct3.write_comp_to_sheet(
                                _res_studio, _comp_title_edit, _edited_scenes
                            )
                            st.success(f"✓ Written to {_res_studio} Compilations sheet starting at {_cell}")
                            st.markdown(
                                f"[Open planning sheet ↗](https://docs.google.com/spreadsheets/d/{_ct3.COMP_SHEET_ID}/edit)",
                                unsafe_allow_html=False
                            )
                        except Exception as _se:
                            st.error(f"Sheet write failed: {_se}")

                    if _save_grail_btn and _edited_scenes:
                        try:
                            import comp_tools as _ct4
                            # Enrich scenes with categories/tags from Grail data for the merge
                            _grail_map = {s["grail_id"]: s for s in _load_grail_cached(_res_studio)}
                            _enriched_for_grail = []
                            for _esc in _edited_scenes:
                                _full = _grail_map.get(_esc["grail_id"], {})
                                _enriched_for_grail.append({
                                    **_esc,
                                    "categories": _full.get("categories", ""),
                                    "tags":       _full.get("tags", ""),
                                })
                            _grail_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                            _grail_result = _ct4.write_comp_to_grail(
                                _res_studio, _comp_title_edit, _enriched_for_grail,
                                api_key=_grail_api_key,
                            )
                            _new_gid = _grail_result["grail_id"]
                            st.success(f"✓ Added to Grail as **{_new_gid}** (row {_grail_result['row_idx']})")
                            st.markdown(
                                f"<div style='display:inline-block;background:{_cs_color}18;border:1px solid {_cs_color}40;"
                                f"color:{_cs_color};font-size:0.75rem;font-weight:700;padding:2px 10px;"
                                f"border-radius:10px;margin:4px 0'>{_new_gid}</div>",
                                unsafe_allow_html=True
                            )
                            st.markdown(
                                f"[Open Grail sheet ↗](https://docs.google.com/spreadsheets/d/{_ct4.GRAIL_SHEET_ID}/edit)",
                                unsafe_allow_html=False
                            )
                            st.session_state["comp_last_grail_id"] = _new_gid
                        except Exception as _ge:
                            st.error(f"Grail write failed: {_ge}")

                    # Export for photoset builder (Mac script)
                    with st.expander("🖼 Build Photoset (Mac command)", expanded=False):
                        _scene_ids_str = ",".join(s["grail_id"] for s in _edited_scenes if s["grail_id"])
                        _comp_gid = st.session_state.get("comp_last_grail_id", "")
                        if not _comp_gid:
                            _comp_gid = f"{_res_studio}XXXX"
                        _mac_cmd = (
                            f"python3 ~/Scripts/comp_photoset.py "
                            f"--comp-id {_comp_gid} "
                            f"--scenes {_scene_ids_str} "
                            f"--output ~/Desktop/Compilations --zip"
                        )
                        st.code(_mac_cmd, language="bash")
                        if _comp_gid.endswith("XXXX"):
                            st.caption("Add to Grail first to get the real comp ID")

            # ── EXISTING COMPS PANEL ───────────────────────────────────────────────────
            with _cp_exist:
                @st.cache_data(ttl=1800, show_spinner=False)
                def _load_existing_rows(studio):
                    import gspread as _gs2
                    from google.oauth2.service_account import Credentials as _Creds2
                    _sa2 = os.path.join(os.path.dirname(__file__), "service_account.json")
                    _creds2 = _Creds2.from_service_account_file(
                        _sa2, scopes=["https://www.googleapis.com/auth/spreadsheets"])
                    _gc2 = _gs2.authorize(_creds2)
                    _sh2 = _gc2.open_by_key("1i6W4eZ8Bva3HvVmhpAVgjeHwfqbARkwBZ38aUhriaGs")
                    _tab_map = {"FPVR": "FPVR Compilations", "VRH": "VRH Compilations", "VRA": "VRA Compilations"}
                    _ws2 = _sh2.worksheet(_tab_map[studio])
                    return _ws2.get_all_values()

                # Auto-load existing comps
                _ex_needs_load = (
                    "comp_existing" not in st.session_state
                    or st.session_state.get("comp_existing_studio") != _comp_studio
                )
                if _ex_needs_load:
                    try:
                        with st.spinner(f"Loading {_comp_studio} compilations…"):
                            st.session_state["comp_existing"] = _load_existing_rows(_comp_studio)
                            st.session_state["comp_existing_studio"] = _comp_studio
                    except Exception as _ee:
                        st.error(f"Could not load sheet: {_ee}")

                _load_exist = st.button("🔄 Refresh", key="comp_load_exist", use_container_width=False)
                if _load_exist:
                    try:
                        _load_existing_rows.clear()
                        st.session_state["comp_existing"] = _load_existing_rows(_comp_studio)
                        st.session_state["comp_existing_studio"] = _comp_studio
                    except Exception as _ee:
                        st.error(f"Could not load sheet: {_ee}")

                if True:

                    _rows2 = st.session_state.get("comp_existing", [])
                    _ex_studio = st.session_state.get("comp_existing_studio", _comp_studio)

                    if _rows2:
                        # Parse: find header row (row index 1), identify comp groups
                        _hdr = _rows2[1] if len(_rows2) > 1 else []
                        # Each group: find columns where row[1] has a comp title
                        _groups = []
                        _ci2 = 0
                        while _ci2 < len(_hdr):
                            if _hdr[_ci2].strip() and _hdr[_ci2].strip() not in ("Link to Scene", "Scene Title", "Performers", "SLR Link", "MEGA Path", "Grail #"):
                                _gname = _hdr[_ci2].strip()
                                _gcol  = _ci2
                                # Collect scene entries for this group
                                _gscenes = []
                                for _row3 in _rows2[2:]:
                                    _cell_val = _row3[_gcol].strip() if _gcol < len(_row3) else ""
                                    if _cell_val:
                                        _link_val = _row3[_gcol + 1].strip() if _gcol + 1 < len(_row3) else ""
                                        _gscenes.append({"scene": _cell_val, "link": _link_val})
                                _groups.append({"title": _gname, "scenes": _gscenes, "col": _gcol})
                            _ci2 += 1

                        if not _groups:
                            st.info("No compilations found in this tab.")
                        else:
                            _sel_comp = st.selectbox(
                                "Select compilation",
                                [g["title"] for g in _groups],
                                key="comp_exist_sel"
                            )
                            _sel_group = next((g for g in _groups if g["title"] == _sel_comp), None)
                            if _sel_group:
                                _gscenes = _sel_group["scenes"]
                                st.markdown(f"**{len(_gscenes)} scenes** — enriching with Grail IDs…")

                                # Try to look up Grail IDs for each scene
                                with st.spinner("Looking up Grail IDs…"):
                                    try:
                                        import comp_tools as _ct4
                                        _grail_s2 = _load_grail_cached(_ex_studio)
                                        _enriched2 = []
                                        for _sc2 in _gscenes:
                                            _match = _ct4.find_grail_id(_sc2["scene"], _grail_s2)
                                            _enriched2.append({
                                                "scene":    _sc2["scene"],
                                                "grail_id": _match["grail_id"] if _match else "—",
                                                "cast":     _match["cast"] if _match else "",
                                                "link":     _sc2["link"],
                                                "mega":     _ct4.mega_path(_match["grail_id"]) if _match else "",
                                            })
                                    except Exception:
                                        _enriched2 = [{"scene": s["scene"], "grail_id":"—", "cast":"", "link": s["link"], "mega":""} for s in _gscenes]

                                # Display enriched table
                                for _e2 in _enriched2:
                                    _ea, _eb, _ec, _ed = st.columns([1.5, 3, 2.5, 2])
                                    with _ea:
                                        st.markdown(f"`{_e2['grail_id']}`")
                                    with _eb:
                                        st.markdown(_e2["scene"])
                                    with _ec:
                                        st.caption(_e2["cast"])
                                    with _ed:
                                        if _e2["mega"]:
                                            st.caption(_e2["mega"])

                                # Export photoset command
                                st.divider()
                                _ids_ex = ",".join(e["grail_id"] for e in _enriched2 if e["grail_id"] != "—")
                                if _ids_ex:
                                    st.markdown("<div class='sh'>🖼 PHOTOSET BUILDER</div>", unsafe_allow_html=True)
                                    st.code(
                                        f"python3 ~/Scripts/comp_photoset.py "
                                        f"--comp-id {_ex_studio}XXXX "
                                        f"--scenes {_ids_ex} "
                                        f"--output ~/Desktop/Compilations --zip",
                                        language="bash"
                                    )
                                    st.caption("Replace XXXX with the actual Grail ID after adding to Grail")

        _comp_fragment()

    # ── TAB 8: Tickets ────────────────────────────────────────────────────────────
with tab_tickets:
    if _has_tab("Tickets"):
        import ticket_tools as _tkt

        # ── View toggle ──────────────────────────────────────────────────────────
        _tk_mode = st.segmented_control(
            "", ["📝 Submit a Ticket", "📋 All Tickets"],
            default="📋 All Tickets", key="tk_mode", label_visibility="collapsed",
        )

        # ── Submit view ──────────────────────────────────────────────────────────
        if _tk_mode == "📝 Submit a Ticket":
            st.subheader("Submit a New Ticket")
            with st.form("ticket_submit_form", clear_on_submit=True):
                _tk_c1, _tk_c2 = st.columns(2)
                with _tk_c1:
                    _tk_emp_idx = _tkt.EMPLOYEES.index(_user_name) if _user_name in _tkt.EMPLOYEES else 0
                    _tk_who = st.selectbox("Submitted By", _tkt.EMPLOYEES, index=_tk_emp_idx, key="tk_who")
                    _tk_project = st.selectbox("Project", _tkt.PROJECTS, key="tk_project")
                with _tk_c2:
                    _tk_type = st.selectbox("Type", _tkt.TICKET_TYPES, key="tk_type")
                    _tk_priority = st.selectbox("Priority", _tkt.PRIORITIES,
                                                index=1, key="tk_priority")
                _tk_title = st.text_input("Title", placeholder="Short summary of the issue or request",
                                          key="tk_title")
                _tk_desc = st.text_area("Description",
                                        placeholder="Detailed description — steps to reproduce, expected behavior, screenshots, etc.",
                                        height=200, key="tk_desc")
                _tk_submit = st.form_submit_button("🎟️ Submit Ticket", use_container_width=True)

            if _tk_submit:
                if not _tk_title.strip():
                    st.error("Title is required.")
                elif not _tk_desc.strip():
                    st.error("Description is required.")
                else:
                    with st.spinner("Submitting ticket..."):
                        try:
                            _new_id = _tkt.create_ticket(
                                _tk_who, _tk_project, _tk_type, _tk_priority,
                                _tk_title.strip(), _tk_desc.strip(),
                            )
                            st.success(f"Ticket **{_new_id}** submitted successfully!")
                            st.session_state.pop("tickets_cache", None)
                        except Exception as _e:
                            st.error(f"Failed to submit ticket: {_e}")

        # ── Dashboard view ───────────────────────────────────────────────────────
        else:
            st.subheader("Ticket Dashboard")

            # Filters row
            _tf1, _tf2, _tf3, _tf4 = st.columns([2, 2, 2, 1])
            with _tf1:
                _filt_status = st.selectbox("Status", ["All"] + _tkt.STATUSES, key="tk_filt_status")
            with _tf2:
                _filt_project = st.selectbox("Project", ["All"] + _tkt.PROJECTS, key="tk_filt_project")
            with _tf3:
                _filt_priority = st.selectbox("Priority", ["All"] + _tkt.PRIORITIES, key="tk_filt_priority")
            with _tf4:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔄 Refresh", key="tk_refresh", use_container_width=True):
                    st.session_state.pop("tickets_cache", None)
                    st.session_state.pop("tickets_cache_ts", None)
                    st.rerun()

            # Load tickets (cached 60s)
            _tk_cache_key = "tickets_cache"
            _tk_ts_key = "tickets_cache_ts"
            if (_tk_cache_key not in st.session_state
                    or time.time() - st.session_state.get(_tk_ts_key, 0) > 60):
                with st.spinner("Loading tickets..."):
                    try:
                        st.session_state[_tk_cache_key] = _tkt.load_tickets()
                        st.session_state[_tk_ts_key] = time.time()
                    except Exception as _e:
                        st.error(f"Failed to load tickets: {_e}")
                        st.session_state[_tk_cache_key] = []

            _all_tickets = st.session_state.get(_tk_cache_key, [])

            # Apply filters
            _filtered = _all_tickets
            if _filt_status != "All":
                _filtered = [t for t in _filtered if t["status"] == _filt_status]
            if _filt_project != "All":
                _filtered = [t for t in _filtered if t["project"] == _filt_project]
            if _filt_priority != "All":
                _filtered = [t for t in _filtered if t["priority"] == _filt_priority]

            # Summary stats
            _sc1, _sc2, _sc3, _sc4, _sc5 = st.columns(5)
            _status_counts = {}
            for _t in _all_tickets:
                _status_counts[_t["status"]] = _status_counts.get(_t["status"], 0) + 1
            _sc1.metric("🆕 New", _status_counts.get("New", 0))
            _sc2.metric("✅ Approved", _status_counts.get("Approved", 0))
            _sc3.metric("🔧 In Progress", _status_counts.get("In Progress", 0))
            _sc4.metric("🚀 Deployed", _status_counts.get("Deployed", 0))
            _sc5.metric("❌ Rejected", _status_counts.get("Rejected", 0))

            st.divider()

            if not _filtered:
                st.info("No tickets found matching your filters.")
            else:
                # Show tickets newest first
                for _ticket in reversed(_filtered):
                    _pri_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(
                        _ticket["priority"], "⚪"
                    )
                    _status_emoji = {
                        "New": "🆕", "Approved": "✅", "In Progress": "🔧",
                        "Deployed": "🚀", "Rejected": "❌",
                    }.get(_ticket["status"], "")

                    _exp_label = (
                        f"{_pri_emoji} **{_ticket['id']}** — {_ticket['title']}  "
                        f"| {_status_emoji} {_ticket['status']}  "
                        f"| {_ticket['project']}  "
                        f"| by {_ticket['submitted_by']}  "
                        f"| {_ticket['date']}"
                    )
                    with st.expander(_exp_label, expanded=(_ticket["status"] == "New")):
                        # Ticket details
                        _dc1, _dc2, _dc3, _dc4 = st.columns(4)
                        _dc1.markdown(f"**Type:** {_ticket['type']}")
                        _dc2.markdown(f"**Priority:** {_pri_emoji} {_ticket['priority']}")
                        _dc3.markdown(f"**Project:** {_ticket['project']}")
                        _dc4.markdown(f"**Submitted:** {_ticket['date']}")

                        st.markdown("**Description:**")
                        st.text(_ticket["description"])

                        if _ticket["admin_notes"]:
                            st.markdown(f"**Admin Notes:** {_ticket['admin_notes']}")
                        if _ticket["date_resolved"]:
                            st.markdown(f"**Resolved:** {_ticket['date_resolved']}")

                        # Admin actions (only visible to admins)
                        if _user_is_admin:
                            st.markdown("---")
                            st.caption("Admin Actions")
                            _ac1, _ac2 = st.columns([1, 2])
                            with _ac1:
                                _new_status = st.selectbox(
                                    "Update Status",
                                    _tkt.STATUSES,
                                    index=_tkt.STATUSES.index(_ticket["status"])
                                    if _ticket["status"] in _tkt.STATUSES else 0,
                                    key=f"tk_st_{_ticket['row_index']}",
                                )
                            with _ac2:
                                _new_notes = st.text_input(
                                    "Admin Notes",
                                    value=_ticket["admin_notes"],
                                    key=f"tk_notes_{_ticket['row_index']}",
                                )
                            if st.button("💾 Update Ticket", key=f"tk_update_{_ticket['row_index']}",
                                         use_container_width=True):
                                with st.spinner("Updating..."):
                                    try:
                                        _tkt.update_ticket(
                                            _ticket["row_index"],
                                            status=_new_status,
                                            approved_by=_user_name if _new_status in ("Approved", "Rejected") else None,
                                            admin_notes=_new_notes if _new_notes != _ticket["admin_notes"] else None,
                                        )
                                        st.success(f"Ticket {_ticket['id']} updated to **{_new_status}**")
                                        st.session_state.pop("tickets_cache", None)
                                        st.session_state.pop("tickets_cache_ts", None)
                                    except Exception as _e:
                                        st.error(f"Failed to update: {_e}")
