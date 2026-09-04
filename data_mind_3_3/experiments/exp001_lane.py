#!/usr/bin/env python3
from __future__ import annotations

"""One fresh scientific lane for DATA MIND 3.3 Experiment 001.

Each invocation runs exactly one treatment arm on exactly one Frozen-20 target.
The settlement process receives proof-redacted Metamath structure plus the
proof-free holdout-label list. Hidden held-out proof text is not an input.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from data_mind_3.metamath.parser import Database, parse_database
from data_mind_3.metamath.search import SearchConfig
from data_mind_3.metamath.verifier import verify_with_brian_metamath
from data_mind_3_3.costs import account_run_cost
from data_mind_3_3.metamath.causal_bridge import (
    CausalDreamerController,
    search_target_with_causal_dreamer,
)
from data_mind_3_3.promotion import PROMOTION_DELTAS
from data_mind_3_3.experiments.exp001_config import (
    ARMS,
    ARM_ACCESS_BITS,
    CANDIDATE_CAP,
    CONTROL_INTERVAL,
    EXPERIMENT_ID,
    EXPERIMENT_SEED,
    MAX_DEPTH,
    MAX_EXPANSIONS,
    MAX_FRONTIER,
    MAX_OPEN_GOALS,
    ORACLE_THROTTLES,
    PROFESSOR_INTERVAL,
    PROMOTION_THROTTLE,
    TIMEOUT_S,
    controller_for_exp001,
    dreamer_for_arm,
)


CANONICAL_LOCK = "benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json"
ORACLE_SEMANTICS = "data_mind_3_3/ORACLE_SEMANTICS_FROZEN_001.md"
ORACLE_SEMANTICS_IMPLEMENTATION_BLOB = "2342bba42523a00787c1c0d0888001a599e2e4c4"
BENCHMARK_LOCK_BLOB = "2725ae80c22bf0dd74a38ed1ba4ffb21a7ad7b9c"
PROMOTION_MAX_ABS_DELTA = 0.05


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
    if len(labels) != len(set(labels)):
        raise RuntimeError("holdout label file contains duplicates")
    return labels, set(labels)


def proof_safe_database(db: Database, holdout: set[str], target_label: str) -> Database:
    """Remove every non-target held-out theorem from the legal search library."""
    filtered = [
        a
        for a in db.assertions
        if a.kind == "$a" or a.label not in holdout or a.label == target_label
    ]
    by_label: dict[str, object] = dict(db.hypotheses)
    for assertion in filtered:
        by_label[assertion.label] = assertion
    if target_label not in by_label:
        raise RuntimeError("target disappeared while redacting held-out theorem labels")
    leaked = [
        a.label
        for a in filtered
        if a.kind == "$p" and a.label in holdout and a.label != target_label
    ]
    if leaked:
        raise RuntimeError(f"held-out theorem leakage into legal library: {leaked[:5]}")
    return Database(
        constants=set(db.constants),
        variables=set(db.variables),
        hypotheses=dict(db.hypotheses),
        assertions=filtered,
        by_label=by_label,
    )


def reflection_dict(dreamer) -> dict[str, Any]:
    reflection = dreamer.reflection()
    return {
        "access_bits": list(reflection.access_bits),
        "proposals_created": reflection.proposals_created,
        "promotions": reflection.promotions,
        "promotion_rejections": reflection.promotion_rejections,
        "oracle_state": [
            {
                "facet": row.facet.value,
                "enabled": row.enabled,
                "calls": row.calls,
                "remaining_calls": row.remaining_calls,
                "last_call_step": row.last_call_step,
                "total_reported_cost": row.total_reported_cost,
                "skipped_disabled": row.skipped_disabled,
                "skipped_throttled": row.skipped_throttled,
                "proposals_supported": row.proposals_supported,
                "verified_contributions": row.verified_contributions,
                "empirical_yield": row.empirical_yield,
            }
            for row in reflection.oracle_state
        ],
    }


def bridge_history_dict(bridge: CausalDreamerController) -> list[dict[str, Any]]:
    return [
        {
            "proposal_id": row.proposal_id,
            "expansion": row.expansion,
            "action": row.action,
            "promotion_requested": row.promotion_requested,
            "promotion_granted": row.promotion_granted,
            "execution_applied": row.execution_applied,
            "execution_reason": row.execution_reason,
        }
        for row in bridge.history
    ]


def executor_history_dict(bridge: CausalDreamerController) -> list[dict[str, Any]]:
    return [
        {
            "proposal_id": row.proposal_id,
            "action": row.action.value,
            "applied": row.applied,
            "reason": row.reason,
            "creativity_before": row.creativity_before,
            "creativity_after": row.creativity_after,
            "deltas": row.deltas,
            "reported_cost": row.reported_cost,
        }
        for row in bridge.executor.history
    ]


def compact_historian(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep = {
        "CreativityController",
        "Professor",
        "P1",
        "Sentinel",
        "Verifier",
        "Child",
    }
    return [row for row in rows if isinstance(row, dict) and row.get("actor") in keep]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--target-ordinal", type=int, required=True)
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--holdout-labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verifier", default="metamath.py")
    ap.add_argument("--lock", default=CANONICAL_LOCK)
    args = ap.parse_args()

    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    if lock.get("benchmark_name") != "DATA-MIND set.mm Frozen-20 Benchmark 001":
        raise RuntimeError("unexpected benchmark lock")
    source_sha = sha256_file(args.setmm)
    if source_sha != lock["source_setmm_sha256"]:
        raise RuntimeError("set.mm source hash does not match benchmark lock")

    _holdout_ordered, holdout = load_holdout(
        args.holdout_labels, str(lock["holdout_labels_sha256"])
    )
    targets = sorted(lock["targets"], key=lambda row: int(row["ordinal"]))
    if not 0 <= args.target_ordinal < len(targets):
        raise RuntimeError("target ordinal out of range")
    target_label = str(targets[args.target_ordinal]["label"])
    if target_label not in holdout:
        raise RuntimeError("frozen target is not present in reconstructed holdout")

    db = proof_safe_database(parse_database(args.setmm), holdout, target_label)
    config = SearchConfig(
        max_expansions=MAX_EXPANSIONS,
        max_depth=MAX_DEPTH,
        max_open_goals=MAX_OPEN_GOALS,
        candidate_cap=CANDIDATE_CAP,
        timeout_s=TIMEOUT_S,
        max_frontier=MAX_FRONTIER,
    )
    controller = controller_for_exp001()
    dreamer = dreamer_for_arm(args.arm)

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
            "stdout_tail": vr.stdout[-4000:],
            "stderr_tail": vr.stderr[-4000:],
        }

    result, bridge = search_target_with_causal_dreamer(
        db,
        target_label,
        config,
        verify_candidate=verifier_callback,
        controller=controller,
        dreamer=dreamer,
        enabled=(args.arm != "off"),
    )
    costs = account_run_cost(
        result,
        dreamer,
        bridge.executor,
        controller=controller,
    )

    reflection = reflection_dict(dreamer)
    payload: dict[str, Any] = {
        "experiment": EXPERIMENT_ID,
        "scientific_run": True,
        "official_runtime_claim": False,
        "arm": args.arm,
        "target_ordinal": args.target_ordinal,
        "target": target_label,
        "experiment_seed": EXPERIMENT_SEED,
        "benchmark_name": lock["benchmark_name"],
        "benchmark_lock_path": CANONICAL_LOCK,
        "benchmark_lock_git_blob": BENCHMARK_LOCK_BLOB,
        "source_setmm_commit": lock["source_setmm_commit"],
        "source_setmm_sha256": source_sha,
        "holdout_labels_sha256": lock["holdout_labels_sha256"],
        "targets_sha256": lock["targets_sha256"],
        "oracle_semantics": "ORACLE_SEMANTICS_FROZEN_001",
        "oracle_semantics_path": ORACLE_SEMANTICS,
        "oracle_semantics_implementation_blob": ORACLE_SEMANTICS_IMPLEMENTATION_BLOB,
        "proof_access_policy": (
            "settlement parser is proof-redacted; every non-target held-out theorem is removed "
            "from the legal search library; any candidate citing a held-out label is rejected "
            "before the independent verifier"
        ),
        "status": result.status,
        "reason": result.reason,
        "expansions": result.expansions,
        "generated_children": result.generated_children,
        "elapsed_search_s": result.elapsed_s,
        "proof_step_labels": len(result.proof_labels),
        "proof_labels": list(result.proof_labels),
        "verification": result.verification,
        "search_config": {
            "max_expansions": MAX_EXPANSIONS,
            "timeout_s": TIMEOUT_S,
            "candidate_cap": CANDIDATE_CAP,
            "max_depth": MAX_DEPTH,
            "max_open_goals": MAX_OPEN_GOALS,
            "max_frontier": MAX_FRONTIER,
        },
        "controller": {
            "class": type(controller).__name__,
            "control_interval": CONTROL_INTERVAL,
            "professor_interval": PROFESSOR_INTERVAL,
            "child_play": controller.child_play_enabled,
            "actual_professor_calls": controller.actual_professor_calls,
            "professor_updates": controller.professor_updates,
            "initial_creativity": {k: 0.5 for k in controller.creativity.to_dict()},
            "final_creativity": controller.creativity.to_dict(),
        },
        "dreamer": {
            "enabled": args.arm != "off",
            "access_bits": list(ARM_ACCESS_BITS[args.arm]),
            "reflection": reflection,
            "bridge_history": bridge_history_dict(bridge),
            "promotion_execution_history": executor_history_dict(bridge),
            "settled_with_any_promotion": bool(
                result.status == "PROVED" and reflection["promotions"] > 0
            ),
            "individual_proposal_causal_attribution_claimed": False,
        },
        "hard_throttles": {
            facet.value: {
                "max_calls": ORACLE_THROTTLES[facet].max_calls,
                "min_steps_between_calls": ORACLE_THROTTLES[facet].min_steps_between_calls,
            }
            for facet in ORACLE_THROTTLES
        },
        "promotion_throttle": {
            "max_promotions": PROMOTION_THROTTLE.max_promotions,
            "min_steps_between_promotions": PROMOTION_THROTTLE.min_steps_between_promotions,
            "max_abs_creativity_delta_per_coordinate": PROMOTION_MAX_ABS_DELTA,
            "whitelisted_actions": [action.value for action in PROMOTION_DELTAS],
        },
        "resource_accounting": costs.to_dict(),
    }

    if result.status == "PROVED":
        if not isinstance(result.verification, dict) or result.verification.get("accepted") is not True:
            raise RuntimeError("PROVED status requires independent verifier acceptance")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (out / "control_telemetry.jsonl").open("w", encoding="utf-8") as fh:
        for row in compact_historian(result.historian):
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (out / "dreamer_telemetry.jsonl").open("w", encoding="utf-8") as fh:
        for row in payload["dreamer"]["bridge_history"]:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
