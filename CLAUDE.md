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

---

## Design Context

### Users
Small internal team of 7 (3 admins, 3 editors) managing video production workflows for 4 adult content studios. Used daily, in-depth — not casual browsing. Users are comfortable with dense UIs and need speed over hand-holding. Context is typically a desktop browser in a work setting. Power users who will notice inconsistencies.

### Brand Personality
**Three words:** precise · cinematic · backstage

The tool lives behind the scenes of a production operation. It should feel like the equipment rack in a film studio — purposeful, authoritative, no wasted space. Not glamorous, not grim — just completely in control.

### Aesthetic Direction
- **Theme:** Dark, always. Not "dark mode as a preference" — dark as the primary reality of this interface.
- **Reference feel:** Linear, Raycast, Vercel Dashboard — confident use of dark surfaces, restrained accent use, excellent information density
- **Color system:** Keep lime green (`#bed62f`) as the sole primary action color. Keep studio identity colors (FPVR blue `#3b82f6`, VRH purple `#8b5cf6`, VRA pink `#ec4899`, NJOI orange `#f97316`) as contextual anchors — they should dominate when in a studio context.
- **Typography evolution:** Syne and DM Sans are approved to replace on new work. Prefer a high-contrast grotesque display face (e.g., Basement Grotesque, Cabinet Grotesk, Clash Display, Neue Montreal) for headings. Body: General Sans, Geist, or Switzer. DM Mono is fine to keep for code/monospace contexts.
- **Anti-references:** NO purple/cyan gradient combos, NO gradient text, NO glowing card borders, NO AI startup aesthetic. NO gray enterprise table grids, NO blue primary buttons, NO sidebar-with-accordion nav.

### Design Principles
1. **Information density first.** This is a pro tool used all day. Prioritize fitting more on screen over breathing room. Tight line-height, compact spacing, minimal chrome.
2. **Studio color owns its context.** When working in FPVR, blue is the dominant accent. When in VRH, purple leads. Lime green recedes to action-only use (submit, save, approve, CTA).
3. **Lime green means "this commits something."** Any button or chip tinted lime must perform a write on click — Save, Apply, Approve, Start, Submit, Find, Undo, Generate. Active-nav fill also uses lime at ≤12% mix because "you are here" is itself navigational state. Non-committing affordances (Edit, Cancel, filter toggles, Refresh, Preview) must be neutral outlined buttons. If you want lime for emphasis, don't — use font weight instead.
4. **Weight and size carry hierarchy — not color.** Use font weight (400→700) and size steps aggressively. Reserve color for status and identity, not emphasis.
5. **Nothing decorates.** Every visual element must communicate something: status, identity, hierarchy, or interactivity. Purely decorative elements (dividers, background patterns, ambient glow) are banned unless they orient the user.
