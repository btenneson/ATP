#!/usr/bin/env python3
from __future__ import annotations

"""Verifier-first summary for DATA MIND 3.1 Experiment 002."""

import argparse
import json
from pathlib import Path
from statistics import fmean
from typing import Any


MODES = ("off", "p2", "c16", "c64", "c256", "event")
P1_ARMS = ("off", "c16", "c64", "c256", "event")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def proved(row: dict[str, Any]) -> bool:
    verification = row.get("verification") or {}
    return row.get("status") == "PROVED" and bool(verification.get("accepted"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--expected-targets", type=int, default=20)
    args = ap.parse_args()

    root = Path(args.root)
    results: list[dict[str, Any]] = []
    arm_counts = {mode: 0 for mode in P1_ARMS}
    settlement_counts = {mode: 0 for mode in P1_ARMS}
    budget_hits = {mode: 0 for mode in P1_ARMS}
    interventions: dict[str, list[int]] = {mode: [] for mode in P1_ARMS if mode != "off"}
    gains = {mode: [] for mode in P1_ARMS if mode != "off"}
    losses = {mode: [] for mode in P1_ARMS if mode != "off"}

    for ordinal in range(args.expected_targets):
        lane_rows: dict[str, dict[str, Any]] = {}
        complete = True
        for mode in MODES:
            path = root / f"target-{ordinal}" / mode / "result.json"
            if not path.exists():
                complete = False
                continue
            lane_rows[mode] = load(path)

        if not complete:
            results.append({"ordinal": ordinal, "complete": False})
            continue

        target = str(lane_rows["off"]["target"])
        p2_ok = proved(lane_rows["p2"])
        target_summary: dict[str, Any] = {
            "ordinal": ordinal,
            "target": target,
            "complete": True,
            "P2_proved": p2_ok,
            "arms": {},
        }

        off_ok = proved(lane_rows["off"])
        for mode in P1_ARMS:
            row = lane_rows[mode]
            p1_ok = proved(row)
            settled = p1_ok or p2_ok
            if p1_ok:
                arm_counts[mode] += 1
            if settled:
                settlement_counts[mode] += 1
            if int(row.get("expansions", 0)) >= int(row["lane_budget"]["max_expansions"]):
                budget_hits[mode] += 1
            if mode != "off":
                n_updates = int(
                    (row.get("reflective_p1") or {}).get(
                        "professor_control_interventions", 0
                    )
                )
                interventions[mode].append(n_updates)
                if p1_ok and not off_ok:
                    gains[mode].append(target)
                if off_ok and not p1_ok:
                    losses[mode].append(target)
            target_summary["arms"][mode] = {
                "P1_proved": p1_ok,
                "settled_with_common_P2": settled,
                "expansions": row.get("expansions"),
                "elapsed_search_s": row.get("elapsed_search_s"),
                "reason": row.get("reason"),
                "proof_step_labels": row.get("proof_step_labels"),
                "professor_control_interventions": (
                    (row.get("reflective_p1") or {}).get(
                        "professor_control_interventions", 0
                    )
                ),
                "final_creativity": (row.get("controller") or {}).get("final_creativity"),
            }
        results.append(target_summary)

    complete_targets = sum(1 for row in results if row.get("complete"))
    p2_count = sum(
        1
        for row in results
        if row.get("complete") and bool(row.get("P2_proved"))
    )

    arms: dict[str, Any] = {}
    for mode in P1_ARMS:
        arms[mode] = {
            "P1_verifier_certified": arm_counts[mode],
            "settled_with_common_P2": settlement_counts[mode],
            "full_50000_expansion_budget_hits": budget_hits[mode],
        }
        if mode != "off":
            values = interventions[mode]
            arms[mode].update({
                "unique_P1_gains_vs_off": gains[mode],
                "P1_losses_vs_off": losses[mode],
                "net_P1_gain_minus_loss_vs_off": len(gains[mode]) - len(losses[mode]),
                "mean_professor_control_interventions": fmean(values) if values else None,
                "max_professor_control_interventions": max(values) if values else None,
            })

    summary = {
        "experiment": "DATA MIND 3.1 Experiment 002 — Professor Cadence Frozen-20",
        "official_runtime_claim": False,
        "expected_targets": args.expected_targets,
        "complete_targets": complete_targets,
        "primary_rule": "Only fresh verifier-accepted certificates count as proofs; P1 cadence inference is primary and common P2 is a secondary hedge.",
        "common_P2_verifier_certified": p2_count,
        "arms": arms,
        "results": results,
        "interpretation_note": "n=20 cadence stress test; report direction and mechanism, not universal optimality or significance.",
    }

    Path(args.out).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if complete_targets == args.expected_targets else 2


if __name__ == "__main__":
    raise SystemExit(main())
