#!/usr/bin/env python3
r"""
named_ladder.py -- Predator_7.1 against the classical propositional ladder,
from ax-1/ax-2/ax-3/ax-mp ONLY, with negation in the language.

This is the direct replacement for the earlier "4/11 on the named ladder"
figure.  That run used predator71.SELFTEST as its base, which declares

    $c wff |- ( ) -> /\ $.

and only ax1, ax2, ax-mp.  There is no `-.` and no ax-3.  Every negation
target in that ladder was therefore not unprovable but UNSTATABLE, and the
4/11 conflated a language defect with a search ceiling.  Here the base is
set.mm's real propositional core and every target is a genuine theorem of
it, so a failure is a search failure and nothing else.

Every proof found is emitted as a Metamath certificate and handed to
metamath.py, which knows nothing about how it was produced.

    python named_ladder.py
    python named_ladder.py --budgets 1000 5000 20000 60000 --depths 6 12 20
"""
from __future__ import annotations
import argparse, csv, itertools, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.setrecursionlimit(20000)

from metamath import MM, Toks, MMError, classify        # noqa: E402
import setmm_grammar as G                                # noqa: E402
import predator71 as P                                   # noqa: E402

BASE = r"""
$c wff |- ( ) -> -. $.
$v ph ps ch $.
wph $f wff ph $.
wps $f wff ps $.
wch $f wff ch $.
wi $a wff ( ph -> ps ) $.
wn $a wff -. ph $.
ax-1 $a |- ( ph -> ( ps -> ph ) ) $.
ax-2 $a |- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) $.
ax-3 $a |- ( ( -. ph -> -. ps ) -> ( ps -> ph ) ) $.
${
  min $e |- ph $.
  maj $e |- ( ph -> ps ) $.
  ax-mp $a |- ps $.
$}
"""

# set.mm names, set.mm statements.  All are theorems of ax-1/ax-2/ax-3.
LADDER = [
    ("id",       "( ph -> ph )"),
    ("a1i-cl",   "( ph -> ( ps -> ph ) )"),
    ("imim2",    "( ( ph -> ps ) -> ( ( ch -> ph ) -> ( ch -> ps ) ) )"),
    ("pm2.27",   "( ph -> ( ( ph -> ps ) -> ps ) )"),
    ("imim1",    "( ( ph -> ps ) -> ( ( ps -> ch ) -> ( ph -> ch ) ) )"),
    ("pm2.04",   "( ( ph -> ( ps -> ch ) ) -> ( ps -> ( ph -> ch ) ) )"),
    ("pm2.21",   "( -. ph -> ( ph -> ps ) )"),
    ("pm2.24",   "( ph -> ( -. ph -> ps ) )"),
    ("con3",     "( ( ph -> ps ) -> ( -. ps -> -. ph ) )"),
    ("notnot1",  "( ph -> -. -. ph )"),
    ("notnot2",  "( -. -. ph -> ph )"),
    ("con1",     "( ( -. ph -> ps ) -> ( -. ps -> ph ) )"),
    ("con2",     "( ( ph -> -. ps ) -> ( ps -> -. ph ) )"),
    ("pm2.01",   "( ( ph -> -. ph ) -> -. ph )"),
    ("pm2.18",   "( ( -. ph -> ph ) -> ph )"),
    ("peirce",   "( ( ( ph -> ps ) -> ph ) -> ph )"),
]


class Deadline(Exception):
    pass


def attempt(gt, idx, budget, depth, wall):
    t_end = time.perf_counter() + wall

    def tick(_m):
        if time.perf_counter() > t_end:
            raise Deadline()

    t0 = time.perf_counter()
    try:
        res, exp = P.prove(gt, idx, budget, depth, say=tick, progress=200)
        dt = time.perf_counter() - t0
        if res is not None:
            return "proved", res, exp, dt
        return ("budget" if exp > budget else "exhausted"), None, exp, dt
    except Deadline:
        return "timeout", None, -1, time.perf_counter() - t0
    except RecursionError:
        return "recursion", None, -1, time.perf_counter() - t0


def run(a):
    print("=" * 74)
    print("  Predator_7.1 -- classical propositional ladder")
    print("  base: ax-1, ax-2, ax-3, ax-mp   (negation IN the language)")
    print("=" * 74 + "\n")

    mm = MM()
    mm.read(Toks(BASE))
    by_tc = G.build_grammar(mm)
    kind = classify(mm)
    fvar, fallback = {}, {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar.setdefault(d[1], lab)
            fallback.setdefault(d[0], G.Tree(None, d[0], (), d[1]))
    idx = P.Index(mm, by_tc, say=lambda s: print("  " + s))
    print()

    grid = [(b, d) for d in a.depths for b in a.budgets]
    rows, solved, bad = [], 0, 0
    ladder = [(n, t) for n, t in LADDER if not a.only or n in a.only]

    for name, text in ladder:
        gt = G.parse(text.split(), "wff", by_tc)
        if gt is None:
            print("  %-9s DOES NOT PARSE" % name)
            continue
        got = None
        for budget, depth in grid:
            P._counter = itertools.count(1)
            out, res, exp, dt = attempt(gt, idx, budget, depth, a.wall)
            verdict, nlogic, nsteps = "", "", ""
            if out == "proved":
                root, sub = res
                try:
                    proof = root.emit(sub, fvar, fallback)
                    nsteps = len(proof)
                    nlogic = sum(1 for st in proof if kind.get(st) == "logic")
                    src = BASE + "\nchk $p |- %s $= %s $.\n" % (
                        text, " ".join(proof))
                    m2 = MM()
                    m2.read(Toks(src))
                    verdict = m2.verify("chk")
                    if verdict != "ok":
                        bad += 1
                except MMError as e:
                    verdict = "FAILED: %s" % e
                    bad += 1
            rows.append(dict(target=name, statement=text, budget=budget,
                             max_depth=depth, outcome=out, expansions=exp,
                             seconds=round(dt, 2), cv_verdict=verdict,
                             logic_steps=nlogic, proof_steps=nsteps))
            if out == "proved":
                got = (budget, depth, exp, dt, nlogic, verdict)
                break
        if got:
            solved += 1
            print("  %-9s PROVED   b=%-6s d=%-3d %7s exp  %5.1fs  "
                  "%2s logic steps  CV:%s"
                  % (name, f"{got[0]:,}", got[1], f"{got[2]:,}", got[3],
                     got[4], got[5]))
        else:
            last = rows[-1]
            print("  %-9s failed   (%s at b=%s d=%d, %s exp)"
                  % (name, last["outcome"], f"{last['budget']:,}",
                     last["max_depth"],
                     f"{last['expansions']:,}" if last["expansions"] >= 0
                     else "-"))

    os.makedirs(a.out, exist_ok=True)
    csv_path = os.path.join(a.out, "named_ladder.csv")
    exists = os.path.exists(csv_path) and a.append
    with open(csv_path, "a" if exists else "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not exists:
            w.writeheader()
        w.writerows(rows)
    with open(os.path.join(a.out, "named_ladder_%s.json"
                           % (a.tag or "run")), "w") as f:
        json.dump(dict(solved=solved, total=len(ladder),
                       cv_rejections=bad,
                       targets=[n for n, _ in ladder],
                       grid=dict(budgets=a.budgets, depths=a.depths,
                                 wall_seconds=a.wall)), f, indent=2)

    print("\n" + "=" * 74)
    print("  %d/%d proved,  %d CV rejections" % (solved, len(ladder), bad))
    print("=" * 74)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results_ladder")
    ap.add_argument("--budgets", type=int, nargs="+",
                    default=[1000, 5000, 20000, 60000])
    ap.add_argument("--depths", type=int, nargs="+", default=[6, 12])
    ap.add_argument("--wall", type=float, default=30.0)
    ap.add_argument("--only", nargs="*", default=None,
                    help="run only these targets")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--tag", default=None)
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(P._big_stack(main) or 0)
