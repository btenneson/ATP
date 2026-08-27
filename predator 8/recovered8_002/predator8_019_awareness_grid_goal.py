#!/usr/bin/env python3
"""Predator 8.019 16-cell awareness grid with direct H=0 goal seeking.

Controlled intervention relative to predator8_019_awareness_grid.py:

* Same theorem (prcom), historical set.mm, trained model, seed, global budget,
  brute reserve, max depth/open limits, creativity, opener cap, probe limits,
  frontier limit, fixed awareness coordinates, exactifier, bailout logic,
  admissible proof moves, certificate gate, certificate emission, and external
  Metamath verification.
* Same 16 awareness cells: C,I in {0,2,4,5} x {0,2,4,5}.
* Only the H frontier preference is changed.

Original 8.019 H preference (local descent):
    delta = H_hat(current) - H_hat(next)
    edge -= H_WEIGHT * tanh(delta)

This experiment (direct goal seeking):
    goal_error = abs(H_hat(next) - 0)
    edge += H_WEIGHT * tanh(goal_error)

No derivative, finite difference, local-minimum condition, or stationarity
condition is introduced as a new objective.  Existing 8.019 H-improvement
telemetry/controller bookkeeping is otherwise left untouched so that the
experiment changes only the frontier H preference.

Most importantly, an apparent H=0 is NEVER sufficient for settlement.  The
existing 8.019 candidate gate is unchanged: a zero candidate settles only when
its reconstructed certificate is accepted.  Rejected H=0 events remain
FALSE-ZERO events and search continues under the same resource budget.
"""
from __future__ import annotations

import inspect
import sys

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD = '''            if B.H_WEIGHT[mode] > 0.0:\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''

NEW = '''            if B.H_WEIGHT[mode] > 0.0:\n                # Direct root seeking: score absolute error from H=0.\n                # This deliberately does not use current-next H differences.\n                goal_error = abs(B.h_hat(E, successor_goals, s2) - 0.0)\n                edge += B.H_WEIGHT[mode] * math.tanh(goal_error)\n'''


def install_direct_goal_policy():
    src = inspect.getsource(S.adaptive_guided_selective)
    if OLD not in src:
        raise RuntimeError("8.019 H-priority source no longer matches controlled intervention")
    if src.count(OLD) != 1:
        raise RuntimeError("expected exactly one 8.019 local-H priority term")
    patched = src.replace(OLD, NEW, 1)
    ns = {}
    exec(compile(patched, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[H-GOAL] installed direct target policy: goal_error=|H_hat(next)-0|")
    print("[H-GOAL] no H derivative/minimum/stationarity objective; verifier zero-gate unchanged")


def main():
    install_direct_goal_policy()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
