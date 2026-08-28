#!/usr/bin/env python3
"""
Predator 8.032: protected-goal blended ML with growing non-prcom training sets.

Hard scientific rules:
  * prcom is held out completely.
  * V=1 is a hard constraint.
  * Deployment is gated by the protected objective:
        fewer failures, then fewer verified expansions, then shorter proof.
  * ML augments Predator's built-in ranking; it does not replace it.
  * A learned model is deployed only if it strictly beats the baseline key.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

import predator8_031_generalized_training as P

VERSION = "8.032-protected-blended-growth"


class ScaledRank:
    """Learned residual ranking. Predator's native structural score remains active."""
    def __init__(self, weights, alpha, mm, meta):
        self.weights = np.asarray(weights, dtype=float)
        self.alpha = float(alpha)
        self.base = P.Rank(self.weights, mm, meta)

    def scores(self, goal, items):
        return [self.alpha * x for x in self.base.scores(goal, items)]

    def __call__(self, goal, items):
        return self.scores(goal, items)


def choose_eval(master, n):
    ordered = sorted(master, key=lambda z: (z.logic, z.order))
    if not ordered:
        return []
    if len(ordered) <= n:
        return ordered
    picks = []
    for i in range(n):
        j = round(i * (len(ordered) - 1) / max(1, n - 1))
        z = ordered[j]
        if z not in picks:
            picks.append(z)
    return picks[:n]


def growth_sizes(available, rounds):
    rounds = max(1, int(rounds))
    available = max(1, int(available))
    raw = [max(4, math.ceil(available * r / rounds)) for r in range(1, rounds + 1)]
    out = []
    for x in raw:
        x = min(available, x)
        if not out or x > out[-1]:
            out.append(x)
    if out[-1] != available:
        out.append(available)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--holdout", default="prcom")
    ap.add_argument("--holdout-gap", type=int, default=32)
    ap.add_argument("--targets", type=int, default=48)
    ap.add_argument("--eval-theorems", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--exact-targets", type=int, default=8)
    ap.add_argument("--exact-depth", type=int, default=4)
    ap.add_argument("--exact-budget", type=int, default=500)
    ap.add_argument("--search-budget", type=int, default=180)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--out", default="p8_032_protected_blended_model.json")
    ap.add_argument("--report", default="p8_032_protected_blended_report.json")
    a = ap.parse_args()

    t0 = time.perf_counter()
    E = P.RX.load_engine(a.engine)
    mm = E.load(a.environment, say=print)
    hold = mm.order.index(a.holdout)
    print(
        f"[GUARD] holdout={a.holdout}; proof_used=False downstream=False "
        f"gap={a.holdout_gap}; protected=verified-expansions"
    )

    meta = P.proof_meta(mm, hold)
    master = P.select(mm, a.holdout, a.targets + a.eval_theorems, a.holdout_gap, a.seed)
    eval_set = choose_eval(master, a.eval_theorems)
    eval_labels = {z.label for z in eval_set}
    train_pool = [z for z in master if z.label not in eval_labels]
    for z in train_pool:
        z.split = "train"
    for z in eval_set:
        z.split = "validation"

    print("[SPLIT] train_pool", len(train_pool), "frozen_eval", [z.label for z in eval_set])

    ctxs = {}
    for z in eval_set:
        ctxs[z.label] = P.context(E, mm, z.label)

    base_rows, base_key = P.eval_search(E, mm, eval_set, ctxs, a.search_budget, None)
    print("[BASELINE]", base_key, base_rows)

    exact_records = []
    exact_candidates = sorted(train_pool, key=lambda q: (q.logic, q.order))[:a.exact_targets]
    for i, z in enumerate(exact_candidates, 1):
        try:
            c = ctxs.get(z.label) or P.context(E, mm, z.label)
            ctxs[z.label] = c
            z.exact_h, z.lower, z.exact_steps, expanded = P.exact(
                E, mm, c, a.exact_depth, a.exact_budget
            )
            rec = {
                "theorem": z.label,
                "exact_h": z.exact_h,
                "lower_bound": z.lower,
                "exact_proof_steps": z.exact_steps,
                "expanded": expanded,
            }
            exact_records.append(rec)
            print(
                f"[EXACT] {i} {z.label} exact_h={z.exact_h} "
                f"H>={z.lower} expanded={expanded}"
            )
        except Exception as e:
            print("[EXACT] fail", z.label, e)

    best = {
        "kind": "baseline",
        "protected_key": list(base_key),
        "rows": base_rows,
        "round": 0,
        "C": None,
        "alpha": 0.0,
        "weights": [0.0] * len(P.PF),
        "ranking": None,
    }

    history = []
    sizes = growth_sizes(len(train_pool), a.rounds)
    C_grid = [0.05, 1.0, 5.0]
    alpha_grid = [0.02, 0.10, 0.25, 0.50, 1.0]

    for ridx, ntrain in enumerate(sizes, 1):
        round_train = train_pool[:ntrain]
        combined = round_train + eval_set
        X, y, vg, round_ctxs, _ = P.dataset(E, mm, combined, meta, a.seed + ridx)
        ctxs.update(round_ctxs)
        if len(y) == 0:
            print("[ROUND]", ridx, "no training pairs")
            continue
        print(
            f"[ROUND] {ridx} train_theorems={ntrain} pairs={len(y)} "
            f"parameters={len(P.PF)}"
        )

        round_best = None
        for C in C_grid:
            w = P.fit_rank(X, y, C)
            raw_rank = P.Rank(w, mm, meta)
            rank_metrics = P.rmetrics(vg, raw_rank)
            for alpha in alpha_grid:
                R = ScaledRank(w, alpha, mm, meta)
                rows, key = P.eval_search(E, mm, eval_set, ctxs, a.search_budget, R)
                rec = {
                    "round": ridx,
                    "train_theorems": ntrain,
                    "pairs": int(len(y)),
                    "C": C,
                    "alpha": alpha,
                    "protected_key": list(key),
                    "rows": rows,
                    "ranking": rank_metrics,
                    "weights": w.tolist(),
                }
                history.append(rec)
                print(
                    "[CANDIDATE]",
                    "round", ridx,
                    "C", C,
                    "alpha", alpha,
                    "protected", key,
                )
                if round_best is None or key < tuple(round_best["protected_key"]):
                    round_best = rec

                if key < tuple(best["protected_key"]):
                    best = {"kind": "learned_blend", **rec}
                    print(
                        "[ACCEPT]",
                        "round", ridx,
                        "C", C,
                        "alpha", alpha,
                        "protected", key,
                    )

        if round_best is not None:
            print(
                "[ROUND-BEST]",
                ridx,
                tuple(round_best["protected_key"]),
                "C", round_best["C"],
                "alpha", round_best["alpha"],
            )

    accepted = best["kind"] != "baseline"
    print(
        "[DEPLOY]",
        best["kind"],
        "accepted", accepted,
        "protected", tuple(best["protected_key"]),
    )

    model = {
        "version": VERSION,
        "protected_goal": "minimize verified expansions N; V=1 hard constraint",
        "environment_sha256": P.sha256(a.environment),
        "holdout": {
            "label": a.holdout,
            "target_proof_used": False,
            "downstream_used": False,
            "excluded_preceding_theorems": a.holdout_gap,
        },
        "policy": {
            "kind": best["kind"],
            "accepted_over_baseline": accepted,
            "features": P.PF,
            "n_learned_weights": len(P.PF),
            "weights": best["weights"],
            "alpha": best["alpha"],
            "C": best["C"],
            "protected_key": best["protected_key"],
            "round": best["round"],
        },
        "baseline": {
            "protected_key": list(base_key),
            "rows": base_rows,
        },
        "training_growth": {
            "round_sizes": sizes,
            "frozen_eval": [z.label for z in eval_set],
            "exact_records": exact_records,
        },
    }
    Path(a.out).write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")

    report = {
        "version": VERSION,
        "elapsed_seconds": time.perf_counter() - t0,
        "model": model,
        "history": history,
        "train_pool": [z.__dict__ for z in train_pool],
        "eval_set": [z.__dict__ for z in eval_set],
    }
    Path(a.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("[DONE]", a.out, a.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
