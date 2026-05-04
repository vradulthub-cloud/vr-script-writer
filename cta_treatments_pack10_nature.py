"""
Pack 10 — Nature / outdoor.

Ten treatments evoking nature, outdoor, and adventure design conventions:
botanical illustration, ranger badge, national parks, mountain ridge, ocean
depth, sunset gradient, forest pine, desert dust, arctic frost, tropical paradise.
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


# ─── 1. Botanical illustration ────────────────────────────────────────────────

def render_botanical_illustration(title: str, rng: random.Random) -> Image.Image:
    """Old-world botanical book — refined serif on warm parchment with
    delicate hairline rule. Restrained, scholarly."""
    n     = len(title)
    size  = 110 if n <= 14 else (84 if n <= 24 else 66)
    spacing = max(10, size // 12)
    font  = F("luxury", size, rng) or F("elegant", size, rng) or F("serif", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=14)
        face = flat_color(mask, (50, 70, 50))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 80
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (244, 232, 200, 255))

    cd = ImageDraw.Draw(canvas)
    for _ in range(W * H // 800):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(150, 130, 90, rng.randint(20, 50)))

    rule_w = int(W * 0.5)
    cd.line([((W - rule_w) // 2, 30), ((W + rule_w) // 2, 30)], fill=(50, 70, 50, 255), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap

    cd.line([((W - rule_w) // 2, y + 16), ((W + rule_w) // 2, y + 16)], fill=(50, 70, 50, 255), width=1)
    return canvas


# ─── 2. Ranger badge ──────────────────────────────────────────────────────────

def render_ranger_badge(title: str, rng: random.Random) -> Image.Image:
    """Forest ranger / scout badge — stamped slab serif on a deep forest
    green panel with cream rule, single accent star."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("slab", size, rng) or F("retro", size, rng)
    spacing = max(7, size // 16)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, (244, 232, 200))
        bev  = bevel_emboss(mask, depth=3, angle_deg=120,
                            highlight_color=(255, 255, 240), highlight_alpha=140,
                            shadow_color=(20, 30, 20), shadow_alpha=140)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (28, 60, 40, 255))

    cd = ImageDraw.Draw(canvas)
    rule_w = int(W * 0.78)
    cd.rectangle([((W - rule_w) // 2, 30), ((W + rule_w) // 2, 36)],
                 fill=(244, 232, 200, 255))

    # Single five-point star accent above the title
    star_r = 14
    sx, sy = W // 2, 16
    points = []
    for i in range(10):
        ang = math.radians(i * 36 - 90)
        r = star_r if i % 2 == 0 else star_r * 0.4
        points.append((sx + r * math.cos(ang), sy + r * math.sin(ang)))
    cd.polygon(points, fill=(244, 232, 200, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 3. National parks ────────────────────────────────────────────────────────

def render_national_parks(title: str, rng: random.Random) -> Image.Image:
    """National Park Service poster — bold athletic sans on a layered
    silhouette mountain backdrop in restrained earth tones."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("heavy", size, rng) or F("slab", size, rng)
    spacing = max(7, size // 14)
    lines = wrap_chars(title.upper(), 16)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=20)
        face = flat_color(mask, (244, 232, 200))
        bev  = bevel_emboss(mask, depth=3, angle_deg=125,
                            highlight_color=(255, 255, 240), highlight_alpha=120,
                            shadow_color=(30, 20, 14), shadow_alpha=140)
        img  = composite(face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 80
    canvas = Image.new("RGBA", (W, H), (84, 60, 40, 255))   # warm desert ground

    # Mountain silhouettes layered toward horizon
    cd = ImageDraw.Draw(canvas)
    horizon = int(H * 0.65)
    layers = [
        ((50, 70, 60),  horizon - 60, 0.08),
        ((36, 50, 44),  horizon - 30, 0.1),
        ((24, 32, 30),  horizon, 0.12),
    ]
    for col, peak_y, freq in layers:
        pts = [(0, peak_y)]
        for x in range(0, W, 36):
            pts.append((x, peak_y + math.sin(x * freq) * 28 + rng.randint(-8, 8)))
        pts.append((W, peak_y))
        pts.append((W, H))
        pts.append((0, H))
        cd.polygon(pts, fill=(*col, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 4. Mountain ridge ────────────────────────────────────────────────────────

def render_mountain_ridge(title: str, rng: random.Random) -> Image.Image:
    """Stark alpine mountain — deep navy/slate sky with sharp white peak
    silhouette, condensed sans, very narrow letterspacing."""
    n     = len(title)
    size  = 120 if n <= 14 else (94 if n <= 22 else 74)
    font  = F("condensed", size, rng) or F("heavy", size, rng)
    spacing = max(8, size // 14)
    lines = wrap_chars(title.upper(), 18)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=18)
        face = flat_color(mask, (240, 240, 250))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 100
    canvas = Image.new("RGBA", (W, H), (28, 36, 60, 255))

    # Sharp mountain peak silhouette near the bottom
    cd = ImageDraw.Draw(canvas)
    base_y = H - 30
    pts = [(0, base_y)]
    n_peaks = rng.randint(3, 5)
    for i in range(n_peaks):
        x_pos = (W * (i + 1)) // (n_peaks + 1)
        peak_y = base_y - rng.randint(70, 130)
        pts.append((x_pos - 30, base_y - 20))
        pts.append((x_pos, peak_y))
        pts.append((x_pos + 30, base_y - 20))
    pts.append((W, base_y))
    pts.append((W, H))
    pts.append((0, H))
    cd.polygon(pts, fill=(240, 240, 250, 255))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 5. Ocean depth ───────────────────────────────────────────────────────────

def render_ocean_depth(title: str, rng: random.Random) -> Image.Image:
    """Deep-ocean expedition aesthetic — cool deep blue gradient background,
    thin tech sans in pale aqua, faint horizontal pressure lines."""
    n     = len(title)
    size  = 116 if n <= 14 else (90 if n <= 22 else 70)
    spacing = max(8, size // 12)
    font  = F("tech", size, rng) or F("luxury", size, rng)
    lines = wrap_chars(title.upper(), 22)

    line_imgs = []
    for ln in lines:
        mask = wide_track_mask(ln, font, spacing, pad=16)
        face = flat_color(mask, (200, 230, 240))
        line_imgs.append(face)

    text_w = max(t.width for t in line_imgs)
    gap    = 10
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 70
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Vertical gradient: surface light at top → abyssal dark at bottom
    cd = ImageDraw.Draw(canvas)
    for y_pos in range(H):
        t = y_pos / H
        r = int(20 + 30 * (1 - t))
        g = int(50 + 60 * (1 - t))
        b = int(80 + 70 * (1 - t))
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    # Faint horizontal pressure rules
    for y_pos in range(40, H - 40, 50):
        cd.line([(margin // 2, y_pos), (W - margin // 2, y_pos)],
                fill=(180, 220, 240, 60), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 6. Sunset gradient ───────────────────────────────────────────────────────

def render_sunset_gradient(title: str, rng: random.Random) -> Image.Image:
    """Pacific sunset — bold sans backdropped by a rich warm vertical
    gradient (peach → coral → magenta → indigo)."""
    n     = len(title)
    size  = 134 if n <= 14 else (104 if n <= 22 else 80)
    font  = F("heavy", size, rng) or F("athletic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = flat_color(mask, (250, 240, 230))
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=180,
                            shadow_color=(80, 30, 60), shadow_alpha=160)
        sh   = drop_shadow(mask, 4, 7, blur=8, alpha=180)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 50
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Sunset gradient
    cd = ImageDraw.Draw(canvas)
    stops = [(255, 200, 130), (255, 130, 90), (220, 60, 110), (110, 30, 130), (40, 30, 80)]
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


# ─── 7. Forest pine ───────────────────────────────────────────────────────────

def render_forest_pine(title: str, rng: random.Random) -> Image.Image:
    """Pacific Northwest pine forest — deep green, woodgrain texture
    overlay, warm cream slab serif. Outdoor outfitter aesthetic."""
    n     = len(title)
    size  = 124 if n <= 14 else (96 if n <= 22 else 76)
    font  = F("slab", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = flat_color(mask, (244, 232, 200))
        bev  = bevel_emboss(mask, depth=4, angle_deg=125,
                            highlight_color=(255, 255, 240), highlight_alpha=180,
                            shadow_color=(30, 50, 30), shadow_alpha=160)
        sh   = drop_shadow(mask, 4, 6, blur=4, alpha=200)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 40
    canvas = Image.new("RGBA", (W, H), (28, 56, 40, 255))

    # Wood-grain striations — faint horizontal lines through the canvas
    cd = ImageDraw.Draw(canvas)
    for y in range(0, H, rng.randint(4, 8)):
        for x in range(0, W, rng.randint(80, 160)):
            cd.line([(x, y), (x + rng.randint(40, 100), y + rng.randint(-1, 1))],
                    fill=(20, 40, 30, rng.randint(60, 120)), width=1)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 8. Desert dust ───────────────────────────────────────────────────────────

def render_desert_dust(title: str, rng: random.Random) -> Image.Image:
    """Mojave desert — warm tan/terracotta gradient, distressed slab
    typography, fine speckle dust overlay."""
    n     = len(title)
    size  = 130 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("slab", size, rng) or F("retro", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        worn = ink_bleed(mask, radius=1.4, strength=0.45, irregularity=0.7)
        face = colorize(worn, [(232, 196, 130), (180, 120, 60), (100, 50, 20)])
        bev  = bevel_emboss(worn, depth=4, angle_deg=125,
                            highlight_color=(255, 248, 220), highlight_alpha=180,
                            shadow_color=(60, 30, 12), shadow_alpha=140)
        img  = composite(face, bev, size=worn.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Warm sky-to-ground gradient
    cd = ImageDraw.Draw(canvas)
    stops = [(220, 180, 130), (200, 130, 80), (140, 80, 50)]
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        idx = min(int(t * (len(stops) - 1)), len(stops) - 2)
        frac = t * (len(stops) - 1) - idx
        r = int(stops[idx][0] * (1 - frac) + stops[idx + 1][0] * frac)
        g = int(stops[idx][1] * (1 - frac) + stops[idx + 1][1] * frac)
        b = int(stops[idx][2] * (1 - frac) + stops[idx + 1][2] * frac)
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    # Dust speckle overlay
    for _ in range(W * H // 200):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(220, 190, 150, rng.randint(40, 120)))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 9. Arctic frost ──────────────────────────────────────────────────────────

def render_arctic_frost(title: str, rng: random.Random) -> Image.Image:
    """Arctic / glacial — pale ice-blue gradient, bold sans with blue rim
    and frosted texture, soft crystal speckle."""
    n     = len(title)
    size  = 130 if n <= 14 else (100 if n <= 22 else 78)
    font  = F("heavy", size, rng) or F("condensed", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = colorize(mask, [(245, 252, 255), (200, 230, 245), (130, 180, 220)])
        bev  = bevel_emboss(mask, depth=4, angle_deg=120,
                            highlight_color=(255, 255, 255), highlight_alpha=200,
                            shadow_color=(40, 90, 130), shadow_alpha=180)
        rim  = fresnel_metallic(mask, base_color=(220, 240, 250),
                                rim_color=(255, 255, 255), rim_power=2.6)
        rim_a = rim.split()[3].point(lambda p: int(p * 0.4))
        rim.putalpha(rim_a)
        img  = composite(face, bev, rim, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 30
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    cd = ImageDraw.Draw(canvas)
    # Cool gradient backdrop
    stops = [(220, 240, 252), (180, 220, 245), (140, 180, 220), (60, 100, 150)]
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        idx = min(int(t * (len(stops) - 1)), len(stops) - 2)
        frac = t * (len(stops) - 1) - idx
        r = int(stops[idx][0] * (1 - frac) + stops[idx + 1][0] * frac)
        g = int(stops[idx][1] * (1 - frac) + stops[idx + 1][1] * frac)
        b = int(stops[idx][2] * (1 - frac) + stops[idx + 1][2] * frac)
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    # Crystal speckle
    for _ in range(W * H // 350):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        cd.point((x, y), fill=(255, 255, 255, rng.randint(60, 180)))

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── 10. Tropical paradise ────────────────────────────────────────────────────

def render_tropical_paradise(title: str, rng: random.Random) -> Image.Image:
    """Vintage travel poster tropical — saturated coral/teal/cream, hand-
    drawn style retro letterforms, palm-frond silhouette."""
    n     = len(title)
    size  = 130 if n <= 14 else (102 if n <= 22 else 80)
    font  = F("retro", size, rng) or F("comic", size, rng)
    lines = wrap_chars(title.upper(), 14)

    line_imgs = []
    for ln in lines:
        mask = make_mask(ln, font, pad=22)
        face = colorize(mask, [(255, 220, 180), (240, 130, 100), (180, 60, 60)])
        bev  = bevel_emboss(mask, depth=5, angle_deg=125,
                            highlight_color=(255, 250, 230), highlight_alpha=200,
                            shadow_color=(80, 40, 50), shadow_alpha=160)
        sh   = drop_shadow(mask, 4, 7, blur=4, alpha=200)
        img  = composite(sh, face, bev, size=mask.size)
        line_imgs.append(img)

    text_w = max(t.width for t in line_imgs)
    gap    = 8
    text_h = sum(t.height for t in line_imgs) + gap * (len(line_imgs) - 1)
    margin = 60
    W = text_w + margin * 2
    H = text_h + margin * 2 + 60
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Coral-to-teal gradient
    cd = ImageDraw.Draw(canvas)
    stops = [(255, 200, 130), (240, 150, 110), (60, 170, 180), (20, 100, 130)]
    for y_pos in range(H):
        t = y_pos / max(1, H - 1)
        idx = min(int(t * (len(stops) - 1)), len(stops) - 2)
        frac = t * (len(stops) - 1) - idx
        r = int(stops[idx][0] * (1 - frac) + stops[idx + 1][0] * frac)
        g = int(stops[idx][1] * (1 - frac) + stops[idx + 1][1] * frac)
        b = int(stops[idx][2] * (1 - frac) + stops[idx + 1][2] * frac)
        cd.line([(0, y_pos), (W, y_pos)], fill=(r, g, b, 255), width=1)

    # Simplified palm-frond silhouette in a corner
    frond_col = (10, 40, 30, 200)
    frond_x, frond_y = 30, H - 30
    for ang_deg in range(70, 130, 8):
        ang = math.radians(ang_deg)
        x_end = frond_x + int(math.cos(ang) * 80)
        y_end = frond_y - int(math.sin(ang) * 80)
        cd.line([(frond_x, frond_y), (x_end, y_end)], fill=frond_col, width=4)

    y = margin
    for img in line_imgs:
        canvas.paste(img, ((W - img.width) // 2, y), img)
        y += img.height + gap
    return canvas


# ─── Registration ─────────────────────────────────────────────────────────────

PACK10_NATURE_TREATMENTS = {
    "botanical_illustration": render_botanical_illustration,
    "ranger_badge":           render_ranger_badge,
    "national_parks":         render_national_parks,
    "mountain_ridge":         render_mountain_ridge,
    "ocean_depth":            render_ocean_depth,
    "sunset_gradient":        render_sunset_gradient,
    "forest_pine":            render_forest_pine,
    "desert_dust":            render_desert_dust,
    "arctic_frost":           render_arctic_frost,
    "tropical_paradise":      render_tropical_paradise,
}
