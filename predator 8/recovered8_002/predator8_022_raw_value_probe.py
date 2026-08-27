#!/usr/bin/env python3
"""Predator 8.022 diagnostic: raw one-ply policy geometry at the prcom root.

8.021 showed that tanh(score/2) saturates at 1 for almost every subgoal and is
therefore useless as a state-value coordinate.  This diagnostic leaves search
ordering unchanged and logs unsquashed policy information for every legal root
successor: mean/min best closer score, mean/min top-two score margin, average
closer count, and missing-closer count.

No target proof is read or hard-coded.  Proof admissibility, target guard,
candidate-zero gate, and external verification semantics remain unchanged.
"""
from __future__ import annotations

import inspect
import math

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n    last_global_improve = 0\n'''
NEW_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n\n    def raw_one_ply_geometry(goals, sub):\n        if not goals:\n            return {\n                "mean_best": float("inf"),\n                "min_best": float("inf"),\n                "mean_margin": float("inf"),\n                "min_margin": float("inf"),\n                "mean_closers": 0.0,\n                "missing": 0,\n            }\n        bests = []\n        margins = []\n        counts = []\n        missing = 0\n        for gg, _, _ in goals:\n            g2 = E.apply_sub(gg, sub)\n            closers2, _ = index.candidates(g2)\n            counts.append(len(closers2))\n            if not closers2:\n                missing += 1\n                continue\n            raw = [float(s) for s in policy.rank(g2, closers2)]\n            if not raw:\n                missing += 1\n                continue\n            raw.sort(reverse=True)\n            bests.append(raw[0])\n            margins.append(raw[0] - raw[1] if len(raw) > 1 else raw[0])\n        if not bests:\n            return {\n                "mean_best": float("-inf"),\n                "min_best": float("-inf"),\n                "mean_margin": float("-inf"),\n                "min_margin": float("-inf"),\n                "mean_closers": sum(counts) / max(1, len(counts)),\n                "missing": missing,\n            }\n        return {\n            "mean_best": sum(bests) / len(bests),\n            "min_best": min(bests),\n            "mean_margin": sum(margins) / len(margins),\n            "min_margin": min(margins),\n            "mean_closers": sum(counts) / max(1, len(counts)),\n            "missing": missing,\n        }\n\n    last_global_improve = 0\n'''

OLD_SUCCESSOR = '''            successor_goals = newgoals + rest\n            guide = math.tanh(cand_score / 2.0)\n'''
NEW_SUCCESSOR = '''            successor_goals = newgoals + rest\n            if node.depth == 0:\n                q = raw_one_ply_geometry(successor_goals, s2)\n                sh = B.h_hat(E, successor_goals, s2)\n                say("      [RAW-VALUE] label=%s cand=%.6f ehyps=%d goals=%d H=%.6f "\n                    "mean_best=%.6f min_best=%.6f mean_margin=%.6f "\n                    "min_margin=%.6f mean_closers=%.3f missing=%d"\n                    % (lab, cand_score, len(e_hyps), len(successor_goals), sh,\n                       q["mean_best"], q["min_best"], q["mean_margin"],\n                       q["min_margin"], q["mean_closers"], q["missing"]))\n            guide = math.tanh(cand_score / 2.0)\n'''


def install_raw_value_probe():
    src = inspect.getsource(S.adaptive_guided_selective)
    for old, new in ((OLD_INIT, NEW_INIT), (OLD_SUCCESSOR, NEW_SUCCESSOR)):
        if src.count(old) != 1:
            raise RuntimeError("8.019 source no longer matches raw-value patch")
        src = src.replace(old, new, 1)
    ns = {}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[RAW-VALUE] installed unsquashed one-ply root diagnostic")
    print("[RAW-VALUE] search ordering and verifier gate are unchanged")


def main():
    install_raw_value_probe()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
