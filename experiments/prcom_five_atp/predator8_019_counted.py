#!/usr/bin/env python3
"""Thin instrumentation wrapper for predator8_019_target.py.

It does not alter search choices.  It intercepts progress prints so the five-ATP
federation can freeze an exact resource-count snapshot when the first proof is
independently verified.
"""
from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
import re
import sys

_ORIG_PRINT = builtins.print
_PROGRESS_FILE = os.environ.get("ATP_PROGRESS_FILE")


def _arg_int(flag: str, default: int) -> int:
    try:
        i = sys.argv.index(flag)
        return int(sys.argv[i + 1])
    except Exception:
        return default


BUDGET = _arg_int("--budget", 10000)
state = {"expansions": 0, "verified": False, "proof_steps": None, "brute_base": 0}


def write_progress():
    if not _PROGRESS_FILE:
        return
    p = Path(_PROGRESS_FILE)
    payload = {k: state[k] for k in ("expansions", "verified", "proof_steps")}
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def counted_print(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    text = sep.join(str(x) for x in args)

    m = re.search(r"\[GUIDED\].*?total=([0-9,]+)", text)
    if m:
        state["expansions"] = max(state["expansions"], _num(m.group(1)))
        write_progress()

    m = re.search(r"meta-controller:.*?remaining=([0-9,]+)", text)
    if m:
        state["brute_base"] = BUDGET - _num(m.group(1))
        state["expansions"] = max(state["expansions"], state["brute_base"])
        write_progress()

    m = re.search(r"\[BRUTE\] exp=([0-9,]+)", text)
    if m:
        state["expansions"] = max(
            state["expansions"], state["brute_base"] + _num(m.group(1)))
        write_progress()

    m = re.search(r"\[CANDIDATE-ZERO\].*?total=([0-9,]+)", text)
    if m:
        state["expansions"] = max(state["expansions"], _num(m.group(1)))
        write_progress()

    m = re.search(
        r"candidate found after total ([0-9,]+) expansions.*?proof steps=([0-9,]+)",
        text,
    )
    if m:
        state["expansions"] = _num(m.group(1))
        state["proof_steps"] = _num(m.group(2))
        write_progress()

    _ORIG_PRINT(*args, **kwargs)

    if "OUTCOME: VERIFIED PROOF" in text:
        state["verified"] = True
        write_progress()
        _ORIG_PRINT(
            f"@@VERIFIED expansions={state['expansions']} "
            f"proof_steps={state['proof_steps']}",
            flush=True,
        )


builtins.print = counted_print

import predator8_019_target as target  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(target.main())
