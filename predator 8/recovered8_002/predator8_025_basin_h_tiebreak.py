#!/usr/bin/env python3
"""Predator 8.025: basin-local H secondary tie-break for the prcom 16-cell grid.

This controlled experiment applies three edits directly to the untouched 8.019
search function:
  1. H does not influence depth-0 -> depth-1 root-basin selection.
  2. Complete successors are submitted to the unchanged certificate gate
     immediately at generation time (the successful 8.024 optimization).
  3. After a root basin is selected, H_hat is added only as a tiny secondary
     numerical tie-break among otherwise equal or extremely close primary
     frontier costs.

For a nonterminal child generated from node.depth >= 1,

    pushed_priority = primary_priority
                      + eps * H_WEIGHT * H_hat(child),

with eps=1e-5.  The perturbation is orders of magnitude below ordinary primary
edge/state-cost gaps, so it cannot function as global H goal-seeking.  C=0 has
H_WEIGHT=0 and remains the exact 8.024 control row.  C>0 prefers lower-H states
only when the primary search policy is effectively tied.

No target proof labels are used. Proof admissibility, historical set.mm, frozen
model, seed, budgets, exactifier, bailout logic, candidate gate, certificate
reconstruction, and independent external Metamath verification are unchanged.
"""
from __future__ import annotations

import inspect

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S

TIE_EPS = 1.0e-5

OLD_EDGE = '''            if B.H_WEIGHT[mode] > 0.0:\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''
NEW_EDGE = '''            if B.H_WEIGHT[mode] > 0.0 and node.depth >= 1:\n                # Local discrete derivative only after root-basin selection.\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''

OLD_CHILD = '''            child = E.Node(successor_goals, s2,\n                           node.trail + ((slot, hix, step),), node.depth + 1)\n            if Q._blocked(child, blocked_prefixes):\n                continue\n            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))\n'''
NEW_CHILD = '''            child = E.Node(successor_goals, s2,\n                           node.trail + ((slot, hix, step),), node.depth + 1)\n\n            # A closed successor is already a complete candidate. Verify now.\n            if not successor_goals:\n                candidate = B.reconstruct(child)\n                if accept_zero(candidate, "generated-zero",\n                               exp + probe_used_total, basin):\n                    best_h = 0.0\n                    return (candidate, exp + probe_used_total, best_h,\n                            transitions, "generated-zero-settled")\n                continue\n\n            if Q._blocked(child, blocked_prefixes):\n                continue\n\n            # Secondary H tie-break only after basin selection.  This epsilon\n            # cannot override ordinary primary cost differences, but it breaks\n            # the exact sibling ties observed in the 8.023 prcom trace.\n            h_tie = 0.0\n            if node.depth >= 1 and B.H_WEIGHT[mode] > 0.0:\n                h_tie = (TIE_EPS * B.H_WEIGHT[mode] *\n                         B.h_hat(E, successor_goals, s2))\n            heapq.heappush(frontier,\n                           (priority + edge + state_cost + h_tie, tie, child))\n'''


def install_h_tiebreak():
    src = inspect.getsource(S.adaptive_guided_selective)
    for old, new, label in (
        (OLD_EDGE, NEW_EDGE, "basin-local derivative"),
        (OLD_CHILD, NEW_CHILD, "eager zero + H tie-break"),
    ):
        if src.count(old) != 1:
            raise RuntimeError("8.019 source no longer matches controlled %s patch" % label)
        src = src.replace(old, new, 1)
    ns = {}
    glb = dict(S.__dict__)
    glb["TIE_EPS"] = TIE_EPS
    exec(compile(src, __file__ + ":patched", "exec"), glb, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[H-TIE] direct controlled patch installed; eps=%.1e" % TIE_EPS)
    print("[H-TIE] root H guidance OFF; eager verifier gate ON; C0 exact control")


def main():
    install_h_tiebreak()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
