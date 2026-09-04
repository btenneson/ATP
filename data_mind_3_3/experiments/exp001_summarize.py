#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean, median
from typing import Any

from data_mind_3_3.experiments.exp001_config import ARMS, EXPERIMENT_ID


EXPECTED_TARGETS = 20


def _proved(row: dict[str, Any] | None) -> bool:
    return bool(
        row
        and row.get("status") == "PROVED"
        and isinstance(row.get("verification"), dict)
        and row["verification"].get("accepted") is True
    )


def _metric(rows: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return {
        "n": len(values),
        "mean": fmean(values) if values else None,
        "median": median(values) if values else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = Path(args.root)
    records: dict[tuple[int, str], dict[str, Any]] = {}
    duplicates: list[str] = []
    for path in sorted(root.glob("**/result.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("experiment") != EXPERIMENT_ID:
            continue
        key = (int(row["target_ordinal"]), str(row["arm"]))
        if key in records:
            duplicates.append(f"{key}:{path}")
        records[key] = row

    expected = {(ordinal, arm) for ordinal in range(EXPECTED_TARGETS) for arm in ARMS}
    missing = sorted(expected - set(records))
    unexpected = sorted(set(records) - expected)

    per_arm: dict[str, Any] = {}
    for arm in ARMS:
        rows = [records[(ordinal, arm)] for ordinal in range(EXPECTED_TARGETS) if (ordinal, arm) in records]
        proved_rows = [row for row in rows if _proved(row)]
        accounting = [row.get("resource_accounting", {}) for row in rows]
        per_arm[arm] = {
            "records": len(rows),
            "verified_settlements": len(proved_rows),
            "unknown_or_not_verified": len(rows) - len(proved_rows),
            "expansions_all": _metric(rows, "expansions"),
            "wall_time_all_s": _metric(rows, "elapsed_search_s"),
            "accounted_units_all": _metric(
                [a for a in accounting if isinstance(a, dict)], "accounted_units"
            ),
            "dreamer_proposals_total": sum(
                int(a.get("dreamer_proposals", 0)) for a in accounting if isinstance(a, dict)
            ),
            "promotions_granted_total": sum(
                int(a.get("promotions_granted", 0)) for a in accounting if isinstance(a, dict)
            ),
            "promotion_executions_total": sum(
                int(a.get("promotion_executions", 0)) for a in accounting if isinstance(a, dict)
            ),
            "oracle_calls_total": sum(
                int(a.get("oracle_calls", 0)) for a in accounting if isinstance(a, dict)
            ),
            "professor_actual_calls_total": sum(
                int(a.get("professor_actual_calls", 0)) for a in accounting if isinstance(a, dict)
            ),
            "settlements_with_any_promotion": sum(
                1
                for row in proved_rows
                if isinstance(row.get("dreamer"), dict)
                and row["dreamer"].get("settled_with_any_promotion") is True
            ),
        }

    off = {ordinal: records.get((ordinal, "off")) for ordinal in range(EXPECTED_TARGETS)}
    paired_vs_off: dict[str, Any] = {}
    for arm in ARMS:
        if arm == "off":
            continue
        gains: list[str] = []
        losses: list[str] = []
        common: list[int] = []
        for ordinal in range(EXPECTED_TARGETS):
            baseline = off[ordinal]
            treatment = records.get((ordinal, arm))
            if baseline is None or treatment is None:
                continue
            base_ok = _proved(baseline)
            arm_ok = _proved(treatment)
            if arm_ok and not base_ok:
                gains.append(str(treatment["target"]))
            elif base_ok and not arm_ok:
                losses.append(str(treatment["target"]))
            elif base_ok and arm_ok:
                common.append(ordinal)

        common_rows_arm = [records[(ordinal, arm)] for ordinal in common]
        common_rows_off = [records[(ordinal, "off")] for ordinal in common]
        exp_delta = [
            float(a["expansions"]) - float(b["expansions"])
            for a, b in zip(common_rows_arm, common_rows_off)
        ]
        time_delta = [
            float(a["elapsed_search_s"]) - float(b["elapsed_search_s"])
            for a, b in zip(common_rows_arm, common_rows_off)
        ]
        accounted_delta = []
        for a, b in zip(common_rows_arm, common_rows_off):
            aa = a.get("resource_accounting", {})
            bb = b.get("resource_accounting", {})
            if isinstance(aa, dict) and isinstance(bb, dict):
                if aa.get("accounted_units") is not None and bb.get("accounted_units") is not None:
                    accounted_delta.append(float(aa["accounted_units"]) - float(bb["accounted_units"]))

        paired_vs_off[arm] = {
            "gain_targets": gains,
            "loss_targets": losses,
            "net_verified_settlement_gain": len(gains) - len(losses),
            "common_verified_targets": len(common),
            "common_verified_expansion_delta_mean": fmean(exp_delta) if exp_delta else None,
            "common_verified_expansion_delta_median": median(exp_delta) if exp_delta else None,
            "common_verified_wall_time_delta_mean_s": fmean(time_delta) if time_delta else None,
            "common_verified_wall_time_delta_median_s": median(time_delta) if time_delta else None,
            "common_verified_accounted_units_delta_mean": fmean(accounted_delta) if accounted_delta else None,
            "common_verified_accounted_units_delta_median": median(accounted_delta) if accounted_delta else None,
        }

    placebo = per_arm.get("placebo-o3", {})
    real_o3 = per_arm.get("o3", {})
    placebo_comparison = {
        "o3_verified_settlements_minus_placebo": (
            int(real_o3.get("verified_settlements", 0)) - int(placebo.get("verified_settlements", 0))
        ),
        "interpretation_rule": (
            "This comparison separates informative O3 advice from merely receiving a matched legal perturbation surface; "
            "it is descriptive and not by itself a causal proof."
        ),
    }

    target_rows = []
    for ordinal in range(EXPECTED_TARGETS):
        sample = next(
            (records[(ordinal, arm)] for arm in ARMS if (ordinal, arm) in records),
            None,
        )
        target_rows.append({
            "ordinal": ordinal,
            "target": sample.get("target") if sample else None,
            "arms": {
                arm: {
                    "status": records[(ordinal, arm)].get("status"),
                    "verified": _proved(records[(ordinal, arm)]),
                    "expansions": records[(ordinal, arm)].get("expansions"),
                    "elapsed_search_s": records[(ordinal, arm)].get("elapsed_search_s"),
                    "accounted_units": records[(ordinal, arm)].get("resource_accounting", {}).get("accounted_units")
                    if isinstance(records[(ordinal, arm)].get("resource_accounting"), dict)
                    else None,
                }
                for arm in ARMS if (ordinal, arm) in records
            },
        })

    summary = {
        "experiment": EXPERIMENT_ID,
        "summary_policy": "verifier-first; workflow success is not theorem success",
        "expected_records": len(expected),
        "records_found": len(records),
        "complete": not missing and not unexpected and not duplicates,
        "missing_records": [{"ordinal": o, "arm": a} for o, a in missing],
        "unexpected_records": [{"ordinal": o, "arm": a} for o, a in unexpected],
        "duplicate_records": duplicates,
        "primary_endpoint": "verified_settlements per arm",
        "per_arm": per_arm,
        "paired_vs_off": paired_vs_off,
        "placebo_comparison": placebo_comparison,
        "individual_dream_causal_attribution_claimed": False,
        "accounted_units_caveat": (
            "Normalized accounted units make advisory work non-free in bookkeeping but do not assert CPU equivalence across operations."
        ),
        "targets": target_rows,
    }

    out = Path(args.out)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
