"""
Pack 3 — Music genre archetypes.

Ten treatments evoking specific music-genre design traditions. Blue Note
jazz (Reid Miles minimalism), punk zine, hip-hop graffiti, prog rock
fantasy, metal blackletter, country wood-grain, electronic minimal techno,
indie folk hand-drawn, Motown soul, reggae woodcut.
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


# ─── 1. Blue Note jazz (Reid Miles minimalism) ────────────────────────────────

def render_blue_note_jazz(title: str, rng: random.Random) -> Image.Image:
    """Reid Miles for Blue Note Records — restrained sans, single accent
    rule, high horizon line, black + one bold color. Mid-50s confidence."""
    n     = len(title)
    size  = 134 if n <= 14 else (102 if n <= 22 else 78)
    spacing = max(8, size // 14)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((232, 60, 60),   (240, 232, 218)),   # red + cream
        ((232, 168, 30),  (240, 232, 218)),   # mustard + cream
        ((40, 80, 200),   (240, 232, 218)),   # blue + cream
        ((20, 22, 28),    (240, 232, 218)),   # ink on cream
    ]
    accent_c, bg_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, accent_c)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)

    margin_x = 70
    margin_y = 80
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg_c, 255))

    # Heavy single rule above the title block — Reid Miles signature.
    cd = ImageDraw.Draw(canvas)
    rule_y = margin_y - 26
    rule_w = int(W * 0.78)
    cd.rectangle([(margin_x, rule_y), (margin_x + rule_w, rule_y + 8)],
                 fill=(*accent_c, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. Punk zine xerox ───────────────────────────────────────────────────────

def render_punk_zine_xerox(title: str, rng: random.Random) -> Image.Image:
    """Photocopied DIY punk zine — high-contrast B&W, shifted/cut letters
    like ransom note, light edge bleed, scratch overlay."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        # Each WORD picks a different punk-feel font for ransom-note variety.
        words = ln.split()
        word_imgs = []
        for w in words:
            wfont = F(rng.choice(["heavy", "condensed", "marker", "slab"]), size, rng) or F("heavy", size, rng)
            mask = make_mask(w, wfont, pad=14)
            # Photocopy bleed + irregularity
            xerox = ink_bleed(mask, radius=1.4, strength=0.55, irregularity=0.85)
            face = flat_color(xerox, (10, 10, 12))
            # Random vertical jitter per word — ransom note feel
            jitter = rng.randint(-5, 5)
            word_imgs.append((face, jitter))

        # Compose words in a row with small gaps
        gap_w = 14
        row_w = sum(img.width for img, _ in word_imgs) + gap_w * (len(word_imgs) - 1)
        row_h = max(img.height for img, _ in word_imgs) + 14
        row = Image.new("RGBA", (row_w, row_h), (0, 0, 0, 0))
        x = 0
        for img, j in word_imgs:
            row.paste(img, (x, 7 + j), img)
            x += img.width + gap_w
        line_imgs.append(row)

    gap     = 6
    total_w = max(i.width for i in line_imgs) + 24
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 24
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 12
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap

    # Scratch / photocopy noise
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(20, 40)):
        x1 = rng.randint(0, total_w)
        y1 = rng.randint(0, total_h)
        if canvas.getpixel((x1, y1))[3] == 0:
            continue
        cd.line([(x1, y1), (x1 + rng.randint(-4, 4), y1 + rng.randint(-4, 4))],
                fill=(20, 20, 20, rng.randint(60, 150)), width=1)
    return canvas


# ─── 3. Hip-hop graffiti ──────────────────────────────────────────────────────

def render_hip_hop_graffiti(title: str, rng: random.Random) -> Image.Image:
    """Bubble graffiti throw-up — chunky letters, thick black outline,
    drop-shadow stroke, vibrant fill with halftone fade."""
    n     = len(title)
    size  = 154 if n <= 12 else (118 if n <= 20 else 92)
    font  = F("comic", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        [(255, 220, 30), (255, 100, 30),  (220, 30, 60)],     # gold→red
        [(60, 220, 250), (100, 80, 220),  (220, 30, 180)],    # cyan→magenta
        [(180, 250, 60), (60, 220, 100),  (40, 100, 200)],    # lime→blue
    ]
    palette = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 11)                 # thick outline mass
        sl   = flat_color(sm, (10, 10, 14))     # black stroke
        face = colorize(mask, palette)
        # Halftone overlay on the face for added texture
        ht   = halftone_fill(mask, palette[-1], dot_size=4, spacing=8)
        sh   = drop_shadow(sm, 8, 12, blur=4, alpha=200)
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=180,
                            shadow_color=tuple(max(0, c - 100) for c in palette[-1]),
                            shadow_alpha=140)
        img  = composite(sh, sl, face, ht, bev, size=mask.size)
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


# ─── 4. Prog rock fantasy (Roger Dean) ────────────────────────────────────────

def render_prog_rock_dean(title: str, rng: random.Random) -> Image.Image:
    """Roger Dean (Yes) painted-fantasy aesthetic — flowing custom logotype
    with airbrushed gradients, dramatic shadow, pseudo-rainbow bevel."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("retro", size, rng) or F("script", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title, 16)

    palettes = [
        [(160, 220, 250), (60, 130, 220),  (40, 30, 120)],    # sky → ultramarine
        [(255, 220, 130), (240, 130, 60),  (140, 50, 90)],    # sunrise
        [(220, 240, 200), (130, 220, 160), (40, 120, 100)],   # green sunrise
    ]
    palette = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        sh   = drop_shadow(mask, 6, 10, blur=12, alpha=200)
        face = colorize(mask, palette)
        bev  = bevel_emboss(mask, depth=8, angle_deg=130, smoothness=2.0,
                            highlight_color=(255, 255, 230), highlight_alpha=180,
                            shadow_color=palette[-1], shadow_alpha=180)
        # Subtle iridescent rim
        iri  = holographic_shift(mask, hue_range=(0.5, 0.85), bands=4)
        from PIL import Image as _I
        iri_a = iri.split()[3].point(lambda p: int(p * 0.18))
        iri.putalpha(iri_a)
        hl   = highlight(mask, 0.4)
        img  = composite(sh, face, bev, iri, hl, size=mask.size)
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


# ─── 5. Metal blackletter ─────────────────────────────────────────────────────

def render_metal_blackletter(title: str, rng: random.Random) -> Image.Image:
    """Black-metal aesthetic — gothic blackletter on near-black, sharp
    silver edges, occult red bleed at letter feet."""
    n     = len(title)
    size  = 130 if n <= 14 else (104 if n <= 22 else 82)
    font  = F("gothic", size, rng) or F("luxury", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        # Layered: blood bleed beneath, silver face on top
        bled = ink_bleed(mask, radius=2.2, strength=0.7, irregularity=0.85)
        blood = flat_color(bled, (140, 8, 6))
        sh   = drop_shadow(mask, 0, 3, blur=12, alpha=240)
        face = colorize(mask, [(220, 220, 230), (140, 140, 156), (60, 60, 70)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(20, 20, 26), shadow_alpha=200)
        img  = composite(sh, blood, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(i.width for i in line_imgs)
    gap    = 12
    text_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (8, 6, 8, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Country ornate (wood-grain) ───────────────────────────────────────────

def render_country_ornate(title: str, rng: random.Random) -> Image.Image:
    """Nashville-style ornate Western typography — wood-grain warmth with
    decorative scroll rules. Slab + serif vibe, cream + walnut palette."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("retro", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        sh   = drop_shadow(mask, 5, 8, blur=8, alpha=180)
        face = colorize(mask, [(248, 220, 170), (190, 132, 70), (90, 50, 22)])
        bev  = bevel_emboss(mask, depth=6, angle_deg=125,
                            highlight_color=(255, 248, 220), highlight_alpha=200,
                            shadow_color=(60, 30, 8), shadow_alpha=180)
        # Wood-grain striations: faint horizontal lines through the letterforms
        grain = Image.new("L", mask.size, 0)
        gd = ImageDraw.Draw(grain)
        for y in range(0, mask.size[1], 3):
            for x in range(0, mask.size[0], rng.randint(60, 140)):
                gd.line([(x, y), (x + rng.randint(40, 90), y + rng.randint(-1, 1))],
                        fill=rng.randint(40, 90), width=1)
        grain_layer = flat_color(ImageChops.multiply(mask, grain.point(lambda p: int(p * 0.5))),
                                 (60, 30, 8))
        img  = composite(sh, face, bev, grain_layer, size=mask.size)
        line_imgs.append(img)

    max_w   = max(i.width for i in line_imgs) + 80
    rule_w  = int(max_w * 0.6)
    gap     = 12
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 60
    canvas  = Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0))

    rl_top = rule_line(rule_w, (90, 50, 22), 3)
    canvas.paste(rl_top, ((max_w - rule_w) // 2, 16), rl_top)
    y = 36
    for img in line_imgs:
        canvas.paste(img, ((max_w - img.width) // 2, y), img)
        y += img.height + gap
    rl_bot = rule_line(int(rule_w * 0.7), (90, 50, 22), 3)
    canvas.paste(rl_bot, ((max_w - int(rule_w * 0.7)) // 2, y + 6), rl_bot)
    return canvas


# ─── 7. Electronic minimal techno ─────────────────────────────────────────────

def render_electronic_minimal_techno(title: str, rng: random.Random) -> Image.Image:
    """Minimal techno / Berlin sleeve — single thin sans, ultra-spacious
    tracking, monochrome, single hairline rule. Disciplined and quiet."""
    n     = len(title)
    size  = 96 if n <= 14 else (76 if n <= 24 else 60)
    spacing = max(20, size // 4)
    font  = F("condensed", size, rng) or F("tech", size, rng)
    lines = wrap_chars(title.upper(), 22) if n > 22 else [title.upper()]

    palettes = [
        ((20, 20, 24),    (240, 240, 240)),   # ink on white
        ((240, 240, 240), (24, 24, 26)),      # white on near-black
        ((230, 230, 226), (60, 70, 76)),      # off-white on slate
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=20)
        face = flat_color(mask, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    text_h = sum(t.height for t in line_imgs) + 8 * (len(line_imgs) - 1)
    margin_x = 80
    margin_y = 100
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    rule_y = margin_y - 30
    rule_w = int(W * 0.16)
    cd.line([(margin_x, rule_y), (margin_x + rule_w, rule_y)], fill=(*fg, 255), width=1)

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + 8
    return canvas


# ─── 8. Indie folk hand-drawn ─────────────────────────────────────────────────

def render_indie_folk_handdrawn(title: str, rng: random.Random) -> Image.Image:
    """Hand-lettered indie folk sleeve — script font with ink bleed, warm
    earthy palette, light paper-like hue. No decoration, just type."""
    n     = len(title)
    size  = 134 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("script", size, rng) or F("marker", size, rng)
    lines = wrap_chars(title, 18)

    palettes = [
        ((78, 56, 38),   (244, 234, 220)),    # walnut on parchment
        ((50, 70, 60),   (240, 238, 220)),    # forest on cream
        ((120, 60, 60),  (244, 234, 220)),    # rust on parchment
    ]
    ink, paper = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        bled = ink_bleed(mask, radius=1.6, strength=0.5, irregularity=0.5)
        face = flat_color(bled, ink)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*paper, 255))

    # Subtle paper speckle
    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 700):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(180, 160, 130, rng.randint(10, 30)))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Soul Motown ───────────────────────────────────────────────────────────

def render_soul_motown(title: str, rng: random.Random) -> Image.Image:
    """1960s Motown / Stax era — refined gold/amber gradient on warm cream,
    elegant serif, decorative double-rule. Sophisticated soul."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 24 else 76)
    spacing = max(8, size // 14)
    font  = F("luxury", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        sh   = drop_shadow(mask, 3, 5, blur=6, alpha=150)
        face = colorize(mask, [(252, 240, 200), (220, 168, 60), (140, 86, 20)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 252, 220), highlight_alpha=200,
                            shadow_color=(80, 40, 8), shadow_alpha=170)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    max_w   = max(i.width for i in line_imgs) + 80
    rule_w  = int(max_w * 0.7)
    gap     = 12
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 80
    canvas  = Image.new("RGBA", (max_w, total_h), (244, 234, 200, 255))

    cd = ImageDraw.Draw(canvas)
    # Double rule top + double rule bottom
    rule_y_top1 = 18
    rule_y_top2 = 26
    rule_x = (max_w - rule_w) // 2
    for ry in (rule_y_top1, rule_y_top2):
        cd.line([(rule_x, ry), (rule_x + rule_w, ry)], fill=(140, 86, 20, 255), width=2)

    y = 50
    for img in line_imgs:
        canvas.paste(img, ((max_w - img.width) // 2, y), img)
        y += img.height + gap

    rule_y_bot1 = y + 12
    rule_y_bot2 = y + 20
    for ry in (rule_y_bot1, rule_y_bot2):
        cd.line([(rule_x, ry), (rule_x + rule_w, ry)], fill=(140, 86, 20, 255), width=2)
    return canvas


# ─── 10. Dub reggae woodcut ───────────────────────────────────────────────────

def render_dub_reggae_woodcut(title: str, rng: random.Random) -> Image.Image:
    """Jamaica woodblock print aesthetic — bold slab letters on a flat
    background in a Rasta-traditional palette (red/gold/green), with
    distress-cut edges that read as carved wood."""
    n     = len(title)
    size  = 134 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("slab", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((250, 230, 50),  (220, 30, 30),  (50, 130, 50)),   # gold/red/green
        ((230, 30, 30),   (250, 230, 50), (50, 130, 50)),
        ((50, 130, 50),   (250, 230, 50), (230, 30, 30)),
    ]
    bg_c, accent_c, rule_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        # Distress for woodcut feel
        worn = ink_bleed(mask, radius=1.2, strength=0.4, irregularity=0.95)
        # Knock out small grain holes
        noise = Image.new("L", worn.size, 0)
        nd = ImageDraw.Draw(noise)
        for _ in range(rng.randint(80, 180)):
            x = rng.randint(0, worn.size[0] - 1)
            y = rng.randint(0, worn.size[1] - 1)
            r = rng.randint(1, 3)
            nd.ellipse([x - r, y - r, x + r, y + r], fill=255)
        knocked = ImageChops.subtract(worn, noise.filter(ImageFilter.GaussianBlur(0.6)))
        face = flat_color(knocked, accent_c)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg_c, 255))

    # Heavy horizontal bar — Rasta tricolor stripe at the bottom
    cd = ImageDraw.Draw(canvas)
    bar_h = 16
    cd.rectangle([(margin, H - margin // 2 - bar_h),
                  (W - margin, H - margin // 2)], fill=(*rule_c, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK3_MUSIC_TREATMENTS = {
    "blue_note_jazz":             render_blue_note_jazz,
    "punk_zine_xerox":            render_punk_zine_xerox,
    "hip_hop_graffiti":           render_hip_hop_graffiti,
    "prog_rock_dean":             render_prog_rock_dean,
    "metal_blackletter":          render_metal_blackletter,
    "country_ornate":             render_country_ornate,
    "electronic_minimal_techno":  render_electronic_minimal_techno,
    "indie_folk_handdrawn":       render_indie_folk_handdrawn,
    "soul_motown":                render_soul_motown,
    "dub_reggae_woodcut":         render_dub_reggae_woodcut,
}
