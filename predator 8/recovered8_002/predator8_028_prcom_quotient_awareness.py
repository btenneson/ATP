#!/usr/bin/env python3
"""Predator 8.028: quotient-aware prcom experiment.

This is an experimental extension of Predator 8.019 for the
Redundancy-Quotient Geodesic program.  It leaves Metamath legality,
reconstruction, candidate-zero verification, exactification, bailout, and
brute fallback unchanged.  The only search-space change is a conservative
transposition heuristic built from the *same applied-goal signature already
used by 8.019*, but with depth removed: if the same structural unresolved-goal
signature has already been expanded at a shallower or equal depth, the deeper
representative is suppressed.

This is a candidate quotient, not a proved exact quotient.  It may affect
search completeness within a finite budget, but cannot make a false proof pass
the unchanged certificate verifier.

Awareness grid for this experiment:
  C in {0,2,4,5}, preserving the earlier H_WEIGHT rule 0.10*C.
  I=3: recovered native 8.002 exploration profile (the natural intermediate
       profile already identified by the controller as coordinate (*,3)).
  I=5: the existing bounded stronger-than-surge profile from 8.019.
  I=6: a bounded one-step extension of I=5 for this experiment.

No guided condition uses I=0.  Brute fallback remains deterministic (0,0) as a
separate baseline mechanism and is not an awareness-grid treatment.
"""
from __future__ import annotations

import argparse
import inspect
import sys

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S

ALLOWED_C = {0, 2, 4, 5}
ALLOWED_I = {3, 5, 6}


def install_quotient_controller():
    """Patch only 8.019's guided transposition test, leaving all else intact."""
    src = inspect.getsource(S.adaptive_guided_selective)

    old_init = """    false_zeros = 0\n    seen = set()\n    t0 = time.perf_counter()\n"""
    new_init = """    false_zeros = 0\n    seen = set()\n    quotient_best_depth = {}\n    quotient_prunes = 0\n    quotient_improvements = 0\n    t0 = time.perf_counter()\n"""

    old_key = """        key = (node.depth, \" \".join(gt.tokens()),\n               tuple(sorted(\" \".join(E.apply_sub(g, node.sub).tokens())\n                            for g, _, _ in rest)))\n        if key in seen:\n            continue\n        seen.add(key)\n"""
    new_key = """        # Candidate structural quotient: use exactly the unresolved-goal\n        # representation that 8.019 already treats as equivalent *within a depth*,\n        # but allow a shallower representative to dominate a deeper one.\n        structural_key = (\" \".join(gt.tokens()),\n                          tuple(sorted(\" \".join(E.apply_sub(g, node.sub).tokens())\n                                       for g, _, _ in rest)))\n        previous_depth = quotient_best_depth.get(structural_key)\n        if previous_depth is not None and node.depth >= previous_depth:\n            quotient_prunes += 1\n            if quotient_prunes <= 5 or quotient_prunes % 100 == 0:\n                say(\"      [QUOTIENT-PRUNE] count=%d depth=%d best_depth=%d classes=%d\"\n                    % (quotient_prunes, node.depth, previous_depth,\n                       len(quotient_best_depth)))\n            continue\n        if previous_depth is not None:\n            quotient_improvements += 1\n            say(\"      [QUOTIENT-IMPROVE] count=%d depth %d->%d classes=%d\"\n                % (quotient_improvements, previous_depth, node.depth,\n                   len(quotient_best_depth)))\n        quotient_best_depth[structural_key] = node.depth\n"""

    if old_init not in src:
        raise RuntimeError("8.019 source changed: quotient init patch anchor missing")
    if old_key not in src:
        raise RuntimeError("8.019 source changed: quotient key patch anchor missing")
    src = src.replace(old_init, new_init, 1).replace(old_key, new_key, 1)

    ns = {}
    exec(compile(src, "<8.028 quotient-patched adaptive_guided_selective>", "exec"),
         S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]


def install_fixed_pair(c: int, i: int):
    B = P.B
    if c not in ALLOWED_C or i not in ALLOWED_I:
        raise ValueError("C must be one of 0,2,4,5 and I one of 3,5,6")

    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    def fixed_profile(E, mode, creativity=0.55, opener_cap=48):
        if i == 3:
            # The recovered/native profile is already the controller's natural
            # intermediate exploration coordinate, historically labelled (*,3).
            return original_profile(E, "native", creativity, opener_cap)
        if i == 5:
            # Preserve the exact I=5 treatment introduced in the 8.019 grid.
            return E.Profile("imagination-(%d,5)" % c,
                             1.60, 0.95, 0.75, 0.10, 0.85,
                             max(96, opener_cap), 1.0)
        # I=6: bounded one-step extension of I=5.  The constants are declared
        # here so this treatment is auditable rather than inferred at runtime.
        return E.Profile("imagination-(%d,6)" % c,
                         1.85, 1.10, 0.90, 0.08, 1.00,
                         max(128, opener_cap), 1.0)

    B.make_mode_profile = fixed_profile
    for mode in ("native", "high", "low"):
        B.COORD[mode] = (c, i)
        B.H_WEIGHT[mode] = 0.10 * c
        B.ML_WEIGHT[mode] = 1.0
    B.COORD["brute"] = (0, 0)

    def restore():
        B.make_mode_profile = original_profile
        B.COORD.clear(); B.COORD.update(old_coord)
        B.H_WEIGHT.clear(); B.H_WEIGHT.update(old_h)
        B.ML_WEIGHT.clear(); B.ML_WEIGHT.update(old_ml)

    return restore


def main():
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("--control-awareness", type=int, required=True)
    gate.add_argument("--imagination-awareness", type=int, required=True)
    ns, rest = gate.parse_known_args()

    install_quotient_controller()
    restore = install_fixed_pair(ns.control_awareness, ns.imagination_awareness)
    print("[QUOTIENT] 8.028 structural-depth dominance ENABLED")
    print("[QUOTIENT] signature=current applied goal + sorted remaining applied goals")
    print("[AWARENESS-GRID] fixed guided pair (C,I)=(%d,%d)" %
          (ns.control_awareness, ns.imagination_awareness))
    print("[AWARENESS-GRID] guided H_WEIGHT=%.2f; brute fallback=(0,0); verifier unchanged" %
          (0.10 * ns.control_awareness))
    try:
        sys.argv = [sys.argv[0]] + rest
        return S.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
