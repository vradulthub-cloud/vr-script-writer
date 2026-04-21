---
paths:
  - "scan_mega.py"
  - "sync_mega_staging.py"
  - "mega_scan.json"
---

# MEGA Storage Rules

## Paths & Remotes
- Mac rclone remote: `mega_test`
- Windows rclone: `C:\Users\andre\rclone.exe`, remote `mega`
- MEGAcmd (Windows): `C:\Users\andre\AppData\Local\MEGAcmd\`

## Scene Folder Structure
- Main path: `mega:/Grail/{STUDIO}/{ID}/` (newer scenes)
- Backup path: `mega:/Grail/Backup/{STUDIO}/{ID}/` (older scenes)
- Subfolders: Videos/, Storyboard/, Photos/, Legal/, Description/, Video Thumbnail/

## Scan & Sync
- `scan_mega.py` (Mac) → `mega_scan.json` → SCP'd to Windows
- `sync_mega_staging.py` — pulls staging from Windows, uploads to MEGA, cron `*/2 * * * *`
- `mega_scan.json` on Mac may be stale — the live copy is on Windows

## Empty Shell Folders
Scene folders are commonly pre-provisioned with empty subfolders (Videos/, Photos/, Video Thumbnail/, etc.) before any assets are uploaded. Dir-existence means NOTHING on its own — `has_*` flags must require an actual file.

## Previously-suspected Bug (now refuted)
There was a theory that rclone/MEGA's "Entry doesn't belong in directory (too short)" warning dropped files from Video Thumbnail/ during recursive listings, and scan_mega.py had a directory-existence fallback to compensate. Removed 2026-04-21 — ground-truth `rclone ls` probes on every scene that triggered the fallback confirmed those folders were genuinely empty shells. The fallback was producing hundreds of false positives. Do NOT re-add it without concrete evidence files are being dropped; has_thumbnail=True with no filename is useless anyway because the thumbnail proxy needs the filename to serve the image.
