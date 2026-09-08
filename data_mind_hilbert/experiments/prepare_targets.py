#!/usr/bin/env python3
from __future__ import annotations

"""Choose the proof-free 50-target P/R cohort for Hilbert Ablation 001.

The input holdout label list is reconstructed by the canonical Frozen-20 split
preparation process.  This selector reads only proof-redacted parser data.  It
never reads held-out proof text or proof labels.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random

from data_mind_3.metamath.parser import parse_database
from data_mind_hilbert.experiments.exp001_config import (
    CANONICAL_LOCK,
    P_TARGETS,
    R_TARGETS,
    SOURCE_SETMM_SHA256,
    TARGET_COUNT,
    TARGET_SELECTION_SEED,
)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--holdout-labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lock", default=CANONICAL_LOCK)
    args = ap.parse_args()

    if sha256_file(args.setmm) != SOURCE_SETMM_SHA256:
        raise RuntimeError("set.mm source hash mismatch")

    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    holdout = [
        line.strip()
        for line in Path(args.holdout_labels).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if sha256_text("\n".join(holdout) + "\n") != lock["holdout_labels_sha256"]:
        raise RuntimeError("holdout label hash mismatch")

    prior_frozen20 = {str(row["label"]) for row in lock["targets"]}
    db = parse_database(args.setmm)  # parser deliberately discards theorem proof text

    p_pool: list[str] = []
    r_pool: list[str] = []
    for label in holdout:
        if label in prior_frozen20 or label not in db.by_label:
            continue
        target = db.target(label)
        if not target.statement or target.statement[0] != "|-":
            continue
        if target.order <= 500 or len(target.statement) > 60:
            continue
        if any(h.kind == "$e" for h in target.mandatory_hypotheses):
            continue
        if len(target.statement) >= 2 and target.statement[1] == "-.":
            r_pool.append(label)
        else:
            p_pool.append(label)

    if len(p_pool) < P_TARGETS:
        raise RuntimeError(f"only {len(p_pool)} eligible P targets; need {P_TARGETS}")
    if len(r_pool) < R_TARGETS:
        raise RuntimeError(f"only {len(r_pool)} eligible R targets; need {R_TARGETS}")

    rng = random.Random(TARGET_SELECTION_SEED)
    rng.shuffle(p_pool)
    rng.shuffle(r_pool)
    selected: list[tuple[str, str]] = [
        *((label, "P") for label in p_pool[:P_TARGETS]),
        *((label, "R") for label in r_pool[:R_TARGETS]),
    ]
    rng.shuffle(selected)

    rows = []
    for ordinal, (label, channel) in enumerate(selected):
        target = db.target(label)
        statement_text = " ".join(target.statement)
        if channel == "R":
            # The certified set.mm target is literally a negation.  The object
            # claim phi is represented by removing the leading '|- -.' tokens;
            # settlement still requires a verifier-accepted proof of |- -. phi.
            object_claim = " ".join(("|-",) + target.statement[2:])
        else:
            object_claim = statement_text
        rows.append({
            "ordinal": ordinal,
            "label": label,
            "channel": channel,
            "certified_target": statement_text,
            "object_claim": object_claim,
            "statement_sha256": sha256_text(statement_text + "\n"),
        })

    if len(rows) != TARGET_COUNT:
        raise RuntimeError("target-count invariant failed")
    if sum(row["channel"] == "P" for row in rows) != P_TARGETS:
        raise RuntimeError("P-target count invariant failed")
    if sum(row["channel"] == "R" for row in rows) != R_TARGETS:
        raise RuntimeError("R-target count invariant failed")

    payload = {
        "experiment": "DATA-MIND-HILBERT-ABLATION-001",
        "selection_seed": TARGET_SELECTION_SEED,
        "source_setmm_sha256": SOURCE_SETMM_SHA256,
        "parent_holdout_sha256": lock["holdout_labels_sha256"],
        "prior_frozen20_excluded": sorted(prior_frozen20),
        "proof_text_accessed_by_this_selector": False,
        "P_count": P_TARGETS,
        "R_count": R_TARGETS,
        "targets": rows,
    }
    canonical = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    payload["manifest_sha256_without_self_hash"] = sha256_text(canonical)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "targets": len(rows),
        "P": P_TARGETS,
        "R": R_TARGETS,
        "selection_seed": TARGET_SELECTION_SEED,
        "proof_text_accessed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
