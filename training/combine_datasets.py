"""
Combine current + historical training datasets into a single JSONL.

Reads:
  training/data/scripts_dataset.jsonl       (live 2026 sheet — 109 rows)
  training/data/historical_dataset.jsonl    (2023-2025 archives  — ~572 rows)

Writes:
  training/data/combined_dataset.jsonl

Deduplication: keys on (studio, female, theme) — newer entries win.
This catches the edge case where a script in the live sheet was a re-shoot
of an older archived script.

Train/eval split: 90/10 stratified by studio so each studio is fairly
represented in both splits.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def dedup_key(rec: dict) -> tuple[str, str, str]:
    return (
        rec.get("studio", ""),
        rec.get("female", "").lower(),
        rec.get("theme", "").strip().lower(),
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--current",
        type=Path,
        default=Path(__file__).parent / "data" / "scripts_dataset.jsonl",
    )
    p.add_argument(
        "--historical",
        type=Path,
        default=Path(__file__).parent / "data" / "historical_dataset.jsonl",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "data" / "combined_dataset.jsonl",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--eval-fraction", type=float, default=0.1)
    args = p.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    current = load_jsonl(args.current)
    historical = load_jsonl(args.historical)
    print(f"Loaded current:    {len(current)} records from {args.current.name}")
    print(f"Loaded historical: {len(historical)} records from {args.historical.name}")

    # Dedup with current winning on conflict
    by_key: dict[tuple[str, str, str], dict] = {}
    for rec in historical:
        by_key[dedup_key(rec)] = rec
    overwrites = 0
    for rec in current:
        k = dedup_key(rec)
        if k in by_key:
            overwrites += 1
        by_key[k] = rec
    combined = list(by_key.values())
    print(f"\nDeduped: {len(historical) + len(current)} → {len(combined)}  ({overwrites} re-shoots)")

    # Stratified split by studio
    rng = random.Random(args.seed)
    by_studio: dict[str, list[dict]] = defaultdict(list)
    for rec in combined:
        by_studio[rec.get("studio", "")].append(rec)

    train_records: list[dict] = []
    eval_records: list[dict] = []
    for studio, recs in by_studio.items():
        rng.shuffle(recs)
        n_eval = max(1, int(len(recs) * args.eval_fraction))
        eval_records.extend(recs[:n_eval])
        train_records.extend(recs[n_eval:])

    rng.shuffle(train_records)
    rng.shuffle(eval_records)

    with args.out.open("w", encoding="utf-8") as fh:
        for rec in combined:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    train_path = args.out.with_name(args.out.stem + ".train.jsonl")
    eval_path = args.out.with_name(args.out.stem + ".eval.jsonl")
    with train_path.open("w", encoding="utf-8") as fh:
        for rec in train_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with eval_path.open("w", encoding="utf-8") as fh:
        for rec in eval_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(combined)} → {args.out.name}")
    print(f"Wrote {len(train_records)} → {train_path.name}")
    print(f"Wrote {len(eval_records)} → {eval_path.name}")

    print("\n--- Per studio (combined) ---")
    studios = Counter(r["studio"] for r in combined)
    for s, c in studios.most_common():
        in_train = sum(1 for r in train_records if r["studio"] == s)
        in_eval = sum(1 for r in eval_records if r["studio"] == s)
        print(f"  {s:15s}  total={c:4d}  train={in_train:4d}  eval={in_eval:3d}")

    print("\n--- Per scene type (combined) ---")
    types = Counter(r["scene_type"] for r in combined)
    for s, c in types.most_common():
        print(f"  {s:8s}  {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
