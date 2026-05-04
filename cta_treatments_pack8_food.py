"""
Pack 8 — Food & drink.

Ten treatments evoking food/beverage design conventions: cocktail menu,
diner sign, French bistro, sushi bar, ramen shop, bakery, coffee roaster,
craft beer label, wine label, fine dining.
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


# ─── 1. Cocktail menu ─────────────────────────────────────────────────────────

def render_cocktail_menu(title: str, rng: random.Random) -> Image.Image:
    """Speakeasy / hotel-bar cocktail menu — elegant condensed serif on
    dark teal/oxblood, gold rule, refined letter spacing."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 24 else 76)
    spacing = max(8, size // 14)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((220, 168, 60),  (20, 40, 50)),     # gold on dark teal
        ((220, 168, 60),  (50, 20, 30)),     # gold on oxblood
        ((232, 220, 200), (28, 30, 36)),     # cream on near-black
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=tuple(min(255, c + 40) for c in fg),
                            highlight_alpha=120,
                            shadow_color=tuple(max(0, c - 60) for c in fg),
                            shadow_alpha=120)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.6)
    cd.line([((W - rule_w) // 2, 38), ((W + rule_w) // 2, 38)], fill=(*fg, 255), width=1)
    cd.line([((W - rule_w) // 2, 44), ((W + rule_w) // 2, 44)], fill=(*fg, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([((W - rule_w) // 2, y + 12), ((W + rule_w) // 2, y + 12)], fill=(*fg, 255), width=1)
    cd.line([((W - rule_w) // 2, y + 18), ((W + rule_w) // 2, y + 18)], fill=(*fg, 255), width=1)
    return canvas


# ─── 2. Diner sign ────────────────────────────────────────────────────────────

def render_diner_sign(title: str, rng: random.Random) -> Image.Image:
    """1950s American diner sign — chunky retro display with neon outline
    and rounded panel. Classic roadside aesthetic."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("retro", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((255, 100, 100), (40, 200, 220),  (240, 232, 218)),  # red panel + cyan neon
        ((250, 220, 60),  (220, 30, 80),   (40, 30, 60)),     # yellow panel + pink neon
    ]
    panel, glow, fg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        # Neon outer glow
        bloom = mask.filter(ImageFilter.GaussianBlur(8))
        glow_layer = flat_color(bloom, glow)
        glow_a = glow_layer.split()[3].point(lambda p: int(p * 0.65))
        glow_layer.putalpha(glow_a)
        face = flat_color(mask, fg)
        outline = outline_stroke(mask, width=3, rgb=glow, alpha=255)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=180,
                            shadow_color=(20, 20, 24), shadow_alpha=120)
        img  = composite(glow_layer, face, outline, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    pad = 50
    W = text_w + pad * 2
    H = text_h + pad * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(canvas)
    cd.rounded_rectangle([(8, 8), (W - 8, H - 8)], radius=22, fill=(*panel, 255))

    y = pad
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. French bistro ─────────────────────────────────────────────────────────

def render_french_bistro(title: str, rng: random.Random) -> Image.Image:
    """Parisian bistro chalkboard — script font in chalk-white on slate
    green/black. Hand-written cursive with tiny imperfection."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("script", size, rng) or F("luxury", size, rng)
    lines = wrap_chars(title, 16)

    palettes = [
        ((250, 245, 235), (32, 50, 42)),     # chalk on slate green
        ((250, 245, 235), (28, 28, 32)),     # chalk on near-black
    ]
    chalk, slate = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=20)
        bled = ink_bleed(mask, radius=1.4, strength=0.5, irregularity=0.7)
        face = flat_color(bled, chalk)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*slate, 255))

    # Faint chalk-dust speckle
    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 800):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(*chalk, rng.randint(20, 60)))

    # Decorative double-rule top + bottom in chalk
    rule_w = int(W * 0.55)
    cd.line([((W - rule_w) // 2, 28), ((W + rule_w) // 2, 28)], fill=(*chalk, 200), width=1)
    cd.line([((W - rule_w) // 2, 34), ((W + rule_w) // 2, 34)], fill=(*chalk, 200), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([((W - rule_w) // 2, y + 14), ((W + rule_w) // 2, y + 14)], fill=(*chalk, 200), width=1)
    cd.line([((W - rule_w) // 2, y + 20), ((W + rule_w) // 2, y + 20)], fill=(*chalk, 200), width=1)
    return canvas


# ─── 4. Sushi bar ─────────────────────────────────────────────────────────────

def render_sushi_bar(title: str, rng: random.Random) -> Image.Image:
    """Japanese sushi bar — minimal cream background, bold ink-brush
    feeling sans, hinomaru red circle accent."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=2.0, strength=0.55, irregularity=0.65)
        face = flat_color(bled, (24, 22, 22))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 100
    margin_y = 80
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 30
    canvas = Image.new("RGBA", (W, H), (244, 234, 220, 255))

    cd = ImageDraw.Draw(canvas)
    # Hinomaru circle, off-center
    cr = max(36, min(W, H) // 9)
    cx = W - margin_x // 2
    cy = margin_y // 2
    cd.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(200, 30, 40, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Ramen shop ────────────────────────────────────────────────────────────

def render_ramen_shop(title: str, rng: random.Random) -> Image.Image:
    """Tokyo ramen shop curtain (noren) — vertical bold sans on warm
    indigo/maroon panel with stripe accents, steam-like soft fade."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("heavy", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((30, 40, 90),    (240, 230, 200), (220, 220, 220)),  # indigo/cream
        ((110, 30, 40),   (240, 232, 218), (220, 220, 220)),  # maroon/cream
    ]
    bg, fg, stripe = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 240), highlight_alpha=160,
                            shadow_color=tuple(max(0, c - 60) for c in fg),
                            shadow_alpha=120)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    pad = 40
    W = text_w + pad * 2
    H = text_h + pad * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Vertical stripes — noren panel feel
    cd = ImageDraw.Draw(canvas)
    n_stripes = 4
    stripe_w = W // (n_stripes * 4)
    for i in range(n_stripes):
        x = (W // n_stripes) * i + (W // n_stripes - stripe_w) // 2
        cd.rectangle([(x, 8), (x + stripe_w, 24)], fill=(*stripe, 200))

    y = pad + 10
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Bakery sign ───────────────────────────────────────────────────────────

def render_bakery_sign(title: str, rng: random.Random) -> Image.Image:
    """Old-world bakery — warm amber panel with blackboard-script
    typography, decorative flourishes, weathered cream paper feel."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("script", size, rng) or F("luxury", size, rng)
    lines = wrap_chars(title, 18)

    palettes = [
        ((40, 30, 22),    (232, 200, 150)),    # warm ink on amber
        ((90, 50, 30),    (244, 220, 180)),    # walnut on cream
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.4, strength=0.4, irregularity=0.55)
        face = flat_color(bled, fg)
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    cd = ImageDraw.Draw(canvas)
    # Speckle
    for _ in range(W * H // 600):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(*fg, rng.randint(20, 60)))

    # Decorative dotted scroll above and below
    dot_w = int(W * 0.55)
    for ry in (28, H - 28):
        for x in range((W - dot_w) // 2, (W + dot_w) // 2, 12):
            cd.ellipse([x - 2, ry - 2, x + 2, ry + 2], fill=(*fg, 220))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 7. Coffee roaster ────────────────────────────────────────────────────────

def render_coffee_roaster(title: str, rng: random.Random) -> Image.Image:
    """Third-wave coffee roaster bag — mark-making slab serif, restrained
    earthy palette, a single decorative mark (filled circle as sun/coffee bean)."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    spacing = max(7, size // 16)
    font  = F("slab", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 18)

    palettes = [
        ((40, 22, 14),    (232, 220, 200)),    # espresso on parchment
        ((232, 220, 200), (40, 22, 14)),       # parchment on espresso
        ((100, 60, 40),   (240, 232, 218)),    # walnut on cream
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
    margin_x = 70
    margin_y = 80
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    # Single filled circle accent
    cd = ImageDraw.Draw(canvas)
    cr = max(20, min(W, H) // 14)
    cx = W // 2
    cy = margin_y - 30
    cd.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(*fg, 255))

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Craft beer label ──────────────────────────────────────────────────────

def render_craft_beer_label(title: str, rng: random.Random) -> Image.Image:
    """Modern craft beer can — bold display sans on a saturated solid panel,
    thick outline, distinctive flat color block."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((250, 220, 30),  (28, 30, 38)),     # mustard on near-black
        ((220, 60, 80),   (240, 232, 218)),  # cherry on cream
        ((40, 130, 110),  (240, 230, 200)),  # forest on cream
    ]
    fg, bg = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 6)
        sl   = flat_color(sm, tuple(max(0, c - 80) for c in fg))
        face = flat_color(mask, fg)
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 240), highlight_alpha=160,
                            shadow_color=tuple(max(0, c - 100) for c in fg),
                            shadow_alpha=140)
        img  = composite(sl, face, bev, size=mask.size)
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


# ─── 9. Wine label ────────────────────────────────────────────────────────────

def render_wine_label(title: str, rng: random.Random) -> Image.Image:
    """Refined wine bottle label — small-tracked classic serif on cream
    paper, gold double-rule, restrained dignity."""
    n     = len(title)
    size  = 104 if n <= 14 else (84 if n <= 22 else 66)
    spacing = max(10, size // 12)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, (40, 20, 22))
        bev  = bevel_emboss(mask, depth=2, angle_deg=120,
                            highlight_color=(140, 80, 80), highlight_alpha=80,
                            shadow_color=(20, 8, 10), shadow_alpha=120)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 60
    canvas = Image.new("RGBA", (W, H), (244, 232, 200, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.52)
    rule_x_l = (W - rule_w) // 2
    rule_x_r = rule_x_l + rule_w
    # Gold double-rule top
    for ry in (margin // 2 - 4, margin // 2 + 4):
        cd.line([(rule_x_l, ry), (rule_x_r, ry)], fill=(180, 130, 30, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    for ry in (y + 14, y + 22):
        cd.line([(rule_x_l, ry), (rule_x_r, ry)], fill=(180, 130, 30, 255), width=1)
    return canvas


# ─── 10. Fine dining ──────────────────────────────────────────────────────────

def render_fine_dining(title: str, rng: random.Random) -> Image.Image:
    """Michelin-restaurant menu cover — quiet refined typography, narrow
    column hairline rule, deep ivory paper, muted gold ink."""
    n     = len(title)
    size  = 96 if n <= 14 else (76 if n <= 24 else 60)
    spacing = max(14, size // 8)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, (130, 90, 30))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin_x = 110
    margin_y = 110
    W = text_w + margin_x * 2
    H = text_h + margin_y * 2
    canvas = Image.new("RGBA", (W, H), (244, 240, 226, 255))

    cd = ImageDraw.Draw(canvas)
    # Single very small narrow rule centered above
    rule_w = int(W * 0.06)
    cd.line([((W - rule_w) // 2, margin_y - 30),
             ((W + rule_w) // 2, margin_y - 30)],
            fill=(130, 90, 30, 255), width=1)

    y = margin_y
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([((W - rule_w) // 2, y + 22),
             ((W + rule_w) // 2, y + 22)],
            fill=(130, 90, 30, 255), width=1)
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK8_FOOD_TREATMENTS = {
    "cocktail_menu":     render_cocktail_menu,
    "diner_sign":        render_diner_sign,
    "french_bistro":     render_french_bistro,
    "sushi_bar":         render_sushi_bar,
    "ramen_shop":        render_ramen_shop,
    "bakery_sign":       render_bakery_sign,
    "coffee_roaster":    render_coffee_roaster,
    "craft_beer_label":  render_craft_beer_label,
    "wine_label":        render_wine_label,
    "fine_dining":       render_fine_dining,
}
