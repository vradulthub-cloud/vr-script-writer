"""
Pack 13 — Cartoon / children's.

Ten treatments evoking cartoon, children's media, and toy-aisle aesthetics:
saturday morning, anime battle, lego brick, picture book, candy funhouse,
retro cereal, comic pop, kids show logo, sticker bomb, fairground carnival.
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


# ─── 1. Saturday morning ──────────────────────────────────────────────────────

def render_saturday_morning(title: str, rng: random.Random) -> Image.Image:
    """80s/90s Saturday-morning cartoon logo — chunky comic-book sans with
    rainbow gradient face and zigzag underline accent."""
    n     = len(title)
    size  = 144 if n <= 12 else (110 if n <= 20 else 86)
    font  = F("comic", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)
    shear = 0.12

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 8)
        sl   = flat_color(sm, (10, 10, 14))
        face = colorize(mask, [(255, 100, 100), (255, 200, 30), (40, 200, 100)])
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(20, 20, 30), shadow_alpha=160)
        sh   = drop_shadow(sm, 8, 12, blur=4, alpha=220)
        img  = composite(sh, sl, face, bev, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs) + 50
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2 + 60
    canvas = Image.new("RGBA", (W, H), (40, 200, 230, 255))   # sky blue

    # Zigzag accent below text
    cd = ImageDraw.Draw(canvas)
    zigzag_y = H - 40
    zw = 30
    pts = []
    for x in range(margin, W - margin, zw):
        pts.append((x, zigzag_y))
        pts.append((x + zw // 2, zigzag_y + 12))
    if pts:
        cd.line(pts, fill=(255, 220, 30, 255), width=4)

    y = margin + 20
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 2. Anime battle ──────────────────────────────────────────────────────────

def render_anime_battle(title: str, rng: random.Random) -> Image.Image:
    """Shonen anime battle title card — bold sheared sans with lightning-
    bolt halftone speed lines, crimson + electric yellow palette."""
    n     = len(title)
    size  = 150 if n <= 12 else (118 if n <= 20 else 92)
    font  = F("heavy", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 14)
    shear = 0.22

    palettes = [
        ((255, 240, 0),   (220, 30, 30),   (10, 10, 14)),    # yellow on red
        ((255, 110, 30),  (50, 30, 80),    (10, 10, 14)),    # orange on plum
    ]
    fg, accent, ink = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 9)
        sl   = flat_color(sm, ink)
        face = flat_color(mask, fg)
        ext  = extrude(sm, 9, 130, accent, tuple(max(0, c - 80) for c in accent))
        sh   = drop_shadow(mask, 8, 12, blur=4, alpha=220)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=tuple(max(0, c - 80) for c in fg),
                            shadow_alpha=160)
        img  = composite(sh, ext, sl, face, bev, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs) + 80
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1) + 40
    margin = 30
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*accent, 255))

    # Speed lines from edges toward center
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(20, 40)):
        edge = rng.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            x_start = rng.randint(0, W)
            y_start = 0
            x_end = x_start + rng.randint(-40, 40)
            y_end = rng.randint(40, 100)
        elif edge == "bottom":
            x_start = rng.randint(0, W)
            y_start = H
            x_end = x_start + rng.randint(-40, 40)
            y_end = H - rng.randint(40, 100)
        elif edge == "left":
            x_start = 0
            y_start = rng.randint(0, H)
            x_end = rng.randint(40, 100)
            y_end = y_start + rng.randint(-40, 40)
        else:
            x_start = W
            y_start = rng.randint(0, H)
            x_end = W - rng.randint(40, 100)
            y_end = y_start + rng.randint(-40, 40)
        cd.line([(x_start, y_start), (x_end, y_end)],
                fill=(255, 255, 255, rng.randint(60, 150)), width=2)

    y = margin + 20
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. Lego brick ────────────────────────────────────────────────────────────

def render_lego_brick(title: str, rng: random.Random) -> Image.Image:
    """LEGO/toy-brick aesthetic — chunky rounded sans on a primary-color
    rounded panel with stud dots above. Toy-aisle bright."""
    n     = len(title)
    size  = 140 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("rounded", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((250, 220, 30),  (220, 30, 30)),    # yellow on red
        ((250, 200, 30),  (40, 60, 200)),    # yellow on blue
        ((255, 255, 255), (40, 130, 80)),    # white on green
    ]
    fg, panel = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=tuple(max(0, c - 100) for c in fg),
                            shadow_alpha=140)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    pad = 50
    W = text_w + pad * 2
    H = text_h + pad * 2 + 20
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    cd = ImageDraw.Draw(canvas)
    cd.rounded_rectangle([(8, 24), (W - 8, H - 8)], radius=20, fill=(*panel, 255))

    # Brick studs along the top
    stud_r = 14
    stud_spacing = 50
    n_studs = max(1, (W - 40) // stud_spacing)
    stud_y = 24
    start_x = (W - n_studs * stud_spacing) // 2 + stud_spacing // 2
    for i in range(n_studs):
        cx = start_x + i * stud_spacing
        cd.ellipse([cx - stud_r, stud_y - stud_r, cx + stud_r, stud_y + stud_r],
                   fill=(*panel, 255), outline=(*tuple(max(0, c - 60) for c in panel), 255))
        cd.ellipse([cx - stud_r + 5, stud_y - stud_r + 5,
                    cx + stud_r - 5, stud_y + stud_r - 5],
                   fill=(*tuple(min(255, c + 60) for c in panel), 200))

    y = pad
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Picture book ──────────────────────────────────────────────────────────

def render_picture_book(title: str, rng: random.Random) -> Image.Image:
    """Illustrated children's picture-book cover — rounded warm serif on
    paper-cream, little hand-drawn dots/stars accent. Cozy."""
    n     = len(title)
    size  = 130 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("rounded", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((220, 100, 80),  (244, 232, 200)),    # coral on cream
        ((100, 130, 200), (244, 234, 218)),    # blue on cream
        ((100, 160, 100), (244, 232, 210)),    # mint on cream
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=140,
                            shadow_color=tuple(max(0, c - 60) for c in fg),
                            shadow_alpha=120)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Hand-drawn dots and stars as accents
    cd = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(10, 20)):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        # Avoid placing decorations directly on the title band
        if margin < y < H - margin:
            continue
        if rng.random() < 0.5:
            r = rng.randint(3, 8)
            cd.ellipse([x - r, y - r, x + r, y + r], fill=(*fg, 220))
        else:
            r = rng.randint(5, 10)
            pts = []
            for i in range(10):
                ang = math.radians(i * 36 - 90)
                rr = r if i % 2 == 0 else r * 0.4
                pts.append((x + rr * math.cos(ang), y + rr * math.sin(ang)))
            cd.polygon(pts, fill=(*fg, 220))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Candy funhouse ────────────────────────────────────────────────────────

def render_candy_funhouse(title: str, rng: random.Random) -> Image.Image:
    """Bubblegum candy/funhouse — chunky bubble letters in alternating
    pastel pink/turquoise/lavender, glossy highlight, polka-dot background."""
    n     = len(title)
    size  = 144 if n <= 14 else (110 if n <= 22 else 86)
    font  = F("rounded", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palette = [(255, 130, 200), (130, 220, 240), (180, 140, 240), (255, 220, 130)]

    line_imgs = []
    for i, ln in enumerate(lines):
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 8)
        sl   = flat_color(sm, (50, 30, 80))
        col  = palette[i % len(palette)]
        face = flat_color(mask, col)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125, smoothness=2.0,
                            highlight_color=(255, 255, 255), highlight_alpha=240,
                            shadow_color=tuple(max(0, c - 80) for c in col),
                            shadow_alpha=160)
        sh   = drop_shadow(sm, 6, 9, blur=4, alpha=220)
        img  = composite(sh, sl, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (255, 240, 250, 255))

    # Polka-dot background
    cd = ImageDraw.Draw(canvas)
    dot_spacing = 36
    for y in range(0, H, dot_spacing):
        for x in range(0, W, dot_spacing):
            ox = (dot_spacing // 2) if (y // dot_spacing) % 2 == 0 else 0
            r = 4
            cd.ellipse([x + ox - r, y - r, x + ox + r, y + r], fill=(255, 200, 230, 200))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Retro cereal ──────────────────────────────────────────────────────────

def render_retro_cereal(title: str, rng: random.Random) -> Image.Image:
    """Vintage cereal-box mascot logo — chunky retro display, sunburst rays
    behind, kid-aimed saturated palette, deep extrusion."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("retro", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)
    shear = 0.06

    palettes = [
        ((255, 220, 30),  (220, 30, 30),   (40, 30, 80)),
        ((255, 130, 30),  (40, 130, 200),  (15, 20, 60)),
        ((255, 80, 130),  (40, 200, 220),  (10, 14, 40)),
    ]
    fg, ext_c, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 8)
        sl   = flat_color(sm, (10, 10, 14))
        ext  = extrude(sm, 10, 130, ext_c, tuple(max(0, c - 80) for c in ext_c))
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=220,
                            shadow_color=tuple(max(0, c - 100) for c in fg),
                            shadow_alpha=160)
        sh   = drop_shadow(sm, 8, 12, blur=4, alpha=220)
        img  = composite(sh, ext, sl, face, bev, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs) + 60
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2 + 60
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Sunburst rays from center behind text
    cd = ImageDraw.Draw(canvas)
    cx, cy = W // 2, H // 2
    n_rays = 16
    ray_len = max(W, H)
    for i in range(n_rays):
        if i % 2 == 0:
            continue
        ang = (2 * math.pi * i) / n_rays
        # Triangular wedge
        a2 = ang + (math.pi / n_rays) * 0.85
        x1 = cx + int(math.cos(ang) * ray_len)
        y1 = cy + int(math.sin(ang) * ray_len)
        x2 = cx + int(math.cos(a2) * ray_len)
        y2 = cy + int(math.sin(a2) * ray_len)
        cd.polygon([(cx, cy), (x1, y1), (x2, y2)], fill=(*fg, 60))

    y = margin + 20
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Comic pop ─────────────────────────────────────────────────────────────

def render_comic_pop(title: str, rng: random.Random) -> Image.Image:
    """Comic-book onomatopoeia / pop-art — heavy sheared sans with halftone
    dots inside, "POW!"-style burst behind. Lichtenstein meets Marvel."""
    n     = len(title)
    size  = 144 if n <= 12 else (110 if n <= 20 else 86)
    font  = F("comic", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)
    shear = 0.18

    palettes = [
        ((255, 220, 30),   (220, 30, 30),    (40, 50, 200)),    # yellow/red/blue
        ((255, 100, 130),  (40, 200, 220),   (10, 10, 14)),
    ]
    fg, ext_c, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 8)
        sl   = flat_color(sm, (10, 10, 14))
        ext  = extrude(sm, 8, 130, ext_c, tuple(max(0, c - 80) for c in ext_c))
        face = flat_color(mask, fg)
        # Halftone dot overlay
        ht = halftone_fill(mask, accent, dot_size=4, spacing=7)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=tuple(max(0, c - 80) for c in fg),
                            shadow_alpha=160)
        sh   = drop_shadow(sm, 6, 9, blur=3, alpha=220)
        img  = composite(sh, ext, sl, face, ht, bev, size=mask.size)
        img  = shear_image(img, shear)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs) + 80
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 30
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (240, 232, 218, 255))

    # Burst star behind text
    cd = ImageDraw.Draw(canvas)
    cx, cy = W // 2, H // 2
    burst_outer = max(W, H) // 2
    burst_inner = burst_outer // 2
    n_points = 12
    points = []
    for i in range(n_points * 2):
        ang = 2 * math.pi * i / (n_points * 2)
        r = burst_outer if i % 2 == 0 else burst_inner
        points.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    cd.polygon(points, fill=(*ext_c, 180))

    y = margin + 20
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Kids show logo ────────────────────────────────────────────────────────

def render_kids_show_logo(title: str, rng: random.Random) -> Image.Image:
    """Children's TV show logo — thick rounded sans with extra-thick outline,
    bouncy baseline, primary colors. Sesame Street / Bluey energy."""
    n     = len(title)
    size  = 144 if n <= 14 else (112 if n <= 22 else 88)
    font  = F("rounded", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((255, 220, 30),  (40, 60, 200),   (240, 30, 60)),
        ((255, 130, 130), (40, 30, 80),    (255, 220, 30)),
        ((130, 220, 100), (10, 10, 14),    (255, 130, 30)),
    ]
    fg, stroke_c, accent = palettes[rng.randrange(len(palettes))]

    word_imgs = []
    for ln in lines:
        for w in ln.split():
            mask = make_mask(w, F("rounded", size, rng) or F("comic", size, rng), pad=20)
            sm   = dilate(mask, 11)
            sl   = flat_color(sm, stroke_c)
            face = flat_color(mask, fg)
            bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                                highlight_color=(255, 255, 255), highlight_alpha=240,
                                shadow_color=tuple(max(0, c - 100) for c in fg),
                                shadow_alpha=140)
            sh   = drop_shadow(sm, 6, 9, blur=2, alpha=220)
            img  = composite(sh, sl, face, bev, size=mask.size)
            word_imgs.append(img)

    # Place words with bouncy baseline
    if not word_imgs:
        word_imgs = [Image.new("RGBA", (200, 100), (0, 0, 0, 0))]
    x_cursor = 60
    H = max(i.height for i in word_imgs) + 200
    W = sum(i.width for i in word_imgs) + 80 * len(word_imgs) + 80
    canvas = Image.new("RGBA", (W, H), (255, 230, 240, 255))

    placements = []
    for i, img in enumerate(word_imgs):
        bounce = math.sin(i * 1.2) * 22
        ay = (H - img.height) // 2 + int(bounce)
        canvas.paste(img, (x_cursor, ay), img)
        placements.append((x_cursor, ay, img.width, img.height))
        x_cursor += img.width + 30

    if placements:
        min_x = max(0, min(p[0] for p in placements) - 30)
        max_x = min(W, max(p[0] + p[2] for p in placements) + 30)
        min_y = max(0, min(p[1] for p in placements) - 30)
        max_y = min(H, max(p[1] + p[3] for p in placements) + 30)
        canvas = canvas.crop((min_x, min_y, max_x, max_y))
    return canvas


# ─── 9. Sticker bomb ──────────────────────────────────────────────────────────

def render_sticker_bomb(title: str, rng: random.Random) -> Image.Image:
    """Skater / sticker-pack logotype — chunky display with thick white
    border and offset shadow, like a die-cut sticker on dark vinyl."""
    n     = len(title)
    size  = 144 if n <= 12 else (110 if n <= 20 else 86)
    font  = F("heavy", size, rng) or F("retro", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 12)

    palettes = [
        ((255, 80, 130),  (240, 232, 218), (10, 10, 14)),    # hot pink
        ((255, 200, 30),  (240, 232, 218), (10, 10, 14)),    # neon yellow
        ((40, 230, 180),  (240, 232, 218), (10, 10, 14)),    # mint
    ]
    fg, white, ink = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        # Thick white "die-cut" border
        sm_outer = dilate(mask, 14)
        die_cut = flat_color(sm_outer, white)
        # Inner solid colored fill
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=tuple(max(0, c - 100) for c in fg),
                            shadow_alpha=120)
        sh   = drop_shadow(sm_outer, 8, 12, blur=4, alpha=220)
        img  = composite(sh, die_cut, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (28, 28, 36, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Fairground carnival ──────────────────────────────────────────────────

def render_fairground_carnival(title: str, rng: random.Random) -> Image.Image:
    """Vintage carnival / circus poster — heavy slab serif + showman accents,
    red panel, gold scroll. Big top energy."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("retro", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = colorize(mask, [(255, 248, 200), (240, 200, 80), (160, 90, 20)])
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 252, 220), highlight_alpha=220,
                            shadow_color=(80, 30, 8), shadow_alpha=200)
        sh   = drop_shadow(mask, 5, 8, blur=4, alpha=220)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (200, 30, 30, 255))   # carnival red

    cd = ImageDraw.Draw(canvas)
    # Vertical pinstripes — circus tent feel
    stripe_w = 30
    for i, sx in enumerate(range(0, W, stripe_w)):
        if i % 2 == 0:
            cd.rectangle([(sx, 0), (sx + stripe_w, H)], fill=(220, 220, 200, 100))

    # Heavy gold rule top + bottom
    rule_w = int(W * 0.85)
    cd.rectangle([((W - rule_w) // 2, 26), ((W + rule_w) // 2, 32)],
                 fill=(220, 168, 60, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.rectangle([((W - rule_w) // 2, y + 14), ((W + rule_w) // 2, y + 20)],
                 fill=(220, 168, 60, 255))
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK13_CARTOON_TREATMENTS = {
    "saturday_morning":      render_saturday_morning,
    "anime_battle":          render_anime_battle,
    "lego_brick":            render_lego_brick,
    "picture_book":          render_picture_book,
    "candy_funhouse":        render_candy_funhouse,
    "retro_cereal":          render_retro_cereal,
    "comic_pop":             render_comic_pop,
    "kids_show_logo":        render_kids_show_logo,
    "sticker_bomb":          render_sticker_bomb,
    "fairground_carnival":   render_fairground_carnival,
}
