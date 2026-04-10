#!/usr/bin/env python3
"""
extract_gt_segments.py

Parse ground-truth Premiere XMLs (your manual edits) and extract:
  - Positive examples: the removed regions (director speech in room mic)
  - Negative examples: the kept regions (clean audio)

These replace VAD-guessed labels with your exact editorial decisions.

Usage:
    python3 extract_gt_segments.py <xml_or_folder> --audio-root <folder> --out <dataset_dir>
"""

import argparse
import json
import sys
from collections import defaultdict
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
import xml.etree.ElementTree as ET

SR_OUT       = 16000   # resample to 16kHz for WavLM
SEG_SEC      = 2.0     # segment length
HOP_SEC      = 1.0     # hop for negative sampling
MIN_GAP_SEC  = 0.4     # ignore removed regions shorter than this
NEG_RATIO    = 2.0     # negatives per positive segment
MAX_NEGS_PER_FILE = 200


def _resample(audio, sr_in, sr_out=SR_OUT):
    from scipy.signal import resample_poly
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    if sr_in == sr_out:
        return audio
    g = gcd(sr_in, sr_out)
    return resample_poly(audio, sr_out // g, sr_in // g).astype(np.float32)


def parse_xml(xml_path, min_gap_sec=MIN_GAP_SEC):
    """Return dict: wav_filename -> list of (start_sec, end_sec) removed regions."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    seq  = root.find('.//sequence')
    if seq is None:
        return {}

    tb   = int(seq.findtext('.//rate/timebase', '60'))
    ntsc = seq.findtext('.//rate/ntsc', '') == 'TRUE'
    fps  = tb / 1.001 if ntsc else float(tb)

    audio  = seq.find('media/audio')
    if audio is None:
        return {}

    file_ranges = defaultdict(list)
    for track in audio.findall('track'):
        for clip in track.findall('clipitem'):
            src_in  = int(clip.findtext('in',  '-1'))
            src_out = int(clip.findtext('out', '-1'))
            name    = clip.findtext('name', '')
            if src_in < 0 or src_out < 0 or not name.endswith('.WAV'):
                continue
            file_ranges[name].append((src_in, src_out))

    result = {}
    for fname, ranges in file_ranges.items():
        ranges.sort()
        merged = []
        for s, e in ranges:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append([s, e])

        gaps = []
        for i in range(len(merged) - 1):
            gs = merged[i][1] / fps
            ge = merged[i + 1][0] / fps
            if ge - gs >= min_gap_sec:
                gaps.append((gs, ge))
        if gaps:
            result[fname] = gaps
    return result


def find_wav(fname, audio_roots):
    """Search audio_roots recursively for fname."""
    for root in audio_roots:
        for p in Path(root).rglob(fname):
            return p
    return None


def extract_segments(wav_path, removed_regions, sr_out=SR_OUT,
                     seg_sec=SEG_SEC, hop_sec=HOP_SEC, neg_ratio=NEG_RATIO):
    """
    Returns:
        positives: list of (audio_array, label=1, src_info)
        negatives: list of (audio_array, label=0, src_info)
    """
    audio, sr = sf.read(str(wav_path), always_2d=True)
    mono = _resample(audio, sr, sr_out)
    total_sec = len(mono) / sr_out
    seg_samp  = int(seg_sec * sr_out)

    # Build positive mask (sample-level)
    pos_mask = np.zeros(len(mono), dtype=bool)
    for s, e in removed_regions:
        si = max(0, int(s * sr_out))
        ei = min(len(mono), int(e * sr_out))
        pos_mask[si:ei] = True

    positives, negatives = [], []

    # Extract positives: sliding window over removed regions
    for s, e in removed_regions:
        si = int(s * sr_out)
        ei = int(e * sr_out)
        for i in range(si, ei - seg_samp + 1, int(hop_sec * sr_out)):
            chunk = mono[i:i + seg_samp]
            if len(chunk) < seg_samp:
                break
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms < 1e-5:
                continue
            positives.append((chunk, 1, f"{wav_path.name}@{i/sr_out:.2f}s"))

    # Extract negatives: sliding window over clean regions
    hop_neg = int(hop_sec * sr_out)
    for i in range(0, len(mono) - seg_samp + 1, hop_neg):
        if pos_mask[i:i + seg_samp].any():
            continue
        chunk = mono[i:i + seg_samp]
        rms = np.sqrt(np.mean(chunk ** 2))
        if rms < 1e-5:
            continue
        negatives.append((chunk, 0, f"{wav_path.name}@{i/sr_out:.2f}s"))
        if len(negatives) >= int(len(positives) * neg_ratio * 2):
            break

    # Subsample negatives to neg_ratio × positives
    if negatives:
        rng = np.random.default_rng(42)
        n_neg = min(len(negatives), max(int(len(positives) * neg_ratio), 10))
        idx   = rng.choice(len(negatives), size=n_neg, replace=False)
        negatives = [negatives[i] for i in sorted(idx)]

    return positives, negatives


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+', help='XML files or folders containing XMLs')
    ap.add_argument('--audio-root', nargs='+', default=None,
                    help='Root folder(s) to search for WAV files (default: same as XML)')
    ap.add_argument('--out', default='gt_dataset', help='Output dataset directory')
    ap.add_argument('--seg-sec', type=float, default=SEG_SEC)
    ap.add_argument('--neg-ratio', type=float, default=NEG_RATIO)
    args = ap.parse_args()

    # Collect XML files
    xmls = []
    for inp in args.inputs:
        p = Path(inp)
        if p.is_dir():
            xmls.extend(p.rglob('*.xml'))
        elif p.suffix.lower() == '.xml':
            xmls.append(p)

    if not xmls:
        print("No XML files found.")
        sys.exit(1)

    out_dir  = Path(args.out)
    pos_dir  = out_dir / 'director'
    neg_dir  = out_dir / 'other'
    pos_dir.mkdir(parents=True, exist_ok=True)
    neg_dir.mkdir(parents=True, exist_ok=True)

    total_pos = total_neg = 0
    manifest = []

    for xml_path in sorted(xmls):
        print(f"\nParsing: {xml_path.name}")
        regions = parse_xml(xml_path)
        if not regions:
            print("  No cut regions found — skipping")
            continue

        audio_roots = [str(xml_path.parent)]
        if args.audio_root:
            audio_roots = args.audio_root + audio_roots

        for wav_name, removed in regions.items():
            wav_path = find_wav(wav_name, audio_roots)
            if wav_path is None:
                print(f"  WAV not found: {wav_name}")
                continue

            print(f"  {wav_name}: {len(removed)} director regions")
            try:
                pos, neg = extract_segments(wav_path, removed,
                                            seg_sec=args.seg_sec,
                                            neg_ratio=args.neg_ratio)
            except Exception as exc:
                print(f"    ERROR: {exc}")
                continue

            for audio, label, info in pos:
                fname = f"gt_{total_pos:05d}.wav"
                sf.write(str(pos_dir / fname), audio, SR_OUT)
                manifest.append({'file': fname, 'label': 1, 'src': info})
                total_pos += 1

            for audio, label, info in neg:
                fname = f"gt_{total_neg:05d}.wav"
                sf.write(str(neg_dir / fname), audio, SR_OUT)
                manifest.append({'file': fname, 'label': 0, 'src': info})
                total_neg += 1

            print(f"    +{len(pos)} pos / +{len(neg)} neg")

    (out_dir / 'gt_manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f"\nDone. Dataset: {total_pos} director / {total_neg} other -> {out_dir}")


if __name__ == '__main__':
    main()
