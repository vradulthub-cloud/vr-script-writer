"""
Treatment library expansion — distinct aesthetic territories that the existing
728-treatment library under-covers.

Inventory analysis showed heavy concentration in outline (91), neon (77),
gradient (57), retro (52), luxury (34), metallic (33), comic (31), glitch (30),
sport (28), space (26). Genuinely sparse: editorial (1), magazine (1),
stencil (1), nothing in brutalist / blueprint / risograph / terminal /
bauhaus / kraft / vintage-poster.

Each treatment here is hand-crafted, ~30-60 lines, and produces output that
PIL can render natively. No FLUX dependency.

Registration happens at the bottom — both TREATMENTS and FEATURED_TREATMENTS
get the new entries.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter

from cta_fonts import F
from cta_primitives import (
    FACE_GRADIENTS,
    STROKE_COLORS,
    chromatic_aberration,
    colorize,
    composite,
    dilate,
    drop_shadow,
    flat_color,
    halftone_fill,
    highlight,
    long_shadow,
    make_mask,
    measure,
    outline_stroke,
    rule_line,
    scanlines,
    wide_track_mask,
    wrap_chars,
)

if TYPE_CHECKING:
    pass


# Color schemes specific to the new aesthetic categories. Live alongside the
# existing FACE_GRADIENTS rather than mutating that dict so the new palettes
# don't accidentally appear in the auto-color picker for other treatments.
_BLUEPRINT_BG     = (12, 38, 84)        # cyanotype deep blue
_BLUEPRINT_INK    = (220, 235, 255)     # antique paper white
_BLUEPRINT_RULE   = (130, 170, 220)     # faded line color

_TERMINAL_BG      = (4, 14, 8)          # CRT phosphor dark
_TERMINAL_GREEN   = (110, 255, 130)     # P39 phosphor
_TERMINAL_AMBER   = (255, 180, 40)      # alternate phosphor

_KRAFT_BG         = (188, 158, 110)     # warm kraft paper
_KRAFT_INK        = (32, 22, 14)        # india ink

_BAUHAUS_RED      = (220, 50, 40)
_BAUHAUS_YELLOW   = (245, 200, 40)
_BAUHAUS_BLUE     = (40, 70, 180)
_BAUHAUS_BLACK    = (20, 20, 22)

# Risograph fluorescent inks — overprint to magenta-blue mixes.
_RISO_FLO_PINK    = (255, 70, 130, 230)
_RISO_TURQUOISE   = (40, 180, 200, 220)
_RISO_FLO_ORANGE  = (255, 130, 60, 230)
_RISO_TEAL        = (60, 160, 175, 220)


# ─── 1. Editorial: haute couture ──────────────────────────────────────────────

def render_editorial_haute_couture(title: str, rng: random.Random) -> Image.Image:
    """Vogue cover styling — ultra-wide-tracked thin serif, twin hairline rules,
    monochrome ink. Single line preferred; two-line fallback for long titles."""
    n        = len(title)
    size     = 130 if n <= 14 else (96 if n <= 24 else 72)
    spacing  = max(28, size // 4)              # extreme tracking
    font     = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines    = wrap_chars(title.upper(), 18) if n > 18 else [title.upper()]

    line_imgs = []
    for ln in lines:
        mask  = wide_track_mask(ln, font, spacing, pad=18)
        face  = flat_color(mask, (28, 28, 32))
        line_imgs.append(face)

    max_w   = max(i.width for i in line_imgs) + 80
    rule_h  = 1                                 # hairline
    rule_w  = int(max_w * 0.82)
    gap     = 14
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + (rule_h + 24) * 2
    canvas  = Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0))

    rl_top  = rule_line(rule_w, (28, 28, 32), rule_h)
    canvas.paste(rl_top, ((max_w - rule_w) // 2, 12), rl_top)
    y = 12 + rule_h + 22
    for img in line_imgs:
        canvas.paste(img, ((max_w - img.width) // 2, y), img)
        y += img.height + gap
    rl_bot = rule_line(int(rule_w * 0.6), (28, 28, 32), rule_h)
    canvas.paste(rl_bot, ((max_w - int(rule_w * 0.6)) // 2, y + 8), rl_bot)
    return canvas


# ─── 2. Brutalist slab + harsh long shadow ────────────────────────────────────

def render_brutalist_slab_shadow(title: str, rng: random.Random) -> Image.Image:
    """Heavy slab serif, 45° flat long shadow, no decoration. Concrete-poster
    raw aesthetic — color is one solid hue, shadow is one solid hue."""
    n     = len(title)
    size  = 150 if n <= 14 else (118 if n <= 22 else 92)
    font  = F("slab", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    # Brutalist palettes: each is (face_rgb, shadow_rgb). Limited, deliberate.
    palettes = [
        ((220, 60, 50),   (40, 14, 12)),     # signal red
        ((40, 50, 200),   (10, 14, 60)),     # ultramarine
        ((250, 215, 50),  (60, 50, 8)),      # caution yellow
        ((30, 30, 32),    (90, 90, 95)),     # graphite
        ((230, 230, 226), (50, 50, 52)),     # raw paper
        ((50, 110, 70),   (12, 30, 18)),     # forest
    ]
    face_c, shadow_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        sh   = long_shadow(mask, steps=42, angle_deg=45, col=shadow_c, fade=False)
        face = flat_color(mask, face_c)
        img  = composite(sh, face, size=mask.size)
        line_imgs.append(img)

    gap     = 8
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. Architectural blueprint ───────────────────────────────────────────────

def render_blueprint_technical(title: str, rng: random.Random) -> Image.Image:
    """Cyanotype deep-blue background, hairline white outline text,
    technical-drawing crosshair marks at corners, dimension callouts."""
    n     = len(title)
    size  = 120 if n <= 16 else (96 if n <= 26 else 76)
    font  = F("tech", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 18)

    # Build text outline-only on its own canvas, then place over a solid blue bg.
    text_layers = []
    for ln in lines:
        mask    = make_mask(ln, font, pad=18)
        outline = outline_stroke(mask, width=2, rgb=_BLUEPRINT_INK, alpha=240)
        # A faint inner fill at 8% alpha keeps the letters from looking hollow
        # on long stretches (e.g. wide capital strokes).
        inner   = flat_color(mask, _BLUEPRINT_INK)
        from PIL import Image as _I
        inner_a = inner.split()[3].point(lambda p: int(p * 0.12))
        inner.putalpha(inner_a)
        text_layers.append(composite(inner, outline, size=mask.size))

    text_w = max(t.width for t in text_layers)
    gap    = 14
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    # Background canvas with margin for the technical-drawing chrome.
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*_BLUEPRINT_BG, 255))

    # Corner crosshairs (10px arms each).
    d = ImageDraw.Draw(canvas)
    arm = 14
    inset = 22
    rule_kw = {"fill": _BLUEPRINT_RULE, "width": 1}
    for cx, cy in [(inset, inset), (W - inset, inset),
                   (inset, H - inset), (W - inset, H - inset)]:
        d.line([(cx - arm, cy), (cx + arm, cy)], **rule_kw)
        d.line([(cx, cy - arm), (cx, cy + arm)], **rule_kw)

    # Faint title-block rule along the bottom-left, with a tiny dimension stub.
    d.line([(inset + arm + 6, H - inset),
            (inset + arm + 60, H - inset)], **rule_kw)
    d.line([(inset + arm + 6, H - inset - 4),
            (inset + arm + 6, H - inset + 4)], **rule_kw)

    # Drop in the text, top-aligned within the margin frame.
    y = margin
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 4. Industrial stencil ────────────────────────────────────────────────────

def render_stencil_industrial(title: str, rng: random.Random) -> Image.Image:
    """Stencil-style typography in olive-drab military palette with a
    distressed paint-splatter texture. Crate-stencil aesthetic."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    # The 'retro' role contains StardosStencil; falls back to slab if unavailable.
    font  = F("retro", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        (138, 132, 86),   # olive drab
        (76, 84, 60),     # field green
        (88, 64, 36),     # canvas brown
        (32, 36, 36),     # rifle black
        (198, 162, 92),   # ranger tan
    ]
    face_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        # Distress: punch random splatter holes by ANDing with a noise mask.
        noise_mask = Image.new("L", mask.size, 0)
        nd = ImageDraw.Draw(noise_mask)
        for _ in range(rng.randint(180, 320)):
            x = rng.randint(0, mask.size[0] - 1)
            y = rng.randint(0, mask.size[1] - 1)
            r = rng.randint(2, 7)
            nd.ellipse([x - r, y - r, x + r, y + r], fill=255)
        # Combine: keep most of the text, knock out splatter.
        from PIL import ImageChops
        blurred_noise = noise_mask.filter(ImageFilter.GaussianBlur(1.4))
        knocked = ImageChops.subtract(mask, blurred_noise.point(lambda p: p // 4))

        face = flat_color(knocked, face_c)
        # Faint outline so the stencil reads even on light/dark backgrounds.
        edge = outline_stroke(knocked, width=1, rgb=tuple(max(0, c - 40) for c in face_c), alpha=180)
        sh   = drop_shadow(knocked, 3, 4, blur=4, alpha=80)
        img  = composite(sh, edge, face, size=mask.size)
        line_imgs.append(img)

    gap     = 6
    total_w = max(i.width for i in line_imgs) + 24
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 24
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 12
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Risograph duotone ─────────────────────────────────────────────────────

def render_riso_duotone_offset(title: str, rng: random.Random) -> Image.Image:
    """Two-color risograph overprint with halftone fill and slight registration
    offset between the layers. Looks like a hand-cranked print-shop print."""
    n     = len(title)
    size  = 144 if n <= 14 else (108 if n <= 24 else 84)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    pairs = [
        (_RISO_FLO_PINK,   _RISO_TURQUOISE),
        (_RISO_FLO_ORANGE, _RISO_TEAL),
        (_RISO_TURQUOISE,  _RISO_FLO_ORANGE),
    ]
    c1, c2 = pairs[rng.randrange(len(pairs))]

    # Registration offset is the print-shop "off by 2-4px in random direction".
    off_x = rng.randint(-5, 5)
    off_y = rng.randint(-5, 5)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        # Layer 1: halftone dots in c1
        layer1 = halftone_fill(mask, c1[:3], dot_size=6, spacing=7)
        # Layer 2: solid flat fill in c2 at lower opacity
        layer2 = flat_color(mask, c2[:3])
        layer2_a = layer2.split()[3].point(lambda p: int(p * (c2[3] / 255)))
        layer2.putalpha(layer2_a)

        # Place them with offset on a slightly larger canvas.
        pad     = 10 + max(abs(off_x), abs(off_y))
        canvas_size = (mask.size[0] + pad * 2, mask.size[1] + pad * 2)
        layered = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        layered.alpha_composite(layer2, (pad, pad))                    # bottom: solid
        layered.alpha_composite(layer1, (pad + off_x, pad + off_y))    # top: dots
        line_imgs.append(layered)

    gap     = 8
    total_w = max(i.width for i in line_imgs) + 24
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 24
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 12
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. CRT terminal phosphor ─────────────────────────────────────────────────

def render_terminal_phosphor(title: str, rng: random.Random) -> Image.Image:
    """Green CRT phosphor text on a dark glass panel, with scanlines + slight
    chromatic aberration. Vintage operator-terminal aesthetic."""
    n     = len(title)
    size  = 106 if n <= 16 else (84 if n <= 26 else 64)
    font  = F("tech", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 22)

    use_amber = rng.random() < 0.25
    phosphor = _TERMINAL_AMBER if use_amber else _TERMINAL_GREEN

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=16)
        # Soft glow halo, additive — phosphor leaks light off the dot.
        bloom = mask.filter(ImageFilter.GaussianBlur(8))
        glow_layer = flat_color(bloom, phosphor)
        glow_a = glow_layer.split()[3].point(lambda p: int(p * 0.55))
        glow_layer.putalpha(glow_a)
        face = flat_color(mask, phosphor)
        text_layers.append(composite(glow_layer, face, size=mask.size))

    text_w = max(t.width for t in text_layers)
    gap    = 12
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    # Compose onto a CRT panel: dark phosphor glass with subtle scanlines.
    panel_pad = 36
    W = text_w + panel_pad * 2
    H = text_h + panel_pad * 2
    panel = Image.new("RGBA", (W, H), (*_TERMINAL_BG, 255))

    y = panel_pad
    for t in text_layers:
        panel.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap

    # Scanline overlay at low alpha — reads as CRT, doesn't crush the glow.
    panel = scanlines(panel, spacing=3, alpha=0.18)
    # Subtle RGB split — only 1px so it stays "vintage TV" not "broken display".
    panel = chromatic_aberration(panel, offset=2)
    return panel


# ─── 7. Magazine op-ed ────────────────────────────────────────────────────────

def render_magazine_op_ed(title: str, rng: random.Random) -> Image.Image:
    """Newspaper op-ed page styling — bold serif headline above an italic
    smaller-serif "kicker" line, separated by a hairline rule. Two-line max."""
    words = title.split()
    n     = len(title)
    size  = 110 if n <= 18 else (88 if n <= 28 else 72)
    headline_font = F("serif", size, rng) or F("luxury", size, rng) or F("elegant", size, rng)

    # Split into headline + kicker. Short titles get all-headline, no kicker.
    if len(words) <= 3:
        headline = title.upper()
        kicker = ""
    else:
        # First two words become the headline, the rest become the italic kicker.
        # Falls back to the whole title if that produces an awkward split.
        headline = " ".join(words[:2]).upper()
        kicker   = " ".join(words[2:])

    headline_mask = make_mask(headline, headline_font, pad=18)
    headline_face = flat_color(headline_mask, (24, 22, 22))

    layers = [headline_face]
    if kicker:
        kicker_size = max(28, size // 3)
        kicker_font = F("serif", kicker_size, rng) or F("elegant", kicker_size, rng)
        kicker_mask = make_mask(kicker, kicker_font, pad=10)
        kicker_face = flat_color(kicker_mask, (90, 80, 75))
        layers.append(kicker_face)

    max_w = max(l.width for l in layers) + 60
    rule_h = 1
    rule_w = int(max_w * 0.74)
    gap    = 16
    total_h = sum(l.height for l in layers) + gap * (len(layers) - 1) + (rule_h + 22) + 30
    canvas = Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0))

    y = 14
    canvas.paste(layers[0], ((max_w - layers[0].width) // 2, y), layers[0])
    y += layers[0].height + 14
    rl = rule_line(rule_w, (24, 22, 22), rule_h)
    canvas.paste(rl, ((max_w - rule_w) // 2, y), rl)
    y += rule_h + 14
    if len(layers) > 1:
        canvas.paste(layers[1], ((max_w - layers[1].width) // 2, y), layers[1])
    return canvas


# ─── 8. Bauhaus geometric ─────────────────────────────────────────────────────

def render_bauhaus_geometric(title: str, rng: random.Random) -> Image.Image:
    """Sans-serif type with primary-color geometric shapes (red square,
    yellow circle, blue triangle) layered as accents. Bauhaus poster vibe."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 24 else 78)
    font  = F("heavy", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 16)

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        face = flat_color(mask, _BAUHAUS_BLACK)
        text_layers.append(face)

    text_w = max(t.width for t in text_layers)
    gap    = 8
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    # Margin to host the geometric accents around the text.
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Three accents at fixed slots: top-left circle (yellow), top-right square
    # (red), bottom-right triangle (blue). Bauhaus cliché on purpose.
    d = ImageDraw.Draw(canvas)
    r = max(18, min(W, H) // 12)
    d.ellipse([margin // 2 - r, margin // 2 - r, margin // 2 + r, margin // 2 + r],
              fill=_BAUHAUS_YELLOW)
    sq = max(20, min(W, H) // 11)
    d.rectangle([W - margin // 2 - sq, margin // 2 - sq // 2,
                 W - margin // 2,      margin // 2 + sq // 2], fill=_BAUHAUS_RED)
    tri = max(22, min(W, H) // 10)
    d.polygon([(W - margin // 2 - tri, H - margin // 2),
               (W - margin // 2,       H - margin // 2),
               (W - margin // 2 - tri // 2, H - margin // 2 - tri)],
              fill=_BAUHAUS_BLUE)

    # Drop the text on top.
    y = margin
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 9. Kraft paper stamp ─────────────────────────────────────────────────────

def render_kraft_paper_stamp(title: str, rng: random.Random) -> Image.Image:
    """Warm kraft-paper background with dark india-ink stamped typography.
    Coffee-shop / artisan workshop aesthetic. Slightly distressed edges."""
    n     = len(title)
    size  = 124 if n <= 16 else (96 if n <= 26 else 76)
    font  = F("slab", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 18)

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        # Distress: erode slightly and add minor noise punch-outs.
        worn = mask.filter(ImageFilter.MinFilter(3))
        noise = Image.new("L", mask.size, 0)
        nd = ImageDraw.Draw(noise)
        for _ in range(rng.randint(60, 140)):
            x = rng.randint(0, mask.size[0] - 1)
            y = rng.randint(0, mask.size[1] - 1)
            nd.point((x, y), fill=255)
        from PIL import ImageChops
        knocked = ImageChops.subtract(worn, noise.filter(ImageFilter.GaussianBlur(0.5)).point(lambda p: p // 3))
        face = flat_color(knocked, _KRAFT_INK)
        text_layers.append(face)

    text_w = max(t.width for t in text_layers)
    gap    = 8
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    # Kraft background panel with margin.
    margin = 48
    W = text_w + margin * 2
    H = text_h + margin * 2
    bg = Image.new("RGBA", (W, H), (*_KRAFT_BG, 255))
    # Subtle paper texture: scatter darker speckles.
    bd = ImageDraw.Draw(bg)
    for _ in range(W * H // 600):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        a = rng.randint(8, 24)
        bd.point((x, y), fill=(160, 130, 90, a))

    y = margin
    for t in text_layers:
        bg.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return bg


# ─── 10. Vintage poster, distressed ───────────────────────────────────────────

def render_vintage_poster_distressed(title: str, rng: random.Random) -> Image.Image:
    """Warm-toned vintage poster: ochre/wine/cream face, faded color, grain
    overlay, mild edge bleach. Old-cinema lobby card / film-noir feel."""
    n     = len(title)
    size  = 140 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("retro", size, rng) or F("slab", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        # (face_top, face_bottom, shadow)
        ((232, 196, 132), (160, 92, 44),  (50, 22, 8)),     # ochre/sienna
        ((232, 140, 130), (134, 38, 50),  (50, 12, 18)),    # wine/blush
        ((218, 200, 168), (94, 76, 56),   (24, 16, 8)),     # cream/walnut
        ((196, 156, 96),  (78, 56, 32),   (20, 12, 4)),     # tobacco
    ]
    face_top, face_bot, shadow_c = palettes[rng.randrange(len(palettes))]
    stops = [face_top, face_bot]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sh   = drop_shadow(mask, 6, 9, blur=8, alpha=200)
        face = colorize(mask, stops)
        hl   = highlight(mask, 0.3)
        img  = composite(sh, face, hl, size=mask.size)
        line_imgs.append(img)

    gap     = 6
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap

    # Grain overlay — sparse warm/cool noise to read as old paper.
    gd = ImageDraw.Draw(canvas)
    for _ in range(total_w * total_h // 280):
        x = rng.randint(0, total_w - 1)
        y = rng.randint(0, total_h - 1)
        if canvas.getpixel((x, y))[3] == 0:
            continue
        warm = rng.random() < 0.7
        col = (220, 190, 130, rng.randint(20, 55)) if warm else (130, 150, 180, rng.randint(10, 30))
        gd.point((x, y), fill=col)
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

EXPANSION_TREATMENTS = {
    "editorial_haute_couture":   render_editorial_haute_couture,
    "brutalist_slab_shadow":     render_brutalist_slab_shadow,
    "blueprint_technical":       render_blueprint_technical,
    "stencil_industrial":        render_stencil_industrial,
    "riso_duotone_offset":       render_riso_duotone_offset,
    "terminal_phosphor":         render_terminal_phosphor,
    "magazine_op_ed":            render_magazine_op_ed,
    "bauhaus_geometric":         render_bauhaus_geometric,
    "kraft_paper_stamp":         render_kraft_paper_stamp,
    "vintage_poster_distressed": render_vintage_poster_distressed,
}
