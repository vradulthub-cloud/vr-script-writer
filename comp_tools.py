"""
comp_tools.py — Compilation planning helpers
Loads Grail scene data, matches titles to IDs, writes to comp planning sheet.
"""

import os
import re
import sys
import time

# ── Google Sheets setup ───────────────────────────────────────────────────────
_SCRIPTS_DIR = os.path.dirname(__file__)
sys.path.insert(0, _SCRIPTS_DIR)

GRAIL_SHEET_ID = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
COMP_SHEET_ID  = "1i6W4eZ8Bva3HvVmhpAVgjeHwfqbARkwBZ38aUhriaGs"

# Grail sheet tab names per studio
GRAIL_TABS = {"FPVR": "FPVR", "VRH": "VRH", "VRA": "VRA", "NJOI": "NJOI"}

# Comp planning sheet tab names per studio
COMP_TABS = {
    "FPVR": "FPVR Compilations",
    "VRH":  "VRH Compilations",
    "VRA":  "VRA Compilations",
}

# Grail column indices
COL_SITE  = 0
COL_ID    = 1
COL_DATE  = 2
COL_TITLE = 3
COL_CAST  = 4
COL_CATS  = 5
COL_TAGS  = 6

# MEGA studio identifiers are now resolved via s4_client._STUDIO_ALIASES.


def _get_gc():
    """Return an authenticated gspread client."""
    import gspread
    from google.oauth2.service_account import Credentials
    sa_path = os.path.join(_SCRIPTS_DIR, "service_account.json")
    creds = Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)


# ── Grail data loader ─────────────────────────────────────────────────────────

def _retry_on_quota(fn, retries=3, base_wait=15):
    """Retry a function on 429 quota errors with exponential backoff."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                time.sleep(base_wait * (attempt + 1))
                continue
            raise


def load_grail_scenes(studio: str) -> list[dict]:
    """
    Load all scenes for a studio from the Grail sheet.
    Returns list of dicts: {grail_id, title, cast, categories, tags, date, row_idx}
    """
    gc  = _retry_on_quota(lambda: _get_gc())
    sh  = gc.open_by_key(GRAIL_SHEET_ID)
    tab = GRAIL_TABS.get(studio.upper(), studio.upper())
    ws  = sh.worksheet(tab)
    rows = _retry_on_quota(lambda: ws.get_all_values())

    scenes = []
    for i, row in enumerate(rows[1:], start=1):  # skip header
        if len(row) < 4 or not row[COL_ID].strip().isdigit():
            continue
        sid = int(row[COL_ID].strip())
        scenes.append({
            "grail_id":   f"{studio.upper()}{sid:04d}",
            "scene_num":  sid,
            "title":      row[COL_TITLE].strip() if len(row) > COL_TITLE else "",
            "cast":       row[COL_CAST].strip()  if len(row) > COL_CAST  else "",
            "categories": row[COL_CATS].strip()  if len(row) > COL_CATS  else "",
            "tags":       row[COL_TAGS].strip()  if len(row) > COL_TAGS  else "",
            "date":       row[COL_DATE].strip()  if len(row) > COL_DATE  else "",
            "row_idx":    i + 1,  # 1-based sheet row
        })
    return scenes


def find_grail_id(title: str, scenes: list[dict]) -> dict | None:
    """
    Fuzzy-match a scene title to the Grail scenes list.
    Returns the best match or None.
    """
    title_clean = re.sub(r'[^a-z0-9 ]', '', title.lower()).strip()
    best, best_score = None, 0
    for sc in scenes:
        sc_clean = re.sub(r'[^a-z0-9 ]', '', sc["title"].lower()).strip()
        # Exact match
        if title_clean == sc_clean:
            return sc
        # Token overlap score
        t_words  = set(title_clean.split())
        sc_words = set(sc_clean.split())
        if not t_words:
            continue
        score = len(t_words & sc_words) / len(t_words)
        if score > best_score:
            best_score, best = score, sc
    return best if best_score >= 0.5 else None


MEGA_SUBFOLDERS = ["Description", "Legal", "Photos", "Storyboard", "Video Thumbnail", "Videos"]

import s4_client


def create_mega_folder(grail_id: str) -> str:
    """No-op on S4 — buckets don't need pre-created folders, keys are flat.

    Kept for callsite compatibility. Returns the s3:// path of where the
    scene's content will live, in case callers display it as confirmation.
    """
    _m_id = re.match(r'^([A-Za-z]+)', grail_id)
    if not _m_id:
        raise ValueError(f"Invalid grail_id format: {grail_id}")
    studio = _m_id.group(1).upper()
    bucket = s4_client.STUDIO_BUCKETS[studio]
    sid = s4_client.normalize_scene_id(grail_id)
    return f"s3://{bucket}/{sid}/"


def mega_path(grail_id: str) -> str:
    """Return the s3:// URI for a scene's folder. The /Grail/Backup/ branch
    that the legacy MEGA used is gone — backups were merged in the migration."""
    _m_id = re.match(r'^([A-Za-z]+)', grail_id)
    if not _m_id:
        raise ValueError(f"Invalid grail_id format: {grail_id}")
    studio = _m_id.group(1).upper()
    bucket = s4_client.STUDIO_BUCKETS[studio]
    sid = s4_client.normalize_scene_id(grail_id)
    return f"s3://{bucket}/{sid}/"


def _pick_share_object(studio: str, scene_id: str) -> str | None:
    """Choose which object to presign for a 'shareable scene' link.

    Strategy: prefer the largest video in Videos/ (the .mp4 most recipients
    actually want); fall back to the description docx; fall back to any
    object under the scene prefix. Returns the canonical key or None if the
    scene has no objects.
    """
    canonical = s4_client.normalize_scene_id(scene_id)
    # Try the canonical (uppercase) prefix first; resolve_key handles the few
    # lowercase VRH scenes if they're still around at call time.
    for prefix_form in (canonical, canonical.lower()):
        videos = []
        any_obj = None
        desc = None
        for obj in s4_client.list_objects(studio, prefix=f"{prefix_form}/"):
            if obj["key"].endswith("/") and obj["size"] == 0:
                continue
            any_obj = obj
            rel = obj["key"][len(prefix_form) + 1:]
            if rel.startswith("Videos/") and rel.lower().endswith(".mp4"):
                videos.append(obj)
            elif rel.startswith("Description/") and rel.lower().endswith(".docx"):
                desc = obj
        if videos:
            return max(videos, key=lambda o: o["size"])["key"]
        if desc:
            return desc["key"]
        if any_obj:
            return any_obj["key"]
    return None


def mega_export_link(grail_id: str) -> str:
    """Return a shareable URL for a scene. Presigns the scene's primary video
    (largest .mp4 in Videos/) with a 7-day TTL — the SigV4 maximum. The
    weekly refresh_comp_links cron regenerates these so the URLs stored in
    Sheets stay valid.

    Returns "" if the scene has no objects we can share."""
    _m_id = re.match(r'^([A-Za-z]+)', grail_id)
    if not _m_id:
        raise ValueError(f"Invalid grail_id format: {grail_id}")
    studio = _m_id.group(1).upper()
    try:
        key = _pick_share_object(studio, grail_id)
        if not key:
            return ""
        return s4_client.presign(studio, key)
    except Exception:
        return ""


# ── Comp sheet writer ─────────────────────────────────────────────────────────

def write_comp_to_sheet(
    studio: str,
    comp_title: str,
    scenes: list[dict],          # each: {grail_id, title, cast, slr_link}
    dry_run: bool = False,
) -> str:
    """
    Append a new compilation to the planning sheet in 3-column format:
    Col A: "grail_id – Performer, Male" (scene text)
    Col B: SLR scene link (URL)
    Col C: MEGA shareable link
    With a 1-column spacer between comp groups.

    Returns the A1 notation of the first written cell.
    """
    if not scenes:
        raise ValueError("At least 1 scene required")
    import gspread

    gc  = _get_gc()
    sh  = gc.open_by_key(COMP_SHEET_ID)
    tab = COMP_TABS.get(studio.upper())
    if not tab:
        raise ValueError(f"No comp tab for studio {studio}")
    ws  = sh.worksheet(tab)

    all_vals = _retry_on_quota(lambda: ws.get_all_values())
    # Find the rightmost non-empty column in row 2 (header row = index 1)
    header_row = all_vals[1] if len(all_vals) > 1 else []
    # Find next free starting column (skip existing comp groups)
    last_used = 0
    for ci, cell in enumerate(header_row):
        if cell.strip():
            last_used = ci
    # 3 data cols (scene text + link + grail folder) + 1 spacer
    start_col = last_used + 3  # 1-indexed: skip spacer after last comp

    def col_letter(n):
        """Convert 1-based column index to A1 letter(s)."""
        result = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    c0 = start_col      # Scene text column
    c1 = c0 + 1         # Link column
    c2 = c0 + 2         # MEGA path column

    if dry_run:
        print(f"DRY RUN — would write to cols {col_letter(c0)}–{col_letter(c2)}")
        for sc in scenes:
            print(f"  {sc['grail_id']} – {sc['cast']} | {mega_export_link(sc['grail_id'])}")
        return col_letter(c0) + "1"

    # Build batch update
    updates = []

    # Row 2: comp title + "Link to Scene" + "Grail Folder"
    updates.append({
        "range": f"{col_letter(c0)}2:{col_letter(c2)}2",
        "values": [[comp_title, "Link to Scene", "Grail Folder"]],
    })

    # Rows 3+: "grail_id – Cast" | SLR URL | MEGA path
    for i, sc in enumerate(scenes, start=3):
        cast = sc.get("cast", "")
        gid  = sc.get("grail_id", "")
        scene_text = f"{gid.lower()} – {cast}" if cast else gid.lower()
        slr  = sc.get("slr_link", "")
        m_link = mega_export_link(gid)
        updates.append({
            "range": f"{col_letter(c0)}{i}:{col_letter(c2)}{i}",
            "values": [[scene_text, slr, m_link]],
        })

    ws.batch_update(updates)

    # Format header row bold
    try:
        ws.format(
            f"{col_letter(c0)}2:{col_letter(c2)}2",
            {"textFormat": {"bold": True}}
        )
    except Exception:
        pass

    return col_letter(c0) + "2"


# ── Grail sheet writer (for compilations) ────────────────────────────────────

# ── Approved category/tag lists per studio ───────────────────────────────────
_APPROVED_CATS = {
    "FPVR": [
        "8K", "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
        "Body Cumshot", "Brunette", "Compilation", "Creampie", "Cum on Tits",
        "Curvy", "Ebony", "Facial Cumshot", "Hairy Pussy", "Handjob", "Latina",
        "MILF", "Natural Tits", "Petite", "Redhead", "Small Tits", "Threesome",
    ],
    "VRH": [
        "8K", "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
        "Body Cumshot", "Brunette", "Compilation", "Creampie", "Cum in Mouth",
        "Cum on Tits", "Cumshot", "Curvy", "Ebony", "Facial Cumshot",
        "Hairy Pussy", "Handjob", "Hardcore", "Latina", "MILF", "Natural Tits",
        "Oral Creampie", "Petite", "Redhead", "Shaved Pussy", "Small Tits",
        "Threesome",
    ],
    "VRA": [
        "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
        "Brunette", "Compilation", "Curvy", "Ebony", "Hairy Pussy", "Handjob",
        "Latina", "Masturbation", "MILF", "Natural Tits", "Petite", "Redhead",
        "Sex Toys", "Shaved Pussy", "Small Tits",
    ],
}
_APPROVED_TAGS = {
    "FPVR": "8K, African, American, Anal Creampie, Analized, Arab, Argentinian, Asia, Asian, Ass, Ass Bounce, Ass Eating, Ass Fucking, Ass to Mouth, Ass Worship, Athletic, ATM, Australian, Average, Babe, Bald Pussy, Ball Sucking, Bangkok, Beauty Pageant, Belarusian, Belgian, Belgium, Berlin, Big Boobs, Big Fake Tits, Big Natural Tits, Big Oiled Tits, Black, Black Eyes, Blonde, Blue Eyes, Boobjob, Braces, Brazilian, British, Brown Eyes, Brunette, Brunette Fuck, Budapest, Bush, Butt Fuck, Butt Plug, Canadian, Caucasian, Chair Grind, Chile, Chilean, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Colombian, Columbian, Compilation, Cooking, Cowgirl, Creampie, Croatian, Cuban, Cum Eating, Cum in Mouth, Cum In Pussy, Cum on Ass, Cum on Face, Cum Play, Cum Swallow, Cumplay, Czech, Czech Republic, Dancing, Deep Anal, Deep Throat, Deep Throating, Deepthroat, Dick Sucking, Doggy, Doggy Style, Doggystyle, Dutch, Eating Ass, Ebony Babe, Escort, Euro Babe, European, Face Fucking, Face in Camera, Facefuck, Facial, Fake Tits, Farmer's Daughter, FFM porn, Filipina, Filipino, Finger Play, Fingering, Finnish, Fishnet Stockings, Foot Job, Footjob, Freckles, French, German, GFE, Glasses, Green Eyes, Grey Eyes, Grinding, Hair Pulling, Hairy Pussy, Hand Job, Hazel Eyes, Hispanic, Hot Tub, Humping, Hungarian, Intimate, Italian, Italy, Japanese, Jerk to Pop, Jizz Shot, Kenyan, Kissing, Landing Strip, Lap Dance, Latin, Latin Pussy, Latvian, Lingerie, Long Hair, Long Legs, Maid, Maltese, Massage, Massage Oil, Masseuse, Masturbation, Mexican, Mexico, Middle Eastern, Milf Porn, Missionary, Moldovan, Natural Boobs, Natural Tits, Navel Piercing, Nipple Piercing, Nipple Piercings, Nipple Play, Oil, Oil Massage, Oiled Tits, Oral Creampie, Panty Sniffing, Peruvian, Petite, PHAT Ass, Pierce Nipples, Pierced Clit, Pierced Nipples, Pierced Pussy, Pole Dancing, Polish, POV, POV BJ, Puerto Rican, Pull Out Cumshot, Pullout Cumshot, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy to Mouth, Pussy Worship, Redhead, Reverse Cowgirl, Rimjob, Roller Skates, Russian, Saudi, Saudi Arabian, Secretary, Septum Piercing, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Sexy Redheads, Shaved, Shaved Pussy, Short Skirt, Sixty-nine, Slim, Sloppy Blowjob, Slovakian, Small Boobs, Small Natural Tits, South America, Spanish, Squirter, Standing Doggy, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Sucking Tits, Swallow, Syrian, Tall, Tattoo, Tattooed, Tattoos, Tease, Thailand, Tight Ass, Titjob, Tits in Face, Titty Fuck, Titty Sucking, Tittyjob, Toys, Trimmed, Trimmed Pussy, True 8K, Turkish, Turkish Babe, Twerking, Ukraine, Ukrainian, United States, Venezuelan, Vibrator, Wrestling",
    "VRH": "8K, American, Anal, Analized, Arab, Asian, Ass, Ass Bounce, Ass Fucking, Ass Worship, Ass to Mouth, Athletic, ATM, Average, Bald Pussy, Ball Sucking, Big Boobs, Big Fake Tits, Big Natural Tits, Black, Blue Eyes, Brazilian, Brown Eyes, Brunette Fuck, Bush, Butt Fuck, Butt Plug, Canadian, Caucasian, Chair Grind, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Compilation, Cowgirl, Creampie, Cuban, Cum Eating, Cum in Mouth, Cum In Pussy, Cum on Ass, Cum on Face, Cum on Tits, Cum Play, Cum Swallow, Czech, Dancing, Deep Anal, Deep Throat, Deepthroat, Dick Sucking, Doggy Style, Doggystyle, Dutch, Ebony, Escort, Euro Babe, European, Facial, Fake Tits, Filipina, Filipino, Fingering, Fishnet Stockings, Footjob, Freckles, GFE, Glasses, Green Eyes, Grey Eyes, Hairy Pussy, Hazel Eyes, Hispanic, Intimate, Italian, Japanese, Jerk to Pop, Kissing, Landing Strip, Latin, Lingerie, Maltese, Massage, Massage Oil, Masseuse, Masturbation, Middle Eastern, Milf Porn, Missionary, Natural Boobs, Natural Tits, Navel Piercing, Oral Creampie, PHAT Ass, POV, POV BJ, Pierced Clit, Pierced Nipples, Polish, Pull Out Cumshot, Pullout Cumshot, Puerto Rican, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy Worship, Reverse Cowgirl, Rimjob, Roleplay, Romanian, Russian, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Shaved, Shaved Pussy, Short Skirt, Sixty-nine, Slim, Slovakian, Small Boobs, Small Natural Tits, Spanish, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Syrian, Tattoos, Threesome, Tight Ass, Titjob, Tits in Face, Titty Fuck, Titty Sucking, Tittyjob, Toys, Trimmed, Trimmed Pussy, True 8K, Twerking, Ukrainian, Vibrator",
    "VRA": "8K, American, Anal, Arab, Asian, Ass, Ass Bounce, Ass Spread, Ass Worship, Athletic, Australian, Average, Bald Pussy, Big Boobs, Big Fake Tits, Big Natural Tits, Black, Blue Eyes, Brazilian, Brown Eyes, Brunette Fuck, Bush, Butt Plug, Canadian, Caucasian, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Colombian, Compilation, Cowgirl, Creampie, Cuban, Curvy, Dancing, Deep Anal, Dick Sucking, Dildo Penetration, Doggy Style, Ebony, Euro Babe, European, Fake Tits, Filipina, Filipino, Fingering, Fishnet Stockings, Footjob, French, GFE, Glasses, Green Eyes, Grey Eyes, Hairy Pussy, Hazel Eyes, Intimate, Italian, Japanese, Jerk Off Instructions, Ken Doll, Kissing, Landing Strip, Latin, Latina, Lingerie, Maltese, Masturbation, Middle Eastern, Milf Porn, Missionary, Mongolian, Natural Boobs, Natural Tits, Navel Piercing, Outdoors, PHAT Ass, POV, POV BJ, Pierced Clit, Pierced Nipples, Polish, Puerto Rican, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy Worship, Pussylick, Reverse Cowgirl, Russian, Saudi, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Shaved, Shaved Pussy, Sixty-nine, Slim, Small Boobs, Small Natural Tits, Solo, Spanish, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Syrian, Tattoos, Teens, Tight Ass, Titjob, Titty Fuck, Toys, Trimmed, Trimmed Pussy, True 8K, Twerking, Vibrator, Voyeur",
}


def _generate_comp_cats_tags(
    studio: str, comp_title: str, scenes: list[dict], api_key: str
) -> tuple[str, str]:
    """Use Claude to generate appropriate categories and tags for a compilation,
    constrained to the studio's approved lists."""
    import anthropic
    import json as _json

    approved_cats = _APPROVED_CATS.get(studio.upper())
    approved_tags = _APPROVED_TAGS.get(studio.upper(), "")

    # Collect all scene cats/tags for context
    all_cats = set()
    all_tags = set()
    for sc in scenes:
        for c in sc.get("categories", "").split(","):
            if c.strip():
                all_cats.add(c.strip())
        for t in sc.get("tags", "").split(","):
            if t.strip():
                all_tags.add(t.strip())

    cat_constraint = ""
    tag_constraint = ""
    if approved_cats:
        cat_constraint = f"\nAPPROVED CATEGORIES (you MUST only use categories from this list):\n{', '.join(approved_cats)}"
    if approved_tags:
        tag_constraint = f"\nAPPROVED TAGS (you MUST only use tags from this list):\n{approved_tags}"

    prompt = f"""Generate categories and tags for a VR compilation video.

Compilation title: {comp_title}
Studio: {studio}
Number of scenes: {len(scenes)}

Categories from included scenes: {', '.join(sorted(all_cats))}
Tags from included scenes: {', '.join(sorted(all_tags))}
{cat_constraint}
{tag_constraint}

Rules:
- Pick 5-10 categories that best match the compilation theme
- Always include "Compilation" and "8K" as categories
- Pick 10-20 tags that best match the compilation theme
- Use EXACT spelling and casing from the approved lists — do not invent new ones
- Return ONLY valid JSON, no markdown fences

Output format:
{{"categories": "Cat1, Cat2, Cat3", "tags": "Tag1, Tag2, Tag3"}}"""

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw, flags=re.M)
    raw = re.sub(r'^```\s*', '', raw, flags=re.M)
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as _je:
        raise ValueError(f"AI returned invalid JSON: {_je}") from _je
    return data.get("categories", ""), data.get("tags", "")


def write_comp_to_grail(
    studio:    str,
    comp_title: str,
    scenes:    list[dict],   # each: {grail_id, title, cast, categories, ...}
    api_key:   str = "",
) -> dict:
    """
    Append a compilation entry to the Grail sheet.
    Auto-assigns the next sequential ID.
    Uses AI to generate appropriate categories/tags from the comp theme.
    Date is left blank (filled in when the comp is published).
    Returns: {grail_id, scene_num, row_idx}
    """

    gc  = _retry_on_quota(lambda: _get_gc())
    sh  = gc.open_by_key(GRAIL_SHEET_ID)
    tab = GRAIL_TABS.get(studio.upper(), studio.upper())
    ws  = sh.worksheet(tab)
    rows = _retry_on_quota(lambda: ws.get_all_values())

    # Check for duplicate title in last 20 rows
    for r in rows[-20:]:
        if len(r) > COL_TITLE and r[COL_TITLE].strip().lower() == comp_title.strip().lower():
            raise ValueError(f"Comp '{comp_title}' already exists in the Grail sheet — skipping duplicate")

    # Find next ID
    max_id = 0
    for r in rows[1:]:
        if len(r) > COL_ID and r[COL_ID].strip().isdigit():
            max_id = max(max_id, int(r[COL_ID].strip()))
    next_id = max_id + 1

    # Merge unique performers
    all_cast = []
    seen_cast = set()
    for sc in scenes:
        for name in sc.get("cast", "").split(","):
            name = name.strip()
            if name and name.lower() not in seen_cast:
                seen_cast.add(name.lower())
                all_cast.append(name)

    # Categories and tags disabled — user fills these in manually for now
    new_row = [
        studio.lower(),          # Site
        str(next_id),            # ID
        "",                      # Date of Release — left blank for comps
        comp_title,              # Scene Title
        ", ".join(all_cast),     # Pornstars
        "",                      # Category — disabled, user fills manually
        "",                      # Tags — disabled, user fills manually
    ]

    ws.append_row(new_row, value_input_option="USER_ENTERED")

    grail_id = f"{studio.upper()}{next_id:04d}"
    return {"grail_id": grail_id, "scene_num": next_id, "row_idx": len(rows) + 1}


# ── Existing comp loader ──────────────────────────────────────────────────────

def load_existing_comps(studio: str) -> list[dict]:
    """
    Read the comp planning sheet for a studio and return a list of all
    existing compilations with their scene lists.
    Returns: [{title, scenes: [scene_text], vol: int}]
    """
    gc  = _retry_on_quota(lambda: _get_gc())
    sh  = gc.open_by_key(COMP_SHEET_ID)
    tab = COMP_TABS.get(studio.upper())
    if not tab:
        return []
    ws   = sh.worksheet(tab)
    rows = _retry_on_quota(lambda: ws.get_all_values())

    if len(rows) < 2:
        return []

    header_row = rows[1]  # row index 1 = sheet row 2
    comps = []
    ci = 0
    while ci < len(header_row):
        cell = header_row[ci].strip()
        # A comp title cell: non-empty, not a sub-header
        skip = {"Link to Scene", "Scene Title", "Performers", "SLR Link", "MEGA Path", "Grail #", ""}
        if cell and cell not in skip:
            scenes = []
            for row in rows[2:]:
                val = row[ci].strip() if ci < len(row) else ""
                if val:
                    scenes.append(val)
            # Parse volume number from title
            vol_match = re.search(r'(?:[Vv]ol(?:ume)?\.?\s*(\d+))', cell)
            vol = int(vol_match.group(1)) if vol_match else 1
            # Strip volume suffix to get base theme
            base = re.sub(r'\s*[Vv]ol(?:ume)?\.?\s*\d+', '', cell).strip()
            comps.append({"title": cell, "base_theme": base, "vol": vol, "scenes": scenes})
        ci += 1

    return comps


# ── AI idea suggester ─────────────────────────────────────────────────────────

def suggest_comp_ideas(
    studio:        str,
    api_key:       str,
    n_ideas:       int = 6,
    grail_scenes:  list[dict] | None = None,
    existing_comps: list[dict] | None = None,
) -> list[dict]:
    """
    Analyse existing compilations + available Grail scenes to suggest new
    compilation ideas the studio hasn't done yet (or Vol.N+1 continuations).

    Returns list of:
    {
      "title":           "VRHush Best Cowgirl Moments Vol.1",
      "theme":           "Cowgirl",
      "vol":             1,
      "available_count": 14,
      "grail_ids":       ["VRH0305", ...],   # pre-filtered candidates
      "rationale":       "14 strong cowgirl scenes, none yet featured in a comp"
    }
    """
    import anthropic
    import json as _json
    from collections import Counter

    if grail_scenes is None:
        grail_scenes = load_grail_scenes(studio)
    if existing_comps is None:
        existing_comps = load_existing_comps(studio)

    # ── Build category/tag frequency map from Grail ──────────────────────────
    cat_scenes: dict[str, list[str]] = {}
    for sc in grail_scenes:
        combined = sc["categories"] + ", " + sc["tags"]
        tokens = [t.strip().title() for t in combined.split(",") if t.strip()]
        for tok in tokens:
            cat_scenes.setdefault(tok, []).append(sc["grail_id"])

    # ── Build already-used scene IDs per base theme ──────────────────────────
    used_in_comp: dict[str, list[str]] = {}  # base_theme → [grail_ids]
    existing_titles = []
    for ec in existing_comps:
        existing_titles.append(ec["title"])
        used_in_comp[ec["base_theme"]] = ec["scenes"]

    # ── Build compact category summary for the prompt ────────────────────────
    # Sort categories by scene count descending; include top IDs per category
    sorted_cats = sorted(cat_scenes.items(), key=lambda x: -len(x[1]))
    cat_lines = []
    for cat, ids in sorted_cats[:80]:  # top 80 categories is plenty
        sample = ", ".join(ids[:8])  # up to 8 example IDs
        cat_lines.append(f"  {cat} ({len(ids)} scenes): {sample}{'...' if len(ids) > 8 else ''}")
    cat_block = "\n".join(cat_lines)

    existing_block = "\n".join(f"- {t}" for t in existing_titles) if existing_titles else "None yet"

    system = (
        f"You are a senior content strategist for {studio}, a premium VR adult studio. "
        f"You understand what makes a great themed compilation — strong visual variety, "
        f"popular acts/positions, and performer diversity. Your job is to find compilation "
        f"opportunities that are proven performers (popular categories) but haven't been "
        f"covered yet, or deserve a sequel volume."
    )

    prompt = f"""Analyse the existing {studio} compilations and suggest {n_ideas} new compilation ideas.

EXISTING COMPILATIONS (already published — avoid exact repeats):
{existing_block}

CATEGORY FREQUENCY MAP ({len(grail_scenes)} total scenes):
Each line: Category (count of matching scenes): example Grail IDs
{cat_block}

Instructions:
1. Use the category frequency map to identify popular themes
2. Identify themes NOT yet covered by existing comps (or where a Vol.2+ is justified with enough fresh scenes)
3. For continuations (Vol.2, Vol.3), use the same base theme name as the existing comp
4. Prioritise themes with the most matching scenes (more = better compilation depth)
5. Suggest a healthy mix: act-based (Blowjob, Anal), appearance-based (Blonde, Big Tits), mood-based (Romance, Taboo)
6. For candidate_ids pick 8–12 of the best-matching Grail IDs from the category map above
7. Return ONLY valid JSON — no markdown fences, no explanation outside the JSON

Output format:
{{
  "ideas": [
    {{
      "title": "Full compilation title e.g. '{studio} Best Cowgirl Moments Vol.1'",
      "theme": "Cowgirl",
      "vol": 1,
      "rationale": "Why this comp would work — mention scene count and key performers",
      "candidate_ids": ["VRH0305", "VRH0369"]
    }}
  ]
}}"""

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw, flags=re.M)
    raw = re.sub(r'^```\s*', '', raw, flags=re.M)
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as _je:
        raise ValueError(f"AI returned invalid JSON: {_je}") from _je

    # Enrich each idea with available_count from our local frequency map
    scene_map = {sc["grail_id"]: sc for sc in grail_scenes}
    results = []
    for idea in data.get("ideas", []):
        theme = idea.get("theme", "")
        cids  = [c.upper() for c in idea.get("candidate_ids", [])]
        # Count how many Grail scenes match this theme via category map
        theme_key = theme.title()
        all_for_theme = cat_scenes.get(theme_key, cids)
        results.append({
            "title":           idea.get("title", ""),
            "theme":           theme,
            "vol":             idea.get("vol", 1),
            "available_count": len(all_for_theme),
            "candidate_ids":   cids,
            "rationale":       idea.get("rationale", ""),
        })
    return results


# ── AI comp generator ─────────────────────────────────────────────────────────

def generate_comp_with_ai(
    studio:    str,
    theme:     str,
    n_scenes:  int,
    api_key:   str,
    grail_scenes:   list[dict] | None = None,
    existing_comps: list[dict] | None = None,
    preferred_ids:  list[str]  | None = None,
) -> dict:
    """
    Use Claude to pick the best scenes from the Grail for a given theme.
    Returns: {comp_title, scenes: [{grail_id, title, cast, rationale}]}
    """
    import anthropic
    import json as _json

    if grail_scenes is None:
        grail_scenes = load_grail_scenes(studio)
    if existing_comps is None:
        existing_comps = load_existing_comps(studio)

    # Collect all scene IDs already used in any previous comp
    already_used = set()
    for ec in existing_comps:
        for s in ec.get("scenes", []):
            m = re.search(r'[A-Za-z]+\d{3,4}', s)
            if m:
                already_used.add(m.group(0).upper())

    # Build compact scene list — mark already-used and flag preferred candidates
    preferred_set = set(p.upper() for p in (preferred_ids or []))
    scene_lines = []
    for sc in grail_scenes:
        gid    = sc["grail_id"]
        used   = " [ALREADY IN PREV COMP]" if gid in already_used else ""
        pref   = " [SUGGESTED CANDIDATE]"  if gid in preferred_set else ""
        line   = f"ID:{gid}{pref}{used} | {sc['title']} | Cast:{sc['cast']} | Cats:{sc['categories'][:80]}"
        scene_lines.append(line)

    scene_block = "\n".join(scene_lines)

    # Next vol number for this theme
    theme_clean = re.sub(r'[^a-z0-9 ]', '', theme.lower())
    next_vol = 1
    for ec in existing_comps:
        base = re.sub(r'[^a-z0-9 ]', '', ec.get("base_theme", "").lower())
        if base and (base in theme_clean or theme_clean in base):
            next_vol = max(next_vol, ec.get("vol", 1) + 1)

    system = (
        f"You are a compilation video curator for {studio}, a VR adult studio. "
        f"Your job is to select the best scenes for themed compilation videos "
        f"based on scene metadata."
    )

    prompt = f"""Select exactly {n_scenes} scenes for a '{theme}' compilation for {studio}.
This will be Vol.{next_vol} (previous volumes already exist if next_vol > 1).

Available scenes:
{scene_block}

Rules:
- Pick scenes whose categories OR tags STRONGLY match the theme
- Prefer scenes NOT marked [ALREADY IN PREV COMP] — fresh scenes keep compilations novel
- STRONGLY prefer scenes marked [SUGGESTED CANDIDATE] if they fit the theme
- Prefer variety of performers (avoid repeating the same performer more than once unless pool is small)
- Choose scenes that would make a compelling, well-paced compilation
- Return ONLY valid JSON — no markdown, no explanation

Output format:
{{
  "comp_title": "Suggested full compilation title e.g. '{studio} Best {theme} Vol.{next_vol}'",
  "scenes": [
    {{"grail_id": "FPVR0123", "rationale": "One sentence why this scene fits"}}
  ]
}}"""

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    # Strip markdown fences if present
    raw = re.sub(r'^```json\s*', '', raw, flags=re.M)
    raw = re.sub(r'^```\s*', '', raw, flags=re.M)
    result = _json.loads(raw)

    # Enrich with full scene data
    scene_map = {sc["grail_id"]: sc for sc in grail_scenes}
    enriched  = []
    for item in result.get("scenes", []):
        gid = item["grail_id"].upper()
        sc  = scene_map.get(gid, {})
        enriched.append({
            "grail_id":  gid,
            "title":     sc.get("title", ""),
            "cast":      sc.get("cast", ""),
            "categories":sc.get("categories", ""),
            "rationale": item.get("rationale", ""),
            "slr_link":  "",  # user can fill in
        })
    result["scenes"] = enriched
    return result
