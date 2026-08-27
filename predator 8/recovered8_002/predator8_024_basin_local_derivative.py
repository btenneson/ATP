#!/usr/bin/env python3
"""Predator 8.024: basin-local H derivative + eager verified zero for prcom grid.

This controlled experiment follows directly from the C0/I4 basin trace:

* The root transition is ranked exactly as in the recovered target-excluded
  policy.  H is NOT allowed to influence depth-0 -> depth-1 basin selection,
  because the verified prcom route enters 3eqtr4ri by initially increasing H.
* Once a root basin has been selected (node.depth >= 1), retain the original
  discrete directional derivative reward H(x)-H(y), with the same C-dependent
  H weights used in the 16-cell awareness grid.
* If expanding a node generates a closed successor, run the unchanged
  certificate gate immediately.  A verified proof already exists at generation
  time, so delaying verification until that terminal child is popped from the
  heap only adds scheduler overhead.  Rejected generated zeros are logged and
  search continues; verification authority is not weakened.

Everything else stays fixed: theorem prcom, historical set.mm, frozen model,
seed, budgets, proof rules, target-proof guard, exactifier, bailout logic,
awareness profiles, certificate emitter, and independent external Metamath CV.
"""
from __future__ import annotations

import inspect

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD_EDGE = '''            if B.H_WEIGHT[mode] > 0.0:\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''
NEW_EDGE = '''            if B.H_WEIGHT[mode] > 0.0 and node.depth >= 1:\n                # H is a local derivative inside a chosen root basin, not a\n                # global root-basin selector.  The prcom trace shows the\n                # verified root move can initially increase H.\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''

OLD_CHILD = '''            child = E.Node(successor_goals, s2,\n                           node.trail + ((slot, hix, step),), node.depth + 1)\n            if Q._blocked(child, blocked_prefixes):\n                continue\n            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))\n'''
NEW_CHILD = '''            child = E.Node(successor_goals, s2,\n                           node.trail + ((slot, hix, step),), node.depth + 1)\n\n            # A terminal successor is already a complete candidate proof.\n            # Verify it now rather than spending a future frontier expansion\n            # merely to rediscover that its goal list is empty.\n            if not successor_goals:\n                candidate = B.reconstruct(child)\n                if accept_zero(candidate, "generated-zero",\n                               exp + probe_used_total, basin):\n                    best_h = 0.0\n                    return (candidate, exp + probe_used_total, best_h,\n                            transitions, "generated-zero-settled")\n                continue\n\n            if Q._blocked(child, blocked_prefixes):\n                continue\n            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))\n'''


def install_basin_local_derivative():
    src = inspect.getsource(S.adaptive_guided_selective)
    for old, new in ((OLD_EDGE, NEW_EDGE), (OLD_CHILD, NEW_CHILD)):
        if src.count(old) != 1:
            raise RuntimeError("8.019 source no longer matches basin-local patch")
        src = src.replace(old, new, 1)
    ns = {}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[BASIN-DH] root H guidance OFF; local H derivative ON for depth>=1")
    print("[BASIN-DH] closed successors use the unchanged verifier gate immediately")


def main():
    install_basin_local_derivative()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
