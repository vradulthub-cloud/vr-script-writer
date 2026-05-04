"""
Pack 2 — Genre cinema title-card archetypes.

Ten hand-crafted treatments evoking specific film-genre conventions.
Each is built to feel like a single era's poster work, not a generic
"movie poster" — noir is sharp and chiaroscuro, grindhouse is distressed,
giallo is ornate and bloody, etc.
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


# ─── 1. Noir carbon ───────────────────────────────────────────────────────────

def render_noir_carbon(title: str, rng: random.Random) -> Image.Image:
    """High-contrast black-and-white, ultra-condensed, sharp diagonal shadow.
    Inspired by 1940s film noir title cards — chiaroscuro typography."""
    n     = len(title)
    size  = 150 if n <= 14 else (118 if n <= 22 else 92)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        # Hard diagonal shadow — knife-edge cinematic
        sh   = long_shadow(mask, steps=36, angle_deg=55, col=(8, 8, 10), fade=False)
        face = flat_color(mask, (245, 240, 232))
        # Subtle bevel adds the film-stock feel
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=120,
                            shadow_color=(40, 40, 50), shadow_alpha=100)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    gap     = 6
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. Grindhouse grain ──────────────────────────────────────────────────────

def render_grindhouse_grain(title: str, rng: random.Random) -> Image.Image:
    """Distressed exploitation-film aesthetic — warm-shifted, scratch lines,
    splatter dots, blood-red dripping color. Tarantino's worship target."""
    n     = len(title)
    size  = 144 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((220, 35, 30),  (60, 8, 6)),     # blood red
        ((232, 168, 30), (50, 30, 4)),    # mustard yellow
        ((230, 220, 200), (30, 20, 16)),  # cream/sepia
    ]
    face_c, sh_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask    = make_mask(ln, font, pad=22)
        # Distress: bleed the mask so edges are uneven
        worn    = ink_bleed(mask, radius=1.8, strength=0.6, irregularity=0.85)
        # Then knock out random splatter holes
        noise = Image.new("L", worn.size, 0)
        nd = ImageDraw.Draw(noise)
        for _ in range(rng.randint(180, 320)):
            x = rng.randint(0, worn.size[0] - 1)
            y = rng.randint(0, worn.size[1] - 1)
            r = rng.randint(1, 4)
            nd.ellipse([x - r, y - r, x + r, y + r], fill=255)
        knocked = ImageChops.subtract(worn, noise.filter(ImageFilter.GaussianBlur(0.8)))

        sh   = drop_shadow(knocked, 5, 7, blur=6, alpha=180)
        face = flat_color(knocked, face_c)
        img  = composite(sh, face, size=worn.size)
        line_imgs.append(img)

    # Compose with horizontal scratch lines across the whole title
    gap     = 8
    total_w = max(i.width for i in line_imgs) + 40
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 40
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 20
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap

    # Scratch overlay — diagonal hairlines
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(8, 16)):
        x1 = rng.randint(0, total_w)
        y1 = rng.randint(0, total_h)
        length = rng.randint(40, 120)
        ang = rng.uniform(-0.2, 0.2)
        x2 = x1 + int(math.cos(ang) * length)
        y2 = y1 + int(math.sin(ang) * length)
        a = rng.randint(40, 120)
        cd.line([(x1, y1), (x2, y2)], fill=(*sh_c[:3], a), width=1)
    return canvas


# ─── 3. Giallo red void ───────────────────────────────────────────────────────

def render_giallo_red_void(title: str, rng: random.Random) -> Image.Image:
    """Italian horror (Argento/Bava) — heavy serif, deep blood red on
    near-black, dramatic isolation. Now uses a HEAVY serif so the form
    has presence, plus a stronger inner glow so the red feels lit from
    within rather than thin/neon."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 24 else 84)
    # Heavy serif comes first — luxury gave us a hairline weight that read
    # as a thin neon outline. Prefer Bodoni / Abril / Cinzel weight.
    font  = F("serif", size, rng) or F("luxury", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 16)

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        # Outer red bloom — wider and warmer than the previous version
        bloom = mask.filter(ImageFilter.GaussianBlur(22))
        bloom_layer = flat_color(bloom, (220, 30, 24))
        bloom_a = bloom_layer.split()[3].point(lambda p: int(p * 0.85))
        bloom_layer.putalpha(bloom_a)
        sh   = drop_shadow(mask, 0, 0, blur=10, alpha=220)
        face = colorize(mask, [(232, 60, 50), (180, 14, 12), (90, 0, 0)])
        bev  = bevel_emboss(mask, depth=6, angle_deg=110, smoothness=1.5,
                            highlight_color=(255, 200, 195), highlight_alpha=200,
                            shadow_color=(30, 0, 0), shadow_alpha=220)
        img  = composite(bloom_layer, sh, face, bev, size=mask.size)
        text_layers.append(img)

    text_w = max(t.width for t in text_layers)
    gap    = 12
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (10, 6, 8, 255))
    y = margin
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 4. Blaxploitation fist ───────────────────────────────────────────────────

def render_blaxploitation_fist(title: str, rng: random.Random) -> Image.Image:
    """1970s blaxploitation poster — bold yellow/orange + red, slight italic
    shear, heavy stroke. Funky, urgent, declarative."""
    n     = len(title)
    size  = 150 if n <= 12 else (118 if n <= 22 else 90)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((250, 200, 30),  (210, 40, 30)),    # yellow on red
        ((255, 110, 30),  (40, 20, 80)),     # orange on dark purple
        ((230, 60, 80),   (240, 200, 40)),   # red on yellow
    ]
    face_c, stroke_c = palettes[rng.randrange(len(palettes))]
    shear = 0.18

    line_imgs = []
    for ln in lines:
        mask  = make_mask(ln, font, pad=20)
        sm    = dilate(mask, 8)
        sl    = flat_color(sm, stroke_c)
        face  = flat_color(mask, face_c)
        sh    = drop_shadow(mask, 6, 9, blur=4, alpha=200)
        ext   = extrude(sm, 6, 130, tuple(max(0, c - 80) for c in stroke_c),
                        tuple(max(0, c - 120) for c in stroke_c))
        img   = composite(sh, ext, sl, face, size=mask.size)
        img   = shear_image(img, shear)
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


# ─── 5. Drive-in marquee ──────────────────────────────────────────────────────

def render_drive_in_marquee(title: str, rng: random.Random) -> Image.Image:
    """Vintage drive-in / movie-marquee aesthetic — rounded retro letterforms
    with a row of marquee bulbs along the perimeter."""
    n     = len(title)
    size  = 130 if n <= 14 else (104 if n <= 22 else 82)
    font  = F("retro", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((255, 220, 60),  (190, 40, 40)),    # yellow + red
        ((255, 100, 100), (60, 30, 80)),     # pink + indigo
        ((240, 240, 220), (210, 30, 60)),    # cream + crimson
    ]
    face_c, bg_panel = palettes[rng.randrange(len(palettes))]

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        face = flat_color(mask, face_c)
        bev  = bevel_emboss(mask, depth=5, angle_deg=120,
                            highlight_color=(255, 255, 240), highlight_alpha=180,
                            shadow_color=(40, 20, 10), shadow_alpha=160)
        text_layers.append(composite(face, bev, size=mask.size))

    text_w = max(t.width for t in text_layers)
    gap    = 8
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    # Panel with a row of bulbs around the perimeter
    pad = 50
    W = text_w + pad * 2
    H = text_h + pad * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Faux-painted panel background
    cd = ImageDraw.Draw(canvas)
    cd.rounded_rectangle([(8, 8), (W - 8, H - 8)],
                         radius=18, fill=(*bg_panel, 255))

    # Marquee bulbs — top and bottom rows, evenly spaced
    bulb_r = 9
    spacing = 36
    for x in range(spacing, W - spacing + 1, spacing):
        for y in (16, H - 16):
            cd.ellipse([x - bulb_r, y - bulb_r, x + bulb_r, y + bulb_r],
                       fill=(255, 240, 200), outline=(220, 170, 50))
            # Subtle glow center
            cd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 250, 240))
    for y in range(spacing, H - spacing + 1, spacing):
        for x in (16, W - 16):
            cd.ellipse([x - bulb_r, y - bulb_r, x + bulb_r, y + bulb_r],
                       fill=(255, 240, 200), outline=(220, 170, 50))
            cd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 250, 240))

    # Drop the text in
    y = pad
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 6. Lobby card amber ──────────────────────────────────────────────────────

def render_lobby_card_amber(title: str, rng: random.Random) -> Image.Image:
    """Old Hollywood lobby card — warm amber-cream gradient, art-deco
    influenced serif, tasteful drop shadow. Reads as 1940s premiere."""
    n     = len(title)
    size  = 120 if n <= 16 else (96 if n <= 26 else 76)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    spacing = max(6, size // 18)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask  = wide_track_mask(ln, font, spacing, pad=18)
        face  = colorize(mask, [(252, 232, 178), (218, 168, 82), (140, 86, 32)])
        bev   = bevel_emboss(mask, depth=4, angle_deg=120,
                             highlight_color=(255, 248, 220), highlight_alpha=160,
                             shadow_color=(60, 36, 12), shadow_alpha=120)
        sh    = drop_shadow(mask, 4, 6, blur=8, alpha=160)
        img   = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    max_w   = max(i.width for i in line_imgs) + 60
    rule_w  = int(max_w * 0.55)
    gap     = 14
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 50
    canvas  = Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0))

    rl_top = rule_line(rule_w, (140, 86, 32), 2)
    canvas.paste(rl_top, ((max_w - rule_w) // 2, 12), rl_top)
    y = 26
    for img in line_imgs:
        canvas.paste(img, ((max_w - img.width) // 2, y), img)
        y += img.height + gap
    rl_bot = rule_line(int(rule_w * 0.7), (140, 86, 32), 2)
    canvas.paste(rl_bot, ((max_w - int(rule_w * 0.7)) // 2, y + 6), rl_bot)
    return canvas


# ─── 7. Hammer horror ─────────────────────────────────────────────────────────

def render_hammer_horror(title: str, rng: random.Random) -> Image.Image:
    """British Hammer Films aesthetic — gothic blackletter + dripping blood
    red gradient on near-black. Christopher Lee, Peter Cushing energy."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 82)
    font  = F("gothic", size, rng) or F("luxury", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 16)

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sh   = drop_shadow(mask, 4, 8, blur=14, alpha=220)
        face = colorize(mask, [(232, 38, 30), (170, 14, 12), (90, 0, 0)])
        # Slight bleed so it reads as printed/painted not digital
        bled = ink_bleed(mask, radius=0.9, strength=0.35, irregularity=0.7)
        face_b = colorize(bled, [(232, 38, 30), (170, 14, 12), (90, 0, 0)])
        text_layers.append(composite(sh, face_b, face, size=mask.size))

    text_w = max(t.width for t in text_layers)
    gap    = 12
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (12, 4, 4, 255))
    y = margin
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2, y), t)
        y += t.height + gap
    return canvas


# ─── 8. Spaghetti western dust ────────────────────────────────────────────────

def render_spaghetti_western_dust(title: str, rng: random.Random) -> Image.Image:
    """Sergio Leone era — slab serif on dusty tan, burnt-sienna distress,
    cream highlights. Plays well in mono and at large scale."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("slab", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        # Distress with ink bleed
        worn = ink_bleed(mask, radius=1.5, strength=0.55, irregularity=0.7)
        sh   = long_shadow(worn, steps=18, angle_deg=40, col=(60, 30, 12), fade=True)
        face = colorize(worn, [(232, 196, 130), (180, 120, 60), (100, 60, 30)])
        bev  = bevel_emboss(worn, depth=4, angle_deg=125,
                            highlight_color=(255, 232, 180), highlight_alpha=160,
                            shadow_color=(80, 38, 14), shadow_alpha=140)
        img  = composite(sh, face, bev, size=worn.size)
        line_imgs.append(img)

    gap     = 6
    total_w = max(i.width for i in line_imgs) + 30
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap

    # Dust speckle overlay — sparse warm-tone noise
    cd = ImageDraw.Draw(canvas)
    for _ in range(total_w * total_h // 240):
        x = rng.randint(0, total_w - 1)
        y = rng.randint(0, total_h - 1)
        if canvas.getpixel((x, y))[3] == 0:
            continue
        cd.point((x, y), fill=(220, 180, 110, rng.randint(20, 70)))
    return canvas


# ─── 9. Hong Kong kungfu ──────────────────────────────────────────────────────

def render_hong_kong_kungfu(title: str, rng: random.Random) -> Image.Image:
    """1970s Shaw Brothers / Golden Harvest aesthetic — bright yellow/orange
    on red with diagonal energy. Bold, saturated, impactful."""
    n     = len(title)
    size  = 154 if n <= 12 else (120 if n <= 22 else 92)
    font  = F("heavy", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 14)
    shear = 0.12

    # Saturated jewel palettes only — these were too muted in the first cut.
    palettes = [
        ((255, 230, 0),    (210, 20, 20)),    # bright gold on bright red
        ((255, 110, 20),   (50, 0, 60)),      # vivid orange on deep plum
        ((255, 50, 50),    (255, 220, 0)),    # bright red on bright gold
    ]
    face_c, stroke_c = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 11)                                # thicker stroke
        sl   = flat_color(sm, stroke_c)
        face = flat_color(mask, face_c)
        # Multi-tone extrusion — depth + saturation kicker
        ext_near = stroke_c
        ext_far  = tuple(max(0, c - 100) for c in stroke_c)
        ext  = extrude(sm, 12, 135, ext_near, ext_far)
        sh   = drop_shadow(mask, 10, 14, blur=6, alpha=240)
        bev  = bevel_emboss(mask, depth=6, angle_deg=130, smoothness=1.6,
                            highlight_color=(255, 255, 240), highlight_alpha=220,
                            shadow_color=tuple(max(0, c - 120) for c in face_c),
                            shadow_alpha=180)
        # Specular kicker — small bright sliver near the top
        hl = highlight(mask, 0.55)
        img  = composite(sh, ext, sl, face, bev, hl, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    gap     = 4
    total_w = max(i.width for i in line_imgs) + 40
    total_h = sum(i.height for i in line_imgs) + gap * (len(line_imgs) - 1) + 30
    canvas  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 15
    for img in line_imgs:
        canvas.paste(img, ((total_w - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Hitchcock silhouette ─────────────────────────────────────────────────

def render_hitchcock_silhouette(title: str, rng: random.Random) -> Image.Image:
    """Saul Bass / Hitchcock title-card minimalism — heavy single-color
    shapes, asymmetric composition, hairline rule. No texture, no shadow,
    just confident silhouette."""
    n     = len(title)
    size  = 140 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((215, 38, 38),   (240, 232, 218)),   # red on cream
        ((20, 20, 28),    (240, 232, 218)),   # black on cream
        ((240, 232, 218), (20, 20, 28)),      # cream on black
        ((255, 200, 50),  (20, 20, 28)),      # gold on black
    ]
    face_c, bg_c = palettes[rng.randrange(len(palettes))]

    text_layers = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        face = flat_color(mask, face_c)
        text_layers.append(face)

    text_w = max(t.width for t in text_layers)
    gap    = 10
    text_h = sum(t.height for t in text_layers) + gap * (len(text_layers) - 1)

    margin_x = 70
    margin_y = 50
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 20
    canvas = Image.new("RGBA", (W, H), (*bg_c, 255))

    # One asymmetric hairline rule — Bass-style structural line
    cd = ImageDraw.Draw(canvas)
    rule_y = margin_y - 14
    rule_w = int(W * rng.uniform(0.55, 0.78))
    rule_x = rng.randrange(margin_x, W - rule_w - margin_x // 2)
    cd.line([(rule_x, rule_y), (rule_x + rule_w, rule_y)], fill=(*face_c, 255), width=2)

    # Text, slightly off-center
    y = margin_y
    offset_x = rng.randint(-30, 30)
    for t in text_layers:
        canvas.paste(t, ((W - t.width) // 2 + offset_x, y), t)
        y += t.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK2_CINEMA_TREATMENTS = {
    "noir_carbon":              render_noir_carbon,
    "grindhouse_grain":         render_grindhouse_grain,
    "giallo_red_void":          render_giallo_red_void,
    "blaxploitation_fist":      render_blaxploitation_fist,
    "drive_in_marquee":         render_drive_in_marquee,
    "lobby_card_amber":         render_lobby_card_amber,
    "hammer_horror":            render_hammer_horror,
    "spaghetti_western_dust":   render_spaghetti_western_dust,
    "hong_kong_kungfu":         render_hong_kong_kungfu,
    "hitchcock_silhouette":     render_hitchcock_silhouette,
}
