#!/usr/bin/env python3
"""Predator 8.023 diagnostic: trace early root-basin scheduling on prcom C0/I4.

Search behavior is unchanged.  The wrapper instruments the 8.019 pop loop and
prints the first 60 guided frontier pops with cumulative priority, depth, open
goal count, H_hat, and root-basin prefix.  This diagnoses whether the 41
expansions to settlement are caused primarily by over-deepening an early wrong
basin rather than trying promising root alternatives.
"""
from __future__ import annotations

import inspect

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD_POP = '''        exp += 1\n        total_used = exp + probe_used_total\n        basin = Q._basin_prefix(node)\n'''
NEW_POP = '''        exp += 1\n        total_used = exp + probe_used_total\n        basin = Q._basin_prefix(node)\n        if exp <= 60:\n            try:\n                trace_h = B.h_hat(E, node.goals, node.sub)\n            except Exception:\n                trace_h = float("nan")\n            say("      [BASIN-TRACE] exp=%d priority=%.9f depth=%d goals=%d H=%.6f basin=%s"\n                % (exp, priority, node.depth, len(node.goals), trace_h,\n                   basin or "<root>"))\n'''


def install_trace():
    src = inspect.getsource(S.adaptive_guided_selective)
    if src.count(OLD_POP) != 1:
        raise RuntimeError("8.019 source no longer matches basin-trace patch")
    src = src.replace(OLD_POP, NEW_POP, 1)
    ns = {}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[BASIN-TRACE] installed; search ordering is unchanged")


def main():
    install_trace()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
