# Director Voice Removal — Audio Workflow

## What This Is

VR adult film productions record audio on a Zoom F6 field recorder during shooting.
The director speaks to the performers during takes — giving direction, calling action/cut,
and sometimes talking while the camera is rolling. This voice bleeds into the stereo
room microphone and must be completely removed before delivery.

## Recording Setup

| Track | Source | Purpose |
|-------|--------|---------|
| Tr1_2 | Stereo room mic (main) | Primary deliverable audio |
| Tr4   | Push-to-talk mic (director) | Reference for detection only |
| TrL_R | Secondary mic | Supporting audio track |

The F6 writes one `.TAKE` folder per take. Each folder contains the track WAV files
named `YYMMDD_NNN_TrackName.WAV`.

## The Problem

1. **Direct speech on Tr4** — Director presses PTT and speaks. This is always present
   when he gives direction, calls action, or calls cut.
2. **Bleed on Tr1_2** — His voice physically bleeds into the room mic even without PTT.
   This is harder to catch and is the most damaging if missed.

## The Solution: `patch_director_voice.py`

Two-stage detection + copy-paste fill from the same session audio.

### Stage 1 — VAD on Tr4
silero-VAD detects all speech regions on the push-to-talk mic.
These are definitive director speech moments.

### Stage 2 — Spectral bleed scan on Tr1_2
Builds a spectral fingerprint of the director's voice from the Tr4 VAD regions,
then slides that fingerprint over Tr1_2 using cosine similarity to catch bleed
that wasn't picked up by Tr4 (director talking without pressing PTT).

### Fill method — Copy-paste donor
Detected regions are replaced with audio borrowed from clean sections of the same
session. Donor selection scores candidates on:
- RMS level match to surrounding context
- Waveform envelope shape match (visual continuity)
- Spectral brightness match
- Proximity to the gap (prefer nearby audio)

Same-take donors are always preferred. Cross-take donors from the same session
are used as fallback. This ensures the room character, ambient noise floor,
and mic coloration all match exactly — no synthetic fill.

A 10–50ms cosine crossfade is applied at each patch edge.

### Verification
After patching, each region is cross-correlated against Tr4 to confirm the
director's voice is no longer present. Regions that fail verification are flagged
for manual review.

## Running the Script

```bash
# Process a full session folder
python3 patch_director_voice.py /path/to/session/folder

# Process a single take
python3 patch_director_voice.py /path/to/260317_003.TAKE

# Dry run — detect only, no files written
python3 patch_director_voice.py --dry-run /path/to/session/folder

# Skip bleed scan (faster, Tr4 detections only)
python3 patch_director_voice.py --no-bleed /path/to/session/folder
```

## Output

Each processed take gets a `YYMMDD_NNN_Tr1_2_PATCHED.WAV` written into its `.TAKE` folder.
The original `Tr1_2.WAV` is never modified.

## Session Folder Layouts

The script handles two layouts automatically:

```
session/                          session/
  260317_001.TAKE/                  Audio/
  260317_002.TAKE/                    260317_001.TAKE/
  ...                                 260317_002.TAKE/
                                      ...
```

## Known Sessions Processed

| Session | Date | Takes | Total Patches |
|---------|------|-------|---------------|
| DellaCate-DannySteele (March) | 2026-03-17 | 11 | 116 |
| RiverLynn-DannySteele | 2026-03-18 | 5 | 68 |
| KimmyKim-MikeMancini (Feb) | 2026-02-10 | 8 | (pending) |

## Quality Bar

- Every patched region must verify clean (correlation with Tr4 below threshold)
- Patch seams should be inaudible — no clicks, level jumps, or tonal shifts
- Room character must match surrounding audio exactly
- If a take has zero VAD hits on Tr4, it is marked CLEAN and skipped

## What the Agent Should Do

When given a session path, the agent should:
1. Run `patch_director_voice.py` on the session
2. Report the summary (takes processed, regions patched, any warnings)
3. Flag any ⚠ WARN regions for human review
4. Confirm PATCHED files exist in each .TAKE folder before moving on

The agent should NOT modify, delete, or overwrite original WAV files.
The agent should NOT proceed to sequence building until all patches are verified clean.
