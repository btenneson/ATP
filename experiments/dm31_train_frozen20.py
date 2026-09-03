#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from data_mind_3.training.frozen20 import train_from_files


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Train the explicit development learner on the frozen 95% set.mm corpus."
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
    model = artifact["model"]
    summary = {k: v for k, v in artifact.items() if k != "model"}
    summary.update({
        "learner_backend": model["learner_backend"],
        "training_examples_seen": model["training_examples_seen"],
        "training_examples_with_learnable_assertion_event": model[
            "training_examples_with_learnable_assertion_event"
        ],
        "training_examples_without_learnable_assertion_event": model[
            "training_examples_without_learnable_assertion_event"
        ],
        "skipped_training_examples": model["skipped_training_examples"],
        "training_steps_processed_for_used_examples": model[
            "training_steps_processed_for_used_examples"
        ],
    })
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
