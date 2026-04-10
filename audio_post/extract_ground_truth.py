#!/usr/bin/env python3
"""
extract_ground_truth.py

Compares the user's finished edited WAV against the original Tr1_2 source files
to extract ground truth: which regions were CUT (director speech) vs. KEPT (clean).

Cross-correlates 10s chunks of the finished file against each source Tr1_2 to
find where each chunk came from. Regions of the source files with NO matching
chunks in the finished file = director speech that was removed.

Output:
  ground_truth.json  -- per-take cut regions with sample positions
  speaker_dataset/   -- updated with new confirmed director/other segments

Usage:
    python extract_ground_truth.py ^
        --finished  C:\\path\\DellaCate_FINISHED.wav ^
        --session   C:\\path\\DellaCate-DannySteele-March ^
        --speaker-model C:\\path\\speaker_model ^
        --out       C:\\path\\ground_truth.json ^
        --retrain
"""

import argparse
import json
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


SR_WORK = 8000   # downsample for fast cross-correlation
CHUNK_SEC = 8.0  # chunk size for matching
HOP_SEC   = 4.0  # hop between chunks
MIN_GAP_SEC = 0.8  # minimum unmatched gap to flag as a cut


def _mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 2:
        return audio.mean(axis=1).astype(np.float32)
    return audio.astype(np.float32)


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return audio
    g = gcd(src_sr, dst_sr)
    return resample_poly(audio, dst_sr // g, src_sr // g).astype(np.float32)


def load_downsampled(path: Path) -> tuple:
    """Load WAV file downsampled to SR_WORK mono."""
    audio, sr = sf.read(str(path), always_2d=False)
    mono = _mono(audio)
    ds = _resample(mono, sr, SR_WORK)
    return ds, sr


def xcorr_find(query: np.ndarray, reference: np.ndarray,
               threshold: float = 0.25) -> tuple:
    """
    Find the best match of query in reference using normalized cross-correlation.
    Returns (best_ref_position_samples, correlation_value).
    """
    q = query - query.mean()
    q_std = q.std()
    if q_std < 1e-8:
        return -1, 0.0
    q = q / q_std

    # Slide over reference in steps for speed
    step = max(1, len(query) // 8)
    best_pos, best_corr = -1, 0.0

    for i in range(0, len(reference) - len(query), step):
        window = reference[i:i + len(query)]
        w = window - window.mean()
        w_std = w.std()
        if w_std < 1e-8:
            continue
        corr = float(np.mean(q * (w / w_std)))
        if corr > best_corr:
            best_corr = corr
            best_pos = i

    # Refine around best position
    if best_pos >= 0:
        refine_radius = step
        for i in range(max(0, best_pos - refine_radius),
                       min(len(reference) - len(query), best_pos + refine_radius)):
            window = reference[i:i + len(query)]
            w = window - window.mean()
            w_std = w.std()
            if w_std < 1e-8:
                continue
            corr = float(np.mean(q * (w / w_std)))
            if corr > best_corr:
                best_corr = corr
                best_pos = i

    return best_pos if best_corr >= threshold else -1, best_corr


def match_finished_to_sources(finished_ds: np.ndarray,
                               sources: list) -> list:
    """
    For each chunk of the finished file, find its best match across all source files.
    Returns list of {finished_start, source_idx, source_start, corr}.
    """
    chunk = int(CHUNK_SEC * SR_WORK)
    hop   = int(HOP_SEC * SR_WORK)
    matches = []

    total_chunks = (len(finished_ds) - chunk) // hop
    print(f"  Matching {total_chunks} chunks against {len(sources)} source file(s)...")

    for ci, i in enumerate(range(0, len(finished_ds) - chunk, hop)):
        if ci % 20 == 0:
            print(f"    chunk {ci}/{total_chunks} ({100*ci//total_chunks}%)", end="\r")

        q = finished_ds[i:i + chunk]
        rms = np.sqrt(np.mean(q ** 2))
        if rms < 1e-4:
            continue

        best_src, best_pos, best_corr = -1, -1, 0.25  # threshold
        for si, (src_ds, _) in enumerate(sources):
            pos, corr = xcorr_find(q, src_ds)
            if corr > best_corr:
                best_corr = corr
                best_src = si
                best_pos = pos

        if best_src >= 0 and best_pos >= 0:
            matches.append({
                "finished_start": i,
                "source_idx": best_src,
                "source_start": best_pos,
                "corr": round(best_corr, 3),
            })

    print(f"    {len(matches)} matches found          ")
    return matches


def find_unmatched_regions(source_len: int, matches: list,
                           min_gap_samples: int) -> list:
    """Find source regions with no matching chunks in the finished file."""
    covered = np.zeros(source_len, dtype=bool)
    chunk = int(CHUNK_SEC * SR_WORK)

    for m in matches:
        s = m["source_start"]
        e = min(source_len, s + chunk)
        covered[s:e] = True

    # Find unmatched runs
    gaps = []
    in_gap, gap_start = False, 0
    for i, v in enumerate(covered):
        if not v and not in_gap:
            gap_start, in_gap = i, True
        elif v and in_gap:
            if i - gap_start >= min_gap_samples:
                gaps.append((gap_start, i))
            in_gap = False
    if in_gap and source_len - gap_start >= min_gap_samples:
        gaps.append((gap_start, source_len))

    return gaps


def save_segments_for_training(gaps: list, source_path: Path, source_sr: int,
                                covered_regions: list,
                                out_dir: Path, prefix: str,
                                max_segments: int = 50):
    """
    Write short WAV segments:
      out_dir/director/  -- from gap (unmatched) regions
      out_dir/other/     -- from covered (matched) regions
    """
    dir_dir = out_dir / "director"
    oth_dir = out_dir / "other"
    dir_dir.mkdir(parents=True, exist_ok=True)
    oth_dir.mkdir(parents=True, exist_ok=True)

    seg_len = int(2.0 * source_sr)   # 2s segments

    audio, _ = sf.read(str(source_path), always_2d=False)
    mono = _mono(audio)

    written_dir, written_oth = 0, 0

    # Director (gap) segments
    for gap_s_ds, gap_e_ds in gaps:
        if written_dir >= max_segments:
            break
        gap_s = int(gap_s_ds * source_sr / SR_WORK)
        gap_e = int(gap_e_ds * source_sr / SR_WORK)
        for offset in range(gap_s, gap_e - seg_len, seg_len):
            chunk = mono[offset:offset + seg_len]
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms < 5e-4:
                continue
            out_f = dir_dir / f"{prefix}_dir_{offset}.wav"
            sf.write(str(out_f), chunk, source_sr)
            written_dir += 1
            if written_dir >= max_segments:
                break

    # Other (covered) segments
    for cov_s_ds, cov_e_ds in covered_regions:
        if written_oth >= max_segments:
            break
        cov_s = int(cov_s_ds * source_sr / SR_WORK)
        cov_e = int(cov_e_ds * source_sr / SR_WORK)
        for offset in range(cov_s, cov_e - seg_len, seg_len):
            chunk = mono[offset:offset + seg_len]
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms < 5e-4:
                continue
            out_f = oth_dir / f"{prefix}_oth_{offset}.wav"
            sf.write(str(out_f), chunk, source_sr)
            written_oth += 1
            if written_oth >= max_segments:
                break

    return written_dir, written_oth


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="Extract ground truth labels from finished edit vs. source files."
    )
    parser.add_argument("--finished",      required=True, help="Finished edited WAV")
    parser.add_argument("--session",       required=True, help="Session folder with .TAKE dirs")
    parser.add_argument("--speaker-model", default=None,  help="Speaker model dir (for retraining)")
    parser.add_argument("--out",           required=True, help="Output JSON path")
    parser.add_argument("--retrain",       action="store_true",
                        help="Retrain speaker model after extracting labels")
    parser.add_argument("--dataset-dir",   default=None,
                        help="Directory to save training segments (default: auto)")
    args = parser.parse_args()

    finished_path = Path(args.finished)
    session_path  = Path(args.session)
    out_path      = Path(args.out)

    # 1. Load finished file
    print(f"Loading finished file: {finished_path.name}")
    finished_ds, finished_sr = load_downsampled(finished_path)
    print(f"  Duration: {len(finished_ds)/SR_WORK:.1f}s")

    # 2. Find source files
    source_paths = sorted(session_path.rglob("*_Tr1_2.WAV"))
    if not source_paths:
        print(f"No Tr1_2 files found in {session_path}")
        sys.exit(1)
    print(f"\nLoading {len(source_paths)} source file(s)...")
    sources = []
    for sp in source_paths:
        ds, sr = load_downsampled(sp)
        sources.append((ds, sr))
        print(f"  {sp.name}: {len(ds)/SR_WORK:.1f}s")

    # 3. Match finished -> source
    print("\nCross-correlating finished file against sources...")
    all_matches = match_finished_to_sources(finished_ds, sources)

    # 4. Per-source: find unmatched regions (= director speech cuts)
    dataset_dir = Path(args.dataset_dir) if args.dataset_dir else out_path.parent / "gt_dataset"
    all_results = []
    total_cut_sec = 0

    for si, (src_path, (src_ds, src_sr)) in enumerate(zip(source_paths, sources)):
        prefix = src_path.name[:-len("_Tr1_2.WAV")]
        src_matches = [m for m in all_matches if m["source_idx"] == si]

        if not src_matches:
            print(f"\n{prefix}: no matches (not in finished edit)")
            continue

        print(f"\n{prefix}: {len(src_matches)} chunks matched")

        min_gap = int(MIN_GAP_SEC * SR_WORK)
        gaps = find_unmatched_regions(len(src_ds), src_matches, min_gap)

        # Convert gaps from downsampled positions to original SR
        gaps_orig = []
        for g_s, g_e in gaps:
            s_orig = int(g_s * src_sr / SR_WORK)
            e_orig = int(g_e * src_sr / SR_WORK)
            dur = (e_orig - s_orig) / src_sr
            total_cut_sec += dur
            gaps_orig.append({
                "start_samp": s_orig,
                "end_samp": e_orig,
                "start_sec": round(s_orig / src_sr, 3),
                "end_sec": round(e_orig / src_sr, 3),
                "duration_sec": round(dur, 3),
            })
            print(f"  CUT: {s_orig/src_sr:.2f}s -> {e_orig/src_sr:.2f}s ({dur:.2f}s)")

        # Covered regions (kept in final edit)
        covered_regions = [(m["source_start"],
                            m["source_start"] + int(CHUNK_SEC * SR_WORK))
                           for m in src_matches]

        # Save training segments
        n_dir, n_oth = save_segments_for_training(
            gaps, src_path, src_sr, covered_regions,
            dataset_dir, prefix
        )
        print(f"  Saved {n_dir} director + {n_oth} other training segments")

        all_results.append({
            "source_file": str(src_path),
            "prefix": prefix,
            "n_matched_chunks": len(src_matches),
            "n_cut_regions": len(gaps_orig),
            "cut_regions": gaps_orig,
        })

    # 5. Write JSON
    output = {
        "finished_file": str(finished_path),
        "session": str(session_path),
        "total_cut_duration_sec": round(total_cut_sec, 1),
        "results": all_results,
    }
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nWrote: {out_path}")
    print(f"Total cut duration: {total_cut_sec:.1f}s across {len(all_results)} take(s)")
    print(f"Training segments saved to: {dataset_dir}")

    # 6. Optionally retrain
    if args.retrain and args.speaker_model:
        print("\nRetraining speaker model on new ground truth data...")
        retrain_script = Path(__file__).parent / "train_speaker_model.py"
        if retrain_script.exists():
            import subprocess
            result = subprocess.run(
                [sys.executable, str(retrain_script),
                 "--data-dir", str(dataset_dir),
                 "--out", args.speaker_model],
                capture_output=False
            )
            if result.returncode == 0:
                print("Retraining complete.")
            else:
                print("Retraining failed.")
        else:
            print(f"  train_speaker_model.py not found at {retrain_script}")


if __name__ == "__main__":
    main()
