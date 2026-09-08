#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from data_mind_3.metamath.parser import Database, parse_database
from data_mind_3.metamath.search import SearchConfig
from data_mind_3.metamath.verifier import verify_with_brian_metamath
from data_mind_hilbert.experiments.exp001_config import (
    ARMS,
    ARM_DESCRIPTIONS,
    ARM_MODES,
    CANDIDATE_CAP,
    CANONICAL_LOCK,
    HILBERT_BITS,
    HILBERT_WEIGHT,
    MAX_DEPTH,
    MAX_EXPANSIONS,
    MAX_FRONTIER,
    MAX_OPEN_GOALS,
    PRIMARY_ENDPOINT,
    SOURCE_SETMM_COMMIT,
    SOURCE_SETMM_SHA256,
    TIMEOUT_S,
)
from data_mind_hilbert.search import HILBERT_WEIGHT as SEARCH_HILBERT_WEIGHT
from data_mind_hilbert.search import search_target_geometric


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_holdout(path: str | Path, expected_sha: str) -> tuple[list[str], set[str]]:
    text = Path(path).read_text(encoding="utf-8")
    if sha256_text(text) != expected_sha:
        raise RuntimeError("holdout label file hash mismatch")
    labels = [line.strip() for line in text.splitlines() if line.strip()]
    return labels, set(labels)


def proof_safe_database(db: Database, holdout: set[str], target_label: str) -> Database:
    filtered = [
        a
        for a in db.assertions
        if a.kind == "$a" or a.label not in holdout or a.label == target_label
    ]
    by_label: dict[str, object] = dict(db.hypotheses)
    for assertion in filtered:
        by_label[assertion.label] = assertion
    leaked = [
        a.label
        for a in filtered
        if a.kind == "$p" and a.label in holdout and a.label != target_label
    ]
    if leaked:
        raise RuntimeError(f"held-out theorem leakage: {leaked[:5]}")
    return Database(
        constants=set(db.constants),
        variables=set(db.variables),
        hypotheses=dict(db.hypotheses),
        assertions=filtered,
        by_label=by_label,
    )


def compact_geometry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    geom = [
        row for row in rows
        if isinstance(row, dict) and row.get("actor") == "HilbertNavigator"
    ]
    if not geom:
        return {"events": 0, "sample_first": [], "sample_last": []}
    return {
        "events": len(geom),
        "sample_first": geom[:10],
        "sample_last": geom[-10:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--target-ordinal", type=int, required=True)
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--holdout-labels", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verifier", default="metamath.py")
    ap.add_argument("--lock", default=CANONICAL_LOCK)
    args = ap.parse_args()

    if SEARCH_HILBERT_WEIGHT != HILBERT_WEIGHT:
        raise RuntimeError("frozen Hilbert weight differs from search implementation")
    if sha256_file(args.setmm) != SOURCE_SETMM_SHA256:
        raise RuntimeError("set.mm source hash mismatch")

    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    if lock["source_setmm_commit"] != SOURCE_SETMM_COMMIT:
        raise RuntimeError("unexpected source set.mm commit")
    _holdout_ordered, holdout = load_holdout(
        args.holdout_labels, str(lock["holdout_labels_sha256"])
    )
    manifest = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    targets = sorted(manifest["targets"], key=lambda row: int(row["ordinal"]))
    if not 0 <= args.target_ordinal < len(targets):
        raise RuntimeError("target ordinal out of range")
    target_row = targets[args.target_ordinal]
    target_label = str(target_row["label"])
    if target_label not in holdout:
        raise RuntimeError("target not in frozen holdout")

    raw_db = parse_database(args.setmm)
    target = raw_db.target(target_label)
    statement_text = " ".join(target.statement)
    if sha256_text(statement_text + "\n") != target_row["statement_sha256"]:
        raise RuntimeError("target statement hash mismatch")
    if target_row["channel"] == "R":
        if len(target.statement) < 2 or target.statement[1] != "-.":
            raise RuntimeError("R target is not syntactically a negation")
    elif target_row["channel"] != "P":
        raise RuntimeError("unexpected channel")

    db = proof_safe_database(raw_db, holdout, target_label)
    config = SearchConfig(
        max_expansions=MAX_EXPANSIONS,
        max_depth=MAX_DEPTH,
        max_open_goals=MAX_OPEN_GOALS,
        candidate_cap=CANDIDATE_CAP,
        timeout_s=TIMEOUT_S,
        max_frontier=MAX_FRONTIER,
    )

    def verifier_callback(proof_labels: tuple[str, ...]):
        forbidden = [label for label in proof_labels if label in holdout]
        if forbidden:
            return False, {
                "accepted": False,
                "rejected_before_verifier": True,
                "reason": "candidate referenced a held-out theorem label",
                "forbidden_labels": forbidden[:20],
            }
        vr = verify_with_brian_metamath(
            Path(args.setmm),
            target_label,
            proof_labels,
            Path(args.verifier),
            timeout_s=120.0,
        )
        return vr.accepted, {
            "accepted": vr.accepted,
            "returncode": vr.returncode,
            "verifier": vr.verifier,
            "stdout_tail": vr.stdout[-2000:],
            "stderr_tail": vr.stderr[-2000:],
        }

    mode = ARM_MODES[args.arm]
    result = search_target_geometric(
        db,
        target_label,
        config,
        mode=mode,
        verify_candidate=verifier_callback,
        bits=HILBERT_BITS,
    )
    settled = result.status == "PROVED" and bool(
        (result.verification or {}).get("accepted", False)
    )

    payload: dict[str, Any] = {
        "experiment": "DATA-MIND-HILBERT-ABLATION-001",
        "scientific_run": True,
        "arm": args.arm,
        "arm_description": ARM_DESCRIPTIONS[args.arm],
        "navigation_mode": mode,
        "target_ordinal": args.target_ordinal,
        "target": target_label,
        "channel": target_row["channel"],
        "certified_target": target_row["certified_target"],
        "object_claim": target_row["object_claim"],
        "statement_sha256": target_row["statement_sha256"],
        "source_setmm_commit": SOURCE_SETMM_COMMIT,
        "source_setmm_sha256": SOURCE_SETMM_SHA256,
        "holdout_labels_sha256": lock["holdout_labels_sha256"],
        "target_manifest_selection_seed": manifest["selection_seed"],
        "proof_access_policy": (
            "parser discards theorem proof text; every non-target held-out theorem is removed "
            "from the legal search library; any candidate citing a held-out theorem is rejected "
            "before independent Metamath verification"
        ),
        "primary_endpoint": PRIMARY_ENDPOINT,
        "settled": settled,
        "status": result.status,
        "reason": result.reason,
        "expansions": result.expansions,
        "generated_children": result.generated_children,
        "elapsed_search_s": result.elapsed_s,
        "proof_labels": list(result.proof_labels),
        "proof_length": len(result.proof_labels),
        "verification": result.verification,
        "geometry": compact_geometry(result.historian),
        "config": {
            "max_expansions": MAX_EXPANSIONS,
            "timeout_s": TIMEOUT_S,
            "max_depth": MAX_DEPTH,
            "max_open_goals": MAX_OPEN_GOALS,
            "candidate_cap": CANDIDATE_CAP,
            "max_frontier": MAX_FRONTIER,
            "hilbert_bits": HILBERT_BITS,
            "hilbert_weight": HILBERT_WEIGHT,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "arm": args.arm,
        "target": target_label,
        "channel": target_row["channel"],
        "settled": settled,
        "status": result.status,
        "expansions": result.expansions,
        "elapsed_s": round(result.elapsed_s, 3),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
