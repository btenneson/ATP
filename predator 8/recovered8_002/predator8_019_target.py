#!/usr/bin/env python3
"""Target-generic runner for the frozen Predator 8.019 controller.

This file does not modify the historical 8.019 prcom implementation or its
recorded blob SHA.  It reuses the same selective basin controller and full-goal
exactifier on an arbitrary pre-existing Metamath theorem label.

Two ranking modes are supported:
  * --model PATH: requires a target-clean RuntimePolicy whose metadata attests
    cutoff_before == target, target_proof_used == False, downstream_used == False.
  * --no-ml: leakage-safe zero learned scores.  This preserves 8.019's control
    logic but is NOT the recovered 8.002 learned search distribution.

In both modes only assertions strictly before the target are search-visible and
the target proof is guarded from access.  Any emitted certificate is checked
in-process and by the independent external checker.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time

import predator8_015_bidirectional_attention as B
import predator8_016_prcom_exactify as P
import predator8_017_fullgraph_exactify as F
import predator8_019_selective_sink as S
from predator8_ml_ranker import RuntimePolicy

VERSION = "8.019-target-generic"
ROOT = Path(__file__).resolve().parent


class ZeroPolicy:
    """Leakage-safe policy: give every legal candidate learned score 0."""
    artifact = {"metadata": {"mode": "no-ml"}}

    def rank(self, goal, candidates):
        return [0.0] * len(candidates)


def verify_emit(E, mm, cutoff, label, result, environment, output, model_desc):
    root, sub = result
    fvar, fallback = B.formal_variables(E, mm, cutoff)
    proof = root.emit(sub, fvar, fallback)
    statement = mm.labels[label][1][3]
    output = Path(output)
    output.write_text(
        "$( Predator %s candidate for %s; ranking %s $)\n" %
        (VERSION, label, model_desc)
        + "$[ %s $]\n" % Path(environment).name
        + "chk $p %s $= %s $.\n" %
        (" ".join(statement), " ".join(proof)), encoding="utf-8")

    check = E.MM()
    check.labels = dict(mm.labels)
    check.order = list(mm.order)
    check.proofs = dict(mm.proofs)
    check.constants, check.variables = mm.constants, mm.variables
    check.scope_dvs = dict(mm.scope_dvs)
    data = mm.labels[label][1]
    check.labels["__p8_019_generic_check__"] = ("$p", data)
    check.proofs["__p8_019_generic_check__"] = proof
    check.scope_dvs["__p8_019_generic_check__"] = mm.scope_dvs.get(label, data[0])
    verdict = check.verify("__p8_019_generic_check__")
    return verdict, proof, output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    rank = ap.add_mutually_exclusive_group(required=True)
    rank.add_argument("--model")
    rank.add_argument("--no-ml", action="store_true")
    ap.add_argument("--label", required=True)
    ap.add_argument("--budget", type=int, default=30000)
    ap.add_argument("--brute-reserve", type=int, default=6000)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--max-open", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--creativity", type=float, default=0.55)
    ap.add_argument("--opener-cap", type=int, default=48)
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--frontier-limit", type=int, default=120000)
    ap.add_argument("--probe-depth", type=int, default=3)
    ap.add_argument("--probe-cap", type=int, default=2000)
    ap.add_argument("--probe-total-cap", type=int, default=4000)
    ap.add_argument("--probe-next-layer", type=int, default=30000)
    ap.add_argument("--out")
    a = ap.parse_args()

    if not (0 <= a.brute_reserve <= a.budget):
        ap.error("brute reserve must lie in [0,budget]")
    if a.out is None:
        a.out = f"{a.label}_p8_019.mm"

    environment = Path(a.environment).resolve()
    E = B.load_engine(Path(a.engine).resolve())

    print("=" * 78)
    print("Predator %s -- %s -- global budget %s" %
          (VERSION, a.label, f"{a.budget:,}"))
    print("=" * 78)
    mm = E.load(str(environment), say=print)
    if a.label not in mm.labels or a.label not in mm.order:
        raise SystemExit("target label not found in environment: " + a.label)
    cutoff = mm.order.index(a.label)
    by_tc = B.strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=print)
    statement = mm.labels[a.label][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    if a.no_ml:
        policy = ZeroPolicy()
        model_desc = "NO-ML"
        print("  policy: NO-ML leakage-safe zero learned scores")
    else:
        model = Path(a.model).resolve()
        policy = RuntimePolicy.load(model, E, by_tc)
        md = policy.artifact["metadata"]
        if md.get("environment_sha256") != B.sha256(environment):
            raise SystemExit("model/environment hash mismatch")
        if md.get("cutoff_before") != a.label:
            raise SystemExit("model cutoff mismatch: target-clean model required")
        if md.get("target_proof_used") is not False:
            raise SystemExit("target proof exclusion not attested")
        if md.get("downstream_used") is not False:
            raise SystemExit("downstream exclusion not attested")
        model_desc = B.sha256(model)
        print("  policy: clean pre-%s; theorems=%s; target proof used=NO; downstream used=NO"
              % (a.label, md.get("theorems")))
        print("  model sha256: %s" % model_desc)

    print("  environment sha256: %s" % B.sha256(environment))
    target_data = mm.labels[a.label][1]
    probe_ctx = F.make_full_probe_context(E, index, mm, target_data, cutoff)

    original = mm.proofs
    mm.proofs = B.GuardedProofs(original, a.label)
    probe_ctx.mm = mm
    started = time.perf_counter()
    try:
        guided_cap = a.budget - a.brute_reserve
        result, gused, besth, transitions, reason = S.adaptive_guided_selective(
            E, goal, index, policy, guided_cap, a.max_depth, a.max_open, a.seed,
            probe_ctx=probe_ctx, creativity=a.creativity,
            opener_cap=a.opener_cap, progress=a.progress,
            frontier_limit=a.frontier_limit, probe_depth=a.probe_depth,
            probe_cap=a.probe_cap, probe_total_cap=a.probe_total_cap,
            probe_next_layer=a.probe_next_layer)
        bused = 0
        brute_depth = None
        if result is None:
            remaining = a.budget - gused
            print("    meta-controller: guided stop reason=%s; remaining=%s; entering brute %s"
                  % (reason, f"{remaining:,}", B.COORD["brute"]))
            result, bused, brute_depth = B.brute_iddfs(
                E, goal, index, remaining, a.max_depth, a.max_open,
                progress=a.progress)
    finally:
        mm.proofs = original

    total = gused + bused
    elapsed = time.perf_counter() - started
    print("  CONTROL SUMMARY: guided+probe=%s brute=%s total=%s/%s best_h=%.3f transitions=%s"
          % (f"{gused:,}", f"{bused:,}", f"{total:,}", f"{a.budget:,}",
             besth, transitions))
    if brute_depth is not None:
        print("  brute solution depth limit: %d" % brute_depth)
    if result is None:
        print("  OUTCOME: UNKNOWN UNDER DECLARED RESOURCE BOUNDS (%s expansions, %.1fs)"
              % (f"{total:,}", elapsed))
        return 1

    verdict, proof, output = verify_emit(
        E, mm, cutoff, a.label, result, environment, a.out, model_desc)
    print("  candidate found after total %s expansions, %.1fs; proof steps=%s; in-process CV=%s"
          % (f"{total:,}", elapsed, f"{len(proof):,}", verdict.upper()))
    if verdict != "ok":
        print("  OUTCOME: PROTOCOL FAILURE")
        return 2

    external = subprocess.run(
        [sys.executable, str(ROOT / "predator8_external_cv.py"),
         str(environment), "--target", a.label, "--certificate", str(output)],
        cwd=str(ROOT), text=True, capture_output=True, check=False)
    print((external.stdout + external.stderr).strip())
    if external.returncode:
        print("  OUTCOME: PROTOCOL FAILURE")
        return 2
    print("  OUTCOME: VERIFIED PROOF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
