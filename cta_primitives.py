#!/usr/bin/env python3
"""CTA Drawing primitives, color palettes, and utility functions."""

import os, sys, re, math, random, colorsys, hashlib
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
except ImportError:
    os.system(f"{sys.executable} -m pip install pillow numpy --break-system-packages -q")
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np

from cta_fonts import F, FONT_CACHE, _resolve_fonts


# ── Layout engine ─────────────────────────────────────────────────────────────
# Pillow ships with two text layout engines: BASIC (legacy, no kerning, no
# ligatures, no OpenType features) and RAQM (HarfBuzz + FriBidi — proper
# shaping, kerning, ligatures, RTL/CTL scripts, OT features). RAQM requires
# libraqm to be available at Pillow build/install time. On systems where it
# isn't, we silently fall back to BASIC so nothing breaks.
#
# Default Pillow uses BASIC unless told otherwise — that's why default text
# rendering looks slightly cheap (no real kerning). Using LAYOUT_ENGINE
# everywhere lifts every existing treatment to professional letterspacing
# for free.
try:
    if hasattr(ImageFont, "Layout") and hasattr(ImageFont.Layout, "RAQM"):
        _test_path = None
        for _p in [
            FONT_CACHE / "PlayfairDisplay-Bold.ttf",
            FONT_CACHE / "Anton-Regular.ttf",
            FONT_CACHE / "Cinzel-Bold.ttf",
        ]:
            if Path(_p).exists():
                _test_path = str(_p)
                break
        if _test_path is None:
            LAYOUT_ENGINE = ImageFont.Layout.BASIC
        else:
            try:
                ImageFont.truetype(_test_path, 24, layout_engine=ImageFont.Layout.RAQM)
                LAYOUT_ENGINE = ImageFont.Layout.RAQM
            except (OSError, ValueError):
                LAYOUT_ENGINE = ImageFont.Layout.BASIC
    else:
        LAYOUT_ENGINE = 0  # BASIC literal for older Pillow
except Exception:
    LAYOUT_ENGINE = 0


# ── Colour palettes ───────────────────────────────────────────────────────────

VIVID_BANKS = [
    [(255,60,60),  (255,180,0),  (0,210,80),   (0,160,255), (200,60,255)],
    [(255,80,140), (255,160,0),  (80,220,220),  (120,80,255),(80,220,80)],
    [(255,120,0),  (0,200,255),  (240,60,120),  (80,255,120),(255,220,0)],
    [(180,60,255), (0,240,200),  (255,60,80),   (255,200,0), (80,180,255)],
]

FACE_GRADIENTS = {
    "fire":     [(255,255,200),(255,200,40),(255,80,0),(160,20,0)],
    "ice":      [(255,255,255),(190,230,255),(120,190,255),(50,120,220)],
    "gold":     [(255,250,180),(255,215,0),(200,160,20),(140,100,0)],
    "silver":   [(255,255,255),(220,225,235),(170,175,190),(100,110,130)],
    "rose":     [(255,220,230),(255,140,170),(220,60,100),(140,20,60)],
    "violet":   [(240,200,255),(200,130,255),(150,60,220),(80,0,160)],
    "cyan":     [(200,255,255),(80,230,240),(0,180,220),(0,100,180)],
    "lime":     [(220,255,180),(160,240,80),(80,200,0),(30,130,0)],
    "cream":    [(255,250,230),(245,230,180),(210,190,120)],
    "coral":    [(255,200,160),(255,120,70),(200,50,20)],
    "pink":     [(255,230,240),(255,170,200),(230,80,140),(160,20,80)],
    "amber":    [(255,250,200),(255,210,60),(220,140,0),(150,80,0)],
    "teal":     [(200,255,240),(60,220,200),(0,160,160),(0,90,110)],
    "sunset":   [(255,230,160),(255,140,60),(220,60,80),(120,20,60)],
}

STROKE_COLORS = {
    "fire":   (70,15,0),  "ice":    (0,50,130),  "gold":   (80,50,0),
    "silver": (30,35,50), "rose":   (100,0,40),  "violet": (40,0,100),
    "cyan":   (0,40,100), "lime":   (20,80,0),   "cream":  (80,60,10),
    "coral":  (100,20,0), "pink":   (110,0,50),  "amber":  (90,50,0),
    "teal":   (0,50,70),  "sunset": (100,20,30),
}

EXTRUDE_COLORS = {
    "fire":   (110,25,0),  "ice":    (0,40,110),  "gold":   (110,70,0),
    "silver": (50,55,70),  "rose":   (130,0,55),  "violet": (55,0,120),
    "cyan":   (0,55,120),  "lime":   (25,100,0),  "cream":  (100,75,15),
    "coral":  (120,30,0),  "pink":   (130,0,60),  "amber":  (110,60,0),
    "teal":   (0,65,85),   "sunset": (120,25,35),
}

# Chrome-specific gradient: specular → dark reflection → ground reflection
CHROME_STOPS = [
    (255,255,255),  # top: bright specular
    (230,235,245),  # upper silver
    (170,180,200),  # mid silver
    (40,45,58),     # deep dark reflection
    (85,95,115),    # mid-dark
    (195,210,228),  # lower silver
    (255,255,255),  # bottom: ground reflection
]

# Liquid gold: molten amber pour
LIQUID_GOLD_STOPS = [
    (255,252,200),  # bright top highlight
    (255,210,40),   # warm gold
    (220,150,0),    # deep amber
    (160,90,0),     # dark burnt
    (200,130,10),   # mid recovery
    (255,200,50),   # lower highlight
    (255,240,140),  # bottom glint
]

# Vintage: warm sepia/cream aged look
VINTAGE_STOPS = [
    (255,248,220),  # antique white top
    (240,220,160),  # warm parchment
    (200,170,90),   # aged amber
    (150,110,50),   # dark sepia
    (190,155,80),   # mid sepia
    (235,205,130),  # warm recovery
]

# Neon box colors: pairs of (box_color, glow_color)
NEON_BOX_PALETTES = [
    ((255,20,147),  (255,100,180)),   # hot pink
    ((0,255,220),   (80,255,240)),    # cyan
    ((255,100,0),   (255,180,60)),    # orange
    ((140,0,255),   (200,80,255)),    # violet
    ((0,200,80),    (80,255,140)),    # green
    ((255,230,0),   (255,245,100)),   # yellow
]

def title_seed(t: str) -> int:
    return int(hashlib.md5(t.encode()).hexdigest(), 16) % (2**31)

# ── Drawing primitives ────────────────────────────────────────────────────────

def measure(d: ImageDraw.Draw, text: str, font) -> tuple:
    bb = d.textbbox((0,0), text, font=font)
    return bb[2]-bb[0], bb[3]-bb[1], bb[1]

def make_mask(text: str, font, pad: int = 80, max_width: int = 3600,
              supersample: int = 2) -> Image.Image:
    """Render text as a greyscale alpha mask.
    - pad=80 gives glow/shadow effects room to breathe without clipping.
    - max_width auto-scales the font down if text would exceed that pixel width.
    - supersample (default 2) renders at NxN, then downsamples with LANCZOS for
      sub-pixel-smooth alpha edges. Set to 1 to disable for testing/perf.
    """
    dummy = ImageDraw.Draw(Image.new("L", (10000, 3000), 0))
    w, h, top = measure(dummy, text, font)
    # Auto-shrink oversized text so nothing clips horizontally
    if w > max_width:
        try:
            scale    = max_width / w
            new_size = max(60, int(font.size * scale))
            font     = ImageFont.truetype(font.path, new_size)
            w, h, top = measure(dummy, text, font)
        except Exception:
            pass
    if supersample > 1:
        try:
            big_font = ImageFont.truetype(font.path, font.size * supersample, layout_engine=LAYOUT_ENGINE)
            big_w, big_h, big_top = measure(dummy, text, big_font)
            big_pad = pad * supersample
            big = Image.new("L", (big_w + big_pad * 2, big_h + big_pad * 2), 0)
            ImageDraw.Draw(big).text((big_pad, big_pad - big_top), text, fill=255, font=big_font)
            return big.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)
        except Exception:
            pass  # fall through to native-resolution path
    img = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    ImageDraw.Draw(img).text((pad, pad - top), text, fill=255, font=font)
    return img

def auto_size(title: str, base: int = 280, pivot: int = 14) -> int:
    """Scale font size down gracefully for long titles."""
    n = len(title)
    if n <= pivot:
        return base
    return max(80, int(base * pivot / n))


def auto_size_hd(title: str, base: int = 420, pivot: int = 14) -> int:
    """HD variant — 3x resolution for 4K-ready title cards."""
    n = len(title)
    if n <= pivot:
        return base
    return max(120, int(base * pivot / n))

def make_mask_hd(text: str, font, pad: int = 100, max_width: int = 3840,
                 supersample: int = 2) -> Image.Image:
    """HD mask — larger canvas, more padding for effects at 4K resolution.
    supersample=2 by default for crisp 4K edges on transparent backgrounds.
    """
    dummy = ImageDraw.Draw(Image.new("L", (12000, 4000), 0))
    w, h, top = measure(dummy, text, font)
    if w > max_width:
        try:
            scale = max_width / w
            new_size = max(80, int(font.size * scale))
            font = ImageFont.truetype(font.path, new_size, layout_engine=LAYOUT_ENGINE)
            w, h, top = measure(dummy, text, font)
        except Exception:
            pass
    if supersample > 1:
        try:
            big_font = ImageFont.truetype(font.path, font.size * supersample, layout_engine=LAYOUT_ENGINE)
            big_w, big_h, big_top = measure(dummy, text, big_font)
            big_pad = pad * supersample
            big = Image.new("L", (big_w + big_pad * 2, big_h + big_pad * 2), 0)
            ImageDraw.Draw(big).text((big_pad, big_pad - big_top), text, fill=255, font=big_font)
            return big.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)
        except Exception:
            pass
    img = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    ImageDraw.Draw(img).text((pad, pad - top), text, fill=255, font=font)
    return img


# ── Blend mode helpers (RGBA-aware, float32 internal) ─────────────────────────

def _to_f32(img: Image.Image) -> np.ndarray:
    """RGBA -> float32 in [0,1]."""
    return np.array(img.convert("RGBA"), dtype=np.float32) / 255.0

def _to_rgba(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGBA")

def screen_blend(base: Image.Image, top: Image.Image) -> Image.Image:
    """Screen blend (1 - (1-a)(1-b)) on RGB, alpha = max(base.a, top.a).
    Use for additive light effects — glows, highlights — without crushing whites.
    """
    a = _to_f32(base); b = _to_f32(top)
    if a.shape != b.shape:
        # Conform sizes by pasting onto common canvas
        size = (max(a.shape[1], b.shape[1]), max(a.shape[0], b.shape[0]))
        ca = Image.new("RGBA", size, (0, 0, 0, 0)); ca.paste(base, (0, 0), base)
        cb = Image.new("RGBA", size, (0, 0, 0, 0)); cb.paste(top, (0, 0), top)
        a = _to_f32(ca); b = _to_f32(cb)
    out = np.empty_like(a)
    out[..., :3] = 1.0 - (1.0 - a[..., :3]) * (1.0 - b[..., :3])
    out[..., 3]  = np.maximum(a[..., 3], b[..., 3])
    return _to_rgba(out)

def multiply_blend(base: Image.Image, top: Image.Image) -> Image.Image:
    """Multiply RGB, alpha = base.a * top.a. Use for shadows and tints."""
    a = _to_f32(base); b = _to_f32(top)
    if a.shape != b.shape:
        size = (max(a.shape[1], b.shape[1]), max(a.shape[0], b.shape[0]))
        ca = Image.new("RGBA", size, (0, 0, 0, 0)); ca.paste(base, (0, 0), base)
        cb = Image.new("RGBA", size, (0, 0, 0, 0)); cb.paste(top, (0, 0), top)
        a = _to_f32(ca); b = _to_f32(cb)
    out = np.empty_like(a)
    out[..., :3] = a[..., :3] * b[..., :3]
    out[..., 3]  = a[..., 3] * b[..., 3]
    return _to_rgba(out)


def colorize(mask: Image.Image, stops: list) -> Image.Image:
    """Vectorised vertical gradient fill — much faster than a row-loop."""
    stops = [s[:3] for s in stops]   # strip alpha if present (4-tuples)
    m  = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    n  = len(stops)
    t  = np.linspace(0.0, 1.0, h, dtype=np.float32)          # (h,)
    idx = np.clip((t * (n - 1)).astype(np.int32), 0, n - 2)   # lower stop index
    frac = (t * (n - 1) - idx)[:, None]                        # (h,1) for broadcast
    c0 = np.array([stops[i] for i in idx], dtype=np.float32)   # (h,3)
    c1 = np.array([stops[min(i+1, n-1)] for i in idx], dtype=np.float32)
    rgb = np.clip(c0 * (1 - frac) + c1 * frac, 0, 255).astype(np.uint8)  # (h,3)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, :3] = rgb[:, None, :]                            # broadcast to (h,w,3)
    out[:, :, 3]  = m
    return Image.fromarray(out, "RGBA")

def flat_color(mask: Image.Image, rgb: tuple, alpha: int = 255) -> Image.Image:
    m = np.array(mask, dtype=np.uint8)
    out = np.zeros((*m.shape,4), dtype=np.uint8)
    out[:,:,0]=rgb[0]; out[:,:,1]=rgb[1]; out[:,:,2]=rgb[2]
    out[:,:,3] = (m * (alpha/255)).astype(np.uint8)
    return Image.fromarray(out,"RGBA")

def dilate(mask: Image.Image, px: int) -> Image.Image:
    r = mask.copy()
    for _ in range(px):
        r = r.filter(ImageFilter.MaxFilter(3))
    return r

def extrude(mask: Image.Image, depth: int, angle_deg: float,
            col_near: tuple, col_far: tuple) -> Image.Image:
    if depth <= 0:
        return Image.new("RGBA", mask.size, (0,0,0,0))
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    w, h = mask.size
    pad = depth + 6
    canvas = Image.new("RGBA", (w+pad*2, h+pad*2), (0,0,0,0))
    m = np.array(mask, dtype=np.uint8)
    for step in range(depth, 0, -1):
        t = step / depth
        r = int(col_near[0]*(1-t)+col_far[0]*t)
        g = int(col_near[1]*(1-t)+col_far[1]*t)
        b = int(col_near[2]*(1-t)+col_far[2]*t)
        ox, oy = int(round(dx*step)), int(round(dy*step))
        layer = np.zeros((h+pad*2, w+pad*2, 4), dtype=np.uint8)
        layer[pad+oy:pad+oy+h, pad+ox:pad+ox+w] = np.stack([
            np.full_like(m,r), np.full_like(m,g), np.full_like(m,b), m], axis=-1)
        canvas = Image.alpha_composite(canvas, Image.fromarray(layer,"RGBA"))
    return canvas.crop((pad, pad, pad+w, pad+h))

def rainbow_extrude(mask: Image.Image, depth: int, angle_deg: float,
                    hue_start: float = 0.0, sat: float = 0.90,
                    val: float = 0.88) -> Image.Image:
    """Extrusion where each layer cycles through the hue wheel."""
    if depth <= 0:
        return Image.new("RGBA", mask.size, (0,0,0,0))
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    w, h = mask.size
    pad = depth + 6
    canvas = Image.new("RGBA", (w+pad*2, h+pad*2), (0,0,0,0))
    m = np.array(mask, dtype=np.uint8)
    for step in range(depth, 0, -1):
        hue = (hue_start + (step / depth) * 0.82) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        r, g, b = int(r*255), int(g*255), int(b*255)
        ox, oy = int(round(dx*step)), int(round(dy*step))
        layer = np.zeros((h+pad*2, w+pad*2, 4), dtype=np.uint8)
        layer[pad+oy:pad+oy+h, pad+ox:pad+ox+w] = np.stack([
            np.full_like(m,r), np.full_like(m,g), np.full_like(m,b), m], axis=-1)
        canvas = Image.alpha_composite(canvas, Image.fromarray(layer,"RGBA"))
    return canvas.crop((pad, pad, pad+w, pad+h))

def glow_layer(mask: Image.Image, rgb: tuple, radii=None) -> Image.Image:
    """Multi-pass glow with float32 accumulation — preserves bloom energy."""
    if radii is None:
        radii = [(32, 0.35), (16, 0.60), (6, 0.90)]
    h, w = mask.size[1], mask.size[0]  # PIL size is (w, h)
    # Accumulate in float32 to avoid 8-bit clamping
    accum = np.zeros((mask.size[1], mask.size[0]), dtype=np.float32)
    for r, s in radii:
        bl = mask.filter(ImageFilter.GaussianBlur(r))
        arr = np.array(bl, dtype=np.float32) / 255.0
        accum += arr * s
    # Soft tonemap: preserves glow shape without hard clipping
    # Reinhard-style: out = x / (1 + x) mapped to [0, 255]
    alpha = accum / (1.0 + accum) * 2.0  # scale up so peak ~= 1.0
    alpha = np.clip(alpha, 0, 1)
    out = np.zeros((mask.size[1], mask.size[0], 4), dtype=np.uint8)
    out[:, :, 0] = rgb[0]; out[:, :, 1] = rgb[1]; out[:, :, 2] = rgb[2]
    out[:, :, 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def drop_shadow(mask: Image.Image, ox: int, oy: int,
                blur: int = 8, alpha: int = 140) -> Image.Image:
    """Drop shadow — works on an expanded canvas so it never clips."""
    m  = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    # Expand canvas so offset + blur never exceeds boundaries
    ex = abs(ox) + blur + 4
    ey = abs(oy) + blur + 4
    big_h, big_w = h + ey * 2, w + ex * 2
    expanded = np.zeros((big_h, big_w), dtype=np.uint8)
    # Paste original mask, then shift it
    sy = ey + oy
    sx = ex + ox
    expanded[sy:sy+h, sx:sx+w] = m
    bl  = Image.fromarray(expanded, "L").filter(ImageFilter.GaussianBlur(blur))
    arr = np.array(bl, dtype=np.float32)
    # Crop back to original size (centred at ey, ex)
    arr = arr[ey:ey+h, ex:ex+w]
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:,:,3] = np.clip(arr * (alpha / 255), 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def highlight(mask: Image.Image, strength: float = 0.45) -> Image.Image:
    m = np.array(mask, dtype=np.float32)
    h, w = m.shape
    band = np.zeros((h,w), dtype=np.float32)
    hi = max(1, h//4)
    band[:hi,:] = np.linspace(strength, 0, hi)[:,None]
    out = np.zeros((h,w,4), dtype=np.uint8)
    out[:,:,0]=255; out[:,:,1]=255; out[:,:,2]=255
    out[:,:,3] = np.clip(band*m,0,255).astype(np.uint8)
    return Image.fromarray(out,"RGBA")

def composite(*layers, size) -> Image.Image:
    result = Image.new("RGBA", size, (0,0,0,0))
    for L in layers:
        if L is None: continue
        if L.size != size:
            tmp = Image.new("RGBA", size, (0,0,0,0))
            tmp.paste(L, (0,0), L)
            L = tmp
        result = Image.alpha_composite(result, L)
    return result

# ── Premium helpers ───────────────────────────────────────────────────────────

def bevel_light(mask: Image.Image, angle_deg: float = 135,
                strength: float = 1.6) -> tuple:
    """
    Compute bevel shading from mask surface normals.
    Returns (highlight_layer, shadow_layer) RGBA pair.
    angle_deg: direction light comes FROM (135 = top-left, classic lighting).
    """
    rad = math.radians(angle_deg)
    lx, ly = math.cos(rad), -math.sin(rad)          # PIL y-axis is flipped
    m  = np.array(mask, dtype=np.float32) / 255.0
    gy, gx = np.gradient(m)
    mag = np.sqrt(gx**2 + gy**2 + 0.01)
    nx, ny = gx / mag, gy / mag
    dot = np.clip((nx * lx + ny * ly) * strength, -1.0, 1.0)
    hl_a = np.clip( dot * m, 0, 1)
    sh_a = np.clip(-dot * m, 0, 1)
    hl = np.zeros((*m.shape, 4), np.uint8)
    hl[:,:,:3] = 255;  hl[:,:,3] = (hl_a * 230).astype(np.uint8)
    sh = np.zeros((*m.shape, 4), np.uint8)
    sh[:,:,3]  = (sh_a * 200).astype(np.uint8)
    return Image.fromarray(hl, "RGBA"), Image.fromarray(sh, "RGBA")


def inner_glow(mask: Image.Image, rgb: tuple, radii=None) -> Image.Image:
    """
    Glow visible INSIDE the letterforms — edges light up inward.
    Creates the warm core of neon tubes and glowing glass.
    """
    if radii is None:
        radii = [(10, 0.75), (4, 0.95)]
    m  = np.array(mask, dtype=np.float32) / 255.0
    base = Image.new("RGBA", mask.size, (0,0,0,0))
    for r, s in radii:
        bl = np.array(mask.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0
        rim = np.clip(m - bl, 0, 1)          # edge rim inside letters
        layer = np.zeros((*m.shape, 4), np.uint8)
        layer[:,:,0] = rgb[0]; layer[:,:,1] = rgb[1]; layer[:,:,2] = rgb[2]
        layer[:,:,3] = np.clip(rim * s * 255, 0, 255).astype(np.uint8)
        base = Image.alpha_composite(base, Image.fromarray(layer, "RGBA"))
    return base


def fill_solid(size: tuple, rgb: tuple, alpha: int = 255) -> Image.Image:
    """Solid-color RGBA background."""
    img = Image.new("RGBA", size, (*rgb, alpha))
    return img


def mask_to_rgba(mask: Image.Image, rgb: tuple) -> Image.Image:
    """Apply mask as alpha to a solid colour (alias for flat_color)."""
    return flat_color(mask, rgb)


def apply_mask(layer: Image.Image, mask: Image.Image) -> Image.Image:
    """Crop a layer to the text shape — multiply alpha by mask."""
    m = np.array(mask, dtype=np.float32) / 255.0
    a = np.array(layer, dtype=np.float32)
    a[:,:,3] = np.clip(a[:,:,3] * m, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


# ── Advanced primitives (v2) ──────────────────────────────────────────────────

def noise_texture(w: int, h: int, scale: float = 0.02, octaves: int = 4,
                  seed: int = 0) -> np.ndarray:
    """Generate smooth Perlin-like noise as float32 array in [0,1].
    Uses multi-octave value noise (fast, no extra deps)."""
    rng = np.random.RandomState(seed)
    result = np.zeros((h, w), dtype=np.float32)
    amplitude = 1.0
    total_amp = 0.0
    for _ in range(octaves):
        # Random phase offset per octave
        ox, oy = rng.uniform(0, 1000, 2)
        ys = np.arange(h, dtype=np.float32) * scale + oy
        xs = np.arange(w, dtype=np.float32) * scale + ox
        # Bilinear interpolation of random grid
        gw = int(w * scale) + 4
        gh = int(h * scale) + 4
        grid = rng.rand(gh, gw).astype(np.float32)
        from PIL import Image as _Im
        grid_img = _Im.fromarray((grid * 255).astype(np.uint8), "L")
        grid_up = grid_img.resize((w, h), Image.BILINEAR)
        result += np.array(grid_up, dtype=np.float32) / 255.0 * amplitude
        total_amp += amplitude
        amplitude *= 0.5
        scale *= 2.0
    result /= total_amp
    return result


def texture_fill(mask: Image.Image, base_rgb: tuple, highlight_rgb: tuple,
                 noise_scale: float = 0.015, seed: int = 0) -> Image.Image:
    """Fill text with a noise-based texture between two colors."""
    m = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    noise = noise_texture(w, h, scale=noise_scale, seed=seed)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(3):
        out[:, :, c] = np.clip(
            base_rgb[c] + (highlight_rgb[c] - base_rgb[c]) * noise, 0, 255
        ).astype(np.uint8)
    out[:, :, 3] = m
    return Image.fromarray(out, "RGBA")


def env_map_chrome(mask: Image.Image, stops: list = None,
                   angle: float = 0.0, stretch: float = 1.5,
                   noise_amount: float = 0.08, seed: int = 0) -> Image.Image:
    """Simulate chrome environment map — gradient mapped to surface normals
    with subtle noise for realistic reflections."""
    if stops is None:
        stops = [(30, 35, 45), (180, 190, 210), (255, 255, 255),
                 (60, 70, 90), (200, 210, 230), (255, 255, 255),
                 (100, 110, 130)]
    m = np.array(mask, dtype=np.float32) / 255.0
    h, w = m.shape

    # Surface normals from mask gradient
    gy, gx = np.gradient(m)
    mag = np.sqrt(gx**2 + gy**2 + 0.001)
    nx = gx / mag

    # Map normal x to gradient position (simulates horizontal env reflection)
    rad = math.radians(angle)
    env_coord = np.clip((nx * math.cos(rad) + gy / mag * math.sin(rad))
                        * stretch * 0.5 + 0.5, 0, 1)

    # Vertical component for top-down light
    vert = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    env_coord = np.clip(env_coord * 0.6 + vert * 0.4, 0, 1)

    # Add noise for micro-reflections
    if noise_amount > 0:
        noise = noise_texture(w, h, scale=0.03, seed=seed)
        env_coord = np.clip(env_coord + (noise - 0.5) * noise_amount, 0, 1)

    # Map to gradient
    n = len(stops)
    idx = np.clip((env_coord * (n - 1)).astype(np.int32), 0, n - 2)
    frac = env_coord * (n - 1) - idx

    out = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(3):
        c0 = np.array([stops[i][c] for i in range(n)], dtype=np.float32)
        lo = c0[idx]
        hi = c0[np.minimum(idx + 1, n - 1)]
        out[:, :, c] = np.clip(lo + (hi - lo) * frac, 0, 255).astype(np.uint8)
    out[:, :, 3] = (m * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def grain_overlay(img: Image.Image, amount: float = 0.06,
                  seed: int = 0) -> Image.Image:
    """Add film grain / noise to an RGBA image."""
    arr = np.array(img, dtype=np.float32)
    rng = np.random.RandomState(seed)
    noise = rng.randn(arr.shape[0], arr.shape[1]).astype(np.float32)
    for c in range(3):
        arr[:, :, c] = np.clip(arr[:, :, c] + noise * amount * 255, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def emboss_deep(mask: Image.Image, depth: float = 3.0,
                angle_deg: float = 135, ambient: float = 0.3) -> Image.Image:
    """Deep emboss with ambient fill — more dramatic than bevel_light.
    Returns single RGBA layer (combined highlight + shadow on neutral gray)."""
    rad = math.radians(angle_deg)
    lx, ly = math.cos(rad), -math.sin(rad)
    m = np.array(mask.filter(ImageFilter.GaussianBlur(1)), dtype=np.float32) / 255.0
    h, w = m.shape

    gy, gx = np.gradient(m)
    mag = np.sqrt(gx**2 + gy**2 + 0.001)
    nx, ny = gx / mag, gy / mag
    dot = np.clip((nx * lx + ny * ly) * depth, -1.0, 1.0)

    # Ambient + directional
    light = np.clip(ambient + dot * (1.0 - ambient), 0, 1)
    light *= m  # mask out background

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, 0] = (light * 255).astype(np.uint8)
    out[:, :, 1] = (light * 255).astype(np.uint8)
    out[:, :, 2] = (light * 255).astype(np.uint8)
    out[:, :, 3] = (m * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def outline_stroke(mask: Image.Image, width: int = 4,
                   rgb: tuple = (255, 255, 255),
                   alpha: int = 255) -> Image.Image:
    """Clean outline stroke around text."""
    dilated = mask
    for _ in range(width):
        dilated = dilated.filter(ImageFilter.MaxFilter(3))
    # Stroke = dilated minus original
    d_arr = np.array(dilated, dtype=np.float32)
    m_arr = np.array(mask, dtype=np.float32)
    stroke = np.clip(d_arr - m_arr, 0, 255)
    out = np.zeros((*mask.size[::-1], 4), dtype=np.uint8)
    out[:, :, 0] = rgb[0]
    out[:, :, 1] = rgb[1]
    out[:, :, 2] = rgb[2]
    out[:, :, 3] = np.clip(stroke * (alpha / 255), 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def radial_gradient_fill(mask: Image.Image, center_rgb: tuple,
                         edge_rgb: tuple, focus: float = 0.5) -> Image.Image:
    """Radial gradient fill from center to edge of bounding box."""
    m = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    cy, cx = h / 2, w / 2
    max_r = math.sqrt(cx**2 + cy**2)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xs - cx)**2 + (ys - cy)**2) / max_r
    dist = np.clip(dist / focus, 0, 1)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(3):
        out[:, :, c] = np.clip(
            center_rgb[c] + (edge_rgb[c] - center_rgb[c]) * dist, 0, 255
        ).astype(np.uint8)
    out[:, :, 3] = m
    return Image.fromarray(out, "RGBA")


def specular_highlight(mask: Image.Image, pos_y: float = 0.25,
                       width: float = 0.15, intensity: float = 0.7) -> Image.Image:
    """Horizontal specular highlight band across text."""
    m = np.array(mask, dtype=np.float32) / 255.0
    h, w = m.shape
    center = int(h * pos_y)
    band_h = max(1, int(h * width))
    ys = np.arange(h, dtype=np.float32)
    spec = np.exp(-0.5 * ((ys - center) / (band_h * 0.4))**2)
    spec = spec[:, None] * intensity
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, :3] = 255
    out[:, :, 3] = np.clip(spec * m * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def diagonal_gradient_fill(mask: Image.Image, stops: list,
                           angle_deg: float = 45) -> Image.Image:
    """Gradient fill at any angle, not just vertical."""
    m = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    rad = math.radians(angle_deg)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    # Project onto gradient direction
    proj = xs * math.cos(rad) + ys * math.sin(rad)
    proj = (proj - proj.min()) / (proj.max() - proj.min() + 1e-9)

    n = len(stops)
    idx = np.clip((proj * (n - 1)).astype(np.int32), 0, n - 2)
    frac = proj * (n - 1) - idx
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(3):
        c_arr = np.array([s[c] for s in stops], dtype=np.float32)
        lo = c_arr[idx]
        hi = c_arr[np.minimum(idx + 1, n - 1)]
        out[:, :, c] = np.clip(lo + (hi - lo) * frac, 0, 255).astype(np.uint8)
    out[:, :, 3] = m
    return Image.fromarray(out, "RGBA")


# ── Advanced primitives (v2b) ─────────────────────────────────────────────────

def contour_lines(mask: Image.Image, count: int = 3, spacing: int = 4,
                  colors: list = None, alpha: int = 255) -> Image.Image:
    """Multiple concentric outlines (sticker/badge effect).
    Returns all outlines composited on a single RGBA layer."""
    if colors is None:
        colors = [(255, 255, 255)] * count
    base = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    prev = mask
    for i in range(count):
        expanded = prev
        for _ in range(spacing):
            expanded = expanded.filter(ImageFilter.MaxFilter(3))
        # Ring = expanded minus previous
        e_arr = np.array(expanded, dtype=np.float32)
        p_arr = np.array(prev, dtype=np.float32)
        ring = np.clip(e_arr - p_arr, 0, 255)
        c = colors[i % len(colors)]
        layer = np.zeros((*mask.size[::-1], 4), dtype=np.uint8)
        layer[:, :, 0] = c[0]; layer[:, :, 1] = c[1]; layer[:, :, 2] = c[2]
        layer[:, :, 3] = np.clip(ring * (alpha / 255), 0, 255).astype(np.uint8)
        base = Image.alpha_composite(base, Image.fromarray(layer, "RGBA"))
        prev = expanded
    return base


def gradient_stroke(mask: Image.Image, width: int = 4,
                    stops: list = None) -> Image.Image:
    """Outline stroke with a vertical gradient color."""
    if stops is None:
        stops = [(255, 200, 0), (255, 80, 0)]
    dilated = mask
    for _ in range(width):
        dilated = dilated.filter(ImageFilter.MaxFilter(3))
    d_arr = np.array(dilated, dtype=np.float32)
    m_arr = np.array(mask, dtype=np.float32)
    stroke_alpha = np.clip(d_arr - m_arr, 0, 255).astype(np.uint8)
    # Build gradient-colored stroke
    stroke_mask = Image.fromarray(stroke_alpha, "L")
    return colorize(stroke_mask, stops)


def satin_sheen(mask: Image.Image, rgb: tuple = (255, 255, 255),
                angle_deg: float = 135, width: float = 0.4,
                intensity: float = 0.5) -> Image.Image:
    """Satin/silk inner sheen that follows letter contours.
    Like an inner bevel but softer, following the shape's curvature."""
    m = np.array(mask, dtype=np.float32) / 255.0
    h, w = m.shape
    # Compute distance from edges using iterative blur erosion
    eroded = np.array(mask.filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255.0
    contour = np.abs(m - eroded)
    # Directional component
    rad = math.radians(angle_deg)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = (xs / w * math.cos(rad) + ys / h * math.sin(rad))
    proj = (proj - proj.min()) / (proj.max() - proj.min() + 1e-9)
    # Satin bands
    bands = np.sin(proj * math.pi / width) ** 2
    sheen = contour * bands * intensity * m
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, 0] = rgb[0]; out[:, :, 1] = rgb[1]; out[:, :, 2] = rgb[2]
    out[:, :, 3] = np.clip(sheen * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def chromatic_aberration(img: Image.Image, offset: int = 4) -> Image.Image:
    """Split RGB channels for a glitch/CA effect."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    out = np.zeros_like(arr)
    # Shift red left, blue right, green stays
    out[:, :max(0, w - offset), 0] = arr[:, offset:, 0]  # red left
    out[:, :, 1] = arr[:, :, 1]                            # green center
    out[:, min(w, offset):, 2] = arr[:, :max(0, w - offset), 2]  # blue right
    out[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(out, "RGBA")


def scanlines(img: Image.Image, spacing: int = 3, alpha: float = 0.3) -> Image.Image:
    """CRT scanline overlay for retro effects."""
    arr = np.array(img, dtype=np.float32)
    h = arr.shape[0]
    for y in range(0, h, spacing):
        arr[y, :, :3] *= (1.0 - alpha)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def halftone_fill(mask: Image.Image, rgb: tuple, dot_size: int = 6,
                  spacing: int = 8) -> Image.Image:
    """Halftone dot pattern fill."""
    m = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    ys, xs = np.mgrid[0:h, 0:w]
    # Grid of dots
    cx = (xs % spacing) - spacing // 2
    cy = (ys % spacing) - spacing // 2
    dist = np.sqrt(cx**2 + cy**2).astype(np.float32)
    # Dot radius proportional to mask brightness
    m_f = m.astype(np.float32) / 255.0
    radius = m_f * (dot_size / 2)
    dots = (dist < radius).astype(np.float32)
    out[:, :, 0] = rgb[0]; out[:, :, 1] = rgb[1]; out[:, :, 2] = rgb[2]
    out[:, :, 3] = (dots * m_f * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def reflection(img: Image.Image, height_frac: float = 0.4,
               fade: float = 0.5) -> Image.Image:
    """Add a faded mirror reflection below the image."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    ref_h = int(h * height_frac)
    # Flip the bottom portion
    ref = arr[-ref_h:][::-1].copy().astype(np.float32)
    # Fade out
    fade_arr = np.linspace(fade, 0, ref_h, dtype=np.float32)[:, None, None]
    ref[:, :, 3] = np.clip(ref[:, :, 3] * fade_arr[:, :, 0], 0, 255)
    # New canvas with space for reflection
    out = np.zeros((h + ref_h, w, 4), dtype=np.uint8)
    out[:h] = arr
    out[h:h + ref_h] = ref.astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def colored_shadow(mask: Image.Image, ox: int, oy: int, rgb: tuple,
                   blur: int = 10, alpha: int = 160) -> Image.Image:
    """Drop shadow with a custom color (not just black)."""
    m = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    ex = abs(ox) + blur + 4
    ey = abs(oy) + blur + 4
    big_h, big_w = h + ey * 2, w + ex * 2
    expanded = np.zeros((big_h, big_w), dtype=np.uint8)
    sy, sx = ey + oy, ex + ox
    expanded[sy:sy + h, sx:sx + w] = m
    bl = Image.fromarray(expanded, "L").filter(ImageFilter.GaussianBlur(blur))
    arr = np.array(bl, dtype=np.float32)
    arr = arr[ey:ey + h, ex:ex + w]
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, 0] = rgb[0]; out[:, :, 1] = rgb[1]; out[:, :, 2] = rgb[2]
    out[:, :, 3] = np.clip(arr * (alpha / 255), 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def lit_extrude(mask: Image.Image, depth: int, angle_deg: float,
                base_rgb: tuple, light_angle: float = 135,
                light_strength: float = 0.5) -> Image.Image:
    """3D extrusion with directional lighting on the extrusion faces."""
    if depth <= 0:
        return Image.new("RGBA", mask.size, (0, 0, 0, 0))
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    w, h = mask.size
    pad = depth + 6
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    m = np.array(mask, dtype=np.uint8)
    # Light direction
    l_rad = math.radians(light_angle)
    lx, ly = math.cos(l_rad), -math.sin(l_rad)
    # Normal of extrusion faces
    ext_nx, ext_ny = -dx, -dy
    ext_len = math.sqrt(ext_nx**2 + ext_ny**2 + 0.001)
    ext_nx, ext_ny = ext_nx / ext_len, ext_ny / ext_len
    face_light = max(0.2, min(1.0, 0.5 + 0.5 * (ext_nx * lx + ext_ny * ly) * light_strength))
    for step in range(depth, 0, -1):
        t = step / depth
        r = int(base_rgb[0] * face_light * (0.7 + 0.3 * t))
        g = int(base_rgb[1] * face_light * (0.7 + 0.3 * t))
        b = int(base_rgb[2] * face_light * (0.7 + 0.3 * t))
        r, g, b = min(r, 255), min(g, 255), min(b, 255)
        ox, oy = int(round(dx * step)), int(round(dy * step))
        layer = np.zeros((h + pad * 2, w + pad * 2, 4), dtype=np.uint8)
        layer[pad + oy:pad + oy + h, pad + ox:pad + ox + w] = np.stack([
            np.full_like(m, r), np.full_like(m, g),
            np.full_like(m, b), m], axis=-1)
        canvas = Image.alpha_composite(canvas, Image.fromarray(layer, "RGBA"))
    return canvas.crop((pad, pad, pad + w, pad + h))


def stripe_fill(mask: Image.Image, colors: list, stripe_width: int = 8,
                angle_deg: float = 45) -> Image.Image:
    """Diagonal stripe pattern fill."""
    m = np.array(mask, dtype=np.uint8)
    h, w = m.shape
    rad = math.radians(angle_deg)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = xs * math.cos(rad) + ys * math.sin(rad)
    n_colors = len(colors)
    total_width = stripe_width * n_colors
    stripe_idx = ((proj % total_width) / stripe_width).astype(np.int32) % n_colors
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for i, c in enumerate(colors):
        where = stripe_idx == i
        out[where, 0] = c[0]; out[where, 1] = c[1]; out[where, 2] = c[2]
    out[:, :, 3] = m
    return Image.fromarray(out, "RGBA")


def wave_distort(img: Image.Image, amplitude: float = 8.0,
                 frequency: float = 0.03, phase: float = 0.0) -> Image.Image:
    """Horizontal wave distortion."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    out = np.zeros_like(arr)
    for y in range(h):
        shift = int(amplitude * math.sin(frequency * y + phase))
        if shift >= 0:
            out[y, shift:] = arr[y, :w - shift]
        else:
            out[y, :w + shift] = arr[y, -shift:]
    return Image.fromarray(out, "RGBA")


def blend_multiply(base: Image.Image, overlay: Image.Image) -> Image.Image:
    """Multiply blend mode — darkens, great for textures."""
    b = np.array(base, dtype=np.float32) / 255.0
    o = np.array(overlay, dtype=np.float32) / 255.0
    result = b.copy()
    result[:, :, :3] = b[:, :, :3] * o[:, :, :3]
    result[:, :, 3] = np.maximum(b[:, :, 3], o[:, :, 3])
    return Image.fromarray((result * 255).astype(np.uint8), "RGBA")


def blend_screen(base: Image.Image, overlay: Image.Image) -> Image.Image:
    """Screen blend mode — lightens, great for glow effects."""
    b = np.array(base, dtype=np.float32) / 255.0
    o = np.array(overlay, dtype=np.float32) / 255.0
    result = b.copy()
    result[:, :, :3] = 1.0 - (1.0 - b[:, :, :3]) * (1.0 - o[:, :, :3])
    result[:, :, 3] = np.maximum(b[:, :, 3], o[:, :, 3])
    return Image.fromarray((result * 255).astype(np.uint8), "RGBA")


def edge_glow(mask: Image.Image, rgb: tuple, width: int = 6,
              intensity: float = 0.8) -> Image.Image:
    """Outer edge glow — visible outside the letterforms."""
    dilated = mask
    for _ in range(width):
        dilated = dilated.filter(ImageFilter.MaxFilter(3))
    dilated = dilated.filter(ImageFilter.GaussianBlur(width))
    d_arr = np.array(dilated, dtype=np.float32)
    m_arr = np.array(mask, dtype=np.float32)
    # Only keep the outer part
    outer = np.clip(d_arr - m_arr, 0, 255)
    out = np.zeros((*mask.size[::-1], 4), dtype=np.uint8)
    out[:, :, 0] = rgb[0]; out[:, :, 1] = rgb[1]; out[:, :, 2] = rgb[2]
    out[:, :, 3] = np.clip(outer * intensity, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def letterpress(mask: Image.Image, paper_rgb: tuple = (240, 235, 225),
                ink_rgb: tuple = (40, 35, 30),
                depth: float = 1.5) -> Image.Image:
    """Debossed/letterpress effect — text pressed into paper."""
    m = np.array(mask, dtype=np.float32) / 255.0
    h, w = m.shape
    # Paper background within mask bounds
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, 0] = int(ink_rgb[0] * 0.7 + paper_rgb[0] * 0.3)
    out[:, :, 1] = int(ink_rgb[1] * 0.7 + paper_rgb[1] * 0.3)
    out[:, :, 2] = int(ink_rgb[2] * 0.7 + paper_rgb[2] * 0.3)
    out[:, :, 3] = (m * 255).astype(np.uint8)
    base = Image.fromarray(out, "RGBA")
    # Add deboss lighting
    hl, sh = bevel_light(mask, angle_deg=135, strength=depth)
    # Invert — deboss instead of emboss
    hl_arr = np.array(hl)
    sh_arr = np.array(sh)
    return composite(base, Image.fromarray(sh_arr, "RGBA"),
                     Image.fromarray(hl_arr, "RGBA"), size=(w, h))


def shear_image(img: Image.Image, factor: float) -> Image.Image:
    w, h = img.size
    xshift = abs(factor) * h
    new_w = int(w + xshift)
    arr = np.array(img)
    out = np.zeros((h, new_w, 4), dtype=np.uint8)
    for y in range(h):
        shift = int(xshift*(1-y/h)) if factor > 0 else int(xshift*y/h)
        out[y, shift:shift+w] = arr[y]
    return Image.fromarray(out,"RGBA")

def long_shadow(mask: Image.Image, steps: int, angle_deg: float,
                col: tuple, fade: bool = True) -> Image.Image:
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    w, h = mask.size
    pad = steps + 4
    canvas = Image.new("RGBA", (w+pad*2, h+pad*2), (0,0,0,0))
    m = np.array(mask, dtype=np.uint8)
    for step in range(steps, 0, -1):
        a = int(200*(1-step/steps*0.6)) if fade else 180
        ox, oy = int(round(dx*step)), int(round(dy*step))
        layer = np.zeros((h+pad*2, w+pad*2, 4), dtype=np.uint8)
        layer[pad+oy:pad+oy+h, pad+ox:pad+ox+w] = np.stack([
            np.full_like(m,col[0]), np.full_like(m,col[1]),
            np.full_like(m,col[2]), (m*(a/255)).astype(np.uint8)], axis=-1)
        canvas = Image.alpha_composite(canvas, Image.fromarray(layer,"RGBA"))
    return canvas.crop((pad, pad, pad+w, pad+h))

def wide_track_mask(text: str, font, spacing: int, pad: int = 10) -> Image.Image:
    dummy = ImageDraw.Draw(Image.new("L",(8000,2000),0))
    chars = list(text)
    widths, heights, tops = [], [], []
    for c in chars:
        cw, ch, ct = measure(dummy, c, font)
        widths.append(cw); heights.append(ch); tops.append(ct)
    if not widths:
        return Image.new("L",(1,1),0)
    total_w = sum(widths) + spacing*max(0,len(chars)-1) + pad*2
    max_h   = max(heights) + pad*2
    img = Image.new("L", (total_w, max_h), 0)
    d   = ImageDraw.Draw(img)
    x   = pad
    for i, c in enumerate(chars):
        d.text((x, pad-tops[i]), c, fill=255, font=font)
        x += widths[i] + spacing
    return img

def rule_line(width: int, color: tuple, thickness: int = 2) -> Image.Image:
    img = Image.new("RGBA", (width, thickness+4), (0,0,0,0))
    ImageDraw.Draw(img).rectangle([(0,2),(width,2+thickness)], fill=(*color,220))
    return img

def wrap_chars(title: str, max_chars: int) -> list:
    if len(title) <= max_chars: return [title]
    words, lines, cur = title.split(), [], []
    for w in words:
        test = " ".join(cur+[w])
        if len(test) > max_chars and cur:
            lines.append(" ".join(cur)); cur=[w]
        else: cur.append(w)
    if cur: lines.append(" ".join(cur))
    return lines

def wrap_px(title: str, font, max_px: int) -> list:
    """Pixel-width-aware word wrap."""
    dummy = ImageDraw.Draw(Image.new("L",(1,1),0))
    words = title.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur+[word])
        w, _, _ = measure(dummy, test, font)
        if w > max_px and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur: lines.append(" ".join(cur))
    return lines if lines else [title]


# ── CC0 texture compositing (real photographic material clipped to letterforms)

_TEXTURE_DIR = Path(__file__).resolve().parent / "textures"
_TEXTURE_CACHE: dict = {}

def load_texture(slug: str) -> Image.Image:
    """Load a CC0 diffuse texture by slug. In-memory cached after first load."""
    if slug in _TEXTURE_CACHE:
        return _TEXTURE_CACHE[slug]
    for suffix in (f"{slug}_diff_1k.jpg", f"{slug}_col_1k.jpg",
                   f"{slug}_albedo_1k.jpg", f"{slug}.jpg", f"{slug}.png"):
        p = _TEXTURE_DIR / suffix
        if p.exists():
            img = Image.open(p).convert("RGB")
            _TEXTURE_CACHE[slug] = img
            return img
    raise FileNotFoundError(f"Texture '{slug}' not in {_TEXTURE_DIR}")


def hsv_shift(rgb: Image.Image, hue_deg: float = 0, sat: float = 1.0,
              val: float = 1.0) -> Image.Image:
    """Rotate hue (0-360 deg), scale saturation/value. Operates on RGB image."""
    if hue_deg == 0 and sat == 1.0 and val == 1.0:
        return rgb
    arr = np.array(rgb.convert("RGB"), dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    cmax = np.max(arr, axis=2); cmin = np.min(arr, axis=2)
    delta = cmax - cmin
    h = np.zeros_like(cmax)
    safe = np.where(delta > 0, delta, 1.0)
    mr = (cmax == r) & (delta > 0)
    mg = (cmax == g) & (delta > 0)
    mb = (cmax == b) & (delta > 0)
    h[mr] = ((g[mr] - b[mr]) / safe[mr]) % 6
    h[mg] = ((b[mg] - r[mg]) / safe[mg]) + 2
    h[mb] = ((r[mb] - g[mb]) / safe[mb]) + 4
    h = (h / 6.0) % 1.0
    s = np.where(cmax > 0, delta / np.where(cmax > 0, cmax, 1.0), 0)
    v = cmax
    h = (h + hue_deg / 360.0) % 1.0
    s = np.clip(s * sat, 0, 1)
    v = np.clip(v * val, 0, 1)
    i = (h * 6).astype(np.int32) % 6
    f = h * 6 - (h * 6).astype(np.int32)
    p_ = v * (1 - s); q_ = v * (1 - f * s); t_ = v * (1 - (1 - f) * s)
    out = np.stack([v, v, v], axis=2)
    for idx, R, G, B in [(0, v, t_, p_), (1, q_, v, p_), (2, p_, v, t_),
                          (3, p_, q_, v), (4, t_, p_, v), (5, v, p_, q_)]:
        m = (i == idx)
        out[m, 0] = R[m]; out[m, 1] = G[m]; out[m, 2] = B[m]
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8), "RGB")


def _fit_texture(texture: Image.Image, target_size: tuple, fit: str = "cover") -> Image.Image:
    mw, mh = target_size
    tw, th = texture.size
    if fit == "stretch":
        return texture.resize((mw, mh), Image.LANCZOS)
    scale = max(mw / tw, mh / th)
    new_size = (max(mw, int(tw * scale)), max(mh, int(th * scale)))
    tex = texture.resize(new_size, Image.LANCZOS)
    cx = (tex.size[0] - mw) // 2
    cy = (tex.size[1] - mh) // 2
    return tex.crop((cx, cy, cx + mw, cy + mh))


def texture_overlay(mask: Image.Image, texture, hue_deg: float = 0,
                    sat: float = 1.0, val: float = 1.0,
                    fit: str = "cover") -> Image.Image:
    """Composite a CC0 texture clipped to the text alpha mask. Returns RGBA.

    Best for materials whose source texture is already the right color
    (rust, oak, marble, denim, leather). For colored metals / coloured stone,
    use texture_modulate() with a color gradient as the base.
    """
    if isinstance(texture, str):
        texture = load_texture(texture)
    if hue_deg or sat != 1.0 or val != 1.0:
        texture = hsv_shift(texture, hue_deg, sat, val)
    tex = _fit_texture(texture, mask.size, fit)
    rgba = tex.convert("RGBA")
    rgba.putalpha(mask)
    return rgba


def texture_modulate(mask: Image.Image, base_rgba: Image.Image,
                     texture, strength: float = 0.45,
                     fit: str = "cover") -> Image.Image:
    """Use texture luminance to modulate an existing RGBA color layer.

    The base RGBA supplies the COLOR (e.g. from colorize() / FACE_GRADIENTS),
    the texture supplies the surface GRAIN. Sweet spot strength 0.4-0.6.
    """
    if isinstance(texture, str):
        texture = load_texture(texture)
    tex = _fit_texture(texture, mask.size, fit)
    tex_l = np.array(tex.convert("L"), dtype=np.float32) / 255.0
    base = np.array(base_rgba.convert("RGBA"), dtype=np.float32) / 255.0
    modulated = base[..., :3] * (1.0 - strength) + base[..., :3] * tex_l[..., None] * strength * 2.0
    out = np.empty_like(base)
    out[..., :3] = np.clip(modulated, 0, 1)
    m = np.array(mask, dtype=np.float32) / 255.0
    out[..., 3] = m
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


# screen_blend / multiply_blend are defined earlier in this file (~line 197).


# ── Advanced primitives (Pack 1+ expansion) ───────────────────────────────────
# These compound: every treatment that adopts them looks more polished, and
# every new treatment can reach for them as building blocks.


def bevel_emboss(mask: Image.Image,
                 depth: int = 6,
                 angle_deg: float = 135.0,
                 smoothness: float = 1.4,
                 highlight_color: tuple = (255, 255, 255),
                 highlight_alpha: int = 210,
                 shadow_color: tuple = (0, 0, 0),
                 shadow_alpha: int = 200) -> Image.Image:
    """Photoshop-style bevel & emboss. Returns RGBA layer to composite OVER
    the colored face. Computes a normal-map approximation from the mask
    distance field, then lights it with a directional light.

    smoothness >1 softens the bevel (more Gaussian); <1 keeps it sharper.
    """
    m = np.array(mask, dtype=np.float32) / 255.0
    if m.max() <= 0:
        return Image.new("RGBA", mask.size, (0, 0, 0, 0))

    # Smooth the mask so the gradient (used as a normal proxy) reads as a
    # surface, not as binary edges. depth controls Gaussian radius.
    blurred = mask.filter(ImageFilter.GaussianBlur(max(0.5, depth * smoothness)))
    b = np.array(blurred, dtype=np.float32) / 255.0

    # Gradient = surface slope. Use Sobel-ish kernels.
    gx = np.zeros_like(b)
    gy = np.zeros_like(b)
    gx[:, 1:-1] = (b[:, 2:] - b[:, :-2]) * 0.5
    gy[1:-1, :] = (b[2:, :] - b[:-2, :]) * 0.5

    # Light direction in 2D (angle 0 = right, 90 = down per image coords).
    rad = math.radians(angle_deg)
    lx, ly = math.cos(rad), math.sin(rad)
    # Dot product between negative gradient (inward-pointing normal) and light.
    dot = -(gx * lx + gy * ly)
    # Normalise: peak slope is at the edge of the mask
    dot = dot / (np.abs(dot).max() + 1e-6)

    hi = np.clip(dot, 0, 1) ** 1.4   # highlight side
    sh = np.clip(-dot, 0, 1) ** 1.4  # shadow side

    out = np.zeros((*mask.size[::-1], 4), dtype=np.float32)
    out[..., 0] = highlight_color[0] * hi + shadow_color[0] * sh
    out[..., 1] = highlight_color[1] * hi + shadow_color[1] * sh
    out[..., 2] = highlight_color[2] * hi + shadow_color[2] * sh
    out[..., 3] = (hi * highlight_alpha + sh * shadow_alpha) * m
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def fresnel_metallic(mask: Image.Image,
                     base_color: tuple = (220, 200, 120),
                     rim_color: tuple = (255, 250, 220),
                     rim_power: float = 2.4,
                     light_angle_deg: float = 75.0) -> Image.Image:
    """Photographic metallic with grazing-angle (Fresnel) rim brightening.
    Real polished metals brighten dramatically at low view angles — flat
    gradient fills don't capture that and look plastic. This does."""
    m = np.array(mask, dtype=np.float32) / 255.0
    if m.max() <= 0:
        return Image.new("RGBA", mask.size, (0, 0, 0, 0))

    # Distance from edge of mask (interior toward edge approximation).
    blurred = mask.filter(ImageFilter.GaussianBlur(8))
    b = np.array(blurred, dtype=np.float32) / 255.0
    # "Edge proximity": 1 at rim, 0 at deep interior.
    edge = np.clip(1.0 - b * 1.4, 0, 1) ** rim_power

    # Vertical light gradient — brightens upper half, slightly darkens lower.
    rad = math.radians(light_angle_deg)
    h, w = m.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    grad = (xx * math.cos(rad) - yy * math.sin(rad))
    grad = (grad - grad.min()) / (grad.max() - grad.min() + 1e-6)
    light = 0.7 + 0.6 * grad  # 0.7..1.3 multiplier

    out = np.zeros((h, w, 4), dtype=np.float32)
    base = np.array(base_color, dtype=np.float32)
    rim  = np.array(rim_color,  dtype=np.float32)
    for c in range(3):
        face = base[c] * light
        face = face * (1.0 - edge) + rim[c] * edge
        out[..., c] = face
    out[..., 3] = m * 255
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def motion_blur_chrome(mask: Image.Image,
                       angle_deg: float = 90.0,
                       length: int = 28,
                       stops: list = None) -> Image.Image:
    """Photoshop's chrome trick: blur the alpha mask along an axis, then
    treat the blurred grayscale as a chrome reflection lookup. Produces
    streaky horizontal-band reflections you can't get from a static gradient.

    `stops` is the chrome reflection palette (default: dramatic mirror).
    """
    if stops is None:
        stops = CHROME_STOPS

    # Build a directional motion blur via successive shifts.
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    h, w = mask.size[1], mask.size[0]
    accum = np.zeros((h, w), dtype=np.float32)
    weight = 0.0
    for step in range(-length, length + 1):
        ox = int(round(dx * step))
        oy = int(round(dy * step))
        a = math.exp(-((step / (length * 0.6)) ** 2))  # Gaussian weight
        m_arr = np.array(mask, dtype=np.float32) / 255.0
        shifted = np.zeros_like(m_arr)
        ys = slice(max(0, oy), min(h, h + oy))
        xs = slice(max(0, ox), min(w, w + ox))
        ys_src = slice(max(0, -oy), min(h, h - oy))
        xs_src = slice(max(0, -ox), min(w, w - ox))
        shifted[ys, xs] = m_arr[ys_src, xs_src]
        accum += shifted * a
        weight += a
    accum /= max(weight, 1e-6)

    # Map accum (0..1) into the chrome palette.
    n = len(stops)
    idx = np.clip((accum * (n - 1)).astype(np.int32), 0, n - 2)
    frac = (accum * (n - 1)) - idx
    c0 = np.array([stops[i] for i in idx.flatten()], dtype=np.float32).reshape(h, w, 3)
    c1 = np.array([stops[min(i + 1, n - 1)] for i in idx.flatten()], dtype=np.float32).reshape(h, w, 3)
    rgb = c0 * (1 - frac[..., None]) + c1 * frac[..., None]

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = (np.array(mask, dtype=np.uint8))
    return Image.fromarray(out, "RGBA")


def holographic_shift(mask: Image.Image,
                      hue_range: tuple = (0.55, 1.05),
                      saturation: float = 0.85,
                      value: float = 0.95,
                      bands: int = 6) -> Image.Image:
    """Iridescent holographic foil — chromatic shift across the surface in
    bands. Used for Y2K, holographic packaging, and cyberpunk treatments.

    hue_range is in HSV hue (0..1); >1 wraps. bands controls density of the
    iridescent stripes — fewer bands = wider color zones.
    """
    h, w = mask.size[1], mask.size[0]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # Diagonal banding feels more dynamic than vertical.
    diag = (xx + yy * 0.6) / (w + h * 0.6)
    # Wrapping with sine creates smooth bands; modulate hue across them.
    band = (np.sin(diag * bands * 2 * math.pi) + 1.0) * 0.5
    hue_lo, hue_hi = hue_range
    hue = (hue_lo + (hue_hi - hue_lo) * band) % 1.0

    # Vectorised HSV→RGB.
    v = np.full_like(hue, value)
    s = np.full_like(hue, saturation)
    i = (hue * 6).astype(np.int32)
    f = hue * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r = np.choose(i % 6, [v, q, p, p, t, v])
    g = np.choose(i % 6, [t, v, v, q, p, p])
    b = np.choose(i % 6, [p, p, t, v, v, q])

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0] = np.clip(r * 255, 0, 255).astype(np.uint8)
    out[..., 1] = np.clip(g * 255, 0, 255).astype(np.uint8)
    out[..., 2] = np.clip(b * 255, 0, 255).astype(np.uint8)
    out[..., 3] = np.array(mask, dtype=np.uint8)
    return Image.fromarray(out, "RGBA")


def ink_bleed(mask: Image.Image,
              radius: float = 1.4,
              strength: float = 0.5,
              irregularity: float = 0.6) -> Image.Image:
    """Simulate paper absorption — ink wicks outward unevenly from the
    letter edges. Returns a NEW grayscale alpha mask suitable for feeding
    into flat_color/colorize/etc.

    radius   = Gaussian bleed distance in px
    strength = how much of the bleed is added back (0=clean, 1=heavy bleed)
    irregularity = noise modulation on the bleed (0=smooth, 1=very textured)
    """
    base = np.array(mask, dtype=np.float32) / 255.0
    bled = mask.filter(ImageFilter.GaussianBlur(max(0.3, radius)))
    b = np.array(bled, dtype=np.float32) / 255.0

    # Per-pixel noise so the bleed isn't perfectly uniform.
    rng = np.random.default_rng(seed=int(radius * 1000) + int(strength * 100))
    noise = rng.random(base.shape).astype(np.float32)
    noise = (noise - 0.5) * 2.0 * irregularity   # ±irregularity
    bleed_amt = np.clip(b - base, 0, 1) * strength * (1.0 + noise * 0.5)
    out = np.clip(base + bleed_amt, 0, 1)
    return Image.fromarray((out * 255).astype(np.uint8), "L")

