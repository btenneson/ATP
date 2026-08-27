#!/usr/bin/env python3
"""Predator 8.021 diagnostic: inspect one-ply policy value at the prcom root.

This does not change admissibility, verification, the target-proof guard, or the
search score.  It instruments the 8.019 root expansion and asks, for each legal
root successor, how confidently the already-frozen target-excluded policy can
rank a closer for the successor's open subgoals.

The diagnostic is intended to test a candidate state-value coordinate before it
is allowed to affect the 16-cell search grid.
"""
from __future__ import annotations

import inspect
import math

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n    last_global_improve = 0\n'''
NEW_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n\n    def one_ply_value(goals, sub):\n        # Mean best closer confidence of the successor's current open goals.\n        # No child is expanded: this is a policy/index evaluation only.\n        if not goals:\n            return 1.0, 1.0, 0\n        vals = []\n        missing = 0\n        for gg, _, _ in goals:\n            g2 = E.apply_sub(gg, sub)\n            closers2, _ = index.candidates(g2)\n            if not closers2:\n                vals.append(-1.0)\n                missing += 1\n                continue\n            raw = policy.rank(g2, closers2)\n            if not raw:\n                vals.append(-1.0)\n                missing += 1\n                continue\n            vals.append(max(math.tanh(float(s) / 2.0) for s in raw))\n        mean_v = sum(vals) / len(vals)\n        min_v = min(vals)\n        return mean_v, min_v, missing\n\n    last_global_improve = 0\n'''

OLD_SUCCESSOR = '''            successor_goals = newgoals + rest\n            guide = math.tanh(cand_score / 2.0)\n'''
NEW_SUCCESSOR = '''            successor_goals = newgoals + rest\n            if node.depth == 0:\n                vmean, vmin, vmissing = one_ply_value(successor_goals, s2)\n                sh = B.h_hat(E, successor_goals, s2)\n                say("      [VALUE-PROBE] label=%s cand=%.6f ehyps=%d goals=%d "\n                    "H=%.6f value_mean=%.6f value_min=%.6f missing=%d"\n                    % (lab, cand_score, len(e_hyps), len(successor_goals),\n                       sh, vmean, vmin, vmissing))\n            guide = math.tanh(cand_score / 2.0)\n'''


def install_value_probe():
    src = inspect.getsource(S.adaptive_guided_selective)
    for old, new in ((OLD_INIT, NEW_INIT), (OLD_SUCCESSOR, NEW_SUCCESSOR)):
        if src.count(old) != 1:
            raise RuntimeError("8.019 source no longer matches value-probe patch")
        src = src.replace(old, new, 1)
    ns = {}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[VALUE-PROBE] installed root one-ply policy-value diagnostic")
    print("[VALUE-PROBE] search scoring and verifier gate are unchanged")


def main():
    install_value_probe()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
