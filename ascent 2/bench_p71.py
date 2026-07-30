#!/usr/bin/env python3
r"""
bench_p71.py -- chronological-prefix benchmark for Predator_7.1.

Measures search power against ground-truth proof difficulty, base-relative.

PROTOCOL
--------
For target theorem t at position i in the database order:

    1. Build an index over mm.order[:i] ONLY.  The prover may use every
       assertion the human author had available at that point and nothing
       later.  This is the `upto=` argument Predator's cmd_prove already
       uses; here it is applied systematically.
    2. Attempt t across a grid of (budget, max_depth).
    3. Any proof found is emitted as a Metamath certificate and handed to
       metamath.py -- the CV -- which knows nothing about how it was found.
    4. Record the outcome, the cost, and WHICH resource ran out.

The independent variable is the number of LOGICAL steps in the human proof
of t (metamath.classify separates |- steps from formula construction, which
is ~95% of raw proof length).  That is a base-relative difficulty measure
with ground truth, so solve-rate-versus-logical-depth is a strength curve
rather than a single number that only means something on one benchmark.

CAUSE ATTRIBUTION
-----------------
prove() returns (None, exp).  Two failures look alike and are not:

    exp > budget      budget-bound   -- frontier still had nodes
    exp <= budget     exhausted      -- frontier emptied; no route exists
                                        within max_depth, so more budget
                                        cannot help
    timeout           wall-bound     -- neither limit reached in time

Distinguishing these is the whole point of the sweep.  A prover that is
"exhausted" at depth 6 and still exhausted at depth 12 has no route at all.

THE LEMMA-AVAILABILITY CONFOUND
-------------------------------
Solve rate under a chronological prefix is NOT a pure search measure.  If
the database already contains a theorem that unifies with the goal, the
prover closes it in one step and scores a solve without doing any
reasoning.  Two columns separate that from real search:

    found_logic_steps   |- steps in PREDATOR's proof
    human_logic_steps   |- steps in the human proof

A 2-expansion solve of an 11-step human theorem means a shortcut lemma was
sitting in the base, not that the prover reconstructed 11 steps.  Report
the ratio, not just the rate.

--base-mode axioms runs the ablation: index ONLY the primitive assertions,
withholding every derived lemma.  That is the pure search condition and it
is where the real ceiling shows up.

WHAT THIS DOES NOT MEASURE
--------------------------
Certificate power.  Predator emits Frege-style proofs and is as strong as
its base allows on that axis; the ceiling found here is a SEARCH ceiling.
The two are independent and both belong in a report.

    python bench_p71.py --db set.mm --out results
    python bench_p71.py --db set.mm --out results_abl --base-mode axioms
    python bench_p71.py --db fixture.mm --out results --max-logic 4

Brian Tenneson.  Harness by Claude (Anthropic).
"""
from __future__ import annotations
import argparse, csv, json, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.setrecursionlimit(20000)

from metamath import MM, Toks, load, MMError, classify          # noqa: E402
import setmm_grammar as G                                        # noqa: E402
import predator71 as P                                           # noqa: E402


class Deadline(Exception):
    pass


class IncIndex(P.Index):
    """Predator's Index, built incrementally.

    Index(upto=i) reparses every conclusion before i.  Running the whole
    sweep that way is quadratic.  Assertions only ever get APPENDED as the
    cut advances, so the same structure can be grown in order -- one pass
    over the database for the entire benchmark instead of one pass per
    target.  The candidates() logic is inherited untouched."""

    def __init__(self, mm, by_tc):
        self.mm = mm
        self.by_tc = by_tc
        self.closers = defaultdict(list)
        self.openers = defaultdict(list)
        self.n = 0
        self.pos = 0
        self.unparsed = 0

    def advance_to(self, cut):
        for lab in self.mm.order[self.pos:cut]:
            typ, data = self.mm.labels[lab]
            if typ not in ("$a", "$p"):
                continue
            concl = data[3]
            if not concl or concl[0] != "|-" or len(concl) < 2:
                continue
            try:
                t = G.parse(concl[1:], "wff", self.by_tc)
            except (RecursionError, MMError):
                t = None
            if t is None:
                self.unparsed += 1
                continue
            self.n += 1
            head = None if t.var is not None else t.label
            (self.closers if not data[2] else self.openers)[head].append(
                (lab, t, data))
        self.pos = cut


r"""
A NOTE ON TARGETS WITH $e HYPOTHESES -- and how the CV caught a bad harness
--------------------------------------------------------------------------
An earlier version of this file targeted the bare CONCLUSION of theorems
like a1i (ph |- ( ps -> ph )).  That conclusion is not a theorem, so the
prover was being handed unprovable goals and scored for failing them.

The obvious repair -- adjoin each $e hypothesis to the index as a closer --
is WRONG, and instructively so.  Predator renames every candidate's
variables apart at each use, which turns the hypothesis into a schema: `ph`
becomes universally quantified and unifies with anything.  Under that
repair the harness reported 8/8 solved.  metamath.py rejected 7 of the 8
certificates with "proved the wrong statement," because a hypothesis's
variables are FIXED for the duration of the proof, not schematic.

The score went from 1/6 to a false 8/8 and the CV was the only thing that
noticed.  That is the ATP/CV split earning its keep, and it is the reason
the soundness column is reported alongside every solve rate here.

Targets are therefore restricted to CLOSED theorems -- no $e hypotheses --
where the conclusion alone is the whole claim.
"""


def logic_depth(mm, kind, lab):
    """Number of |- steps in the human proof.  None if unmeasurable."""
    try:
        proof = mm.decompress(lab, mm.proofs[lab])
    except (MMError, RecursionError, ValueError, KeyError):
        return None
    if "?" in proof:
        return None
    return sum(1 for st in proof if kind.get(st) == "logic")


def attempt(gt, idx, budget, depth, wall):
    """One (budget, depth) attempt with a wall-clock cap.

    prove() calls say() every `progress` expansions and has no timeout of
    its own; raising from say() is a non-invasive deadline that leaves the
    prover source untouched."""
    t_end = time.perf_counter() + wall

    def tick(_msg):
        if time.perf_counter() > t_end:
            raise Deadline()

    t0 = time.perf_counter()
    try:
        # progress=5: say() is the only deadline hook prove() offers, and on
        # set.mm a single expansion can take milliseconds, so checking every
        # 200 expansions overshoots the wall badly.
        res, exp = P.prove(gt, idx, budget, depth,
                           say=tick, progress=5)
        dt = time.perf_counter() - t0
        if res is not None:
            return "proved", res, exp, dt
        return ("budget" if exp > budget else "exhausted"), None, exp, dt
    except Deadline:
        return "timeout", None, -1, time.perf_counter() - t0
    except RecursionError:
        return "recursion", None, -1, time.perf_counter() - t0


def certify(mm, lab, stat, proof):
    """Hand the certificate to the CV.  Returns 'ok' or an error string."""
    try:
        chk = MM()
        chk.labels = dict(mm.labels)
        chk.order = list(mm.order)
        chk.proofs = dict(mm.proofs)
        chk.constants, chk.variables = mm.constants, mm.variables
        chk.scope_dvs = dict(mm.scope_dvs)
        dvs, f_hyps, e_hyps, _ = mm.labels[lab][1]
        chk.labels["__chk__"] = ("$p", (dvs, f_hyps, e_hyps, stat))
        chk.proofs["__chk__"] = proof
        chk.scope_dvs["__chk__"] = mm.scope_dvs.get(lab, dvs)
        return chk.verify("__chk__")
    except MMError as e:
        return "MMError: %s" % e
    except RecursionError:
        return "RecursionError"


def run(a):
    print("=" * 74)
    print("  Predator_7.1 -- chronological-prefix benchmark")
    print("=" * 74)

    # NB: only mm is cached.  build_grammar populates module-level state in
    # setmm_grammar that a pickled by_tc does not carry, and a restored one
    # silently fails every parse.  Rebuilding costs 0.1s.
    if a.cache and os.path.exists(a.cache):
        import pickle
        t0 = time.time()
        with open(a.cache, "rb") as f:
            mm = pickle.load(f)
        print("  cache %s loaded in %.1fs" % (a.cache, time.time() - t0))
    else:
        mm = load(a.db, say=lambda s: print("  " + s))
        if a.cache:
            import pickle
            with open(a.cache, "wb") as f:
                pickle.dump(mm, f, protocol=5)
            print("  cached to %s" % a.cache)
    by_tc = G.build_grammar(mm)
    kind = classify(mm)

    fvar, fallback = {}, {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar.setdefault(d[1], lab)
            fallback.setdefault(d[0], G.Tree(None, d[0], (), d[1]))

    # ---- select targets, stratified by human logical-proof length --------
    thms = [l for l in mm.order if mm.labels[l][0] == "$p"]
    if a.scan:
        thms = thms[:a.scan]

    tc = a.targets_cache
    if tc and os.path.exists(tc):
        import pickle
        with open(tc, "rb") as f:
            targets, by_depth = pickle.load(f)
        print("\n  target list from cache: %d targets" % len(targets))
    else:
        print("\n  measuring human proofs of %s theorems..."
              % f"{len(thms):,}")
        by_depth = defaultdict(list)
        nskip = 0
        for i, lab in enumerate(thms, 1):
            if mm.labels[lab][1][2]:          # has $e hypotheses
                nskip += 1
                continue
            d = logic_depth(mm, kind, lab)
            if d is not None and 1 <= d <= a.max_logic:
                by_depth[d].append(lab)
            if a.progress and i % a.progress == 0:
                print("    %s/%s" % (f"{i:,}", f"{len(thms):,}"))
        targets = []
        for d in sorted(by_depth):
            picked = by_depth[d][:a.per_depth]
            targets.extend(picked)
            print("    logic depth %d: %s available, %d sampled"
                  % (d, f"{len(by_depth[d]):,}", len(picked)))
        pos = {l: i for i, l in enumerate(mm.order)}
        targets.sort(key=lambda l: pos[l])
        by_depth = {k: len(v) for k, v in by_depth.items()}
        if tc:
            import pickle
            with open(tc, "wb") as f:
                pickle.dump((targets, by_depth), f, protocol=5)
    if a.chunk:
        targets = targets[a.chunk[0]:a.chunk[1]]
        print("  chunk %d:%d -> %d targets" % (a.chunk[0], a.chunk[1],
                                               len(targets)))
    print("\n  %d targets\n" % len(targets))
    if not targets:
        print("  nothing to do.")
        return 1

    grid = [(b, d) for d in a.depths for b in a.budgets]
    idx = IncIndex(mm, by_tc)
    rows = []
    bad_certs = 0

    # ablation: freeze the index at the primitive assertions only
    if a.base_mode == "axioms":
        first_thm = min((mm.order.index(l) for l in thms), default=len(mm.order))
        idx.advance_to(first_thm)
        print("  ABLATION: base frozen at %s primitive assertions "
              "(no derived lemmas)\n" % f"{idx.n:,}")

    posn = {l: i for i, l in enumerate(mm.order)}
    for tn, lab in enumerate(targets, 1):
        cut = posn[lab]
        if a.base_mode == "prefix":
            idx.advance_to(cut)
        stat = mm.labels[lab][1][3]
        hd = logic_depth(mm, kind, lab)
        try:
            gt = G.parse(stat[1:], "wff", by_tc)
        except (RecursionError, MMError):
            gt = None
        if gt is None:
            print("  [%d/%d] %-14s goal does not parse -- skipped"
                  % (tn, len(targets), lab))
            continue

        print("  [%d/%d] %-14s human logic steps %-3d base %s assertions"
              % (tn, len(targets), lab, hd, f"{idx.n:,}"))

        solved_at = None
        for budget, depth in grid:
            P._counter = __import__("itertools").count(1)   # fresh metavars
            out, res, exp, dt = attempt(gt, idx, budget, depth, a.wall)
            verdict, nsteps, flogic = "", "", ""
            if out == "proved":
                root, sub = res
                try:
                    proof = root.emit(sub, fvar, fallback)
                    verdict = certify(mm, lab, stat, proof)
                    nsteps = len(proof)
                    flogic = sum(1 for st in proof if kind.get(st) == "logic")
                    if verdict != "ok":
                        bad_certs += 1
                except MMError as e:
                    verdict = "emit failed: %s" % e
            rows.append(dict(
                label=lab, human_logic_steps=hd,
                found_logic_steps=flogic, base_size=idx.n,
                base_mode=a.base_mode,
                budget=budget, max_depth=depth, outcome=out,
                expansions=exp, seconds=round(dt, 3),
                cv_verdict=verdict, proof_steps=nsteps))
            flag = {"proved": "PROVED", "budget": "budget-bound",
                    "exhausted": "exhausted", "timeout": "wall",
                    "recursion": "recursion"}[out]
            print("        b=%-6s d=%-3d %-13s %8s exp  %6.1fs  %s%s"
                  % (f"{budget:,}", depth, flag,
                     f"{exp:,}" if exp >= 0 else "-", dt,
                     ("CV:" + verdict) if verdict else "",
                     ("  found %s logic steps vs human %s"
                      % (flogic, hd)) if flogic != "" else ""))
            if out == "proved":
                solved_at = (budget, depth, exp)
                break            # cheapest setting that works; stop sweeping
        if solved_at:
            print("        -> solved at budget %s depth %d, %s expansions"
                  % (f"{solved_at[0]:,}", solved_at[1], f"{solved_at[2]:,}"))
        print()

    # ---- write results ---------------------------------------------------
    os.makedirs(a.out, exist_ok=True)
    csv_path = os.path.join(a.out, "p71_runs.csv")
    exists = os.path.exists(csv_path) and a.chunk
    with open(csv_path, "a" if exists else "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not exists:
            w.writeheader()
        w.writerows(rows)

    solved = {r["label"] for r in rows if r["outcome"] == "proved"}
    attempted = {r["label"] for r in rows}
    per_depth = defaultdict(lambda: [0, 0])
    seen = set()
    for r in rows:
        if r["label"] in seen:
            continue
        seen.add(r["label"])
        per_depth[r["human_logic_steps"]][1] += 1
        if r["label"] in solved:
            per_depth[r["human_logic_steps"]][0] += 1

    threshold = 0
    for d in sorted(per_depth):
        got, tot = per_depth[d]
        if got == tot:
            threshold = d
        else:
            break

    # how many "solves" were really one-step lemma lookups?
    wins = [r for r in rows if r["outcome"] == "proved"]
    shortcut = sum(1 for r in wins
                   if r["found_logic_steps"] != ""
                   and r["found_logic_steps"] < r["human_logic_steps"])
    onestep = sum(1 for r in wins if r["found_logic_steps"] == 1)

    summary = dict(
        database=a.db,
        base_mode=a.base_mode,
        targets=len(attempted),
        solved=len(solved),
        solve_rate=round(len(solved) / max(1, len(attempted)), 4),
        certificates_emitted=sum(1 for r in rows if r["proof_steps"] != ""),
        cv_rejections=bad_certs,
        solves_shorter_than_human=shortcut,
        solves_in_one_logic_step=onestep,
        completeness_threshold_logic_steps=threshold,
        by_logic_depth={str(d): dict(solved=per_depth[d][0],
                                     targets=per_depth[d][1])
                        for d in sorted(per_depth)},
        grid=dict(budgets=a.budgets, depths=a.depths, wall_seconds=a.wall),
    )
    with open(os.path.join(a.out, "p71_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("=" * 74)
    print("  base mode  %s" % a.base_mode)
    print("  solved     %d/%d   CV rejections %d"
          % (len(solved), len(attempted), bad_certs))
    print("  of those,  %d found a proof SHORTER than the human's "
          "(%d in a single logic step)" % (shortcut, onestep))
    print("  completeness threshold: every target at <= %d human logic steps"
          % threshold)
    print("  wrote %s" % csv_path)
    print("=" * 74)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="set.mm")
    ap.add_argument("--out", default="results")
    ap.add_argument("--scan", type=int, default=4000,
                    help="only consider the first N theorems")
    ap.add_argument("--max-logic", type=int, default=6,
                    help="highest human logical-step count to target")
    ap.add_argument("--per-depth", type=int, default=12,
                    help="targets sampled at each logical depth")
    ap.add_argument("--budgets", type=int, nargs="+",
                    default=[1000, 5000, 20000, 60000])
    ap.add_argument("--depths", type=int, nargs="+", default=[6, 12])
    ap.add_argument("--base-mode", choices=["prefix", "axioms"],
                    default="prefix",
                    help="prefix: every assertion before the target. "
                         "axioms: primitives only, no derived lemmas.")
    ap.add_argument("--wall", type=float, default=120.0,
                    help="wall-clock cap per attempt, seconds")
    ap.add_argument("--progress", type=int, default=1000)
    ap.add_argument("--cache", default=None,
                    help="pickle of (mm, by_tc); written if absent")
    ap.add_argument("--targets-cache", default=None,
                    help="pickle of the stratified target list")
    ap.add_argument("--chunk", type=int, nargs=2, default=None,
                    metavar=("START", "END"),
                    help="run only targets[START:END]")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(P._big_stack(main) or 0)
