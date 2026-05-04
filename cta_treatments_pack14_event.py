"""
Pack 14 — Wedding & event / formal invitation.

Ten treatments evoking wedding invitation, formal event, ceremonial, and
celebration design conventions: wedding invitation, save the date, gala
poster, rsvp card, bar mitzvah, baby shower, anniversary, retirement,
graduation, holiday card.
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


# ─── 1. Wedding invitation ────────────────────────────────────────────────────

def render_wedding_invitation(title: str, rng: random.Random) -> Image.Image:
    """Classical wedding invitation — calligraphic script + small caps
    accent, gold rule, ivory paper, ornamental flourishes."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("script", size, rng) or F("luxury", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title, 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.0, strength=0.35, irregularity=0.5)
        face = flat_color(bled, (40, 30, 20))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 14
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 90
    W = text_w + margin * 2
    H = text_h + margin * 2 + 50
    canvas = Image.new("RGBA", (W, H), (250, 244, 232, 255))

    cd = ImageDraw.Draw(canvas)
    # Decorative quadruple-rule top
    rule_w = int(W * 0.5)
    rx_l = (W - rule_w) // 2
    rx_r = rx_l + rule_w
    for ry in (38, 44, 50, 56):
        cd.line([(rx_l, ry), (rx_r, ry)], fill=(180, 130, 60, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    for ry in (y + 14, y + 20, y + 26, y + 32):
        cd.line([(rx_l, ry), (rx_r, ry)], fill=(180, 130, 60, 255), width=1)
    return canvas


# ─── 2. Save the date ─────────────────────────────────────────────────────────

def render_save_the_date(title: str, rng: random.Random) -> Image.Image:
    """Modern save-the-date — sans-serif heavy with a delicate hand-script
    accent line. Clean, dated, contemporary."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("luxury", size, rng) or F("serif", size, rng) or F("elegant", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((30, 60, 70),    (240, 232, 218)),    # deep teal on cream
        ((90, 60, 80),    (244, 234, 218)),    # plum on cream
        ((40, 50, 60),    (244, 240, 230)),    # slate on cream
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 90
    margin_y = 90
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    # Single delicate hairline rule below title block
    rule_w = int(W * 0.18)
    cd.line([((W - rule_w) // 2, margin_y - 30), ((W + rule_w) // 2, margin_y - 30)],
            fill=(*fg, 255), width=1)

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([((W - rule_w) // 2, y + 18), ((W + rule_w) // 2, y + 18)],
            fill=(*fg, 255), width=1)
    return canvas


# ─── 3. Gala poster ───────────────────────────────────────────────────────────

def render_gala_poster(title: str, rng: random.Random) -> Image.Image:
    """Black-tie gala poster — gold metallic on near-black, refined serif,
    ornate gold double-rule. High formality."""
    n     = len(title)
    size  = 132 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = colorize(mask, [(255, 240, 180), (220, 168, 60), (130, 80, 14)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 252, 220), highlight_alpha=220,
                            shadow_color=(60, 30, 8), shadow_alpha=200)
        rim  = fresnel_metallic(mask, base_color=(220, 168, 60),
                                rim_color=(255, 230, 160), rim_power=2.4)
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
    H = text_h + margin * 2 + 60
    canvas = Image.new("RGBA", (W, H), (16, 12, 16, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.7)
    rx_l = (W - rule_w) // 2
    rx_r = rx_l + rule_w
    # Triple gold rule above
    for ry in (38, 44, 50):
        cd.line([(rx_l, ry), (rx_r, ry)], fill=(220, 168, 60, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    for ry in (y + 18, y + 24, y + 30):
        cd.line([(rx_l, ry), (rx_r, ry)], fill=(220, 168, 60, 255), width=1)
    return canvas


# ─── 4. RSVP card ─────────────────────────────────────────────────────────────

def render_rsvp_card(title: str, rng: random.Random) -> Image.Image:
    """Refined small-format response card — small wide-tracked all-caps in
    deep navy on natural cream, single small ornament."""
    n     = len(title)
    size  = 84 if n <= 14 else (68 if n <= 24 else 56)
    spacing = max(20, size // 5)
    font  = F("luxury", size, rng) or F("serif", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, (28, 36, 60))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 110
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (244, 240, 226, 255))

    cd = ImageDraw.Draw(canvas)
    # Small diamond ornament between hairline
    cx = W // 2
    rule_w = 90
    cd.line([(cx - rule_w, margin // 2), (cx - 14, margin // 2)],
            fill=(28, 36, 60, 255), width=1)
    cd.line([(cx + 14, margin // 2), (cx + rule_w, margin // 2)],
            fill=(28, 36, 60, 255), width=1)
    d = 6
    cd.polygon([(cx, margin // 2 - d), (cx + d, margin // 2),
                (cx, margin // 2 + d), (cx - d, margin // 2)],
               fill=(28, 36, 60, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Bar mitzvah ───────────────────────────────────────────────────────────

def render_bar_mitzvah(title: str, rng: random.Random) -> Image.Image:
    """Celebratory bar/bat mitzvah — ornate serif on cream with deep blue
    + gold double-rule, formal but festive."""
    n     = len(title)
    size  = 120 if n <= 14 else (94 if n <= 22 else 74)
    spacing = max(8, size // 14)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = colorize(mask, [(40, 60, 130), (20, 30, 80)])
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(180, 200, 230), highlight_alpha=160,
                            shadow_color=(10, 14, 40), shadow_alpha=160)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 50
    canvas = Image.new("RGBA", (W, H), (244, 240, 226, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.6)
    rx_l = (W - rule_w) // 2
    rx_r = rx_l + rule_w
    # Blue + gold double-rule
    cd.line([(rx_l, margin // 2 - 4), (rx_r, margin // 2 - 4)], fill=(40, 60, 130, 255), width=2)
    cd.line([(rx_l, margin // 2 + 6), (rx_r, margin // 2 + 6)], fill=(220, 168, 60, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([(rx_l, y + 14), (rx_r, y + 14)], fill=(220, 168, 60, 255), width=1)
    cd.line([(rx_l, y + 24), (rx_r, y + 24)], fill=(40, 60, 130, 255), width=2)
    return canvas


# ─── 6. Baby shower ───────────────────────────────────────────────────────────

def render_baby_shower(title: str, rng: random.Random) -> Image.Image:
    """Soft pastel baby-shower aesthetic — rounded sans on a delicate
    blush/mint gradient with tiny star + heart accents."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("rounded", size, rng) or F("script", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title.upper(), 16)

    palettes = [
        ((150, 80, 110),  (252, 230, 235), (252, 220, 220)),    # rose on blush
        ((60, 100, 130),  (220, 240, 240), (220, 230, 240)),    # blue on mint
    ]
    fg, bg_top, bg_bot = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=3, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=160,
                            shadow_color=tuple(max(0, c - 40) for c in fg),
                            shadow_alpha=120)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Soft vertical gradient
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        r = int(bg_top[0] * (1 - t) + bg_bot[0] * t)
        g = int(bg_top[1] * (1 - t) + bg_bot[1] * t)
        b = int(bg_top[2] * (1 - t) + bg_bot[2] * t)
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    # Tiny scattered heart/star accents
    for _ in range(rng.randint(8, 16)):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        if margin < y < H - margin:
            continue
        if rng.random() < 0.5:
            r = rng.randint(3, 6)
            cd.ellipse([x - r, y - r, x + r, y + r], fill=(*fg, 200))
        else:
            cd.text((x, y), "★", fill=(*fg, 200))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Anniversary ───────────────────────────────────────────────────────────

def render_anniversary(title: str, rng: random.Random) -> Image.Image:
    """Wedding anniversary — refined didone serif in champagne gold on
    deep burgundy, ornate frame, ceremonial dignity."""
    n     = len(title)
    size  = 128 if n <= 14 else (100 if n <= 22 else 78)
    spacing = max(8, size // 14)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = colorize(mask, [(252, 220, 140), (210, 168, 60), (130, 80, 14)])
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(255, 248, 200), highlight_alpha=200,
                            shadow_color=(50, 20, 4), shadow_alpha=160)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 50
    canvas = Image.new("RGBA", (W, H), (60, 22, 30, 255))

    cd = ImageDraw.Draw(canvas)
    # Decorative gold frame inside the canvas
    cd.rectangle([(20, 20), (W - 20, H - 20)], outline=(220, 168, 60, 220), width=2)
    cd.rectangle([(28, 28), (W - 28, H - 28)], outline=(220, 168, 60, 160), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Retirement ────────────────────────────────────────────────────────────

def render_retirement(title: str, rng: random.Random) -> Image.Image:
    """Retirement celebration — warm beach/sunset palette, friendly script
    above a serif tagline, hand-drawn dot accents."""
    n     = len(title)
    size  = 128 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("script", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title, 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        bled = ink_bleed(mask, radius=1.4, strength=0.4, irregularity=0.6)
        face = colorize(bled, [(220, 100, 60), (140, 50, 50)])
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Sunset-warm gradient
    cd = ImageDraw.Draw(canvas)
    stops = [(255, 220, 170), (255, 180, 130), (240, 130, 80)]
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        idx = min(int(t * (len(stops) - 1)), len(stops) - 2)
        frac = t * (len(stops) - 1) - idx
        r = int(stops[idx][0] * (1 - frac) + stops[idx + 1][0] * frac)
        g = int(stops[idx][1] * (1 - frac) + stops[idx + 1][1] * frac)
        b = int(stops[idx][2] * (1 - frac) + stops[idx + 1][2] * frac)
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Graduation ────────────────────────────────────────────────────────────

def render_graduation(title: str, rng: random.Random) -> Image.Image:
    """Cap-and-gown graduation — heavy serif in school colors, athletic-
    crest energy, dignified."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("athletic", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((40, 70, 130),  (240, 200, 30),  (240, 232, 218)),  # navy/gold
        ((140, 30, 30),  (200, 200, 200), (240, 232, 218)),  # crimson/silver
        ((20, 80, 60),   (240, 200, 30),  (240, 232, 218)),  # forest/gold
    ]
    fg, accent, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 6)
        sl   = flat_color(sm, accent)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=tuple(min(255, c + 80) for c in fg),
                            highlight_alpha=180,
                            shadow_color=tuple(max(0, c - 60) for c in fg),
                            shadow_alpha=180)
        sh   = drop_shadow(mask, 4, 7, blur=4, alpha=200)
        img  = composite(sh, sl, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    # Heavy single accent rule top
    rule_w = int(W * 0.7)
    cd.rectangle([((W - rule_w) // 2, 30), ((W + rule_w) // 2, 36)],
                 fill=(*accent, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Holiday card ─────────────────────────────────────────────────────────

def render_holiday_card(title: str, rng: random.Random) -> Image.Image:
    """Christmas / holiday card — refined script in cranberry red on
    forest-green, gold double-rule, heritage warmth."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 74)
    font  = F("script", size, rng) or F("luxury", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title, 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.0, strength=0.35, irregularity=0.55)
        face = colorize(bled, [(220, 60, 60), (140, 20, 20)])
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(255, 220, 220), highlight_alpha=160,
                            shadow_color=(40, 0, 4), shadow_alpha=140)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (24, 56, 38, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.7)
    rx_l = (W - rule_w) // 2
    rx_r = rx_l + rule_w
    for ry in (32, 38, 44):
        cd.line([(rx_l, ry), (rx_r, ry)], fill=(220, 168, 60, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    for ry in (y + 14, y + 20, y + 26):
        cd.line([(rx_l, ry), (rx_r, ry)], fill=(220, 168, 60, 255), width=1)
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK14_EVENT_TREATMENTS = {
    "wedding_invitation":  render_wedding_invitation,
    "save_the_date":       render_save_the_date,
    "gala_poster":         render_gala_poster,
    "rsvp_card":           render_rsvp_card,
    "bar_mitzvah":         render_bar_mitzvah,
    "baby_shower":         render_baby_shower,
    "anniversary":         render_anniversary,
    "retirement":          render_retirement,
    "graduation":          render_graduation,
    "holiday_card":        render_holiday_card,
}
