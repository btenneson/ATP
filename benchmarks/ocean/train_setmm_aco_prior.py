#!/usr/bin/env python3
"""Learn representation-independent ACO memory parameters from all set.mm proofs.

The learner scans every complete theorem proof, keeps only logical assertion
steps, fits a preferential-reuse exponent alpha, and derives evaporation rho
from empirical assertion-reuse gaps.  It does not inspect any Ocean instance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

import metamath


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("setmm", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--progress", type=int, default=5000)
    args = ap.parse_args()

    mm = metamath.load(str(args.setmm), say=print)
    kind = metamath.classify(mm)
    theorems = [l for l in mm.order if mm.labels[l][0] == "$p"]
    alpha_grid = [i / 10.0 for i in range(31)]
    ll = [0.0 for _ in alpha_grid]

    complete = 0
    incomplete = 0
    skipped = 0
    proofs_with_logic = 0
    total_logical_steps = 0
    distinct_logic_counts = []
    reuse_events = 0
    reuse_gaps = []

    for ti, label in enumerate(theorems, 1):
        try:
            proof = mm.decompress(label, mm.proofs[label])
        except Exception:
            skipped += 1
            continue
        if "?" in proof:
            incomplete += 1
            continue
        complete += 1
        seq = [s for s in proof if kind.get(s) == "logic"]
        if not seq:
            continue
        proofs_with_logic += 1
        total_logical_steps += len(seq)
        distinct_logic_counts.append(len(set(seq)))

        counts = {}
        last = {}
        sums = [0.0 for _ in alpha_grid]

        for idx, lab in enumerate(seq):
            c = counts.get(lab, 0)
            if c > 0:
                reuse_events += 1
                reuse_gaps.append(idx - last[lab])
                # Conditional likelihood over labels already seen in this proof.
                for j, a in enumerate(alpha_grid):
                    denom = sums[j]
                    if denom <= 0:
                        raise RuntimeError("nonpositive preferential-reuse denominator")
                    ll[j] += a * math.log(c) - math.log(denom)

            for j, a in enumerate(alpha_grid):
                if c > 0:
                    sums[j] -= c ** a
                sums[j] += (c + 1) ** a
            counts[lab] = c + 1
            last[lab] = idx

        if args.progress and ti % args.progress == 0:
            print(
                f"[TRAIN] {ti}/{len(theorems)} complete={complete} "
                f"logical_steps={total_logical_steps} reuse_events={reuse_events}",
                flush=True,
            )

    if reuse_events == 0 or not reuse_gaps:
        raise SystemExit("no logical assertion reuse events found; cannot fit ACO prior")

    best_i = max(range(len(alpha_grid)), key=lambda i: ll[i])
    alpha = alpha_grid[best_i]
    mean_gap = statistics.fmean(reuse_gaps)
    rho = 1.0 - math.exp(-1.0 / mean_gap)

    out = {
        "kind": "set.mm representation-independent ACO colony-memory prior",
        "environment_sha256": sha256(args.setmm),
        "theorems_total": len(theorems),
        "complete_proofs_scanned": complete,
        "incomplete_proofs": incomplete,
        "decompression_skips": skipped,
        "proofs_with_logical_steps": proofs_with_logic,
        "total_logical_steps": total_logical_steps,
        "mean_distinct_logical_assertions_per_proof": (
            statistics.fmean(distinct_logic_counts) if distinct_logic_counts else None
        ),
        "reuse_events": reuse_events,
        "mean_reuse_gap_logical_steps": mean_gap,
        "median_reuse_gap_logical_steps": statistics.median(reuse_gaps),
        "learned": {
            "alpha": alpha,
            "rho": rho,
        },
        "alpha_fit": {
            "grid": alpha_grid,
            "conditional_reuse_log_likelihood": ll,
            "best_grid_index": best_i,
            "model": "P(j|reuse,history) proportional to prior_count(j)^alpha",
        },
        "rho_fit": {
            "formula": "rho = 1 - exp(-1 / mean_reuse_gap)",
            "mean_reuse_gap": mean_gap,
        },
        "scope_note": (
            "All complete theorem proofs in the pinned set.mm are scanned. "
            "Only logical assertion-step recurrence is used; no Ocean instance, "
            "seed, planted route, BFS distance, or target solution is used."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("[LEARNED] alpha=", alpha)
    print("[LEARNED] rho=", rho)
    print("[LEARNED] reuse_events=", reuse_events)
    print("[LEARNED] mean_reuse_gap=", mean_gap)


if __name__ == "__main__":
    main()
