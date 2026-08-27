#!/usr/bin/env python3
"""Predator 8.019 16-cell awareness grid with recursive bisection toward H=0.

Controlled intervention relative to predator8_019_awareness_grid.py:

* Same theorem (prcom), historical set.mm, trained model, seed, global budget,
  brute reserve, max depth/open limits, creativity, opener cap, probe limits,
  frontier limit, fixed awareness coordinates, exactifier, bailout logic,
  admissible proof moves, candidate gate, certificate emission, and external
  Metamath verification.
* Same 16 awareness cells: C,I in {0,2,4,5} x {0,2,4,5}.
* Only the H-directed search behavior is changed.

The original controller rewards local H descent.  This experiment instead
recursively bisects the nonnegative target interval toward the boundary root 0.
If the current upper target bound is U, the active midpoint is M=U/2.  Search
states above M receive an H-guidance penalty; states at or below M enter the
left half, causing U<-M and a new midpoint M<-U/2.  Thus the target sequence is

    H0/2, H0/4, H0/8, ... -> 0.

This is a goal-seeking/domain-bisection experiment.  No derivative, finite
-difference objective, stationarity requirement, or local-minimum acceptance
criterion is added.  Existing H telemetry may still be printed by 8.019, but
it is not the H frontier objective in this variant.

CRITICAL ZERO RULE: an observed or estimated H=0 is only a candidate event.
The unchanged 8.019 candidate gate must accept the reconstructed certificate,
and the emitted certificate is independently checked by Metamath.  A rejected
zero is logged FALSE-ZERO and search continues under the same budget.
"""
from __future__ import annotations

import inspect

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n    last_global_improve = 0\n'''
NEW_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n    # Recursive bisection of the nonnegative H target interval [0,U].\n    bisect_upper = best_h\n    bisect_mid = 0.5 * bisect_upper\n    say("    [H-BISECT] interval=[0,%.6f] midpoint=%.6f" %\n        (bisect_upper, bisect_mid))\n    last_global_improve = 0\n'''

OLD_NH = '''        nh = B.h_hat(E, node.goals, node.sub)\n        improved = nh < best_h - H_IMPROVEMENT_EPS\n'''
NEW_NH = '''        nh = B.h_hat(E, node.goals, node.sub)\n\n        # Goal-seeking bisection event: enter the left half [0,M], then bisect\n        # that half again.  A jump to H=0 may cross several dyadic targets at\n        # once; cap the loop at machine-relevant resolution.\n        bisect_crossed = False\n        while bisect_mid > 1e-12 and nh <= bisect_mid:\n            old_upper = bisect_upper\n            old_mid = bisect_mid\n            bisect_upper = bisect_mid\n            bisect_mid = 0.5 * bisect_upper\n            bisect_crossed = True\n            say("      [H-BISECT] H_hat=%.6f entered [0,%.6f]; "\n                "new interval=[0,%.6f] midpoint=%.6f"\n                % (nh, old_mid, bisect_upper, bisect_mid))\n            transitions.append((total_used, mode, "H-BISECT",\n                                "[0,%.9f] -> [0,%.9f]" %\n                                (old_upper, bisect_upper)))\n\n        # Keep legacy best-H bookkeeping only as telemetry/controller accounting;\n        # it is not the frontier objective.\n        improved = nh < best_h - H_IMPROVEMENT_EPS\n'''

OLD_EDGE = '''            if B.H_WEIGHT[mode] > 0.0:\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''
NEW_EDGE = '''            if B.H_WEIGHT[mode] > 0.0:\n                # Recursive bisection target, not local current-next descent.\n                successor_h = B.h_hat(E, successor_goals, s2)\n                bisect_error = max(0.0, successor_h - bisect_mid)\n                edge += B.H_WEIGHT[mode] * math.tanh(bisect_error)\n'''


def install_bisection_policy():
    src = inspect.getsource(S.adaptive_guided_selective)
    replacements = ((OLD_INIT, NEW_INIT), (OLD_NH, NEW_NH), (OLD_EDGE, NEW_EDGE))
    for old, new in replacements:
        if src.count(old) != 1:
            raise RuntimeError("8.019 source no longer matches controlled bisection patch")
        src = src.replace(old, new, 1)
    ns = {}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[H-BISECT] installed recursive interval bisection toward H=0")
    print("[H-BISECT] no derivative/minimum/stationarity objective; verifier zero-gate unchanged")


def main():
    install_bisection_policy()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
