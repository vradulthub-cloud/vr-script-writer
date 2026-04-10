#!/usr/bin/env python3
"""
analyze_workflow_video.py

Analyzes the screen recording of the Premiere Pro editing session to extract
ground truth edit decisions. Uses two strategies:

1. Audio cross-correlation: extracts audio from the screen recording, finds
   where each chunk aligns in the source Tr1_2 WAV files, then uses gaps in
   that alignment to identify cut regions (= director speech ground truth).

2. Speaker detection: runs the trained speaker model on the screen recording
   audio to find director speech, cross-referencing to source file positions.

Output: ground_truth_labels.json -- list of (source_file, start_sec, end_sec)
        regions confirmed as director speech from the user's editing session.

Usage:
    python analyze_workflow_video.py ^
        --video C:\\Users\\andre\\audio_post\\workflow_recording.mov ^
        --session C:\\Users\\andre\\Dropbox\\AudioTraining\\DellaCate-DannySteele-March ^
        --speaker-model C:\\Users\\andre\\speaker_model ^
        --out C:\\Users\\andre\\audio_post\\ground_truth_labels.json
"""

import argparse
import json
import sys
import tempfile
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, correlate


# -- Audio extraction ---------------------------------------------------------

def extract_audio_from_video(video_path: Path, out_wav: Path, target_sr: int = 16000):
    """Extract mono audio from video file using moviepy/ffmpeg."""
    print(f"Extracting audio from {video_path.name} ...")
    try:
        from moviepy import VideoFileClip
        clip = VideoFileClip(str(video_path))
        audio = clip.audio
        if audio is None:
            raise ValueError("Video has no audio track")
        # Write to temp wav
        audio.write_audiofile(str(out_wav), fps=target_sr, nbytes=2,
                              ffmpeg_params=["-ac", "1"], logger=None)
        clip.close()
    except Exception as e:
        # Fallback: use ffmpeg directly
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-ar", str(target_sr), "-ac", "1", "-f", "wav", str(out_wav)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    print(f"  Extracted to {out_wav} ({out_wav.stat().st_size // 1024}KB)")


# -- Cross-correlation alignment ----------------------------------------------

def _to_mono_float(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 2:
        return audio.mean(axis=1).astype(np.float32)
    return audio.astype(np.float32)


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return audio
    g = gcd(src_sr, dst_sr)
    return resample_poly(audio, dst_sr // g, src_sr // g).astype(np.float32)


def find_alignment(query: np.ndarray, reference: np.ndarray,
                   query_sr: int, ref_sr: int,
                   chunk_sec: float = 10.0,
                   hop_sec: float = 5.0) -> list:
    """
    Slide chunk_sec windows of `query` over `reference` to find where each
    chunk aligns. Returns list of (query_start_sec, ref_start_sec, correlation).
    Only returns alignments above a correlation threshold.
    """
    # Resample query to ref sample rate for comparison
    if query_sr != ref_sr:
        query_r = _resample(query, query_sr, ref_sr)
    else:
        query_r = query

    chunk = int(chunk_sec * ref_sr)
    hop   = int(hop_sec * ref_sr)
    alignments = []

    for i in range(0, len(query_r) - chunk, hop):
        q_chunk = query_r[i:i + chunk].astype(np.float64)
        q_rms = np.sqrt(np.mean(q_chunk ** 2))
        if q_rms < 1e-4:  # skip silence
            continue
        q_norm = (q_chunk - q_chunk.mean()) / (q_chunk.std() + 1e-10)

        # Only search a reasonable portion of the reference
        # (full xcorr is too slow for hour-long files)
        # Use energy envelope to narrow search first
        ref_r = reference.astype(np.float64)
        r_norm = (ref_r - ref_r.mean()) / (ref_r.std() + 1e-10)

        # Downsample for fast search
        ds = 16
        q_ds = q_norm[::ds]
        r_ds = r_norm[::ds]

        xcorr = np.correlate(r_ds, q_ds, mode='valid')
        if len(xcorr) == 0:
            continue

        peak_idx = int(np.argmax(xcorr)) * ds
        peak_val = float(xcorr[np.argmax(xcorr)]) / (len(q_ds) + 1e-10)

        if peak_val > 0.15:
            q_start_sec = i / ref_sr
            ref_start_sec = peak_idx / ref_sr
            alignments.append({
                "query_start_sec": q_start_sec,
                "ref_start_sec": ref_start_sec,
                "correlation": round(peak_val, 3),
                "chunk_sec": chunk_sec,
            })

    return alignments


# -- Find cuts from alignment gaps --------------------------------------------

def find_cut_regions(alignments: list, source_frames: int, source_sr: int,
                     min_gap_sec: float = 1.0) -> list:
    """
    Given a list of (ref_start_sec, chunk_sec) alignment hits, find gaps in
    the source file that were NOT played during editing = likely cut regions.
    """
    if not alignments:
        return []

    # Build a mask of which source regions were observed in the recording
    mask = np.zeros(source_frames, dtype=bool)
    for hit in alignments:
        s = int(hit["ref_start_sec"] * source_sr)
        e = int((hit["ref_start_sec"] + hit["chunk_sec"]) * source_sr)
        e = min(e, source_frames)
        if s < source_frames:
            mask[s:e] = True

    # Find contiguous unobserved regions
    min_gap = int(min_gap_sec * source_sr)
    cuts = []
    in_gap = False
    gap_start = 0
    for i, v in enumerate(mask):
        if not v and not in_gap:
            gap_start = i
            in_gap = True
        elif v and in_gap:
            if i - gap_start >= min_gap:
                cuts.append({
                    "start_samp": gap_start,
                    "end_samp": i,
                    "start_sec": round(gap_start / source_sr, 3),
                    "end_sec": round(i / source_sr, 3),
                    "source": "gap_in_playback",
                })
            in_gap = False
    return cuts


# -- Speaker model detection on recording audio -------------------------------

def detect_director_in_recording(recording_audio: np.ndarray, recording_sr: int,
                                  speaker_model_dir: Path,
                                  win_sec: float = 1.5, hop_sec: float = 0.5) -> list:
    """Run speaker model on the screen recording audio to find director speech."""
    sys.path.insert(0, str(Path(__file__).parent))
    from patch_director_voice import SpeakerDetector

    detector = SpeakerDetector(speaker_model_dir)
    print(f"  Speaker model loaded: threshold={detector.threshold:.2f}")

    win = int(win_sec * recording_sr)
    hop = int(hop_sec * recording_sr)
    hits = []
    in_hit = False
    hit_start = 0

    for i in range(0, len(recording_audio) - win, hop):
        chunk = recording_audio[i:i + win]
        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
        if rms < 1e-5:
            if in_hit:
                hits.append({"start_sec": hit_start / recording_sr,
                              "end_sec": i / recording_sr})
                in_hit = False
            continue
        try:
            score = detector.score(chunk, recording_sr)
        except Exception:
            continue
        if score >= detector.threshold:
            if not in_hit:
                hit_start = max(0, i - int(0.5 * recording_sr))
                in_hit = True
        else:
            if in_hit:
                hits.append({"start_sec": hit_start / recording_sr,
                              "end_sec": (i + int(0.3 * recording_sr)) / recording_sr})
                in_hit = False

    if in_hit:
        hits.append({"start_sec": hit_start / recording_sr,
                     "end_sec": len(recording_audio) / recording_sr})

    # Merge close hits
    merged = []
    for h in hits:
        if merged and h["start_sec"] - merged[-1]["end_sec"] < 1.0:
            merged[-1]["end_sec"] = h["end_sec"]
        else:
            merged.append(dict(h))

    return [h for h in merged if h["end_sec"] - h["start_sec"] >= 0.5]


# -- Main ---------------------------------------------------------------------

def main():
    import sys, io
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="Extract ground truth edit labels from a Premiere Pro screen recording."
    )
    parser.add_argument("--video",   required=True, help="Path to screen recording .mov/.mp4")
    parser.add_argument("--session", required=True, help="Session folder with .TAKE dirs")
    parser.add_argument("--speaker-model", default=None, metavar="DIR",
                        help="Trained speaker model folder (for recording-level detection)")
    parser.add_argument("--out",     required=True, help="Output JSON path")
    args = parser.parse_args()

    video_path   = Path(args.video)
    session_path = Path(args.session)
    out_path     = Path(args.out)

    # 1. Extract audio from recording
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        rec_wav_path = Path(tf.name)

    extract_audio_from_video(video_path, rec_wav_path, target_sr=16000)
    rec_audio, rec_sr = sf.read(str(rec_wav_path), always_2d=False)
    rec_audio = _to_mono_float(rec_audio)
    print(f"  Recording: {len(rec_audio)/rec_sr:.1f}s at {rec_sr}Hz")

    # 2. Find source Tr1_2 files
    source_files = sorted(session_path.rglob("*_Tr1_2.WAV"))
    if not source_files:
        print(f"No Tr1_2 WAV files found in {session_path}")
        sys.exit(1)
    print(f"\nFound {len(source_files)} source file(s) to align against")

    # 3. Cross-correlate recording against each source file
    all_results = []
    for src_path in source_files:
        prefix = src_path.name[:-len("_Tr1_2.WAV")]
        print(f"\nAligning against {prefix} ...")
        src_audio, src_sr = sf.read(str(src_path), always_2d=False)
        src_mono = _to_mono_float(src_audio)
        # Downsample source to 16kHz for alignment
        src_16k = _resample(src_mono, src_sr, 16000)

        alignments = find_alignment(rec_audio, src_16k,
                                     query_sr=rec_sr, ref_sr=16000,
                                     chunk_sec=10.0, hop_sec=5.0)
        print(f"  {len(alignments)} alignment hit(s)")

        if alignments:
            cuts = find_cut_regions(alignments, len(src_16k), 16000)
            print(f"  {len(cuts)} gap region(s) found (likely cut = director speech)")
            all_results.append({
                "source_file": str(src_path),
                "prefix": prefix,
                "alignment_hits": len(alignments),
                "gaps": cuts,
            })

    # 4. Speaker detection on recording audio
    if args.speaker_model:
        print(f"\nRunning speaker model on recording audio ...")
        speaker_hits = detect_director_in_recording(
            rec_audio, rec_sr, Path(args.speaker_model)
        )
        print(f"  {len(speaker_hits)} director speech segment(s) in recording")
    else:
        speaker_hits = []

    # 5. Write output
    output = {
        "video": str(video_path),
        "session": str(session_path),
        "recording_duration_sec": round(len(rec_audio) / rec_sr, 1),
        "source_alignments": all_results,
        "speaker_detections_in_recording": speaker_hits,
        "summary": {
            "total_gap_regions": sum(len(r["gaps"]) for r in all_results),
            "total_speaker_hits": len(speaker_hits),
        }
    }
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nWrote: {out_path}")
    print(f"Summary: {output['summary']}")

    # Cleanup temp file
    try:
        rec_wav_path.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    main()
