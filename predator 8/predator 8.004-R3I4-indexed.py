#!/usr/bin/env python3
"""Predator 8.004-R3I4-indexed.

This is the SAME operational (3,4) proof-search controller as
predator 8.003-R3I4.py, with engineering-only preprocessing changes:

* the old eager serial assertion index is replaced by a full parallel,
  persistent cache;
* set.mm parsing uses exact split-point acceleration;
* any proved theorem that remains pathological for generic parsing is
  reconstructed exactly from its existing Metamath proof and token-checked; and
* the search is given the target declaration's active disjoint-variable set so
  already-forced DV violations can be pruned before certificate emission.

No pre-target logical assertion is omitted.  None of these changes adds a proof
rule, reads the target proof, or relaxes Metamath verification.
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
import predator_index_cache_v4 as PIC

# Install exact parsing acceleration before indexing/search.  V4 then uses the
# existing Metamath proof as an exact syntax-tree source only for any proved
# theorem that still exceeds bounded parser guards.  Final token equality is
# mandatory, so the fallback fails closed if reconstruction disagrees.
PFP.install(P8.G)
PIC.configure(P8)
P8.Index = PIC.CachedParallelIndexV4
P8.VERSION = "8.004-R3I4-indexed-prooftree-v4-dvaware"

# Base Predator's prove() callback does not receive the target theorem frame.
# Load only enough context before cmd_prove to expose the unrestricted $d pairs
# active at the target declaration.  This is not target-proof access: only the
# declaration frame is read, while mm.proofs[target] remains untouched by the
# search.  The ordinary cmd_prove then reloads the file and runs unchanged.
_ORIG_CMD_PROVE = P8.cmd_prove


def _cmd_prove_with_dv_scope(a):
    mm0 = P8.load(a.file, say=lambda _s: None)
    if a.label in mm0.labels:
        data = mm0.labels[a.label][1]
        declared_dvs = data[0]
        active_dvs = mm0.scope_dvs.get(a.label, declared_dvs)
        R3I4.set_target_scope_dvs(active_dvs)
    else:
        R3I4.set_target_scope_dvs(None)
    return _ORIG_CMD_PROVE(a)


P8.cmd_prove = _cmd_prove_with_dv_scope


def build_index(argv):
    ap = argparse.ArgumentParser(
        prog="predator8-r3i4 build-index",
        description="Build or validate the complete cached pre-target assertion index")
    ap.add_argument("file")
    ap.add_argument("--label", required=True)
    a = ap.parse_args(argv)

    if not os.environ.get("PREDATOR_INDEX_CACHE"):
        raise SystemExit("PREDATOR_INDEX_CACHE must name the cache file")

    print("\n" + "=" * 74)
    print("  PREDATOR 8 v%s  --  build complete cached index for %s"
          % (P8.VERSION, a.label))
    print("=" * 74 + "\n")

    mm = P8.load(a.file)
    by_tc = P8.G.build_grammar(mm)
    if a.label not in mm.labels:
        raise SystemExit("target label %s not found" % a.label)
    cut = mm.order.index(a.label)
    idx = PIC.CachedParallelIndexV4(
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
