#!/usr/bin/env python3
"""CTA Font discovery, download, and resolution."""

import os, sys, re, random
from pathlib import Path

try:
    from PIL import ImageFont
except ImportError:
    os.system(f"{sys.executable} -m pip install pillow --break-system-packages -q")
    from PIL import ImageFont

import urllib.request

# ── Font discovery + optional download ────────────────────────────────────────
FONT_CACHE = Path(__file__).resolve().parent / ".cache" / "cta_fonts"
if not FONT_CACHE.exists():
    # Fallback for dev machines where fonts live under ~/.cache
    FONT_CACHE = Path.home() / ".cache" / "cta_fonts"

_GFONTS = {
    # ── Condensed / display ────────────────────────────────────────────────────
    "Anton-Regular.ttf":              "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
    "BebasNeue-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
    "Oswald-Bold.ttf":                "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "BarlowCond-ExtraBold.ttf":       "https://github.com/google/fonts/raw/main/ofl/barlowcondensed/BarlowCondensed-ExtraBold.ttf",
    "FjallaOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/fjallaone/FjallaOne-Regular.ttf",
    "ChangaOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/changaone/ChangaOne-Regular.ttf",
    "RobotoCondensed-Bold.ttf":       "https://github.com/google/fonts/raw/main/ofl/robotocondensed/RobotoCondensed%5Bwght%5D.ttf",
    "SairaCondensed-ExtraBold.ttf":   "https://github.com/google/fonts/raw/main/ofl/sairacondensed/SairaCondensed-ExtraBold.ttf",
    "Staatliches-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/staatliches/Staatliches-Regular.ttf",
    "SquadaOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/squadaone/SquadaOne-Regular.ttf",
    "PassionOne-Black.ttf":           "https://github.com/google/fonts/raw/main/ofl/passionone/PassionOne-Black.ttf",
    "Homenaje-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/homenaje/Homenaje-Regular.ttf",
    "JockeyOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/jockeyone/JockeyOne-Regular.ttf",
    "StintUltraCondensed-Regular.ttf":"https://github.com/google/fonts/raw/main/ofl/stintultracondensed/StintUltraCondensed-Regular.ttf",
    "RacingSansOne-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/racingsansone/RacingSansOne-Regular.ttf",
    # ── Heavy sans ────────────────────────────────────────────────────────────
    "Barlow-ExtraBold.ttf":           "https://github.com/google/fonts/raw/main/ofl/barlow/Barlow-ExtraBold.ttf",
    "BlackOpsOne-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/blackopsone/BlackOpsOne-Regular.ttf",
    "Montserrat-ExtraBold.ttf":       "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Lato-Black.ttf":                 "https://github.com/google/fonts/raw/main/ofl/lato/Lato-Black.ttf",
    "ArchivoBlack-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf",
    "TitanOne-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/titanone/TitanOne-Regular.ttf",
    "Rowdies-Bold.ttf":               "https://github.com/google/fonts/raw/main/ofl/rowdies/Rowdies-Bold.ttf",
    "Bungee-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/bungee/Bungee-Regular.ttf",
    "FasterOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/fasterone/FasterOne-Regular.ttf",
    "Koulen-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/koulen/Koulen-Regular.ttf",
    "Mohave-Bold.ttf":                "https://github.com/google/fonts/raw/main/ofl/mohave/Mohave%5Bwght%5D.ttf",
    # ── Athletic / ultra-condensed ────────────────────────────────────────────
    "Teko-SemiBold.ttf":              "https://github.com/google/fonts/raw/main/ofl/teko/Teko%5Bwght%5D.ttf",
    "BigShouldersDisplay-Black.ttf":  "https://github.com/google/fonts/raw/main/ofl/bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf",
    "Graduate-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/graduate/Graduate-Regular.ttf",
    "Shrikhand-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/shrikhand/Shrikhand-Regular.ttf",
    "Skranji-Bold.ttf":               "https://github.com/google/fonts/raw/main/ofl/skranji/Skranji-Bold.ttf",
    # ── Slab serif ────────────────────────────────────────────────────────────
    "AlfaSlabOne-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/alfaslabone/AlfaSlabOne-Regular.ttf",
    "Arvo-Bold.ttf":                  "https://github.com/google/fonts/raw/main/ofl/arvo/Arvo-Bold.ttf",
    "RobotoSlab-ExtraBold.ttf":       "https://github.com/google/fonts/raw/main/apache/robotoslab/RobotoSlab%5Bwght%5D.ttf",
    "VastShadow-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/vastshadow/VastShadow-Regular.ttf",
    "RumRaisin-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/rumraisin/RumRaisin-Regular.ttf",
    # ── Comic / pop ───────────────────────────────────────────────────────────
    "Bangers-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf",
    "LuckiestGuy-Regular.ttf":        "https://github.com/google/fonts/raw/main/apache/luckiestguy/LuckiestGuy-Regular.ttf",
    "Boogaloo-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/boogaloo/Boogaloo-Regular.ttf",
    "Lilita-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/lilitaone/LilitaOne-Regular.ttf",
    "Galindo-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/galindo/Galindo-Regular.ttf",
    # ── Elegant / serif display ───────────────────────────────────────────────
    "AbrilFatface-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/abrilfatface/AbrilFatface-Regular.ttf",
    "PlayfairDisplay-Bold.ttf":       "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "Raleway-ExtraBold.ttf":          "https://github.com/google/fonts/raw/main/ofl/raleway/Raleway%5Bwght%5D.ttf",
    "Cinzel-Bold.ttf":                "https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
    "Limelight-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/limelight/Limelight-Regular.ttf",
    "PirataOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/pirataone/PirataOne-Regular.ttf",
    "Sancreek-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/sancreek/Sancreek-Regular.ttf",
    # ── Tech / futuristic ─────────────────────────────────────────────────────
    "RussoOne-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/russoone/RussoOne-Regular.ttf",
    "Exo2-ExtraBold.ttf":             "https://github.com/google/fonts/raw/main/ofl/exo2/Exo2%5Bwght%5D.ttf",
    "Orbitron-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
    "ChakraPetch-Bold.ttf":           "https://github.com/google/fonts/raw/main/ofl/chakrapetch/ChakraPetch-Bold.ttf",
    "Rajdhani-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/rajdhani/Rajdhani-Bold.ttf",
    "Audiowide-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/audiowide/Audiowide-Regular.ttf",
    "Michroma-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/michroma/Michroma-Regular.ttf",
    "Iceland-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/iceland/Iceland-Regular.ttf",
    "TurretRoad-ExtraBold.ttf":       "https://github.com/google/fonts/raw/main/ofl/turretroad/TurretRoad-ExtraBold.ttf",
    "Wallpoet-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/wallpoet/Wallpoet-Regular.ttf",
    "Monoton-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/monoton/Monoton-Regular.ttf",
    "Quantico-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/quantico/Quantico-Bold.ttf",
    # ── Retro / art deco / western ────────────────────────────────────────────
    "Righteous-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/righteous/Righteous-Regular.ttf",
    "Rye-Regular.ttf":                "https://github.com/google/fonts/raw/main/ofl/rye/Rye-Regular.ttf",
    "PressStart2P-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/pressstart2p/PressStart2P-Regular.ttf",
    "Warnes-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/warnes/Warnes-Regular.ttf",
    "Kranky-Regular.ttf":             "https://github.com/google/fonts/raw/main/apache/kranky/Kranky-Regular.ttf",
    "Smokum-Regular.ttf":             "https://github.com/google/fonts/raw/main/apache/smokum/Smokum-Regular.ttf",
    "Rancho-Regular.ttf":             "https://github.com/google/fonts/raw/main/apache/rancho/Rancho-Regular.ttf",
    "RuslanDisplay-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/ruslandisplay/RuslanDisplay-Regular.ttf",
    "StardosStencil-Bold.ttf":        "https://github.com/google/fonts/raw/main/ofl/stardosstencil/StardosStencil-Bold.ttf",
    "FontdinerSwanky-Regular.ttf":    "https://github.com/google/fonts/raw/main/apache/fontdinerswanky/FontdinerSwanky-Regular.ttf",
    "Pirata-One.ttf":                 "https://github.com/google/fonts/raw/main/ofl/pirataone/PirataOne-Regular.ttf",
    # ── Script / handwritten ──────────────────────────────────────────────────
    "Pacifico-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/pacifico/Pacifico-Regular.ttf",
    "Lobster-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/lobster/Lobster-Regular.ttf",
    "DancingScript-Bold.ttf":         "https://github.com/google/fonts/raw/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf",
    "Satisfy-Regular.ttf":            "https://raw.githubusercontent.com/google/fonts/main/apache/satisfy/Satisfy-Regular.ttf",
    "Knewave-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/knewave/Knewave-Regular.ttf",
    "KaushanScript-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/kaushanscript/KaushanScript-Regular.ttf",
    "GreatVibes-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/greatvibes/GreatVibes-Regular.ttf",
    "Sacramento-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/sacramento/Sacramento-Regular.ttf",
    "Yellowtail-Regular.ttf":         "https://github.com/google/fonts/raw/main/apache/yellowtail/Yellowtail-Regular.ttf",
    "LobsterTwo-Bold.ttf":            "https://github.com/google/fonts/raw/main/ofl/lobstertwo/LobsterTwo-Bold.ttf",
    "Courgette-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/courgette/Courgette-Regular.ttf",
    "AmaticSC-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/amaticsc/AmaticSC-Bold.ttf",
    # ── Marker / grunge ───────────────────────────────────────────────────────
    "PermanentMarker-Regular.ttf":    "https://github.com/google/fonts/raw/main/apache/permanentmarker/PermanentMarker-Regular.ttf",
    "SpecialElite-Regular.ttf":       "https://github.com/google/fonts/raw/main/apache/specialelite/SpecialElite-Regular.ttf",
    "RockSalt-Regular.ttf":           "https://github.com/google/fonts/raw/main/apache/rocksalt/RockSalt-Regular.ttf",
    # ── Rounded / bubbly ──────────────────────────────────────────────────────
    "Nunito-ExtraBold.ttf":           "https://github.com/google/fonts/raw/main/ofl/nunito/Nunito%5Bwght%5D.ttf",
    "Rubik-ExtraBold.ttf":            "https://github.com/google/fonts/raw/main/ofl/rubik/Rubik%5Bwght%5D.ttf",
    "Fredoka-SemiBold.ttf":           "https://github.com/google/fonts/raw/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf",
    # ── Luxury / fashion serif ───────────────────────────────────────────────
    "CormorantGaramond-Bold.ttf":     "https://github.com/google/fonts/raw/main/ofl/cormorantgaramond/CormorantGaramond-Bold.ttf",
    "JosefinSans-Bold.ttf":           "https://github.com/google/fonts/raw/main/ofl/josefinsans/JosefinSans%5Bwght%5D.ttf",
    "PoiretOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/poiretone/PoiretOne-Regular.ttf",
    "TenorSans-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/tenorsans/TenorSans-Regular.ttf",
    "Italiana-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/italiana/Italiana-Regular.ttf",
    "Forum-Regular.ttf":              "https://github.com/google/fonts/raw/main/ofl/forum/Forum-Regular.ttf",
    "BodoniModa-Bold.ttf":            "https://github.com/google/fonts/raw/main/ofl/bodonimoda/BodoniModa%5Bopsz%2Cwght%5D.ttf",
    "Corben-Bold.ttf":                "https://github.com/google/fonts/raw/main/ofl/corben/Corben-Bold.ttf",
    "Yeseva-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/yesevaone/YesevaOne-Regular.ttf",
    "Marcellus-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/marcellus/Marcellus-Regular.ttf",
    # ── Gothic / blackletter ─────────────────────────────────────────────────
    "UnifrakturMaguntia-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf",
    "MedievalSharp-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/medievalsharp/MedievalSharp.ttf",
    "Almendra-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/almendra/Almendra-Bold.ttf",
    # ── Brush / handwritten ──────────────────────────────────────────────────
    "Caveat-Bold.ttf":                "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "ShadowsIntoLight-Regular.ttf":   "https://github.com/google/fonts/raw/main/ofl/shadowsintolight/ShadowsIntoLight.ttf",
    "IndieFlower-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower.ttf",
    "PatrickHand-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "ArchitectsDaughter-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/architectsdaughter/ArchitectsDaughter-Regular.ttf",
    "CoveredByYourGrace-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/coveredbyyourgrace/CoveredByYourGrace.ttf",
    "Handlee-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/handlee/Handlee-Regular.ttf",
    # ── Geometric sans ───────────────────────────────────────────────────────
    "Poppins-ExtraBold.ttf":          "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf",
    "Comfortaa-Bold.ttf":             "https://github.com/google/fonts/raw/main/ofl/comfortaa/Comfortaa%5Bwght%5D.ttf",
    "Quicksand-Bold.ttf":             "https://github.com/google/fonts/raw/main/ofl/quicksand/Quicksand%5Bwght%5D.ttf",
    "Outfit-ExtraBold.ttf":           "https://github.com/google/fonts/raw/main/ofl/outfit/Outfit%5Bwght%5D.ttf",
    "SpaceGrotesk-Bold.ttf":          "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "Inter-ExtraBold.ttf":            "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "Manrope-ExtraBold.ttf":          "https://github.com/google/fonts/raw/main/ofl/manrope/Manrope%5Bwght%5D.ttf",
    "Syne-Bold.ttf":                  "https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf",
    "Urbanist-ExtraBold.ttf":         "https://github.com/google/fonts/raw/main/ofl/urbanist/Urbanist%5Bwght%5D.ttf",
    # ── Pixel / 8-bit ────────────────────────────────────────────────────────
    "Silkscreen-Bold.ttf":            "https://github.com/google/fonts/raw/main/ofl/silkscreen/Silkscreen-Bold.ttf",
    "VT323-Regular.ttf":              "https://github.com/google/fonts/raw/main/ofl/vt323/VT323-Regular.ttf",
    "DotGothic16-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/dotgothic16/DotGothic16-Regular.ttf",
    # ── Wide / extended display ──────────────────────────────────────────────
    "BungeeShade-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/bungeeshade/BungeeShade-Regular.ttf",
    "BungeeInline-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/bungeeinline/BungeeInline-Regular.ttf",
    "Tourney-ExtraBold.ttf":          "https://github.com/google/fonts/raw/main/ofl/tourney/Tourney%5Bwdth%2Cwght%5D.ttf",
    "Modak-Regular.ttf":              "https://github.com/google/fonts/raw/main/ofl/modak/Modak-Regular.ttf",
    "Fascinate-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/fascinate/Fascinate-Regular.ttf",
    "Unlock-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/unlock/Unlock-Regular.ttf",
    # ── Horror / decorative ──────────────────────────────────────────────────
    "Creepster-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/creepster/Creepster-Regular.ttf",
    "Nosifer-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/nosifer/Nosifer-Regular.ttf",
    "Butcherman-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/butcherman/Butcherman-Regular.ttf",
    "MetalMania-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/metalmania/MetalMania-Regular.ttf",
    "Eater-Regular.ttf":              "https://github.com/google/fonts/raw/main/ofl/eater/Eater-Regular.ttf",
    # ── Stencil / military ───────────────────────────────────────────────────
    "MajorMonoDisplay-Regular.ttf":   "https://github.com/google/fonts/raw/main/ofl/majormonodisplay/MajorMonoDisplay-Regular.ttf",
    # ── Extra display ────────────────────────────────────────────────────────
    "Codystar-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/codystar/Codystar-Regular.ttf",
    "Baumans-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/baumans/Baumans-Regular.ttf",
    "Megrim-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/megrim/Megrim.ttf",
    "NovaFlat-Regular.ttf":           "https://github.com/google/fonts/raw/main/ofl/novaflat/NovaFlat.ttf",
    "Electrolize-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/electrolize/Electrolize-Regular.ttf",
    "Oxanium-Bold.ttf":               "https://github.com/google/fonts/raw/main/ofl/oxanium/Oxanium%5Bwght%5D.ttf",
    "Expletus-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/expletussans/ExpletusSans%5Bwght%5D.ttf",
    "Tomorrow-Bold.ttf":              "https://github.com/google/fonts/raw/main/ofl/tomorrow/Tomorrow-Bold.ttf",
    "K2D-ExtraBold.ttf":              "https://github.com/google/fonts/raw/main/ofl/k2d/K2D-ExtraBold.ttf",
    "Sixtyfour-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/sixtyfour/Sixtyfour%5BBLED%2CSCAN%5D.ttf",

    # ── Expansion: 30 hand-picked fresh additions (avoiding reflex picks). ────
    # Distinctive display
    "BowlbyOne-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/bowlbyone/BowlbyOne-Regular.ttf",
    "Honk-Variable.ttf":              "https://github.com/google/fonts/raw/main/ofl/honk/Honk%5BMORF%2CSHLN%5D.ttf",
    "Caprasimo-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/caprasimo/Caprasimo-Regular.ttf",
    "Plaster-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/plaster/Plaster-Regular.ttf",
    "RubikMonoOne-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/rubikmonoone/RubikMonoOne-Regular.ttf",
    "Fascinate-Regular.ttf":          "https://github.com/google/fonts/raw/main/ofl/fascinate/Fascinate-Regular.ttf",
    "Foldit-Variable.ttf":            "https://github.com/google/fonts/raw/main/ofl/foldit/Foldit%5Bwght%5D.ttf",
    "ClimateCrisis-Variable.ttf":     "https://github.com/google/fonts/raw/main/ofl/climatecrisis/ClimateCrisis%5BYEAR%5D.ttf",
    "Bungee-Inline.ttf":              "https://github.com/google/fonts/raw/main/ofl/bungeeinline/BungeeInline-Regular.ttf",
    "BungeeShade-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/bungeeshade/BungeeShade-Regular.ttf",

    # Vintage / book serifs (distinct from the existing luxury cluster)
    "CinzelDecorative-Bold.ttf":      "https://github.com/google/fonts/raw/main/ofl/cinzeldecorative/CinzelDecorative-Bold.ttf",
    "IMFellEnglishSC-Regular.ttf":    "https://github.com/google/fonts/raw/main/ofl/imfellenglishsc/IMFELLEnglishSC-Regular.ttf",
    "IMFellDoublePica-Regular.ttf":   "https://github.com/google/fonts/raw/main/ofl/imfelldoublepica/IMFELLDoublePica-Regular.ttf",
    "DellaRespira-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/dellarespira/DellaRespira-Regular.ttf",
    "Lustria-Regular.ttf":            "https://github.com/google/fonts/raw/main/ofl/lustria/Lustria-Regular.ttf",
    "PinyonScript-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/pinyonscript/PinyonScript-Regular.ttf",

    # Modern / variable sans (avoiding banned reflex picks)
    "BricolageGrotesque-Variable.ttf": "https://github.com/google/fonts/raw/main/ofl/bricolagegrotesque/BricolageGrotesque%5Bopsz%2Cwdth%2Cwght%5D.ttf",
    "FunnelDisplay-Variable.ttf":     "https://github.com/google/fonts/raw/main/ofl/funneldisplay/FunnelDisplay%5Bwght%5D.ttf",
    "SansitaSwashed-Variable.ttf":    "https://github.com/google/fonts/raw/main/ofl/sansitaswashed/SansitaSwashed%5Bwght%5D.ttf",

    # Mono with character (no IBM Plex per impeccable rules)
    "Doto-Variable.ttf":              "https://github.com/google/fonts/raw/main/ofl/doto/Doto%5BROND%2Cwght%5D.ttf",
    "MajorMonoDisplay-Regular.ttf":   "https://github.com/google/fonts/raw/main/ofl/majormonodisplay/MajorMonoDisplay-Regular.ttf",
    "VT323-Regular.ttf":              "https://github.com/google/fonts/raw/main/ofl/vt323/VT323-Regular.ttf",

    # Hand-drawn / script
    "Zeyada-Regular.ttf":             "https://github.com/google/fonts/raw/main/ofl/zeyada/Zeyada-Regular.ttf",
    "Caveat-Variable.ttf":            "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "HomemadeApple-Regular.ttf":      "https://github.com/google/fonts/raw/main/apache/homemadeapple/HomemadeApple-Regular.ttf",
    "RougeScript-Regular.ttf":        "https://github.com/google/fonts/raw/main/ofl/rougescript/RougeScript-Regular.ttf",
    "DrSugiyama-Regular.ttf":         "https://github.com/google/fonts/raw/main/ofl/drsugiyama/DrSugiyama-Regular.ttf",
    "ReenieBeanie-Regular.ttf":       "https://github.com/google/fonts/raw/main/ofl/reeniebeanie/ReenieBeanie-Regular.ttf",

    # Specialty
    "UnifrakturCook-Bold.ttf":        "https://github.com/google/fonts/raw/main/ofl/unifrakturcook/UnifrakturCook-Bold.ttf",
    "Rye-Regular.ttf":                "https://github.com/google/fonts/raw/main/ofl/rye/Rye-Regular.ttf",
}

# Font role → candidate paths (ALL valid ones are collected; rng picks from the pool)
_FONT_ROLES = {
    "condensed": [
        FONT_CACHE / "SairaCondensed-ExtraBold.ttf",
        FONT_CACHE / "Staatliches-Regular.ttf",
        FONT_CACHE / "StintUltraCondensed-Regular.ttf",
        FONT_CACHE / "BebasNeue-Regular.ttf",
        FONT_CACHE / "BarlowCond-ExtraBold.ttf",
        FONT_CACHE / "Anton-Regular.ttf",
        FONT_CACHE / "Oswald-Bold.ttf",
        FONT_CACHE / "FjallaOne-Regular.ttf",
        FONT_CACHE / "ChangaOne-Regular.ttf",
        FONT_CACHE / "RobotoCondensed-Bold.ttf",
        FONT_CACHE / "PassionOne-Black.ttf",
        FONT_CACHE / "Homenaje-Regular.ttf",
        FONT_CACHE / "JockeyOne-Regular.ttf",
        FONT_CACHE / "RacingSansOne-Regular.ttf",
        FONT_CACHE / "SquadaOne-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
    ],
    "heavy": [
        FONT_CACHE / "BlackOpsOne-Regular.ttf",
        FONT_CACHE / "ArchivoBlack-Regular.ttf",
        FONT_CACHE / "Barlow-ExtraBold.ttf",
        FONT_CACHE / "Montserrat-ExtraBold.ttf",
        FONT_CACHE / "Lato-Black.ttf",
        FONT_CACHE / "TitanOne-Regular.ttf",
        FONT_CACHE / "Rowdies-Bold.ttf",
        FONT_CACHE / "Bungee-Regular.ttf",
        FONT_CACHE / "Koulen-Regular.ttf",
        FONT_CACHE / "Mohave-Bold.ttf",
        FONT_CACHE / "AlfaSlabOne-Regular.ttf",
        # Expansion
        FONT_CACHE / "BowlbyOne-Regular.ttf",
        FONT_CACHE / "Caprasimo-Regular.ttf",
        FONT_CACHE / "FunnelDisplay-Variable.ttf",
        FONT_CACHE / "BricolageGrotesque-Variable.ttf",
        FONT_CACHE / "BungeeShade-Regular.ttf",
        FONT_CACHE / "Bungee-Inline.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/Users/andrewninn/Library/Fonts/Hamilton-Bold.otf",
    ],
    "athletic": [
        FONT_CACHE / "BigShouldersDisplay-Black.ttf",
        FONT_CACHE / "Teko-SemiBold.ttf",
        FONT_CACHE / "SairaCondensed-ExtraBold.ttf",
        FONT_CACHE / "FjallaOne-Regular.ttf",
        FONT_CACHE / "Graduate-Regular.ttf",
        FONT_CACHE / "Shrikhand-Regular.ttf",
        FONT_CACHE / "Skranji-Bold.ttf",
        FONT_CACHE / "PassionOne-Black.ttf",
        FONT_CACHE / "BebasNeue-Regular.ttf",
        FONT_CACHE / "Anton-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
    ],
    "slab": [
        FONT_CACHE / "AlfaSlabOne-Regular.ttf",
        FONT_CACHE / "Arvo-Bold.ttf",
        FONT_CACHE / "RobotoSlab-ExtraBold.ttf",
        FONT_CACHE / "VastShadow-Regular.ttf",
        FONT_CACHE / "RumRaisin-Regular.ttf",
        FONT_CACHE / "BlackOpsOne-Regular.ttf",
        FONT_CACHE / "ArchivoBlack-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Rockwell Extra Bold.ttf",
    ],
    "comic": [
        FONT_CACHE / "Bangers-Regular.ttf",       # wide comic book — ideal for halftone
        FONT_CACHE / "LuckiestGuy-Regular.ttf",   # chunky retro
        FONT_CACHE / "Lilita-Regular.ttf",         # round & bold
        FONT_CACHE / "Galindo-Regular.ttf",        # wide display
        FONT_CACHE / "Boogaloo-Regular.ttf",       # playful but readable
        FONT_CACHE / "TitanOne-Regular.ttf",       # heavy display
        FONT_CACHE / "Rowdies-Bold.ttf",           # chunky
    ],
    "elegant": [
        FONT_CACHE / "Cinzel-Bold.ttf",
        FONT_CACHE / "Limelight-Regular.ttf",
        FONT_CACHE / "AbrilFatface-Regular.ttf",
        FONT_CACHE / "PlayfairDisplay-Bold.ttf",
        FONT_CACHE / "Raleway-ExtraBold.ttf",
        FONT_CACHE / "PirataOne-Regular.ttf",
        FONT_CACHE / "Sancreek-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf",
    ],
    "tech": [
        FONT_CACHE / "Orbitron-Bold.ttf",
        FONT_CACHE / "ChakraPetch-Bold.ttf",
        FONT_CACHE / "RussoOne-Regular.ttf",
        FONT_CACHE / "Exo2-ExtraBold.ttf",
        FONT_CACHE / "Rajdhani-Bold.ttf",
        FONT_CACHE / "Audiowide-Regular.ttf",
        FONT_CACHE / "Michroma-Regular.ttf",
        FONT_CACHE / "Iceland-Regular.ttf",
        FONT_CACHE / "TurretRoad-ExtraBold.ttf",
        FONT_CACHE / "Wallpoet-Regular.ttf",
        FONT_CACHE / "Monoton-Regular.ttf",
        FONT_CACHE / "Quantico-Bold.ttf",
        FONT_CACHE / "BarlowCond-ExtraBold.ttf",
        # Expansion — mono/dot/CRT character
        FONT_CACHE / "MajorMonoDisplay-Regular.ttf",
        FONT_CACHE / "VT323-Regular.ttf",
        FONT_CACHE / "Doto-Variable.ttf",
        FONT_CACHE / "RubikMonoOne-Regular.ttf",
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
    ],
    "retro": [
        FONT_CACHE / "Rye-Regular.ttf",
        FONT_CACHE / "Righteous-Regular.ttf",
        FONT_CACHE / "LuckiestGuy-Regular.ttf",
        FONT_CACHE / "Boogaloo-Regular.ttf",
        FONT_CACHE / "Warnes-Regular.ttf",
        FONT_CACHE / "Kranky-Regular.ttf",
        FONT_CACHE / "Smokum-Regular.ttf",
        FONT_CACHE / "Rancho-Regular.ttf",
        FONT_CACHE / "RuslanDisplay-Regular.ttf",
        FONT_CACHE / "FontdinerSwanky-Regular.ttf",
        FONT_CACHE / "StardosStencil-Bold.ttf",
        FONT_CACHE / "Nunito-ExtraBold.ttf",
        FONT_CACHE / "Anton-Regular.ttf",
        # Expansion — distinctive retro/display
        FONT_CACHE / "Caprasimo-Regular.ttf",
        FONT_CACHE / "Fascinate-Regular.ttf",
        FONT_CACHE / "Plaster-Regular.ttf",
        FONT_CACHE / "BungeeShade-Regular.ttf",
    ],
    "rounded": [
        FONT_CACHE / "Fredoka-SemiBold.ttf",
        FONT_CACHE / "Nunito-ExtraBold.ttf",
        FONT_CACHE / "Rubik-ExtraBold.ttf",
        FONT_CACHE / "Lilita-Regular.ttf",
        FONT_CACHE / "Galindo-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
        "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    ],
    "script": [
        FONT_CACHE / "Knewave-Regular.ttf",
        FONT_CACHE / "KaushanScript-Regular.ttf",
        FONT_CACHE / "Satisfy-Regular.ttf",
        FONT_CACHE / "Pacifico-Regular.ttf",
        FONT_CACHE / "Lobster-Regular.ttf",
        FONT_CACHE / "LobsterTwo-Bold.ttf",
        FONT_CACHE / "DancingScript-Bold.ttf",
        FONT_CACHE / "Courgette-Regular.ttf",
        FONT_CACHE / "Yellowtail-Regular.ttf",
        FONT_CACHE / "GreatVibes-Regular.ttf",
        FONT_CACHE / "Sacramento-Regular.ttf",
        # Expansion — hand-written variety
        FONT_CACHE / "PinyonScript-Regular.ttf",
        FONT_CACHE / "Zeyada-Regular.ttf",
        FONT_CACHE / "Caveat-Variable.ttf",
        FONT_CACHE / "HomemadeApple-Regular.ttf",
        FONT_CACHE / "RougeScript-Regular.ttf",
        FONT_CACHE / "DrSugiyama-Regular.ttf",
        FONT_CACHE / "ReenieBeanie-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Brush Script.ttf",
        "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    ],
    "marker": [
        FONT_CACHE / "PermanentMarker-Regular.ttf",
        FONT_CACHE / "SpecialElite-Regular.ttf",
        FONT_CACHE / "RockSalt-Regular.ttf",
        FONT_CACHE / "AmaticSC-Bold.ttf",
        FONT_CACHE / "Kranky-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Marker Felt Thin.ttf",
        FONT_CACHE / "Anton-Regular.ttf",
    ],
    "stark": [
        FONT_CACHE / "SairaCondensed-ExtraBold.ttf",
        FONT_CACHE / "Staatliches-Regular.ttf",
        FONT_CACHE / "BebasNeue-Regular.ttf",
        FONT_CACHE / "BlackOpsOne-Regular.ttf",
        FONT_CACHE / "BarlowCond-ExtraBold.ttf",
        FONT_CACHE / "Anton-Regular.ttf",
        FONT_CACHE / "SquadaOne-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    ],
    "serif": [
        FONT_CACHE / "Cinzel-Bold.ttf",
        FONT_CACHE / "AbrilFatface-Regular.ttf",
        FONT_CACHE / "PlayfairDisplay-Bold.ttf",
        FONT_CACHE / "Arvo-Bold.ttf",
        FONT_CACHE / "AlfaSlabOne-Regular.ttf",
        FONT_CACHE / "VastShadow-Regular.ttf",
        FONT_CACHE / "PirataOne-Regular.ttf",
        FONT_CACHE / "BodoniModa-Bold.ttf",
        FONT_CACHE / "CormorantGaramond-Bold.ttf",
        FONT_CACHE / "Yeseva-Regular.ttf",
        FONT_CACHE / "Marcellus-Regular.ttf",
        # Expansion — vintage book/title serifs
        FONT_CACHE / "IMFellEnglishSC-Regular.ttf",
        FONT_CACHE / "IMFellDoublePica-Regular.ttf",
        FONT_CACHE / "DellaRespira-Regular.ttf",
        FONT_CACHE / "Lustria-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    ],
    "luxury": [
        FONT_CACHE / "CormorantGaramond-Bold.ttf",
        FONT_CACHE / "BodoniModa-Bold.ttf",
        FONT_CACHE / "JosefinSans-Bold.ttf",
        FONT_CACHE / "PoiretOne-Regular.ttf",
        FONT_CACHE / "TenorSans-Regular.ttf",
        FONT_CACHE / "Italiana-Regular.ttf",
        FONT_CACHE / "Forum-Regular.ttf",
        FONT_CACHE / "Yeseva-Regular.ttf",
        FONT_CACHE / "Marcellus-Regular.ttf",
        FONT_CACHE / "Cinzel-Bold.ttf",
        FONT_CACHE / "PlayfairDisplay-Bold.ttf",
        FONT_CACHE / "Corben-Bold.ttf",
        FONT_CACHE / "Raleway-ExtraBold.ttf",
        # Expansion
        FONT_CACHE / "CinzelDecorative-Bold.ttf",
        FONT_CACHE / "DellaRespira-Regular.ttf",
        FONT_CACHE / "Lustria-Regular.ttf",
    ],
    "gothic": [
        FONT_CACHE / "UnifrakturMaguntia-Regular.ttf",
        FONT_CACHE / "MedievalSharp-Regular.ttf",
        FONT_CACHE / "Almendra-Bold.ttf",
        FONT_CACHE / "PirataOne-Regular.ttf",
        FONT_CACHE / "Sancreek-Regular.ttf",
        FONT_CACHE / "MetalMania-Regular.ttf",
        # Expansion — second blackletter, first Western
        FONT_CACHE / "UnifrakturCook-Bold.ttf",
        FONT_CACHE / "Rye-Regular.ttf",
    ],
    "brush": [
        FONT_CACHE / "Caveat-Bold.ttf",
        FONT_CACHE / "ShadowsIntoLight-Regular.ttf",
        FONT_CACHE / "IndieFlower-Regular.ttf",
        FONT_CACHE / "PatrickHand-Regular.ttf",
        FONT_CACHE / "ArchitectsDaughter-Regular.ttf",
        FONT_CACHE / "CoveredByYourGrace-Regular.ttf",
        FONT_CACHE / "Handlee-Regular.ttf",
        FONT_CACHE / "PermanentMarker-Regular.ttf",
        FONT_CACHE / "RockSalt-Regular.ttf",
        FONT_CACHE / "Knewave-Regular.ttf",
    ],
    "geometric": [
        FONT_CACHE / "Poppins-ExtraBold.ttf",
        FONT_CACHE / "Comfortaa-Bold.ttf",
        FONT_CACHE / "Quicksand-Bold.ttf",
        FONT_CACHE / "Outfit-ExtraBold.ttf",
        FONT_CACHE / "SpaceGrotesk-Bold.ttf",
        FONT_CACHE / "Inter-ExtraBold.ttf",
        FONT_CACHE / "Manrope-ExtraBold.ttf",
        FONT_CACHE / "Syne-Bold.ttf",
        FONT_CACHE / "Urbanist-ExtraBold.ttf",
        FONT_CACHE / "Montserrat-ExtraBold.ttf",
        FONT_CACHE / "Nunito-ExtraBold.ttf",
        FONT_CACHE / "Rubik-ExtraBold.ttf",
    ],
    "pixel_font": [
        FONT_CACHE / "PressStart2P-Regular.ttf",
        FONT_CACHE / "Silkscreen-Bold.ttf",
        FONT_CACHE / "VT323-Regular.ttf",
        FONT_CACHE / "DotGothic16-Regular.ttf",
        FONT_CACHE / "Sixtyfour-Regular.ttf",
    ],
    "wide": [
        FONT_CACHE / "BungeeShade-Regular.ttf",
        FONT_CACHE / "BungeeInline-Regular.ttf",
        FONT_CACHE / "Bungee-Regular.ttf",
        FONT_CACHE / "Tourney-ExtraBold.ttf",
        FONT_CACHE / "Modak-Regular.ttf",
        FONT_CACHE / "Fascinate-Regular.ttf",
        FONT_CACHE / "Unlock-Regular.ttf",
        FONT_CACHE / "FasterOne-Regular.ttf",
        FONT_CACHE / "TitanOne-Regular.ttf",
    ],
    "horror": [
        FONT_CACHE / "Creepster-Regular.ttf",
        FONT_CACHE / "Nosifer-Regular.ttf",
        FONT_CACHE / "Butcherman-Regular.ttf",
        FONT_CACHE / "MetalMania-Regular.ttf",
        FONT_CACHE / "Eater-Regular.ttf",
        FONT_CACHE / "UnifrakturMaguntia-Regular.ttf",
        FONT_CACHE / "PirataOne-Regular.ttf",
    ],
    "futuristic": [
        FONT_CACHE / "Electrolize-Regular.ttf",
        FONT_CACHE / "Oxanium-Bold.ttf",
        FONT_CACHE / "Tomorrow-Bold.ttf",
        FONT_CACHE / "K2D-ExtraBold.ttf",
        FONT_CACHE / "Baumans-Regular.ttf",
        FONT_CACHE / "Megrim-Regular.ttf",
        FONT_CACHE / "NovaFlat-Regular.ttf",
        FONT_CACHE / "Codystar-Regular.ttf",
        FONT_CACHE / "Orbitron-Bold.ttf",
        FONT_CACHE / "Audiowide-Regular.ttf",
        FONT_CACHE / "Michroma-Regular.ttf",
        FONT_CACHE / "Rajdhani-Bold.ttf",
    ],
}

_RESOLVED: dict[str, list] = {}  # role → list of all valid font paths

def _download_font(name: str, url: str, verbose: bool = False) -> bool:
    dest = FONT_CACHE / name
    if dest.exists():
        return True
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            dest.write_bytes(r.read())
        if verbose:
            print(f"  ↓ {name} — ok")
        return True
    except Exception as e:
        if verbose:
            print(f"  DL {name} -- FAILED ({e})", file=sys.stderr)
        return False

def download_font_pack(verbose: bool = True) -> int:
    ok = 0
    for name, url in _GFONTS.items():
        if verbose:
            print(f"  DL {name}...", end=" ", flush=True)
        if _download_font(name, url, verbose=False):
            if verbose: print("ok")
            ok += 1
        else:
            if verbose: print("FAIL")
    _RESOLVED.clear()
    return ok

def _resolve_fonts():
    if _RESOLVED:
        return
    for role, candidates in _FONT_ROLES.items():
        _RESOLVED[role] = []
        for c in candidates:
            p = Path(c)
            if p.exists():
                try:
                    ImageFont.truetype(str(p), 20)
                    _RESOLVED[role].append(str(p))
                except Exception:
                    pass
    # Silently attempt to download missing critical roles
    needs_download = any(not _RESOLVED.get(r)
                         for r in ("script", "condensed", "heavy", "marker", "retro"))
    if needs_download:
        for name, url in _GFONTS.items():
            _download_font(name, url)
        # Re-try all roles that came up empty
        for role, candidates in _FONT_ROLES.items():
            if not _RESOLVED.get(role):
                for c in candidates:
                    p = Path(c)
                    if p.exists():
                        try:
                            ImageFont.truetype(str(p), 20)
                            _RESOLVED[role].append(str(p))
                        except Exception:
                            pass

# Variable fonts default to Regular weight — map filename → target wght axis value
_VAR_FONT_WEIGHT: dict[str, int] = {
    "Montserrat-ExtraBold.ttf":      800,
    "Oswald-Bold.ttf":               700,
    "RobotoCondensed-Bold.ttf":      700,
    "Mohave-Bold.ttf":               700,
    "Teko-SemiBold.ttf":             600,
    "BigShouldersDisplay-Black.ttf": 900,
    "RobotoSlab-ExtraBold.ttf":      800,
    "PlayfairDisplay-Bold.ttf":      700,
    "Raleway-ExtraBold.ttf":         800,
    "Cinzel-Bold.ttf":               700,
    "Exo2-ExtraBold.ttf":            800,
    "Orbitron-Bold.ttf":             700,
    "DancingScript-Bold.ttf":        700,
    "Nunito-ExtraBold.ttf":          800,
    "Rubik-ExtraBold.ttf":           800,
    "Fredoka-SemiBold.ttf":          600,
    "JosefinSans-Bold.ttf":          700,
    "BodoniModa-Bold.ttf":           700,
    "Caveat-Bold.ttf":               700,
    "Comfortaa-Bold.ttf":            700,
    "Quicksand-Bold.ttf":            700,
    "Outfit-ExtraBold.ttf":          800,
    "SpaceGrotesk-Bold.ttf":         700,
    "Inter-ExtraBold.ttf":           800,
    "Manrope-ExtraBold.ttf":         800,
    "Syne-Bold.ttf":                 700,
    "Urbanist-ExtraBold.ttf":        800,
    "Tourney-ExtraBold.ttf":         800,
    "Oxanium-Bold.ttf":              700,
    "Expletus-Bold.ttf":             700,
}

def F(role: str, size: int, rng: random.Random = None) -> ImageFont.FreeTypeFont:
    """Return a font for the given role. If rng is provided, picks randomly from the pool.
    Automatically sets the weight axis for variable fonts so they render at the intended weight."""
    _resolve_fonts()
    paths = _RESOLVED.get(role, [])
    if not paths:
        for p in _RESOLVED.values():
            if p:
                paths = p
                break
    if paths:
        path = rng.choice(paths) if (rng and len(paths) > 1) else paths[0]
        try:
            # Lazy-import to avoid a circular import at module load time.
            from cta_primitives import LAYOUT_ENGINE
            font = ImageFont.truetype(path, size, layout_engine=LAYOUT_ENGINE)
            fname = Path(path).name
            if fname in _VAR_FONT_WEIGHT:
                try:
                    font.set_variation_by_axes([_VAR_FONT_WEIGHT[fname]])
                except Exception:
                    pass
            return font
        except Exception:
            try:
                font = ImageFont.truetype(path, size)
                fname = Path(path).name
                if fname in _VAR_FONT_WEIGHT:
                    try:
                        font.set_variation_by_axes([_VAR_FONT_WEIGHT[fname]])
                    except Exception:
                        pass
                return font
            except Exception:
                pass
    return ImageFont.load_default()

