#!/usr/bin/env python3
"""
build_sequence.py

Scans a session audio folder and generates a Premiere Pro XML (XMEML) file
that imports cleanly via File > Import in Premiere Pro.

Track layout:
  A1  →  Tr1_2_PATCHED.WAV  (falls back to Tr1_2.WAV if no patched file exists)
  A2  →  TrL_R.WAV

All takes are placed full-duration in order with no gaps.
You do the Action/Cut trims in Premiere as usual.

Usage:
    python3 build_sequence.py /path/to/session/Audio
    python3 build_sequence.py /path/to/session
    python3 build_sequence.py /path/to/session --out MyScene.xml
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import soundfile as sf


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uid(path: Path) -> str:
    return hashlib.md5(str(path).encode()).hexdigest()


def _find_audio(take_dir: Path, prefix: str):
    # Always use original Tr1_2 — edits are encoded in the XMEML, not baked in
    raw  = take_dir / f"{prefix}_Tr1_2.WAV"
    trlr = take_dir / f"{prefix}_TrL_R.WAV"
    return (raw if raw.exists() else None), (trlr if trlr.exists() else None)


def _load_patches_meta(take_dir: Path, prefix: str) -> dict:
    """Load full patches sidecar JSON."""
    p = take_dir / f"{prefix}_patches.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def find_takes(root: Path):
    takes = []
    for take_dir in sorted(root.glob("*.TAKE")):
        if not take_dir.is_dir():
            continue
        wavs = list(take_dir.glob("*_Tr4.WAV"))
        if not wavs:
            continue
        prefix = wavs[0].name[: -len("_Tr4.WAV")]
        main, trlr = _find_audio(take_dir, prefix)
        if main is None:
            print(f"  WARNING: no Tr1_2 audio in {take_dir.name} — skipping")
            continue
        meta = _load_patches_meta(take_dir, prefix)
        takes.append({
            "prefix": prefix, "dir": take_dir, "main": main, "trlr": trlr,
            "patches": meta.get("regions", []),
            "patches_meta": meta,
        })
    return takes


# ── XMEML builder ─────────────────────────────────────────────────────────────

def _file_elem(path: Path, file_id: str, frames: int, sr: int, channels: int) -> str:
    url = path.as_uri()
    return f"""        <file id="{file_id}">
          <name>{escape(path.name)}</name>
          <pathurl>{escape(url)}</pathurl>
          <rate>
            <timebase>{sr}</timebase>
            <ntsc>FALSE</ntsc>
          </rate>
          <duration>{frames}</duration>
          <media>
            <audio>
              <samplecharacteristics>
                <depth>24</depth>
                <samplerate>{sr}</samplerate>
              </samplecharacteristics>
              <channelcount>{channels}</channelcount>
            </audio>
          </media>
        </file>"""


def _clip_from_source(clip_id: str, file_id: str, name: str,
                      tl_start: int, tl_end: int,
                      src_in: int, src_out: int,
                      file_frames: int, sr: int, track_index: int,
                      emit_file: bool, path: Path, channels: int) -> str:
    """Build a clipitem. Stereo files omit sourcetrack so Premiere uses all channels."""
    file_block = (_file_elem(path, file_id, file_frames, sr, channels)
                  if emit_file else f'        <file id="{file_id}"/>')
    src_track = ("" if channels >= 2 else
                 f"        <sourcetrack>\n"
                 f"          <mediatype>audio</mediatype>\n"
                 f"          <trackindex>{track_index}</trackindex>\n"
                 f"        </sourcetrack>\n")
    return f"""      <clipitem id="{clip_id}">
        <name>{escape(name)}</name>
        <duration>{file_frames}</duration>
        <rate>
          <timebase>{sr}</timebase>
          <ntsc>FALSE</ntsc>
        </rate>
        <start>{tl_start}</start>
        <end>{tl_end}</end>
        <in>{src_in}</in>
        <out>{src_out}</out>
{file_block}
{src_track}      </clipitem>"""


def build_xmeml(takes: list, sequence_name: str) -> str:
    """
    Track layout:
      A1  — original Tr1_2.WAV, one stereo clip per take
      A2  — TrL_R.WAV, one stereo clip per take
      A3  — donor fill clips at director speech regions
      A4  — Tr4.WAV mono QC track
    Sequence markers at every detected region (yellow=clean, red=warn).
    """
    sr = 48000
    file_seen = set()
    clips_a1  = []
    clips_a2  = []
    clips_a3  = []
    clips_a4  = []
    markers   = []
    tl_offset = 0

    for t in takes:
        src_path    = t["main"]
        info        = sf.info(str(src_path))
        file_frames = info.frames
        fid         = f"file_{_uid(src_path)}"
        tl_start    = tl_offset
        tl_end      = tl_offset + file_frames

        # A1: full original Tr1_2 stereo clip
        clips_a1.append(_clip_from_source(
            clip_id=f"clip_a1_{t['prefix']}", file_id=fid,
            name=src_path.name,
            tl_start=tl_start, tl_end=tl_end,
            src_in=0, src_out=file_frames,
            file_frames=file_frames, sr=sr, track_index=1,
            emit_file=fid not in file_seen,
            path=src_path, channels=info.channels,
        ))
        file_seen.add(fid)

        # A2: TrL_R stereo clip
        if t["trlr"] is not None:
            trlr_info = sf.info(str(t["trlr"]))
            trlr_fid  = f"file_{_uid(t['trlr'])}"
            use_len   = min(trlr_info.frames, file_frames)
            clips_a2.append(_clip_from_source(
                clip_id=f"clip_a2_{t['prefix']}", file_id=trlr_fid,
                name=t["trlr"].name,
                tl_start=tl_start, tl_end=tl_start + use_len,
                src_in=0, src_out=use_len,
                file_frames=trlr_info.frames, sr=sr, track_index=1,
                emit_file=trlr_fid not in file_seen,
                path=t["trlr"], channels=trlr_info.channels,
            ))
            file_seen.add(trlr_fid)

        # A4: Tr4 mono QC track
        tr4_path = t["dir"] / f"{t['prefix']}_Tr4.WAV"
        if tr4_path.exists():
            tr4_info = sf.info(str(tr4_path))
            tr4_fid  = f"file_{_uid(tr4_path)}"
            tr4_len  = min(tr4_info.frames, file_frames)
            clips_a4.append(_clip_from_source(
                clip_id=f"clip_tr4_{t['prefix']}", file_id=tr4_fid,
                name=tr4_path.name + " [QC]",
                tl_start=tl_start, tl_end=tl_start + tr4_len,
                src_in=0, src_out=tr4_len,
                file_frames=tr4_info.frames, sr=sr, track_index=1,
                emit_file=tr4_fid not in file_seen,
                path=tr4_path, channels=tr4_info.channels,
            ))
            file_seen.add(tr4_fid)

        # A3: fill clips + markers
        for i, region in enumerate(t.get("patches", [])):
            gap_s  = region["start_samp"]
            gap_e  = region["end_samp"]
            status = region.get("status", "CLEAN")

            color = 2 if status == "CLEAN" else 0
            label = f"DIR {gap_s/sr:.1f}s" + (" WARN" if status != "CLEAN" else "")
            markers.append(f"""    <marker>
      <name>{escape(label)}</name>
      <comment>{escape(t['prefix'])}</comment>
      <in>{tl_start + gap_s}</in>
      <out>{tl_start + gap_e}</out>
      <color>{color}</color>
    </marker>""")

            fill_tl = tl_start + gap_s
            for d_idx, donor in enumerate(region.get("donors", [])):
                d_file  = Path(donor["file"])
                d_fid   = f"file_{_uid(d_file)}"
                d_info  = sf.info(str(d_file))
                d_in    = donor["start"]
                d_out   = min(donor["end"], d_info.frames)
                d_len   = d_out - d_in
                if d_len <= 0:
                    continue
                remaining = (tl_start + gap_e) - fill_tl
                use_len   = min(d_len, remaining)
                if use_len <= 0:
                    break
                clips_a3.append(_clip_from_source(
                    clip_id=f"clip_a3_{t['prefix']}_{i}_{d_idx}",
                    file_id=d_fid,
                    name=d_file.name + " [fill]",
                    tl_start=fill_tl, tl_end=fill_tl + use_len,
                    src_in=d_in, src_out=d_in + use_len,
                    file_frames=d_info.frames, sr=sr, track_index=1,
                    emit_file=d_fid not in file_seen,
                    path=d_file, channels=d_info.channels,
                ))
                file_seen.add(d_fid)
                fill_tl += use_len

        tl_offset = tl_end

    total = tl_offset

    def _track(clips):
        return "    <track>\n" + "\n".join(clips) + "\n    </track>"

    tracks = _track(clips_a1)
    if clips_a2:
        tracks += "\n" + _track(clips_a2)
    if clips_a3:
        tracks += "\n" + _track(clips_a3)
    if clips_a4:
        tracks += "\n" + _track(clips_a4)

    markers_xml = "\n".join(markers)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
  <sequence>
    <name>{escape(sequence_name)}</name>
    <duration>{total}</duration>
    <rate>
      <timebase>{sr}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
{markers_xml}
    <media>
      <audio>
        <numOutputChannels>2</numOutputChannels>
{tracks}
      </audio>
    </media>
  </sequence>
</xmeml>
"""
    return xml


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate Premiere Pro XML audio assembly from session TAKE folders."
    )
    parser.add_argument("path", help="Session folder (or Audio subfolder) containing .TAKE dirs")
    parser.add_argument("--out",  default=None, help="Output .xml path")
    parser.add_argument("--name", default=None, help="Sequence name")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}")
        sys.exit(1)

    # Support both session/Audio/*.TAKE and session/*.TAKE layouts
    has_takes = any(root.glob("*.TAKE"))
    if not has_takes:
        audio_sub = root / "Audio"
        if audio_sub.is_dir() and any(audio_sub.glob("*.TAKE")):
            root = audio_sub
            has_takes = True

    if not has_takes:
        print(f"No .TAKE folders found under: {root}")
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
        seq_name = args.name or out_path.stem
    else:
        # Write next to (or inside) the session folder
        session_dir = root if any(root.glob("*.TAKE")) else root.parent
        # If TAKE folders are directly in root, write inside; otherwise next to Audio/
        if any(root.glob("*.TAKE")) and root.name != "Audio":
            session_dir = root
        else:
            session_dir = root.parent
        seq_name = args.name or session_dir.name
        out_path = session_dir / f"{seq_name}.xml"

    print(f"Scanning: {root}")
    takes = find_takes(root)
    if not takes:
        print("No takes found.")
        sys.exit(1)

    print(f"Found {len(takes)} take(s):")
    for t in takes:
        trlr = t["trlr"].name if t["trlr"] else "—"
        patched = "PATCHED" if "PATCHED" in t["main"].name else "RAW"
        print(f"  {t['prefix']}   A1={patched}   A2={trlr}")

    xml = build_xmeml(takes, seq_name)
    out_path.write_text(xml, encoding="utf-8")
    print(f"\nWrote: {out_path}")
    print(f"Premiere: File > Import > {out_path.name}")


if __name__ == "__main__":
    main()
