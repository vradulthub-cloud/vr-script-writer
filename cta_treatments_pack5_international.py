"""
Pack 5 — International poster schools.

Eight treatments evoking national/regional poster traditions: Russian
constructivism, Italian futurism, Polish poster school, Swiss
international, Japanese mid-century, Dutch De Stijl, Mexican mural,
Cuban silkscreen.
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
    flat_color,
    halftone_fill,
    ink_bleed,
    make_mask,
    rule_line,
    shear_image,
    wide_track_mask,
    wrap_chars,
)


# ─── 1. Russian constructivist ────────────────────────────────────────────────

def render_russian_constructivist(title: str, rng: random.Random) -> Image.Image:
    """Rodchenko / El Lissitzky 1920s — red, black, white, ultra-condensed
    sans, dramatic diagonal composition with single bold geometric element."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, (240, 232, 218))   # cream-white text
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 70
    margin_y = 70
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 30
    canvas = Image.new("RGBA", (W, H), (28, 28, 32, 255))   # near-black

    # Diagonal red wedge — constructivist signature
    cd = ImageDraw.Draw(canvas)
    cd.polygon([
        (W - 1, 0),
        (W - 1, int(H * 0.55)),
        (int(W * 0.65), 0),
    ], fill=(220, 36, 30, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, (margin_x, y), img)   # left-aligned, not centered
        y += img.height + gap
    return canvas


# ─── 2. Italian futurist ──────────────────────────────────────────────────────

def render_italian_futurist(title: str, rng: random.Random) -> Image.Image:
    """Marinetti's parolibere — type as image. Each word at a different size,
    rotation, and position; type strokes radiate energy. 1909-1930 movement."""
    n     = len(title)
    words = title.split()[:6]
    if not words:
        words = [title]

    line_imgs = []
    for w in words:
        size = rng.randint(72, 144)
        role = rng.choice(["heavy", "condensed", "slab", "athletic"])
        font = F(role, size, rng) or F("heavy", size, rng)
        mask = make_mask(w.upper(), font, pad=14)
        # Per-word saturated palette
        col = rng.choice([(220, 36, 30), (40, 30, 200), (240, 200, 40), (20, 20, 24)])
        face = flat_color(mask, col)
        # Rotate by a random angle, ±35° feels futurist not chaotic
        angle = rng.uniform(-30, 30)
        rotated = face.rotate(angle, resample=Image.BICUBIC, expand=True)
        line_imgs.append(rotated)

    # Place in a chaotic but bounded composition
    W = sum(i.width for i in line_imgs) + 80
    H = max(i.height for i in line_imgs) + 240
    canvas = Image.new("RGBA", (W, H), (244, 232, 200, 255))

    placements = []
    x_cursor = 40
    for img in line_imgs:
        ay = rng.randint(40, max(40, H - img.height - 40))
        canvas.paste(img, (x_cursor, ay), img)
        placements.append((x_cursor, ay, img.width, img.height))
        x_cursor += img.width + rng.randint(-30, 60)

    # Crop to actual content bounds with a small margin
    if placements:
        min_x = min(p[0] for p in placements) - 24
        max_x = max(p[0] + p[2] for p in placements) + 24
        min_y = min(p[1] for p in placements) - 24
        max_y = max(p[1] + p[3] for p in placements) + 24
        canvas = canvas.crop((max(0, min_x), max(0, min_y),
                              min(W, max_x), min(H, max_y)))

    return canvas


# ─── 3. Polish poster school ──────────────────────────────────────────────────

def render_polish_poster_school(title: str, rng: random.Random) -> Image.Image:
    """Cieslewicz / Trepkowski 1950s-70s — bold, painterly, conceptual.
    Single large form, hand-painted feel, restricted palette with one accent."""
    n     = len(title)
    size  = 130 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((232, 60, 30),   (240, 232, 200), (40, 40, 50)),    # red on cream
        ((60, 130, 80),   (240, 232, 200), (40, 40, 50)),    # green on cream
        ((40, 40, 50),    (220, 200, 130), (220, 60, 30)),   # ink on tan + red accent
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.4, strength=0.5, irregularity=0.7)
        face = flat_color(bled, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Single accent shape — circle behind one corner
    cd = ImageDraw.Draw(canvas)
    cr = max(40, min(W, H) // 4)
    corner = rng.choice(["tl", "tr", "br"])
    if corner == "tl":
        cd.ellipse([-cr // 2, -cr // 2, cr, cr], fill=(*accent, 255))
    elif corner == "tr":
        cd.ellipse([W - cr, -cr // 2, W + cr // 2, cr], fill=(*accent, 255))
    else:
        cd.ellipse([W - cr, H - cr, W + cr // 2, H + cr // 2], fill=(*accent, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Swiss international ───────────────────────────────────────────────────

def render_swiss_international(title: str, rng: random.Random) -> Image.Image:
    """Brockmann / Müller-Brockmann mid-century — strict grid, neutral
    grotesk, generous whitespace, single accent. Helvetica-era discipline."""
    n     = len(title)
    size  = 102 if n <= 14 else (78 if n <= 24 else 60)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 22)

    palettes = [
        ((20, 22, 28),    (240, 240, 240), (220, 36, 30)),   # ink on white + red
        ((240, 240, 240), (28, 30, 36),    (220, 36, 30)),   # white on near-black + red
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=14)
        face = flat_color(mask, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 100
    margin_y = 110
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Single horizontal accent rule, top of grid block
    cd = ImageDraw.Draw(canvas)
    cd.rectangle([(margin_x, margin_y - 30), (margin_x + 8, margin_y - 10)], fill=(*accent, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, (margin_x, y), img)   # left-aligned to grid
        y += img.height + gap
    return canvas


# ─── 5. Japanese mid-century ──────────────────────────────────────────────────

def render_japanese_midcentury(title: str, rng: random.Random) -> Image.Image:
    """Tanaka / Yokoo 1960s — restrained palette (warm white, indigo, vermilion),
    asymmetric composition, single bold accent. Quiet authority."""
    n     = len(title)
    size  = 110 if n <= 14 else (84 if n <= 22 else 64)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((30, 40, 100),   (244, 234, 220), (200, 50, 40)),   # indigo/warm-white/vermilion
        ((200, 50, 40),   (244, 234, 220), (30, 40, 100)),   # vermilion/warm-white/indigo
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 90
    margin_y = 90
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 50
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Single hinomaru-style accent circle
    cd = ImageDraw.Draw(canvas)
    cr = max(36, min(W, H) // 8)
    cx = margin_x // 2
    cy = margin_y - 12
    cd.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(*accent, 255))

    y = margin_y + 10
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Dutch De Stijl ────────────────────────────────────────────────────────

def render_dutch_de_stijl(title: str, rng: random.Random) -> Image.Image:
    """Mondrian / Van Doesburg — primary colors (red/yellow/blue), heavy
    black grid lines, white background, geometric purity."""
    n     = len(title)
    size  = 112 if n <= 14 else (84 if n <= 22 else 66)
    font  = F("heavy", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 20)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=14)
        face = flat_color(mask, (20, 20, 24))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))

    cd = ImageDraw.Draw(canvas)
    # De Stijl grid — heavy black rules with one or two colored panels
    line_w = 8
    # One vertical and one horizontal heavy line forming the grid asymmetry
    vx = rng.randint(int(W * 0.18), int(W * 0.32))
    hy = rng.randint(int(H * 0.18), int(H * 0.32))
    cd.rectangle([(vx - line_w // 2, 0), (vx + line_w // 2, H)], fill=(20, 20, 24, 255))
    cd.rectangle([(0, hy - line_w // 2), (W, hy + line_w // 2)], fill=(20, 20, 24, 255))

    # One colored panel filling a cell
    primaries = [(220, 36, 30), (240, 200, 40), (40, 60, 200)]
    panel_col = rng.choice(primaries)
    cd.rectangle([(0, 0), (vx - line_w // 2, hy - line_w // 2)], fill=(*panel_col, 255))

    # Outer black frame
    cd.rectangle([(0, 0), (W - 1, line_w)], fill=(20, 20, 24, 255))
    cd.rectangle([(0, H - line_w), (W - 1, H - 1)], fill=(20, 20, 24, 255))
    cd.rectangle([(0, 0), (line_w, H - 1)], fill=(20, 20, 24, 255))
    cd.rectangle([(W - line_w, 0), (W - 1, H - 1)], fill=(20, 20, 24, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Mexican mural ─────────────────────────────────────────────────────────

def render_mexican_mural(title: str, rng: random.Random) -> Image.Image:
    """Diego Rivera / Siqueiros mural energy — earthy ochres + saturated
    cobalt, heavy slab type, distress that reads as paint-on-plaster."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 78)
    font  = F("slab", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((232, 168, 30),  (40, 60, 130),    (140, 60, 30)),   # ochre on cobalt + sienna
        ((220, 60, 40),   (220, 198, 150),  (40, 60, 130)),   # vermilion on tan + cobalt
        ((230, 200, 130), (110, 50, 30),    (40, 60, 130)),   # sand on rust + cobalt
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        worn = ink_bleed(mask, radius=1.6, strength=0.55, irregularity=0.85)
        face = flat_color(worn, fg)
        bev  = bevel_emboss(worn, depth=4, angle_deg=125,
                            highlight_color=(255, 248, 220), highlight_alpha=140,
                            shadow_color=tuple(max(0, c - 60) for c in fg),
                            shadow_alpha=140)
        img  = composite(face, bev, size=worn.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Plaster speckle — base background grain
    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 220):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(*accent, rng.randint(20, 70)))

    # Single accent rule — heavy bottom band
    cd.rectangle([(margin, H - margin // 2 - 12), (W - margin, H - margin // 2)],
                 fill=(*accent, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Cuban silkscreen ──────────────────────────────────────────────────────

def render_cuban_silkscreen(title: str, rng: random.Random) -> Image.Image:
    """OSPAAAL-era Cuban poster — flat saturated color, halftone overlay,
    bold sans, slight registration imperfection. Revolutionary screenprint."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((250, 220, 30),  (220, 30, 60),    (40, 60, 200)),   # yellow/red/blue
        ((240, 60, 100),  (40, 200, 220),   (240, 230, 200)), # pink/teal/cream
        ((40, 200, 160),  (250, 200, 30),   (200, 30, 100)),  # mint/gold/magenta
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = flat_color(mask, fg)
        # Halftone overlay shifted slightly for misregistration feel
        ht_layer = halftone_fill(mask, accent, dot_size=4, spacing=7)
        # Registration offset: paste accent layer at slight offset
        out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        out.alpha_composite(face, (0, 0))
        out.alpha_composite(ht_layer, (rng.randint(-3, 3), rng.randint(-3, 3)))
        line_imgs.append(out)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK5_INTERNATIONAL_TREATMENTS = {
    "russian_constructivist":  render_russian_constructivist,
    "italian_futurist":        render_italian_futurist,
    "polish_poster_school":    render_polish_poster_school,
    "swiss_international":     render_swiss_international,
    "japanese_midcentury":     render_japanese_midcentury,
    "dutch_de_stijl":          render_dutch_de_stijl,
    "mexican_mural":           render_mexican_mural,
    "cuban_silkscreen":        render_cuban_silkscreen,
}
