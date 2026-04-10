---
paths:
  - "cta_generator.py"
  - "cta_learn.py"
  - "style_scout.py"
  - "comp_tools.py"
  - "comp_photoset.py"
---

# ComfyUI, LoRA & Image Generation Rules

## ComfyUI
- Location: `E:\ComfyUI`, port 8188, manual launch required
- FLUX.1 Schnell Q8 GGUF + ControlNet Canny v3

## LoRA Training
- Kohya SS at `E:\kohya_ss`
- MUST launch from Windows desktop (SSH kills it)
- Use Task Scheduler + log-to-Dropbox pattern for remote training launches
- DO NOT run ComfyUI while training — shared GPU VRAM (RTX 3080 Ti 12GB)

## CTA Title Generator
- 25 visually distinct treatments in cta_generator.py
- LLM-powered routing via learned_routes.json (built by cta_learn.py)
- Fonts auto-discovered from macOS/Linux system; missing fonts downloaded on demand

## Compilations
- Backend: `comp_tools.py` — Grail/sheet reads, AI generation, MEGA paths
- Photoset builder: `comp_photoset.py` (Mac-only, watermarks with studio logos)
- Logos: `comp_logos/` — FPVR.png, VRH.png, VRA.png (NJOI.png still missing)
- DISABLED: cats/tags writing to Grail, MEGA description saves (user fills manually)
