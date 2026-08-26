#!/usr/bin/env python3
"""Fixed-(C,I) awareness-grid wrapper for Predator 8.019 on prcom.

Purpose: compare the 16 ordered pairs C,I in {0,2,4,5}^2 while holding the
8.019 theorem, model, seed, budget, authority gate, exactifier, bailout logic,
and brute fallback fixed.

Operationalization used for this grid:
  * Control awareness C changes only the settlement-distance frontier term:
      C=0 -> H_WEIGHT 0.00, C=2 -> 0.20, C=4 -> 0.40, C=5 -> 0.50.
  * Imagination awareness I changes only the guided-search profile:
      I=0 -> minimal exploration profile;
      I=2 -> the existing 8.015 torpor profile;
      I=4 -> the existing 8.015 surge profile;
      I=5 -> a bounded stronger-than-surge profile for this ablation.

For a given run, the same ordered pair is held across native/high/low guided
controller modes. Brute remains (0,0) and deterministic. This prevents the
controller's mode transitions from silently changing the tested awareness pair.
The Metamath rules, candidate-zero certificate gate, and target-proof guard are
untouched.
"""
from __future__ import annotations

import argparse
import sys

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S

ALLOWED = {0, 2, 4, 5}


def install_fixed_pair(c: int, i: int):
    B = P.B
    if c not in ALLOWED or i not in ALLOWED:
        raise ValueError("C and I must each be one of 0,2,4,5")

    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    def fixed_profile(E, mode, creativity=0.55, opener_cap=48):
        # Use already-existing profiles wherever possible so the grid extends
        # rather than replaces the 8.019 search semantics.
        if i == 2:
            return original_profile(E, "low", creativity, opener_cap)
        if i == 4:
            return original_profile(E, "high", creativity, opener_cap)
        if i == 0:
            return E.Profile("imagination-(%d,0)" % c,
                             0.0, 0.0, 0.0, 0.25, 0.0,
                             max(32, opener_cap), 1.0)
        # I=5: bounded one-step extension of the I=4 surge profile.
        return E.Profile("imagination-(%d,5)" % c,
                         1.60, 0.95, 0.75, 0.10, 0.85,
                         max(96, opener_cap), 1.0)

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

    restore = install_fixed_pair(ns.control_awareness, ns.imagination_awareness)
    print("[AWARENESS-GRID] fixed pair (C,I)=(%d,%d)" %
          (ns.control_awareness, ns.imagination_awareness))
    print("[AWARENESS-GRID] guided H_WEIGHT=%.2f; brute=(0,0); H=0 still requires certificate" %
          (0.10 * ns.control_awareness))
    try:
        sys.argv = [sys.argv[0]] + rest
        return S.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
