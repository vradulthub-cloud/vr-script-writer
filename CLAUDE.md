# Eclatech Hub — Project Instructions

## Ticketing System Integration (MANDATORY)

Every conversation that touches code in this repo MUST interact with the ticketing system.

### At the start of any coding session:
```bash
cd /Users/andrewninn/Scripts && python3 -c "
import ticket_tools as t
for tk in t.load_tickets():
    if tk['status'] not in ('Closed', 'Rejected'):
        print(f'{tk[\"id\"]}  {tk[\"status\"]:12s}  {tk[\"priority\"]:8s}  {tk[\"title\"]}')
"
```
Check if any open tickets relate to the work being done.

### After completing a fix or feature:
```bash
cd /Users/andrewninn/Scripts && python3 -c "
import ticket_tools as t
t.resolve_ticket('TKT-XXXX', status='In Review', notes='Brief description of what was fixed')
"
```
This moves the ticket to "In Review" so the team can verify. Do this for EVERY ticket addressed by the work.

### Important: ticket_tools.py lives at `/Users/andrewninn/Scripts/ticket_tools.py`
You MUST `cd /Users/andrewninn/Scripts` before importing it, or use `sys.path.insert(0, '/Users/andrewninn/Scripts')`. The service_account.json for Google Sheets auth is in the same directory.

### Key functions:
- `ticket_tools.load_tickets()` — get all tickets
- `ticket_tools.get_open_tickets()` — get active tickets only
- `ticket_tools.resolve_ticket(id, status, notes)` — update a ticket after fixing it
- `ticket_tools.resolve_tickets([ids], status, notes)` — batch update
- `ticket_tools.create_ticket(...)` — create a new ticket if you discover an issue

---

## Infrastructure

### Windows PC (Production Server)
- **IP:** `100.90.90.68` (Tailscale)
- **SSH:** `ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68`
- **App path:** `C:\Users\andre\eclatech-hub\`
- **Service:** `EclatechHub` (NSSM), port 8501
- **URL:** `https://desktop-9d407v9.tail3f755a.ts.net/`
- **Python:** 3.11 — NO backslashes inside f-string expressions, pre-build HTML as variables
- **Streamlit:** 1.55.0 — `use_container_width` deprecated, use `width='stretch'`
- **NSSM:** `C:\Users\andre\nssm\nssm-2.24\win32\nssm.exe`
- **Logs:** `C:\Users\andre\eclatech-hub\nssm_stdout.log`, `nssm_stderr.log`
- **GPU:** RTX 3080 Ti 12GB (ComfyUI, LoRA training)

### Deploy Process
```bash
scp -i ~/.ssh/id_ed25519_win <files> andre@100.90.90.68:"C:/Users/andre/eclatech-hub/"
ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68 "net stop EclatechHub && net start EclatechHub"
```
Always check `nssm_stdout.log` for errors after deploy:
```bash
ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68 "powershell -Command \"Get-Content 'C:\\Users\\andre\\eclatech-hub\\nssm_stdout.log' -Tail 20\""
```

### Ollama (Windows)
MCP server `mcp__ollama-windows` connects directly — use `ollama_generate`, `ollama_chat`, `ollama_list` etc. Fallback: `ssh ... "ollama run llama3 'prompt'"`.

---

## Team & Auth

### Employees (7 people)
| Name | Email | Role | Tabs |
|------|-------|------|------|
| Drew | andrewninn@gmail.com | admin | ALL |
| Drew | andrewrowe72@gmail.com | admin | ALL |
| David | vradulthub@gmail.com | admin | ALL |
| Duc | volemanhduc@gmail.com | editor | ALL |
| Isaac | ibjessup@gmail.com | admin | ALL |
| Flo | f.kaute@gmail.com | editor | Missing, Model Research, Tickets, Titles |
| Tam | thanhtam512@gmail.com | editor | Missing, Tickets, Descriptions |

### Permission Notes
- **Grail writes (title/cats/tags):** Drew, David, Duc only
- **User management:** Drew, David only

### Auth System
- Streamlit native OIDC (st.login/st.user) with Google OAuth
- GCP Project: `model-roster-updater` (447656112292)
- Users sheet in Tickets Google Sheet controls access — `admin` = all tabs + ticket management, `editor` = listed tabs only
- OAuth creds in `.streamlit/secrets.toml`
- All employee emails must be GCP test users (consent screen in Testing mode)

---

## Google Sheets

| Sheet | ID | Tabs |
|-------|----|------|
| Scripts | `1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ` | Monthly: "January 2026", etc. |
| Grail | `1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk` | FPVR, VRH, VRA, NNJOI |
| Tickets | `1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA` | Sheet1 (tickets), Users (auth) |
| Budgets | `1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc` | Monthly tabs |
| Booking | `1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw` | Agency tabs |
| Comp Planning | `1i6W4eZ8Bva3HvVmhpAVgjeHwfqbARkwBZ38aUhriaGs` | FPVR/VRH/VRA Compilations |

Service account: `service_account.json` in eclatech-hub dir.

### Scripts Sheet Columns (0-indexed)
A=Date, B=Studio, C=Location, D=Scene, E=Female, F=Male, G=Theme, H=WardrobeF, I=WardrobeM, J=Plot, K=Title, L=Props, M=Status

### Grail Columns
A=SiteCode, B=SceneID, C=ReleaseDate, D=Title, E=Performers, F=Categories, G=Tags

### Studio Name Mapping (CRITICAL — different everywhere)
| Context | FPVR | VRH | VRA | NJOI |
|---------|------|-----|-----|------|
| App UI | FuckPassVR | VRHush | VRAllure | NaughtyJOI |
| Scripts Sheet | FuckPassVR | VRHush | VRAllure | NaughtyJOI |
| Grail Tabs | FPVR | VRH | VRA | NNJOI |
| MEGA Folders | Grail/FPVR | Grail/VRH | Grail/VRA | Grail/NNJOI |
| Site Codes | fpvr | vrh | vra | njoi |

---

## MEGA

- **Mac rclone remote:** `mega_test`
- **Windows rclone:** `C:\Users\andre\rclone.exe`, remote `mega`
- **MEGAcmd (Windows):** `C:\Users\andre\AppData\Local\MEGAcmd\`
- **Main path:** `mega:/Grail/{STUDIO}/{ID}/` (newer scenes)
- **Backup path:** `mega:/Grail/Backup/{STUDIO}/{ID}/` (older scenes)
- **Scene folder structure:** Videos/, Storyboard/, Photos/, Legal/, Description/, Video Thumbnail/
- **Scan:** `scan_mega.py` (Mac) → `mega_scan.json` → SCP'd to Windows
- **Sync:** `sync_mega_staging.py` — pulls staging from Windows, uploads to MEGA, cron `*/2 * * * *`
- **rclone MEGA bug:** "Entry doesn't belong in directory (too short)" drops files from Video Thumbnail/ — scan_mega.py has directory-existence fallback

---

## Key App Features

### Current Tabs (in order)
1. Missing — QA dashboard with MEGA asset tracking + Create MEGA Folder
2. Model Research — performer lookup with booking sheet integration
3. Scripts — script generation with auto-title
4. Call Sheets — Google Drive call sheet creation
5. Titles — Cloud (Ideogram V3 via fal.ai) + Local (PIL) title card generation
6. Descriptions — full description generator with inline editing, approved cats/tags
7. Compilations — AI comp ideas, scene selection, save to planning sheet + Grail
8. Tickets — Asset Tracker, Approvals, Tickets dashboard, Submit

### Ticket Pipeline
New → Approved → In Progress → In Review → Closed (or Rejected at any point)
- QC Feedback: anyone can mark active tickets "Fixed" or "Still Broken"
- Admin quick approve/reject for New tickets
- Status transitions are guarded to valid next states only
- Timestamped notes: `[2026-04-08 14:30 Drew] Note text`

### Asset Tracker
- Joins Grail + Scripts + MEGA scan + Approvals into per-scene status
- 7 tracked assets: title, description, categories, tags, videos, thumbnail, photos
- Compilation detection: "Vol." in title OR 4+ performers
- Parallel Grail tab reads via ThreadPoolExecutor

### Performance / Caching
- `@st.cache_data(ttl=1800)` for global caching (shared across all sessions, 30 min)
- Module-level caches in asset_tracker.py: Scripts (10 min), MEGA scan (1 hour)
- Refresh buttons call `.clear()` on cached functions
- Parallel API calls where possible

### Description Workflow
- Per-studio system prompts (FPVR=2 paragraphs 350-400 words, VRH=single punchy, VRA=intimate, NJOI=JOI)
- Scene prompt with: Title, Model, Plot, Categories, Model Properties, Sex Positions, Keywords
- Inline paragraph editing after generation
- SEO: Meta Title + Meta Description (160 chars)
- POV rule: male talent IS "you" — never referred to by name

### Compilations
- Backend: `comp_tools.py` — Grail/sheet reads, AI generation, MEGA paths
- Photoset builder: `comp_photoset.py` (Mac-only, watermarks with studio logos)
- Logos: `comp_logos/` — FPVR.png, VRH.png, VRA.png (NJOI.png still missing)
- DISABLED: cats/tags writing to Grail, MEGA description saves (user fills manually)

---

## Audio Post-Production

### Director Voice Removal
- Script: `patch_director_voice.py`
- Zoom F6 recording: Tr1_2 (stereo room), Tr4 (director PTT), TrL_R (secondary)
- Stage 1: silero-VAD on Tr4 detects director speech
- Stage 2: Spectral fingerprint scan on Tr1_2 catches bleed
- Fill: copy-paste from clean sections of same session (not synthetic)
- Output: `_PATCHED.WAV` per take, originals never modified

---

## ComfyUI + LoRA (GPU tasks)

- ComfyUI at `E:\ComfyUI`, port 8188, manual launch required
- FLUX.1 Schnell Q8 GGUF + ControlNet Canny v3
- LoRA training: Kohya SS at `E:\kohya_ss`, MUST launch from Windows desktop (SSH kills it)
- Use Task Scheduler + log-to-Dropbox pattern for remote training launches
- DO NOT run ComfyUI while training — shared GPU VRAM

---

## IMPORTANT: Do Not Run App Code on Mac
The Streamlit app runs on Windows. Do NOT try to import or test app modules on the Mac.
- **NEVER run:** `asset_tracker.py`, `hub_ui.py`, `script_writer_app.py`, `scan_mega.py`, `approval_tools.py` on Mac
- **OK to run on Mac:** `ticket_tools.py` (for checking/updating tickets only)
- If something breaks, check the Windows logs via SSH, don't try to reproduce locally
- `mega_scan.json` on Mac may be stale — the live copy is on Windows

---

## Windows SSH Lessons (DO NOT REPEAT)
- `Start-Process -WindowStyle Hidden` via SSH DOES NOT work — process dies on disconnect
- `start /b` via SSH DOES NOT work — same problem
- ONLY reliable method: `launch_training.ps1` using ProcessStartInfo + WaitForExit via `Register-ScheduledTask`
- Training logs MUST go to Dropbox so Mac can monitor without SSH
- SSH on Windows kills child processes on disconnect — always use Task Scheduler

---

## References

- **Shoot Budgets:** `1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc` — use F1 Agency column (col I) to verify model's current agency
- **Local budget files:** `/Users/andrewninn/Scripts/shoot_budgets/` (2021-2026 xlsx)
- **VRPorn data:** SLR and VRPorn are same revenue stream. Per-studio xlsx files at `/Users/andrewninn/Documents/drive-download-20260317T015637Z-3-001/`
