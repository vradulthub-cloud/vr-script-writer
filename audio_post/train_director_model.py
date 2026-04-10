#!/usr/bin/env python3
"""
train_director_model.py

Fine-tunes WavLM-Base+ as a binary classifier:
  1 = director voice
  0 = not director

Two-phase training:
  Phase 1 - frozen encoder, train head only        (fast, ~5 epochs)
  Phase 2 - unfreeze top 4 transformer layers      (precise, ~15 epochs)

Validation held out on a full unseen session (default: anything matching
--val-session, e.g. "RiverLynn") so we test true generalization.

Usage:
    pip install transformers accelerate
    python train_director_model.py --dataset C:\\speaker_dataset --out C:\\speaker_model

Output:
    C:\\speaker_model\\
        wavlm_director\\   ← HuggingFace model dir (load with from_pretrained)
        config.json        ← threshold + metadata for patch_director_voice.py
        val_report.txt     ← per-class metrics on validation set
"""

import argparse
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import sys
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import soundfile as sf
import scipy.signal as sig
from torch.utils.data import Dataset, DataLoader

# -- Dataset -------------------------------------------------------------------

class DirectorDataset(Dataset):
    def __init__(self, files: list, labels: list, target_sr: int = 16000,
                 seg_len_sec: float = 1.5, augment: bool = False):
        self.files      = files
        self.labels     = labels
        self.target_sr  = target_sr
        self.seg_samples = int(seg_len_sec * target_sr)
        self.augment    = augment

    def _load(self, path: Path) -> np.ndarray:
        audio, sr = sf.read(str(path), always_2d=False)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if sr != self.target_sr:
            from math import gcd
            g = gcd(sr, self.target_sr)
            audio = sig.resample_poly(audio, self.target_sr // g, sr // g)
        return audio.astype(np.float32)

    def _pad_or_trim(self, audio: np.ndarray) -> np.ndarray:
        n = self.seg_samples
        if len(audio) >= n:
            # Random crop during training
            start = random.randint(0, len(audio) - n) if self.augment else 0
            return audio[start:start + n]
        return np.pad(audio, (0, n - len(audio)))

    def _augment(self, audio: np.ndarray) -> np.ndarray:
        # Speed perturbation ±5%
        if random.random() < 0.4:
            rate = random.uniform(0.95, 1.05)
            n = int(len(audio) * rate)
            audio = sig.resample(audio, n).astype(np.float32)
        # Gaussian noise
        if random.random() < 0.3:
            audio = audio + np.random.randn(len(audio)).astype(np.float32) * 0.003
        # Volume jitter
        if random.random() < 0.4:
            audio = audio * random.uniform(0.7, 1.3)
        return np.clip(audio, -1.0, 1.0)

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        audio = self._load(self.files[idx])
        if self.augment:
            audio = self._augment(audio)
        audio = self._pad_or_trim(audio)
        # Normalize
        rms = np.sqrt(np.mean(audio ** 2))
        if rms > 1e-6:
            audio = audio / (rms * 10)
        return torch.from_numpy(audio), torch.tensor(self.labels[idx], dtype=torch.float32)


# -- Model ---------------------------------------------------------------------

class DirectorClassifier(nn.Module):
    def __init__(self, wavlm_model):
        super().__init__()
        self.wavlm = wavlm_model
        hidden = wavlm_model.config.hidden_size  # 768 for base
        self.head = nn.Sequential(
            nn.Linear(hidden, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
        )

    def forward(self, input_values, attention_mask=None):
        out = self.wavlm(input_values, attention_mask=attention_mask)
        # Mean-pool over time
        hidden = out.last_hidden_state.mean(dim=1)
        return self.head(hidden).squeeze(-1)

    def freeze_encoder(self):
        for p in self.wavlm.parameters():
            p.requires_grad = False

    def unfreeze_top_layers(self, n: int = 4):
        # Unfreeze the top N transformer layers + feature projection
        layers = self.wavlm.encoder.layers
        for layer in layers[-n:]:
            for p in layer.parameters():
                p.requires_grad = True
        for p in self.wavlm.feature_projection.parameters():
            p.requires_grad = True


# -- Train / eval loops --------------------------------------------------------

def run_epoch(model, loader, optimizer, device, threshold=0.5, train=True):
    model.train(train)
    total_loss = 0.0
    tp = fp = tn = fn = 0
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([2.0]).to(device))

    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)
            if train:
                optimizer.zero_grad()
            logits = model(inputs)
            loss = criterion(logits, labels)
            if train:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total_loss += loss.item()
            preds = (torch.sigmoid(logits) >= threshold).float()
            tp += ((preds == 1) & (labels == 1)).sum().item()
            fp += ((preds == 1) & (labels == 0)).sum().item()
            tn += ((preds == 0) & (labels == 0)).sum().item()
            fn += ((preds == 0) & (labels == 1)).sum().item()

    precision = tp / (tp + fp + 1e-8)
    recall    = tp / (tp + fn + 1e-8)
    f1        = 2 * precision * recall / (precision + recall + 1e-8)
    acc       = (tp + tn) / (tp + fp + tn + fn + 1e-8)
    return total_loss / len(loader), f1, precision, recall, acc


def find_threshold(model, loader, device):
    """Find optimal decision threshold on validation set."""
    model.eval()
    all_scores, all_labels = [], []
    with torch.no_grad():
        for inputs, labels in loader:
            logits = model(inputs.to(device))
            scores = torch.sigmoid(logits).cpu().numpy()
            all_scores.extend(scores.tolist())
            all_labels.extend(labels.numpy().tolist())

    best_f1, best_thresh = 0, 0.5
    for t in np.arange(0.1, 0.95, 0.01):
        preds = [1 if s >= t else 0 for s in all_scores]
        tp = sum(p == 1 and l == 1 for p, l in zip(preds, all_labels))
        fp = sum(p == 1 and l == 0 for p, l in zip(preds, all_labels))
        fn = sum(p == 0 and l == 1 for p, l in zip(preds, all_labels))
        pr = tp / (tp + fp + 1e-8)
        rc = tp / (tp + fn + 1e-8)
        f1 = 2 * pr * rc / (pr + rc + 1e-8)
        if f1 > best_f1:
            best_f1, best_thresh = f1, float(t)
    return best_thresh, best_f1


# -- Main ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="speaker_dataset")
    ap.add_argument("--out",     default="speaker_model")
    ap.add_argument("--val-session", default="RiverLynn",
                    help="Hold out files whose path contains this string for validation")
    ap.add_argument("--epochs-p1", type=int, default=5,   help="Phase 1 epochs (frozen encoder)")
    ap.add_argument("--epochs-p2", type=int, default=15,  help="Phase 2 epochs (top layers unfrozen)")
    ap.add_argument("--batch",     type=int, default=16)
    ap.add_argument("--lr-p1",     type=float, default=3e-4)
    ap.add_argument("--lr-p2",     type=float, default=5e-5)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory // 1073741824}GB")

    dataset_dir = Path(args.dataset)
    out_dir     = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # -- Load file lists --
    dir_files   = sorted((dataset_dir / "director").glob("*.wav"))
    other_files = sorted((dataset_dir / "other").glob("*.wav"))

    if not dir_files:
        print(f"No director segments found in {dataset_dir}/director/")
        print("Run build_speaker_dataset.py first.")
        sys.exit(1)

    print(f"\nDataset:")
    print(f"  Director : {len(dir_files)} segments")
    print(f"  Other    : {len(other_files)} segments")

    # -- Train/val split by session --
    val_kw = args.val_session.lower()
    train_files, train_labels = [], []
    val_files,   val_labels   = [], []

    for f in dir_files:
        if val_kw in str(f).lower():
            val_files.append(f);   val_labels.append(1)
        else:
            train_files.append(f); train_labels.append(1)

    for f in other_files:
        if val_kw in str(f).lower():
            val_files.append(f);   val_labels.append(0)
        else:
            train_files.append(f); train_labels.append(0)

    print(f"\nSplit (held-out session: '{args.val_session}'):")
    print(f"  Train: {len(train_files)} segments  "
          f"({sum(train_labels)} pos / {len(train_files)-sum(train_labels)} neg)")
    print(f"  Val:   {len(val_files)} segments  "
          f"({sum(val_labels)} pos / {len(val_files)-sum(val_labels)} neg)")

    if not val_files:
        print(f"WARNING: no val files matched '{args.val_session}' - using 10% random split")
        n_val = max(20, len(train_files) // 10)
        idx = random.sample(range(len(train_files)), n_val)
        idx_set = set(idx)
        val_files   = [train_files[i] for i in idx]
        val_labels  = [train_labels[i] for i in idx]
        train_files = [f for i, f in enumerate(train_files) if i not in idx_set]
        train_labels= [l for i, l in enumerate(train_labels) if i not in idx_set]

    train_ds = DirectorDataset(train_files, train_labels, augment=True)
    val_ds   = DirectorDataset(val_files,   val_labels,   augment=False)
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True,  num_workers=4, pin_memory=True)
    val_dl   = DataLoader(val_ds,   batch_size=args.batch, shuffle=False, num_workers=2, pin_memory=True)

    # -- Load WavLM --
    print("\nLoading WavLM-Base+...")
    from transformers import WavLMModel
    wavlm = WavLMModel.from_pretrained("microsoft/wavlm-base-plus")
    model = DirectorClassifier(wavlm).to(device)

    total_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"Model: {total_params:.0f}M parameters")

    # -- Phase 1: frozen encoder ----------------------------------------------
    print(f"\n{'-'*55}")
    print(f"Phase 1 - frozen encoder, training head only ({args.epochs_p1} epochs)")
    print(f"{'-'*55}")
    model.freeze_encoder()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad) / 1e6
    print(f"Trainable: {trainable:.1f}M params")

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr_p1
    )
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=args.lr_p1,
        steps_per_epoch=len(train_dl), epochs=args.epochs_p1
    )

    best_val_f1 = 0.0
    for epoch in range(1, args.epochs_p1 + 1):
        tr_loss, tr_f1, tr_pr, tr_rc, tr_acc = run_epoch(model, train_dl, optimizer, device, train=True)
        scheduler.step()
        vl_loss, vl_f1, vl_pr, vl_rc, vl_acc = run_epoch(model, val_dl,   optimizer, device, train=False)
        print(f"  P1 ep{epoch:02d}  train loss={tr_loss:.3f} f1={tr_f1:.3f}  "
              f"val loss={vl_loss:.3f} f1={vl_f1:.3f} pr={vl_pr:.3f} rc={vl_rc:.3f}")
        if vl_f1 > best_val_f1:
            best_val_f1 = vl_f1
            torch.save(model.state_dict(), out_dir / "best_model.pt")

    # -- Phase 2: unfreeze top layers -----------------------------------------
    print(f"\n{'-'*55}")
    print(f"Phase 2 - top 4 WavLM layers unfrozen ({args.epochs_p2} epochs)")
    print(f"{'-'*55}")
    model.unfreeze_top_layers(4)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad) / 1e6
    print(f"Trainable: {trainable:.1f}M params")

    optimizer = torch.optim.AdamW([
        {"params": model.head.parameters(),          "lr": args.lr_p1},
        {"params": filter(lambda p: p.requires_grad,
                          model.wavlm.parameters()), "lr": args.lr_p2},
    ])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs_p2, eta_min=1e-6
    )

    for epoch in range(1, args.epochs_p2 + 1):
        tr_loss, tr_f1, tr_pr, tr_rc, tr_acc = run_epoch(model, train_dl, optimizer, device, train=True)
        scheduler.step()
        vl_loss, vl_f1, vl_pr, vl_rc, vl_acc = run_epoch(model, val_dl,   optimizer, device, train=False)
        print(f"  P2 ep{epoch:02d}  train loss={tr_loss:.3f} f1={tr_f1:.3f}  "
              f"val loss={vl_loss:.3f} f1={vl_f1:.3f} pr={vl_pr:.3f} rc={vl_rc:.3f}")
        if vl_f1 > best_val_f1:
            best_val_f1 = vl_f1
            torch.save(model.state_dict(), out_dir / "best_model.pt")
            print(f"  ✓ new best val F1: {best_val_f1:.4f}")

    # -- Load best, calibrate threshold ---------------------------------------
    print(f"\nLoading best checkpoint (val F1={best_val_f1:.4f})...")
    model.load_state_dict(torch.load(out_dir / "best_model.pt"))
    threshold, thresh_f1 = find_threshold(model, val_dl, device)
    print(f"Calibrated threshold: {threshold:.2f}  (F1={thresh_f1:.4f})")

    # -- Save model ------------------------------------------------------------
    model_save_dir = out_dir / "wavlm_director"
    model_save_dir.mkdir(exist_ok=True)
    # Save WavLM config + weights together
    model.wavlm.save_pretrained(str(model_save_dir / "wavlm"))
    torch.save(model.head.state_dict(), model_save_dir / "head.pt")

    config = {
        "model_type": "wavlm_director",
        "wavlm_path": str(model_save_dir / "wavlm"),
        "head_path":  str(model_save_dir / "head.pt"),
        "threshold":  threshold,
        "val_f1":     thresh_f1,
        "n_train":    len(train_files),
        "n_val":      len(val_files),
        "val_session": args.val_session,
    }
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Val report
    report_lines = [
        f"Val session (held out): {args.val_session}",
        f"Best val F1:  {best_val_f1:.4f}",
        f"Threshold:    {threshold:.2f}",
        f"Threshold F1: {thresh_f1:.4f}",
        f"Train set:    {len(train_files)} segments",
        f"Val set:      {len(val_files)} segments",
    ]
    (out_dir / "val_report.txt").write_text("\n".join(report_lines))

    print(f"\n{'='*55}")
    print(f"Model saved: {out_dir}")
    print(f"Val F1:      {thresh_f1:.4f}")
    print(f"Threshold:   {threshold:.2f}")
    print(f"\nNext:")
    print(f"  python patch_director_voice.py --speaker-model {out_dir} /path/to/session")


if __name__ == "__main__":
    main()
