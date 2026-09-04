#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean
from typing import Any


def read_result(root: Path, ordinal: int, lane: str) -> dict[str, Any] | None:
    matches = list(root.glob(f"**/target-{ordinal:02d}/{lane}/result.json"))
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(f"duplicate results for target {ordinal} lane {lane}: {matches}")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def proved(r: dict[str, Any] | None) -> bool:
    return bool(r) and r.get("status") == "PROVED" and (r.get("verification") or {}).get("accepted") is True


def best_expansions(*rows: dict[str, Any] | None) -> int | None:
    vals = [int(r["expansions"]) for r in rows if proved(r)]
    return min(vals) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    root = Path(args.root)

    rows: list[dict[str, Any]] = []
    for ordinal in range(20):
        a = read_result(root, ordinal, "a-p1")
        p2 = read_result(root, ordinal, "p2")
        c = read_result(root, ordinal, "c-p1")
        if not all((a, p2, c)):
            rows.append({
                "ordinal": ordinal,
                "complete": False,
                "missing": [
                    lane for lane, result in (("a-p1", a), ("p2", p2), ("c-p1", c))
                    if result is None
                ],
            })
            continue

        assert a is not None and p2 is not None and c is not None
        a_settle = proved(a) or proved(p2)
        c_settle = proved(c) or proved(p2)
        rows.append({
            "ordinal": ordinal,
            "target": a["target"],
            "complete": True,
            "A_settled": a_settle,
            "B_settled": a_settle,
            "C_settled": c_settle,
            "A_P1_proved": proved(a),
            "C_P1_proved": proved(c),
            "P2_proved": proved(p2),
            "A_best_lane_expansions": best_expansions(a, p2),
            "C_best_lane_expansions": best_expansions(c, p2),
            "A_P1_expansions": a["expansions"],
            "C_P1_expansions": c["expansions"],
            "P2_expansions": p2["expansions"],
            "shadow_professor_max_credit": (a.get("shadow_professor") or {}).get("max_credit"),
            "shadow_professor_last_credit": (a.get("shadow_professor") or {}).get("last_credit"),
            "C_professor_last_credit": (c.get("reflective_p1") or {}).get("last_professor_credit"),
        })

    complete = [r for r in rows if r.get("complete")]
    a_solved = sum(bool(r["A_settled"]) for r in complete)
    c_solved = sum(bool(r["C_settled"]) for r in complete)
    p2_saves_a = sum(bool(r["P2_proved"]) and not bool(r["A_P1_proved"]) for r in complete)
    p2_saves_c = sum(bool(r["P2_proved"]) and not bool(r["C_P1_proved"]) for r in complete)

    solved_shadow = [
        float(r["shadow_professor_max_credit"])
        for r in complete
        if r["A_P1_proved"] and r["shadow_professor_max_credit"] is not None
    ]
    unsolved_shadow = [
        float(r["shadow_professor_max_credit"])
        for r in complete
        if not r["A_P1_proved"] and r["shadow_professor_max_credit"] is not None
    ]

    summary = {
        "experiment": "DATA MIND 3.1 Experiment 001 — Professor/Self-Awareness Frozen-20 Ablation",
        "official_runtime_claim": False,
        "expected_targets": 20,
        "complete_targets": len(complete),
        "arms": {
            "A": "balanced fixed P1 + common independent fixed P2",
            "B": "Arm A exact trajectory + shadow Professor measurement; no search influence",
            "C": "Professor/self-aware adaptive P1 (Child off) + same common P2",
        },
        "pair_budget": {
            "max_expansions": 100000,
            "lane_max_expansions": 50000,
            "time_budget_s": 1800,
            "lane_timeout_s": 900,
        },
        "settlement_counts": {
            "A": a_solved,
            "B": a_solved,
            "C": c_solved,
            "C_minus_A": c_solved - a_solved,
        },
        "P1_settlement_counts": {
            "A_P1": sum(bool(r["A_P1_proved"]) for r in complete),
            "C_P1": sum(bool(r["C_P1_proved"]) for r in complete),
        },
        "independent_partner_hedge": {
            "P2_proved": sum(bool(r["P2_proved"]) for r in complete),
            "P2_saved_A_when_A_P1_failed": p2_saves_a,
            "P2_saved_C_when_C_P1_failed": p2_saves_c,
        },
        "shadow_professor_diagnostic": {
            "mean_max_credit_A_P1_solved": fmean(solved_shadow) if solved_shadow else None,
            "mean_max_credit_A_P1_unsolved": fmean(unsolved_shadow) if unsolved_shadow else None,
            "note": "descriptive calibration diagnostic only; n=20 and no significance claim",
        },
        "interpretation_rule": (
            "Primary evidence is verifier-accepted settlement. Professor scores are secondary diagnostics. "
            "B must have exactly the same settlement outcome as A by construction."
        ),
        "results": rows,
    }

    Path(args.out).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
