"""
Pack 11 — Gaming / RPG fantasy.

Ten treatments evoking video game / fantasy / tabletop RPG conventions:
dragon scale, MMO logo, retro pixel, sword steel, magic scroll, neon arcade,
console titanium, dungeon blackletter, fantasy calligraphy, eldritch glow.
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
    scanlines,
    shear_image,
    wide_track_mask,
    wrap_chars,
)


# ─── 1. Dragon scale ──────────────────────────────────────────────────────────

def render_dragon_scale(title: str, rng: random.Random) -> Image.Image:
    """Heavy fantasy logotype — gothic / blackletter face with scale-tile
    pattern overlay, deep emerald or crimson gradient, gold rim."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("gothic", size, rng) or F("luxury", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        [(160, 230, 180), (40, 130, 70),  (10, 50, 30)],   # emerald
        [(255, 180, 100), (180, 50, 30),  (60, 14, 8)],    # ember
        [(220, 200, 240), (90, 50, 180),  (30, 10, 60)],   # amethyst
    ]
    palette = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        sh   = drop_shadow(mask, 4, 8, blur=10, alpha=220)
        face = colorize(mask, palette)
        # Scale-tile pattern: small overlapping arcs
        pat = Image.new("L", mask.size, 0)
        pd = ImageDraw.Draw(pat)
        tile = 14
        for ty in range(-tile, mask.size[1] + tile, tile):
            for tx in range(-tile, mask.size[0] + tile, tile):
                ox = (tile // 2) if (ty // tile) % 2 == 0 else 0
                pd.arc([tx + ox - tile // 2, ty - tile // 2,
                        tx + ox + tile // 2, ty + tile // 2],
                       180, 360, fill=80, width=1)
        pat_layer = flat_color(ImageChops.multiply(mask, pat),
                               tuple(max(0, c - 50) for c in palette[-1]))
        bev  = bevel_emboss(mask, depth=5, angle_deg=120,
                            highlight_color=(255, 250, 210), highlight_alpha=200,
                            shadow_color=palette[-1], shadow_alpha=200)
        rim  = fresnel_metallic(mask, base_color=palette[1],
                                rim_color=(255, 220, 130), rim_power=2.2)
        rim_a = rim.split()[3].point(lambda p: int(p * 0.55))
        rim.putalpha(rim_a)
        img  = composite(sh, face, pat_layer, bev, rim, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
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


# ─── 2. MMO logo ──────────────────────────────────────────────────────────────

def render_mmo_logo(title: str, rng: random.Random) -> Image.Image:
    """Massive online RPG logo — heavy slab with deep extrude, gold metallic
    fresnel, dark fantasy backdrop."""
    n     = len(title)
    size  = 144 if n <= 12 else (110 if n <= 20 else 86)
    font  = F("slab", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 12)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sm   = dilate(mask, 7)
        sl   = flat_color(sm, (40, 30, 18))
        ext  = extrude(sm, 12, 135, (60, 40, 20), (20, 14, 8))
        face = colorize(mask, [(255, 240, 180), (220, 180, 60), (120, 70, 10)])
        bev  = bevel_emboss(mask, depth=6, angle_deg=120, smoothness=1.6,
                            highlight_color=(255, 255, 220), highlight_alpha=220,
                            shadow_color=(60, 30, 8), shadow_alpha=200)
        rim  = fresnel_metallic(mask, base_color=(220, 180, 60),
                                rim_color=(255, 230, 160), rim_power=2.4)
        rim_a = rim.split()[3].point(lambda p: int(p * 0.55))
        rim.putalpha(rim_a)
        sh   = drop_shadow(sm, 8, 12, blur=6, alpha=220)
        img  = composite(sh, ext, sl, face, bev, rim, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 4
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (12, 14, 22, 255))

    # Faint radial glow behind text
    cd = ImageDraw.Draw(canvas)
    for r in range(int(min(W, H) * 0.6), 0, -10):
        a = int(35 * r / (min(W, H) * 0.6))
        cd.ellipse([W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r],
                   outline=(80, 60, 30, a))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. Retro pixel ───────────────────────────────────────────────────────────

def render_retro_pixel(title: str, rng: random.Random) -> Image.Image:
    """8-bit pixel art logo — chunky tech sans rendered as if pixelated.
    Drops the mask through a heavy posterize then nearest-neighbor downsample."""
    n     = len(title)
    size  = 132 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("tech", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    palettes = [
        ((250, 220, 30),  (40, 50, 130),  (220, 30, 60)),    # gold/blue/red
        ((130, 255, 100), (40, 30, 60),   (255, 60, 200)),
        ((60, 240, 240),  (40, 14, 70),   (255, 200, 30)),
    ]
    fg, bg, accent = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=18)
        # Pixelate: downsample then upsample with NEAREST
        scale = 6
        small = mask.resize((max(1, mask.size[0] // scale),
                             max(1, mask.size[1] // scale)), Image.NEAREST)
        pixelated = small.resize(mask.size, Image.NEAREST)
        face = flat_color(pixelated, fg)
        sm   = dilate(pixelated, 4)
        sl   = flat_color(sm, accent)
        sh   = drop_shadow(pixelated, 6, 6, blur=0, alpha=255)
        line_imgs.append(composite(sh, sl, face, size=mask.size))

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (*bg, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Sword steel ───────────────────────────────────────────────────────────

def render_sword_steel(title: str, rng: random.Random) -> Image.Image:
    """Forged steel sword-name aesthetic — heavy serif with brushed motion-
    blur chrome and a sharp diagonal highlight 'cut'."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 84)
    font  = F("serif", size, rng) or F("luxury", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        chrome = motion_blur_chrome(mask, angle_deg=90, length=22,
                                    stops=[(255, 255, 255), (200, 210, 220),
                                           (60, 70, 90), (120, 130, 150),
                                           (255, 255, 255)])
        bev  = bevel_emboss(mask, depth=6, angle_deg=125, smoothness=1.4,
                            highlight_color=(255, 255, 255), highlight_alpha=220,
                            shadow_color=(20, 22, 30), shadow_alpha=200)
        sh   = drop_shadow(mask, 0, 6, blur=12, alpha=200)
        img  = composite(sh, chrome, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 6
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (10, 12, 18, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Magic scroll ──────────────────────────────────────────────────────────

def render_magic_scroll(title: str, rng: random.Random) -> Image.Image:
    """Aged parchment scroll — calligraphic script in burnt umber on warm
    cream, with edge-burn vignette."""
    n     = len(title)
    size  = 120 if n <= 14 else (94 if n <= 22 else 72)
    font  = F("script", size, rng) or F("luxury", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title, 18)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.6, strength=0.45, irregularity=0.65)
        face = flat_color(bled, (60, 28, 14))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (240, 220, 180, 255))

    # Edge burn — darker tone toward the corners
    cd = ImageDraw.Draw(canvas)
    burn_steps = 30
    for i in range(burn_steps):
        a = int(70 * (1 - i / burn_steps))
        cd.rectangle([(i, i), (W - 1 - i, H - 1 - i)],
                     outline=(120, 80, 40, a), width=1)

    # Speckle
    for _ in range(W * H // 600):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(120, 80, 40, rng.randint(20, 60)))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Neon arcade ───────────────────────────────────────────────────────────

def render_neon_arcade(title: str, rng: random.Random) -> Image.Image:
    """1980s arcade marquee — hot neon outline on near-black, double-glow,
    angular tech sans, scanlines for CRT feel."""
    n     = len(title)
    size  = 138 if n <= 14 else (108 if n <= 22 else 86)
    font  = F("tech", size, rng) or F("athletic", size, rng) or F("heavy", size, rng)
    lines = wrap_chars(title.upper(), 14)

    glow_pairs = [
        ((255, 60, 200),  (60, 240, 240)),
        ((255, 200, 30),  (255, 60, 100)),
        ((120, 255, 200), (255, 60, 200)),
    ]
    glow1, glow2 = glow_pairs[rng.randrange(len(glow_pairs))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=24)
        bloom_outer = mask.filter(ImageFilter.GaussianBlur(18))
        bloom_inner = mask.filter(ImageFilter.GaussianBlur(7))
        outer = flat_color(bloom_outer, glow2)
        outer_a = outer.split()[3].point(lambda p: int(p * 0.55))
        outer.putalpha(outer_a)
        inner = flat_color(bloom_inner, glow1)
        inner_a = inner.split()[3].point(lambda p: int(p * 0.7))
        inner.putalpha(inner_a)
        outline = outline_stroke(mask, width=2, rgb=(255, 255, 255), alpha=240)
        face = flat_color(mask, glow1)
        layered = composite(outer, inner, face, outline, size=mask.size)
        line_imgs.append(layered)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 40
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (8, 8, 18, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    canvas = scanlines(canvas, spacing=4, alpha=0.18)
    return canvas


# ─── 7. Console titanium ──────────────────────────────────────────────────────

def render_console_titanium(title: str, rng: random.Random) -> Image.Image:
    """Modern console UI logotype — brushed titanium with ambient occlusion
    shadow, restrained tech sans on a dark gray panel."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("tech", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        chrome = motion_blur_chrome(mask, angle_deg=90, length=18,
                                    stops=[(220, 220, 230), (180, 184, 196),
                                           (96, 100, 112), (140, 144, 156),
                                           (220, 220, 230)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 255), highlight_alpha=160,
                            shadow_color=(40, 44, 58), shadow_alpha=200)
        sh   = drop_shadow(mask, 0, 4, blur=8, alpha=160)
        img  = composite(sh, chrome, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (28, 32, 44, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Dungeon blackletter ───────────────────────────────────────────────────

def render_dungeon_blackletter(title: str, rng: random.Random) -> Image.Image:
    """D&D / dungeon-crawler aesthetic — deep blackletter, parchment torch-
    lit ochre face with hard shadow, single ornamental bullet between words."""
    n     = len(title)
    size  = 130 if n <= 14 else (104 if n <= 22 else 82)
    font  = F("gothic", size, rng) or F("luxury", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        sh   = drop_shadow(mask, 6, 10, blur=12, alpha=240)
        face = colorize(mask, [(255, 230, 170), (200, 140, 60), (90, 40, 14)])
        bev  = bevel_emboss(mask, depth=5, angle_deg=120,
                            highlight_color=(255, 250, 220), highlight_alpha=220,
                            shadow_color=(40, 18, 8), shadow_alpha=180)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (16, 12, 10, 255))

    # Ornamental diamond between top rules
    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.62)
    rx_l = (W - rule_w) // 2
    rx_r = rx_l + rule_w
    cd.line([(rx_l, 30), (rx_r, 30)], fill=(180, 130, 40, 255), width=1)
    diamond_cx, diamond_cy = W // 2, 30
    d = 8
    cd.polygon([(diamond_cx, diamond_cy - d), (diamond_cx + d, diamond_cy),
                (diamond_cx, diamond_cy + d), (diamond_cx - d, diamond_cy)],
               fill=(180, 130, 40, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([(rx_l, y + 14), (rx_r, y + 14)], fill=(180, 130, 40, 255), width=1)
    cd.polygon([(diamond_cx, y + 14 - d), (diamond_cx + d, y + 14),
                (diamond_cx, y + 14 + d), (diamond_cx - d, y + 14)],
               fill=(180, 130, 40, 255))
    return canvas


# ─── 9. Fantasy calligraphy ───────────────────────────────────────────────────

def render_fantasy_calligraphy(title: str, rng: random.Random) -> Image.Image:
    """Hand-inked fantasy calligraphy — lush script with soft outer glow,
    inked-page warm cream backdrop. Tolkien title-page feel."""
    n     = len(title)
    size  = 132 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("script", size, rng) or F("luxury", size, rng) or F("elegant", size, rng)
    lines = wrap_chars(title, 18)

    palettes = [
        ((40, 22, 14),    (240, 220, 180)),    # ink on parchment
        ((30, 50, 30),    (240, 220, 180)),    # forest ink
        ((60, 30, 100),   (244, 234, 220)),    # purple ink
    ]
    ink, paper = palettes[rng.randrange(len(palettes))]

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        bled = ink_bleed(mask, radius=1.6, strength=0.45, irregularity=0.5)
        sh   = drop_shadow(mask, 0, 0, blur=12, alpha=160)
        face = flat_color(bled, ink)
        line_imgs.append(composite(sh, face, size=mask.size))

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (*paper, 255))

    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 700):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(140, 110, 70, rng.randint(20, 60)))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Eldritch glow ────────────────────────────────────────────────────────

def render_eldritch_glow(title: str, rng: random.Random) -> Image.Image:
    """Lovecraftian / cosmic horror — wide-tracked condensed sans glowing
    sickly green-cyan on near-black, subtle chromatic aberration."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    spacing = max(8, size // 12)
    font  = F("condensed", size, rng) or F("tech", size, rng)
    lines = wrap_chars(title.upper(), 22)

    glow = (130, 240, 180)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        bloom = mask.filter(ImageFilter.GaussianBlur(18))
        bloom_layer = flat_color(bloom, glow)
        bloom_a = bloom_layer.split()[3].point(lambda p: int(p * 0.7))
        bloom_layer.putalpha(bloom_a)
        face = flat_color(mask, glow)
        layered = composite(bloom_layer, face, size=mask.size)
        layered = chromatic_aberration(layered, offset=2)
        line_imgs.append(layered)

    text_w = max(t.width for t in line_imgs)
    gap    = 12
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2
    canvas = Image.new("RGBA", (W, H), (8, 12, 14, 255))
    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK11_GAMING_TREATMENTS = {
    "dragon_scale":          render_dragon_scale,
    "mmo_logo":              render_mmo_logo,
    "retro_pixel":           render_retro_pixel,
    "sword_steel":           render_sword_steel,
    "magic_scroll":          render_magic_scroll,
    "neon_arcade":           render_neon_arcade,
    "console_titanium":      render_console_titanium,
    "dungeon_blackletter":   render_dungeon_blackletter,
    "fantasy_calligraphy":   render_fantasy_calligraphy,
    "eldritch_glow":         render_eldritch_glow,
}
