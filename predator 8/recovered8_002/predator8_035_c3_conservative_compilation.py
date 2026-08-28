#!/usr/bin/env python3
"""Predator 8.035: C3 creativity knobs + conservative compilation for prcom.

Fixed scientific controls
-------------------------
* control-awareness C = 0
* imagination-awareness I = 4
* target theorem/proof unavailable to search
* Metamath verifier unchanged; every accepted certificate must satisfy V(P)=1
* historical set.mm/model guards remain in the inherited 8.016/8.019 pipeline

The experiment exposes the ten Certified Creativity Controls proposed in the
HaloProof design note:
    (cT,cW,cN,cR,cL,c_lemma,cS,cB,cD,cM)
for policy dispersion, candidate width, novelty, route independence, proof
length tolerance, lemma speculation, restart diversity, breadth allocation,
retrieval diversity, and macro compilation.

This first implementation deliberately concentrates engineering changes where
the present experiment has a clean conservative interpretation:
* cT rescales policy logits through T(c)=0.5+1.5 cT;
* cW controls bounded macro candidate width;
* cN rewards labels not repeatedly dominating recent rankings;
* cR is logged but route attraction is disabled (no prcom route is supplied);
* cL controls maximum tolerated primitive depth;
* c_lemma controls how much verified pre-prcom proof experience is mined;
* cS is realized as the workflow's independent-seed restart ensemble and is
  logged per profile; no hidden mid-run target-informed restart is added;
* cB controls opener/breadth allocation in the fixed I=4 profile;
* cD controls the strength of the verified proof-bank retrieval prior;
* cM controls variable macro span and macro admission thresholds.

Macros remain search shortcuts only.  Every primitive inference stays in the
Node trail, and the emitted proof is checked by the unchanged in-process and
external Metamath verifiers.  Thus macro compilation cannot create theoremhood.
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S
import predator8_029_prcom_shortcut_macros as M
import predator8_033_bit_coupled_adaptive as B33

VERSION = "8.035-C3-conservative-compilation"

C3_PROFILES = {
    "focused": {
        "cT": .20, "cW": .25, "cN": .15, "cR": 1.00, "cL": .20,
        "c_lemma": .45, "cS": .20, "cB": .25, "cD": .35, "cM": .65,
    },
    "balanced": {
        "cT": .50, "cW": .50, "cN": .40, "cR": 1.00, "cL": .45,
        "c_lemma": .60, "cS": .35, "cB": .50, "cD": .55, "cM": .78,
    },
    "compile-heavy": {
        "cT": .35, "cW": .55, "cN": .25, "cR": 1.00, "cL": .50,
        "c_lemma": .90, "cS": .25, "cB": .45, "cD": .80, "cM": 1.00,
    },
    "diversity-heavy": {
        "cT": .75, "cW": .72, "cN": .85, "cR": 1.00, "cL": .70,
        "c_lemma": .72, "cS": .75, "cB": .78, "cD": .82, "cM": .88,
    },
}


def mine_pre_target(environment: str, engine: str, target: str, window: int):
    """Mine only verifier-stored proofs strictly before target."""
    E = P.B.load_engine(Path(engine).resolve())
    mm = E.load(str(Path(environment).resolve()), say=lambda *args, **kwargs: None)
    cutoff = mm.order.index(target)
    labs = [z for z in mm.order[max(0, cutoff - window):cutoff]
            if z in mm.proofs and mm.labels.get(z, (None,))[0] == "$p"]
    freq = Counter()
    bigram = Counter()
    used = 0
    for lab in labs:
        try:
            q = list(mm.decompress(lab, mm.proofs[lab]))
            if not q or "?" in q:
                continue
            used += 1
            freq.update(q)
            bigram.update(zip(q, q[1:]))
        except Exception:
            continue
    return freq, bigram, used, cutoff


class C3Policy:
    """Frozen recovered policy plus legal pre-target experience priors."""
    def __init__(self, base, c3, freq, bigram):
        self.base = base
        self.artifact = base.artifact
        self.c3 = c3
        self.freq = freq
        self.bigram = bigram
        self.top_seen = Counter()
        self.prev_top = None
        self.max_log_freq = max([math.log1p(v) for v in freq.values()] or [1.0])
        self.max_log_bigram = max([math.log1p(v) for v in bigram.values()] or [1.0])

    def rank(self, goal, items):
        raw = list(self.base.rank(goal, items))
        if not items:
            return raw
        T = 0.5 + 1.5 * self.c3["cT"]
        out = []
        for score, item in zip(raw, items):
            lab = item[0]
            reuse = math.log1p(self.freq.get(lab, 0)) / self.max_log_freq
            trans = 0.0
            if self.prev_top is not None:
                trans = math.log1p(self.bigram.get((self.prev_top, lab), 0)) / self.max_log_bigram
            novelty = 1.0 / math.sqrt(1.0 + self.top_seen.get(lab, 0))
            bank_bonus = (0.42 * self.c3["cD"] +
                          0.28 * self.c3["c_lemma"] +
                          0.22 * self.c3["cM"]) * reuse
            transition_bonus = 0.24 * self.c3["cD"] * trans
            novelty_bonus = 0.12 * self.c3["cN"] * novelty
            out.append(float(score) / T + bank_bonus + transition_bonus + novelty_bonus)
        k = max(range(len(out)), key=out.__getitem__)
        top = items[k][0]
        self.top_seen[top] += 1
        self.prev_top = top
        return out


def install_policy_proxy(c3, freq, bigram):
    original = P.RuntimePolicy

    class Proxy:
        @staticmethod
        def load(model, E, by_tc):
            return C3Policy(original.load(model, E, by_tc), c3, freq, bigram)

    P.RuntimePolicy = Proxy
    return original


def install_fixed_c0_i4(c3, opener_cap):
    """Hold awareness coordinates at C=0, I=4; let C3 change soft controls."""
    B = P.B
    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    # I=4 base from Predator 8.030.  cB widens alternatives without changing
    # inference legality; cS adds a small exploration/escape allowance.
    exploration = min(0.95, 0.50 + 0.28 * c3["cB"] + 0.10 * c3["cS"])
    cap = max(48, int(opener_cap))

    def fixed_profile(E, mode, creativity=0.55, opener_cap=48):
        return E.Profile("C3-C0-I4", 1.35, 0.75, 0.55, 0.12,
                         exploration, max(cap, opener_cap), 1.0)

    B.make_mode_profile = fixed_profile
    for mode in ("native", "high", "low"):
        B.COORD[mode] = (0, 4)
        B.H_WEIGHT[mode] = 0.0
        B.ML_WEIGHT[mode] = 1.0
    B.COORD["brute"] = (0, 0)

    def restore():
        B.make_mode_profile = original_profile
        B.COORD.clear(); B.COORD.update(old_coord)
        B.H_WEIGHT.clear(); B.H_WEIGHT.update(old_h)
        B.ML_WEIGHT.clear(); B.ML_WEIGHT.update(old_ml)

    return restore


def install_bit_logger():
    original = P.B.verify_emit

    def wrapped(*args, **kwargs):
        verdict, proof, output = original(*args, **kwargs)
        if verdict == "ok":
            bits = B33.cert_bits(list(proof))
            print("[C3-CERT] codec=%s bits=%d proof_steps=%d" %
                  (B33.CODEC, bits, len(proof)))
        return verdict, proof, output

    P.B.verify_emit = wrapped
    return original


def configure_macros(c3):
    # Existing 8.029 spans at most 3 primitive steps.  C3 makes span variable.
    M.MACRO_MAX_EXTRA = 1 + int(round(5 * c3["cM"]))  # total span <= 2..7
    M.MACRO_TOPK_PER_KIND = min(64, 8 + int(56 * c3["cW"] ** 2))
    M.MACRO_DECISION_DISCOUNT = max(0.10, 0.44 - 0.28 * c3["cM"])
    M.MACRO_MIN_H_GAIN = max(0.02, 0.16 - 0.11 * c3["cM"])
    M.MACRO_MIN_GUIDE = max(0.05, 0.28 - 0.18 * c3["cM"])


def main():
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("environment")
    gate.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    gate.add_argument("--model", required=True)
    gate.add_argument("--label", default="prcom")
    gate.add_argument("--seed", type=int, default=2301)
    gate.add_argument("--c3-profile", choices=sorted(C3_PROFILES), required=True)
    ns, rest = gate.parse_known_args()

    c3 = dict(C3_PROFILES[ns.c3_profile])
    mining_window = 400 + int(round(2200 * c3["c_lemma"]))
    freq, bigram, mined, cutoff = mine_pre_target(
        ns.environment, ns.engine, ns.label, mining_window)
    print("[C3] version=%s profile=%s C=0 I=4 vector=%s" %
          (VERSION, ns.c3_profile, c3))
    print("[C3-GUARD] target=%s target_proof_used=False downstream=False route_attraction=False" % ns.label)
    print("[C3-MINE] strict_pre_target=True cutoff=%d window=%d verified_proofs=%d labels=%d bigrams=%d" %
          (cutoff, mining_window, mined, len(freq), len(bigram)))

    configure_macros(c3)
    macro_span = 1 + M.MACRO_MAX_EXTRA
    opener_cap = min(128, 8 + int(120 * c3["cW"] ** 2))
    max_depth = 12 + int(round(4 * c3["cL"]))
    print("[C3-DERIVED] macro_span<=%d macro_topk=%d opener_cap=%d max_depth=%d discount=%.3f min_H_gain=%.3f min_guide=%.3f" %
          (macro_span, M.MACRO_TOPK_PER_KIND, opener_cap, max_depth,
           M.MACRO_DECISION_DISCOUNT, M.MACRO_MIN_H_GAIN, M.MACRO_MIN_GUIDE))
    print("[C3-ACCOUNTING] outer expansions, macro internal primitive work, wall time, proof steps, and certificate bits are distinct metrics")

    original_policy = install_policy_proxy(c3, freq, bigram)
    original_verify_emit = install_bit_logger()
    M.install_shortcut_controller()
    restore_profile = install_fixed_c0_i4(c3, opener_cap)
    S.VERSION = VERSION + "/" + ns.c3_profile

    # Strip C3-only argument and supply derived soft controls to inherited main.
    sys.argv = [sys.argv[0], ns.environment,
                "--engine", ns.engine,
                "--model", ns.model,
                "--label", ns.label,
                "--seed", str(ns.seed),
                "--creativity", str(c3["cT"]),
                "--opener-cap", str(opener_cap),
                "--max-depth", str(max_depth)] + rest
    try:
        return S.main()
    finally:
        restore_profile()
        P.RuntimePolicy = original_policy
        P.B.verify_emit = original_verify_emit


if __name__ == "__main__":
    raise SystemExit(main())
