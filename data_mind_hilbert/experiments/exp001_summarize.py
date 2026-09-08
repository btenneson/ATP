#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from data_mind_hilbert.experiments.exp001_config import ARMS, ARM_DESCRIPTIONS, TARGET_COUNT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    rows = []
    for path in sorted(Path(args.input_dir).rglob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if row.get("experiment") == "DATA-MIND-HILBERT-ABLATION-001" and "arm" in row:
            row["_source"] = str(path)
            rows.append(row)

    expected = TARGET_COUNT * len(ARMS)
    if len(rows) != expected:
        raise RuntimeError(f"expected {expected} lane records, found {len(rows)}")

    keyed = {(row["arm"], int(row["target_ordinal"])): row for row in rows}
    if len(keyed) != expected:
        raise RuntimeError("duplicate arm/target lane records")
    for arm in ARMS:
        missing = [i for i in range(TARGET_COUNT) if (arm, i) not in keyed]
        if missing:
            raise RuntimeError(f"arm {arm} missing targets: {missing}")

    arm_summary = {}
    for arm in ARMS:
        arows = [keyed[(arm, i)] for i in range(TARGET_COUNT)]
        settled = [r for r in arows if r.get("settled")]
        p_rows = [r for r in arows if r.get("channel") == "P"]
        r_rows = [r for r in arows if r.get("channel") == "R"]
        arm_summary[arm] = {
            "description": ARM_DESCRIPTIONS[arm],
            "settled": len(settled),
            "total": len(arows),
            "settlement_rate": len(settled) / len(arows),
            "P_settled": sum(bool(r.get("settled")) for r in p_rows),
            "P_total": len(p_rows),
            "R_settled": sum(bool(r.get("settled")) for r in r_rows),
            "R_total": len(r_rows),
            "median_expansions_all": median(int(r["expansions"]) for r in arows),
            "median_elapsed_s_all": median(float(r["elapsed_search_s"]) for r in arows),
            "median_expansions_settled": (
                median(int(r["expansions"]) for r in settled) if settled else None
            ),
            "median_elapsed_s_settled": (
                median(float(r["elapsed_search_s"]) for r in settled) if settled else None
            ),
            "unknown_reasons": dict(
                sorted(
                    (
                        reason,
                        sum(1 for r in arows if not r.get("settled") and r.get("reason") == reason),
                    )
                    for reason in {r.get("reason") for r in arows if not r.get("settled")}
                )
            ),
        }

    comparisons = {}
    for left, right, name in (
        ("B", "A", "B_minus_A_naive_Hilbert"),
        ("C", "B", "C_minus_B_structural_geometry"),
        ("C", "A", "C_minus_A_full_geometry_pilot"),
    ):
        wins = losses = ties = 0
        expansion_deltas_on_joint_settled = []
        for i in range(TARGET_COUNT):
            l = keyed[(left, i)]
            r = keyed[(right, i)]
            ls = bool(l.get("settled"))
            rs = bool(r.get("settled"))
            if ls and not rs:
                wins += 1
            elif rs and not ls:
                losses += 1
            else:
                ties += 1
            if ls and rs:
                expansion_deltas_on_joint_settled.append(int(l["expansions"]) - int(r["expansions"]))
        comparisons[name] = {
            "left": left,
            "right": right,
            "settlement_rate_difference": (
                arm_summary[left]["settlement_rate"] - arm_summary[right]["settlement_rate"]
            ),
            "discordant_left_wins": wins,
            "discordant_right_wins": losses,
            "settlement_ties": ties,
            "median_expansion_delta_on_joint_settled": (
                median(expansion_deltas_on_joint_settled)
                if expansion_deltas_on_joint_settled else None
            ),
        }

    payload = {
        "experiment": "DATA-MIND-HILBERT-ABLATION-001",
        "complete": True,
        "lane_records": len(rows),
        "deterministic_runs_per_target_arm": 1,
        "primary_interpretation": "additional verifier-certified settlements within equal 20,000-expansion budget",
        "arms": arm_summary,
        "paired_comparisons": comparisons,
    }
    Path(args.out_json).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fieldnames = [
        "target_ordinal", "target", "channel",
        "A_settled", "A_expansions", "A_elapsed_s",
        "B_settled", "B_expansions", "B_elapsed_s",
        "C_settled", "C_expansions", "C_elapsed_s",
    ]
    with Path(args.out_csv).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(TARGET_COUNT):
            base = keyed[("A", i)]
            out = {"target_ordinal": i, "target": base["target"], "channel": base["channel"]}
            for arm in ARMS:
                row = keyed[(arm, i)]
                out[f"{arm}_settled"] = bool(row.get("settled"))
                out[f"{arm}_expansions"] = int(row["expansions"])
                out[f"{arm}_elapsed_s"] = float(row["elapsed_search_s"])
            writer.writerow(out)

    md = [
        "# DATA MIND Hilbert Ablation 001 — Results",
        "",
        "Primary endpoint: verifier-accepted settlement within the same 20,000-expansion budget.",
        "",
        "| Arm | Settled | Rate | P | R | Median expansions |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        s = arm_summary[arm]
        md.append(
            f"| {arm} | {s['settled']}/{s['total']} | {s['settlement_rate']:.3f} | "
            f"{s['P_settled']}/{s['P_total']} | {s['R_settled']}/{s['R_total']} | "
            f"{s['median_expansions_all']} |"
        )
    md += ["", "## Paired comparisons", ""]
    for name, c in comparisons.items():
        md.append(
            f"- **{name}**: rate difference {c['settlement_rate_difference']:+.3f}; "
            f"discordant wins {c['discordant_left_wins']} vs {c['discordant_right_wins']}; "
            f"median expansion delta on jointly settled targets "
            f"{c['median_expansion_delta_on_joint_settled']}."
        )
    Path(args.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
