#!/usr/bin/env python3
"""Correct entry point for Predator 8.030 structural-width experiment.

8.030 patches predator8_019_selective_sink.adaptive_guided_selective, so the
experiment must enter through predator8_019_selective_sink.main().  The first
pilot entry point accidentally called the 8.016 main path; those pilot results
are controls only and are not evidence about structural width.
"""
from __future__ import annotations

import argparse
import sys

import predator8_030_structural_width as W


def main():
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("--structural-width", type=int, required=True)
    ns, rest = gate.parse_known_args()
    if ns.structural_width < 1:
        gate.error("--structural-width must be >= 1")

    restore = W.install_c0_profile(160)
    W.install_structural_width_controller(ns.structural_width)
    print("[STRUCTURAL-WIDTH] Predator 8.030b ENABLED")
    print("[STRUCTURAL-WIDTH] C=0; exact retained structural-class cap D=%d" % ns.structural_width)
    print("[STRUCTURAL-WIDTH] primitive and macro successors compete after quotienting")
    print("[STRUCTURAL-WIDTH] final certificate verification unchanged")
    try:
        sys.argv = [sys.argv[0]] + rest
        return W.S.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
