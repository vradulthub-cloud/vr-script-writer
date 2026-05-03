---
paths:
  - "scan_mega.py"
  - "sync_mega_staging.py"
  - "mega_scan.json"
  - "s4_client.py"
  - "comp_tools.py"
  - "comp_photoset.py"
---

# MEGA S4 Storage Rules

We migrated off the legacy MEGA cloud account to **MEGA S4** (S3-compatible
object storage) on 2026-04-29. All rclone + MEGAcmd plumbing is gone — every
S4 op flows through `s4_client.py`.

## Buckets & endpoint
- Endpoint: `https://s3.g.s4.mega.io` (virtual-host style: `{bucket}.s3.g.s4.mega.io`)
- One bucket per studio — flat lowercase studio code:

  | Studio | Bucket |
  |---|---|
  | FPVR | `fpvr` |
  | VRH  | `vrh` |
  | VRA  | `vra` |
  | NJOI | `njoi` (note: drops the `NN` from the Grail-tab convention) |

- Out-of-scope buckets in the same account: `models`, `bjn`, `eclatech` — codebase ignores them.

## Key shape
- Bucket-rooted scene ID, **no `/Grail/`, no studio prefix**. Example: in
  bucket `vrh`, the description for VRH0762 lives at
  `VRH0762/Description/VRH0762_description.docx`.
- Subfolders preserved verbatim: `Description/`, `Videos/`, `Photos/`,
  `Storyboard/`, `Legal/`, `Video Thumbnail/` (case-sensitive).
- The legacy `/Grail/Backup/{STUDIO}/` hierarchy was merged into the main
  tree during migration — `comp_tools.mega_path` no longer probes a Backup
  branch.

## Casing
The migration preserved on-disk casing. The `vrh` bucket has 23 lowercase
prefixes (`vrh0002/...` through `vrh0025/...`) alongside 281 uppercase ones.
Code holding canonical (always-uppercase) scene IDs uses
`s4_client.resolve_key()` which falls back to the lowercase variant on a
404 — at most 1 extra HEAD per cache-miss.

The `rename_lowercase_vrh.py` ops script backfills these to uppercase
(server-side COPY + DELETE per object). After it runs, `resolve_key`'s
fallback path becomes unreachable but stays as a safety net.

## Credentials
Loaded by `s4_client._autoload_creds()` at import time from one of
(in priority order):

1. `$S4_ENV_FILE` if set
2. `~/.config/eclatech/s4.env` — Mac shell + cron
3. `<dir of s4_client.py>/.config/eclatech/s4.env`
4. `<dir of s4_client.py>/s4.env` — flat, used on Windows where the
    EclatechHubAPI service runs as LocalSystem (no $HOME)

Required env vars:
```
S4_ENDPOINT_URL=https://s3.g.s4.mega.io
S4_ACCESS_KEY_ID=...
S4_SECRET_ACCESS_KEY=...
S4_REGION=us-east-1
```

## Destructive-op protection (no versioning, no undo)
MEGA S4 does **not** support bucket versioning — verified 2026-04-30 via
boto3 (`get_bucket_versioning` returns `NotImplemented`). Once an object
is deleted, it's gone. To compensate:

1. **Code-level guard** — `s4_client._client()` registers a boto3 event
   hook that blocks `DeleteObject` / `DeleteObjects` / `DeleteBucket`
   unless `S4_ALLOW_DESTRUCTIVE=1` is set in the calling process's env.
   Both the convenience `s4_client.delete_object()` and direct
   `_client().delete_object()` calls go through this guard.

   To delete intentionally:
   ```bash
   S4_ALLOW_DESTRUCTIVE=1 python3 your_ops_script.py
   ```
   Never put this in any persistent env file, dotenv, shell rc, or CI
   secret. It must be set per-invocation, in plain sight.

2. **Read-only credential pattern (recommended)** — create a separate
   read-only access key in the MEGA S4 console, save its env to
   `~/.config/eclatech/s4.env.readonly`, and use it for ad-hoc / agent /
   review work:
   ```bash
   S4_ENV_FILE=~/.config/eclatech/s4.env.readonly python3 -c "..."
   ```
   The full-access key stays the default for the FastAPI service and
   Mac cron. Combined with the guard above, even a leaked or
   misused full-access key needs an explicit env opt-in to delete.

3. **Daily snapshot tripwire** — `snapshot_s4.py` writes a gzipped key
   listing for every bucket to `~/Scripts/logs/s4_snapshots/`. Cron it
   for 5 AM:
   ```
   0 5 * * *  /opt/homebrew/bin/python3 ~/Scripts/snapshot_s4.py >> ~/Scripts/logs/s4_snapshots.log 2>&1
   ```
   Diff yesterday vs today: `python3 snapshot_s4.py --diff`. Catches
   unauthorized deletes within 24 h even if they slip past #1.

## Shareable links (compilation index)
Presigned URLs cap at 7 days (SigV4 max). `comp_tools.mega_export_link`
presigns the scene's primary video (largest .mp4 in `Videos/`, falls back
to description .docx, falls back to any object).

`refresh_comp_links.py` is a weekly cron that walks each studio's `{Studio}
Index` tab and rewrites column F per scene row. Suggested cadence:
```
0 3 * * 0  python3 ~/Scripts/refresh_comp_links.py >> ~/Scripts/logs/refresh_comp_links.log 2>&1
```

## Scan & sync
- `scan_mega.py` (Mac) — `s4_client.list_objects` per studio → `mega_scan.json` → SCP'd to Windows. Cron `0 6,14 * * *`. ~50s for ~92k objects across 4 buckets.
- `sync_mega_staging.py` (Mac) — pulls staging from Windows, uploads each scene's Description/ via `s4_client.put_object`, marks `has_description=True` in mega_scan.json, deploys back. Cron `*/2 * * * *`.
- `mega_scan_worker.py` is **deleted** in Phase 5 decom — no longer needed since S4 listing runs from anywhere. The hub's "Refresh MEGA" button now hits a FastAPI route that runs scan logic directly.

## Thumbnail proxy
`/api/scenes/{id}/thumbnail` calls `s4_client.get_object` into the existing
`thumb_cache/` (7-day Cache-Control). Don't switch to 302-redirect-to-presigned
— per-request URL changes break browser caching.

## Empty shell folders
Legacy MEGA pre-provisioned scene subfolders (Videos/, Photos/, …) before
upload. S4 doesn't have folder objects, but the migration preserved 0-byte
trailing-slash markers (`VRH0001/`, `VRH0001/Description/`). `scan_mega.py`
filters those out (`obj.size == 0 and key.endswith("/")`). `has_*` flags
require an actual file, not a marker.

## Drive→S4 backfill
`migrate_drive_to_s4.py` mirrors a Google Drive folder into a studio bucket
via the existing `service_account.json` (Drive API must be enabled in GCP
project 447656112292; folder shared with `roster-updater@model-roster-updater.iam.gserviceaccount.com`).
Idempotent (HEAD + size check), thread-local Drive clients (httplib2 isn't
thread-safe), TransferConfig caps multipart at 4 GB and retries on
`InvalidPart`/`NoSuchUpload` after aborting any lingering multipart upload.
