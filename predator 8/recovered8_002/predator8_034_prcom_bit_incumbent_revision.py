#!/usr/bin/env python3
"""
Predator 8.034: theorem-specific bit-incumbent revision for prcom.

This is intentionally NOT a blind-transfer experiment.  It starts from the
28-parameter model learned without prcom in 8.033, then exposes only aggregate
label-use counts from the best recovered verifier-accepted historical prcom
certificate.  The exact certificate order is never installed as a replay path
or inference rule.

Hard constraint:
    V(P) = 1

Protected incumbent:
    (B, N, M) = (470 bits, 35 expansions, 28 proof steps)

A new certificate wins lexicographically on (B, N, M).  Thus no expansion
improvement may trade away even one compressed-certificate bit.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

import predator8_031_generalized_training as P
import predator8_033_bit_coupled_adaptive as B

VERSION = "8.034-prcom-bit-incumbent-revision"
INCUMBENT = (470, 35, 28)

# Best recovered historical certificate: independently verifier-accepted in the
# 35-expansion 8.029/8.030 lineage. Deliberately store only the multiset of
# labels, not their order, so the search policy cannot replay the certificate.
INCUMBENT_COUNTS = {
    "cA.wceq": 7,
    "cB.wceq": 7,
    "csn": 6,
    "cun": 2,
    "cpr": 2,
    "df-pr": 2,
    "uncom": 1,
    "3eqtr4i": 1,
}

# Logged 8.033 selected 28-vector (C=5.0), frozen as theta_0.
THETA0 = np.array([
     0.00000000,
    -1.12938839,
    -0.24989268,
     2.15252925,
    -1.34439208,
     0.38474809,
     0.00877048,
     0.18625675,
     0.00820086,
    -0.46110091,
    -0.52494418,
     2.22987554,
     0.00000000,
    -0.15791677,
     0.13715819,
     1.94550094,
     0.16387990,
     2.64144262,
    -1.39954609,
     2.03735622,
     3.51530565,
    -0.37087453,
     2.63210111,
    -2.76901785,
     0.00437566,
     0.11175614,
    -0.34324586,
     2.13286403,
], dtype=float)
assert len(THETA0) == 28

# Coupled arm groups. Index 22 is lemma/reuse and is deliberately coupled to
# the bank/reuse arm; 25:28 are awareness.
GROUPS = {
    "compression": [15, 16, 26],
    "reuse_lemma": [17, 22, 27],
    "shortcut": [18, 19],
    "search": [20, 21],
    "creativity": [23],
    "revision": [24],
    "awareness": [25, 26, 27],
}

PROFILE_PARAMS = {
    # 8.033 evaluation profile
    "simple": (0.0, 0.0, 0.0, 0.0, 0.0, 64, 1.0),
    # 8.030 I=5 search-arm regime
    "i5": (1.60, 0.95, 0.75, 0.10, 0.85, 96, 1.0),
    # 8.030 I=4 intermediate torpor regime
    "i4": (1.35, 0.75, 0.55, 0.12, 0.68, 80, 1.0),
}


def revised_weights(parent: np.ndarray, multipliers: dict[str, float]) -> np.ndarray:
    w = np.asarray(parent, float).copy()
    for name, mult in multipliers.items():
        for i in GROUPS[name]:
            # Awareness/bit-pressure overlaps other groups. Multipliers compose.
            w[i] *= float(mult)
    return w


def experience_reuse(strength: float) -> Counter:
    # Aggregate label counts only: deliberately discards certificate order.
    c = Counter(INCUMBENT_COUNTS)
    for k in list(c):
        c[k] = max(1, int(round(c[k] * strength)))
    return c


def make_profile(E, name: str):
    return E.Profile("8.034-" + name, *PROFILE_PARAMS[name])


def verified_search(E, mm, ctx, budget, rank, seed, profile_name):
    prof = make_profile(E, profile_name)
    res, n = E.prove(
        ctx.goal, ctx.index, budget, max_depth=12, rank=rank, say=None,
        progress=0, max_open=8, profile=prof, seed=seed,
    )
    row = {
        "verified": False,
        "expansions": int(n),
        "proof_steps": None,
        "logical_steps": None,
        "compressed_bits": None,
        "codec": B.CODEC,
        "profile": profile_name,
        "seed": int(seed),
    }
    if res is None:
        return row
    try:
        root, sub = res
        fv, fb = P.RX.formal_variables(E, mm, ctx.cut)
        proof = list(root.emit(sub, fv, fb))
        q = P.verify_result(E, mm, ctx, res)
        if q is None:
            return row
        bits = B.cert_bits(proof)
        row.update({
            "verified": True,
            "proof_steps": int(q[0]),
            "logical_steps": int(q[1]),
            "compressed_bits": int(bits),
            "proof_labels": proof,
        })
    except Exception as exc:
        row["error"] = str(exc)
    return row


def single_key(row):
    if not row["verified"]:
        return (10**12, 10**12, 10**12)
    return (
        int(row["compressed_bits"]),
        int(row["expansions"]),
        int(row["proof_steps"]),
    )


def aggregate_key(rows, budget):
    fail = sum(not r["verified"] for r in rows)
    bits = sum(r["compressed_bits"] if r["verified"] else 10**12 for r in rows)
    exp = sum(r["expansions"] if r["verified"] else budget for r in rows)
    steps = sum(r["proof_steps"] if r["verified"] else 10**6 for r in rows)
    return (fail, int(bits), int(exp), int(steps))


def candidate(name, parent, profile, reuse_strength=8.0, **mult):
    return {
        "name": name,
        "weights": revised_weights(parent, mult),
        "profile": profile,
        "reuse_strength": float(reuse_strength),
        "multipliers": mult,
    }


def round_one(parent):
    return [
        candidate("theta0-simple", parent, "simple", 8.0),
        candidate("theta0-i5", parent, "i5", 8.0),
        candidate("theta0-i4", parent, "i4", 8.0),
        candidate("reuse-i5", parent, "i5", 12.0,
                  reuse_lemma=1.35, awareness=1.20),
        candidate("bits-i5", parent, "i5", 8.0,
                  compression=1.35, awareness=1.20),
        candidate("shortcut-reuse-i5", parent, "i5", 12.0,
                  shortcut=1.25, reuse_lemma=1.30, awareness=1.25),
        candidate("crossarm-i5", parent, "i5", 14.0,
                  compression=1.20, reuse_lemma=1.35, shortcut=1.15,
                  search=1.10, awareness=1.40),
        candidate("explore-i4", parent, "i4", 10.0,
                  creativity=1.25, revision=1.50, awareness=1.35),
        candidate("bit-pressure-i5", parent, "i5", 10.0,
                  compression=1.55, reuse_lemma=1.20, search=0.90,
                  awareness=1.50),
    ]


def local_round(parent, parent_profile, r):
    # Successive revision: narrow coupled perturbations around previous winner.
    amt = 1.20 if r == 2 else 1.10
    inv = 1.0 / amt
    return [
        candidate(f"r{r}-parent", parent, parent_profile, 12.0),
        candidate(f"r{r}-reuse+", parent, parent_profile, 16.0,
                  reuse_lemma=amt, awareness=amt),
        candidate(f"r{r}-compress+", parent, parent_profile, 12.0,
                  compression=amt, awareness=amt),
        candidate(f"r{r}-shortcut+", parent, parent_profile, 14.0,
                  shortcut=amt, reuse_lemma=amt),
        candidate(f"r{r}-search+", parent, "i5", 12.0,
                  search=amt, awareness=amt),
        candidate(f"r{r}-creative+", parent, "i4", 12.0,
                  creativity=amt, revision=amt, awareness=amt),
        candidate(f"r{r}-cross+", parent, "i5", 16.0,
                  compression=amt, reuse_lemma=amt, shortcut=amt,
                  search=amt, awareness=amt),
        candidate(f"r{r}-cross-", parent, parent_profile, 10.0,
                  compression=inv, creativity=amt, revision=amt,
                  awareness=amt),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--target", default="prcom")
    ap.add_argument("--budget", type=int, default=500)
    ap.add_argument("--seeds", default="2301,2302,2303")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--report", default="p8_034_report.json")
    ap.add_argument("--csv", default="p8_034_candidates.csv")
    a = ap.parse_args()

    t0 = time.perf_counter()
    # The 470-bit value was audited directly from the historical artifact with
    # the frozen 8.033 codec before this run. Only its unordered label counts
    # are carried into 8.034.
    E = P.RX.load_engine(a.engine)
    mm = E.load(a.environment, say=print)
    ctx = P.context(E, mm, a.target)
    seeds = [int(x) for x in a.seeds.split(",") if x.strip()]

    # The target theorem is cut out of the available assertion index by context().
    # We never call mm.decompress(target, ...).
    print(
        f"[GUARD] target={a.target}; theorem_specific=True; exact_order_replay=False; "
        f"target_rule_unavailable=True; codec={B.CODEC}; V=1"
    )
    print(f"[INCUMBENT] B={INCUMBENT[0]} N={INCUMBENT[1]} M={INCUMBENT[2]}")
    print("[EXPERIENCE] aggregate label-use counts only; order discarded",
          dict(Counter(INCUMBENT_COUNTS)))

    bit_cache = {}
    history = []
    global_best = {
        "key": INCUMBENT,
        "source": "historical-incumbent",
        "row": None,
    }
    parent = THETA0.copy()
    parent_profile = "i5"
    meta = P.proof_meta(mm, ctx.cut)

    for ridx in range(1, a.rounds + 1):
        props = round_one(parent) if ridx == 1 else local_round(parent, parent_profile, ridx)
        round_best = None
        print(f"[ROUND] {ridx} proposals={len(props)}")
        for proposal in props:
            reuse = experience_reuse(proposal["reuse_strength"])
            rows = []
            for seed in seeds:
                # Independent seed trial: awareness call-history starts fresh.
                rank = B.CoupledRank(proposal["weights"], mm, meta, reuse, bit_cache)
                row = verified_search(E, mm, ctx, a.budget, rank, seed, proposal["profile"])
                rows.append(row)
                key = single_key(row)
                if key < global_best["key"]:
                    global_best = {"key": key, "source": proposal["name"], "row": row}
                    print("[NEW-BEST]", proposal["name"], "seed", seed, "key", key)
                print("[TRIAL]", "round", ridx, proposal["name"], "seed", seed,
                      "key", key, "verified", row["verified"])
            aggregate = aggregate_key(rows, a.budget)
            rec = {
                "round": ridx,
                "name": proposal["name"],
                "profile": proposal["profile"],
                "reuse_strength": proposal["reuse_strength"],
                "multipliers": proposal["multipliers"],
                "aggregate_key": list(aggregate),
                "best_single_key": list(min(single_key(x) for x in rows)),
                "rows": rows,
                "weights": proposal["weights"].tolist(),
            }
            history.append(rec)
            print("[CANDIDATE]", ridx, proposal["name"], "aggregate", aggregate,
                  "best", tuple(rec["best_single_key"]))
            if round_best is None or aggregate < tuple(round_best["aggregate_key"]):
                round_best = rec

        if round_best is None:
            break
        parent = np.asarray(round_best["weights"], float)
        parent_profile = round_best["profile"]
        print("[ROUND-WINNER]", ridx, round_best["name"],
              tuple(round_best["aggregate_key"]),
              "best", tuple(round_best["best_single_key"]))

    improved = tuple(global_best["key"]) < INCUMBENT
    if improved:
        print("[DEPLOY] ACCEPT new incumbent", global_best["key"],
              "source", global_best["source"])
    else:
        print("[DEPLOY] RETAIN historical incumbent", INCUMBENT,
              "best_new", global_best["key"])

    report = {
        "version": VERSION,
        "target": a.target,
        "hard_constraint": "V(P)=1",
        "protected_objective": "FirstOccurrenceGammaV1 compressed bits",
        "scientific_mode": "theorem-specific adaptation after verified experience",
        "certificate_order_exposed_to_policy": False,
        "incumbent": {
            "compressed_bits": INCUMBENT[0],
            "expansions": INCUMBENT[1],
            "proof_steps": INCUMBENT[2],
            "codec": B.CODEC,
        },
        "best": {
            "key": list(global_best["key"]),
            "source": global_best["source"],
            "row": global_best["row"],
            "improved_incumbent": improved,
        },
        "history": history,
        "elapsed_seconds": time.perf_counter() - t0,
    }
    Path(a.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(a.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "name", "profile", "failures", "sum_bits",
                         "sum_expansions", "sum_steps", "best_bits", "best_expansions",
                         "best_steps"])
        for rec in history:
            writer.writerow([rec["round"], rec["name"], rec["profile"],
                             *rec["aggregate_key"], *rec["best_single_key"]])

    print("[DONE]", a.report, a.csv, "elapsed=%.1fs" % report["elapsed_seconds"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
