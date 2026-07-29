#!/usr/bin/env python3
"""
arena.py -- every search strategy on one fragment, timed in seconds.

    python arena.py --depth 5 --seeds 0,1,2,3,4

Four strategies, one learned ranker, one set of held-out targets:

    BFS              lambda=0.  No policy.  Complete, returns geodesics.
    weighted-A*      Predator_5.  f(q) = depth(q) - lambda*score.  Complete.
    A* + pruning     Predator_5 --mode prune.  Top-k only.  INCOMPLETE.
    beam search      Predator_1's strategy.  Level-synchronous, keep top W.
                     INCOMPLETE.

WHY THIS EXISTS
---------------
Predator_1 used beam search on a synthetic corpus.  Predator_5 uses weighted-A*
on the condensed-detachment fragment.  They have never shared a benchmark, so
"which search is better" has never been asked, only assumed.  Here the features,
the ranker, the targets and the split are identical and only the strategy moves.

AND THE THING NOBODY MEASURED
-----------------------------
Predator_1 is the only system in this project that reported WALL CLOCK:

    EXPANSIONS   18.1x fewer
    WALL CLOCK   0.32s -> 0.81s     2.5x SLOWER
    per expansion  21us -> 883us    (41x overhead)

It opened 18x fewer nodes and finished 2.5x slower, because scoring cost 41x
more per node than the nodes it saved were worth.  A node count is
hardware-independent and that is exactly why it can lie: it does not charge you
for thinking.

Predator_5 reports node counts only, claims 1.6-1.8x, and pays a feature
extraction plus a dot product on every edge at every state.  If Predator_1 could
not break even at 18x, 1.8x is a thin margin.  Every row below carries seconds,
microseconds per expansion, and the break-even test:

    a policy wins in real time iff   node speedup  >  per-node overhead

TWO INTERPOLATIONS, NOT ONE
---------------------------
lambda interpolates weighted-A*:   0 = BFS,  infinity = greedy descent.
W      interpolates beam search:   infinity = BFS,  1 = hill climbing.

Both collapse to breadth-first search at one end.  Neither preserves
proof-covering away from it -- pruning and beam both DISCARD states, so the
Branch-Covering Theorem stops applying and a failure to find a proof stops
meaning anything.  Only the BFS and reorder rows keep the guarantee.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import predator5 as P5
    from predator5 import (GAMMA, sweep, admissible, show, make_ranker,
                           Policy, split_targets, HAVE_SKLEARN)
except ImportError as e:
    raise SystemExit("arena.py needs predator5.py in the same folder (%s)" % e)

WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)


# ===========================================================================
#  beam search -- Predator_1's strategy
# ===========================================================================
def beam_search(gamma, target, policy, max_size, edge_cap, budget, width,
                max_depth=40):
    """Level-synchronous search keeping the best `width` states per level.

    This is what Predator_1 did.  It differs from weighted-A* in two ways that
    matter:

      * it is SYNCHRONOUS -- every state at depth d is expanded before any at
        depth d+1, so it cannot dive the way best-first can;
      * it DISCARDS -- everything outside the top `width` at each level is gone
        permanently, not deferred.  Proof-covering fails and so does the
        Branch-Covering Theorem.

    width = infinity is exactly breadth-first search.  width = 1 is hill
    climbing.  Returns (length, expansions)."""
    start = frozenset(gamma)
    if target in start:
        return 0, 0
    seen = {start}
    level = [start]
    exp = 0
    for depth in range(1, max_depth + 1):
        scored = []
        for p in level:
            exp += 1
            if exp > budget:
                return None, exp
            edges, sc = policy.order(p, admissible(p, max_size, edge_cap),
                                     gamma, target)
            for e, s in zip(edges, sc):
                qs = p | {e.concl}
                if qs in seen:
                    continue
                seen.add(qs)
                if e.concl == target:
                    return depth, exp
                scored.append((s, qs))
        if not scored:
            return None, exp
        scored.sort(key=lambda x: -x[0])
        level = [q for _, q in scored[:width]] if width else [q for _, q in scored]
    return None, exp


# ===========================================================================
#  timed evaluation
# ===========================================================================
def run_strategy(name, fn, held, guarantee):
    """Run one strategy over the held-out targets, timing it."""
    exps, secs, solved, optimal = [], 0.0, 0, 0
    for t, d in held:
        t0 = time.perf_counter()
        L, e = fn(t)
        secs += time.perf_counter() - t0
        exps.append(e)
        if L is not None:
            solved += 1
            if L == d:
                optimal += 1
    n = max(len(held), 1)
    tot = sum(exps)
    return dict(name=name, guarantee=guarantee,
                solved=solved / n, mean_exp=tot / n, total_exp=tot,
                secs=secs, us_per_exp=1e6 * secs / max(tot, 1),
                optimal=optimal / max(solved, 1))


def one_seed(a_, seed):
    dist, pred, targets = sweep(GAMMA, a_.depth, a_.max_size, a_.edge_cap,
                                a_.state_budget)
    tr, held = split_targets(targets, a_.test_frac, seed)
    if not held:
        return None
    pairs = P5.build_pairs(GAMMA, dist, pred, tr, a_.max_size, a_.edge_cap,
                           a_.max_pairs_per_target, say=lambda *x: None)
    if not pairs:
        return None
    ranker = make_ranker(a_.model, seed=seed, n_estimators=a_.n_estimators,
                         max_depth=a_.max_depth, min_samples_leaf=4)
    ranker.fit(pairs, say=lambda *x: None)

    reorder = Policy(ranker, mode="reorder")
    prune = Policy(ranker, mode="prune", k=a_.k)
    nullp = Policy(None)

    mk = lambda pol, lam: (lambda t: P5.guided_search(
        GAMMA, t, pol, a_.max_size, a_.edge_cap, a_.budget, lam))
    mkb = lambda pol, w: (lambda t: beam_search(
        GAMMA, t, pol, a_.max_size, a_.edge_cap, a_.budget, w))

    return [
        run_strategy("BFS (lam=0)", mk(nullp, 0.0), held,
                     "geodesic, complete"),
        run_strategy("weighted-A* reorder", mk(reorder, a_.lam), held,
                     "complete"),
        run_strategy("A* prune k=%d" % a_.k, mk(prune, a_.lam), held,
                     "INCOMPLETE"),
        run_strategy("beam W=%d" % a_.width, mkb(reorder, a_.width), held,
                     "INCOMPLETE"),
        run_strategy("beam W=1 (hill)", mkb(reorder, 1), held,
                     "INCOMPLETE"),
    ], len(held)


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def main():
    ap = argparse.ArgumentParser(prog="arena", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--max-size", type=int, default=14)
    ap.add_argument("--edge-cap", type=int, default=12)
    ap.add_argument("--state-budget", type=int, default=20000)
    ap.add_argument("--test-frac", type=float, default=0.3)
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--lam", type=float, default=0.5)
    ap.add_argument("-k", type=int, default=4, help="prune width")
    ap.add_argument("--width", type=int, default=8, help="beam width")
    ap.add_argument("--seeds", default="0,1,2,3,4")
    ap.add_argument("--model", default="logistic",
                    choices=["logistic", "forest"])
    ap.add_argument("--n-estimators", type=int, default=60)
    ap.add_argument("--max-depth", type=int, default=8)
    ap.add_argument("--max-pairs-per-target", type=int, default=2000)
    ap.add_argument("--out", default=None)
    a_ = ap.parse_args()
    if a_.edge_cap == 0:
        a_.edge_cap = None

    seeds = [int(s) for s in a_.seeds.split(",")]
    print("=" * 78)
    print("  ARENA  --  search strategies on the condensed-detachment fragment")
    print("=" * 78)
    print("\n  Gamma = %s" % ",  ".join(show(t) for t in GAMMA))
    print("  depth %d   lambda %.2f   prune k=%d   beam W=%d   budget %d"
          % (a_.depth, a_.lam, a_.k, a_.width, a_.budget))
    print("  %d seeds, same ranker and same held-out targets in every row\n"
          % len(seeds))

    runs, held_n = [], 0
    for s in seeds:
        print("  seed %d ..." % s, end="", flush=True)
        t0 = time.time()
        r = one_seed(a_, s)
        if r is None:
            print(" skipped")
            continue
        rows, held_n = r
        runs.append(rows)
        print(" %.0fs" % (time.time() - t0))

    if not runs:
        print("\n  no held-out targets; raise --depth\n")
        return

    names = [r["name"] for r in runs[0]]
    agg = []
    for i, nm in enumerate(names):
        agg.append(dict(
            name=nm, guarantee=runs[0][i]["guarantee"],
            solved=_mean([r[i]["solved"] for r in runs]),
            exp=_mean([r[i]["mean_exp"] for r in runs]),
            sd_exp=_sd([r[i]["mean_exp"] for r in runs]),
            secs=_mean([r[i]["secs"] for r in runs]),
            us=_mean([r[i]["us_per_exp"] for r in runs]),
            opt=_mean([r[i]["optimal"] for r in runs])))

    base = agg[0]                                    # BFS
    print("\n" + "=" * 78)
    print("  RESULTS   (%d held-out targets, mean over %d seeds)"
          % (held_n, len(runs)))
    print("=" * 78)
    print("\n  %-21s %7s %14s %8s %9s %8s" %
          ("strategy", "solved", "expansions", "seconds", "us/exp", "optimal"))
    print("  " + "-" * 74)
    for r in agg:
        print("  %-21s %6.0f%% %8.1f+/-%-4.1f %8.4f %9.1f %7.0f%%"
              % (r["name"], 100 * r["solved"], r["exp"], r["sd_exp"],
                 r["secs"], r["us"], 100 * r["opt"]))

    print("\n" + "=" * 78)
    print("  BREAK-EVEN   (Predator_1's test, applied to every strategy)")
    print("=" * 78)
    print("""
  A policy wins in real time only if it saves more in nodes than it spends
  per node:

        node speedup   =  BFS expansions / policy expansions
        overhead       =  policy us-per-expansion / BFS us-per-expansion
        real speedup   =  BFS seconds / policy seconds
""")
    print("  %-21s %12s %11s %13s  %s" %
          ("strategy", "node speedup", "overhead", "real speedup", "verdict"))
    print("  " + "-" * 76)
    for r in agg[1:]:
        ns = base["exp"] / max(r["exp"], 1e-9)
        ov = r["us"] / max(base["us"], 1e-9)
        rs = base["secs"] / max(r["secs"], 1e-9)
        if rs > 1.05:
            v = "FASTER in seconds"
        elif rs < 0.95:
            v = "SLOWER in seconds"
        else:
            v = "a wash"
        print("  %-21s %11.2fx %10.1fx %12.2fx  %s"
              % (r["name"], ns, ov, rs, v))

    print("\n  guarantees")
    for r in agg:
        print("    %-21s %s" % (r["name"], r["guarantee"]))

    losers = [r for r in agg[1:]
              if base["secs"] / max(r["secs"], 1e-9) < 0.95]
    print("\n" + "=" * 78)
    print("  WHAT THIS SHOWS")
    print("=" * 78)
    if losers:
        print("""
  %d of %d policies expand fewer nodes than breadth-first search and still
  finish SLOWER in seconds.  That is Predator_1's result reproducing on a
  different fragment with a different search: a node count does not charge you
  for thinking, and scoring every edge at every state is not free.

  Any speedup this project quotes in expansions should be quoted next to its
  seconds, or it is not a speedup claim about anything a user experiences."""
              % (len(losers), len(agg) - 1))
    else:
        print("""
  Every policy that saved nodes also saved seconds here.  That is the outcome
  Predator_1 did NOT get, so the difference is worth understanding before it is
  trusted -- most likely the per-node cost of this feature set is lower, or the
  fragment's nodes are more expensive to expand than the synthetic corpus's.""")
    print()
    if a_.out:
        json.dump(agg, open(a_.out, "w"), indent=2, default=str)
        print("  wrote %s\n" % a_.out)


if __name__ == "__main__":
    main()
