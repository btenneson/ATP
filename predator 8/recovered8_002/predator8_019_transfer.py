#!/usr/bin/env python3
"""Target-generic transfer runner for the frozen Predator 8.019 controller.

This file does NOT modify the historical 8.019 prcom freeze.  It reuses the
same selective self-aware controller, full-goal exactifier, proof engine, and
verifier boundary on another target label.

A model trained at an earlier strict cutoff may be transferred to a later
Metamath target when:
  * the environment hash matches exactly;
  * the model attests target_proof_used == False;
  * the model attests downstream_used == False; and
  * the model cutoff label occurs no later than the requested target.

Thus the recovered prcom policy can be tested as a leakage-controlled transfer
policy on later theorems such as sgrpcl without reading the sgrpcl proof.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time

import predator8_016_prcom_exactify as P
import predator8_017_fullgraph_exactify as F
import predator8_019_selective_sink as S
from predator8_ml_ranker import RuntimePolicy

VERSION = "8.019-transfer"
ROOT = Path(__file__).resolve().parent


def _attest_transfer(B, mm, environment: Path, model: Path, metadata: dict,
                     target: str) -> None:
    if metadata.get("environment_sha256") != B.sha256(environment):
        raise SystemExit("model/environment hash mismatch")
    if metadata.get("target_proof_used") is not False:
        raise SystemExit("model attestation failed: target_proof_used is not false")
    if metadata.get("downstream_used") is not False:
        raise SystemExit("model attestation failed: downstream_used is not false")

    model_cutoff = metadata.get("cutoff_before")
    if not model_cutoff or model_cutoff not in mm.order:
        raise SystemExit("model attestation failed: cutoff_before label missing from environment")
    if target not in mm.order:
        raise SystemExit("target label not present in environment: %s" % target)

    model_ix = mm.order.index(model_cutoff)
    target_ix = mm.order.index(target)
    if model_ix > target_ix:
        raise SystemExit(
            "unsafe transfer: model cutoff %s occurs after target %s" %
            (model_cutoff, target)
        )
    print("  TRANSFER ATTESTATION: model cutoff=%s index=%d <= target=%s index=%d; "
          "target/downstream proof use attested false" %
          (model_cutoff, model_ix, target, target_ix))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True)
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
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if not (0 <= a.brute_reserve <= a.budget):
        ap.error("brute reserve must lie in [0,budget]")

    environment = Path(a.environment).resolve()
    model = Path(a.model).resolve()
    output = a.out or ("%s_p8_019_transfer.mm" % a.label)

    B = P.B
    E = B.load_engine(Path(a.engine).resolve())
    print("=" * 78)
    print("Predator %s -- %s -- global budget %s" %
          (VERSION, a.label, f"{a.budget:,}"))
    print("=" * 78)

    mm = E.load(str(environment), say=print)
    if a.label not in mm.order:
        raise SystemExit("target label not found: %s" % a.label)
    cutoff = mm.order.index(a.label)
    by_tc = B.strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=print)
    statement = mm.labels[a.label][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    policy = RuntimePolicy.load(model, E, by_tc)
    md = policy.artifact["metadata"]
    _attest_transfer(B, mm, environment, model, md, a.label)

    target_data = mm.labels[a.label][1]
    probe_ctx = F.make_full_probe_context(E, index, mm, target_data, cutoff)

    # Hide the requested target proof for the whole search/probe interval.
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

    if result is None:
        print("  OUTCOME: UNKNOWN UNDER DECLARED RESOURCE BOUNDS (%s expansions, %.1fs)"
              % (f"{total:,}", elapsed))
        return 1

    verdict, proof, emitted = B.verify_emit(
        E, mm, cutoff, a.label, result, environment, output, model)
    print("  candidate found after total %s expansions, %.1fs; proof steps=%s; in-process CV=%s"
          % (f"{total:,}", elapsed, f"{len(proof):,}", verdict.upper()))
    if verdict != "ok":
        print("  OUTCOME: PROTOCOL FAILURE")
        return 2

    external = subprocess.run(
        [sys.executable, str(ROOT / "predator8_external_cv.py"),
         str(environment), "--target", a.label, "--certificate", str(emitted)],
        cwd=str(ROOT), text=True, capture_output=True, check=False)
    print((external.stdout + external.stderr).strip())
    if external.returncode:
        print("  OUTCOME: PROTOCOL FAILURE")
        return 2

    print("  OUTCOME: VERIFIED PROOF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
