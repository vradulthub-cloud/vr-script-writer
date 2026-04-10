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

### Key functions:
- `ticket_tools.load_tickets()` — get all tickets
- `ticket_tools.get_open_tickets()` — get active tickets only
- `ticket_tools.resolve_ticket(id, status, notes)` — update a ticket after fixing it
- `ticket_tools.resolve_tickets([ids], status, notes)` — batch update
- `ticket_tools.create_ticket(...)` — create a new ticket if you discover an issue

ticket_tools.py lives at `/Users/andrewninn/Scripts/ticket_tools.py`. You MUST `cd /Users/andrewninn/Scripts` before importing it.

---

## Infrastructure

### Windows PC (Production Server)
- **IP:** `100.90.90.68` (Tailscale)
- **SSH:** `ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68`
- **App path:** `C:\Users\andre\eclatech-hub\`
- **Service:** `EclatechHub` (NSSM), port 8501
- **URL:** `https://desktop-9d407v9.tail3f755a.ts.net/`

### Deploy Process
```bash
scp -i ~/.ssh/id_ed25519_win <files> andre@100.90.90.68:"C:/Users/andre/eclatech-hub/"
ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68 "net stop EclatechHub && net start EclatechHub"
```
Always check logs after deploy:
```bash
ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68 "powershell -Command \"Get-Content 'C:\\Users\\andre\\eclatech-hub\\nssm_stdout.log' -Tail 20\""
```

### Ollama (Windows)
MCP server `mcp__ollama-windows` connects directly. Fallback: `ssh ... "ollama run llama3 'prompt'"`.

---

## IMPORTANT: Do Not Run App Code on Mac
The Streamlit app runs on Windows. Do NOT try to import or test app modules on the Mac.
- **NEVER run:** `asset_tracker.py`, `hub_ui.py`, `script_writer_app.py`, `scan_mega.py`, `approval_tools.py` on Mac
- **OK to run on Mac:** `ticket_tools.py` (for checking/updating tickets only)
- If something breaks, check the Windows logs via SSH, don't try to reproduce locally

---

## Studio Name Mapping (CRITICAL — different everywhere)
| Context | FPVR | VRH | VRA | NJOI |
|---------|------|-----|-----|------|
| App UI | FuckPassVR | VRHush | VRAllure | NaughtyJOI |
| Scripts Sheet | FuckPassVR | VRHush | VRAllure | NaughtyJOI |
| Grail Tabs | FPVR | VRH | VRA | NNJOI |
| MEGA Folders | Grail/FPVR | Grail/VRH | Grail/VRA | Grail/NNJOI |
| Site Codes | fpvr | vrh | vra | njoi |

---

## Domain-Specific Rules
Detailed rules for each subsystem are in `.claude/rules/`:
- `hub-app.md` — Streamlit app, auth, caching, Python 3.11 gotchas
- `sheets.md` — Google Sheets IDs, column mappings, service account
- `mega.md` — MEGA storage paths, rclone, scan/sync
- `audio.md` — Director voice removal, WAV handling
- `comfyui.md` — Image generation, LoRA training, CTA titles, compilations
- `windows-ssh.md` — SSH lessons learned (process lifecycle gotchas)

These load automatically when you work on matching files.
