#!/usr/bin/env python3
"""Predator 8.020: control-awareness ablation over frozen 8.019 search.

This experiment changes only the control-awareness coordinate while preserving
8.019's mode-specific search/imagination profiles.  Operationally, control
awareness C is represented by the strength of the settlement-distance control
term used in frontier ordering: C=0 -> 0.00, C=1 -> 0.10, ..., C=5 -> 0.50.

Coordinates for this ablation:
  native: (C,I) = (5,3)
  surge:  (C,I) = (5,4)
  torpor: (C,I) = (1,2)
  brute:  (C,I) = (0,0)

The second coordinate (imagination) and all make_mode_profile behavior are left
unchanged from Predator 8.019/8.015.  This is therefore a one-axis ablation of
control influence, not a new imagination policy.  Certificate authority and
target-proof guards are unchanged.
"""
from __future__ import annotations

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S

VERSION = "8.020-C5-control-ablation"

COORD_C5 = {
    "native": (5, 3),
    "high": (5, 4),
    "low": (1, 2),
    "brute": (0, 0),
}

# Linear operationalization of control-awareness strength only.
# Imagination/search profiles remain exactly those selected by the underlying
# 8.019 controller via make_mode_profile().
H_WEIGHT_C5 = {
    "native": 0.50,
    "high": 0.50,
    "low": 0.10,
}


def adaptive_guided_selective(*args, **kwargs):
    """Run frozen 8.019 logic with only the C-awareness axis remapped."""
    B = P.B
    say = kwargs.get("say", print)
    old_coord = dict(B.COORD)
    old_h_weight = dict(B.H_WEIGHT)
    try:
        B.COORD.update(COORD_C5)
        B.H_WEIGHT.update(H_WEIGHT_C5)
        say("    [C-AWARENESS ABLATION] native=(5,3) surge=(5,4) "
            "torpor=(1,2) brute=(0,0)")
        say("    [C-AWARENESS OPERATION] H control weights: "
            "native=0.50 surge=0.50 torpor=0.10 brute=0.00; "
            "imagination profiles unchanged")
        return S.adaptive_guided_selective(*args, **kwargs)
    finally:
        B.COORD.clear()
        B.COORD.update(old_coord)
        B.H_WEIGHT.clear()
        B.H_WEIGHT.update(old_h_weight)
