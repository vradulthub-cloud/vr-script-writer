"""
cloud_renderer.py — Cloud-based title card rendering via fal.ai Ideogram V3.

Pipeline:
  1. Ideogram V3 DESIGN mode generates styled text with accurate spelling
  2. Unmult background removal → transparent RGBA PNG
  3. Results cached to disk by (title, style, seed)

Requires: FAL_KEY environment variable set to your fal.ai API key.
Install:  pip install fal-client
"""

import os, io, hashlib, random, time, base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

FAL_KEY    = os.environ.get("FAL_KEY", "")
CACHE_DIR  = Path(r"C:\Users\andre\script-writer\cloud_cache")
CACHE_DIR.mkdir(exist_ok=True)
_CACHE_VER = "v17"   # ideogram v3, tuned unmult

# ── Style library ─────────────────────────────────────────────────────────────
# Each entry: (style_prompt, negative_prompt, color_palette)
# color_palette: list of {"r": int, "g": int, "b": int} dicts for Ideogram V3
CLOUD_STYLES = {
    "chrome_luxury": (
        "highly polished mirror chrome finish, deep metallic reflections, "
        "sharp specular highlights, studio lighting, ultra detailed",
        "blurry, low quality",
        [{"r": 200, "g": 200, "b": 210}, {"r": 120, "g": 120, "b": 126}, {"r": 0, "g": 0, "b": 0}],
    ),
    "gold_embossed": (
        "24-karat gold embossed finish, deep rich gold texture, ornate beveled edges, "
        "dramatic lighting, luxury brand aesthetic",
        "blurry, silver, cheap",
        [{"r": 212, "g": 175, "b": 55}, {"r": 180, "g": 140, "b": 28}, {"r": 0, "g": 0, "b": 0}],
    ),
    "neon_glow": (
        "vibrant neon sign effect, glowing electric neon tubes, colorful light halos, "
        "cyan and magenta colors, cinematic lighting",
        "blurry, daylight",
        [{"r": 0, "g": 255, "b": 255}, {"r": 255, "g": 0, "b": 200}, {"r": 0, "g": 0, "b": 0}],
    ),
    "fire_inferno": (
        "blazing fire effect, engulfed in realistic flames, orange yellow white hot core, "
        "embers and sparks, dramatic lighting",
        "blurry, cartoon, anime",
        [{"r": 255, "g": 120, "b": 0}, {"r": 255, "g": 200, "b": 50}, {"r": 0, "g": 0, "b": 0}],
    ),
    "ice_frozen": (
        "frozen crystalline ice effect, blue-white ice with light refraction, "
        "frost fractures, condensation droplets",
        "blurry, warm, fire",
        [{"r": 180, "g": 220, "b": 255}, {"r": 100, "g": 180, "b": 240}, {"r": 0, "g": 0, "b": 0}],
    ),
    "holographic": (
        "holographic iridescent finish, rainbow spectrum color shift, chrome foil surface, "
        "prismatic light diffraction, futuristic aesthetic",
        "blurry, matte, flat",
        [{"r": 200, "g": 100, "b": 255}, {"r": 100, "g": 255, "b": 200}, {"r": 0, "g": 0, "b": 0}],
    ),
    "neon_retro_80s": (
        "1980s retro synthwave neon style, hot pink and electric blue gradients, "
        "chrome depth, retrowave aesthetic",
        "blurry, modern",
        [{"r": 255, "g": 50, "b": 150}, {"r": 50, "g": 150, "b": 255}, {"r": 0, "g": 0, "b": 0}],
    ),
    "diamond_gem": (
        "diamond and gemstone finish, cut faceted diamonds, "
        "brilliant sparkle caustics, deep blue sapphire accents",
        "blurry, matte, cheap",
        [{"r": 200, "g": 220, "b": 255}, {"r": 50, "g": 80, "b": 200}, {"r": 0, "g": 0, "b": 0}],
    ),
    "lava_molten": (
        "molten lava effect, glowing magma flowing through cracked dark rock, "
        "orange-red incandescent glow, volcanic texture",
        "blurry, cool tones, ice",
        [{"r": 255, "g": 80, "b": 0}, {"r": 200, "g": 40, "b": 0}, {"r": 0, "g": 0, "b": 0}],
    ),
    "galaxy_cosmic": (
        "cosmic galaxy effect, filled with deep space nebula, swirling stars and stardust, "
        "purple-blue tones, glowing edge light",
        "blurry, earthly, daytime",
        [{"r": 100, "g": 50, "b": 200}, {"r": 50, "g": 100, "b": 255}, {"r": 0, "g": 0, "b": 0}],
    ),
    "rose_gold_glam": (
        "rose gold metallic finish, warm pink-gold metal, luxury fashion aesthetic, "
        "subtle glitter, high fashion",
        "blurry, cheap, silver",
        [{"r": 230, "g": 170, "b": 150}, {"r": 200, "g": 140, "b": 120}, {"r": 0, "g": 0, "b": 0}],
    ),
    "grunge_metal": (
        "heavy metal grunge style, brushed steel with rust patina, battle-worn texture, "
        "industrial rivets and scratches, harsh lighting",
        "blurry, clean, glossy",
        [{"r": 150, "g": 140, "b": 130}, {"r": 180, "g": 100, "b": 50}, {"r": 0, "g": 0, "b": 0}],
    ),
    "electric_plasma": (
        "electric plasma energy effect, crackling lightning, "
        "blue-white electrical discharge, Tesla coil effect",
        "blurry, calm, soft",
        [{"r": 100, "g": 150, "b": 255}, {"r": 200, "g": 220, "b": 255}, {"r": 0, "g": 0, "b": 0}],
    ),
    "velvet_luxury": (
        "deep velvet texture, rich burgundy and purple velvet, "
        "subtle gold border, dramatic side lighting, fashion editorial",
        "blurry, cheap, plastic",
        [{"r": 120, "g": 20, "b": 60}, {"r": 80, "g": 10, "b": 80}, {"r": 0, "g": 0, "b": 0}],
    ),
    "toxic_slime": (
        "toxic slime drip effect, bright radioactive green glow, viscous dripping slime, "
        "bio-hazard aesthetic, neon green backlight",
        "blurry, clean, dry",
        [{"r": 0, "g": 255, "b": 50}, {"r": 100, "g": 255, "b": 0}, {"r": 0, "g": 0, "b": 0}],
    ),
    "marble_carved": (
        "white Carrara marble carved in deep relief, subtle gray veining, "
        "museum lighting, classical sculpture aesthetic",
        "blurry, dark, colorful",
        [{"r": 240, "g": 235, "b": 230}, {"r": 180, "g": 175, "b": 170}, {"r": 0, "g": 0, "b": 0}],
    ),
    "cyberpunk_holo": (
        "cyberpunk hologram effect, glitching digital distortion, cyan and red chromatic aberration, "
        "scanlines, translucent holographic projection",
        "blurry, analog, natural",
        [{"r": 0, "g": 255, "b": 255}, {"r": 255, "g": 50, "b": 50}, {"r": 0, "g": 0, "b": 0}],
    ),
    "bronze_ancient": (
        "ancient bronze patina finish, verdigris oxidation, archaeological artifact aesthetic, "
        "textured surface with age marks, deep relief",
        "blurry, modern, clean",
        [{"r": 140, "g": 120, "b": 80}, {"r": 80, "g": 140, "b": 100}, {"r": 0, "g": 0, "b": 0}],
    ),
    "candy_glossy": (
        "candy gloss finish, bright saturated colors, highly polished glossy surface, "
        "specular white highlights, playful fun aesthetic",
        "blurry, dark, matte",
        [{"r": 255, "g": 100, "b": 150}, {"r": 100, "g": 200, "b": 255}, {"r": 0, "g": 0, "b": 0}],
    ),
    "obsidian_dark": (
        "obsidian volcanic glass finish, jet black with deep purple-blue inner glow, "
        "sharp reflective edges, mystical dark aesthetic",
        "blurry, bright, colorful",
        [{"r": 30, "g": 10, "b": 50}, {"r": 80, "g": 40, "b": 120}, {"r": 0, "g": 0, "b": 0}],
    ),
}

# ── Core rendering ─────────────────────────────────────────────────────────────

def _make_text_mask(title: str, width: int = 1200, height: int = 300) -> Image.Image:
    """Render title as white text on black for img2img conditioning."""
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = 180
    font = None
    font_paths = [
        r"C:\Windows\Fonts\Arial.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\Impact.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    for size in range(180, 40, -8):
        try:
            f = ImageFont.truetype(font_paths[0] if os.path.exists(font_paths[0]) else font_paths[-1], size)
            bbox = draw.textbbox((0, 0), title.upper(), font=f)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            if tw < width - 60 and th < height - 40:
                font = f
                break
        except Exception:
            pass

    bbox = draw.textbbox((0, 0), title.upper(), font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2 - bbox[0]
    y = (height - th) // 2 - bbox[1]
    draw.text((x, y), title.upper(), fill=(255, 255, 255), font=font)
    return img


def _pil_to_b64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def _remove_background(img_bytes: bytes, title: str = "") -> bytes:
    """Remove black/dark background → transparent PNG using Unmult (screen blend).
    alpha = max(R,G,B), then RGB_out = RGB / alpha to recover premultiplied colors."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.float64) / 255.0
    h, w = arr.shape[:2]

    # Detect actual background level from corners
    s = max(20, min(40, h // 10, w // 10))
    brightness = np.max(arr, axis=2)
    corners = np.concatenate([
        brightness[:s, :s].ravel(), brightness[:s, -s:].ravel(),
        brightness[-s:, :s].ravel(), brightness[-s:, -s:].ravel(),
    ])
    # Use a low percentile — we want the true black floor, not midtones
    bg_level = float(np.percentile(corners, 30))

    # Thin dead zone: only kill pixels very close to the background
    floor = bg_level + 0.01
    alpha = np.clip((brightness - floor) / max(1.0 - floor, 0.01), 0, 1)

    # Per-channel background (low percentile of corners)
    bg_color = np.zeros(3)
    for c in range(3):
        ch_corners = np.concatenate([
            arr[:s, :s, c].ravel(), arr[:s, -s:, c].ravel(),
            arr[-s:, :s, c].ravel(), arr[-s:, -s:, c].ravel(),
        ])
        bg_color[c] = float(np.percentile(ch_corners, 30))

    # Subtract bg color but preserve the original RGB intensity
    adjusted = np.clip(arr - bg_color[np.newaxis, np.newaxis, :], 0, 1)
    safe_alpha = np.where(alpha > 0.01, alpha, 1.0)
    rgb_out = np.clip(adjusted / safe_alpha[:, :, np.newaxis], 0, 1)

    alpha_u8 = (alpha * 255).astype(np.uint8)
    rgb_u8 = (rgb_out * 255).astype(np.uint8)
    rgba = np.dstack([rgb_u8, alpha_u8])

    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return buf.getvalue()


def render_cloud(title: str, style_key: str, seed: int = 0) -> bytes | None:
    """
    Render title using fal.ai Ideogram V3 DESIGN mode.
    Returns transparent PNG bytes or None on failure.
    """
    import fal_client, requests as _req

    fal_key = os.environ.get("FAL_KEY", FAL_KEY)
    if not fal_key:
        raise RuntimeError("FAL_KEY environment variable not set")
    os.environ["FAL_KEY"] = fal_key

    if style_key not in CLOUD_STYLES:
        style_key = random.choice(list(CLOUD_STYLES.keys()))

    style_prompt, negative_prompt, color_palette = CLOUD_STYLES[style_key]

    # Check cache
    cache_key = hashlib.md5(f"{_CACHE_VER}|{title}|{style_key}|{seed}".encode()).hexdigest()
    cache_path = CACHE_DIR / f"{cache_key}.png"
    if cache_path.exists():
        return cache_path.read_bytes()

    # Simple, direct prompt — no negative phrasing in the main prompt
    prompt = (
        f'Bold 3D text reading "{title}" with {style_prompt}, '
        f'centered on solid black background'
    )

    result = fal_client.run(
        "fal-ai/ideogram/v3",
        arguments={
            "prompt": prompt,
            "negative_prompt": negative_prompt + ", misspelled, wrong text, extra letters, "
                "scene, room, landscape, floor, ground, grid, furniture, people, objects, decorations",
            "style": "DESIGN",
            "image_size": "landscape_16_9",
            "rendering_speed": "TURBO",
            "expand_prompt": False,
            "seed": seed if seed > 0 else random.randint(1, 99999),
            "color_palette": {"members": [{"rgb": c, "color_weight": 0.5} for c in color_palette]},
        }
    )

    image_url = result["images"][0]["url"]
    r = _req.get(image_url, timeout=30)
    if r.status_code != 200:
        return None

    # Unmult: remove black background → transparent PNG
    transparent = _remove_background(r.content, title=title)
    cache_path.write_bytes(transparent)
    return transparent


def render_cloud_batch(title: str, style_keys: list, seed: int = 0) -> list:
    """Render multiple styles. Returns list of (style_key, png_bytes) tuples."""
    import concurrent.futures
    results = []

    def _render_one(sk):
        png = render_cloud(title, sk, seed=seed)
        return (sk, png)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_render_one, sk): sk for sk in style_keys}
        for f in concurrent.futures.as_completed(futures):
            sk, png = f.result()
            if png:
                results.append((sk, png))

    return results
