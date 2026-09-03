#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from data_mind_3.training.frozen20 import train_from_files


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Train DATA MIND 3.1 learner on the frozen 95% set.mm corpus."
    )
    ap.add_argument("--setmm", required=True)
    ap.add_argument(
        "--lock",
        default="benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    artifact = train_from_files(
        setmm_path=args.setmm,
        lock_path=args.lock,
        output_path=args.out,
    )
    summary = {k: v for k, v in artifact.items() if k != "model"}
    summary["learner_backend"] = artifact["model"]["learner_backend"]
    summary["trained_theorems"] = artifact["model"]["trained_theorems"]
    summary["training_steps_processed"] = artifact["model"]["training_steps_processed"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
