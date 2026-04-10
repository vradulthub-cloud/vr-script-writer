#!/usr/bin/env python3
"""
build_speaker_dataset.py

Scans session folders for Tr4 WAV files, runs silero-VAD on each,
and extracts labeled audio segments into a dataset folder.
Applies augmentation (speed/pitch shift, noise) to improve generalization.

Output layout:
  dataset/
    director/       ← positive: director speech from Tr4 (+ augmented copies)
    other/          ← negative: performer speech / ambience from Tr1_2

Usage:
    python build_speaker_dataset.py C:\\AudioTraining --out C:\\speaker_dataset
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import scipy.signal as sig

# ── VAD setup ─────────────────────────────────────────────────────────────────

def load_vad():
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True
    )
    get_speech_ts = utils[0]
    return model, get_speech_ts


def get_speech_regions(wav_path: Path, model, get_speech_ts,
                       min_speech_ms=300, min_silence_ms=200):
    audio, sr = sf.read(str(wav_path), always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio_16k = sig.resample_poly(audio, 16000, sr).astype(np.float32) if sr != 16000 else audio.astype(np.float32)
    audio_t = torch.from_numpy(audio_16k)
    timestamps = get_speech_ts(
        audio_t, model,
        min_speech_duration_ms=min_speech_ms,
        min_silence_duration_ms=min_silence_ms,
        return_seconds=False,
    )
    ratio = sr / 16000
    return [(int(t["start"] * ratio), int(t["end"] * ratio)) for t in timestamps], sr, audio


# ── Quality filter ─────────────────────────────────────────────────────────────

def is_quality_segment(audio: np.ndarray, sr: int,
                        min_rms: float = 0.001, max_clip_pct: float = 0.02) -> bool:
    """Reject silent, clipped, or very short segments."""
    if len(audio) < int(sr * 0.3):
        return False
    rms = np.sqrt(np.mean(audio ** 2))
    if rms < min_rms:
        return False
    clip_pct = np.mean(np.abs(audio) > 0.98)
    if clip_pct > max_clip_pct:
        return False
    return True


# ── Augmentation ──────────────────────────────────────────────────────────────

def augment(audio: np.ndarray, sr: int) -> list:
    """Return list of augmented variants of the audio chunk."""
    variants = []

    # Speed shift ±5% (changes pitch too — natural for speech)
    for rate in [0.95, 1.05]:
        n_samples = int(len(audio) * rate)
        resampled = sig.resample(audio, n_samples).astype(np.float32)
        variants.append(("spd{:.0f}".format(rate * 100), resampled))

    # Add light Gaussian noise (simulates mic hiss)
    noise_level = 0.004
    noisy = (audio + np.random.randn(len(audio)).astype(np.float32) * noise_level).clip(-1, 1)
    variants.append(("noise", noisy))

    # Slight volume variation ±20%
    for gain in [0.8, 1.2]:
        variants.append(("vol{:.0f}".format(gain * 100), (audio * gain).clip(-1, 1)))

    return variants


# ── Segment extraction ─────────────────────────────────────────────────────────

def extract_segments(audio: np.ndarray, sr: int, regions: list,
                     out_dir: Path, prefix: str,
                     min_dur_sec: float = 0.5, max_dur_sec: float = 8.0,
                     augment_data: bool = False) -> int:
    saved = 0
    for i, (s, e) in enumerate(regions):
        dur = (e - s) / sr
        if dur < min_dur_sec:
            continue
        # Take center slice if too long
        if dur > max_dur_sec:
            center = (s + e) // 2
            half = int(max_dur_sec * sr / 2)
            s, e = center - half, center + half

        chunk = audio[s:e].astype(np.float32)
        if not is_quality_segment(chunk, sr):
            continue

        # Normalize
        peak = np.abs(chunk).max()
        if peak > 0:
            chunk = chunk / peak * 0.9

        # Save original
        out_path = out_dir / f"{prefix}_seg{i:04d}.wav"
        sf.write(str(out_path), chunk, sr, subtype="PCM_16")
        saved += 1

        # Save augmented versions (director only — more positives = better)
        if augment_data:
            for aug_name, aug_chunk in augment(chunk, sr):
                if is_quality_segment(aug_chunk, sr):
                    aug_path = out_dir / f"{prefix}_seg{i:04d}_{aug_name}.wav"
                    sf.write(str(aug_path), aug_chunk, sr, subtype="PCM_16")
                    saved += 1

    return saved


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions_root", help="Root folder containing session subfolders with .TAKE dirs")
    ap.add_argument("--out", default="speaker_dataset", help="Output dataset folder")
    ap.add_argument("--neg-ratio", type=float, default=2.0,
                    help="Negative to positive segment ratio (default 2.0)")
    ap.add_argument("--no-augment", action="store_true",
                    help="Disable augmentation of director segments")
    args = ap.parse_args()

    sessions_root = Path(args.sessions_root)
    out_root  = Path(args.out)
    dir_out   = out_root / "director"
    other_out = out_root / "other"
    dir_out.mkdir(parents=True, exist_ok=True)
    other_out.mkdir(parents=True, exist_ok=True)

    print("Loading VAD model...")
    vad_model, get_speech_ts = load_vad()

    tr4_files = sorted(sessions_root.rglob("*_Tr4.WAV"))
    print(f"Found {len(tr4_files)} Tr4 files\n")

    if not tr4_files:
        print("No Tr4 files found. Check the path.")
        sys.exit(1)

    total_pos = 0
    total_neg = 0

    for tr4_path in tr4_files:
        take_prefix = tr4_path.stem.replace("_Tr4", "")
        tr12_path   = tr4_path.parent / f"{take_prefix}_Tr1_2.WAV"

        print(f"  {tr4_path.parent.name}/{tr4_path.name}")

        # ── Positive: director speech from Tr4 ──
        try:
            regions, sr, audio = get_speech_regions(tr4_path, vad_model, get_speech_ts)
            if not regions:
                print(f"    no speech detected - skipping")
                continue
            do_aug = not args.no_augment
            n = extract_segments(audio, sr, regions, dir_out, take_prefix,
                                  augment_data=do_aug)
            total_pos += n
            aug_note = f" (+{n - len(regions)} augmented)" if do_aug else ""
            print(f"    +{len(regions)} regions -> {n} director segments{aug_note}")
        except Exception as ex:
            print(f"    ERROR on Tr4: {ex}")
            continue

        # ── Negative: non-director sections from Tr1_2 ──
        if not tr12_path.exists():
            continue
        try:
            tr12_audio, tr12_sr = sf.read(str(tr12_path), always_2d=False)
            if tr12_audio.ndim == 2:
                tr12_audio = tr12_audio.mean(axis=1)
            total_frames = len(tr12_audio)

            # Mask out director regions (+1s padding each side)
            dirty = np.zeros(total_frames, dtype=bool)
            for s, e in regions:
                pad = int(sr * 1.0)
                dirty[max(0, s - pad):min(total_frames, e + pad)] = True

            # Find clean stretches >= 2s
            clean_regions = []
            in_clean, seg_start = False, 0
            for i, d in enumerate(dirty):
                if not d and not in_clean:
                    seg_start, in_clean = i, True
                elif d and in_clean:
                    if (i - seg_start) >= int(sr * 2.0):
                        clean_regions.append((seg_start, i))
                    in_clean = False
            if in_clean and (total_frames - seg_start) >= int(sr * 2.0):
                clean_regions.append((seg_start, total_frames))

            # Sample evenly, target neg_ratio × positives
            raw_pos = len(regions)
            want_neg = max(1, int(raw_pos * args.neg_ratio))
            step = max(1, len(clean_regions) // want_neg)
            neg_regions = clean_regions[::step][:want_neg]

            neg_count = extract_segments(
                tr12_audio.astype(np.float32), tr12_sr, neg_regions,
                other_out, f"{take_prefix}_neg",
                augment_data=False  # no augment on negatives
            )
            total_neg += neg_count
            print(f"    -{neg_count} non-director segments")
        except Exception as ex:
            print(f"    ERROR on Tr1_2: {ex}")

    print(f"\n{'='*55}")
    print(f"Dataset: {out_root}")
    print(f"  Director  (positive): {total_pos:4d} segments  (includes augmented)")
    print(f"  Other     (negative): {total_neg:4d} segments")
    print(f"  Ratio pos:neg = 1:{total_neg/(total_pos+1):.1f}")
    print(f"\nNext: python train_speaker_model.py --dataset {out_root} --out C:\\speaker_model")


if __name__ == "__main__":
    main()
