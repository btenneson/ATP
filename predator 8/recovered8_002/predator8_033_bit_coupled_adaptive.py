#!/usr/bin/env python3
"""Predator 8.033: bit-primary coupled adaptive training with prcom blind holdout.

Protected objective
-------------------
For every candidate proof P we first require V(P)=1.  Among verifier-accepted
proofs, the primary objective is the exact bit length B(P) under the frozen,
deterministic, lossless FirstOccurrenceGammaV1 certificate code defined here.
The deployment key is lexicographic:
    (# failures, sum compressed bits, sum expansions, sum proof steps).

Scientific guards
-----------------
* prcom and all downstream theorems are absent from training.
* the prcom proof is never decompressed or inspected before the blind test.
* the verifier and certificate code are frozen during the run.
* the learned policy has exactly 28 fitted coefficients grouped across ML,
  compression, shortcut, search, lemma/bank, creativity, revision, awareness,
  and cross-arm coupling coordinates.
* baseline remains deployed unless a learned model strictly improves the
  protected validation key.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import predator8_031_generalized_training as P

VERSION = "8.033-bit-primary-coupled-adaptive"
CODEC = "FirstOccurrenceGammaV1"

FEATURES = P.PF + [
    "log_candidate_label_bytes",          # compression arm
    "log_candidate_known_cert_bits",      # compression arm
    "log_training_reuse",                 # bank/reuse arm
    "shortcut_samehead_closer",           # shortcut arm
    "shortcut_overlap_theorem",           # shortcut arm
    "search_overlap_sizefit",              # search arm
    "search_depth_closer",                 # search arm
    "lemma_reuse_theorem",                 # lemma / bank arm
    "creativity_novel_closer",             # creativity arm
    "revision_complexity_pressure",        # revision controller
    "awareness_head_overlap_conflict",     # awareness
    "awareness_bit_pressure",              # awareness
    "awareness_crossarm_reuse",            # awareness / coupling
]
assert len(FEATURES) == 28

GROUPS = {
    "base_ML_structural": list(range(0, 15)),
    "compression": [15, 16],
    "bank_reuse": [17, 22],
    "shortcut": [18, 19],
    "search": [20, 21],
    "creativity": [23],
    "revision": [24],
    "awareness_coupling": [25, 26, 27],
}


def gamma_bits(n: int) -> str:
    """Elias-gamma code for positive integer n."""
    if n < 1:
        raise ValueError("gamma expects n>=1")
    b = bin(n)[2:]
    return "0" * (len(b) - 1) + b


def gamma_read(bits: str, pos: int) -> tuple[int, int]:
    z = 0
    while pos < len(bits) and bits[pos] == "0":
        z += 1
        pos += 1
    if pos >= len(bits):
        raise ValueError("truncated gamma code")
    end = pos + z + 1
    if end > len(bits):
        raise ValueError("truncated gamma payload")
    return int(bits[pos:end], 2), end


def encode_certificate(labels: list[str]) -> str:
    """Deterministic lossless code: first-use dictionary + gamma-coded indices."""
    dictionary = []
    index = {}
    stream = []
    for lab in labels:
        if lab not in index:
            index[lab] = len(dictionary) + 1
            dictionary.append(lab)
        stream.append(index[lab])
    out = [gamma_bits(len(dictionary) + 1)]  # +1 permits empty dictionary
    for lab in dictionary:
        raw = lab.encode("utf-8")
        out.append(gamma_bits(len(raw) + 1))
        out.extend(f"{byte:08b}" for byte in raw)
    out.append(gamma_bits(len(stream) + 1))
    out.extend(gamma_bits(i) for i in stream)
    return "".join(out)


def decode_certificate(bits: str) -> list[str]:
    pos = 0
    nd1, pos = gamma_read(bits, pos)
    nd = nd1 - 1
    dictionary = []
    for _ in range(nd):
        ln1, pos = gamma_read(bits, pos)
        ln = ln1 - 1
        end = pos + 8 * ln
        if end > len(bits):
            raise ValueError("truncated label bytes")
        raw = bytes(int(bits[j:j+8], 2) for j in range(pos, end, 8))
        pos = end
        dictionary.append(raw.decode("utf-8"))
    ns1, pos = gamma_read(bits, pos)
    ns = ns1 - 1
    out = []
    for _ in range(ns):
        i, pos = gamma_read(bits, pos)
        if not (1 <= i <= len(dictionary)):
            raise ValueError("bad dictionary reference")
        out.append(dictionary[i-1])
    if pos != len(bits):
        raise ValueError("noncanonical trailing bits")
    return out


def cert_bits(labels: list[str]) -> int:
    b = encode_certificate(labels)
    if decode_certificate(b) != list(labels):
        raise AssertionError("certificate codec roundtrip failed")
    return len(b)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def known_proof_bits(mm, label: str, cache: dict[str, int]) -> int:
    if label in cache:
        return cache[label]
    value = 0
    try:
        if label in mm.proofs:
            q = mm.decompress(label, mm.proofs[label])
            if q and "?" not in q:
                value = cert_bits(list(q))
    except Exception:
        value = 0
    cache[label] = value
    return value


def feat28(goal, item, mm, meta, reuse: Counter, bit_cache: dict[str, int]):
    b = P.feat(goal, item, mm, meta)
    lab = item[0]
    label_bytes = math.log1p(len(lab.encode("utf-8")))
    kb = math.log1p(known_proof_bits(mm, lab, bit_cache))
    rf = math.log1p(reuse.get(lab, 0))
    overlap = float(b[11])
    same = float(b[3])
    closer = float(b[4])
    theorem = float(b[8])
    sizegap = float(b[2])
    depthgap = float(b[14])
    hyp_burden = float(b[5] + b[6] + b[7])
    extra = np.array([
        label_bytes,
        kb,
        rf,
        same * closer,
        overlap * theorem,
        overlap / (1.0 + max(0.0, sizegap)),
        closer / (1.0 + max(0.0, depthgap)),
        theorem * rf,
        (1.0 - overlap) * closer,
        (sizegap + depthgap) * (1.0 + hyp_burden),
        abs(same - overlap),
        kb * (1.0 - overlap),
        rf * overlap * (0.5 + same),
    ], dtype=float)
    return np.concatenate([b, extra])


def training_reuse(mm, targets) -> Counter:
    c = Counter()
    for z in targets:
        try:
            q = mm.decompress(z.label, mm.proofs[z.label])
            if q and "?" not in q:
                c.update(q)
        except Exception:
            pass
    return c


def pair_dataset(E, mm, targets, meta, reuse, bit_cache, seed):
    rng = random.Random(seed)
    X, y, sw = [], [], []
    rows = []
    contexts = {}
    for j, z in enumerate(targets, 1):
        try:
            q = mm.decompress(z.label, mm.proofs[z.label])
            if not q or "?" in q:
                continue
            source_bits = cert_bits(list(q))
            c = P.context(E, mm, z.label)
            contexts[z.label] = c
            act = P.final_action(mm, z.label)
            closers, openers = c.index.candidates(c.goal)
            items = closers + openers
            pos = next((it for it in items if it[0] == act), None)
            if pos is None:
                continue
            neg = [it for it in items if it[0] != act]
            rng.shuffle(neg)
            neg = neg[:28]
            xp = feat28(c.goal, pos, mm, meta, reuse, bit_cache)
            # Shorter verified source certificates have greater training authority.
            authority = 1.0 / max(1.0, math.log2(source_bits + 2.0))
            for it in neg:
                xn = feat28(c.goal, it, mm, meta, reuse, bit_cache)
                d = xp - xn
                X.extend([d, -d])
                y.extend([1, 0])
                sw.extend([authority, authority])
            rows.append({
                "theorem": z.label,
                "stored_proof_steps": len(q),
                "stored_cert_bits": source_bits,
                "candidate_count": len(items),
                "positive_action": act,
            })
            print(f"[TRAIN-DATA] {j}/{len(targets)} {z.label} bits={source_bits} pairs={2*len(neg)}")
        except Exception as exc:
            print("[TRAIN-DATA] skip", z.label, exc)
    if not X:
        raise RuntimeError("no training pairs")
    return np.vstack(X), np.asarray(y, int), np.asarray(sw, float), rows, contexts


def fit28(X, y, sw, C):
    scaler = StandardScaler(with_mean=False)
    Xs = scaler.fit_transform(X)
    model = LogisticRegression(
        C=C, fit_intercept=False, max_iter=1500, solver="liblinear", random_state=0
    ).fit(Xs, y, sample_weight=sw)
    scale = np.where(scaler.scale_ == 0, 1.0, scaler.scale_)
    return model.coef_[0] / scale


class CoupledRank:
    """28-parameter ranker. Awareness coordinates couple all arm signals."""
    def __init__(self, weights, mm, meta, reuse, bit_cache):
        self.w = np.asarray(weights, float)
        self.mm = mm
        self.meta = meta
        self.reuse = reuse
        self.bit_cache = bit_cache
        self.calls = 0

    def scores(self, goal, items):
        self.calls += 1
        vals = [float(np.dot(self.w, feat28(goal, it, self.mm, self.meta, self.reuse, self.bit_cache))) for it in items]
        if not vals:
            return vals
        # Level-2 awareness: as the search persists, the fitted awareness/coupling
        # coordinates increasingly determine revisions of the candidate ordering.
        awareness_strength = math.tanh(float(np.linalg.norm(self.w[25:28])) / 10.0)
        persistence = min(1.0, math.log1p(self.calls) / math.log(2000.0))
        mean = sum(vals) / len(vals)
        gain = 1.0 + awareness_strength * persistence
        return [mean + gain * (v - mean) for v in vals]

    def __call__(self, goal, items):
        return self.scores(goal, items)


def verified_search(E, mm, c, budget, rank, seed):
    prof = E.Profile("bit-eval", 0, 0, 0, 0, 0, 64, 1)
    res, n = E.prove(
        c.goal, c.index, budget, max_depth=12, rank=rank, say=None,
        progress=0, max_open=8, profile=prof, seed=seed,
    )
    row = {
        "verified": False,
        "expansions": int(n),
        "proof_steps": None,
        "logical_steps": None,
        "compressed_bits": None,
        "codec": CODEC,
    }
    if res is None:
        return row
    try:
        root, sub = res
        fv, fb = P.RX.formal_variables(E, mm, c.cut)
        proof = list(root.emit(sub, fv, fb))
        q = P.verify_result(E, mm, c, res)
        if q is None:
            return row
        # Bit count is computed only after independent verifier acceptance.
        bits = cert_bits(proof)
        row.update({
            "verified": True,
            "proof_steps": int(q[0]),
            "logical_steps": int(q[1]),
            "compressed_bits": int(bits),
        })
        return row
    except Exception as exc:
        row["error"] = str(exc)
        return row


def protected_key(rows, budget):
    fail = sum(not r["verified"] for r in rows)
    bit_penalty = 10**12
    bits = sum(r["compressed_bits"] if r["verified"] else bit_penalty for r in rows)
    exps = sum(r["expansions"] if r["verified"] else budget for r in rows)
    steps = sum(r["proof_steps"] if r["verified"] else 10**6 for r in rows)
    return (fail, int(bits), int(exps), int(steps))


def eval_set(E, mm, labels, budget, rank, seed):
    rows = []
    for lab in labels:
        c = P.context(E, mm, lab)
        r = verified_search(E, mm, c, budget, rank, seed)
        r["theorem"] = lab
        rows.append(r)
    return rows, protected_key(rows, budget)


def choose_baseline_solvable(E, mm, pool, n, budget):
    chosen, records = [], []
    for lab in pool:
        if lab not in mm.labels or mm.labels[lab][0] != "$p":
            continue
        try:
            c = P.context(E, mm, lab)
            r = verified_search(E, mm, c, budget, None, 0)
            r["theorem"] = lab
            records.append(r)
            print("[EVAL-PROBE]", lab, r)
            if r["verified"]:
                chosen.append(lab)
            if len(chosen) >= n:
                break
        except Exception as exc:
            print("[EVAL-PROBE] skip", lab, exc)
    return chosen, records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--holdout", default="prcom")
    ap.add_argument("--holdout-gap", type=int, default=32)
    ap.add_argument("--train-theorems", type=int, default=36)
    ap.add_argument("--eval-theorems", type=int, default=3)
    ap.add_argument("--eval-budget", type=int, default=250)
    ap.add_argument("--prcom-budget", type=int, default=3500)
    ap.add_argument("--prcom-seeds", default="2301,2302,2303")
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--out", default="p8_033_bit_model.json")
    ap.add_argument("--report", default="p8_033_bit_report.json")
    ap.add_argument("--csv", default="p8_033_training.csv")
    a = ap.parse_args()
    t0 = time.perf_counter()

    E = P.RX.load_engine(a.engine)
    mm = E.load(a.environment, say=print)
    hold = mm.order.index(a.holdout)
    print(
        f"[GUARD] holdout={a.holdout}; target_proof_used=False; downstream=False; "
        f"codec={CODEC}; protected=compressed_bits; V=1"
    )

    # Meta-information is strict pre-prcom only.
    meta = P.proof_meta(mm, hold)
    master = P.select(mm, a.holdout, a.train_theorems + 12, a.holdout_gap, a.seed)

    eval_pool = [
        "simp-10l", "simp2l", "simp13", "pm5.33", "bitrdi", "jctild",
        "ad5ant24", "nesym", "3expa", "mp3an23", "pm2.75", "ifpn",
    ]
    eval_labels, probe_records = choose_baseline_solvable(
        E, mm, eval_pool, a.eval_theorems, a.eval_budget
    )
    if not eval_labels:
        raise RuntimeError("no baseline-solvable evaluation theorem; bit objective cannot be compared")
    print("[EVAL] frozen", eval_labels)

    banned = set(eval_labels) | {a.holdout}
    train = [z for z in master if z.label not in banned][:a.train_theorems]
    for z in train:
        z.split = "train"
    print("[TRAIN] theorems", len(train), "parameters", len(FEATURES))

    reuse = training_reuse(mm, train)
    bit_cache = {}
    X, y, sw, training_rows, contexts = pair_dataset(
        E, mm, train, meta, reuse, bit_cache, a.seed
    )
    print("[PAIRS]", len(y), "fitted_parameters", len(FEATURES))

    baseline_rows, baseline_key = eval_set(E, mm, eval_labels, a.eval_budget, None, 0)
    print("[BASELINE]", baseline_key, baseline_rows)

    candidates = []
    best_learned = None
    for C in [0.02, 0.05, 0.2, 1.0, 5.0]:
        w = fit28(X, y, sw, C)
        R = CoupledRank(w, mm, meta, reuse, bit_cache)
        rows, key = eval_set(E, mm, eval_labels, a.eval_budget, R, 0)
        rec = {
            "C": C,
            "weights": w.tolist(),
            "protected_key": list(key),
            "rows": rows,
        }
        candidates.append(rec)
        print("[MODEL] C", C, "protected", key)
        if best_learned is None or key < tuple(best_learned["protected_key"]):
            best_learned = rec

    accepted = best_learned is not None and tuple(best_learned["protected_key"]) < baseline_key
    deployed = best_learned if accepted else {
        "C": None,
        "weights": [0.0] * len(FEATURES),
        "protected_key": list(baseline_key),
        "rows": baseline_rows,
    }
    print(
        "[DEPLOY]", "learned" if accepted else "baseline",
        "accepted", accepted, "protected", tuple(deployed["protected_key"])
    )

    # Blind prcom test happens only after all training/model selection is finished.
    pr = P.context(E, mm, a.holdout)
    seeds = [int(x.strip()) for x in a.prcom_seeds.split(",") if x.strip()]
    blind_baseline = []
    blind_learned = []
    learned_rank = None
    if best_learned is not None:
        learned_rank = CoupledRank(best_learned["weights"], mm, meta, reuse, bit_cache)

    print("[BLIND-BEGIN] prcom proof still unused; seeds", seeds)
    for seed in seeds:
        rb = verified_search(E, mm, pr, a.prcom_budget, None, seed)
        rb["seed"] = seed
        blind_baseline.append(rb)
        print("[PRCOM-BASELINE]", seed, rb)
        if learned_rank is not None:
            # Fresh awareness state per seed.
            learned_rank = CoupledRank(best_learned["weights"], mm, meta, reuse, bit_cache)
            rl = verified_search(E, mm, pr, a.prcom_budget, learned_rank, seed)
            rl["seed"] = seed
            blind_learned.append(rl)
            print("[PRCOM-LEARNED]", seed, rl)

    blind_base_key = protected_key(blind_baseline, a.prcom_budget)
    blind_learn_key = protected_key(blind_learned, a.prcom_budget) if blind_learned else None
    print("[PRCOM-KEY] baseline", blind_base_key, "learned", blind_learn_key)

    model = {
        "version": VERSION,
        "codec": CODEC,
        "hard_constraint": "V(P)=1",
        "protected_objective": "minimize compressed certificate bits B(P)",
        "deployment_key": ["failures", "sum_compressed_bits", "sum_expansions", "sum_proof_steps"],
        "feature_count": len(FEATURES),
        "features": FEATURES,
        "groups": GROUPS,
        "accepted": accepted,
        "baseline_key": list(baseline_key),
        "best_learned": best_learned,
        "deployed": deployed,
        "holdout": {
            "label": a.holdout,
            "target_proof_used_in_training": False,
            "downstream_used": False,
            "excluded_preceding": a.holdout_gap,
        },
        "environment_sha256": sha256(a.environment),
    }
    Path(a.out).write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")

    report = {
        "version": VERSION,
        "elapsed_seconds": time.perf_counter() - t0,
        "codec": CODEC,
        "eval_labels": eval_labels,
        "eval_probe": probe_records,
        "training_rows": training_rows,
        "baseline": {"key": list(baseline_key), "rows": baseline_rows},
        "candidates": candidates,
        "accepted": accepted,
        "blind_prcom": {
            "seeds": seeds,
            "baseline": blind_baseline,
            "baseline_key": list(blind_base_key),
            "learned": blind_learned,
            "learned_key": None if blind_learn_key is None else list(blind_learn_key),
            "note": "prcom proof was not used for training or model selection",
        },
    }
    Path(a.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    with open(a.csv, "w", newline="") as f:
        cols = ["theorem", "stored_proof_steps", "stored_cert_bits", "candidate_count", "positive_action"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(training_rows)

    print("[DONE]", a.out, a.report, a.csv)
    if best_learned is not None:
        print("[WEIGHTS] best C", best_learned["C"])
        for name, value in zip(FEATURES, best_learned["weights"]):
            print(f"  {name:38s} {value:+.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
