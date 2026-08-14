"""Summarize the already-completed Experiment 007 raw results.

This script performs no fitting or training. It only derives cohort A/B/pooled
aggregates from the committed raw rows produced by Experiment 007.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

RDIR = Path("optimizations/settlement_compass/results")
RAW = RDIR / "experiment_007_changed_test20_raw.json"
OLD = RDIR / "experiment_004_shell_results.json"
SUMMARY = RDIR / "experiment_007_changed_test20_summary.json"
CHECK = RDIR / "experiment_007_protocol_check.json"

raw = json.loads(RAW.read_text())
old = json.loads(OLD.read_text())

A = list(raw["test20"])
B = list(raw["test20_b"])
ALL = list(raw["test_all"])
setA, setB = set(A), set(B)

if A != old["test20"]:
    raise SystemExit("Cohort A is not the exact Experiment-004 test20")
if len(setA) != 20 or len(setB) != 20 or setA & setB:
    raise SystemExit("A/B cohorts are not disjoint 20-element sets")
if len(ALL) != 40 or set(ALL) != setA | setB:
    raise SystemExit("Joint test40 is malformed")

shells = [str(a["shell"]) for a in raw["aggregates"]]
if shells != ["320", "640", "1280", "2560"]:
    raise SystemExit(f"Unexpected shells: {shells}")
if any(int(a["n_test"]) != 40 for a in raw["aggregates"]):
    raise SystemExit("Raw run did not evaluate all 40 sealed targets")


def aggregate(rows, pooled):
    return {
        "n_test": len(rows),
        "mean_auc": float(np.mean([r["auc"] for r in rows])),
        "mean_spearman_distance": float(np.nanmean([r["spearman_distance"] for r in rows])),
        "mean_mae_distance": float(np.mean([r["mae_distance"] for r in rows])),
        "median_compass_rank_first_dag": float(np.median([r["compass_rank_first_dag"] for r in rows])),
        "median_compass_rank_first_direct_parent": float(np.median([r["compass_rank_first_direct_parent"] for r in rows])),
        "mean_precision_at_10": float(np.mean([r["precision_at_10"] for r in rows])),
        "compass_beats_random_direct_parent": int(sum(
            r["compass_rank_first_direct_parent"] < r["random_rank_first_direct_parent"] for r in rows
        )),
        "random_beats_compass_direct_parent": int(sum(
            r["compass_rank_first_direct_parent"] > r["random_rank_first_direct_parent"] for r in rows
        )),
        "n_train": pooled["n_train"],
        "n_training_classifier_examples": pooled["n_training_classifier_examples"],
        "n_training_regression_examples": pooled["n_training_regression_examples"],
    }

cohort_results = []
for pooled in raw["aggregates"]:
    shell = str(pooled["shell"])
    rows = [r for r in raw["rows"] if str(r["shell"]) == shell]
    ra = [r for r in rows if r["target"] in setA]
    rb = [r for r in rows if r["target"] in setB]
    aa, ab, ap = aggregate(ra, pooled), aggregate(rb, pooled), aggregate(rows, pooled)
    cohort_results.append({
        "shell": shell,
        "A_original20": aa,
        "B_new20": ab,
        "pooled40": ap,
        "B_minus_A": {
            "mean_auc": ab["mean_auc"] - aa["mean_auc"],
            "mean_spearman_distance": ab["mean_spearman_distance"] - aa["mean_spearman_distance"],
            "mean_mae_distance": ab["mean_mae_distance"] - aa["mean_mae_distance"],
            "mean_precision_at_10": ab["mean_precision_at_10"] - aa["mean_precision_at_10"],
            "median_direct_parent_rank": (
                ab["median_compass_rank_first_direct_parent"] -
                aa["median_compass_rank_first_direct_parent"]
            ),
        },
    })

summary = {
    "experiment": 7,
    "protocol": raw["protocol"],
    "test20_A": A,
    "test20_B": B,
    "test40_jointly_sealed": ALL,
    "training_shells": [320, 640, 1280, 2560],
    "manifest_vocabulary_sha256": raw.get("manifest_vocabulary_sha256"),
    "cohort_results": cohort_results,
    "interpretation_guardrail": (
        "Within each shell A and B share the same fitted compass. This probes theorem-mix sensitivity; "
        "it does not turn the compass into a learned closed-loop controller."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

check = {
    "experiment": 7,
    "recovery_only_no_retraining": True,
    "cohort_A_is_exact_experiment004_test20": True,
    "cohort_B_is_disjoint_new20": True,
    "joint_test40_has_40_unique_targets": True,
    "all_four_raw_shells_completed": True,
    "shells": shells,
    "raw_n_test_each_shell": [int(a["n_test"]) for a in raw["aggregates"]],
    "note": (
        "The original run completed all model fits and row outputs, then failed only while writing its convenience summary. "
        "This recovery derives the summary from those committed raw rows and performs no model fitting."
    ),
}
CHECK.write_text(json.dumps(check, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2))
