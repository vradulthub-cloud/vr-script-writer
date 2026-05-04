"""
Pack 6 — Mutant Heritage (2026 trends).

Per the 2026 typography forecast: classic letterforms hacked and
reengineered, mid-century grotesks returning with off-kilter feel,
hand-drawn rawness, dynamic angles, expressive personality.

Ten treatments that lean INTO that direction — deliberately imperfect,
character-forward, weight-asymmetric, anti-default.
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
    shear_image,
    wide_track_mask,
    wrap_chars,
)


# ─── 1. Mutant serif glitch ───────────────────────────────────────────────────

def render_mutant_serif_glitch(title: str, rng: random.Random) -> Image.Image:
    """Classic serif with chromatic-aberration RGB split — old form,
    digital corruption. The 2026 'tech-tuned heritage' lookbook entry."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("luxury", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        face = flat_color(mask, (28, 28, 32))
        # Chromatic split: red+cyan ghosts behind the black face
        red_ghost  = flat_color(mask, (220, 30, 30))
        cyan_ghost = flat_color(mask, (30, 200, 220))
        offset = rng.randint(4, 8)
        canvas = Image.new("RGBA", (mask.size[0] + offset * 2, mask.size[1] + offset * 2),
                           (0, 0, 0, 0))
        canvas.alpha_composite(red_ghost,  (0, 0))
        canvas.alpha_composite(cyan_ghost, (offset * 2, offset))
        canvas.alpha_composite(face, (offset, offset // 2))
        line_imgs.append(canvas)

    text_w = max(i.width for i in line_imgs)
    gap    = 10
    text_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. Handcrafted tech ──────────────────────────────────────────────────────

def render_handcrafted_tech(title: str, rng: random.Random) -> Image.Image:
    """Marker-style hand-drawn lettering on a tech-grid background.
    The 'visibly handcrafted yet tech-tuned' brief from 2026 trend forecasts."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("marker", size, rng) or F("script", size, rng)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        bled = ink_bleed(mask, radius=1.4, strength=0.45, irregularity=0.6)
        face = flat_color(bled, (20, 22, 28))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 20
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))

    # Tech grid background — fine dotted grid
    cd = ImageDraw.Draw(canvas)
    for x in range(0, W, 14):
        for y in range(0, H, 14):
            cd.point((x, y), fill=(140, 130, 110, 180))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. Raw hand-lettered ─────────────────────────────────────────────────────

def render_raw_hand_lettered(title: str, rng: random.Random) -> Image.Image:
    """Sketchy, uneven, unapologetically raw — 2026's 'untamed passion'
    direction. Marker-style face with subtle hand-jitter offsets."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("marker", size, rng) or F("script", size, rng)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        # Per-character horizontal jitter for "hand-drawn" feel
        char_imgs = []
        for ch in ln:
            if ch == " ":
                char_imgs.append((Image.new("RGBA", (size // 3, size), (0, 0, 0, 0)), 0))
                continue
            mask = make_mask(ch, font, pad=8)
            bled = ink_bleed(mask, radius=1.6, strength=0.55, irregularity=0.85)
            face = flat_color(bled, (20, 20, 24))
            jitter_y = rng.randint(-8, 8)
            jitter_rot = rng.uniform(-3, 3)
            face = face.rotate(jitter_rot, resample=Image.BICUBIC, expand=True)
            char_imgs.append((face, jitter_y))

        row_w = sum(img.width for img, _ in char_imgs) + 4 * (len(char_imgs) - 1)
        row_h = max(img.height for img, _ in char_imgs) + 16
        row = Image.new("RGBA", (row_w, row_h), (0, 0, 0, 0))
        x = 0
        for img, jy in char_imgs:
            row.paste(img, (x, 8 + jy), img)
            x += img.width + 4
        line_imgs.append(row)

    text_w = max(i.width for i in line_imgs)
    gap    = 6
    text_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Dynamic angle bold ────────────────────────────────────────────────────

def render_dynamic_angle_bold(title: str, rng: random.Random) -> Image.Image:
    """Heavy sans on aggressive baseline angles — 'confident, unapologetic'.
    Each line tilts a different way; the composition has motion-energy."""
    n     = len(title)
    size  = 142 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("heavy", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((230, 50, 30),   (244, 234, 220)),
        ((40, 60, 200),   (244, 234, 220)),
        ((20, 22, 28),    (250, 230, 60)),     # ink on yellow
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=140,
                            shadow_color=tuple(max(0, c - 100) for c in fg),
                            shadow_alpha=160)
        img  = composite(face, bev, size=mask.size)
        # Each line gets a distinct rotation angle
        ang = rng.uniform(-12, 12)
        img = img.rotate(ang, resample=Image.BICUBIC, expand=True)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Expressive personality ────────────────────────────────────────────────

def render_expressive_personality(title: str, rng: random.Random) -> Image.Image:
    """Each word picks its OWN personality — different role, different
    saturation, different size. Reads as a typographic conversation."""
    n     = len(title)
    words = title.split()[:5]
    if not words:
        words = [title]

    word_imgs = []
    palettes = [
        (220, 50, 30),   (40, 60, 200),  (250, 200, 30),
        (40, 130, 110),  (200, 50, 140), (20, 20, 24),
    ]
    for w in words:
        # Pick a different role and palette per word
        role = rng.choice(["heavy", "luxury", "marker", "slab", "condensed"])
        sz = rng.randint(82, 144)
        font = F(role, sz, rng) or F("heavy", sz, rng)
        col = rng.choice(palettes)
        mask = make_mask(w.upper(), font, pad=12)
        face = flat_color(mask, col)
        word_imgs.append(face)

    # Stack them tightly — each word centered on its own row
    text_w = max(i.width for i in word_imgs) + 40
    gap    = 6
    text_h = sum(i.height for i in word_imgs) + gap * (len(word_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))
    y = margin
    for img in word_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Anti-design print ─────────────────────────────────────────────────────

def render_anti_design_print(title: str, rng: random.Random) -> Image.Image:
    """David Carson era anti-design — mismatched faces, no grid, layers
    out-of-register, deliberate roughness. Beauty from chaos."""
    n     = len(title)
    words = title.split()[:5]
    if not words:
        words = [title]

    word_imgs = []
    for w in words:
        role = rng.choice(["heavy", "condensed", "marker", "slab", "retro"])
        sz = rng.randint(70, 138)
        font = F(role, sz, rng) or F("heavy", sz, rng)
        col = rng.choice([(20, 22, 28), (220, 50, 30), (40, 60, 200)])
        mask = make_mask(w.upper(), font, pad=14)
        face = flat_color(mask, col)
        # Random rotation and shear
        face = face.rotate(rng.uniform(-15, 15), resample=Image.BICUBIC, expand=True)
        if rng.random() < 0.5:
            face = shear_image(face, rng.uniform(-0.15, 0.15))
        word_imgs.append(face)

    # Place them in a chaotic flow
    W = sum(i.width for i in word_imgs) + 120
    H = max(i.height for i in word_imgs) + 240
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))

    placements = []
    x_cursor = 60
    for img in word_imgs:
        ay = rng.randint(40, max(40, H - img.height - 40))
        canvas.paste(img, (x_cursor, ay), img)
        placements.append((x_cursor, ay, img.width, img.height))
        x_cursor += img.width + rng.randint(-40, 40)

    # Crop to actual content
    if placements:
        min_x = max(0, min(p[0] for p in placements) - 20)
        max_x = min(W, max(p[0] + p[2] for p in placements) + 20)
        min_y = max(0, min(p[1] for p in placements) - 20)
        max_y = min(H, max(p[1] + p[3] for p in placements) + 20)
        canvas = canvas.crop((min_x, min_y, max_x, max_y))
    return canvas


# ─── 7. Chunky monoline ───────────────────────────────────────────────────────

def render_chunky_monoline(title: str, rng: random.Random) -> Image.Image:
    """Thick rounded monoline display sans — like extra-bold Fredoka or
    Lilita with deliberate irregularity. 2026 'chunky character' wave."""
    n     = len(title)
    size  = 150 if n <= 14 else (118 if n <= 22 else 92)
    font  = F("rounded", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((255, 100, 130),  (240, 232, 218)),
        ((100, 220, 200),  (40, 30, 80)),
        ((250, 200, 30),   (40, 50, 100)),
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=6, angle_deg=125, smoothness=1.8,
                            highlight_color=(255, 255, 255), highlight_alpha=180,
                            shadow_color=tuple(max(0, c - 80) for c in fg),
                            shadow_alpha=140)
        sh   = drop_shadow(mask, 4, 7, blur=4, alpha=200)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Off-kilter grotesk ────────────────────────────────────────────────────

def render_off_kilter_grotesk(title: str, rng: random.Random) -> Image.Image:
    """Mid-century grotesk with subtle character-level imperfection —
    each letter is rotated 1-3°. Reads as 'human-touched' typography."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        char_imgs = []
        for ch in ln:
            if ch == " ":
                char_imgs.append(Image.new("RGBA", (size // 3, size), (0, 0, 0, 0)))
                continue
            mask = make_mask(ch, font, pad=8)
            face = flat_color(mask, (28, 28, 32))
            face = face.rotate(rng.uniform(-2.5, 2.5), resample=Image.BICUBIC, expand=True)
            char_imgs.append(face)

        row_w = sum(img.width for img in char_imgs) + 2 * (len(char_imgs) - 1)
        row_h = max(img.height for img in char_imgs) + 12
        row = Image.new("RGBA", (row_w, row_h), (0, 0, 0, 0))
        x = 0
        for img in char_imgs:
            row.paste(img, (x, 6 + rng.randint(-3, 3)), img)
            x += img.width + 2
        line_imgs.append(row)

    text_w = max(i.width for i in line_imgs)
    gap    = 8
    text_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 230, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Neue grotesk hairline ─────────────────────────────────────────────────

def render_neue_grotesk_hairline(title: str, rng: random.Random) -> Image.Image:
    """Ultra-modern hairline grotesk — extremely thin, very large, generous
    whitespace, single-color, sharp digital aesthetic."""
    n     = len(title)
    size  = 156 if n <= 14 else (124 if n <= 22 else 96)
    font  = F("luxury", size, rng) or F("serif", size, rng)
    spacing = max(8, size // 18)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((20, 22, 28),    (244, 240, 230)),
        ((244, 240, 230), (28, 30, 36)),
        ((220, 50, 30),   (244, 240, 230)),
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        # Use outline_stroke for a hairline effect (thin)
        outline = outline_stroke(mask, width=1, rgb=fg, alpha=255)
        line_imgs.append(outline)

    text_w = max(t.width for t in line_imgs)
    gap    = 14
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 90
    margin_y = 90
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))
    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Iridescent foil packaging ────────────────────────────────────────────

def render_iridescent_foil_packaging(title: str, rng: random.Random) -> Image.Image:
    """Y2K beauty-product packaging — holographic shift across the surface,
    chrome rim, metallic feel. 'Top-shelf consumer' aesthetic."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("luxury", size, rng) or F("heavy", size, rng)
    spacing = max(6, size // 16)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=22)
        sh   = drop_shadow(mask, 0, 5, blur=10, alpha=160)
        # Holographic base
        iri  = holographic_shift(mask, hue_range=(0.55, 1.0), bands=4,
                                 saturation=0.85, value=0.95)
        # Chrome rim via Fresnel
        rim  = fresnel_metallic(mask, base_color=(220, 220, 230),
                                rim_color=(255, 255, 255), rim_power=2.6)
        from PIL import Image as _I
        rim_a = rim.split()[3].point(lambda p: int(p * 0.45))
        rim.putalpha(rim_a)
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=180,
                            shadow_color=(60, 60, 80), shadow_alpha=140)
        img  = composite(sh, iri, rim, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK6_MUTANT_TREATMENTS = {
    "mutant_serif_glitch":       render_mutant_serif_glitch,
    "handcrafted_tech":          render_handcrafted_tech,
    "raw_hand_lettered":         render_raw_hand_lettered,
    "dynamic_angle_bold":        render_dynamic_angle_bold,
    "expressive_personality":    render_expressive_personality,
    "anti_design_print":         render_anti_design_print,
    "chunky_monoline":           render_chunky_monoline,
    "off_kilter_grotesk":        render_off_kilter_grotesk,
    "neue_grotesk_hairline":     render_neue_grotesk_hairline,
    "iridescent_foil_packaging": render_iridescent_foil_packaging,
}
