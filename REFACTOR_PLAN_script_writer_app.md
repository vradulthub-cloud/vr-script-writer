# Refactor Plan: script_writer_app.py (5,784 lines)

**Run this refactor in Claude Code on the Windows machine** — this file is the Streamlit app and must be tested on Windows where it actually runs.

## Current Structure

```
Lines 1-12:     Imports
Lines 13-160:   _refine_treatment() — title card refinement helper
Lines 161-349:  Title generation helpers (_generate_title, _write_title_to_grail, etc.)
Lines 350-496:  Design system constants, cached data loaders, ticket helpers
Lines 414-496:  Auth gate, notifications, header
Lines 497-643:  Slop phrase substitutions, description config, URL helpers
Lines 644-1050: System prompts (per-studio), description parsing, scene prompt builder
Lines 1051-1070: Main tab routing
Lines 1071-2082: TAB 1 — Scripts (manual + from sheet, single + batch)
Lines 2083-2172: TAB 3 — Call Sheets
Lines 2173-2477: TAB 4 — Titles
Lines 2478-3120: TAB 5 — Model Research
Lines 3121-3830: TAB 6 — Description Generator
Lines 3831-4253: TAB 7 — Compilations
Lines 4254-5784: TAB 8 — Tickets (Asset Tracker + Approvals + Tickets + Submit)
```

## Recommended Split: 4 files

### 1. `hub_shared.py` (~700 lines)
Extract the shared infrastructure that all tabs use:
- Design system constants (line 350+)
- Cached data loaders (_cached_load_assets, _cached_load_approvals, _cached_load_tickets)
- Ticket linking helpers (_ticket_linker, _ticket_progress)
- Auth gate function
- Notification functions (_cached_unread_count, _cached_notifications)
- Header rendering
- Slop phrase substitutions

### 2. `hub_descriptions.py` (~800 lines)
Extract description-related logic used by both Missing tab and Description tab:
- Description config (APPROVED_CATS, APPROVED_TAGS, etc.)
- Category/tag URL helpers (_cat_slug, _category_url, _tag_url, _cats_as_html, _tags_as_html)
- Per-studio system prompts (the big string constants)
- Compilation system prompts
- _is_compilation, _parse_desc_output, _reassemble_desc
- _build_scene_prompt

### 3. `hub_titles.py` (~300 lines)
Extract title generation logic:
- _refine_treatment
- _generate_title
- _write_title_to_grail, _write_grail_cell
- _write_title_to_scripts_sheet
- _list_ollama_models
- _checkerboard_bg

### 4. `script_writer_app.py` (~3,900 lines — the 8 tab implementations)
Keep the main app file with:
- Imports from hub_shared, hub_descriptions, hub_titles
- Main tab routing
- All 8 tab implementations (these share too much Streamlit session state to easily split further)

## How to Execute

1. `git checkout -b refactor-swa-split` (create a branch)
2. Create `hub_shared.py` — extract shared infrastructure
3. Create `hub_descriptions.py` — extract description logic  
4. Create `hub_titles.py` — extract title helpers
5. Update `script_writer_app.py` to import from new files
6. Test on Windows: `streamlit run script_writer_app.py`
7. Check all 8 tabs load and function correctly
8. Commit and merge when verified

## Important Notes
- All files use `@st.cache_data` — make sure `import streamlit as st` is in each file
- The description system prompts are long string constants — they'll move cleanly
- Session state (st.session_state) is global — tabs can still access it from the main file
- The _refine_treatment function imports cta_generator lazily — that still works
