#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig
from data_mind_3.metamath.verifier import verify_with_brian_metamath
from data_mind_3_3.costs import account_run_cost
from data_mind_3_3.metamath.causal_bridge import search_target_with_causal_dreamer
from data_mind_3_3.experiments.exp001_lane import (
    BENCHMARK_LOCK_BLOB,
    CANONICAL_LOCK,
    compact_historian,
    load_holdout,
    proof_safe_database,
    sha256_file,
)
from data_mind_3_3.experiments.exp002_config import (
    ARMS,
    CANDIDATE_CAP,
    CONTROL_INTERVAL,
    EXPERIMENT_ID,
    EXPERIMENT_SEED,
    MAX_DEPTH,
    MAX_EXPANSIONS,
    MAX_FRONTIER,
    MAX_OPEN_GOALS,
    PROFESSOR_INTERVALS,
    TIMEOUT_S,
    controller_for_arm,
    disabled_dreamer,
)


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
    controller = controller_for_arm(args.arm)
    dreamer = disabled_dreamer()

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
            Path(args.setmm), target_label, proof_labels, Path(args.verifier), timeout_s=120.0
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
        enabled=False,
    )
    costs = account_run_cost(result, dreamer, bridge.executor, controller=controller)

    payload = {
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
        "proof_access_policy": (
            "proof-redacted settlement parser; every non-target held-out theorem removed from legal "
            "search library; held-out theorem labels rejected before independent verifier"
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
            "professor_interval": PROFESSOR_INTERVALS[args.arm],
            "professor_enabled": PROFESSOR_INTERVALS[args.arm] is not None,
            "child_play": controller.child_play_enabled,
            "actual_professor_calls": controller.actual_professor_calls,
            "professor_updates": controller.professor_updates,
            "self_awareness_updates": controller.self_awareness_updates,
            "final_creativity": controller.creativity.to_dict(),
        },
        "dreamer": {
            "enabled": False,
            "access_bits": [0, 0, 0, 0],
        },
        "resource_accounting": costs.to_dict(),
    }

    if args.arm == "prof-off" and controller.actual_professor_calls != 0:
        raise RuntimeError("Professor OFF arm made an actual Professor call")
    expected_interval = PROFESSOR_INTERVALS[args.arm]
    if expected_interval is not None and controller.professor_interval != expected_interval:
        raise RuntimeError("Professor interval drift")
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
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
