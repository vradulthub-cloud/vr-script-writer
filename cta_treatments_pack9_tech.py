"""
Pack 9 — Tech / Sci-fi.

Ten treatments rooted in technology and science-fiction visual languages:
HUD overlay, wireframe vector, cyberpunk neon kanji, AI ML aesthetic,
cassette futurism, vector wireframe, mainframe terminal, glitch corruption,
synthwave grid, satellite tracking.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageChops

from cta_fonts import F
from cta_primitives import (
    bevel_emboss,
    chromatic_aberration,
    colorize,
    composite,
    dilate,
    drop_shadow,
    flat_color,
    fresnel_metallic,
    halftone_fill,
    holographic_shift,
    ink_bleed,
    long_shadow,
    make_mask,
    motion_blur_chrome,
    outline_stroke,
    rule_line,
    scanlines,
    shear_image,
    wide_track_mask,
    wrap_chars,
)


# ─── 1. HUD overlay ───────────────────────────────────────────────────────────

def render_hud_overlay(title: str, rng: random.Random) -> Image.Image:
    """Heads-up display from a fighter cockpit / sci-fi helmet — thin tech
    sans, corner brackets, faint grid, single hue."""
    n     = len(title)
    size  = 110 if n <= 14 else (84 if n <= 22 else 64)
    spacing = max(10, size // 12)
    font  = F("tech", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 22)

    palettes = [(80, 240, 220),  (140, 255, 80),  (255, 200, 60),  (180, 200, 255)]
    glow = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        outline = outline_stroke(mask, width=1, rgb=glow, alpha=240)
        line_imgs.append(outline)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (8, 12, 18, 255))

    cd = ImageDraw.Draw(canvas)
    # Faint grid background
    for x in range(0, W, 28):
        cd.line([(x, 0), (x, H)], fill=(*glow, 30), width=1)
    for y in range(0, H, 28):
        cd.line([(0, y), (W, y)], fill=(*glow, 30), width=1)

    # Corner brackets
    arm = 30
    inset = 30
    for cx, cy, dx, dy in [
        (inset, inset, 1, 1),
        (W - inset, inset, -1, 1),
        (inset, H - inset, 1, -1),
        (W - inset, H - inset, -1, -1),
    ]:
        cd.line([(cx, cy), (cx + dx * arm, cy)], fill=(*glow, 220), width=2)
        cd.line([(cx, cy), (cx, cy + dy * arm)], fill=(*glow, 220), width=2)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. Cyberpunk neon kanji ──────────────────────────────────────────────────

def render_cyberpunk_neon_kanji(title: str, rng: random.Random) -> Image.Image:
    """Blade Runner / Neuromancer street-level neon — saturated rim glow on
    a wet-asphalt black background, plus simulated "neon sign katakana" stripes."""
    n     = len(title)
    size  = 132 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("tech", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((255, 80, 200),  (60, 240, 230)),    # magenta + cyan
        ((255, 60, 100),  (255, 200, 30)),    # red + amber
        ((130, 255, 80),  (255, 60, 200)),    # green + magenta
    ]
    primary, secondary = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bloom = mask.filter(ImageFilter.GaussianBlur(14))
        glow = flat_color(bloom, primary)
        glow_a = glow.split()[3].point(lambda p: int(p * 0.7))
        glow.putalpha(glow_a)
        outline = outline_stroke(mask, width=2, rgb=primary, alpha=240)
        face = flat_color(mask, (240, 240, 250))
        # Slight chromatic aberration on the white face
        layered = composite(glow, face, outline, size=mask.size)
        layered = chromatic_aberration(layered, offset=2)
        line_imgs.append(layered)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (10, 8, 18, 255))

    # Vertical neon-stripe accents on the right side (faux katakana signage)
    cd = ImageDraw.Draw(canvas)
    for i in range(rng.randint(4, 8)):
        x_pos = W - 30 - i * 6
        height = rng.randint(10, 60)
        y_pos = rng.randint(20, H - 80)
        col = secondary if i % 2 == 0 else primary
        cd.rectangle([(x_pos, y_pos), (x_pos + 2, y_pos + height)], fill=(*col, 200))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. AI / ML aesthetic ─────────────────────────────────────────────────────

def render_ai_ml_aesthetic(title: str, rng: random.Random) -> Image.Image:
    """Modern 'AI-startup' glow — thin sans + subtle iridescent rim,
    deep purple-to-blue background. Restrained, not showy."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    spacing = max(8, size // 14)
    font  = F("luxury", size, rng) or F("tech", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=22)
        # Subtle iridescent rim layer at low alpha — refined, not loud
        iri = holographic_shift(mask, hue_range=(0.55, 0.95), bands=2,
                                saturation=0.7, value=0.95)
        iri_a = iri.split()[3].point(lambda p: int(p * 0.45))
        iri.putalpha(iri_a)
        face = flat_color(mask, (240, 240, 250))
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=160,
                            shadow_color=(40, 30, 80), shadow_alpha=130)
        img  = composite(face, iri, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (18, 14, 30, 255))

    # Subtle radial gradient — fade from center
    cd = ImageDraw.Draw(canvas)
    for r in range(int(min(W, H) * 0.7), 0, -10):
        a = int(40 * r / (min(W, H) * 0.7))
        cd.ellipse([W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r],
                   outline=(60, 40, 110, a))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Cassette futurism ─────────────────────────────────────────────────────

def render_cassette_futurism(title: str, rng: random.Random) -> Image.Image:
    """Alien (1979) computer terminal aesthetic — heavy condensed sans on
    deep navy, single amber accent, pre-LCD industrial future."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("condensed", size, rng) or F("tech", size, rng)
    spacing = max(8, size // 12)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, (255, 200, 80))      # amber phosphor
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (18, 30, 50, 255))

    # Single horizontal accent rule + small status block
    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.7)
    cd.rectangle([((W - rule_w) // 2, 30), ((W + rule_w) // 2, 36)],
                 fill=(255, 200, 80, 255))

    # Faint scanlines for retro CRT feel
    canvas = scanlines(canvas, spacing=4, alpha=0.16)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Vector wireframe ──────────────────────────────────────────────────────

def render_vector_wireframe(title: str, rng: random.Random) -> Image.Image:
    """Tron / Battlezone arcade wireframe — single-color outline on deep
    perspective grid background, geometric tech sans."""
    n     = len(title)
    size  = 130 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("tech", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 16)

    glow = rng.choice([(80, 240, 240), (130, 255, 100), (255, 60, 200)])

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        outline = outline_stroke(mask, width=2, rgb=glow, alpha=255)
        line_imgs.append(outline)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 60
    canvas = Image.new("RGBA", (W, H), (6, 8, 16, 255))

    cd = ImageDraw.Draw(canvas)
    # Perspective grid: horizontal lines converging toward horizon at center
    horizon_y = int(H * 0.55)
    n_lines = 10
    for i in range(n_lines):
        y_pos = horizon_y + (H - horizon_y) * (i + 1) / n_lines
        # Lines get more saturated as they approach the viewer
        a = int(70 + 130 * (i + 1) / n_lines)
        cd.line([(0, y_pos), (W, y_pos)], fill=(*glow, a), width=1)
    # Diverging vertical lines from horizon center
    for i in range(-6, 7):
        x_end = W // 2 + i * (W // 12)
        cd.line([(W // 2, horizon_y), (x_end, H)], fill=(*glow, 80), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Mainframe terminal ────────────────────────────────────────────────────

def render_mainframe_terminal(title: str, rng: random.Random) -> Image.Image:
    """1970s mainframe printout — dot-matrix monospace feel on tractor-feed
    fanfold paper, alternating green-bar background."""
    n     = len(title)
    size  = 96 if n <= 14 else (74 if n <= 22 else 58)
    font  = F("tech", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 20)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=14)
        # Halftone fill simulating dot-matrix grain
        ht = halftone_fill(mask, (28, 28, 30), dot_size=4, spacing=5)
        line_imgs.append(ht)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))

    # Alternating green-bar fanfold rows
    cd = ImageDraw.Draw(canvas)
    bar_h = 22
    for i, by in enumerate(range(0, H, bar_h)):
        if i % 2 == 0:
            cd.rectangle([(0, by), (W, by + bar_h)], fill=(220, 232, 200, 255))

    # Simulated tractor-feed perforations along the edges
    for y_pos in range(20, H - 20, 24):
        cd.ellipse([12 - 4, y_pos - 4, 12 + 4, y_pos + 4], fill=(180, 180, 170, 255))
        cd.ellipse([W - 12 - 4, y_pos - 4, W - 12 + 4, y_pos + 4], fill=(180, 180, 170, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Glitch corruption ─────────────────────────────────────────────────────

def render_glitch_corruption(title: str, rng: random.Random) -> Image.Image:
    """Datamosh / glitch — heavy displaced RGB channels with horizontal
    band scrambles. Reads as 'broken signal'."""
    n     = len(title)
    size  = 144 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("heavy", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        face = flat_color(mask, (240, 240, 250))
        # Heavy chromatic split
        red = flat_color(mask, (255, 30, 30))
        green = flat_color(mask, (30, 255, 30))
        blue = flat_color(mask, (60, 80, 255))
        offset = rng.randint(8, 14)
        out_w = mask.size[0] + offset * 4
        out_h = mask.size[1] + offset
        canvas_rgb = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        canvas_rgb.alpha_composite(red, (0, 0))
        canvas_rgb.alpha_composite(blue, (offset * 3, offset // 2))
        canvas_rgb.alpha_composite(green, (offset, offset))
        canvas_rgb.alpha_composite(face, (offset * 2, offset // 3))
        line_imgs.append(canvas_rgb)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (8, 8, 16, 255))

    # Scrambled horizontal data bands across the canvas
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(4, 8)):
        band_y = rng.randint(0, H - 1)
        band_h = rng.randint(2, 6)
        col = rng.choice([(255, 30, 100), (30, 255, 200), (255, 200, 30)])
        cd.rectangle([(0, band_y), (W, band_y + band_h)], fill=(*col, 60))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Synthwave grid ────────────────────────────────────────────────────────

def render_synthwave_grid(title: str, rng: random.Random) -> Image.Image:
    """80s synthwave — chrome-pink-purple gradient face on perspective
    purple grid receding to neon-magenta horizon."""
    n     = len(title)
    size  = 144 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("tech", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = colorize(mask, [(255, 220, 250), (255, 100, 200), (130, 30, 200)])
        chrome = motion_blur_chrome(mask, angle_deg=90, length=18,
                                    stops=[(255, 250, 255), (255, 180, 220),
                                           (130, 60, 200), (40, 20, 80)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(40, 20, 80), shadow_alpha=180)
        sh   = drop_shadow(mask, 0, 6, blur=10, alpha=200)
        img  = composite(sh, chrome, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 80
    canvas = Image.new("RGBA", (W, H), (28, 12, 48, 255))

    # Magenta sun on horizon
    cd = ImageDraw.Draw(canvas)
    horizon_y = int(H * 0.6)
    sun_r = int(min(W, H) * 0.18)
    cd.ellipse([W // 2 - sun_r, horizon_y - sun_r, W // 2 + sun_r, horizon_y + sun_r],
               fill=(255, 80, 180, 255))

    # Perspective grid receding to horizon
    n_lines = 10
    for i in range(n_lines):
        y_pos = horizon_y + (H - horizon_y) * (i + 1) / n_lines
        a = int(80 + 175 * (i + 1) / n_lines)
        cd.line([(0, y_pos), (W, y_pos)], fill=(255, 60, 200, a), width=1)
    for i in range(-8, 9):
        x_end = W // 2 + i * (W // 16)
        cd.line([(W // 2, horizon_y), (x_end, H)], fill=(255, 60, 200, 100), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Satellite tracking ────────────────────────────────────────────────────

def render_satellite_tracking(title: str, rng: random.Random) -> Image.Image:
    """Mission-control / NORAD aesthetic — thin tech sans, tracking
    crosshairs, coordinate labels in monospace, single accent color."""
    n     = len(title)
    size  = 108 if n <= 14 else (84 if n <= 22 else 64)
    spacing = max(8, size // 12)
    font  = F("tech", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, (240, 240, 240))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (12, 18, 24, 255))

    cd = ImageDraw.Draw(canvas)
    accent = (240, 100, 60)
    # Crosshair around the title bounding box
    bb_y_top = margin - 12
    bb_y_bot = margin + text_h + 12
    arm = 22
    for cx, cy in [
        (margin - 14, bb_y_top), (W - margin + 14, bb_y_top),
        (margin - 14, bb_y_bot), (W - margin + 14, bb_y_bot),
    ]:
        cd.line([(cx - arm, cy), (cx + arm, cy)], fill=(*accent, 200), width=1)
        cd.line([(cx, cy - arm), (cx, cy + arm)], fill=(*accent, 200), width=1)

    # Mock coordinate labels in corners (small, monospace)
    cd.text((20, 20), f"LAT 34.05  LON -118.24", fill=(*accent, 220))
    cd.text((20, H - 30), f"ELEV 0089  HDG 270", fill=(*accent, 220))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Holographic packaging ────────────────────────────────────────────────

def render_holographic_packaging(title: str, rng: random.Random) -> Image.Image:
    """Mid-90s computer software box — chrome wordmark + iridescent
    holographic seal, deep gradient panel."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("tech", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        chrome = motion_blur_chrome(mask, angle_deg=90, length=22)
        # Iridescent overlay
        iri = holographic_shift(mask, hue_range=(0.5, 1.0), bands=4,
                                saturation=0.85, value=0.95)
        iri_a = iri.split()[3].point(lambda p: int(p * 0.35))
        iri.putalpha(iri_a)
        bev = bevel_emboss(mask, depth=5, angle_deg=120, smoothness=1.6,
                           highlight_color=(255, 255, 255), highlight_alpha=200,
                           shadow_color=(40, 60, 100), shadow_alpha=200)
        sh  = drop_shadow(mask, 0, 6, blur=12, alpha=200)
        img = composite(sh, chrome, iri, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (18, 24, 50, 255))

    # Subtle gradient: lighter top → darker bottom
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(H):
        a = int(60 * (1 - y_pos / H))
        cd.line([(0, y_pos), (W, y_pos)], fill=(60, 80, 140, a), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK9_TECH_TREATMENTS = {
    "hud_overlay":             render_hud_overlay,
    "cyberpunk_neon_kanji":    render_cyberpunk_neon_kanji,
    "ai_ml_aesthetic":         render_ai_ml_aesthetic,
    "cassette_futurism":       render_cassette_futurism,
    "vector_wireframe":        render_vector_wireframe,
    "mainframe_terminal":      render_mainframe_terminal,
    "glitch_corruption":       render_glitch_corruption,
    "synthwave_grid":          render_synthwave_grid,
    "satellite_tracking":      render_satellite_tracking,
    "holographic_packaging":   render_holographic_packaging,
}
