#!/usr/bin/env python3
"""Build the permanent manifest for DATA-MIND set.mm Frozen-20 Benchmark 001."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import metamath
from experiments import data_mind_2_12_setmm_holdout as dm


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    source = Path(args.setmm)
    mm = metamath.load(str(source), say=lambda _s: None)
    base, split = dm.build_split(
        mm, seed=271828, holdout_fraction=0.05,
        min_target_proof_steps=5, max_target_proof_steps=30,
        max_target_statement_tokens=60,
    )
    complete = list(split["complete"])
    training = list(split["training"])
    holdout = list(split["holdout"])
    dec = split["decompressed"]
    cited = {
        step for label in complete for step in dec[label]
        if mm.labels.get(step, (None,))[0] == "$p"
    }
    leaves = [label for label in complete if label not in cited]
    rng = random.Random(271828)
    shuffled = list(leaves)
    rng.shuffle(shuffled)
    if shuffled[:len(holdout)] != holdout:
        raise RuntimeError("frozen holdout reconstruction mismatch")
    order = {label: i for i, label in enumerate(mm.order)}

    def eligible(label: str) -> bool:
        _dvs, _f, essential, statement = mm.labels[label][1]
        return (not essential and 5 <= len(dec[label]) <= 30
                and len(statement) <= 60 and order[label] > 500)

    available = [label for label in holdout if eligible(label)]
    targets = []
    for ordinal in range(20):
        label = rng.choice(available)
        available.remove(label)
        statement = " ".join(dm.assertion_statement(mm, label)) + "\n"
        proof = " ".join(dec[label]) + "\n"
        targets.append({
            "ordinal": ordinal,
            "label": label,
            "statement_sha256": digest(statement),
            "hidden_proof_sha256": digest(proof),
            "hidden_proof_steps": len(dec[label]),
            "statement_tokens": len(dm.assertion_statement(mm, label)),
        })

    training_labels = "\n".join(training) + "\n"
    training_records = "".join(
        label + "\t" + " ".join(dm.assertion_statement(mm, label)) +
        "\t" + " ".join(dec[label]) + "\n" for label in training
    )
    manifest = {
        "benchmark_name": "DATA-MIND set.mm Frozen-20 Benchmark 001",
        "architecture": dm.ARCH,
        "status_at_creation": "ordinals 0-13 completed; ordinals 14-19 launched separately",
        "source_commit": dm.DEFAULT_SOURCE_COMMIT,
        "source_sha256": dm.sha256_file(source),
        "split_seed": 271828,
        "holdout_fraction": 0.05,
        "complete_theorem_count": len(complete),
        "training_count": len(training),
        "holdout_count": len(holdout),
        "leaf_count": len(leaves),
        "holdout_policy": "random sample of reverse-citation leaves; no training proof cites a holdout label",
        "target_policy": "first 20 draws without replacement from eligible frozen holdout pool",
        "training_labels_sha256": digest(training_labels),
        "training_corpus_records_sha256": digest(training_records),
        "holdout_labels_sha256": digest("\n".join(holdout) + "\n"),
        "targets_sha256": digest("\n".join(x["label"] for x in targets) + "\n"),
        "evaluation_protocol": {
            "budget_seconds_per_target": 1800,
            "fresh_process_per_target": True,
            "holdout_proofs_redacted": True,
            "target_exposed_to_training": False,
            "acceptance": "candidate certificate must pass a fresh metamath.py verifier subprocess",
            "reported": ["status", "wall time", "attempts", "candidate proof steps", "certificate hash", "verifier result", "breadcrumb chain"],
        },
        "targets": targets,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
