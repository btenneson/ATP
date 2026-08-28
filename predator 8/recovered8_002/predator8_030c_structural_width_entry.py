#!/usr/bin/env python3
"""Parameterized entry point for Predator 8.030 structural-width search.

This wrapper exposes both retained structural width D and macro internal span so
adaptive-refinement experiments can change them between passes without changing
proof semantics.  C remains fixed at zero and final verification remains the
same Metamath check used by the recovered Predator stack.
"""
from __future__ import annotations

import argparse
import sys

import predator8_030_structural_width as W


def main():
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("--structural-width", type=int, required=True)
    gate.add_argument("--macro-max-extra", type=int, default=2)
    ns, rest = gate.parse_known_args()
    if ns.structural_width < 1:
        gate.error("--structural-width must be >= 1")
    if ns.macro_max_extra < 0 or ns.macro_max_extra > 2:
        gate.error("--macro-max-extra must be one of 0,1,2")

    # install_structural_width_controller captures this module constant when it
    # compiles the patched controller, so set it before installation.
    W.MACRO_MAX_EXTRA = int(ns.macro_max_extra)
    restore = W.install_c0_profile(160)
    W.install_structural_width_controller(ns.structural_width)
    print("[STRUCTURAL-WIDTH] Predator 8.030c ENABLED")
    print("[STRUCTURAL-WIDTH] C=0; retained structural-class cap D=%d" % ns.structural_width)
    print("[STRUCTURAL-WIDTH] macro_max_extra=%d; max primitive span=%d" %
          (ns.macro_max_extra, 1 + ns.macro_max_extra))
    print("[STRUCTURAL-WIDTH] verifier unchanged")
    try:
        sys.argv = [sys.argv[0]] + rest
        return W.S.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
