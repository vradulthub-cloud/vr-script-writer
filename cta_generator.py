#!/usr/bin/env python3
"""
CTA Title PNG Generator — v4 (refactored)

Generates transparent-background PNG title cards with 700+ visual treatments.
LLM-powered routing via learned_routes.json (built by cta_learn.py).

Usage:
  python3 cta_generator.py "Better Than Imagined"
  python3 cta_generator.py "The Laid Over" --treatment graffiti
  python3 cta_generator.py --from-sheet --outdir ./outputs
  python3 cta_generator.py --test-all "Some Title" --test-outdir ./test
  python3 cta_generator.py --list-treatments
  python3 cta_generator.py --download-fonts
"""

import sys, os, re, csv, io, math, hashlib, argparse, random, colorsys, json
import urllib.request
from pathlib import Path
from datetime import date

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
except ImportError:
    os.system(f"{sys.executable} -m pip install pillow numpy --break-system-packages -q")
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np

# ── Module imports ────────────────────────────────────────────────────────────
from cta_fonts import (
    F, FONT_CACHE, _resolve_fonts, download_font_pack,
    _download_font, _GFONTS,
)
from cta_primitives import (
    measure, make_mask, auto_size, auto_size_hd, make_mask_hd,
    colorize, flat_color, dilate, extrude, rainbow_extrude,
    glow_layer, drop_shadow, highlight, composite,
    bevel_light, inner_glow, fill_solid, mask_to_rgba, apply_mask,
    wide_track_mask, title_seed,
)
from cta_treatments import TREATMENTS, FEATURED_TREATMENTS

# ── Learned routes (built by cta_learn.py) ────────────────────────────────────
_LEARNED_FILE = Path(__file__).parent / "learned_routes.json"
_LEARNED: dict = {}

def _load_learned():
    global _LEARNED
    if _LEARNED:
        return
    if _LEARNED_FILE.exists():
        try:
            _LEARNED = json.loads(_LEARNED_FILE.read_text(encoding="utf-8"))
        except Exception:
            _LEARNED = {}

# ── Sheet IDs ─────────────────────────────────────────────────────────────────
GRAIL_SHEET_ID  = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
SCRIPT_SHEET_ID = "1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ"

# ── Keyword routing ───────────────────────────────────────────────────────────

KEYWORD_TREATMENT: dict[str, list] = {
    "impact": [
        "stacked","massive","extreme","blondes","doggystyle","best","top",
        "adventures","vol","collection","anthology","hardcore","ultimate",
        "biggest","hottest","baddest","compilation","featuring","presents",
        "unleashed","returns","the best","all star","vs","versus",
        "fire","lava","burning","flame","blazing","inferno","scorching",
        "superhero","action","explosive","detonation",
    ],
    "neon_wire": [
        "neon","electric","cyber","digital","night","glow","pulse","flash",
        "stream","online","live","tonight","tech","vr","virtual","stream",
        "signal","frequency","algorithm","online","download",
        "laser","lightning","storm","electric blue","neon sign","glitch",
        "gaming","datamosh","speed","led light","plasma",
    ],
    "editorial": [
        "exclusive","premium","luxury","vip","elite","refined","elegant",
        "member","benefits","milky","queen","royal","majestic","gallery",
        "collection exclusive","the art","curator","connoisseur","premiere",
        "pearl","opulent","haute","couture","bespoke","distinguished",
    ],
    "graffiti": [
        "laid","over","raw","bold","street","urban","heat","hustle","grind",
        "sunrise","seduction","production","session","behind","doors","cosmic",
        "connection","behind closed","attraction","dirty","rough","gritty",
        "spray","drip","dripping","tag","splash","rebel","vandal","marker",
    ],
    "bubble": [
        "fun","party","play","sweet","honey","morning","wake","cozy","cute",
        "delicious","glorious","wok wild","happy","beginning","first time",
        "totally","basically","just","little","adorable","sunshine","bubbly",
        "puffy","inflated","balloon","bouncy","cheerful","bubbly","jolly",
    ],
    "cinematic": [
        "private","view","thorough","inspection","convenient","journey",
        "story","tale","chapter","episode","peak","the art","tour","a moment",
        "an evening","experience","encounter","affair","rendez","scene",
        "motion","film","cinematic","dramatic","panoramic","sweeping",
    ],
    "block_3d": [
        "fire","ice","gold","silver","metallic","crystal","diamond","platinum",
        "bringing","the heat","power","force","surge","blaze","drive","pulse",
        "big","huge","massive delivery","loaded",
        "isometric","dimensional","embossed","carved","sculpted","champion",
    ],
    "script": [
        "taking care","great care","giving","satisfaction","dream","pleasure",
        "affection","sensual","aura","touches","spring","summer","fall release",
        "fresh","gentle","tender","loving","devoted","true","warm","morning",
        "evening","memories","romance","fantasy","pre fall","post summer",
        "the happy","beginning","the soft","sweet","desire","intimate",
        "caress","embrace","cherish","adore","allure","appeal",
        "cursive","handwritten","lettering","embroidery","stitched","knitted",
        "brushstroke","calligraphy","flourish","graceful","feminine",
    ],
    "retro_rainbow": [
        "let me","do you","let do","you do","come on","come here","bigger",
        "more than","pop","flash desire","wet dream","sugar","candy","colorful",
        "dream comes","bigger is","let","do","you",
        "comic","cartoon","funky","psychedelic","groovy","warped","pop art",
        "retro fun","rainbow","arcade","pinball","trippy","kaleidoscope",
    ],
    "chrome": [
        "steel","blade","sharp","chrome","crystal clear","mirror","glass",
        "machine","conductor","amplified","polished","refined steel",
        "algorithm of","the algorithm","cold steel","liquid",
        "iridescent","holographic","silver chrome","futuristic","titanium",
        "reflective","prismatic","glossy chrome","liquid metal","acrylic",
    ],
    "stark": [
        "deep","raw","hard","dark","black","straight","pure","solo",
        "just","only","alone","real","take that","stir","purple",
        "absolutely","completely","totally raw","uncut","unfiltered",
        "minimal","stark","plain","bare","cut","clean cut","stripped",
    ],
    "vintage": [
        "royal","heritage","old","classic","traditional","tailor","colonial",
        "era","legacy","antique","charm","aged","historic","timeless",
        "manor","estate","garden","parlor","period","golden age",
        "halftone","letterpress","analog","photocopy","weathered","faded ink",
        "parchment","wax seal","emblem","crest","distressed",
    ],
    "spray_stencil": [
        "pain","gain","nasty","backdoor","channeling","gritty","underground",
        "raw deal","stir","mission","blasting","slav","blast",
        "operation","strike","rough","crude","unpolished","street",
        "stencil","cracked","overspray","grunge","ink bleed","smudge",
        "war zone","battle","frontline","resistance","protest","regime",
    ],
    "liquid_gold": [
        "honey","maple","whipping dripping","spilling","oily","cream","golden",
        "dripping","pour","flowing","luscious","rich","decadent","indulgent",
        "molten","amber","butter","caramel","syrup","nectar",
        "foil","embossed gold","gold leaf","gilded","shimmer","sparkle",
        "lustrous","opulent gold","warm glow","gleam",
    ],
    "neon_box": [
        "strip","club","bar","mardi gras","nola","vegas","nightlife","rave",
        "party","disco","lounge","suite","showroom","stage","spotlight",
        "backstage","venue","hotspot","marquee","sign",
        "cabaret","burlesque","jazz club","speakeasy","casino","arcade bar",
    ],
    "glitch": [
        "glitch","corrupt","broken","static","error","404","lag","crash",
        "distort","hack","virus","malfunction","overload","interference",
        "datamosh","buffer","overflow","corrupted","pixel","fragmented",
        "scanline","crt","artifact","dropout","signal loss","noise",
        "system failure","debug","matrix","byte","decode","encrypt",
    ],
    "holographic": [
        "holographic","holo","prism","prismatic","iridescent","ethereal",
        "cosmic","aurora","rainbow crystal","spectral","dreamlike","celestial",
        "infinite","beyond","transcend","dimensional","opalescent","lustrous",
        "angel","fairy","fantasy realm","otherworldly","mythic","divine",
        "pastel","soft glow","shimmer veil","crystalline","stardust",
    ],
    "fire": [
        "fire","flame","blaze","burn","scorch","ignite","inferno","lava","heat",
        "torch","ember","sizzle","smoke","ablaze","incinerate","explosive",
        "volcanic","magma","forge","smoldering","fiery","char","flicker",
        "pyro","incendiary","wildfire","hellfire","bonfire","campfire",
    ],
    "ice": [
        "ice","frost","frozen","freeze","blizzard","arctic","glacier","crystal",
        "cold","chill","winter","snow","sub zero","tundra","permafrost","icy",
        "cool","frigid","polar","diamond ice","black ice","hoarfrost","sleet",
        "snowstorm","avalanche","iceberg","absolute zero","shiver","crisp",
    ],
    "comic": [
        "pow","bam","kapow","zap","wham","boom","smash","crash","bang","thud",
        "comic","cartoon","toon","strip","panel","action hero","woo","yow",
        "superhero","villain","sidekick","pow right","over the top","epic fail",
        "pop art","bold print","graphic novel","manga","anime","illustrated",
    ],
    "drip": [
        "drip","drippy","dripping","melt","melting","ooze","oozing","seep",
        "wet paint","pour","spill","overflow","runoff","trickle","drizzle",
        "paint splash","ink bleed","color bleed","splatted","painted","mess",
        "gooey","sticky","viscous","thick liquid","slow pour","lava drip",
    ],
    "outline_glow": [
        "ghost","phantom","hollow","neon outline","wire frame","see through",
        "transparent","spirit","invisible","shadow","trace","wireframe","empty",
        "barely there","faint","dim","translucent","spectral","vapor","mist",
        "half light","thin air","ether","apparition","glowing edge","lit edge",
    ],
    "movie_title": [
        "presents","production","feature","film","cinematic release","starring",
        "directed","the return","part ii","part 2","chapter ii","chapter 2",
        "volume ii","volume 2","season","episode","saga","epic","blockbuster",
        "event","limited","theatrical","motion picture","a story of","world premiere",
        "the legend","the rise","untold","behind the scenes","documentary",
    ],
    "glitter": [
        "glitter","sparkle","shimmer","dazzle","sequin","jewel","gem","diamond",
        "rhinestone","bedazzle","glam","glamour","diva","glitzy","shiny",
        "sparkly","star","glittering","confetti","tinsel","opal","crystal shine",
        "fairytale","princess","tiara","ballroom","gown","velvet","luxury glow",
        "pink","rose gold","feminine","gorgeous","stunning","radiant",
    ],
    "psychedelic": [
        "psychedelic","acid","trip","lsd","mushroom","melt","hallucinate","vision",
        "kaleidoscope","warp","warped","colors explode","mind bend","expanded",
        "surreal","lysergic","trance","rave color","festival","neon melt",
        "technicolor","saturated","vivid dream","color burst","distorted reality",
        "groovy","far out","cosmic trip","third eye","peyote","altered state",
    ],
    "varsity": [
        "team","squad","crew","varsity","champion","championship","league",
        "sport","athletic","college","letterman","jersey","number","roster",
        "playoffs","tournament","bowl","trophy","mvp","allstar","athlete",
        "game day","stadium","locker room","home team","rivalry","coach",
    ],
    "chalk": [
        "lesson","class","school","board","classroom","teacher","study",
        "handmade","craft","artisan","diy","homemade","casual","sketch",
        "drawing","doodle","scribble","note","written","soft","gentle flair",
        "chalk","pastel","hand drawn","texture","rough","cozy vibe",
    ],
    "pixel": [
        "pixel","8bit","8-bit","retro game","arcade","gaming","video game",
        "controller","joystick","sprite","level up","boss battle","cheat code",
        "insert coin","high score","game over","respawn","dungeon","quest",
        "npc","loot","spawn","raid","grind","xp","achievement","mod","patch",
    ],
    "watercolor": [
        "watercolor","paint","brushstroke","canvas","artist","studio","gallery",
        "soft","dreamy","whimsical","floral","botanical","wash","fade","blend",
        "pastel palette","light","airy","delicate","wispy","misty","haze",
        "impressionist","bloom","petals","garden","nature","tranquil","drift",
    ],
    "neon_script": [
        "doll","babe","bae","honey","darling","lover","secret","confession",
        "desire","passionate","hot girl","girl","femme","sensual script",
        "love note","written in light","glow script","femme fatale","seductive",
        "lounge script","cocktail","nightcap","champagne toast","silk","velvet",
    ],
    "rubber_stamp": [
        "certified","approved","classified","confidential","official","authorized",
        "stamped","sealed","registered","denied","rejected","urgent","priority",
        "filed","processed","verified","proof","document","labeled","marked",
        "top secret","for your eyes","cleared","case closed","exhibit",
    ],
    "tie_dye": [
        "tie dye","tiedye","hippie","peace","love","woodstock","boho","bohemian",
        "free spirit","woke","spiral","rainbow","groovy","60s","70s","flower child",
        "festival vibe","summer of love","commune","zen","chakra","aura color",
        "grateful","psychedelic fabric","dyed","batik","wax print","pattern",
    ],
    "grunge_metal": [
        "metal","brutal","death","heavy","hell","rage","wrath","fury","dark lord",
        "demon","infernal","thrash","shred","slayer","destroyer","carnage","chaos",
        "savage","barbaric","war machine","iron","steel fist","skull","bone",
        "underground metal","noise","sludge","doom","black","grindcore","extreme",
    ],
    "poster_print": [
        "print","screen print","poster","flyer","zine","underground press",
        "punk","anarchist","rebel yell","manifesto","revolution","resistance art",
        "indie","lo-fi print","risograph","offset","silk screen","broadside",
        "protest sign","declaration","handbill","broadsheet","newsprint","press run",
    ],
    "splatter": [
        "splatter","splat","explosion","burst","chaos art","abstract","drip art",
        "paint fight","messy","wild brush","thrown","flung","sprayed","hosed down",
        "jackson","pollock","action painting","spontaneous","energetic art",
        "paint bomb","color blast","chromatic explosion","unfiltered","raw art",
    ],
    "neon_outline": [
        "neon", "outline", "effect", "rgb split", "futuristic",
    ],
    "cold_ice": [
        "cool", "blue", "texture", "with", "glowing", "outline", "shadow", "effect.", "rgb split",
    ],
    "long_shadow": [
        "long", "shadow", "rgb split", "bold",
    ],
    "gold_text": [
        "gold", "foil", "text", "effect", "text effect", "bold", "gold foil",
    ],
    "distort": [
        "distorted", "text", "effect", "text distortion", "dark",
    ],
    "organic_text": [
        "organic", "text", "effect", "none", "paper",
    ],
    "retro_vibes": [
        "retro-inspired", "text", "effect", "with", "neon", "outline", "shadow.", "rgb split", "retro",
    ],
    "acid_neon": [
        "neon", "outline", "with", "dark", "background", "rgb split",
    ],
    "chalk_writing": [
        "chalk", "writing", "effect", "organic",
    ],
    "old_gold_text": [
        "gold", "foil", "effect", "text", "textured background", "bold", "paper",
    ],
    "cutout": [
        "cutout", "effect", "text effect", "bold",
    ],
    "silver_neon": [
        "neon", "effect", "with", "metallic", "sheen", "rgb split", "futuristic",
    ],
    "goldfish": [
        "goldfish", "text", "effect", "list", "effects", "like", "rgb_split", "scanlines", "drips", "bold",
    ],
    "hololographic_outline": [
        "holo-style", "text", "effect", "with", "glowing", "outline", "subtle", "gradient", "background.", "rgb split effect", "futuristic",
    ],
    "error_template": [
        "digital", "glitch", "effect", "with", "text", "overlay", "rgb split effect", "grain",
    ],
    "shiny_holidays": [
        "shiny", "holidays", "text", "effect", "list", "effects", "like", "rgb_split", "scanlines", "drips", "futuristic",
    ],
    "glitch_bloom": [
        "glitch", "bloom", "rgb split", "scanlines", "futuristic",
    ],
    "space_neon": [
        "neon", "outline", "with", "starry", "space", "background", "rgb split", "futuristic",
    ],
    "glitch_text": [
        "glitch", "effect", "rgb split", "futuristic",
    ],
    "stacker_text": [
        "text", "effect", "with", "shadow", "glow", "text effect", "dark",
    ],
    "bang_spray": [
        "graffiti-style", "text", "effect", "with", "spray", "paint", "texture", "shadow", "textured background", "spray paint texture", "bold", "grunge",
    ],
    "text_mask": [
        "text", "mask", "effect", "with", "colorful", "gradient", "stylized", "typography.", "text mask", "futuristic",
    ],
    "ink_text": [
        "text", "effect", "text effect", "bold", "paper",
    ],
    "rainbow_neon": [
        "neon", "text", "effect", "with", "rainbow", "colors", "glowing", "outline.", "rgb split effect", "bright",
    ],
    "go_big_or_go_home": [
        "text", "effect", "with", "neon", "outline", "glow", "rgb split", "scanlines", "bold",
    ],
    "lucky_neon": [
        "neon", "outline", "effect", "rgb split", "bright",
    ],
    "heatwave": [
        "neon", "outline", "with", "gradient", "glow", "effects", "rgb split", "scanlines", "futuristic",
    ],
    "cloudy_text": [
        "cloudy", "text", "effect", "text_effect", "dark",
    ],
    "retro_outline": [
        "retro", "style", "with", "neon", "outline", "shadow", "effect.", "rgb split effect",
    ],
    "concrete_grunge": [
        "concrete", "texture", "overlay", "text", "textured background", "industrial",
    ],
    "stamp_printing": [
        "stamp", "printing", "effect", "stamp print effect", "bold",
    ],
    "embroidery": [
        "embroidery-style", "text", "effect", "embroidery stitching", "organic", "fabric",
    ],
    "halftone": [
        "printed", "halftone", "effect", "text", "bold",
    ],
    "trust_template": [
        "text", "effect", "with", "shadow", "glow", "rgb split", "scanlines", "bold",
    ],
    "dark_neon_outline": [
        "neon", "outline", "with", "glow", "shadow", "effects", "rgb split", "scanlines", "dark",
    ],
    "speed": [
        "neon", "outline", "with", "colorful", "gradient", "glow", "effect", "rgb split", "scanlines", "futuristic",
    ],
    "chrome_text_effect": [
        "neon", "outline", "glow", "effect", "rgb split", "futuristic",
    ],
    "rise_shine": [
        "neon", "outline", "with", "glowing", "text", "slight", "shadow", "effect", "rgb split effect", "bright",
    ],
    "burnt_parchment": [
        "burnt", "parchment", "effect", "rgb split", "bold",
    ],
    "bold_text": [
        "bold", "text", "effect", "with", "smart", "object", "template", "smart object template",
    ],
    "glossy_text": [
        "glossy", "effect", "text", "textured background", "dark",
    ],
    "cloud_logo": [
        "text", "effect", "with", "cloud", "theme", "3d rendering", "futuristic",
    ],
    "overprint_template": [
        "overlay", "text", "image", "text overlay", "bold",
    ],
    "dark_forest": [
        "mysterious", "ominous", "rgb split", "dark",
    ],
    "gold_glow": [
        "gold", "glow", "effect", "with", "metallic", "texture", "shadow", "rgb split", "bold",
    ],
    "neon_speed": [
        "neon", "speed", "text", "effect", "rgb split", "futuristic",
    ],
    "glowing_neon": [
        "glowing", "neon", "text", "effect", "rgb split", "futuristic",
    ],
    "summer_style": [
        "text", "effect", "with", "summer", "vibe", "light",
    ],
    "silver_outline": [
        "silver", "outline", "with", "metallic", "texture", "subtle", "glow", "effect.", "rgb split", "futuristic",
    ],
    "modern_grunge": [
        "grunge", "text", "effect", "textured background", "bold",
    ],
    "wood_carved": [
        "wood", "carving", "effect", "textured background", "organic",
    ],
    "bright_outline": [
        "bright", "outline", "effect", "text", "rgb split",
    ],
    "stamped_gold": [
        "gold", "foil", "stamp", "effect", "gold foil texture", "bold", "metallic",
    ],
    "stressed_outline": [
        "outlined", "text", "with", "distressed", "texture", "shadow", "effect.", "textured background", "dark", "grunge",
    ],
    "smoke": [
        "smoke", "effect", "with", "text", "overlay", "text overlay", "dark",
    ],
    "stroke_text": [
        "stroke", "effect", "text", "bold",
    ],
    "flow_new": [
        "overlay", "text", "with", "watermark", "effect", "rgb split effect", "light",
    ],
    "glam_effect": [
        "glittery", "text", "effect", "with", "glossy", "finish", "textured background with glittery text", "futuristic",
    ],
    "cosmic_text": [
        "neon", "text", "effect", "rgb split", "scanlines", "futuristic",
    ],
    "logo_template": [
        "text", "effect", "with", "grunge", "texture", "drop", "shadow", "3d text effect", "bold",
    ],
    "broken_text": [
        "distressed", "text", "effect", "text distortion", "dark", "grunge",
    ],
    "neon_mockup": [
        "neon", "outline", "effect", "rgb split", "futuristic",
    ],
    "float": [
        "neon", "outline", "with", "purple", "gradient", "shadow", "effect", "rgb split", "futuristic",
    ],
    "white_text_effect": [
        "white", "text", "grey", "background", "with", "subtle", "shadow", "outline", "effect.", "light",
    ],
    "text_overlay": [
        "overlay", "text", "image", "text overlay", "subtle",
    ],
    "3d_standout": [
        "standout", "effect", "3d rendering", "futuristic",
    ],
    "metal_gradients": [
        "metallic", "gradients", "with", "real", "brushed", "metal", "effect", "texture", "list", "effects", "like", "rgb_split", "scanlines", "drips", "industrial",
    ],
    "bling_text": [
        "neon", "outline", "with", "glow", "shadow", "effects", "rgb split", "bright",
    ],
    "dark_neon": [
        "neon", "outline", "with", "glow", "shadow", "effects", "rgb split", "scanlines", "dark",
    ],
    "chrome_glow": [
        "chrome", "text", "effect", "rgb split", "scanlines", "futuristic",
    ],
    "galaxy_text": [
        "neon", "outline", "with", "glow", "shadow", "effects", "rgb split", "futuristic",
    ],
    "neon_glow": [
        "glowing", "neon", "text", "effect", "rgb split", "futuristic",
    ],
    "glow": [
        "glowing", "neon", "text", "effect", "rgb split", "futuristic",
    ],
    "vintage_text": [
        "vintage", "text", "effect", "with", "variety", "font", "styles", "colors.", "list of effects", "retro", "paper",
    ],
    "chrome_text": [
        "metallic", "text", "effect", "3d depth", "futuristic",
    ],
    "grainy_text": [
        "grainy", "text", "effect", "rgb split", "dark", "grain",
    ],
    # Premium treatments
    "chrome_bevel": ["chrome", "mirror", "silver", "steel", "metallic", "bevel"],
    "gold_luxury": ["gold", "luxury", "award", "premium", "embossed", "opulent"],
    "neon_tube": ["neon", "sign", "tube", "bar", "club", "glow", "buzz"],
    "gold_chrome": ["rose gold", "platinum", "elegant", "sheen"],
    "stone_carved": ["stone", "granite", "carved", "rock", "monument", "ancient"],
    "holographic_foil": ["holographic", "holo", "foil", "rainbow", "iridescent", "prismatic"],
    "pop_halftone": ["pop", "halftone", "comic", "dots", "lichtenstein", "retro pop"],
    "obsidian": ["obsidian", "dark", "glass", "rim", "sleek", "matte"],
    "candy_gloss": ["candy", "glossy", "sweet", "bubbly", "shiny", "plastic"],
    "retro_3d": ["retro", "80s", "arcade", "vintage 3d", "chunky", "block"],
    "plasma_electric": ["plasma", "electric", "lightning", "energy", "charged", "voltage"],
    "letterpress": ["letterpress", "ink", "press", "aged", "vintage print", "paper"],
    "laser_etch": ["laser", "etch", "anodised", "engraved", "tech", "precision"],
    "duotone_bold": ["duotone", "two-color", "graphic", "bold design", "split"],
    # ── Font expansion keyword routing ─────────────────────────────────────
    "velvet_luxury": [
        "velvet","plush","velour","luxe","opulent","rich","sumptuous","lavish",
        "burgundy","wine","plum","majestic","regal","sovereign","throne",
    ],
    "gothic_iron": [
        "gothic","medieval","dark lord","kingdom","castle","dungeon","fortress",
        "blackletter","iron","shield","sword","knight","templar","ancient order",
    ],
    "pastel_dream": [
        "pastel","dreamy","soft","gentle","tender","sweet dream","cotton","fluffy",
        "light","fairy","angel wings","cloud nine","serene","peaceful","calm",
    ],
    "cyber_split": [
        "cyber","cyberpunk","split","divided","dual","versus","binary","code",
        "matrix","synthetic","android","replicant","neuro","augmented","hack",
    ],
    "tropical_sunset": [
        "tropical","paradise","island","beach","ocean","sunset","sunrise","palm",
        "hawaii","malibu","caribbean","vacation","getaway","summer vibes","poolside",
    ],
    "frosted_glass": [
        "frosted","glass","translucent","crystal clear","clean","minimal","pure",
        "fresh","crisp","alpine","morning dew","ice queen","frost","winter morning",
    ],
    "pixel_arcade": [
        "pixel","8bit","8-bit","retro game","arcade","gaming","video game","level",
        "boss","gamer","console","joystick","controller","insert coin","game on",
    ],
    "brush_ink": [
        "ink","brush","calligraphy","zen","kanji","stroke","artistic","express",
        "painted","waterink","sumi","bamboo","handmade","artisan","natural",
    ],
    "art_deco": [
        "deco","gatsby","1920s","jazz age","nouveau","metropolitan","glamour",
        "ballroom","chandelier","speakeasy","prohibition","gilded","ornate","grand",
    ],
    "magazine_cover": [
        "cover","magazine","editorial","vogue","fashion","model","runway","haute",
        "couture","photoshoot","beauty","cosmopolitan","glamour shot","portfolio",
    ],
    "cotton_candy": [
        "cotton candy","unicorn","fairground","carnival","bubblegum","sugar","sweet",
        "sprinkles","cupcake","lollipop","candy floss","caramel","treat","dessert",
    ],
    "midnight_luxe": [
        "midnight","after dark","nocturnal","twilight","moonlight","starlit","night sky",
        "after hours","late night","black tie","gala","masquerade","phantom","noir",
    ],
    "electric_slide": [
        "electric","slide","motion","speed","fast","racing","turbo","boost",
        "acceleration","velocity","momentum","rush","dash","sprint","blitz",
    ],
    "hand_sketch": [
        "sketch","pencil","drawing","notebook","diary","journal","written","note",
        "doodle","scribble","draft","rough","raw sketch","line art","illustration",
    ],
    "sunset_strip": [
        "strip","boulevard","highway","road","cruise","drive","coast","scenic",
        "sunset blvd","la","hollywood","palm drive","golden coast","oceanside",
    ],
    "neon_cursive": [
        "love","heart","kiss","romance","date night","valentine","sweetheart",
        "darling","babe","honey","gorgeous","beautiful","soulmate","forever",
    ],
    "leather_emboss": [
        "leather","saddle","western","ranch","cowboy","country","rodeo","boots",
        "whiskey","bourbon","cigar","gentleman","rustic","cabin","lodge",
    ],
    "glam_rock": [
        "glam","rock star","concert","stadium","encore","backstage","tour","band",
        "rockstar","groupie","rebel","punk rock","metal","guitar","drums",
    ],
    "ocean_deep": [
        "ocean","deep","underwater","submarine","dive","coral","reef","aqua",
        "mermaid","atlantis","abyss","trench","marine","nautical","seafloor",
    ],
    "bubblegum_pop": [
        "bubblegum","pop","fun","party","birthday","celebrate","cheerful","happy",
        "joy","sunshine","rainbow","yay","woo","hooray","exciting","blast",
    ],
    "ivory_serif": [
        "elegant","refined","sophisticated","classy","tasteful","distinguished",
        "posh","formal","dignified","graceful","noble","timeless elegance",
    ],
    "golden_hour": [
        "golden","hour","warm","amber","glow","sunbeam","daylight","radiant",
        "luminous","golden age","golden gate","treasure","precious","blessed",
    ],
    "vapor_chrome": [
        "vaporwave","vapor","aesthetic","synthwave","retrowave","80s","miami",
        "outrun","synth","palm tree neon","grid","digital sunset","lo-fi","chill",
    ],
    "wild_west": [
        "wanted","outlaw","sheriff","saloon","dusty","frontier","pioneer",
        "desperado","bandit","bounty","gunslinger","rustler","canyon","mesa",
    ],
    "silk_ribbon": [
        "silk","ribbon","satin","smooth","flowing","graceful","elegant flow",
        "delicate","feminine","charming","lovely","enchanting","captivating",
    ],
    "candy_stripe": [
        "stripe","striped","candy","colorful","multicolor","circus","carnival ride",
        "big top","ringmaster","clown","performer","acrobat","trapeze","show",
    ],
    "smoky_noir": [
        "noir","detective","shadow","mystery","dark alley","smoke","smoky",
        "mysterious","enigma","intrigue","suspense","thriller","undercover",
    ],
    "horror_drip": [
        "horror","blood","bloody","scream","nightmare","terror","fear","dread",
        "creepy","sinister","macabre","evil","curse","haunted","possessed",
    ],
    "street_neon": [
        "street","urban","city","downtown","neon sign","night city","alley",
        "block","corner","underground","warehouse","loft","industrial","brick",
    ],
    "vapor_gradient": [
        "gradient","smooth","blend","fade","transition","spectrum","ombre",
        "modern","clean","minimal design","contemporary","fresh look","sleek",
    ],
}

# Phrase-level theme routing (longer = higher priority)
THEME_PHRASES: list[tuple] = sorted([
    # script phrases
    ("taking great care",  "script"),
    ("pre fall",           "script"),
    ("last spring",        "script"),
    ("peak pleasure",      "script"),
    ("sensual aura",       "script"),
    ("the happy beginning","script"),
    # retro
    ("let me do you",      "retro_rainbow"),
    ("wet dream",          "retro_rainbow"),
    ("bigger is better",   "retro_rainbow"),
    # cinematic
    ("peak pleasure",      "cinematic"),
    ("virtual tour",       "cinematic"),
    # editorial
    ("the queen",          "editorial"),
    ("member benefits",    "editorial"),
    # impact
    ("deep release",       "stark"),
    ("bring the heat",     "impact"),
    # chrome
    ("algorithm of blues", "chrome"),
    # graffiti
    ("behind closed doors","graffiti"),
    ("sunrise seduction",  "graffiti"),
    ("cosmic connection",  "graffiti"),
    # bubble
    ("glorious morning",   "bubble"),
    ("wok wild",           "bubble"),
    # vintage
    ("royal treatment",    "vintage"),
    ("the dutch tailor",   "vintage"),
    ("lucky passage",      "vintage"),
    # spray_stencil
    ("pain & gain",        "spray_stencil"),
    ("getting nasty",      "spray_stencil"),
    # liquid_gold
    ("whipping dripping",  "liquid_gold"),
    ("spilling maple",     "liquid_gold"),
    ("oily privatization", "liquid_gold"),
    # neon_box
    ("strip view in vegas","neon_box"),
    ("mardi gras in nola", "neon_box"),
    ("rave & misbehave",   "neon_box"),
    # glitch
    ("signal lost",        "glitch"),
    ("system failure",     "glitch"),
    ("buffer overflow",    "glitch"),
    ("pixel corruption",   "glitch"),
    # holographic
    ("crystal dreams",     "holographic"),
    ("aurora borealis",    "holographic"),
    ("prismatic view",     "holographic"),
    ("iridescent kiss",    "holographic"),
    # fire
    ("body on fire",       "fire"),
    ("playing with fire",  "fire"),
    ("trial by fire",      "fire"),
    ("ring of fire",       "fire"),
    # ice
    ("breaking the ice",   "ice"),
    ("ice cold",           "ice"),
    ("cold as ice",        "ice"),
    ("frozen in time",     "ice"),
    # comic
    ("holy cow",           "comic"),
    ("holy smokes",        "comic"),
    ("pow right in the",   "comic"),
    # drip
    ("let it drip",        "drip"),
    ("paint it wet",       "drip"),
    ("slow pour",          "drip"),
    # outline_glow
    ("ghost of a chance",  "outline_glow"),
    ("neon ghost",         "outline_glow"),
    # movie_title
    ("the untold story",   "movie_title"),
    ("world premiere",     "movie_title"),
    ("limited engagement", "movie_title"),
    ("directed by",        "movie_title"),
    # glitter
    ("all that glitters",  "glitter"),
    ("diamond in the rough","glitter"),
    ("sequin dreams",      "glitter"),
    # psychedelic
    ("third eye open",     "psychedelic"),
    ("mind expanding",     "psychedelic"),
    ("color me crazy",     "psychedelic"),
    ("see the colors",     "psychedelic"),
], key=lambda x: -len(x[0]))  # longest first = highest specificity


def detect_treatment(title: str, theme: str = "", wardrobe: str = "",
                     plot: str = "") -> str:
    _load_learned()
    text  = " ".join([title, theme, wardrobe, plot]).lower().strip()
    words = title.split()
    n     = len(title)

    # 0. LLM-learned route (highest priority)
    if title in _LEARNED:
        t = _LEARNED[title].get("treatment", "")
        if t in TREATMENTS:
            return t

    # 1. Exact phrase match (specificity-ordered)
    for phrase, treatment in THEME_PHRASES:
        if phrase in text:
            return treatment

    # 2. Weighted keyword scoring (longer keyword = stronger signal)
    scores: dict[str,float] = {t: 0.0 for t in KEYWORD_TREATMENT}
    for treatment, kws in KEYWORD_TREATMENT.items():
        for kw in kws:
            if kw in text:
                scores[treatment] += max(1.0, len(kw.split()) * 1.5)

    best = max(scores, key=lambda t: scores[t])
    if scores[best] > 0:
        return best

    # 3. Location title heuristic ("X in City" pattern)
    if re.search(r'\bin\b', title, re.I) and n > 15:
        seed = title_seed(title)
        return ["cinematic", "block_3d", "editorial", "graffiti"][seed % 4]

    # 4. Collection title heuristic
    if re.search(r'\bvol\.?\s*\d+\b', title, re.I) or \
       re.search(r'\bbest\b.*\badventures?\b', title, re.I):
        return "impact"

    # 5. Short title fallback
    if len(words) <= 2 and n <= 12:
        return "stark"
    if len(words) >= 3 and n >= 16:
        seed = title_seed(title)
        return ["script", "editorial", "cinematic", "block_3d",
                "vintage", "liquid_gold"][seed % 6]

    # 6. Deterministic seed fallback across all treatments
    keys = list(TREATMENTS.keys())
    return keys[title_seed(title) % len(keys)]


# ── Top-level generate ────────────────────────────────────────────────────────

# ── Model Name Generators ─────────────────────────────────────────────────────

def render_vra_model_name(name: str) -> Image.Image:
    """
    VRA-style model name: BebasNeue, cyan fill, white stroke, drop shadow, bevel.
    Matches the VRA PSD template exactly.
    Returns transparent RGBA PNG.
    """
    _resolve_fonts()
    name = name.upper()
    font_size = 560
    font_path = FONT_CACHE / "BebasNeue-Regular.ttf"
    if not font_path.exists():
        font_path = FONT_CACHE / "Anton-Regular.ttf"
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except Exception:
        font = ImageFont.load_default()

    # Letter spacing: tracking 120 = 120/1000 em
    spacing = int(font_size * 120 / 1000)
    mask = wide_track_mask(name, font, spacing, pad=70)
    mw, mh = mask.size

    # Cyan gradient fill — slightly lighter in center, matches PSD
    cyan_stops = [
        (85, 200, 245),   # top
        (100, 218, 252),  # mid-bright
        (80, 195, 240),   # bottom
    ]
    fill = colorize(mask, cyan_stops)

    # White stroke: 6px
    stroke_mask = dilate(mask, 6)
    stroke = flat_color(stroke_mask, (255, 255, 255))

    # Bevel/emboss: light from top (90°), strong
    hl, sh = bevel_light(mask, angle_deg=90, strength=2.2)

    # Drop shadow: black, prominent, straight down
    ds = drop_shadow(mask, 2, 18, blur=18, alpha=190)

    return composite(ds, stroke, fill, hl, sh, size=(mw, mh))


def render_vrh_model_name(name: str) -> Image.Image:
    """
    VRH-style model name: Ethnocentric, teal fill with gradient,
    black stroke, strong bevel. Matches the VRH PSD template.
    Returns transparent RGBA PNG sized to ~2800x600 canvas.
    """
    _resolve_fonts()
    name = name.upper()
    font_path = FONT_CACHE / "Ethnocentric-Regular.otf"
    if not font_path.exists():
        font_path = FONT_CACHE / "Audiowide-Regular.ttf"

    # Target canvas ~2800 wide x 600 tall (similar to VRA output).
    # Auto-size font to fit within that width.
    canvas_w, canvas_h = 2800, 600
    # Start with a trial font, measure, and scale to fit
    trial_size = 300
    try:
        trial_font = ImageFont.truetype(str(font_path), trial_size)
    except Exception:
        trial_font = ImageFont.load_default()
    trial_spacing = int(trial_size * 30 / 1000)
    trial_mask = wide_track_mask(name, trial_font, trial_spacing, pad=20)
    tw, th = trial_mask.size
    # Scale font so text width fills ~90% of canvas
    target_w = int(canvas_w * 0.90)
    font_size = max(60, int(trial_size * target_w / tw))
    # Cap font height to ~70% of canvas height
    max_font_h = int(canvas_h * 0.70)
    scaled_h = int(th * font_size / trial_size)
    if scaled_h > max_font_h:
        font_size = int(font_size * max_font_h / scaled_h)


    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except Exception:
        font = ImageFont.load_default()

    spacing = int(font_size * 30 / 1000)
    mask = wide_track_mask(name, font, spacing, pad=30)
    mw, mh = mask.size

    # Teal gradient (lighter top, darker bottom — matches PSD)
    teal_stops = [
        (130, 210, 210),
        (98, 174, 174),
        (65, 140, 140),
    ]
    fill = colorize(mask, teal_stops)

    # Black stroke
    stroke_px = max(3, int(font_size * 6 / 500))
    stroke_mask = dilate(mask, stroke_px)
    stroke = flat_color(stroke_mask, (10, 15, 15))

    # Strong bevel/emboss from top
    hl, sh = bevel_light(mask, angle_deg=90, strength=2.8)

    # Inner glow for the glossy/3D look
    ig_r1 = max(4, int(font_size * 12 / 500))
    ig_r2 = max(2, int(font_size * 5 / 500))
    ig = inner_glow(mask, (160, 220, 220), radii=[(ig_r1, 0.7), (ig_r2, 0.95)])

    text_img = composite(stroke, fill, hl, sh, ig, size=(mw, mh))

    # Center on canvas
    final = Image.new("RGBA", (max(mw, canvas_w), canvas_h), (0, 0, 0, 0))
    px = (final.width - mw) // 2
    py = (canvas_h - mh) // 2
    final.paste(text_img, (px, py), text_img)
    return final


def generate_model_name_png(name: str, studio: str) -> bytes:
    """
    Generate a model name PNG for the given studio.
    Returns PNG bytes (transparent background).
    """
    if studio == "VRA":
        img = render_vra_model_name(name)
    elif studio == "VRH":
        img = render_vrh_model_name(name)
    else:
        img = render_vrh_model_name(name)  # default to VRH style

    # Add padding
    padding = 20
    final = Image.new("RGBA",
                      (img.width + padding * 2, img.height + padding * 2),
                      (0, 0, 0, 0))
    final.paste(img, (padding, padding), img)

    buf = io.BytesIO()
    final.save(buf, format="PNG")
    return buf.getvalue()


def generate_cta_png(
    title:     str,
    out_path:  str  = None,
    treatment: str  = "auto",
    theme:     str  = "",
    wardrobe:  str  = "",
    plot:      str  = "",
    padding:   int  = 30,
    outdir:    str  = None,
) -> str:
    seed = title_seed(title)
    rng  = random.Random(seed)

    if treatment == "auto":
        chosen = detect_treatment(title, theme, wardrobe, plot)
    elif treatment == "random":
        chosen = rng.choice(list(TREATMENTS.keys()))
    else:
        chosen = treatment if treatment in TREATMENTS else \
                 detect_treatment(title, theme, wardrobe, plot)

    result = TREATMENTS[chosen](title, rng)

    final = Image.new("RGBA",
                      (result.width+padding*2, result.height+padding*2),
                      (0,0,0,0))
    final.paste(result, (padding, padding), result)

    if out_path is None:
        safe = re.sub(r'[^\w\s-]','',title).strip().replace(' ','_')
        base = Path(outdir) if outdir else Path("cta_output")
        base.mkdir(parents=True, exist_ok=True)
        out_path = str(base / f"{safe}.png")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "PNG")
    print(f"  ✓  [{chosen}]  {title!r}  →  {final.width}×{final.height}px  →  {out_path}")
    return out_path


# ── Sheet helpers ─────────────────────────────────────────────────────────────

def fetch_csv(sheet_id: str, gid: str = "0") -> list:
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return list(csv.reader(io.StringIO(r.read().decode("utf-8"))))

def fetch_upcoming(sheet_id: str = GRAIL_SHEET_ID) -> list:
    rows, today = fetch_csv(sheet_id), date.today()
    out = []
    for row in rows[1:]:
        if len(row) < 4: continue
        site  = row[0].strip()
        ds    = row[2].strip()
        title = row[3].strip()
        ready = row[14].strip() if len(row) > 14 else ""
        if not title: continue
        if ds:
            try:
                if date.fromisoformat(ds.replace("/","-")) > today:
                    out.append({"site":site,"title":title,"date":ds,"ready":ready})
            except ValueError:
                pass
        else:
            out.append({"site":site,"title":title,"date":"TBD","ready":ready})
    return out

def fetch_script_cues(title: str, sheet_id: str = SCRIPT_SHEET_ID) -> dict:
    try:
        rows = fetch_csv(sheet_id)
    except Exception:
        return {}
    for row in rows[1:]:
        if len(row) > 10 and row[10].strip().lower() == title.lower():
            return {
                "theme":   row[6].strip() if len(row)>6 else "",
                "wardrobe":row[7].strip() if len(row)>7 else "",
                "plot":    row[9].strip() if len(row)>9 else "",
            }
    return {}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate transparent CTA title PNGs — 11 visual treatments",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("title", nargs="?", help="Title to render")
    parser.add_argument("--out",        help="Explicit output path for single title")
    parser.add_argument("--outdir",     default="cta_output",
                        help="Output directory (default: ./cta_output)")
    parser.add_argument("--treatment",  default="auto",
                        help="Treatment: auto, random, or one of: " +
                             ", ".join(TREATMENTS))
    parser.add_argument("--from-sheet", action="store_true",
                        help="Pull upcoming titles from Grail sheet and generate all")
    parser.add_argument("--test-all",   metavar="TITLE",
                        help="Generate every treatment for one title")
    parser.add_argument("--test-outdir",default="./test_all",
                        help="Output directory for --test-all (default: ./test_all)")
    parser.add_argument("--list-treatments", action="store_true",
                        help="Print available treatments and exit")
    parser.add_argument("--download-fonts", action="store_true",
                        help="Pre-download the full optional Google Fonts pack and exit")
    parser.add_argument("--padding",    type=int, default=30,
                        help="Transparent padding in pixels (default: 30)")
    args = parser.parse_args()

    if args.list_treatments:
        print("\nAvailable treatments:")
        for t in TREATMENTS:
            print(f"  {t}")
        print()
        return

    if args.download_fonts:
        print("Downloading font pack to", FONT_CACHE)
        n = download_font_pack(verbose=True)
        print(f"\nDone. {n}/{len(_GFONTS)} fonts downloaded.")
        return

    if args.test_all:
        out = Path(args.test_outdir)
        out.mkdir(parents=True, exist_ok=True)
        title = args.test_all
        safe  = re.sub(r'[^\w\s-]','',title).strip().replace(' ','_')
        print(f"\nGenerating all {len(TREATMENTS)} treatments for: {title!r}\n")
        for t in TREATMENTS:
            generate_cta_png(title, treatment=t,
                             out_path=str(out/f"{safe}_{t}.png"),
                             padding=args.padding)
        print(f"\nDone → {out}/")
        return

    if args.from_sheet:
        scenes = fetch_upcoming()
        if not scenes:
            print("No upcoming scenes found in Grail sheet.")
            return
        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        print(f"\nGenerating {len(scenes)} CTA PNGs → {out}/\n")
        for s in scenes:
            tag = "READY" if s.get("ready","").upper()=="TRUE" else "pending"
            print(f"  [{s['date']}][{tag}] {s['title']}")
            cues = fetch_script_cues(s["title"])
            safe = re.sub(r'[^\w\s-]','',s["title"]).strip().replace(' ','_')
            generate_cta_png(
                s["title"],
                out_path=str(out/f"{safe}.png"),
                treatment=args.treatment,
                padding=args.padding,
                **{k: cues.get(k,"") for k in ("theme","wardrobe","plot")},
            )
        print(f"\nDone. {len(scenes)} PNG(s) saved to {out}/")
        return

    if args.title:
        cues = fetch_script_cues(args.title)
        generate_cta_png(
            args.title,
            out_path=args.out,
            outdir=args.outdir,
            treatment=args.treatment,
            padding=args.padding,
            **{k: cues.get(k,"") for k in ("theme","wardrobe","plot")},
        )
        return

    parser.print_help()
    print("\nExamples:")
    print('  python3 cta_generator.py "Better Than Imagined"')
    print('  python3 cta_generator.py "The Laid Over" --treatment graffiti')
    print('  python3 cta_generator.py --test-all "Better Than Imagined" --test-outdir ./test')
    print('  python3 cta_generator.py --from-sheet --outdir ./titles')
    print('  python3 cta_generator.py --download-fonts')
    print('  python3 cta_generator.py --list-treatments')

if __name__ == "__main__":
    main()
