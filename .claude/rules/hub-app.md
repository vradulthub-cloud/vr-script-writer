---
paths:
  - "hub_ui.py"
  - "asset_tracker.py"
  - "script_writer_app.py"
  - "approval_tools.py"
  - "notification_tools.py"
  - "auth_config.py"
  - "script_writer.py"
  - "sheets_integration.py"
---

# Hub App Rules (Streamlit on Windows)

## CRITICAL: Do Not Run on Mac
These files run ONLY on the Windows production server. NEVER import or execute them on Mac.
- If something breaks, check Windows logs via SSH — don't try to reproduce locally
- OK to run on Mac: `ticket_tools.py` only

## Python 3.11 Gotchas
- NO backslashes inside f-string expressions — pre-build HTML as variables
- Example: `html = f"<div>{value}</div>"` not `f"<div>{d['key']}</div>"`

## Streamlit 1.55.0
- `use_container_width` is DEPRECATED — use `width='stretch'` instead
- `@st.cache_data(ttl=1800)` for global caching (shared across all sessions, 30 min)
- Module-level caches in asset_tracker.py: Scripts (10 min), MEGA scan (1 hour)
- Refresh buttons call `.clear()` on cached functions
- Parallel API calls via ThreadPoolExecutor where possible

## Auth System
- Streamlit native OIDC (st.login/st.user) with Google OAuth
- GCP Project: `model-roster-updater` (447656112292)
- Users sheet in Tickets Google Sheet controls access
- `admin` = all tabs + ticket management, `editor` = listed tabs only
- OAuth creds in `.streamlit/secrets.toml` — NEVER commit this
- All employee emails must be GCP test users (consent screen in Testing mode)

## Employees
| Name | Email | Role | Tabs |
|------|-------|------|------|
| Drew | andrewninn@gmail.com | admin | ALL |
| Drew | andrewrowe72@gmail.com | admin | ALL |
| David | vradulthub@gmail.com | admin | ALL |
| Duc | volemanhduc@gmail.com | editor | ALL |
| Isaac | ibjessup@gmail.com | admin | ALL |
| Flo | f.kaute@gmail.com | editor | Missing, Model Research, Tickets, Titles |
| Tam | thanhtam512@gmail.com | editor | Missing, Tickets, Descriptions |

## Permission Notes
- Grail writes (title/cats/tags): Drew, David, Duc only
- User management: Drew, David only

## Current Tabs (in order)
1. Missing — QA dashboard with MEGA asset tracking + Create MEGA Folder
2. Model Research — performer lookup with booking sheet integration
3. Scripts — script generation with auto-title
4. Call Sheets — Google Drive call sheet creation
5. Titles — Cloud (Ideogram V3 via fal.ai) + Local (PIL) title card generation
6. Descriptions — full description generator with inline editing
7. Compilations — AI comp ideas, scene selection, save to planning sheet + Grail
8. Tickets — Asset Tracker, Approvals, Tickets dashboard, Submit

## Ticket Pipeline
New → Approved → In Progress → In Review → Closed (or Rejected at any point)
- Status transitions are guarded to valid next states only
- Timestamped notes: `[2026-04-08 14:30 Drew] Note text`

## Description Workflow
- Per-studio system prompts (FPVR=2 paragraphs 350-400 words, VRH=single punchy, VRA=intimate, NJOI=JOI)
- POV rule: male talent IS "you" — never referred to by name
- SEO: Meta Title + Meta Description (160 chars)
