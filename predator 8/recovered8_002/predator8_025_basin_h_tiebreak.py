#!/usr/bin/env python3
"""Predator 8.025: basin-local H secondary tie-break for the prcom 16-cell grid.

This experiment starts from Predator 8.024, retaining both of its controlled
changes:
  * no H influence on depth-0 -> depth-1 root-basin selection;
  * immediate verifier-gated checking of a complete successor at generation.

8.024 showed that its bounded additive local dH reward did not change the
positive-I schedule at any C value: every row was 30000/57/33/39.  The 8.023
trace explains why a different use of H is worth testing: many internal siblings
have exactly equal primary frontier priority even though their H_hat values
are different.

8.025 therefore adds H_hat only as a *secondary numerical tie-break* after a
root basin is chosen.  The perturbation is intentionally tiny compared with
ordinary primary edge/state-cost gaps, so it cannot act as global goal-seeking.
For a child generated from depth >= 1, the pushed priority is

    primary_priority + eps * H_WEIGHT * H_hat(child),

where eps=1e-5.  For C=0 the perturbation is exactly zero, preserving the 8.024
control row.  For C>0, lower-H children win exact or extremely close primary
priority ties.  The original basin-local derivative term remains in place.

No target proof labels are used.  Proof admissibility, historical set.mm,
frozen model, seed, budgets, candidate gate, certificate reconstruction, and
independent external Metamath verification are unchanged.
"""
from __future__ import annotations

import inspect

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S
import predator8_024_basin_local_derivative as D

TIE_EPS = 1.0e-5

OLD_PUSH = '''            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))\n'''
NEW_PUSH = '''            # Secondary local H ordering only.  The perturbation is far\n            # smaller than ordinary primary edge/state-cost gaps, so it breaks\n            # internal ties without turning H into a global root objective.\n            h_tie = 0.0\n            if node.depth >= 1 and B.H_WEIGHT[mode] > 0.0:\n                h_tie = (TIE_EPS * B.H_WEIGHT[mode] *\n                         B.h_hat(E, successor_goals, s2))\n            heapq.heappush(frontier,\n                           (priority + edge + state_cost + h_tie, tie, child))\n'''


def install_h_tiebreak():
    src = inspect.getsource(S.adaptive_guided_selective)
    if src.count(OLD_PUSH) != 1:
        raise RuntimeError("8.024 source no longer matches H-tiebreak patch")
    src = src.replace(OLD_PUSH, NEW_PUSH, 1)
    ns = {"TIE_EPS": TIE_EPS}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__ | {"TIE_EPS": TIE_EPS}, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[H-TIE] installed basin-local secondary H ordering; eps=%.1e" % TIE_EPS)
    print("[H-TIE] C=0 remains exact 8.024 control; root H guidance remains OFF")


def main():
    D.install_basin_local_derivative()
    install_h_tiebreak()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
