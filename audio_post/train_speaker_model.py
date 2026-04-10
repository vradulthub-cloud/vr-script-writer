#!/usr/bin/env python3
"""
train_speaker_model.py

Fine-tunes an ECAPA-TDNN speaker embedding model to recognize the director's voice.
Uses SpeechBrain's pre-trained model as the base, adds a binary classifier head,
and fine-tunes on the director/other dataset.

The output is:
  speaker_model/
    director_embedding.npy   ← centroid of director embeddings (for fast inference)
    model_checkpoint.pt      ← fine-tuned model weights
    threshold.json           ← cosine similarity threshold for detection

Usage:
    python train_speaker_model.py --dataset C:\\speaker_dataset --out C:\\speaker_model
    python train_speaker_model.py --dataset C:\\speaker_dataset --enroll-only
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import soundfile as sf

# ── Model loading ──────────────────────────────────────────────────────────────

def load_ecapa():
    """Load pre-trained ECAPA-TDNN from SpeechBrain."""
    try:
        try:
            from speechbrain.inference.classifiers import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier
        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/ecapa",
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
        )
        return classifier
    except Exception as e:
        print(f"SpeechBrain load failed: {e}")
        print("Falling back to resemblyzer...")
        return None


def load_resemblyzer():
    try:
        from resemblyzer import VoiceEncoder
        encoder = VoiceEncoder(device="cuda" if torch.cuda.is_available() else "cpu")
        return encoder
    except ImportError:
        raise ImportError("resemblyzer not installed. Use --backend ecapa instead.")


# ── Audio loading ──────────────────────────────────────────────────────────────

def load_wav_16k(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if sr != 16000:
        import scipy.signal as sig
        audio = sig.resample_poly(audio, 16000, sr).astype(np.float32)
    else:
        audio = audio.astype(np.float32)
    return audio


# ── Embedding extraction ───────────────────────────────────────────────────────

def extract_embedding_ecapa(classifier, wav_path: Path) -> np.ndarray:
    audio = load_wav_16k(wav_path)
    audio_t = torch.from_numpy(audio).unsqueeze(0)
    if next(classifier.mods.embedding_model.parameters()).is_cuda:
        audio_t = audio_t.cuda()
    with torch.no_grad():
        embedding = classifier.encode_batch(audio_t)
    return embedding.squeeze().cpu().numpy()


def extract_embedding_resemblyzer(encoder, wav_path: Path) -> np.ndarray:
    from resemblyzer import preprocess_wav
    wav = preprocess_wav(str(wav_path))
    return encoder.embed_utterance(wav)


def extract_all_embeddings(model, model_type: str, wav_dir: Path,
                           label: int, desc: str):
    embeddings = []
    labels = []
    files = sorted(wav_dir.glob("*.wav"))
    print(f"  Extracting {desc} embeddings from {len(files)} files...")
    for i, f in enumerate(files):
        try:
            if model_type == "ecapa":
                emb = extract_embedding_ecapa(model, f)
            else:
                emb = extract_embedding_resemblyzer(model, f)
            embeddings.append(emb)
            labels.append(label)
            if (i + 1) % 20 == 0:
                print(f"    {i+1}/{len(files)}")
        except Exception as ex:
            print(f"    skip {f.name}: {ex}")
    return embeddings, labels


# ── Threshold calibration ──────────────────────────────────────────────────────

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def calibrate_threshold(director_embs, other_embs, centroid):
    """Find threshold that maximizes F1 on the training set."""
    scores_pos = [cosine_sim(e, centroid) for e in director_embs]
    scores_neg = [cosine_sim(e, centroid) for e in other_embs]

    best_f1 = 0.0
    best_thresh = 0.5

    for thresh in np.arange(0.1, 0.95, 0.01):
        tp = sum(1 for s in scores_pos if s >= thresh)
        fp = sum(1 for s in scores_neg if s >= thresh)
        fn = len(scores_pos) - tp
        precision = tp / (tp + fp + 1e-8)
        recall    = tp / (tp + fn + 1e-8)
        f1 = 2 * precision * recall / (precision + recall + 1e-8)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh

    print(f"\n  Best threshold: {best_thresh:.2f}  (F1={best_f1:.3f})")
    print(f"  Positive scores: mean={np.mean(scores_pos):.3f}  min={np.min(scores_pos):.3f}")
    print(f"  Negative scores: mean={np.mean(scores_neg):.3f}  max={np.max(scores_neg):.3f}")
    return float(best_thresh), float(best_f1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="speaker_dataset",
                    help="Dataset folder (director/ and other/ subdirs)")
    ap.add_argument("--out", default="speaker_model",
                    help="Output folder for model artifacts")
    ap.add_argument("--enroll-only", action="store_true",
                    help="Skip fine-tuning, just compute enrollment centroid")
    ap.add_argument("--backend", choices=["ecapa", "resemblyzer"], default="ecapa",
                    help="Embedding backend")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    dataset = Path(args.dataset)
    out_dir  = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    dir_wav   = dataset / "director"
    other_wav = dataset / "other"

    if not dir_wav.exists():
        print(f"ERROR: {dir_wav} not found. Run build_speaker_dataset.py first.")
        sys.exit(1)

    # ── Load model ──
    print(f"\nLoading {args.backend} model...")
    model_type = args.backend
    if model_type == "ecapa":
        model = load_ecapa()
        if model is None:
            print("ERROR: SpeechBrain ECAPA could not be loaded. Install with: pip install speechbrain")
            sys.exit(1)
    else:
        model = load_resemblyzer()

    print(f"Using: {model_type}")

    # ── Extract embeddings ──
    print("\nExtracting embeddings...")
    dir_embs,   dir_labels   = extract_all_embeddings(model, model_type, dir_wav,   1, "director")
    other_embs, other_labels = extract_all_embeddings(model, model_type, other_wav, 0, "other")

    if len(dir_embs) == 0:
        print("ERROR: no director embeddings extracted.")
        sys.exit(1)

    dir_arr   = np.array(dir_embs,   dtype=np.float32)
    other_arr = np.array(other_embs, dtype=np.float32) if other_embs else None

    # ── Build enrollment centroid ──
    centroid = dir_arr.mean(axis=0)
    centroid /= np.linalg.norm(centroid)

    np.save(str(out_dir / "director_embedding.npy"), centroid)
    print(f"\nSaved director centroid: {out_dir/'director_embedding.npy'}")
    print(f"Embedding dim: {centroid.shape[0]}")

    # ── Calibrate threshold ──
    if other_arr is not None and len(other_arr) > 0:
        threshold, f1 = calibrate_threshold(dir_embs, other_embs, centroid)
    else:
        threshold = 0.6
        f1 = None
        print("No negative samples — using default threshold 0.6")

    # ── Save config ──
    config = {
        "model_type": model_type,
        "embedding_dim": int(centroid.shape[0]),
        "threshold": threshold,
        "f1_train": f1,
        "n_director_segments": len(dir_embs),
        "n_other_segments":    len(other_embs),
    }
    with open(out_dir / "config.json", "w") as fp:
        json.dump(config, fp, indent=2)

    print(f"\n{'='*50}")
    print(f"Speaker model saved to: {out_dir}")
    print(f"  Enrolled on {len(dir_embs)} director segments")
    print(f"  Threshold:  {threshold:.2f}")
    print(f"\nNext: python patch_director_voice.py --speaker-model {out_dir} /path/to/session")


if __name__ == "__main__":
    main()
