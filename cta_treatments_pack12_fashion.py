"""
Pack 12 — Fashion / luxury brand archetypes.

Ten treatments evoking high-end fashion and luxury brand conventions:
fashion masthead, hermes orange, chanel serif, ysl minimal, gucci emboss,
dior couture, perfume bottle, runway caption, glossy magazine, jewelry box.
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


# ─── 1. Fashion masthead ──────────────────────────────────────────────────────

def render_fashion_masthead(title: str, rng: random.Random) -> Image.Image:
    """Fashion magazine cover masthead — heavy contrast didone serif on
    cream, cap-height tight tracking. The classic masthead silhouette."""
    n     = len(title)
    size  = 158 if n <= 12 else (124 if n <= 20 else 96)
    font  = F("luxury", size, rng) or F("serif", size, rng) or F("elegant", size, rng)
    spacing = 0
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=20)
        face = flat_color(mask, (20, 18, 22))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 232, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. Hermès orange ─────────────────────────────────────────────────────────

def render_hermes_orange(title: str, rng: random.Random) -> Image.Image:
    """Hermès aesthetic — refined slab serif in deep brown on signature
    saturated orange, tight kerning, restrained dignity."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    spacing = max(6, size // 18)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, (60, 30, 14))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (240, 110, 30, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. Chanel serif ──────────────────────────────────────────────────────────

def render_chanel_serif(title: str, rng: random.Random) -> Image.Image:
    """Chanel-aesthetic minimalism — refined didone in pure black on pure
    white, generous tracking, single thin rule above and below."""
    n     = len(title)
    size  = 110 if n <= 14 else (84 if n <= 24 else 64)
    spacing = max(14, size // 8)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=16)
        face = flat_color(mask, (16, 16, 18))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 100
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (250, 250, 248, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.42)
    rx_l = (W - rule_w) // 2
    rx_r = rx_l + rule_w
    cd.line([(rx_l, margin // 2 - 4), (rx_r, margin // 2 - 4)], fill=(16, 16, 18, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([(rx_l, y + 14), (rx_r, y + 14)], fill=(16, 16, 18, 255), width=1)
    return canvas


# ─── 4. YSL minimal ───────────────────────────────────────────────────────────

def render_ysl_minimal(title: str, rng: random.Random) -> Image.Image:
    """Yves Saint Laurent style — pure black wordmark on pure black, subtle
    high-gloss reflective sheen on the type. All-black-on-black power move."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    spacing = max(10, size // 12)
    font  = F("luxury", size, rng) or F("serif", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=20)
        face = flat_color(mask, (20, 20, 22))
        # Subtle metallic sheen — Fresnel rim brightens edges
        rim = fresnel_metallic(mask, base_color=(40, 40, 44),
                               rim_color=(150, 150, 160), rim_power=2.4)
        rim_a = rim.split()[3].point(lambda p: int(p * 0.6))
        rim.putalpha(rim_a)
        bev = bevel_emboss(mask, depth=4, angle_deg=120,
                           highlight_color=(120, 120, 130), highlight_alpha=160,
                           shadow_color=(8, 8, 10), shadow_alpha=180)
        img = composite(face, bev, rim, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (12, 12, 14, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Gucci emboss ──────────────────────────────────────────────────────────

def render_gucci_emboss(title: str, rng: random.Random) -> Image.Image:
    """Italian luxury house emboss — gold-foil-stamped serif on rich
    burgundy/forest leather. Heavy bevel and Fresnel."""
    n     = len(title)
    size  = 128 if n <= 14 else (100 if n <= 22 else 78)
    spacing = max(7, size // 16)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        (60, 24, 30),     # burgundy
        (28, 50, 38),     # forest
        (40, 30, 20),     # espresso
    ]
    bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = colorize(mask, [(255, 240, 180), (220, 180, 60), (130, 90, 20)])
        bev  = bevel_emboss(mask, depth=5, angle_deg=120,
                            highlight_color=(255, 250, 220), highlight_alpha=220,
                            shadow_color=(60, 30, 8), shadow_alpha=200)
        rim  = fresnel_metallic(mask, base_color=(220, 180, 60),
                                rim_color=(255, 230, 160), rim_power=2.6)
        rim_a = rim.split()[3].point(lambda p: int(p * 0.5))
        rim.putalpha(rim_a)
        sh   = drop_shadow(mask, 2, 5, blur=6, alpha=200)
        img  = composite(sh, face, bev, rim, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Faint leather-grain speckle
    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 220):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(*tuple(min(255, c + 30) for c in bg), rng.randint(20, 60)))

    # Decorative rule top + bottom in gold
    rule_w = int(W * 0.6)
    cd.line([((W - rule_w) // 2, 30), ((W + rule_w) // 2, 30)],
            fill=(220, 180, 60, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([((W - rule_w) // 2, y + 14), ((W + rule_w) // 2, y + 14)],
            fill=(220, 180, 60, 255), width=1)
    return canvas


# ─── 6. Dior couture ──────────────────────────────────────────────────────────

def render_dior_couture(title: str, rng: random.Random) -> Image.Image:
    """Couture house cover — extra-thin all-caps wordmark + extreme
    tracking, on cream. The 'whisper' end of luxury."""
    n     = len(title)
    size  = 120 if n <= 14 else (94 if n <= 24 else 72)
    spacing = max(20, size // 5)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        outline = outline_stroke(mask, width=1, rgb=(20, 18, 22), alpha=255)
        line_imgs.append(outline)

    text_w = max(t.width for t in line_imgs)
    gap    = 14
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 110
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 232, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Perfume bottle ────────────────────────────────────────────────────────

def render_perfume_bottle(title: str, rng: random.Random) -> Image.Image:
    """Perfume bottle label — small refined serif in metallic ink on a
    blush/cream gradient panel. Soft, intimate, luxurious."""
    n     = len(title)
    size  = 100 if n <= 14 else (76 if n <= 24 else 60)
    spacing = max(12, size // 8)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = colorize(mask, [(220, 168, 100), (160, 80, 50)])
        bev  = bevel_emboss(mask, depth=2, angle_deg=120,
                            highlight_color=(255, 240, 220), highlight_alpha=140,
                            shadow_color=(80, 30, 30), shadow_alpha=130)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 90
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Blush gradient backdrop
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        r = int(252 - 30 * t)
        g = int(232 - 50 * t)
        b = int(218 - 30 * t)
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    # Small thin rule
    rule_w = int(W * 0.16)
    cd.line([((W - rule_w) // 2, 36), ((W + rule_w) // 2, 36)],
            fill=(160, 80, 50, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Runway caption ────────────────────────────────────────────────────────

def render_runway_caption(title: str, rng: random.Random) -> Image.Image:
    """Catwalk show subtitle — small all-caps grotesk in bright accent
    color on a single horizontal accent bar. Direct, declarative."""
    n     = len(title)
    size  = 96 if n <= 14 else (74 if n <= 24 else 60)
    spacing = max(8, size // 12)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 22)

    palettes = [
        ((20, 22, 26),    (240, 240, 240), (220, 30, 60)),    # ink/white/coral
        ((240, 240, 240), (28, 30, 36),    (250, 220, 30)),
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
    margin_x = 100
    margin_y = 90
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    # Heavy single horizontal accent bar above the title
    cd.rectangle([(margin_x, margin_y - 30), (margin_x + 80, margin_y - 18)],
                 fill=(*accent, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, (margin_x, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Glossy magazine ───────────────────────────────────────────────────────

def render_glossy_magazine(title: str, rng: random.Random) -> Image.Image:
    """Glossy fashion editorial — heavy didone with chrome motion-blur
    reflection, on a deep magenta/oxblood gradient backdrop."""
    n     = len(title)
    size  = 144 if n <= 12 else (110 if n <= 20 else 86)
    font  = F("luxury", size, rng) or F("serif", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        chrome = motion_blur_chrome(mask, angle_deg=90, length=20)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(30, 18, 30), shadow_alpha=200)
        sh   = drop_shadow(mask, 0, 8, blur=14, alpha=200)
        img  = composite(sh, chrome, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Magenta-oxblood gradient
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        r = int(160 - 100 * t)
        g = int(40 - 30 * t)
        b = int(80 - 60 * t)
        cd.line([(0, y_pos), (W, y_pos)], fill=(max(0, r), max(0, g), max(0, b), 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Jewelry box ──────────────────────────────────────────────────────────

def render_jewelry_box(title: str, rng: random.Random) -> Image.Image:
    """Tiffany / Cartier jewelry box lid — small wordmark in metallic ink
    on a velvet-textured deep panel, double thin gold rule frame."""
    n     = len(title)
    size  = 96 if n <= 14 else (76 if n <= 24 else 60)
    spacing = max(14, size // 8)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 22)

    palettes = [
        ((30, 80, 80),    (220, 220, 230)),    # tiffany teal + silver
        ((50, 22, 30),    (220, 180, 60)),     # oxblood + gold
    ]
    bg, ink = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, ink)
        bev  = bevel_emboss(mask, depth=2, angle_deg=120,
                            highlight_color=tuple(min(255, c + 40) for c in ink),
                            highlight_alpha=140,
                            shadow_color=tuple(max(0, c - 60) for c in ink),
                            shadow_alpha=130)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Velvet speckle
    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 350):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(*tuple(min(255, c + 18) for c in bg), rng.randint(40, 120)))

    # Double thin frame
    cd.rectangle([(20, 20), (W - 20, H - 20)], outline=(*ink, 200), width=1)
    cd.rectangle([(28, 28), (W - 28, H - 28)], outline=(*ink, 160), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK12_FASHION_TREATMENTS = {
    "fashion_masthead":   render_fashion_masthead,
    "hermes_orange":      render_hermes_orange,
    "chanel_serif":       render_chanel_serif,
    "ysl_minimal":        render_ysl_minimal,
    "gucci_emboss":       render_gucci_emboss,
    "dior_couture":       render_dior_couture,
    "perfume_bottle":     render_perfume_bottle,
    "runway_caption":     render_runway_caption,
    "glossy_magazine":    render_glossy_magazine,
    "jewelry_box":        render_jewelry_box,
}
