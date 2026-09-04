#!/usr/bin/env python3
from __future__ import annotations

"""Prepare proof-free split metadata for DATA MIND 3.1 Experiment 001.

This process is allowed to inspect the frozen source proofs solely to reconstruct
and hash-check the permanent 95/5 split. It emits labels/hashes only. Settlement
runs happen in separate fresh Python processes whose parser discards proof text.
"""

import argparse
import json
from pathlib import Path

import metamath as mmcore

from data_mind_3.training.frozen20 import (
    load_lock,
    reconstruct_and_verify,
    sha256_file,
    sha256_text,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setmm", required=True)
    ap.add_argument(
        "--lock",
        default="benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json",
    )
    ap.add_argument("--out-labels", required=True)
    ap.add_argument("--out-summary", required=True)
    args = ap.parse_args()

    lock = load_lock(args.lock)
    actual = sha256_file(args.setmm)
    if actual != lock["source_setmm_sha256"]:
        raise RuntimeError(f"set.mm SHA mismatch: {actual} != {lock['source_setmm_sha256']}")

    mm = mmcore.load(args.setmm, say=lambda _s: None)
    split = reconstruct_and_verify(mm, lock)

    labels_text = "\n".join(split.holdout) + "\n"
    digest = sha256_text(labels_text)
    if digest != lock["holdout_labels_sha256"]:
        raise RuntimeError("holdout label hash mismatch after reconstruction")

    out_labels = Path(args.out_labels)
    out_labels.parent.mkdir(parents=True, exist_ok=True)
    out_labels.write_text(labels_text, encoding="utf-8")

    summary = {
        "benchmark_name": lock["benchmark_name"],
        "source_setmm_sha256": actual,
        "split_seed": lock["split_seed"],
        "training_count": len(split.training),
        "holdout_count": len(split.holdout),
        "holdout_labels_sha256": digest,
        "target_labels_sha256": lock["targets_sha256"],
        "hidden_proofs_emitted": False,
        "purpose": "proof-free split metadata for Experiment 001 settlement processes",
    }
    Path(args.out_summary).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
