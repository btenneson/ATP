#!/usr/bin/env python3
from __future__ import annotations

"""One fresh settlement lane for DATA MIND 3.1 Experiment 001.

Modes:
  a-p1  balanced P1 search with frozen, non-updating creativity.
  p2    independent P2 search with a reproducible seed-derived fixed strategy.
  c-p1  Professor-facing/self-aware P1 with active feedback, Child disabled.

Arm B is not a second search. It is the Professor shadow replay derived from the
exact a-p1 trajectory, which guarantees that measurement itself cannot affect
the search.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random
from statistics import fmean
from typing import Any

from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.control.knobs import CreativityVector
from data_mind_3.control.professor import Professor, ProfessorEvidence
from data_mind_3.control.reflective import (
    PROFESSOR_SCALARIZATION,
    ReflectiveP1Controller,
)
from data_mind_3.metamath.parser import Database, parse_database
from data_mind_3.metamath.search import SearchConfig, SearchResult, search_target
from data_mind_3.metamath.verifier import verify_with_brian_metamath


STATIC_INTERVAL = 1_000_000_000
PAIR_EXPANSION_BUDGET = 100_000
LANE_EXPANSION_BUDGET = PAIR_EXPANSION_BUDGET // 2
PAIR_TIME_BUDGET_S = 1800.0
LANE_TIME_BUDGET_S = PAIR_TIME_BUDGET_S / 2.0
CONTROL_INTERVAL = 16
BASE_CANDIDATE_CAP = 64
BASE_MAX_DEPTH = 24
BASE_MAX_OPEN_GOALS = 24
BASE_MAX_FRONTIER = 200_000


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_holdout(path: str | Path, expected_sha: str) -> tuple[list[str], set[str]]:
    text = Path(path).read_text(encoding="utf-8")
    if sha256_text(text) != expected_sha:
        raise RuntimeError("holdout label file hash mismatch")
    labels = [line.strip() for line in text.splitlines() if line.strip()]
    if len(labels) != len(set(labels)):
        raise RuntimeError("holdout label file contains duplicates")
    return labels, set(labels)


def proof_safe_database(db: Database, holdout: set[str], target_label: str) -> Database:
    """Remove every non-target held-out theorem from the legal search database."""
    filtered = [
        a
        for a in db.assertions
        if a.kind == "$a" or a.label not in holdout or a.label == target_label
    ]
    by_label: dict[str, object] = dict(db.hypotheses)
    for a in filtered:
        by_label[a.label] = a
    if target_label not in by_label:
        raise RuntimeError("target disappeared while redacting holdout theorem labels")
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


def p2_creativity(split_seed: int) -> CreativityVector:
    """A theorem-independent partner strategy frozen from the benchmark split seed."""
    rng = random.Random(int(split_seed))
    values = [rng.uniform(0.25, 0.75) for _ in range(11)]
    names = list(CreativityVector().__dict__)
    return CreativityVector(**dict(zip(names, values)))


def compact_control_history(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep = {"CreativityController", "Professor", "P1", "Sentinel", "Verifier", "Child"}
    return [
        row for row in rows
        if isinstance(row, dict) and row.get("actor") in keep
    ]


def shadow_professor(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    professor = Professor()
    h_half: float | None = None
    prev_pc: float | None = None
    samples: list[dict[str, Any]] = []

    for row in rows:
        if row.get("actor") != "Search" or row.get("action") != "expand":
            continue
        q = float(row["pc"])
        expansion = int(row["expansion"])
        relevance = float(row.get("target_relevance", 0.0))
        q_clip = max(1e-12, min(1.0, q))
        h_hat = max(0.0, 1.0 / q_clip - 1.0)
        if h_half is None and h_hat > 0:
            h_half = h_hat
        hp = h_half or 1.0
        grade = professor.grade(
            ProfessorEvidence(
                verified_structure=q,
                target_relevance=relevance,
                repair_horizon=h_hat,
                repair_half_distance=hp,
            )
        )
        pc = grade.scalarize(PROFESSOR_SCALARIZATION)
        if expansion == 1 or expansion % CONTROL_INTERVAL == 0:
            samples.append({
                "expansion": expansion,
                "q_raw": q,
                "repair_horizon_proxy": h_hat,
                "repair_half_distance": hp,
                "repair_proximity": grade.repair_proximity,
                "professor_credit": pc,
                "delta_professor_credit": None if prev_pc is None else pc - prev_pc,
                "target_relevance": relevance,
            })
        prev_pc = pc

    credits = [float(r["professor_credit"]) for r in samples]
    summary = {
        "measurement_only": True,
        "search_influence": False,
        "sample_interval": CONTROL_INTERVAL,
        "samples": len(samples),
        "repair_horizon_semantics": "H_hat=max(0,1/q_raw-1); burden proxy, not exact repair distance",
        "professor_scalarization": dict(PROFESSOR_SCALARIZATION),
        "first_repair_half_distance": h_half,
        "first_credit": credits[0] if credits else None,
        "last_credit": credits[-1] if credits else None,
        "max_credit": max(credits) if credits else None,
        "mean_credit": fmean(credits) if credits else None,
        "positive_sample_deltas": sum(
            1 for r in samples
            if r["delta_professor_credit"] is not None and r["delta_professor_credit"] > 0
        ),
    }
    return summary, samples


def result_payload(
    *,
    mode: str,
    target_ordinal: int,
    target_label: str,
    source_sha: str,
    lock: dict[str, Any],
    result: SearchResult,
    controller: AdaptiveCreativityController,
    shadow: dict[str, Any] | None,
) -> dict[str, Any]:
    reflective = controller if isinstance(controller, ReflectiveP1Controller) else None
    return {
        "experiment": "DATA MIND 3.1 Experiment 001 — Professor/Self-Awareness Frozen-20 Ablation",
        "official_runtime_claim": False,
        "reason_not_official": "RUNTIME_CONFIG_001 remains unresolved; this is an explicit research ablation",
        "mode": mode,
        "target_ordinal": target_ordinal,
        "target": target_label,
        "benchmark_name": lock["benchmark_name"],
        "architecture_snapshot_sha256": lock["architecture_snapshot_sha256"],
        "source_setmm_sha256": source_sha,
        "holdout_labels_sha256": lock["holdout_labels_sha256"],
        "proof_access_policy": "parser discards proof text; all non-target held-out theorems removed from legal search library",
        "status": result.status,
        "reason": result.reason,
        "expansions": result.expansions,
        "generated_children": result.generated_children,
        "elapsed_search_s": result.elapsed_s,
        "proof_step_labels": len(result.proof_labels),
        "proof_labels": list(result.proof_labels),
        "verification": result.verification,
        "lane_budget": {
            "max_expansions": LANE_EXPANSION_BUDGET,
            "timeout_s": LANE_TIME_BUDGET_S,
            "pair_max_expansions": PAIR_EXPANSION_BUDGET,
            "pair_time_budget_s": PAIR_TIME_BUDGET_S,
            "candidate_cap": BASE_CANDIDATE_CAP,
            "max_depth": BASE_MAX_DEPTH,
            "max_open_goals": BASE_MAX_OPEN_GOALS,
            "max_frontier": BASE_MAX_FRONTIER,
        },
        "controller": {
            "class": type(controller).__name__,
            "control_interval": controller.interval,
            "child_play": controller.child_play_enabled,
            "initial_or_frozen_creativity": (
                CreativityVector().to_dict()
                if mode in {"a-p1", "c-p1"}
                else p2_creativity(int(lock["split_seed"])).to_dict()
            ),
            "final_creativity": controller.creativity.to_dict(),
            "control_updates": sum(
                1 for r in controller.history if r.get("actor") == "CreativityController"
            ),
        },
        "reflective_p1": {
            "enabled": reflective is not None,
            "professor_updates": reflective.professor_updates if reflective else 0,
            "self_awareness_updates": reflective.self_awareness_updates if reflective else 0,
            "repair_half_distance": reflective.repair_half_distance if reflective else None,
            "last_professor_credit": reflective.last_professor_credit if reflective else None,
            "professor_scalarization": dict(PROFESSOR_SCALARIZATION) if reflective else None,
            "child_disabled_for_mechanism_isolation": True if reflective else None,
        },
        "shadow_professor": shadow,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("a-p1", "p2", "c-p1"), required=True)
    ap.add_argument("--target-ordinal", type=int, required=True)
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--holdout-labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verifier", default="metamath.py")
    ap.add_argument(
        "--lock",
        default="benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json",
    )
    args = ap.parse_args()

    lock = load_json(args.lock)
    source_sha = sha256_file(args.setmm)
    if source_sha != lock["source_setmm_sha256"]:
        raise RuntimeError("set.mm source hash does not match benchmark lock")

    _holdout_ordered, holdout = load_holdout(
        args.holdout_labels, lock["holdout_labels_sha256"]
    )
    targets = sorted(lock["targets"], key=lambda r: int(r["ordinal"]))
    if not 0 <= args.target_ordinal < len(targets):
        raise RuntimeError("target ordinal out of range")
    target_label = str(targets[args.target_ordinal]["label"])
    if target_label not in holdout:
        raise RuntimeError("frozen target is not present in reconstructed holdout")

    db = proof_safe_database(parse_database(args.setmm), holdout, target_label)
    config = SearchConfig(
        max_expansions=LANE_EXPANSION_BUDGET,
        max_depth=BASE_MAX_DEPTH,
        max_open_goals=BASE_MAX_OPEN_GOALS,
        candidate_cap=BASE_CANDIDATE_CAP,
        timeout_s=LANE_TIME_BUDGET_S,
        max_frontier=BASE_MAX_FRONTIER,
    )

    if args.mode == "a-p1":
        controller: AdaptiveCreativityController = AdaptiveCreativityController(
            initial=CreativityVector(),
            interval=STATIC_INTERVAL,
            child_play=False,
        )
    elif args.mode == "p2":
        controller = AdaptiveCreativityController(
            initial=p2_creativity(int(lock["split_seed"])),
            interval=STATIC_INTERVAL,
            child_play=False,
        )
    else:
        controller = ReflectiveP1Controller(
            initial=CreativityVector(),
            interval=CONTROL_INTERVAL,
            experience=(),
            child_play=False,
        )

    def verifier_callback(proof_labels: tuple[str, ...]):
        forbidden = [lab for lab in proof_labels if lab in holdout]
        if forbidden:
            return False, {
                "accepted": False,
                "rejected_before_verifier": True,
                "reason": "candidate referenced held-out theorem label",
                "forbidden_labels": forbidden[:20],
            }
        vr = verify_with_brian_metamath(
            Path(args.setmm),
            target_label,
            proof_labels,
            Path(args.verifier),
            timeout_s=600.0,
        )
        return vr.accepted, {
            "accepted": vr.accepted,
            "returncode": vr.returncode,
            "verifier": vr.verifier,
            "stdout_tail": vr.stdout[-4000:],
            "stderr_tail": vr.stderr[-4000:],
        }

    result = search_target(
        db,
        target_label,
        config,
        verify_candidate=verifier_callback,
        controller=controller,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    shadow_summary = None
    if args.mode == "a-p1":
        shadow_summary, shadow_samples = shadow_professor(result.historian)
        with (out / "shadow_professor.jsonl").open("w", encoding="utf-8") as fh:
            for row in shadow_samples:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    payload = result_payload(
        mode=args.mode,
        target_ordinal=args.target_ordinal,
        target_label=target_label,
        source_sha=source_sha,
        lock=lock,
        result=result,
        controller=controller,
        shadow=shadow_summary,
    )
    (out / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    compact = compact_control_history(result.historian)
    with (out / "control_telemetry.jsonl").open("w", encoding="utf-8") as fh:
        for row in compact:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    print(json.dumps(payload, indent=2, sort_keys=True))
    # UNKNOWN is an experimental outcome, not a workflow failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
