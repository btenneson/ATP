#!/usr/bin/env python3
from __future__ import annotations

"""One fresh lane for DATA MIND 3.1 Experiment 002 Professor-cadence ablation."""

import argparse
import json
from pathlib import Path
from typing import Any

from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.control.knobs import CreativityVector
from data_mind_3.control.reflective import PROFESSOR_SCALARIZATION, ReflectiveP1Controller
from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig, SearchResult, search_target
from data_mind_3.metamath.verifier import verify_with_brian_metamath
from experiments.dm31_exp001_lane import (
    STATIC_INTERVAL,
    PAIR_EXPANSION_BUDGET,
    LANE_EXPANSION_BUDGET,
    PAIR_TIME_BUDGET_S,
    LANE_TIME_BUDGET_S,
    BASE_CANDIDATE_CAP,
    BASE_MAX_DEPTH,
    BASE_MAX_OPEN_GOALS,
    BASE_MAX_FRONTIER,
    compact_control_history,
    load_holdout,
    load_json,
    p2_creativity,
    proof_safe_database,
    sha256_file,
)


ARM_INTERVALS = {"c16": 16, "c64": 64, "c256": 256}
EVENT_COOLDOWN = 128
EVENT_STAGNATION = 256
EVENT_PC_DELTA = 0.05
EVENT_FRONTIER_RATIO = 0.75
EVENT_RESOURCE_THRESHOLDS = (0.50, 0.75)


class EventTriggeredReflectiveP1Controller(ReflectiveP1Controller):
    """Continuous Professor measurement with sparse event-triggered intervention.

    The Professor may observe/grade every expansion, but P1's creativity state can
    change only on a preregistered event after the refractory period.  This keeps
    diagnostic observation separate from search-changing communication.
    """

    def __init__(self, initial: CreativityVector | None = None) -> None:
        super().__init__(
            initial=initial,
            interval=EVENT_COOLDOWN,
            experience=(),
            child_play=False,
        )
        self._best_raw_pc = 0.0
        self._last_raw_improvement_expansion = 0
        self._last_intervention_expansion = 0
        self._last_raw_at_intervention: float | None = None
        self._resource_thresholds_fired: set[float] = set()
        self.event_interventions: list[dict[str, object]] = []

    def _trigger_reasons(
        self,
        *,
        expansion: int,
        partial_credit: float,
        frontier: int,
        max_frontier: int,
        elapsed: float,
        timeout: float,
    ) -> list[str]:
        raw = float(partial_credit)
        if raw > self._best_raw_pc + 1e-12:
            self._best_raw_pc = raw
            self._last_raw_improvement_expansion = expansion

        if expansion - self._last_intervention_expansion < EVENT_COOLDOWN:
            return []

        reasons: list[str] = []
        if self._last_intervention_expansion == 0 and expansion >= EVENT_COOLDOWN:
            reasons.append("bootstrap")
        if (
            self._last_raw_at_intervention is not None
            and abs(raw - self._last_raw_at_intervention) >= EVENT_PC_DELTA
        ):
            reasons.append("partial_credit_change")
        if expansion - self._last_raw_improvement_expansion >= EVENT_STAGNATION:
            reasons.append("stagnation")
        if max_frontier > 0 and frontier / max_frontier >= EVENT_FRONTIER_RATIO:
            reasons.append("frontier_pressure")
        resource_ratio = elapsed / max(1e-9, timeout)
        for threshold in EVENT_RESOURCE_THRESHOLDS:
            if threshold not in self._resource_thresholds_fired and resource_ratio >= threshold:
                reasons.append(f"resource_{int(threshold * 100)}pct")
        return reasons

    def observe_expansion(
        self,
        *,
        expansion: int,
        generated_total: int,
        frontier: int,
        max_frontier: int,
        elapsed: float,
        timeout: float,
        partial_credit: float,
        relevance: float,
        base_config: object,
    ) -> dict[str, object] | None:
        raw_partial_credit = float(partial_credit)

        # Professor measurement remains continuous, but it cannot alter search
        # unless a preregistered communication event fires below.
        grade, professor_credit, self_observation, h_hat = self._grade(
            expansion=expansion,
            raw_partial_credit=raw_partial_credit,
            relevance=relevance,
        )
        reasons = self._trigger_reasons(
            expansion=expansion,
            partial_credit=raw_partial_credit,
            frontier=frontier,
            max_frontier=max_frontier,
            elapsed=elapsed,
            timeout=timeout,
        )
        if not reasons:
            return None

        event = AdaptiveCreativityController.observe_expansion(
            self,
            expansion=expansion,
            generated_total=generated_total,
            frontier=frontier,
            max_frontier=max_frontier,
            elapsed=elapsed,
            timeout=timeout,
            partial_credit=professor_credit,
            relevance=relevance,
            base_config=base_config,
        )
        if event is None:
            return None

        professor_event: dict[str, object] = {
            "actor": "Professor",
            "action": "grade_P1_event_triggered",
            "expansion": expansion,
            "recipient": "P1",
            "communication_reasons": list(reasons),
            "raw_structural_partial_credit": raw_partial_credit,
            "repair_horizon_proxy": h_hat,
            "repair_half_distance": self._repair_half_distance,
            "grade": grade.to_dict(),
            "professor_credit": professor_credit,
            "scalarization": dict(PROFESSOR_SCALARIZATION),
        }
        self_event: dict[str, object] = {
            "actor": "P1",
            "action": "self_observe_event_triggered",
            "expansion": expansion,
            "self_aware": True,
            "communication_reasons": list(reasons),
            "resource_spent": self_observation.resource_spent,
            "professor_credit": self_observation.partial_credit,
            "previous_professor_credit": self_observation.previous_partial_credit,
            "resource_delta": self_observation.resource_delta,
            "marginal_credit_per_resource": self_observation.marginal_credit_per_resource,
        }
        event.update({
            "agent": "P1",
            "communication_reasons": list(reasons),
            "professor_credit": professor_credit,
            "professor_grade": grade.to_dict(),
            "repair_horizon_proxy": h_hat,
            "repair_half_distance": self._repair_half_distance,
            "self_awareness": self_event,
        })
        self.history.append(professor_event)
        self.history.append(self_event)
        self.professor_updates += 1
        self.self_awareness_updates += 1
        self._last_intervention_expansion = expansion
        self._last_raw_at_intervention = raw_partial_credit
        for threshold in EVENT_RESOURCE_THRESHOLDS:
            if elapsed / max(1e-9, timeout) >= threshold:
                self._resource_thresholds_fired.add(threshold)
        self.event_interventions.append({
            "expansion": expansion,
            "reasons": list(reasons),
            "raw_partial_credit": raw_partial_credit,
            "professor_credit": professor_credit,
        })
        return event


def controller_for(mode: str, split_seed: int) -> AdaptiveCreativityController:
    if mode == "off":
        return AdaptiveCreativityController(
            initial=CreativityVector(), interval=STATIC_INTERVAL, child_play=False
        )
    if mode == "p2":
        return AdaptiveCreativityController(
            initial=p2_creativity(split_seed), interval=STATIC_INTERVAL, child_play=False
        )
    if mode in ARM_INTERVALS:
        return ReflectiveP1Controller(
            initial=CreativityVector(),
            interval=ARM_INTERVALS[mode],
            experience=(),
            child_play=False,
        )
    if mode == "event":
        return EventTriggeredReflectiveP1Controller(initial=CreativityVector())
    raise ValueError(mode)


def result_payload(
    *,
    mode: str,
    target_ordinal: int,
    target_label: str,
    source_sha: str,
    lock: dict[str, Any],
    result: SearchResult,
    controller: AdaptiveCreativityController,
) -> dict[str, Any]:
    reflective = controller if isinstance(controller, ReflectiveP1Controller) else None
    event_controller = (
        controller if isinstance(controller, EventTriggeredReflectiveP1Controller) else None
    )
    initial = (
        p2_creativity(int(lock["split_seed"])).to_dict()
        if mode == "p2"
        else CreativityVector().to_dict()
    )
    return {
        "experiment": "DATA MIND 3.1 Experiment 002 — Professor Cadence Frozen-20",
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
            "pair_max_expansions_reference": PAIR_EXPANSION_BUDGET,
            "pair_time_budget_reference_s": PAIR_TIME_BUDGET_S,
            "candidate_cap": BASE_CANDIDATE_CAP,
            "max_depth": BASE_MAX_DEPTH,
            "max_open_goals": BASE_MAX_OPEN_GOALS,
            "max_frontier": BASE_MAX_FRONTIER,
        },
        "controller": {
            "class": type(controller).__name__,
            "control_interval": controller.interval,
            "child_play": controller.child_play_enabled,
            "initial_or_frozen_creativity": initial,
            "final_creativity": controller.creativity.to_dict(),
            "control_updates": sum(
                1 for row in controller.history
                if row.get("actor") == "CreativityController"
                and row.get("action") == "control_update"
            ),
        },
        "reflective_p1": {
            "enabled": reflective is not None,
            "communication_definition": "Professor-to-P1 control intervention capable of changing creativity/search control",
            "professor_control_interventions": reflective.professor_updates if reflective else 0,
            "self_awareness_updates": reflective.self_awareness_updates if reflective else 0,
            "repair_half_distance": reflective.repair_half_distance if reflective else None,
            "last_professor_credit": reflective.last_professor_credit if reflective else None,
            "professor_scalarization": dict(PROFESSOR_SCALARIZATION) if reflective else None,
            "child_disabled_for_mechanism_isolation": True if reflective else None,
        },
        "event_policy": {
            "enabled": event_controller is not None,
            "cooldown_expansions": EVENT_COOLDOWN if event_controller else None,
            "stagnation_expansions": EVENT_STAGNATION if event_controller else None,
            "raw_partial_credit_delta": EVENT_PC_DELTA if event_controller else None,
            "frontier_ratio": EVENT_FRONTIER_RATIO if event_controller else None,
            "resource_thresholds": list(EVENT_RESOURCE_THRESHOLDS) if event_controller else None,
            "interventions": event_controller.event_interventions if event_controller else [],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=("off", "p2", "c16", "c64", "c256", "event"),
        required=True,
    )
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
    targets = sorted(lock["targets"], key=lambda row: int(row["ordinal"]))
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
    controller = controller_for(args.mode, int(lock["split_seed"]))

    def verifier_callback(proof_labels: tuple[str, ...]):
        forbidden = [label for label in proof_labels if label in holdout]
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
    payload = result_payload(
        mode=args.mode,
        target_ordinal=args.target_ordinal,
        target_label=target_label,
        source_sha=source_sha,
        lock=lock,
        result=result,
        controller=controller,
    )
    (out / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (out / "control_telemetry.jsonl").open("w", encoding="utf-8") as fh:
        for row in compact_control_history(result.historian):
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
