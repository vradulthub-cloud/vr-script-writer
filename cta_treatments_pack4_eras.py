"""
Pack 4 — Era pastiche.

Ten treatments paying tribute to specific design moments: Saul Bass 1950s
title cards, Push Pin Studios mid-60s NYC, WPA Depression-era posters,
Memphis Group 1980s Italian, 1990s xerox zine, Y2K chrome, Victorian
playbill, Art Nouveau (Mucha), Belle Époque, American traditional tattoo.
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


# ─── 1. Saul Bass 1950s ───────────────────────────────────────────────────────

def render_saul_bass_50s(title: str, rng: random.Random) -> Image.Image:
    """Pioneering 1950s Bass title-card minimalism — solid colored shapes,
    a single asymmetric rule, condensed sans, hot color on warm cream."""
    n     = len(title)
    size  = 140 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((230, 50, 50),   (244, 232, 200)),    # red on cream
        ((30, 32, 40),    (244, 232, 200)),    # ink on cream
        ((40, 90, 180),   (244, 232, 200)),    # blue on cream
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        face = flat_color(mask, fg)
        text_layers.append(face)

    text_w = max(t.width for t in text_layers)
    gap    = 8
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)
    margin_x = 70
    margin_y = 60
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 20
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Single asymmetric solid bar — Bass signature.
    cd = ImageDraw.Draw(canvas)
    bar_y = margin_y - 28
    bar_w = int(W * rng.uniform(0.32, 0.5))
    bar_x = margin_x + rng.randint(0, max(0, W - bar_w - margin_x * 2))
    cd.rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 12)], fill=(*fg, 255))

    y = margin_y
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 2. Push Pin 1960s ────────────────────────────────────────────────────────

def render_push_pin_60s(title: str, rng: random.Random) -> Image.Image:
    """Push Pin Studios (Glaser, Chwast) mid-60s NYC — playful retro display
    serif, layered candy palette, slight bouncy baseline."""
    n     = len(title)
    size  = 130 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("retro", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        [(255, 80, 130),  (250, 200, 60),  (60, 30, 100)],   # pink/yellow/plum
        [(255, 130, 60),  (60, 200, 220),  (40, 30, 80)],    # orange/cyan/navy
        [(220, 60, 80),   (240, 200, 50),  (50, 130, 100)],  # red/gold/teal
    ]
    palette = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 5)
        sl   = flat_color(sm, palette[2])
        face = colorize(mask, palette[:2])
        ext  = extrude(sm, 6, 130, palette[2], tuple(max(0, c - 60) for c in palette[2]))
        sh   = drop_shadow(mask, 4, 6, blur=3, alpha=200)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 252, 220), highlight_alpha=180,
                            shadow_color=palette[2], shadow_alpha=140)
        img  = composite(sh, ext, sl, face, bev, size=mask.size)
        line_imgs.append(img)

    gap     = 4
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        # Slight per-line horizontal jitter for the bouncy feel
        x_jit = rng.randint(-12, 12)
        canvas.paste(img, ((total_w - img.width) // 2 + x_jit, y), img)
        y += img.height + gap
    return canvas


# ─── 3. WPA poster (1930s) ────────────────────────────────────────────────────

def render_wpa_poster_30s(title: str, rng: random.Random) -> Image.Image:
    """Federal Art Project 1930s screenprint — limited 3-color palette,
    bold geometric sans, decorative rules, slight ink-bleed printed feel."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    spacing = max(6, size // 14)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((232, 50, 30),   (240, 220, 160), (40, 40, 50)),    # vermilion/cream/ink
        ((40, 110, 130),  (240, 220, 160), (40, 40, 50)),    # teal/cream/ink
        ((180, 130, 40),  (40, 60, 80),    (240, 230, 200)), # mustard/navy/cream
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        bled = ink_bleed(mask, radius=1.0, strength=0.35, irregularity=0.5)
        face = flat_color(bled, fg)
        line_imgs.append(face)

    text_w = max(i.width for i in line_imgs)
    gap    = 10
    text_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    # Heavy decorative rules
    rule_w = int(W * 0.7)
    cd.rectangle([((W - rule_w) // 2, margin - 30),
                  ((W + rule_w) // 2, margin - 22)], fill=(*accent, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.rectangle([((W - rule_w) // 2, y + 8),
                  ((W + rule_w) // 2, y + 16)], fill=(*accent, 255))
    return canvas


# ─── 4. Memphis Group 1980s ───────────────────────────────────────────────────

def render_memphis_group_80s(title: str, rng: random.Random) -> Image.Image:
    """Sottsass / Memphis Milano — geometric chaos, primary colors, dot
    patterns and squiggle accents, playful Italian post-modernism."""
    n     = len(title)
    size  = 120 if n <= 14 else (94 if n <= 22 else 74)
    font  = F("heavy", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 16)

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        face = flat_color(mask, (20, 20, 24))
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=140,
                            shadow_color=(60, 60, 70), shadow_alpha=120)
        text_layers.append(composite(face, bev, size=mask.size))

    text_w = max(t.width for t in text_layers)
    gap    = 8
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))

    cd = ImageDraw.Draw(canvas)
    # Memphis chaos: random primary-color geometric shapes around the title.
    accents = [(232, 60, 90), (255, 200, 30), (60, 180, 220), (40, 60, 200), (120, 200, 80)]
    n_shapes = rng.randint(8, 14)
    for _ in range(n_shapes):
        ax = rng.randint(0, W - 1)
        ay = rng.randint(0, H - 1)
        # Avoid placing shapes directly on the central text band
        if margin + 30 < ay < H - margin - 30 and margin + 30 < ax < W - margin - 30:
            continue
        col = rng.choice(accents)
        kind = rng.choice(["circle", "square", "triangle", "squiggle", "dots"])
        sz = rng.randint(18, 44)
        if kind == "circle":
            cd.ellipse([ax - sz, ay - sz // 2, ax, ay + sz // 2], fill=(*col, 255))
        elif kind == "square":
            cd.rectangle([ax, ay, ax + sz, ay + sz], fill=(*col, 255))
        elif kind == "triangle":
            cd.polygon([(ax, ay), (ax + sz, ay), (ax + sz // 2, ay - sz)], fill=(*col, 255))
        elif kind == "squiggle":
            for i in range(0, sz * 2, 4):
                phase = math.sin(i * 0.3) * 6
                cd.point((ax + i, ay + phase), fill=(*col, 255))
                cd.point((ax + i, ay + phase + 1), fill=(*col, 255))
        else:  # dots
            for dx in range(-sz, sz + 1, 6):
                for dy in range(-sz // 2, sz // 2 + 1, 6):
                    if dx * dx + dy * dy * 4 <= sz * sz:
                        cd.ellipse([ax + dx - 2, ay + dy - 2, ax + dx + 2, ay + dy + 2],
                                   fill=(*col, 255))

    y = margin
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 5. 90s zine xerox ────────────────────────────────────────────────────────

def render_zine_90s_xerox(title: str, rng: random.Random) -> Image.Image:
    """1990s photocopied zine — high-contrast, halftone bleed, slightly
    askew layout, distressed edges. Sleater-Kinney era DIY."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 16)
    shear = rng.uniform(-0.05, 0.05)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.6, strength=0.6, irregularity=0.85)
        face = flat_color(bled, (10, 10, 12))
        # Halftone overlay knocks out tiny dots
        ht_layer = halftone_fill(bled, (10, 10, 12), dot_size=3, spacing=5)
        img = composite(face, ht_layer, size=bled.size)
        img = shear_image(img, shear)
        line_imgs.append(img)

    gap     = 6
    total_w = max(i.width for i in line_imgs) + 32
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 32
    canvas  = Image.new("RGBA", (total_w, total_h), (240, 236, 226, 255))

    # Photocopier streaks — vertical hairlines across the canvas
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(6, 14)):
        x = rng.randint(0, total_w)
        cd.line([(x, 0), (x, total_h)], fill=(20, 20, 22, rng.randint(20, 60)), width=1)

    y = 16
    for img in line_imgs:
        x = (total_w - img.width) // 2 + rng.randint(-10, 10)
        canvas.paste(img, (x, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Y2K chrome ────────────────────────────────────────────────────────────

def render_y2k_chrome(title: str, rng: random.Random) -> Image.Image:
    """Late 90s / early 00s liquid-chrome — motion-blur reflection, heavy
    gradient face, slight iridescent rim. Vapor-y future-shock optimism."""
    n     = len(title)
    size  = 144 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("tech", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sh   = drop_shadow(mask, 0, 8, blur=14, alpha=200)
        chrome = motion_blur_chrome(mask, angle_deg=90, length=24)
        # Iridescent rim layer at low alpha
        iri = holographic_shift(mask, hue_range=(0.55, 0.95), bands=3)
        from PIL import Image as _I
        iri_a = iri.split()[3].point(lambda p: int(p * 0.16))
        iri.putalpha(iri_a)
        bev = bevel_emboss(mask, depth=5, angle_deg=110, smoothness=1.6,
                           highlight_color=(255, 255, 255), highlight_alpha=200,
                           shadow_color=(40, 40, 60), shadow_alpha=180)
        img = composite(sh, chrome, iri, bev, size=mask.size)
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


# ─── 7. Victorian playbill ────────────────────────────────────────────────────

def render_victorian_playbill(title: str, rng: random.Random) -> Image.Image:
    """19th-century theatrical playbill — extreme typographic hierarchy,
    every line a different display face, decorative rules between lines."""
    n     = len(title)
    words = title.split()
    lines = [w.upper() for w in words[:4]] if len(words) <= 4 else wrap_chars(title.upper(), 14)

    line_imgs = []
    for i, ln in enumerate(lines):
        # Each line picks a different face for typographic hierarchy
        role = ["luxury", "slab", "retro", "elegant"][i % 4]
        size = [130, 96, 110, 88][i % 4] if len(ln) <= 14 else [104, 80, 90, 72][i % 4]
        font = F(role, size, rng) or F("serif", size, rng)
        mask = make_mask(ln, font, pad=18)
        face = colorize(mask, [(60, 30, 14), (30, 14, 6)])
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(220, 200, 160), highlight_alpha=140,
                            shadow_color=(20, 10, 4), shadow_alpha=180)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    max_w   = max(i.width for i in line_imgs) + 80
    gap     = 10
    rule_h  = 3
    total_h = sum(i.height for i in line_imgs) + (gap + rule_h + gap) * (len(line_imgs) - 1) + 60
    canvas  = Image.new("RGBA", (max_w, total_h), (244, 232, 200, 255))

    cd = ImageDraw.Draw(canvas)
    # Outer decorative rules — top + bottom
    cd.rectangle([(20, 10), (max_w - 20, 16)], fill=(60, 30, 14, 255))
    cd.rectangle([(20, total_h - 16), (max_w - 20, total_h - 10)], fill=(60, 30, 14, 255))

    y = 30
    for i, img in enumerate(line_imgs):
        canvas.paste(img, ((max_w - img.width) // 2, y), img)
        y += img.height + gap
        if i < len(line_imgs) - 1:
            cd.rectangle([(max_w // 4, y), (max_w * 3 // 4, y + rule_h)], fill=(60, 30, 14, 255))
            y += rule_h + gap
    return canvas


# ─── 8. Art Nouveau (Mucha) ───────────────────────────────────────────────────

def render_art_nouveau_mucha(title: str, rng: random.Random) -> Image.Image:
    """Mucha-era art nouveau — flowing decorative serif on warm parchment,
    organic bordering, sage/burgundy palette."""
    n     = len(title)
    size  = 120 if n <= 14 else (94 if n <= 22 else 74)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    spacing = max(6, size // 16)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((110, 140, 110), (216, 180, 140), (60, 80, 60)),    # sage/parchment/forest
        ((140, 60, 80),   (240, 220, 180), (60, 30, 40)),    # burgundy/parchment
        ((90, 70, 100),   (232, 220, 200), (50, 40, 60)),    # plum/parchment
    ]
    fg, paper, rule = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=3, angle_deg=125,
                            highlight_color=(255, 248, 220), highlight_alpha=130,
                            shadow_color=tuple(max(0, c - 40) for c in fg),
                            shadow_alpha=140)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*paper, 255))

    cd = ImageDraw.Draw(canvas)
    # Decorative double-rule top + bottom with a small spacer
    rule_x_l = margin // 2
    rule_x_r = W - margin // 2
    for ry in (margin // 2, margin // 2 + 5):
        cd.line([(rule_x_l, ry), (rule_x_r, ry)], fill=(*rule, 255), width=1)
    for ry in (H - margin // 2 - 5, H - margin // 2):
        cd.line([(rule_x_l, ry), (rule_x_r, ry)], fill=(*rule, 255), width=1)

    y = margin + 10
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Belle Époque ──────────────────────────────────────────────────────────

def render_belle_epoque(title: str, rng: random.Random) -> Image.Image:
    """Late-19th-century Parisian theater poster — refined decorative serif,
    metallic gold + ivory + black palette, ornate composition."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("luxury", size, rng) or F("elegant", size, rng)
    spacing = max(8, size // 16)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        sh   = drop_shadow(mask, 4, 6, blur=8, alpha=160)
        face = colorize(mask, [(252, 232, 168), (220, 168, 60), (140, 86, 20)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 248, 200), highlight_alpha=200,
                            shadow_color=(80, 40, 8), shadow_alpha=180)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 50
    canvas = Image.new("RGBA", (W, H), (24, 20, 24, 255))

    cd = ImageDraw.Draw(canvas)
    # Gold ornamental triple-rule top + bottom
    rule_w = int(W * 0.74)
    rule_x_l = (W - rule_w) // 2
    rule_x_r = rule_x_l + rule_w
    for ry in (32, 38, 44):
        cd.line([(rule_x_l, ry), (rule_x_r, ry)], fill=(220, 168, 60, 255), width=1)

    y = 80
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    for ry in (y + 8, y + 14, y + 20):
        cd.line([(rule_x_l, ry), (rule_x_r, ry)], fill=(220, 168, 60, 255), width=1)
    return canvas


# ─── 10. American traditional tattoo ──────────────────────────────────────────

def render_american_traditional_tattoo(title: str, rng: random.Random) -> Image.Image:
    """Sailor Jerry / American Traditional aesthetic — bold black outline,
    flat saturated fill (red/yellow/teal), hard solid color blocks."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("retro", size, rng) or F("slab", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((220, 50, 50),   (250, 220, 60),  (10, 10, 12)),   # red/yellow/black
        ((40, 130, 130),  (250, 220, 60),  (10, 10, 12)),   # teal/yellow/black
        ((220, 140, 60),  (50, 60, 130),   (10, 10, 12)),   # orange/blue/black
    ]
    face_c, accent_c, ink = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 9)
        sl   = flat_color(sm, ink)              # heavy black outline
        face = flat_color(mask, face_c)
        # Inner stripe band (single horizontal band of accent color)
        stripe_mask = Image.new("L", mask.size, 0)
        sd = ImageDraw.Draw(stripe_mask)
        h = mask.size[1]
        sd.rectangle([(0, h // 2 - h // 14), (mask.size[0], h // 2 + h // 14)], fill=255)
        stripe_mask = ImageChops.multiply(mask, stripe_mask)
        stripe_layer = flat_color(stripe_mask, accent_c)
        sh   = drop_shadow(sm, 5, 7, blur=2, alpha=200)
        img  = composite(sh, sl, face, stripe_layer, size=mask.size)
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


# ─── Registration ─────────────────────────────────────────────────────────────

PACK4_ERAS_TREATMENTS = {
    "saul_bass_50s":              render_saul_bass_50s,
    "push_pin_60s":               render_push_pin_60s,
    "wpa_poster_30s":             render_wpa_poster_30s,
    "memphis_group_80s":          render_memphis_group_80s,
    "zine_90s_xerox":             render_zine_90s_xerox,
    "y2k_chrome":                 render_y2k_chrome,
    "victorian_playbill":         render_victorian_playbill,
    "art_nouveau_mucha":          render_art_nouveau_mucha,
    "belle_epoque":               render_belle_epoque,
    "american_traditional_tattoo": render_american_traditional_tattoo,
}
