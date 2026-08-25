#!/usr/bin/env python3
"""Predator 8.004-R3I4-indexed.

This is the SAME operational (3,4) proof-search controller as
predator 8.003-R3I4.py, with engineering-only preprocessing changes:

* the old eager serial assertion index is replaced by a full parallel,
  persistent cache; and
* set.mm parsing uses an exact split-point acceleration that preserves every
  legal parse while avoiding the combinatorial blow-up on huge stress-test
  formulas.

Neither change alters proof semantics, the R3/I4 control law, target access, or
Metamath verification.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R3I4_PATH = os.path.join(HERE, "predator 8.003-R3I4.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4", R3I4_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.003-R3I4")
R3I4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R3I4)
P8 = R3I4.P8

sys.path.insert(0, HERE)
import predator_fast_parse as PFP
import predator_index_cache as PIC

# Install before any full-corpus indexing or proof search.  The replacement is
# semantics-preserving: it only skips split points that cannot match the next
# literal grammar token.
PFP.install(P8.G)
PIC.configure(P8)
P8.Index = PIC.CachedParallelIndex
P8.VERSION = "8.004-R3I4-indexed-fastparse"


def build_index(argv):
    ap = argparse.ArgumentParser(
        prog="predator8-r3i4 build-index",
        description="Build or validate the full cached pre-target assertion index")
    ap.add_argument("file")
    ap.add_argument("--label", required=True)
    a = ap.parse_args(argv)

    if not os.environ.get("PREDATOR_INDEX_CACHE"):
        raise SystemExit("PREDATOR_INDEX_CACHE must name the cache file")

    print("\n" + "=" * 74)
    print("  PREDATOR 8 v%s  --  build full cached index for %s"
          % (P8.VERSION, a.label))
    print("=" * 74 + "\n")

    mm = P8.load(a.file)
    by_tc = P8.G.build_grammar(mm)
    if a.label not in mm.labels:
        raise SystemExit("target label %s not found" % a.label)
    cut = mm.order.index(a.label)
    idx = PIC.CachedParallelIndex(
        mm, by_tc, upto=cut, say=lambda s: print("  " + s))
    print("\n  INDEX READY: %s complete pre-target logical assertions\n"
          % f"{idx.n:,}")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "build-index":
        return build_index(sys.argv[2:])
    return P8.main()


if __name__ == "__main__":
    sys.exit(main() or 0)
