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

## Known Bug
rclone MEGA bug: "Entry doesn't belong in directory (too short)" drops files from Video Thumbnail/
- scan_mega.py has a directory-existence fallback to handle this
- Do NOT remove this fallback
