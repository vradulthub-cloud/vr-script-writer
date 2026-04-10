---
paths:
  - "patch_director_voice.py"
  - "audio_post/*"
  - "build_sequence.py"
  - "extract_gt_segments.py"
---

# Audio Post-Production Rules

## Director Voice Removal
- Script: `patch_director_voice.py`
- Zoom F6 recording: Tr1_2 (stereo room), Tr4 (director PTT), TrL_R (secondary)
- Stage 1: silero-VAD on Tr4 detects director speech
- Stage 2: Spectral fingerprint scan on Tr1_2 catches bleed
- Fill: copy-paste from clean sections of same session (not synthetic)
- Output: `_PATCHED.WAV` per take, originals never modified
- NEVER modify original WAV files
