"""
Pack 7 — Sport / athletic.

Ten treatments evoking sports and athletic design conventions: NFL crest,
MLB jersey, college varsity, racing livery, basketball jersey, X-games
extreme, Olympics-style, motorsport carbon, esports, soccer kit.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageChops

from cta_fonts import F
from cta_primitives import (
    bevel_emboss,
    colorize,
    composite,
    dilate,
    drop_shadow,
    extrude,
    flat_color,
    fresnel_metallic,
    halftone_fill,
    highlight,
    holographic_shift,
    ink_bleed,
    long_shadow,
    make_mask,
    motion_blur_chrome,
    outline_stroke,
    rule_line,
    shear_image,
    wide_track_mask,
    wrap_chars,
)


# ─── 1. NFL crest ─────────────────────────────────────────────────────────────

def render_nfl_crest(title: str, rng: random.Random) -> Image.Image:
    """NFL team crest aesthetic — heavy slab, navy/red/silver, deep extrude
    with metallic highlight, stitched-jersey feel."""
    n     = len(title)
    size  = 144 if n <= 12 else (112 if n <= 20 else 88)
    font  = F("athletic", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((30, 50, 110),   (200, 30, 40),   (220, 220, 230)),  # navy/red/silver
        ((10, 20, 30),    (220, 180, 30),  (230, 230, 235)),  # ink/gold/silver
        ((140, 30, 40),   (40, 50, 70),    (230, 230, 235)),  # crimson/slate/silver
    ]
    fg, accent, sl = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 8)
        sl_layer = flat_color(sm, sl)
        face = colorize(mask, [fg, tuple(max(0, c - 30) for c in fg)])
        ext  = extrude(sm, 10, 130, accent, tuple(max(0, c - 60) for c in accent))
        sh   = drop_shadow(sm, 8, 12, blur=4, alpha=220)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=tuple(max(0, c - 80) for c in fg),
                            shadow_alpha=200)
        img  = composite(sh, ext, sl_layer, face, bev, size=mask.size)
        line_imgs.append(img)

    gap     = 4
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. MLB jersey ────────────────────────────────────────────────────────────

def render_mlb_jersey(title: str, rng: random.Random) -> Image.Image:
    """Baseball-jersey type — wide-tracked athletic serif with chenille-
    patch feel, classic stitched red/navy on cream wool."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 78)
    font  = F("athletic", size, rng) or F("slab", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((180, 30, 30),   (240, 232, 218), (40, 50, 90)),    # red on cream + navy stroke
        ((40, 50, 90),    (240, 232, 218), (180, 30, 30)),
    ]
    fg, bg, stroke_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=20)
        sm   = dilate(mask, 6)
        sl   = flat_color(sm, stroke_c)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=tuple(min(255, c + 80) for c in fg),
                            highlight_alpha=140,
                            shadow_color=tuple(max(0, c - 60) for c in fg),
                            shadow_alpha=160)
        sh   = drop_shadow(mask, 3, 5, blur=5, alpha=140)
        img  = composite(sh, sl, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Faint horizontal pinstripes — wool-flannel feel
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(0, H, 6):
        cd.line([(0, y_pos), (W, y_pos)], fill=(220, 210, 188, 160), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. College varsity ───────────────────────────────────────────────────────

def render_college_varsity(title: str, rng: random.Random) -> Image.Image:
    """College varsity sweater — chunky athletic letters with split-color
    interior (top color/bottom color), heavy outline, drop shadow."""
    n     = len(title)
    size  = 154 if n <= 12 else (118 if n <= 20 else 92)
    font  = F("athletic", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 12)

    palettes = [
        ((220, 30, 30),  (250, 220, 50),  (10, 10, 12)),    # red over yellow + black
        ((40, 50, 130),  (220, 220, 230), (10, 10, 12)),    # navy over silver + black
        ((40, 100, 50),  (250, 220, 50),  (10, 10, 12)),    # forest over yellow + black
    ]
    top_c, bot_c, stroke_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        sm   = dilate(mask, 10)
        sl   = flat_color(sm, stroke_c)
        # Split fill: top half top_c, bottom half bot_c
        h, w = mask.size[1], mask.size[0]
        face_arr = np.array(mask, dtype=np.float32) / 255.0
        rgba = np.zeros((h, w, 4), dtype=np.float32)
        rgba[:h // 2, :, :3] = top_c
        rgba[h // 2:, :, :3] = bot_c
        rgba[..., 3] = face_arr * 255
        face = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=180,
                            shadow_color=(20, 20, 24), shadow_alpha=160)
        sh   = drop_shadow(sm, 7, 11, blur=4, alpha=220)
        img  = composite(sh, sl, face, bev, size=mask.size)
        line_imgs.append(img)

    gap     = 4
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Racing livery ─────────────────────────────────────────────────────────

def render_racing_livery(title: str, rng: random.Random) -> Image.Image:
    """F1/NASCAR racing livery — italic sheared sans, motion-blur chrome,
    sponsor-decal feel. Speed lines underneath."""
    n     = len(title)
    size  = 142 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("athletic", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 16)
    shear = 0.22

    palettes = [
        [(240, 232, 218), (200, 200, 210)],     # silver on dark
        [(220, 220, 230), (140, 150, 160)],     # chrome on dark
        [(255, 250, 220), (220, 168, 30)],      # pale → gold
    ]
    stops = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sh   = drop_shadow(mask, 6, 10, blur=6, alpha=220)
        face = colorize(mask, stops)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(20, 20, 30), shadow_alpha=180)
        img  = composite(sh, face, bev, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs) + 80
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1) + 60
    margin = 30
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (15, 18, 24, 255))

    # Speed lines — diagonal hairlines streaking from right to left
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(20, 32)):
        x_start = rng.randint(int(W * 0.4), W)
        y_start = rng.randint(0, H)
        line_len = rng.randint(40, 120)
        cd.line([(x_start, y_start), (x_start - line_len, y_start)],
                fill=(220, 220, 230, rng.randint(20, 80)), width=1)

    y = margin + 30
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Basketball jersey ─────────────────────────────────────────────────────

def render_basketball_jersey(title: str, rng: random.Random) -> Image.Image:
    """NBA-style player jersey lettering — mesh-gradient face, rounded
    chunky athletic font, side-stripe panel."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("athletic", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((220, 100, 30),  (40, 30, 90),    (240, 232, 218)),  # orange/navy/cream
        ((140, 50, 220),  (220, 200, 30),  (10, 10, 14)),     # purple/gold/black
        ((30, 170, 80),   (240, 240, 240), (10, 10, 14)),     # green/white/black
    ]
    fg, side, ink = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 7)
        sl   = flat_color(sm, ink)
        face = colorize(mask, [tuple(min(255, c + 40) for c in fg), fg,
                               tuple(max(0, c - 30) for c in fg)])
        bev  = bevel_emboss(mask, depth=5, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(20, 20, 24), shadow_alpha=160)
        sh   = drop_shadow(sm, 6, 9, blur=4, alpha=220)
        img  = composite(sh, sl, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Side stripes
    cd = ImageDraw.Draw(canvas)
    cd.rectangle([(0, 0), (12, H)], fill=(*side, 255))
    cd.rectangle([(W - 12, 0), (W, H)], fill=(*side, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. X-games extreme ───────────────────────────────────────────────────────

def render_xgames_extreme(title: str, rng: random.Random) -> Image.Image:
    """Extreme sports — heavy distorted/sheared italic with energy splash,
    saturated electric palette, halftone fade for grit."""
    n     = len(title)
    size  = 144 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("heavy", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 14)
    shear = 0.18

    palettes = [
        ((255, 240, 0),   (220, 30, 50)),      # electric yellow on red
        ((50, 255, 200),  (40, 30, 80)),       # neon mint on indigo
        ((255, 100, 0),   (15, 20, 30)),       # electric orange on near-black
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = flat_color(mask, fg)
        # Halftone overlay for grit
        ht_layer = halftone_fill(mask, tuple(max(0, c - 100) for c in fg),
                                 dot_size=4, spacing=6)
        bev = bevel_emboss(mask, depth=5, angle_deg=120,
                           highlight_color=(255, 255, 255), highlight_alpha=200,
                           shadow_color=tuple(max(0, c - 100) for c in fg),
                           shadow_alpha=180)
        sh   = drop_shadow(mask, 6, 9, blur=3, alpha=220)
        img  = composite(sh, face, ht_layer, bev, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs) + 80
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1) + 40
    margin = 30
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Energy splash — random bright dots/sparks behind text
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(20, 40)):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        r = rng.randint(2, 6)
        cd.ellipse([x - r, y - r, x + r, y + r], fill=(*fg, rng.randint(40, 180)))

    y = margin + 20
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Olympics rings ────────────────────────────────────────────────────────

def render_olympics_rings(title: str, rng: random.Random) -> Image.Image:
    """Olympic-poster aesthetic — clean condensed sans on white, with the
    five-ring color palette appearing as small circular accents."""
    n     = len(title)
    size  = 112 if n <= 14 else (88 if n <= 24 else 70)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, (20, 22, 30))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 80
    margin_y = 90
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 40
    canvas = Image.new("RGBA", (W, H), (244, 240, 232, 255))

    # Five Olympic rings as small color dots above the title
    olympic = [(40, 130, 200), (10, 10, 14), (220, 30, 30),
               (240, 200, 30), (60, 160, 80)]
    cd = ImageDraw.Draw(canvas)
    r = 8
    spacing_rings = 28
    rings_w = spacing_rings * 4
    start_x = (W - rings_w) // 2
    ring_y = margin_y - 30
    for i, col in enumerate(olympic):
        cx = start_x + i * spacing_rings
        cd.ellipse([cx - r, ring_y - r, cx + r, ring_y + r], fill=(*col, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Motorsport carbon ─────────────────────────────────────────────────────

def render_motorsport_carbon(title: str, rng: random.Random) -> Image.Image:
    """Carbon-fiber weave background, sharp tech sans in chrome — F1 garage
    interior aesthetic."""
    n     = len(title)
    size  = 130 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("tech", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        chrome = motion_blur_chrome(mask, angle_deg=90, length=20)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125, smoothness=1.6,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(20, 20, 30), shadow_alpha=200)
        sh   = drop_shadow(mask, 0, 6, blur=10, alpha=200)
        img  = composite(sh, chrome, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (12, 14, 18, 255))

    # Carbon-fiber weave — diagonal cross-hatch
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(-W, H, 8):
        cd.line([(0, y_pos), (W, y_pos + W)],
                fill=(28, 30, 36, 200), width=1)
        cd.line([(0, y_pos + 4), (W, y_pos + 4 - W)],
                fill=(28, 30, 36, 200), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Esports tournament ────────────────────────────────────────────────────

def render_esports_tournament(title: str, rng: random.Random) -> Image.Image:
    """Modern esports broadcast graphic — angular tech sans with neon
    rim glow on near-black, geometric chevron accents."""
    n     = len(title)
    size  = 132 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("tech", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        (60, 220, 240),     # cyan
        (255, 80, 130),     # magenta
        (130, 255, 80),     # acid green
    ]
    glow = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        # Outer glow
        bloom = mask.filter(ImageFilter.GaussianBlur(10))
        glow_layer = flat_color(bloom, glow)
        glow_a = glow_layer.split()[3].point(lambda p: int(p * 0.55))
        glow_layer.putalpha(glow_a)
        face = flat_color(mask, glow)
        outline = outline_stroke(mask, width=2, rgb=(255, 255, 255), alpha=200)
        img  = composite(glow_layer, face, outline, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 80
    margin_y = 60
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2
    canvas = Image.new("RGBA", (W, H), (10, 12, 22, 255))

    # Chevron accents — angular brackets at corners
    cd = ImageDraw.Draw(canvas)
    chev = 26
    for cx, cy, dx, dy in [
        (margin_x // 2, margin_y // 2, 1, 1),
        (W - margin_x // 2, margin_y // 2, -1, 1),
        (margin_x // 2, H - margin_y // 2, 1, -1),
        (W - margin_x // 2, H - margin_y // 2, -1, -1),
    ]:
        cd.line([(cx, cy + dy * chev), (cx, cy)], fill=(*glow, 255), width=2)
        cd.line([(cx, cy), (cx + dx * chev, cy)], fill=(*glow, 255), width=2)

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Soccer kit ───────────────────────────────────────────────────────────

def render_soccer_kit(title: str, rng: random.Random) -> Image.Image:
    """European soccer kit — clean condensed sans with a colored shoulder-
    panel accent stripe, sponsor-tier crispness."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("condensed", size, rng) or F("athletic", size, rng)
    spacing = max(7, size // 16)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((240, 232, 218), (40, 50, 130),  (220, 30, 40)),    # cream on navy + red stripe
        ((40, 40, 50),    (240, 240, 240), (220, 30, 40)),   # ink on white + red stripe
        ((240, 232, 218), (40, 130, 80),  (250, 220, 30)),   # cream on green + yellow
    ]
    fg, bg, stripe = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=16)
        face = flat_color(mask, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Diagonal shoulder-panel stripe
    cd = ImageDraw.Draw(canvas)
    cd.polygon([
        (0, 0), (W // 4, 0), (0, H // 4),
    ], fill=(*stripe, 255))
    cd.polygon([
        (W, H), (W - W // 4, H), (W, H - H // 4),
    ], fill=(*stripe, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

import numpy as np  # used by render_college_varsity for split-fill array

PACK7_SPORT_TREATMENTS = {
    "nfl_crest":            render_nfl_crest,
    "mlb_jersey":           render_mlb_jersey,
    "college_varsity":      render_college_varsity,
    "racing_livery":        render_racing_livery,
    "basketball_jersey":    render_basketball_jersey,
    "xgames_extreme":       render_xgames_extreme,
    "olympics_rings":       render_olympics_rings,
    "motorsport_carbon":    render_motorsport_carbon,
    "esports_tournament":   render_esports_tournament,
    "soccer_kit":           render_soccer_kit,
}
