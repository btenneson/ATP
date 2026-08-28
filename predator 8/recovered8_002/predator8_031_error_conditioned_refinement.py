#!/usr/bin/env python3
"""Predator 8.031: error-conditioned multi-pass structural refinement.

Idea
----
Use a cheap, narrow first pass to locate an approximate proof trajectory.  Do
not treat verifier rejection as a dead end.  Instead classify the failure and
change the next pass accordingly.

Current refinement policy:
* VERIFIED -> stop immediately.
* type/substitution/verifier mismatch -> widen structural diversity and shorten
  shortcut macros, exposing more primitive distinctions around the failure.
* UNKNOWN/no closed candidate -> widen structural diversity but preserve macro
  span, because the evidence points to insufficient future diversity rather
  than an over-compressed candidate.
* other protocol failure -> widen and shorten conservatively.

All pass expansions are accumulated.  A refinement proof therefore does not get
free restarts.  Each pass writes its own log/candidate, and only an independently
verified pass is copied to the requested final certificate path.

This is a first implementation of error-conditioned refinement.  It adapts
between passes; a later version can resume from the earliest implicated local
proof state rather than restarting the whole guided search.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "predator8_030c_structural_width_entry.py"

TOTAL_RE = re.compile(r"CONTROL SUMMARY:.*?total=([0-9,]+)/")
PROOF_RE = re.compile(r"proof steps=([0-9,]+)")


def classify(text: str, returncode: int) -> str:
    low = text.lower()
    if "outcome: verified proof" in low and returncode == 0:
        return "VERIFIED"
    if "type mismatch" in low:
        return "TYPE_MISMATCH"
    if "distinct variable" in low or "disjoint" in low or " dv " in low:
        return "DV_MISMATCH"
    if "unification" in low or "substitution" in low:
        return "SUBSTITUTION_MISMATCH"
    if "outcome: unknown" in low or "unknown under declared resource bounds" in low:
        return "UNKNOWN"
    if "mmerror" in low or "external cv: failed" in low or "protocol failure" in low:
        return "VERIFIER_FAILURE"
    if returncode == 0:
        return "NO_CERTIFICATE"
    return "OTHER_FAILURE"


def next_parameters(kind: str, width: int, macro_extra: int, max_width: int):
    widened = min(max_width, max(width + 1, width * 2))
    if kind in {"TYPE_MISMATCH", "DV_MISMATCH", "SUBSTITUTION_MISMATCH",
                "VERIFIER_FAILURE", "OTHER_FAILURE"}:
        return widened, max(0, macro_extra - 1), "widen+decompress"
    if kind in {"UNKNOWN", "NO_CERTIFICATE"}:
        return widened, macro_extra, "widen-only"
    return width, macro_extra, "halt"


def extract_total(text: str) -> int:
    vals = TOTAL_RE.findall(text)
    if not vals:
        return 0
    return int(vals[-1].replace(",", ""))


def extract_proof_steps(text: str):
    vals = PROOF_RE.findall(text)
    if not vals:
        return None
    return int(vals[-1].replace(",", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--total-budget", type=int, default=9000)
    ap.add_argument("--pass-budget", type=int, default=3000)
    ap.add_argument("--max-passes", type=int, default=3)
    ap.add_argument("--initial-width", type=int, default=2)
    ap.add_argument("--initial-macro-extra", type=int, default=2)
    ap.add_argument("--max-width", type=int, default=16)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--max-open", type=int, default=8)
    ap.add_argument("--creativity", type=float, default=0.55)
    ap.add_argument("--opener-cap", type=int, default=160)
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--frontier-limit", type=int, default=120000)
    ap.add_argument("--probe-depth", type=int, default=3)
    ap.add_argument("--probe-cap", type=int, default=2000)
    ap.add_argument("--probe-total-cap", type=int, default=4000)
    ap.add_argument("--probe-next-layer", type=int, default=30000)
    ap.add_argument("--out", default="prcom_p8_031.mm")
    a = ap.parse_args()

    if a.total_budget < 1 or a.pass_budget < 1 or a.max_passes < 1:
        ap.error("budgets and max-passes must be positive")
    if a.initial_width < 1 or a.max_width < a.initial_width:
        ap.error("invalid structural-width range")
    if a.initial_macro_extra not in (0, 1, 2):
        ap.error("initial-macro-extra must be 0, 1, or 2")

    final_out = Path(a.out).resolve()
    stem = final_out.with_suffix("")
    width = a.initial_width
    macro_extra = a.initial_macro_extra
    cumulative = 0
    records = []
    started = time.perf_counter()

    print("=" * 78)
    print("Predator 8.031 error-conditioned refinement -- %s -- seed=%d" %
          (a.label, a.seed))
    print("initial D=%d macro_extra=%d total_budget=%s max_passes=%d" %
          (width, macro_extra, f"{a.total_budget:,}", a.max_passes))
    print("=" * 78)

    verified = False
    final_steps = None

    for pass_ix in range(1, a.max_passes + 1):
        remaining = a.total_budget - cumulative
        if remaining <= 0:
            print("[REFINE] total expansion budget exhausted before pass %d" % pass_ix)
            break
        this_budget = min(a.pass_budget, remaining)
        pass_out = Path("%s.pass%d.D%d.M%d.mm" %
                        (stem, pass_ix, width, macro_extra))

        print("[REFINE] PASS %d start: D=%d macro_extra=%d pass_budget=%s cumulative=%s" %
              (pass_ix, width, macro_extra, f"{this_budget:,}", f"{cumulative:,}"))

        cmd = [
            sys.executable, str(ENTRY),
            "--structural-width", str(width),
            "--macro-max-extra", str(macro_extra),
            str(Path(a.environment).resolve()),
            "--engine", str(Path(a.engine).resolve()),
            "--model", str(Path(a.model).resolve()),
            "--label", a.label,
            "--budget", str(this_budget),
            "--brute-reserve", "0",
            "--max-depth", str(a.max_depth),
            "--max-open", str(a.max_open),
            "--seed", str(a.seed),
            "--creativity", str(a.creativity),
            "--opener-cap", str(a.opener_cap),
            "--progress", str(a.progress),
            "--frontier-limit", str(a.frontier_limit),
            "--probe-depth", str(a.probe_depth),
            "--probe-cap", str(a.probe_cap),
            "--probe-total-cap", str(a.probe_total_cap),
            "--probe-next-layer", str(a.probe_next_layer),
            "--out", str(pass_out),
        ]

        proc = subprocess.Popen(
            cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        lines = []
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line)
            print("[P%d] %s" % (pass_ix, line.rstrip()))
        rc = proc.wait()
        text = "".join(lines)
        used = extract_total(text)
        # If a crash occurred before CONTROL SUMMARY, conservatively charge the
        # full pass budget rather than silently making a failed pass free.
        charged = used if used > 0 else this_budget
        cumulative += charged
        kind = classify(text, rc)
        steps = extract_proof_steps(text)

        rec = {
            "pass": pass_ix,
            "width": width,
            "macro_extra": macro_extra,
            "budget": this_budget,
            "expansions_charged": charged,
            "cumulative_expansions": cumulative,
            "returncode": rc,
            "classification": kind,
            "proof_steps": steps,
            "candidate": str(pass_out),
        }
        records.append(rec)
        print("[REFINE] PASS %d result=%s charged=%s cumulative=%s" %
              (pass_ix, kind, f"{charged:,}", f"{cumulative:,}"))

        if kind == "VERIFIED" and pass_out.exists():
            shutil.copyfile(pass_out, final_out)
            verified = True
            final_steps = steps
            print("[REFINE] VERIFIED: refinement halts; final certificate=%s" % final_out)
            break

        new_width, new_macro, action = next_parameters(
            kind, width, macro_extra, a.max_width)
        print("[REFINE] diagnosis=%s -> action=%s -> D %d->%d, macro_extra %d->%d" %
              (kind, action, width, new_width, macro_extra, new_macro))
        if new_width == width and new_macro == macro_extra:
            print("[REFINE] no further parameter change available; halting")
            break
        width, macro_extra = new_width, new_macro

    elapsed = time.perf_counter() - started
    summary_path = Path(str(stem) + ".refinement.json")
    summary = {
        "version": "8.031",
        "seed": a.seed,
        "verified": verified,
        "final_proof_steps": final_steps,
        "cumulative_expansions": cumulative,
        "elapsed_seconds": elapsed,
        "records": records,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("REFINEMENT SUMMARY: verified=%s cumulative_expansions=%s passes=%d elapsed=%.1fs" %
          ("YES" if verified else "NO", f"{cumulative:,}", len(records), elapsed))
    if verified:
        if final_steps is not None:
            print("REFINEMENT PROOF STEPS: %d" % final_steps)
        print("OUTCOME: VERIFIED PROOF AFTER ERROR-CONDITIONED REFINEMENT")
        return 0
    print("OUTCOME: UNKNOWN AFTER ERROR-CONDITIONED REFINEMENT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
