from __future__ import annotations

"""Reconstruct and train on DATA-MIND set.mm Frozen-20 Benchmark 001.

This module deliberately separates *benchmark reconstruction/training* from
settlement runtime.  It reads the original frozen set.mm only in the training
process, verifies the permanent 95/5 split against immutable hashes, and emits
a learner artifact.  A settlement process must load a proof-redacted/search
representation and must not receive hidden held-out proofs.

The learner implemented here is the existing 2.12 count-prior training method,
renamed explicitly as ``setmm_count_priors_v1`` for provenance.  It is a
DEVELOPMENT learner backend, not a silent definition of DATA MIND 3.1.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

import metamath as mmcore

LEARNER_BACKEND = "setmm_count_priors_v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_lock(path: str | Path) -> dict[str, Any]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("benchmark_name") != "DATA-MIND set.mm Frozen-20 Benchmark 001":
        raise RuntimeError("unexpected benchmark lock")
    targets = obj.get("targets")
    if not isinstance(targets, list) or len(targets) != 20:
        raise RuntimeError("Frozen-20 lock must contain exactly 20 targets")
    labels = [row.get("label") for row in targets]
    if len(set(labels)) != 20:
        raise RuntimeError("Frozen-20 target labels must be unique")
    return obj


def raw_proof_complete(proof: Sequence[str]) -> bool:
    return bool(proof) and not any("?" in token for token in proof)


def assertion_statement(mm: mmcore.MM, label: str) -> tuple[str, ...]:
    typ, data = mm.labels[label]
    if typ in ("$a", "$p"):
        return tuple(data[3])
    return tuple(data)


def decompressed(mm: mmcore.MM, label: str) -> list[str]:
    return list(mm.decompress(label, mm.proofs[label]))


@dataclass
class FrozenSplit:
    complete: list[str]
    training: list[str]
    holdout: list[str]
    target_labels: list[str]
    decompressed_proofs: dict[str, list[str]]

    def training_records_text(self, mm: mmcore.MM) -> str:
        return "".join(
            label
            + "\t"
            + " ".join(assertion_statement(mm, label))
            + "\t"
            + " ".join(self.decompressed_proofs[label])
            + "\n"
            for label in self.training
        )


def reconstruct_and_verify(mm: mmcore.MM, lock: Mapping[str, Any]) -> FrozenSplit:
    """Rebuild the permanent 95/5 split and fail on any mismatch."""

    complete = [
        lab
        for lab in mm.order
        if mm.labels.get(lab, (None,))[0] == "$p"
        and raw_proof_complete(mm.proofs.get(lab, ()))
    ]
    if len(complete) != int(lock["complete_theorem_count"]):
        raise RuntimeError(
            f"complete theorem count mismatch: {len(complete)} != "
            f"{lock['complete_theorem_count']}"
        )

    dec: dict[str, list[str]] = {}
    cited_theorems: set[str] = set()
    for lab in complete:
        steps = decompressed(mm, lab)
        dec[lab] = steps
        for step in steps:
            if mm.labels.get(step, (None,))[0] == "$p":
                cited_theorems.add(step)

    leaves = [lab for lab in complete if lab not in cited_theorems]
    holdout_n = int(lock["holdout_count"])
    if holdout_n != max(1, int(round(len(complete) * float(lock["holdout_fraction"])))):
        raise RuntimeError("holdout count/fraction mismatch")
    if len(leaves) < holdout_n:
        raise RuntimeError("dependency-safe leaf pool is too small")

    seed = int(lock["split_seed"])
    rng = random.Random(seed)
    shuffled = list(leaves)
    rng.shuffle(shuffled)
    holdout = shuffled[:holdout_n]
    holdout_set = set(holdout)
    training = [lab for lab in complete if lab not in holdout_set]

    if len(training) != int(lock["training_count"]):
        raise RuntimeError("training count mismatch")

    for lab in training:
        leak = next((step for step in dec[lab] if step in holdout_set), None)
        if leak is not None:
            raise RuntimeError(f"training proof {lab} cites held-out theorem {leak}")

    training_labels_text = "\n".join(training) + "\n"
    holdout_labels_text = "\n".join(holdout) + "\n"
    if sha256_text(training_labels_text) != lock["training_labels_sha256"]:
        raise RuntimeError("training label hash mismatch")
    if sha256_text(holdout_labels_text) != lock["holdout_labels_sha256"]:
        raise RuntimeError("holdout label hash mismatch")

    order = {label: i for i, label in enumerate(mm.order)}

    def eligible(label: str) -> bool:
        _dvs, _f, essential, statement = mm.labels[label][1]
        return (
            not essential
            and 5 <= len(dec[label]) <= 30
            and len(statement) <= 60
            and order[label] > 500
        )

    available = [label for label in holdout if eligible(label)]
    selected: list[str] = []
    for _ordinal in range(20):
        label = rng.choice(available)
        available.remove(label)
        selected.append(label)

    expected_targets = sorted(lock["targets"], key=lambda row: int(row["ordinal"]))
    expected_labels = [str(row["label"]) for row in expected_targets]
    if selected != expected_labels:
        raise RuntimeError(
            "Frozen-20 target reconstruction mismatch: "
            f"computed={selected!r} expected={expected_labels!r}"
        )
    if sha256_text("\n".join(selected) + "\n") != lock["targets_sha256"]:
        raise RuntimeError("target label hash mismatch")

    for row in expected_targets:
        label = str(row["label"])
        statement_text = " ".join(assertion_statement(mm, label)) + "\n"
        proof_text = " ".join(dec[label]) + "\n"
        if sha256_text(statement_text) != row["statement_sha256"]:
            raise RuntimeError(f"statement hash mismatch for {label}")
        if sha256_text(proof_text) != row["hidden_proof_sha256"]:
            raise RuntimeError(f"hidden proof hash mismatch for {label}")

    split = FrozenSplit(complete, training, holdout, selected, dec)
    records_text = split.training_records_text(mm)
    if sha256_text(records_text) != lock["training_corpus_records_sha256"]:
        raise RuntimeError("training corpus record hash mismatch")
    return split


def train_count_priors(
    mm: mmcore.MM,
    training: Sequence[str],
    dec: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Train the explicitly named legacy count-prior learner backend.

    Every one of the 45,410 frozen training theorem labels is inspected.  A
    theorem whose decompressed proof contains no $a/$p assertion step has no
    event that this particular assertion-prior learner can count; those cases
    are reported explicitly rather than silently disappearing from the total.
    """

    final_counts: Counter[str] = Counter()
    premise_counts: Counter[str] = Counter()
    token_final: dict[str, Counter[str]] = defaultdict(Counter)
    used = 0
    step_total = 0
    skipped: list[dict[str, Any]] = []
    for lab in training:
        steps = list(dec[lab])
        if not steps:
            skipped.append({"label": lab, "reason": "empty_decompressed_proof"})
            continue
        assertion_steps = [
            s for s in steps if mm.labels.get(s, (None,))[0] in ("$a", "$p")
        ]
        if not assertion_steps:
            skipped.append({
                "label": lab,
                "reason": "no_assertion_step_for_count_prior_backend",
                "decompressed_step_count": len(steps),
            })
            continue
        final = assertion_steps[-1]
        final_counts[final] += 1
        premise_counts.update(assertion_steps)
        stat = assertion_statement(mm, lab)
        for token in set(stat):
            if token in mm.constants:
                token_final[token][final] += 1
        used += 1
        step_total += len(steps)

    return {
        "learner_backend": LEARNER_BACKEND,
        "training_examples_seen": len(training),
        "training_examples_with_learnable_assertion_event": used,
        "training_examples_without_learnable_assertion_event": len(skipped),
        "skipped_training_examples": skipped,
        "training_steps_processed_for_used_examples": step_total,
        "final_counts": dict(final_counts),
        "premise_counts": dict(premise_counts),
        "token_final": {token: dict(counts) for token, counts in token_final.items()},
    }


def train_from_files(
    *,
    setmm_path: str | Path,
    lock_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    lock = load_lock(lock_path)
    actual_source_sha = sha256_file(setmm_path)
    if actual_source_sha != lock["source_setmm_sha256"]:
        raise RuntimeError(
            f"set.mm SHA-256 mismatch: {actual_source_sha} != "
            f"{lock['source_setmm_sha256']}"
        )

    mm = mmcore.load(str(setmm_path), say=lambda _s: None)
    split = reconstruct_and_verify(mm, lock)
    model = train_count_priors(mm, split.training, split.decompressed_proofs)

    artifact = {
        "artifact_type": "DATA_MIND_3_1_TRAINED_LEARNER",
        "architecture_snapshot_sha256": lock["architecture_snapshot_sha256"],
        "benchmark_name": lock["benchmark_name"],
        "benchmark_source_commit": lock["benchmark_source_commit"],
        "source_setmm_commit": lock["source_setmm_commit"],
        "source_setmm_sha256": actual_source_sha,
        "split_seed": lock["split_seed"],
        "training_count": len(split.training),
        "holdout_count": len(split.holdout),
        "training_labels_sha256": lock["training_labels_sha256"],
        "training_corpus_records_sha256": lock["training_corpus_records_sha256"],
        "holdout_labels_sha256": lock["holdout_labels_sha256"],
        "target_labels_sha256": lock["targets_sha256"],
        "target_labels": list(split.target_labels),
        "heldout_proofs_emitted": False,
        "heldout_proofs_used_for_training": False,
        "target_exposed_to_training": False,
        "model": model,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
    return artifact
