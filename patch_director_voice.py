#!/usr/bin/env python3
"""
patch_director_voice.py

Detects director speech and fills those regions in the stereo pair (Tr1_2)
with clean audio borrowed from elsewhere in the same session.

Two-stage detection:
  1. silero-VAD on Tr4 (push-to-talk mic) - catches obvious director speech
  2. Spectral bleed scan on Tr1_2 - catches director voice even without PTT

Donor selection mirrors the Premiere Pro manual process:
  - Find a clean section whose waveform envelope looks similar to the region
    being replaced (same visual shape, same level)
  - Prefer same-take audio; allow any other take in the session

Usage:
    python3 patch_director_voice.py /path/to/shoot/folder
    python3 patch_director_voice.py /path/to/single.TAKE
    python3 patch_director_voice.py --dry-run /path/to/folder
    python3 patch_director_voice.py --no-bleed /path/to/folder

Output:
    YYMMDD_NNN_Tr1_2_PATCHED.WAV  - written inside each .TAKE folder
"""

import argparse
import json
import sys
from math import gcd

import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import resample_poly


# -- Config -------------------------------------------------------------------

VAD_THRESHOLD      = 0.5    # silero-VAD speech probability threshold (0-1)
VAD_TARGET_SR      = 16000  # silero-VAD requires 16 kHz input
MIN_SPEECH_SEC     = 0.15   # ignore detections shorter than this
PRE_BUFFER_SEC     = 0.70   # pad each region start by this much
POST_BUFFER_SEC    = 0.30   # pad each region end by this much
MERGE_GAP_SEC      = 0.50   # merge VAD hits closer than this (seconds)

BLEED_WIN_SEC      = 0.40   # spectral bleed scan window
BLEED_HOP_SEC      = 0.10   # spectral bleed scan hop
BLEED_SIM_THRESH   = 0.92   # cosine similarity to director fingerprint
BLEED_MIN_SEC      = 0.30   # ignore bleed detections shorter than this

CROSSFADE_SEC      = 0.40   # crossfade at patch edges
POOL_MIN_SEC       = 0.5    # min chunk length for cross-take donor pool
POOL_VAD_THRESHOLD = 0.3    # relaxed VAD threshold for pool building (more donors)
WINDOW_SEC         = 0.05   # RMS window for noise-floor/clean-mask
NOISE_PERCENTILE   = 20
MAX_DIRTY_RUN_SEC  = 0.10   # max continuous dirty samples allowed in a donor

VERIFY_CORR_THRESH = 0.12   # warn if patched region correlates above this with Tr4


# -- silero-VAD helpers --------------------------------------------------------

_vad_model = None

def _get_vad_model():
    global _vad_model
    if _vad_model is None:
        from silero_vad import load_silero_vad
        _vad_model = load_silero_vad()
    return _vad_model


def _to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    """Resample mono float32 array to 16 kHz."""
    if sr == VAD_TARGET_SR:
        return audio.astype(np.float32)
    g = gcd(sr, VAD_TARGET_SR)
    return resample_poly(audio, VAD_TARGET_SR // g, sr // g).astype(np.float32)


def _run_vad(audio_mono: np.ndarray, sr: int, threshold: float) -> list:
    """Run silero-VAD on a mono audio array. Returns list of (start, end) in original samples."""
    import torch
    from silero_vad import get_speech_timestamps

    audio_16k = _to_16k(audio_mono, sr)
    model = _get_vad_model()

    ts = get_speech_timestamps(
        torch.from_numpy(audio_16k),
        model,
        sampling_rate=VAD_TARGET_SR,
        threshold=threshold,
        min_speech_duration_ms=int(MIN_SPEECH_SEC * 1000),
        min_silence_duration_ms=int(MERGE_GAP_SEC * 1000),
    )

    scale = sr / VAD_TARGET_SR
    regions = []
    for t in ts:
        s = max(0, int(t["start"] * scale) - int(PRE_BUFFER_SEC * sr))
        e = min(len(audio_mono), int(t["end"] * scale) + int(POST_BUFFER_SEC * sr))
        if e - s >= int(MIN_SPEECH_SEC * sr):
            regions.append((s, e))

    # merge overlaps
    merged = []
    for s, e in sorted(regions):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


# -- Detection: Tr4 VAD -------------------------------------------------------

def detect_on_tr4(tr4: np.ndarray, sr: int) -> list:
    """Stage 1: silero-VAD on the push-to-talk mic."""
    mono = tr4[:, np.argmax(np.max(np.abs(tr4), axis=0))] if tr4.ndim == 2 else tr4
    return _run_vad(mono, sr, VAD_THRESHOLD)


# -- Detection: Tr1_2 bleed scan ----------------------------------------------

def build_director_fingerprint(tr4: np.ndarray, sr: int, vad_regions: list,
                                fft_size: int = 2048) -> np.ndarray | None:
    """Build an average spectral fingerprint of the director's voice from Tr4
    during VAD-confirmed speech segments."""
    mono = tr4[:, np.argmax(np.max(np.abs(tr4), axis=0))] if tr4.ndim == 2 else tr4
    window = np.hanning(fft_size)
    spectra = []
    for s, e in vad_regions:
        # Strip buffers to get core speech
        s_core = s + int(PRE_BUFFER_SEC * sr)
        e_core = e - int(POST_BUFFER_SEC * sr)
        if e_core - s_core < fft_size:
            continue
        chunk = mono[s_core:e_core].astype(np.float64)
        for i in range(0, len(chunk) - fft_size, fft_size // 2):
            frame = np.abs(np.fft.rfft(chunk[i:i + fft_size] * window))
            spectra.append(frame)
    if not spectra:
        return None
    mean = np.mean(spectra, axis=0)
    norm = np.linalg.norm(mean)
    return mean / norm if norm > 1e-10 else None


def detect_bleed_in_tr12(tr12: np.ndarray, sr: int,
                          fingerprint: np.ndarray,
                          vad_regions: list,
                          fft_size: int = 2048) -> list:
    """Stage 2: slide the director's spectral fingerprint over Tr1_2 mono and
    flag windows with high cosine similarity (director voice bleed)."""
    if fingerprint is None:
        return []

    mono = tr12.mean(axis=1).astype(np.float64)
    window = np.hanning(fft_size)
    win_samp = int(BLEED_WIN_SEC * sr)
    hop_samp = int(BLEED_HOP_SEC * sr)
    min_samp = int(BLEED_MIN_SEC * sr)

    # pre-mark VAD-covered samples to skip
    covered = np.zeros(len(mono), dtype=bool)
    for s, e in vad_regions:
        covered[s:e] = True

    in_bleed, bleed_start = False, 0
    raw_bleed = []

    for i in range(0, len(mono) - win_samp, hop_samp):
        center = i + win_samp // 2
        if covered[center]:
            if in_bleed:
                raw_bleed.append((bleed_start, i + int(POST_BUFFER_SEC * sr)))
                in_bleed = False
            continue

        chunk = mono[i:i + win_samp]
        chunk_spectra = []
        for j in range(0, len(chunk) - fft_size, fft_size // 2):
            frame = np.abs(np.fft.rfft(chunk[j:j + fft_size] * window))
            chunk_spectra.append(frame)
        if not chunk_spectra:
            continue

        mean = np.mean(chunk_spectra, axis=0)
        norm = np.linalg.norm(mean)
        if norm < 1e-10:
            continue
        sim = float(np.dot(fingerprint, mean / norm))

        if sim >= BLEED_SIM_THRESH:
            if not in_bleed:
                bleed_start = max(0, i - int(PRE_BUFFER_SEC * sr))
                in_bleed = True
        else:
            if in_bleed:
                raw_bleed.append((bleed_start, min(len(mono), i + int(POST_BUFFER_SEC * sr))))
                in_bleed = False

    if in_bleed:
        raw_bleed.append((bleed_start, len(mono)))

    # filter by minimum duration and merge
    filtered = [(s, e) for s, e in raw_bleed if e - s >= min_samp]
    merged = []
    for s, e in filtered:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


# -- Speaker model detection ---------------------------------------------------

class SpeakerDetector:
    """Loads the trained director speaker model and scores audio windows."""

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        cfg_path = model_dir / "config.json"
        emb_path = model_dir / "director_embedding.npy"

        if not cfg_path.exists() or not emb_path.exists():
            raise FileNotFoundError(f"Speaker model not found in {model_dir}")

        with open(cfg_path) as f:
            self.cfg = json.load(f)

        self.centroid  = np.load(str(emb_path)).astype(np.float32)
        self.threshold = float(self.cfg.get("threshold", 0.65))
        self.model_type = self.cfg.get("model_type", "resemblyzer")
        self._encoder  = None
        print(f"  Speaker model: {self.model_type}  threshold={self.threshold:.2f}")

    def _load_encoder(self):
        if self._encoder is not None:
            return
        import torch

        if self.model_type == "wavlm_director":
            # Fine-tuned WavLM binary classifier (best accuracy)
            from transformers import WavLMModel
            import torch.nn as nn
            wavlm_path = self.cfg.get("wavlm_path", str(self.model_dir / "wavlm_director" / "wavlm"))
            head_path  = self.cfg.get("head_path",  str(self.model_dir / "wavlm_director" / "head.pt"))
            device = "cuda" if torch.cuda.is_available() else "cpu"
            wavlm = WavLMModel.from_pretrained(wavlm_path)
            hidden = wavlm.config.hidden_size
            head = nn.Sequential(
                nn.Linear(hidden, 256), nn.ReLU(), nn.Dropout(0.3), nn.Linear(256, 1)
            )
            head.load_state_dict(torch.load(head_path, map_location=device))

            class _WavLMClassifier(nn.Module):
                def __init__(self, wavlm, head):
                    super().__init__()
                    self.wavlm = wavlm
                    self.head  = head
                def forward(self, x):
                    h = self.wavlm(x).last_hidden_state.mean(dim=1)
                    return torch.sigmoid(self.head(h).squeeze(-1))

            self._encoder = _WavLMClassifier(wavlm, head).to(device).eval()
            self._device = device
            self._backend = "wavlm_director"
        else:
            # Fallback: ECAPA-TDNN enrollment (centroid cosine similarity)
            try:
                from speechbrain.inference.classifiers import EncoderClassifier
            except ImportError:
                from speechbrain.pretrained import EncoderClassifier
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(self.model_dir / "pretrained_ecapa"),
                run_opts={"device": device},
            )
            self._device = device
            self._backend = "ecapa"

    def score(self, audio_mono: np.ndarray, sr: int) -> float:
        """Return probability (0-1) that audio contains the director's voice."""
        self._load_encoder()
        import torch
        # Resample to 16kHz
        if sr != 16000:
            g = gcd(sr, 16000)
            audio_mono = resample_poly(audio_mono, 16000 // g, sr // g).astype(np.float32)
        else:
            audio_mono = audio_mono.astype(np.float32)
        # Normalize RMS
        rms = np.sqrt(np.mean(audio_mono ** 2))
        if rms > 1e-6:
            audio_mono = audio_mono / (rms * 10)

        t = torch.from_numpy(audio_mono).unsqueeze(0).to(self._device)
        with torch.no_grad():
            if self._backend == "wavlm_director":
                return float(self._encoder(t).cpu())
            else:
                emb = self._encoder.encode_batch(t).squeeze().cpu().numpy()
                norm = np.linalg.norm(emb)
                emb = emb / norm if norm > 1e-8 else emb
                return float(np.dot(emb, self.centroid))


def detect_speaker_in_tr12(tr12: np.ndarray, sr: int,
                            detector: SpeakerDetector,
                            vad_regions: list,
                            win_sec: float = 1.5,
                            hop_sec: float = 0.5) -> list:
    """Slide speaker embedding windows over Tr1_2, flag director-matching frames.

    More accurate than spectral fingerprint - uses the trained speaker embedding.
    Skips windows already covered by Tr4 VAD.
    """
    mono = tr12.mean(axis=1).astype(np.float32) if tr12.ndim == 2 else tr12.astype(np.float32)
    win_samp = int(win_sec * sr)
    hop_samp = int(hop_sec * sr)
    min_samp  = int(0.3 * sr)

    covered = np.zeros(len(mono), dtype=bool)
    for s, e in vad_regions:
        covered[s:e] = True

    in_hit, hit_start = False, 0
    detections = []

    for i in range(0, len(mono) - win_samp, hop_samp):
        center = i + win_samp // 2
        if covered[center]:
            if in_hit:
                detections.append((hit_start, i + int(POST_BUFFER_SEC * sr)))
                in_hit = False
            continue

        chunk = mono[i:i + win_samp]
        # Skip near-silence
        if np.sqrt(np.mean(chunk ** 2)) < 1e-5:
            if in_hit:
                detections.append((hit_start, i))
                in_hit = False
            continue

        try:
            sim = detector.score(chunk, sr)
        except Exception:
            continue

        if sim >= detector.threshold:
            if not in_hit:
                hit_start = max(0, i - int(PRE_BUFFER_SEC * sr))
                in_hit = True
        else:
            if in_hit:
                detections.append((hit_start, min(len(mono), i + int(POST_BUFFER_SEC * sr))))
                in_hit = False

    if in_hit:
        detections.append((hit_start, len(mono)))

    # Filter short hits and merge
    filtered = [(s, e) for s, e in detections if e - s >= min_samp]
    merged = []
    for s, e in filtered:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


# -- Merge all detected regions ------------------------------------------------

def merge_regions(regions_a: list, regions_b: list) -> list:
    combined = sorted(regions_a + regions_b)
    merged = []
    for s, e in combined:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


# -- Clean mask (for donor selection) -----------------------------------------

def _rms_envelope(audio: np.ndarray, sr: int) -> tuple:
    hop = max(1, int(sr * WINDOW_SEC))
    frames = [np.sqrt(np.mean(audio[i:i + hop] ** 2)) for i in range(0, len(audio), hop)]
    return np.array(frames), hop


def build_clean_mask(tr4: np.ndarray, sr: int, mult: float = 1.1) -> np.ndarray:
    """True where Tr4 is below mult x noise floor (no director speech)."""
    mono = tr4[:, np.argmax(np.max(np.abs(tr4), axis=0))] if tr4.ndim == 2 else tr4
    envelope, hop = _rms_envelope(mono, sr)
    noise_floor = float(np.percentile(envelope, NOISE_PERCENTILE))
    threshold = noise_floor * mult
    mask = np.zeros(len(mono), dtype=bool)
    for i, v in enumerate(envelope):
        s = i * hop
        e = min(len(mono), s + hop)
        if v <= threshold:
            mask[s:e] = True
    return mask


def _donor_ok(clean_mask: np.ndarray, s: int, e: int, sr: int) -> bool:
    max_run = int(MAX_DIRTY_RUN_SEC * sr)
    run = 0
    for v in clean_mask[s:e]:
        if not v:
            run += 1
            if run > max_run:
                return False
        else:
            run = 0
    return True


# -- Waveform envelope shape matching -----------------------------------------

def _coarse_env(audio: np.ndarray, sr: int, hop_ms: float = 20.0) -> np.ndarray:
    hop = max(1, int(sr * hop_ms / 1000))
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    return np.array([np.sqrt(np.mean(mono[i:i + hop] ** 2))
                     for i in range(0, len(mono), hop)])


def _shape_score(template: np.ndarray, candidate: np.ndarray) -> float:
    """Slide template over candidate; return min normalised MSE (lower = better match)."""
    n = len(template)
    if len(candidate) < n:
        return float("inf")
    t_std = template.std()
    if t_std < 1e-8:
        return 0.0
    t_norm = (template - template.mean()) / t_std
    best = float("inf")
    for i in range(len(candidate) - n + 1):
        w = candidate[i:i + n]
        w_std = w.std()
        if w_std < 1e-8:
            continue
        dist = float(np.mean(((w - w.mean()) / w_std - t_norm) ** 2))
        if dist < best:
            best = dist
    return best


# -- Donor pool helpers --------------------------------------------------------

def _collect_same_take_chunks(tr12: np.ndarray, clean_mask: np.ndarray,
                               sr: int, center: int,
                               tr12_path: "Path" = None,
                               slice_radius_sec: float = 12.0) -> list:
    """Return clean audio slices sorted by proximity to center.

    Returns list of (dist, chunk, source_file, source_start, source_end).
    """
    hop     = max(1, int(sr * WINDOW_SEC))
    min_len = int(0.1 * sr)
    radius  = int(slice_radius_sec * sr)

    segments = []
    in_clean, seg_start = False, 0
    for i in range(0, len(clean_mask), hop):
        block_ok = bool(np.all(clean_mask[i:i + hop]))
        if block_ok and not in_clean:
            seg_start, in_clean = i, True
        elif not block_ok and in_clean:
            if i - seg_start >= min_len:
                segments.append((seg_start, i))
            in_clean = False
    if in_clean and len(clean_mask) - seg_start >= min_len:
        segments.append((seg_start, len(clean_mask)))

    chunks = []
    for seg_s, seg_e in segments:
        closest = max(seg_s, min(seg_e, center))
        dist    = abs(closest - center)
        sl_s = max(seg_s, closest - radius)
        sl_e = min(seg_e, closest + radius)
        if sl_e - sl_s >= min_len:
            chunks.append((dist, tr12[sl_s:sl_e], tr12_path, sl_s, sl_e))

    chunks.sort(key=lambda x: x[0])
    return chunks


def _longest_clean_stretch_pos(clean_mask: np.ndarray) -> tuple:
    """Returns (start, end) of the longest clean stretch."""
    best_s, best_len, cur_s = 0, 0, None
    for i, v in enumerate(clean_mask):
        if v and cur_s is None:
            cur_s = i
        elif not v and cur_s is not None:
            if i - cur_s > best_len:
                best_s, best_len = cur_s, i - cur_s
            cur_s = None
    if cur_s is not None and len(clean_mask) - cur_s > best_len:
        best_s, best_len = cur_s, len(clean_mask) - cur_s
    return best_s, best_s + best_len


# -- Crossfade stitch ---------------------------------------------------------

def _xfade_join(a: np.ndarray, b: np.ndarray, cf_samp: int) -> np.ndarray:
    """Join two arrays with a cosine crossfade of cf_samp samples."""
    n = min(cf_samp, len(a), len(b))
    if n < 2:
        return np.concatenate([a, b], axis=0)
    t = np.linspace(0, np.pi / 2, n)
    fo, fi = np.cos(t), np.sin(t)
    if a.ndim == 2:
        fo, fi = fo[:, None], fi[:, None]
    joined = np.concatenate([a[:-n], a[-n:] * fo + b[:n] * fi, b[n:]], axis=0)
    return joined


# -- Find best donor -----------------------------------------------------------

def _find_clean_segments(clean_mask: np.ndarray, min_len: int) -> list:
    """Return list of (start, end) contiguous clean runs of at least min_len samples."""
    segments = []
    in_clean, seg_start = False, 0
    for i, v in enumerate(clean_mask):
        if v and not in_clean:
            seg_start, in_clean = i, True
        elif not v and in_clean:
            if i - seg_start >= min_len:
                segments.append((seg_start, i))
            in_clean = False
    if in_clean and len(clean_mask) - seg_start >= min_len:
        segments.append((seg_start, len(clean_mask)))
    return segments


def find_donor(tr12: np.ndarray, sr: int, clean_mask: np.ndarray,
               start: int, end: int,
               tr12_path: "Path" = None,
               cross_pool: list = None) -> list:
    """Return a minimal list of source segments to fill the gap [start, end).

    Prefers single long clean sections close to the gap - matching how an editor
    would manually find a room-tone fill in Premiere. Returns at most 3 segments.

    Each segment: {"file": Path, "start": int, "end": int}
    """
    region_len = end - start
    center = (start + end) // 2

    # Scoring helpers
    ctx = int(0.5 * sr)
    rms_parts = []
    if start >= ctx:
        rms_parts.append(tr12[start - ctx:start])
    if end + ctx <= len(tr12):
        rms_parts.append(tr12[end:end + ctx])
    target_rms = float(np.sqrt(np.mean(np.concatenate(rms_parts) ** 2))) if rms_parts else 0.0

    def _score_seg(seg_s, seg_e, src_file=None):
        chunk = tr12[seg_s:seg_e] if src_file == tr12_path else None
        dist  = abs(max(seg_s, min(seg_e, center)) - center)
        # Penalise distance from gap; cross-take gets extra penalty
        dist_penalty = dist / sr  # seconds away
        cross_penalty = 0.3 if src_file != tr12_path else 0.0
        # RMS match
        if chunk is not None:
            mono = chunk.mean(axis=1) if chunk.ndim == 2 else chunk
            rms  = float(np.sqrt(np.mean(mono[:region_len] ** 2)))
            rms_dist = abs(rms - target_rms) / (target_rms + 1e-8)
        else:
            rms_dist = 0.1
        return dist_penalty * 0.6 + rms_dist * 0.25 + cross_penalty

    # Collect candidate segments - any clean run >= 500ms, sorted by score
    min_seg = int(0.5 * sr)
    candidates = []  # (score, file, seg_s, seg_e)

    for seg_s, seg_e in _find_clean_segments(clean_mask, min_seg):
        if seg_e <= start or seg_s >= end:  # exclude the gap itself
            candidates.append((_score_seg(seg_s, seg_e, tr12_path),
                                tr12_path, seg_s, seg_e))

    # Cross-take fallback if same-take pool is thin
    if cross_pool and len(candidates) < 3:
        for entry in cross_pool:
            candidates.append((_score_seg(entry["start"], entry["end"], entry["file"]) + 0.3,
                                entry["file"], entry["start"], entry["end"]))

    # Absolute fallback: longest clean stretch in this take
    if not candidates:
        fb_s, fb_e = _longest_clean_stretch_pos(clean_mask)
        candidates.append((0.0, tr12_path, fb_s, fb_e))

    candidates.sort(key=lambda x: x[0])

    # Fill gap using best segments (max 3 clips in Premiere)
    segments = []
    filled = 0
    used = set()
    for score, src_file, seg_s, seg_e in candidates:
        if filled >= region_len or len(segments) >= 3:
            break
        key = (str(src_file), seg_s, seg_e)
        if key in used:
            continue
        used.add(key)
        needed  = region_len - filled
        use_end = min(seg_e, seg_s + needed)
        use_len = use_end - seg_s
        if use_len <= 0:
            continue
        segments.append({"file": src_file, "start": seg_s, "end": use_end})
        filled += use_len

    # If still not filled (all clean segments too short), loop best segment
    if filled < region_len and segments:
        best = segments[0]
        seg_len = best["end"] - best["start"]
        while filled < region_len and len(segments) < 3:
            needed  = region_len - filled
            use_len = min(seg_len, needed)
            segments.append({"file": best["file"],
                             "start": best["start"],
                             "end":   best["start"] + use_len})
            filled += use_len

    return segments if segments else [{"file": tr12_path, "start": 0, "end": region_len}]


# -- Splice with crossfade -----------------------------------------------------

def apply_region(output: np.ndarray, donor: np.ndarray,
                 original: np.ndarray, sr: int, start: int, end: int):
    output[start:end] = donor
    # Scale crossfade to gap size: 10% of gap, clamped 100ms-500ms
    gap_sec = (end - start) / sr
    cf_sec  = max(0.10, min(0.50, gap_sec * 0.10))
    cf      = min(int(cf_sec * sr), (end - start) // 3)
    if cf <= 0:
        return
    t = np.linspace(0, np.pi / 2, cf)
    fi, fo = np.sin(t), np.cos(t)
    if output.ndim == 2:
        fi, fo = fi[:, None], fo[:, None]

    n_in = min(cf, end - start)
    output[start:start + n_in] = donor[:n_in] * fi[:n_in] + original[start:start + n_in] * fo[:n_in]

    e_start = max(end - cf, start)
    n_out   = end - e_start
    off     = e_start - start
    output[e_start:end] = donor[off:off + n_out] * fo[-n_out:] + original[e_start:end] * fi[-n_out:]


# -- Cross-take donor pool -----------------------------------------------------

def build_cross_take_pool(takes: list) -> list:
    pool = []
    print(f"\nBuilding cross-take donor pool from {len(takes)} take(s)...")
    sr_last = 48000
    for take in takes:
        try:
            tr4,  sr4  = sf.read(str(take["tr4"]),  always_2d=False)
            tr12, sr12 = sf.read(str(take["tr1_2"]), always_2d=True)
        except Exception as exc:
            print(f"  {take['prefix']}: skipped ({exc})")
            continue
        if sr4 != sr12:
            continue
        sr_last = sr12

        mono4 = tr4[:, np.argmax(np.max(np.abs(tr4), axis=0))] if tr4.ndim == 2 else tr4
        n = min(len(mono4), len(tr12))
        mono4 = mono4[:n]

        # Use relaxed VAD so we get more pool chunks
        try:
            silent_regions = _run_vad(mono4, sr4, POOL_VAD_THRESHOLD)
        except Exception:
            silent_regions = []

        # Invert: collect the gaps between speech (= clean audio)
        events = sorted(silent_regions)
        boundaries = [0]
        for s, e in events:
            boundaries += [s, e]
        boundaries.append(n)

        min_len = int(POOL_MIN_SEC * sr12)
        count_before = len(pool)
        for i in range(0, len(boundaries) - 1, 2):
            s, e = boundaries[i], boundaries[i + 1]
            if e - s >= min_len:
                pool.append({"audio": tr12[s:e], "file": take["tr1_2"],
                             "start": s, "end": e})

        added = len(pool) - count_before
        total_sec = sum(len(c["audio"]) for c in pool[count_before:]) / sr12
        print(f"  {take['prefix']}: {added} chunk(s)  ({total_sec:.1f}s clean)")

    total_sec = sum(len(c["audio"]) for c in pool) / sr_last
    print(f"  Pool total: {len(pool)} chunks, {total_sec:.1f}s\n")
    return pool


# -- Verification --------------------------------------------------------------

def verify_regions(output: np.ndarray, tr4: np.ndarray, sr: int, regions: list) -> list:
    mono4 = tr4[:, np.argmax(np.max(np.abs(tr4), axis=0))] if tr4.ndim == 2 else tr4
    report = []
    for s, e in regions:
        out_mono = output[s:e].mean(axis=1) if output.ndim == 2 else output[s:e]
        ref = mono4[s:e]
        n = min(len(out_mono), len(ref))
        if n < 64:
            report.append((s / sr, e / sr, "CLEAN"))
            continue
        a, b = out_mono[:n].astype(np.float64), ref[:n].astype(np.float64)
        a_std, b_std = a.std(), b.std()
        if a_std < 1e-10 or b_std < 1e-10:
            report.append((s / sr, e / sr, "CLEAN"))
            continue
        corr = float(np.mean(((a - a.mean()) / a_std) * ((b - b.mean()) / b_std)))
        status = "CLEAN" if corr <= VERIFY_CORR_THRESH else f"WARN (corr={corr:.3f})"
        report.append((s / sr, e / sr, status))
    return report


# -- File discovery ------------------------------------------------------------

def find_takes(root: str) -> list:
    root = Path(root)
    dirs = ([root] if (root.suffix == ".TAKE" and root.is_dir())
            else list(root.rglob("*.TAKE")) + [root])
    takes = []
    for d in sorted(dirs):
        for tr4 in sorted(d.glob("*_Tr4.WAV")):
            prefix = tr4.name[:-len("_Tr4.WAV")]
            tr12 = next(iter(sorted(d.glob(f"{prefix}_Tr1_2.WAV"))), None)
            if tr12:
                takes.append({"tr4": tr4, "tr1_2": tr12, "prefix": prefix})
    return takes


# -- Per-take processing -------------------------------------------------------

def process_take(take: dict, dry_run: bool, no_bleed: bool,
                 cross_pool: list = None,
                 speaker_detector: "SpeakerDetector" = None) -> dict:
    prefix = take["prefix"]
    print(f"\n{'-' * 60}\nTake: {prefix}")

    tr4,  sr4  = sf.read(str(take["tr4"]),  always_2d=False)
    tr12, sr12 = sf.read(str(take["tr1_2"]), always_2d=True)

    if sr4 != sr12:
        print(f"  WARNING: sample rate mismatch ({sr4} vs {sr12}) - skipping")
        return {"prefix": prefix, "status": "SKIPPED", "patched": 0}

    mono4 = tr4[:, np.argmax(np.max(np.abs(tr4), axis=0))] if tr4.ndim == 2 else tr4
    n = min(len(mono4), len(tr12))
    mono4, tr12 = mono4[:n], tr12[:n]

    # Stage 1: VAD on Tr4
    print("  Detecting director speech on Tr4 (VAD)...")
    vad_regions = detect_on_tr4(mono4, sr4)
    print(f"  VAD: {len(vad_regions)} region(s)")
    for s, e in vad_regions:
        print(f"    {s/sr4:.2f}s -> {e/sr4:.2f}s")

    # Stage 2: bleed detection on Tr1_2
    # Prefer speaker model if provided; fall back to spectral fingerprint
    bleed_regions = []
    if not no_bleed:
        if speaker_detector is not None:
            print("  Scanning Tr1_2 with speaker model...")
            bleed_regions = detect_speaker_in_tr12(tr12, sr12, speaker_detector, vad_regions)
            if bleed_regions:
                print(f"  Speaker: {len(bleed_regions)} region(s)")
                for s, e in bleed_regions:
                    print(f"    {s/sr12:.2f}s -> {e/sr12:.2f}s  [speaker]")
            else:
                print("  Speaker: none detected")
        elif vad_regions:
            print("  Building director voice fingerprint...")
            fp = build_director_fingerprint(mono4, sr4, vad_regions)
            if fp is not None:
                print("  Scanning Tr1_2 for director voice bleed...")
                bleed_regions = detect_bleed_in_tr12(tr12, sr12, fp, vad_regions)
                if bleed_regions:
                    print(f"  Bleed: {len(bleed_regions)} region(s)")
                    for s, e in bleed_regions:
                        print(f"    {s/sr12:.2f}s -> {e/sr12:.2f}s  [bleed]")
                else:
                    print("  Bleed: none detected")

    all_regions = merge_regions(vad_regions, bleed_regions)

    if not all_regions:
        print("  Clean - no director speech detected.")
        return {"prefix": prefix, "status": "CLEAN", "patched": 0}

    print(f"  Total regions to patch: {len(all_regions)}")

    if dry_run:
        print("  [DRY RUN] No files written.")
        return {"prefix": prefix, "status": "DRY_RUN", "patched": len(all_regions)}

    clean_mask = build_clean_mask(mono4, sr4)

    # Mark bleed regions as dirty so they're not used as donors
    if vad_regions:
        _fp_for_mask = build_director_fingerprint(mono4, sr4, vad_regions)
        if _fp_for_mask is not None:
            _bleed_for_mask = detect_bleed_in_tr12(tr12, sr12, _fp_for_mask, vad_regions)
            for _s, _e in _bleed_for_mask:
                clean_mask[_s:_e] = False

    # Build a donor mask: exclude only the detected dirty regions themselves.
    # Everything else is fair game for fill audio - we know where the director
    # spoke, we don't need the noise-floor threshold for donor selection.
    donor_mask = np.ones(len(tr12), dtype=bool)
    for s, e in all_regions:
        donor_mask[s:e] = False

    # Find donors - returns source positions, no audio written yet
    region_donors = []
    for start, end in all_regions:
        segs = find_donor(tr12, sr12, donor_mask, start, end,
                          tr12_path=take["tr1_2"], cross_pool=cross_pool)
        region_donors.append(segs)

    # Verify by building a temporary patched buffer for correlation check
    output = tr12.copy()
    for (start, end), segs in zip(all_regions, region_donors):
        pos = start
        for seg in segs:
            seg_file = seg["file"]
            s_in, s_out = seg["start"], seg["end"]
            # Read audio from source file
            try:
                donor_audio, _ = sf.read(str(seg_file), start=s_in, stop=s_out, always_2d=True)
            except Exception:
                continue
            n = min(len(donor_audio), end - pos)
            if n <= 0:
                break
            apply_region(output, donor_audio[:n], tr12, sr12, pos, pos + n)
            pos += n

    print("  Verifying patches...")
    report = verify_regions(output, mono4, sr12, all_regions)
    n_warn = sum(1 for *_, s in report if s != "CLEAN")

    for ts, te, status in report:
        icon = "OK" if status == "CLEAN" else "!!"
        print(f"    {ts:.2f}s -> {te:.2f}s  {icon}  {status}")

    if n_warn:
        print(f"  !!  {n_warn} region(s) flagged - manual review recommended.")
    else:
        print(f"  OK  All {len(report)} region(s) verified clean.")

    # Write sidecar JSON - source positions for non-destructive Premiere edit
    import json
    patches_meta = {
        "prefix": prefix,
        "sr": sr12,
        "source_file": str(take["tr1_2"]),
        "total_frames": len(tr12),
        "regions": [
            {
                "start_samp": start,
                "end_samp": end,
                "start_sec": start / sr12,
                "end_sec": end / sr12,
                "status": status,
                "donors": [
                    {"file": str(seg["file"]) if seg["file"] else str(take["tr1_2"]),
                     "start": seg["start"],
                     "end":   seg["end"]}
                    for seg in segs
                ]
            }
            for (start, end), segs, (_, _, status)
            in zip(all_regions, region_donors, report)
        ]
    }
    json_path = take["tr1_2"].parent / (prefix + "_patches.json")
    json_path.write_text(json.dumps(patches_meta, indent=2))
    print(f"  Written: {json_path.name}")

    return {"prefix": prefix, "status": "PATCHED",
            "patched": len(all_regions), "warnings": n_warn}


# -- Main ----------------------------------------------------------------------

def main():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(
        description="Replace director speech in Tr1_2 with matched clean audio."
    )
    parser.add_argument("path", help="Shoot folder or single .TAKE folder")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect only - do not write files.")
    parser.add_argument("--no-bleed", action="store_true",
                        help="Skip the Tr1_2 bleed scan (faster, Tr4 only).")
    parser.add_argument("--speaker-model", default=None, metavar="DIR",
                        help="Path to trained speaker model folder (from train_speaker_model.py). "
                             "Uses speaker embeddings instead of spectral fingerprint for bleed detection.")
    args = parser.parse_args()

    takes = find_takes(args.path)
    if not takes:
        print(f"No Tr4 + Tr1_2 pairs found in: {args.path}")
        sys.exit(1)

    # Load speaker model if provided
    speaker_detector = None
    if args.speaker_model and not args.no_bleed:
        print(f"\nLoading speaker model from: {args.speaker_model}")
        try:
            speaker_detector = SpeakerDetector(Path(args.speaker_model))
        except Exception as e:
            print(f"  WARNING: could not load speaker model ({e}) - using spectral fingerprint")

    print(f"Found {len(takes)} take(s).")
    cross_pool = build_cross_take_pool(takes) if len(takes) > 1 else []

    results = [process_take(t, args.dry_run, args.no_bleed, cross_pool, speaker_detector)
               for t in takes]

    print(f"\n{'=' * 60}\nSummary:")
    for r in results:
        print(f"  {r['prefix']:40s}  {r['status']}  ({r.get('patched', 0)} patched)")


if __name__ == "__main__":
    main()
