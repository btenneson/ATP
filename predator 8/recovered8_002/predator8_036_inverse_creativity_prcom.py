#!/usr/bin/env python3
"""Predator 8.036: inverse-creativity group test on the fast prcom regime.

Scientific aim
--------------
Test whether algebraically distinguished creativity moves carry useful search
information.  Each soft creativity coordinate lives in the group

    G = ((0,1), \oplus)
    a \oplus b = sigmoid(logit(a) + logit(b)),

which is isomorphic to (R,+).  Its identity is e=0.5 and its inverse is

    a^{-1} = 1-a.

The theorem prover remains fixed at control-awareness C=0 and imagination I=5,
with seed 2302 in the workflow.  Verification, target guards, and frozen model /
set.mm hashes are inherited unchanged.  The target proof is unavailable to the
search.

This is a static proof-of-concept before a dynamic stagnation -> inverse
controller.  Treatments are group identity e, a nontrivial state x, full
coordinatewise x^{-1}, and one-coordinate inversions of cM and cN.
"""
from __future__ import annotations

import argparse
import math
import sys

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S
import predator8_029_prcom_shortcut_macros as M
import predator8_035_c3_conservative_compilation as C3

VERSION = "8.036-inverse-creativity-prcom"

# Interior coordinates only: endpoints 0 and 1 are not elements of the
# logit-addition group.  cR is neutral because route attraction is disabled.
X = {
    "cT": .35, "cW": .60, "cN": .25, "cR": .50, "cL": .45,
    "c_lemma": .75, "cS": .30, "cB": .40, "cD": .70, "cM": .70,
}


def inv_scalar(c: float) -> float:
    if not (0.0 < c < 1.0):
        raise ValueError("group coordinate must lie in (0,1)")
    return 1.0 - c


def inverse_vector(x):
    return {k: inv_scalar(v) for k, v in x.items()}


def one_inverse(x, key):
    y = dict(x)
    y[key] = inv_scalar(y[key])
    return y


E = {k: .50 for k in X}
X_INV = inverse_vector(X)
PROFILES = {
    "group-e": E,
    "x": X,
    "x-inverse": X_INV,
    "x-inv-cM": one_inverse(X, "cM"),
    "x-inv-cN": one_inverse(X, "cN"),
}


def group_op(a: float, b: float) -> float:
    """Logit-addition group operation, used for audit checks only."""
    la = math.log(a / (1.0 - a))
    lb = math.log(b / (1.0 - b))
    z = la + lb
    return 1.0 / (1.0 + math.exp(-z))


def audit_group():
    for k, v in X.items():
        w = inv_scalar(v)
        if abs(group_op(v, w) - .5) > 1e-12:
            raise RuntimeError("inverse audit failed for %s" % k)


def install_fixed_c0_i5(c3, opener_cap):
    """Hold the known fast awareness regime C=0, I=5 fixed."""
    B = P.B
    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    # Start from the exact 8.029 I=5 shape.  Only soft C3 controls perturb
    # breadth/exploration; inference legality and verifier semantics do not move.
    cap = max(96, int(opener_cap))
    exploration = min(1.0, max(.55, .70 + .20 * c3["cB"] + .10 * c3["cS"]))

    def fixed_profile(Eengine, mode, creativity=.55, opener_cap=48):
        return Eengine.Profile("INV-C0-I5", 1.60, .95, .75, .10,
                               exploration, max(cap, opener_cap), 1.0)

    B.make_mode_profile = fixed_profile
    for mode in ("native", "high", "low"):
        B.COORD[mode] = (0, 5)
        B.H_WEIGHT[mode] = 0.0
        B.ML_WEIGHT[mode] = 1.0
    B.COORD["brute"] = (0, 0)

    def restore():
        B.make_mode_profile = original_profile
        B.COORD.clear(); B.COORD.update(old_coord)
        B.H_WEIGHT.clear(); B.H_WEIGHT.update(old_h)
        B.ML_WEIGHT.clear(); B.ML_WEIGHT.update(old_ml)

    return restore


def main():
    audit_group()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--seed", type=int, default=2302)
    ap.add_argument("--treatment", choices=sorted(PROFILES), required=True)
    ns, rest = ap.parse_known_args()

    c3 = dict(PROFILES[ns.treatment])
    mining_window = 400 + int(round(2200 * c3["c_lemma"]))
    freq, bigram, mined, cutoff = C3.mine_pre_target(
        ns.environment, ns.engine, ns.label, mining_window)

    print("[INV] version=%s treatment=%s C=0 I=5 seed=%d" %
          (VERSION, ns.treatment, ns.seed))
    print("[INV-GROUP] G=((0,1),logit-addition) identity=0.5 inverse(c)=1-c")
    print("[INV-X] %s" % X)
    print("[INV-X^-1] %s" % X_INV)
    print("[INV-VECTOR] %s" % c3)
    print("[INV-GUARD] target=%s target_proof_used=False downstream=False route_attraction=False" % ns.label)
    print("[INV-MINE] strict_pre_target=True cutoff=%d window=%d verified_proofs=%d labels=%d bigrams=%d" %
          (cutoff, mining_window, mined, len(freq), len(bigram)))

    C3.configure_macros(c3)
    macro_span = 1 + M.MACRO_MAX_EXTRA
    opener_cap = min(128, 8 + int(120 * c3["cW"] ** 2))
    max_depth = 12 + int(round(4 * c3["cL"]))
    print("[INV-DERIVED] macro_span<=%d macro_topk=%d opener_cap=%d max_depth=%d discount=%.3f min_H_gain=%.3f min_guide=%.3f" %
          (macro_span, M.MACRO_TOPK_PER_KIND, opener_cap, max_depth,
           M.MACRO_DECISION_DISCOUNT, M.MACRO_MIN_H_GAIN, M.MACRO_MIN_GUIDE))
    print("[INV-ACCOUNTING] outer expansions, macro internal work, wall time, proof steps, certificate bits kept distinct")

    original_policy = C3.install_policy_proxy(c3, freq, bigram)
    original_verify_emit = C3.install_bit_logger()
    M.install_shortcut_controller()
    restore_profile = install_fixed_c0_i5(c3, opener_cap)
    S.VERSION = VERSION + "/" + ns.treatment

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
