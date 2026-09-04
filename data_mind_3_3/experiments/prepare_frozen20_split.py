#!/usr/bin/env python3
from __future__ import annotations

"""Reconstruct proof-free Frozen-20 split metadata in a preparation process.

This process is permitted to inspect source proofs only to reconstruct and
hash-check the already-frozen split.  It emits holdout labels and hashes, never
held-out proof text.  Scientific settlement runs happen in fresh processes.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random

import metamath as mmcore


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def raw_proof_complete(proof) -> bool:
    return bool(proof) and not any("?" in token for token in proof)


def assertion_statement(mm, label: str) -> tuple[str, ...]:
    typ, data = mm.labels[label]
    return tuple(data[3]) if typ in ("$a", "$p") else tuple(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--lock", default="benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json")
    ap.add_argument("--out-labels", required=True)
    ap.add_argument("--out-summary", required=True)
    args = ap.parse_args()

    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    actual = sha256_file(args.setmm)
    if actual != lock["source_setmm_sha256"]:
        raise RuntimeError("set.mm source hash mismatch")

    mm = mmcore.load(args.setmm, say=lambda _s: None)
    complete = [
        lab for lab in mm.order
        if mm.labels.get(lab, (None,))[0] == "$p"
        and raw_proof_complete(mm.proofs.get(lab, ()))
    ]
    if len(complete) != int(lock["complete_theorem_count"]):
        raise RuntimeError("complete theorem count mismatch")

    dec: dict[str, list[str]] = {}
    cited: set[str] = set()
    for lab in complete:
        steps = list(mm.decompress(lab, mm.proofs[lab]))
        dec[lab] = steps
        for step in steps:
            if mm.labels.get(step, (None,))[0] == "$p":
                cited.add(step)

    leaves = [lab for lab in complete if lab not in cited]
    rng = random.Random(int(lock["split_seed"]))
    shuffled = list(leaves)
    rng.shuffle(shuffled)
    holdout = shuffled[: int(lock["holdout_count"])]
    training = [lab for lab in complete if lab not in set(holdout)]
    if len(training) != int(lock["training_count"]):
        raise RuntimeError("training count mismatch")

    holdout_text = "\n".join(holdout) + "\n"
    if sha256_text(holdout_text) != lock["holdout_labels_sha256"]:
        raise RuntimeError("holdout labels hash mismatch")
    training_text = "\n".join(training) + "\n"
    if sha256_text(training_text) != lock["training_labels_sha256"]:
        raise RuntimeError("training labels hash mismatch")

    order = {label: i for i, label in enumerate(mm.order)}
    def eligible(label: str) -> bool:
        _dvs, _f, essential, statement = mm.labels[label][1]
        return not essential and 5 <= len(dec[label]) <= 30 and len(statement) <= 60 and order[label] > 500

    available = [label for label in holdout if eligible(label)]
    selected = []
    for _ in range(20):
        label = rng.choice(available)
        available.remove(label)
        selected.append(label)
    expected = [str(row["label"]) for row in sorted(lock["targets"], key=lambda r: int(r["ordinal"]))]
    if selected != expected:
        raise RuntimeError("Frozen-20 target reconstruction mismatch")
    if sha256_text("\n".join(selected) + "\n") != lock["targets_sha256"]:
        raise RuntimeError("target labels hash mismatch")

    # Recheck every frozen target statement/proof hash inside this preparation
    # process, but do not emit proof text.
    for row in lock["targets"]:
        label = str(row["label"])
        statement_text = " ".join(assertion_statement(mm, label)) + "\n"
        proof_text = " ".join(dec[label]) + "\n"
        if sha256_text(statement_text) != row["statement_sha256"]:
            raise RuntimeError(f"statement hash mismatch for {label}")
        if sha256_text(proof_text) != row["hidden_proof_sha256"]:
            raise RuntimeError(f"hidden proof hash mismatch for {label}")

    out = Path(args.out_labels)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(holdout_text, encoding="utf-8")
    summary = {
        "benchmark_name": lock["benchmark_name"],
        "source_setmm_sha256": actual,
        "split_seed": lock["split_seed"],
        "training_count": len(training),
        "holdout_count": len(holdout),
        "holdout_labels_sha256": lock["holdout_labels_sha256"],
        "targets_sha256": lock["targets_sha256"],
        "hidden_proofs_emitted": False,
        "purpose": "proof-free split metadata for DATA MIND 3.3 Experiment 001",
    }
    Path(args.out_summary).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
