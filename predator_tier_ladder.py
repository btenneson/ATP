#!/usr/bin/env python3
"""
predator_tier_ladder.py
=======================

Tiered benchmark harness for Predator 7.1 on set.mm.

Answers one question: *what tier is Predator 7.1?* — where the prover is rated
tier N if there exists a tier-N target it genuinely proves.

The ladder is the dep/position calibration table from Predator 7.1
Documentation, Part III Section 15.4, ordered by dependency count.  Two extra
tracks bracket it:

  T0   a known duplicate-lookup target.  Should be SCREENED OUT.  If it is not,
       the screening is broken and every result below it is worthless.
  X1/X2 the out-of-distribution infinitesimals suite.  Reported separately and
       never folded into the tier verdict.

Screening implements Definition 5.2 (admissible index): exclude any label whose
conclusion is a substitution instance of the target, or of which the target is a
substitution instance, under variable renaming.  Excluding only exact duplicates
is not enough — falanfal survives that test.

Usage
-----
    python predator_tier_ladder.py --dry-run       # exercise the flow, no prover
    python predator_tier_ladder.py                 # real run, interactive
    python predator_tier_ladder.py --auto          # real run, no pauses
    python predator_tier_ladder.py --from T4       # resume partway up
    python predator_tier_ladder.py --budget 500000

Configure the four paths in CONFIG before a real run.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------
# CONFIG — edit these four for a real run
# --------------------------------------------------------------------------

CONFIG = {
    "setmm":     "set.mm",
    "predator":  "predator71.py",
    "verifier":  "metamath_cv.py",
    "workdir":   "runs",

    # Command templates.  {target} {setmm} {budget} {out} are substituted.
    "predator_cmd": "python {predator} --db {setmm} --target {target} "
                    "--budget {budget} --emit {out}",
    "verify_cmd":   "python {verifier} {out}",

    "budget": 200_000,          # expansions, not seconds
    "timeout_s": 3600,
}

# Regexes for pulling stats out of prover/verifier output.  Adjust to match
# whatever predator71.py actually prints.
PATTERNS = {
    "expansions":   re.compile(r"expansions[:=]\s*(\d+)", re.I),
    "raw_steps":    re.compile(r"raw[ _]steps[:=]\s*(\d+)", re.I),
    "logical_steps": re.compile(r"logical[ _]steps[:=]\s*(\d+)", re.I),
    "cv_ok":        re.compile(r"(\d+)\s+verified,\s*0\s+failed", re.I),
    "cv_fail":      re.compile(r"(\d+)\s+failed", re.I),
}


# --------------------------------------------------------------------------
# The ladder
# --------------------------------------------------------------------------

@dataclass
class Target:
    tier: str
    label: str
    pos: Optional[int]
    dep: Optional[int]
    regime: str
    note: str
    track: str = "main"          # "main" | "control" | "ood"
    expect: str = "unknown"


LADDER: list[Target] = [
    Target("T0", "axin1", None, None, "retrieval",
           "Known duplicate-lookup from Section 5. MUST be screened out — "
           "this target tests the screening, not the prover.",
           track="control", expect="screened"),

    Target("T1", "pm2.01", 189, 37, "deterministic",
           "Propositional. Harness check. Failure here means the rig is broken.",
           expect="pass"),

    Target("T2", "simpl", 486, 44, "deterministic",
           "Propositional, slightly deeper.", expect="pass"),

    Target("T3", "falim", 1584, 80, "deterministic",
           "End of the propositional region.", expect="pass"),

    Target("T4", "sbth", 9083, 1299, "witness-requiring",
           "Cantor-Schroeder-Bernstein. Needs a fixed-point construction.",
           expect="fail"),

    Target("T5", "canth2", 9116, 1608, "witness-requiring",
           "Cantor. The diagonal set is a witness you invent, not a rule you apply.",
           expect="fail"),

    Target("T6", "zorn", 10489, 2707, "witness-requiring",
           "Zorn. Chain construction.", expect="fail"),

    Target("T7", "ruc", 16297, 3585, "search-hard",
           "Uncountability of the reals.", expect="fail"),

    Target("T8", "sqrt2irr", 16303, 3914, "search-hard",
           "THE DISCRIMINATING TARGET. Short logical proof, enormous applicable "
           "lemma pool at this position. Check hard for an ALT sibling.",
           expect="fail"),

    Target("T9", "pythag", 26957, 7568, "deep chain",
           "Pythagorean theorem.", expect="fail"),

    Target("T10", "fta", 27219, 7839, "deep chain",
           "Fundamental theorem of algebra.", expect="fail"),

    Target("T11", "bpos", 27432, 8271, "deep chain",
           "Bertrand's postulate. Ceiling probe.", expect="fail"),

    Target("X1", "infml-A3", None, None, "ood-retrieval",
           "|Infml| = |RR|. Standard proof, novel vocabulary. "
           "Contamination risk: one sbth application from a common shape.",
           track="ood", expect="pass"),

    Target("X2", "infml-B4", None, None, "ood-order",
           "Infml = t*RR[t]. Requires reasoning inside an order the prover has "
           "never seen. The real out-of-distribution test.",
           track="ood", expect="fail"),
]


# --------------------------------------------------------------------------
# Screening — Definition 5.2
# --------------------------------------------------------------------------

VAR_RE = re.compile(r"\b(ph|ps|ch|th|ta|et|ze|si|rh|mu|la|ka|[A-Z])\b")


def normalise(stmt: str) -> str:
    """Collapse whitespace and rename every variable to a positional slot, so
    two statements alpha-equivalent under renaming normalise identically."""
    toks = stmt.split()
    mapping: dict[str, str] = {}
    out = []
    for t in toks:
        if VAR_RE.fullmatch(t):
            if t not in mapping:
                mapping[t] = f"?{len(mapping)}"
            out.append(mapping[t])
        else:
            out.append(t)
    return " ".join(out)


def load_assertions(setmm_path: Path) -> list[tuple[str, str, int]]:
    """Return (label, conclusion, ordinal_position) for every $p/$a in set.mm.

    Deliberately crude: a real implementation should use setmm_grammar.py.
    This is enough to catch exact and alpha-renamed duplicates.
    """
    if not setmm_path.exists():
        return []
    text = setmm_path.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"^\s*(\S+)\s+\$([pa])\s+(.*?)\s*\$[.=]", re.M | re.S)
    out = []
    for i, m in enumerate(pat.finditer(text)):
        out.append((m.group(1), " ".join(m.group(3).split()), i))
    return out


def screen(target: Target, assertions: list[tuple[str, str, int]]) -> list[str]:
    """Return a list of screening violations. Empty list means admissible."""
    violations = []

    # C-ALT: any label sharing the name with an ALT/OLD suffix
    siblings = [lab for lab, _, _ in assertions
                if lab != target.label
                and (lab == target.label + "ALT"
                     or lab == target.label + "OLD"
                     or lab.startswith(target.label + "ALT"))]
    if siblings:
        violations.append(f"ALT/OLD sibling(s) present: {', '.join(siblings[:5])}")

    # C1/C2: exact or alpha-renamed conclusion duplicate at lower position
    own = [(lab, con, p) for lab, con, p in assertions if lab == target.label]
    if own:
        _, own_con, own_pos = own[0]
        key = normalise(own_con)
        dups = [lab for lab, con, p in assertions
                if p < own_pos and normalise(con) == key]
        if dups:
            violations.append(
                f"conclusion duplicated at lower position by: {', '.join(dups[:5])}")

    # C3 hook: substitution-instance check in both directions.  Requires a real
    # matcher; wire setmm_grammar.py in here before trusting a clean result.
    # Left explicit rather than silently skipped.
    return violations


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

@dataclass
class Result:
    tier: str
    label: str
    outcome: str = "not-run"      # proved | failed | screened | error
    screened: list[str] = field(default_factory=list)
    expansions: Optional[int] = None
    budget: Optional[int] = None
    raw_steps: Optional[int] = None
    logical_steps: Optional[int] = None
    wall_s: Optional[float] = None
    cv_verdict: str = "n/a"
    horizon_ratio: Optional[float] = None
    note: str = ""


def grab(pattern: re.Pattern, text: str) -> Optional[int]:
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def run_real(target: Target, budget: int, workdir: Path) -> Result:
    r = Result(tier=target.tier, label=target.label, budget=budget)
    out = workdir / f"{target.label}_p71.mm"

    cmd = CONFIG["predator_cmd"].format(
        predator=CONFIG["predator"], setmm=CONFIG["setmm"],
        target=target.label, budget=budget, out=out)
    t0 = time.time()
    try:
        proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True,
                              timeout=CONFIG["timeout_s"])
    except FileNotFoundError as e:
        r.outcome, r.note = "error", f"prover not found: {e}"
        return r
    except subprocess.TimeoutExpired:
        r.outcome, r.wall_s = "failed", time.time() - t0
        r.note = "prover timeout"
        return r
    r.wall_s = round(time.time() - t0, 1)

    blob = proc.stdout + proc.stderr
    r.expansions = grab(PATTERNS["expansions"], blob)
    r.raw_steps = grab(PATTERNS["raw_steps"], blob)
    r.logical_steps = grab(PATTERNS["logical_steps"], blob)

    if not out.exists():
        r.outcome = "failed"
        r.note = "no certificate emitted"
        return r

    vcmd = CONFIG["verify_cmd"].format(verifier=CONFIG["verifier"], out=out)
    try:
        vproc = subprocess.run(shlex.split(vcmd), capture_output=True, text=True,
                               timeout=CONFIG["timeout_s"])
    except Exception as e:                                  # noqa: BLE001
        r.outcome, r.note = "error", f"verifier failed to run: {e}"
        return r

    vblob = vproc.stdout + vproc.stderr
    if PATTERNS["cv_ok"].search(vblob):
        r.outcome, r.cv_verdict = "proved", "CV: verified, 0 failed"
    else:
        m = PATTERNS["cv_fail"].search(vblob)
        r.outcome = "failed"
        r.cv_verdict = f"CV REJECTED ({m.group(1)} failed)" if m else "CV: unparsed"

    if r.expansions and r.logical_steps:
        r.horizon_ratio = round(r.expansions / r.logical_steps, 2)
    return r


def run_dry(target: Target, budget: int) -> Result:
    """Simulate, so the flow can be exercised without the prover."""
    r = Result(tier=target.tier, label=target.label, budget=budget)
    time.sleep(0.25)
    proved = target.expect == "pass"
    r.outcome = "proved" if proved else "failed"
    r.wall_s = round(random.uniform(2, 90), 1)
    if proved:
        r.logical_steps = random.randint(4, 30)
        r.raw_steps = int(r.logical_steps * random.uniform(12, 22))
        r.expansions = random.randint(50, budget // 4)
        r.cv_verdict = "CV: verified, 0 failed  [SIMULATED]"
        r.horizon_ratio = round(r.expansions / r.logical_steps, 2)
    else:
        r.expansions = budget
        r.note = "budget exhausted  [SIMULATED]"
    return r


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------

BAR = "=" * 74


def show_upcoming(t: Target) -> None:
    print(f"\n{BAR}\n  NEXT: {t.tier}   {t.label}\n{BAR}")
    print(f"  track        {t.track}")
    if t.pos is not None:
        print(f"  position     {t.pos:,}")
        print(f"  dep          {t.dep:,}")
    print(f"  regime       {t.regime}")
    print(f"  expectation  {t.expect}")
    print(f"\n  {t.note}\n")


def show_result(r: Result, t: Target) -> None:
    tag = {"proved": "PASS", "failed": "FAIL",
           "screened": "SCREENED OUT", "error": "ERROR"}[r.outcome]
    print(f"\n  ----- {t.tier} {t.label}: {tag} -----")
    if r.screened:
        for v in r.screened:
            print(f"    ! {v}")
    rows = [
        ("outcome", tag),
        ("wall time", f"{r.wall_s}s" if r.wall_s else "-"),
        ("expansions", f"{r.expansions:,} / {r.budget:,}"
                       if r.expansions and r.budget else "-"),
        ("logical steps", r.logical_steps or "-"),
        ("raw steps", r.raw_steps or "-"),
        ("raw/logical", round(r.raw_steps / r.logical_steps, 1)
                        if r.raw_steps and r.logical_steps else "-"),
        ("horizon ratio", r.horizon_ratio if r.horizon_ratio else "-"),
        ("verifier", r.cv_verdict),
    ]
    for k, v in rows:
        print(f"    {k:<16}{v}")
    if r.note:
        print(f"    note            {r.note}")

    if r.outcome == "proved" and t.expect == "screened":
        print("\n    *** SCREENING FAILURE: a known duplicate-lookup target was")
        print("        proved rather than screened out. Every result below this")
        print("        line is uninterpretable until the screening is fixed. ***")


def verdict(results: list[Result]) -> None:
    main = [r for r in results if r.tier.startswith("T") and r.tier != "T0"]
    passed = [r for r in main if r.outcome == "proved" and not r.screened]
    print(f"\n{BAR}\n  VERDICT\n{BAR}")
    if passed:
        top = max(passed, key=lambda r: int(r.tier[1:]))
        print(f"\n  Predator 7.1 is TIER {top.tier[1:]}.")
        print(f"  Highest genuine pass: {top.tier} {top.label}")
    else:
        print("\n  Predator 7.1 is TIER 0 — no genuine pass on the main ladder.")

    print("\n  Main ladder:")
    for r in main:
        mark = {"proved": "+", "failed": ".", "screened": "x", "error": "!",
                "not-run": " "}[r.outcome]
        print(f"    [{mark}] {r.tier:<4}{r.label:<12}{r.outcome}")

    ood = [r for r in results if r.tier.startswith("X")]
    if ood:
        print("\n  Out-of-distribution track (NOT part of the tier rating):")
        for r in ood:
            mark = {"proved": "+", "failed": ".", "screened": "x",
                    "error": "!", "not-run": " "}[r.outcome]
            print(f"    [{mark}] {r.tier:<4}{r.label:<12}{r.outcome}")

    t0 = next((r for r in results if r.tier == "T0"), None)
    if t0 and t0.outcome == "proved":
        print("\n  WARNING: T0 control was proved, not screened. Rating is void.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="simulate outcomes; no prover needed")
    ap.add_argument("--auto", action="store_true", help="do not pause between targets")
    ap.add_argument("--budget", type=int, default=CONFIG["budget"])
    ap.add_argument("--from", dest="start", default=None,
                    help="resume at a tier, e.g. T4")
    ap.add_argument("--skip-screen", action="store_true",
                    help="run targets even if screening rejects them (unsound)")
    args = ap.parse_args()

    workdir = Path(CONFIG["workdir"])
    workdir.mkdir(exist_ok=True)

    assertions = [] if args.dry_run else load_assertions(Path(CONFIG["setmm"]))
    if not args.dry_run and not assertions:
        print(f"WARNING: could not read {CONFIG['setmm']} — screening disabled.\n"
              f"         Results will not be trustworthy.")

    ladder = LADDER
    if args.start:
        idx = next((i for i, t in enumerate(ladder) if t.tier == args.start), 0)
        ladder = ladder[idx:]

    print(f"\n{BAR}")
    print("  PREDATOR 7.1 TIER LADDER")
    print(f"  budget {args.budget:,} expansions   "
          f"{'DRY RUN' if args.dry_run else 'LIVE'}   {len(ladder)} targets")
    print(BAR)

    results: list[Result] = []
    for i, t in enumerate(ladder):
        show_upcoming(t)

        if not args.auto:
            ans = input("  Proceed?  [y] yes  [s] skip  [q] quit : ").strip().lower()
            if ans == "q":
                print("\n  Stopped by user.")
                break
            if ans == "s":
                results.append(Result(tier=t.tier, label=t.label, outcome="not-run",
                                      note="skipped by user"))
                continue

        if args.dry_run:
            # Simulate the screening so the T0 control demonstrates its purpose.
            violations = (["ALT/OLD sibling(s) present: axin1ALT  [SIMULATED]"]
                          if t.expect == "screened" else [])
        elif not assertions:
            violations = []
        else:
            violations = screen(t, assertions)
        if violations and not args.skip_screen:
            r = Result(tier=t.tier, label=t.label, outcome="screened",
                       screened=violations,
                       note="excluded by Definition 5.2 admissible index")
            results.append(r)
            show_result(r, t)
            continue

        print(f"  running {t.label} ...")
        r = run_dry(t, args.budget) if args.dry_run else run_real(t, args.budget, workdir)
        r.screened = violations
        results.append(r)
        show_result(r, t)

        # running rating
        so_far = [x for x in results
                  if x.tier.startswith("T") and x.tier != "T0"
                  and x.outcome == "proved" and not x.screened]
        if so_far:
            top = max(so_far, key=lambda x: int(x.tier[1:]))
            print(f"\n    running rating: TIER {top.tier[1:]}")
        else:
            print("\n    running rating: TIER 0")

    verdict(results)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    log = workdir / f"ladder-{stamp}.json"
    log.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"\n  results written to {log}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
