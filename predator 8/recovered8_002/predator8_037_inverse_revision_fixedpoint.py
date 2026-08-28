#!/usr/bin/env python3
"""Predator 8.037: iterative inverse-creativity revision to a local fixed point.

Starting point
--------------
Use the verified 8.036 full-inverse prcom treatment as the initial creativity
state.  Each creativity coordinate is an element of the logit-addition group
G=((0,1),oplus), with identity 0.5 and inverse c^{-1}=1-c.

Revision rule
-------------
A pass proposes the algebraically distinguished inverse neighbors of the
current state: invert each coordinate separately, plus the full coordinatewise
inverse.  Exact creativity vectors already tested are never tested again.

A verified outcome is *novel* when its
    (compressed_bits, outer_expansions, proof_steps, certificate_sha256)
has not appeared before.  Novel but non-improving outcomes are banked as
experience.  A revision becomes the next parent only when it strictly improves
protected lexicographic key
    (compressed_bits, outer_expansions, proof_steps).

The process stops at the first complete pass with no accepted improvement.
That is the experimental fixed point under this inverse-neighborhood operator.
A max-pass argument is only a safety ceiling, not the scientific stop rule.

Verifier, theoremhood, frozen set.mm, target guards, and C=0/I=5 are unchanged.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S
import predator8_029_prcom_shortcut_macros as M
import predator8_035_c3_conservative_compilation as C3
import predator8_036_inverse_creativity_prcom as I36

VERSION = "8.037-inverse-revision-fixedpoint"
KEYS = tuple(I36.X.keys())
START_VECTOR = dict(I36.X_INV)
START_RESULT = {
    "bits": 478,
    "expansions": 107,
    "proof_steps": 28,
    "certificate_sha256": "53b24a27c16874ad9de94776a9b528ba57ee384072cc082032ab82d26f557ca0",
    "verified": True,
    "source_run": 33186595412,
}

BITS_RE = re.compile(r"\[C3-CERT\].*?bits=(\d+)\s+proof_steps=(\d+)")
EXP_RE = re.compile(r"candidate found after total\s+(\d+)\s+expansions")
SHA_RE = re.compile(r"certificate sha256:\s*([0-9a-fA-F]{64})")


def canonical_vector(v):
    return tuple((k, round(float(v[k]), 12)) for k in KEYS)


def inv_scalar(c):
    c = float(c)
    if not (0.0 < c < 1.0):
        raise ValueError("creativity group coordinate must be in (0,1)")
    return 1.0 - c


def inverse_one(v, key):
    out = dict(v)
    out[key] = inv_scalar(out[key])
    return out


def inverse_all(v):
    return {k: inv_scalar(v[k]) for k in KEYS}


def protected_key(result):
    return (int(result["bits"]), int(result["expansions"]), int(result["proof_steps"]))


def result_signature(result):
    return protected_key(result) + (str(result["certificate_sha256"]),)


def parse_result(text, returncode, tag):
    bm = list(BITS_RE.finditer(text))
    em = list(EXP_RE.finditer(text))
    sm = list(SHA_RE.finditer(text))
    verified = ("OUTCOME: VERIFIED PROOF" in text and
                "EXTERNAL CV: OK" in text and bm and em and sm)
    if not verified:
        return {
            "tag": tag, "verified": False, "returncode": returncode,
            "bits": None, "expansions": None, "proof_steps": None,
            "certificate_sha256": None,
        }
    return {
        "tag": tag,
        "verified": True,
        "returncode": returncode,
        "bits": int(bm[-1].group(1)),
        "proof_steps": int(bm[-1].group(2)),
        "expansions": int(em[-1].group(1)),
        "certificate_sha256": sm[-1].group(1).lower(),
    }


def worker_main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--seed", type=int, default=2302)
    ap.add_argument("--vector-json", required=True)
    ap.add_argument("--tag", required=True)
    ns, rest = ap.parse_known_args(argv)

    c3 = json.loads(ns.vector_json)
    if set(c3) != set(KEYS):
        raise SystemExit("worker vector keys do not match creativity coordinates")
    for k in KEYS:
        if not (0.0 < float(c3[k]) < 1.0):
            raise SystemExit("worker coordinate %s not in (0,1)" % k)

    mining_window = 400 + int(round(2200 * c3["c_lemma"]))
    freq, bigram, mined, cutoff = C3.mine_pre_target(
        ns.environment, ns.engine, ns.label, mining_window)

    print("[REV-WORKER] version=%s tag=%s C=0 I=5 seed=%d" %
          (VERSION, ns.tag, ns.seed))
    print("[REV-VECTOR] %s" % json.dumps(c3, sort_keys=True))
    print("[REV-GROUP] G=((0,1),logit-addition) identity=0.5 inverse(c)=1-c")
    print("[REV-GUARD] target=%s target_proof_used=False downstream=False route_attraction=False" % ns.label)
    print("[REV-MINE] strict_pre_target=True cutoff=%d window=%d verified_proofs=%d labels=%d bigrams=%d" %
          (cutoff, mining_window, mined, len(freq), len(bigram)))

    C3.configure_macros(c3)
    opener_cap = min(128, 8 + int(120 * c3["cW"] ** 2))
    max_depth = 12 + int(round(4 * c3["cL"]))
    print("[REV-DERIVED] macro_span<=%d macro_topk=%d opener_cap=%d max_depth=%d" %
          (1 + M.MACRO_MAX_EXTRA, M.MACRO_TOPK_PER_KIND, opener_cap, max_depth))

    original_policy = C3.install_policy_proxy(c3, freq, bigram)
    original_verify_emit = C3.install_bit_logger()
    M.install_shortcut_controller()
    restore_profile = I36.install_fixed_c0_i5(c3, opener_cap)
    S.VERSION = VERSION + "/" + ns.tag

    sys.argv = [sys.argv[0], ns.environment,
                "--engine", ns.engine,
                "--model", ns.model,
                "--label", ns.label,
                "--seed", str(ns.seed),
                "--creativity", str(c3["cT"]),
                "--opener-cap", str(opener_cap),
                "--max-depth", str(max_depth)] + rest
    try:
        return S.main()
    finally:
        restore_profile()
        P.RuntimePolicy = original_policy
        P.B.verify_emit = original_verify_emit


def run_candidate(script, environment, engine, model, label, seed, vector,
                  tag, outdir, budget, timeout_seconds):
    outdir = Path(outdir)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", tag)
    mm_path = outdir / (safe + ".mm")
    log_path = outdir / (safe + ".log")
    cmd = [
        sys.executable, str(script), "--worker", environment,
        "--engine", engine, "--model", model, "--label", label,
        "--seed", str(seed),
        "--vector-json", json.dumps(vector, sort_keys=True, separators=(",", ":")),
        "--tag", tag,
        "--budget", str(budget),
        "--brute-reserve", "0",
        "--max-open", "8",
        "--progress", "25",
        "--frontier-limit", "120000",
        "--probe-depth", "0",
        "--probe-cap", "0",
        "--probe-total-cap", "0",
        "--probe-next-layer", "0",
        "--out", str(mm_path),
    ]
    started = time.time()
    try:
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=timeout_seconds)
        text = cp.stdout
        rc = cp.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        text = (exc.stdout or "")
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        text += "\n[REV-TIMEOUT] candidate timeout reached\n"
        rc = 124
        timed_out = True
    log_path.write_text(text, encoding="utf-8", errors="replace")
    result = parse_result(text, rc, tag)
    result["vector"] = vector
    result["wall_seconds"] = round(time.time() - started, 3)
    result["timed_out"] = timed_out
    result["log"] = str(log_path)
    result["certificate"] = str(mm_path) if mm_path.exists() else None
    return result


def controller_main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--seed", type=int, default=2302)
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--max-passes", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--candidate-timeout", type=int, default=1500)
    ap.add_argument("--outdir", default="p8_037_revision_records")
    ns = ap.parse_args(argv)

    outdir = Path(ns.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()

    parent_vector = dict(START_VECTOR)
    parent_result = dict(START_RESULT)
    bank_signatures = {result_signature(parent_result)}
    visited_vectors = {canonical_vector(parent_vector)}
    history = []

    print("[REV] version=%s" % VERSION)
    print("[REV-START] source_run=%s vector=%s result=%s key=%s" %
          (START_RESULT["source_run"], json.dumps(parent_vector, sort_keys=True),
           json.dumps(parent_result, sort_keys=True), protected_key(parent_result)))
    print("[REV-RULE] accept iff verified, novel, and protected key strictly improves parent")
    print("[REV-STOP] stabilize after one complete pass with no accepted improvement")

    stabilized = False
    for pass_no in range(1, ns.max_passes + 1):
        proposals = []
        for key in KEYS:
            v = inverse_one(parent_vector, key)
            cv = canonical_vector(v)
            if cv not in visited_vectors:
                proposals.append(("p%d-inv-%s" % (pass_no, key), v))
                visited_vectors.add(cv)
        vfull = inverse_all(parent_vector)
        cvfull = canonical_vector(vfull)
        if cvfull not in visited_vectors:
            proposals.append(("p%d-full-inverse" % pass_no, vfull))
            visited_vectors.add(cvfull)

        print("[REV-PASS] pass=%d parent_key=%s proposals=%d" %
              (pass_no, protected_key(parent_result), len(proposals)))
        if not proposals:
            print("[REV-STABLE] pass=%d reason=no-unvisited-inverse-neighbors" % pass_no)
            stabilized = True
            break

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, ns.parallel)) as ex:
            futs = [ex.submit(run_candidate, script, ns.environment, ns.engine,
                              ns.model, ns.label, ns.seed, vector, tag, outdir,
                              ns.budget, ns.candidate_timeout)
                    for tag, vector in proposals]
            for fut in concurrent.futures.as_completed(futs):
                r = fut.result()
                results.append(r)
                print("[REV-CANDIDATE] %s" % json.dumps(r, sort_keys=True))

        novel = []
        improving = []
        for r in results:
            if not r.get("verified"):
                continue
            sig = result_signature(r)
            is_novel = sig not in bank_signatures
            if is_novel:
                bank_signatures.add(sig)
                novel.append(r)
            if is_novel and protected_key(r) < protected_key(parent_result):
                improving.append(r)

        pass_record = {
            "pass": pass_no,
            "parent_before": parent_result,
            "parent_vector_before": parent_vector,
            "results": results,
            "novel_count": len(novel),
            "improving_count": len(improving),
        }

        if not improving:
            print("[REV-STABLE] pass=%d novel_verified=%d improving=0 parent_key=%s" %
                  (pass_no, len(novel), protected_key(parent_result)))
            pass_record["accepted"] = None
            history.append(pass_record)
            stabilized = True
            break

        winner = min(improving, key=protected_key)
        old_key = protected_key(parent_result)
        parent_result = {k: winner[k] for k in
                         ("bits", "expansions", "proof_steps", "certificate_sha256", "verified")}
        parent_result["tag"] = winner["tag"]
        parent_vector = dict(winner["vector"])
        pass_record["accepted"] = winner
        history.append(pass_record)
        print("[REV-ACCEPT] pass=%d tag=%s %s -> %s" %
              (pass_no, winner["tag"], old_key, protected_key(parent_result)))

    summary = {
        "version": VERSION,
        "stabilized": stabilized,
        "max_passes": ns.max_passes,
        "passes_completed": len(history),
        "final_result": parent_result,
        "final_key": protected_key(parent_result),
        "final_vector": parent_vector,
        "novel_verified_signatures": len(bank_signatures),
        "visited_vectors": len(visited_vectors),
        "history": history,
    }
    (outdir / "revision_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print("[REV-FINAL] %s" % json.dumps({
        "stabilized": stabilized,
        "passes_completed": len(history),
        "final_key": list(protected_key(parent_result)),
        "final_vector": parent_vector,
        "novel_verified_signatures": len(bank_signatures),
        "visited_vectors": len(visited_vectors),
    }, sort_keys=True))
    return 0


def main():
    args = sys.argv[1:]
    if args and args[0] == "--worker":
        return worker_main(args[1:])
    return controller_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
