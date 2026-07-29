#!/usr/bin/env python3
"""
Predator_6 -- expert iteration over a learned search policy.
Brian Tenneson, v6.0.

    python predator6.py run -p 0.7 -n 3 --max-steps 2000000
    python predator6.py versus                 <- Predator_5 vs Predator_6
    python predator6.py doctor

WHAT IS NEW SINCE PREDATOR_5
----------------------------
Predator_5 trains once, on targets whose shortest proofs breadth-first search
has already computed.  That caps it at the BFS horizon: it can only learn from
what BFS could already reach, so it can never be trained toward anything BFS
cannot find.

Predator_6 runs n passes:

    pass 1   train on BFS-CERTIFIED geodesics up to --seed-depth
    pass k   use the current policy to search the FRONTIER (targets beyond the
             seed depth, which have no computed label).  Every target solved
             contributes its found proof as new training data.  Retrain.

That is expert iteration, and it is the standard answer to the label problem.
It buys reach.  What it spends is label quality, and the program tracks the
exchange rate explicitly.

TWO KINDS OF LABEL, AND WHY THE DIFFERENCE MATTERS
--------------------------------------------------
    CERTIFIED   from BFS.  The marked edges lie on a true shortest path.  This
                is the shortest-path principle doing its job.
    BOOTSTRAP   from a proof the policy found.  The marked edges lie on SOME
                proof.  It may be far from shortest, and nothing here can tell.

This is exactly the objection Predator_5 raised against training on set.mm's
human-written proofs: a recorded proof is an upper bound on the geodesic, not
the geodesic.  Bootstrapped labels have the same defect.  The difference is
that here we know it and measure it, so the honest question is whether the
extra reach outweighs the noise -- and the answer is allowed to be no.

Every pass prints the certified/bootstrap ratio of its training set.  When that
ratio collapses, the policy is training on its own guesses.

THE STEP BUDGET
---------------
--max-steps is a hard cap on TOTAL node expansions across every pass and every
target.  When it is exhausted the run stops immediately and reports what it had
at that point.  Nothing is silently truncated: the summary states how much of
the budget was consumed and whether the run ended early.

WHAT THIS DOES NOT DO
---------------------
It runs on the condensed-detachment fragment, exactly like Predator_5.  It does
not run on set.mm, and it does not attempt the hyperreal statement, which is
not expressible in set.mm as it stands.  Expert iteration does not change
either of those facts -- it needs somewhere to bootstrap TOWARD, and on a
fragment BFS can exhaust, there is nothing past the horizon to reach.  Read the
frontier solve rate below with that in mind: it measures the mechanism, not a
capability on real mathematics.
"""
from __future__ import annotations
import argparse, heapq, json, os, platform, random, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import predator5 as P5
    from predator5 import (GAMMA, sweep, admissible, edge_features, show,
                           make_ranker, Policy, split_targets, normalise,
                           HAVE_NUMPY, HAVE_SKLEARN)
except ImportError as e:
    raise SystemExit("predator6.py needs predator5.py in the same folder (%s)" % e)

VERSION = "6.0"

WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)


# ===========================================================================
#  a hard global budget
# ===========================================================================
class Budget:
    """Total node expansions across the whole run.  Hard stop, no exceptions."""
    def __init__(self, cap):
        self.cap, self.used, self.exhausted = cap, 0, False

    def spend(self, n):
        self.used += n
        if self.used >= self.cap:
            self.exhausted = True
        return self.exhausted

    @property
    def left(self):
        return max(0, self.cap - self.used)

    def __str__(self):
        return "%s / %s (%.1f%%)" % (f"{self.used:,}", f"{self.cap:,}",
                                     100.0 * self.used / max(self.cap, 1))


# ===========================================================================
#  search that returns the PATH, so a found proof can become training data
# ===========================================================================
def guided_search_path(gamma, target, policy, max_size, edge_cap, budget,
                       lam=1.0):
    """Weighted-A* returning (length, expansions, path).

    path is [(state, Edge)] along the proof actually found.  Predator_5's
    guided_search discards this; expert iteration needs it, because the found
    proof IS the label."""
    start = frozenset(gamma)
    if target in start:
        return 0, 0, []
    seen = {start}
    parent = {}                      # state -> (prev_state, edge)
    frontier = [(0.0, 0, 0, start)]
    exp = tie = 0
    while frontier:
        _, depth, _, p = heapq.heappop(frontier)
        exp += 1
        if exp > budget:
            return None, exp, []
        edges, sc = policy.order(p, admissible(p, max_size, edge_cap),
                                 gamma, target)
        for e, s in zip(edges, sc):
            qs = p | {e.concl}
            if qs in seen:
                continue
            seen.add(qs)
            parent[qs] = (p, e)
            if e.concl == target:
                path, cur = [], qs
                while cur in parent:
                    pv, ed = parent[cur]
                    path.append((pv, ed))
                    cur = pv
                return depth + 1, exp, list(reversed(path))
            tie += 1
            heapq.heappush(frontier, (depth + 1 - lam * s, depth + 1, tie, qs))
    return None, exp, []


# ===========================================================================
#  training pairs from a found proof (bootstrap labels)
# ===========================================================================
def pairs_from_path(gamma, target, path, max_size, edge_cap, cap=4000):
    """Positives are the edges on the found proof; negatives are the other
    edges offered AT THE SAME STATE.

    Same within-state pairing as Predator_5 -- that is what makes it a policy
    and not a classifier.  The difference is only in what counts as positive:
    'on some proof we found' rather than 'on a shortest path'."""
    on = {(s, e.key()) for s, e in path}
    out, n = [], 0
    for s, _ in path:
        edges = admissible(s, max_size, edge_cap)
        pos = [e for e in edges if (s, e.key()) in on]
        neg = [e for e in edges if (s, e.key()) not in on]
        if not pos or not neg:
            continue
        fp = [edge_features(s, e, gamma, target) for e in pos]
        fn = [edge_features(s, e, gamma, target) for e in neg]
        for xp in fp:
            for xn in fn:
                out.append((xp, xn)); n += 1
                if n >= cap:
                    return out
    return out


# ===========================================================================
#  expert iteration
# ===========================================================================
def expert_iteration(a_, say=print):
    rng = random.Random(a_.seed)
    say("\n  sweeping to depth %d for ground truth..." % a_.depth)
    t0 = time.time()
    dist, pred, targets = sweep(GAMMA, a_.depth, a_.max_size, a_.edge_cap,
                                a_.state_budget)
    say("    %s states, %s targets, %.1fs"
        % (f"{len(dist):,}", f"{len(targets):,}", time.time() - t0))

    # seed = what BFS is ALLOWED to have priced.  frontier = beyond it.
    seed = [(t, d) for t, d in targets.items() if 2 <= d <= a_.seed_depth]
    deep = [(t, d) for t, d in targets.items() if d > a_.seed_depth]
    rng.shuffle(deep)

    # The held-out set is carved off FIRST, at a fixed fraction, and p then
    # divides only what remains.  An earlier version let p set the held-out
    # size directly, so raising p shrank the test set -- 30 targets at p=0.5
    # down to 10 at p=0.8 -- and the resulting sweep could not be read: rows
    # differed in sample size as well as in treatment.  Held-out is now
    # constant as p varies, which is the whole point of sweeping p.
    n_held = max(1, int(round(len(deep) * a_.test_frac)))
    held = deep[:n_held]
    pool = deep[n_held:]
    frontier = pool[:max(1, int(round(len(pool) * a_.p)))] if pool else []

    say("\n  seed      %3d targets at depth <= %d   (BFS-certified labels)"
        % (len(seed), a_.seed_depth))
    say("  held out  %3d targets  (%.0f%% of deep, FIXED -- does not move with p)"
        % (len(held), 100 * a_.test_frac))
    say("  frontier  %3d targets  (p=%.2f of the remaining %d; bootstrap here)"
        % (len(frontier), a_.p, len(pool)))
    if not held:
        say("\n  no held-out targets -- raise --depth or lower --seed-depth\n")
        return None

    budget = Budget(a_.max_steps)
    say("\n  step budget %s, p=%.2f, n=%d passes, lam=%.2f"
        % (f"{a_.max_steps:,}", a_.p, a_.passes, a_.lam))

    # certified pairs, computed once
    say("\n  building certified pairs from BFS geodesics...")
    certified = P5.build_pairs(GAMMA, dist, pred, seed, a_.max_size,
                               a_.edge_cap, a_.max_pairs_per_target, say=say)
    bootstrap = []
    solved = set()
    history = []

    for k in range(1, a_.passes + 1):
        say("\n" + "-" * 70)
        say("  PASS %d of %d" % (k, a_.passes))
        say("-" * 70)

        pool = certified + bootstrap
        nc, nb = len(certified), len(bootstrap)
        say("  training pairs  %s certified + %s bootstrap = %s"
            % (f"{nc:,}", f"{nb:,}", f"{nc + nb:,}"))
        if nc + nb:
            say("  certified share %.0f%%%s"
                % (100.0 * nc / (nc + nb),
                   "   <- training mostly on its own guesses"
                   if nc / (nc + nb) < 0.5 else ""))
        if not pool:
            say("  no training data; stopping")
            break

        ranker = make_ranker(a_.model, seed=a_.seed,
                             n_estimators=a_.n_estimators,
                             max_depth=a_.max_depth,
                             min_samples_leaf=a_.min_samples_leaf)
        ranker.fit(pool, say=say)
        policy = Policy(ranker, mode="reorder")

        # ---- evaluate on held-out, before touching the frontier ----------
        ev = evaluate(held, policy, a_, budget)
        say("  held-out        %d/%d solved, mean %.1f expansions, %.0f%% optimal"
            % (ev["solved"], len(held), ev["mean_exp"], 100 * ev["optimal"]))

        # ---- push the frontier ------------------------------------------
        newly = 0
        for t, d in frontier:
            if t in solved or budget.exhausted:
                continue
            L, exp, path = guided_search_path(GAMMA, t, policy, a_.max_size,
                                              a_.edge_cap,
                                              min(a_.budget, budget.left),
                                              a_.lam)
            budget.spend(exp)
            if L is not None and path:
                solved.add(t)
                bootstrap.extend(pairs_from_path(GAMMA, t, path, a_.max_size,
                                                 a_.edge_cap,
                                                 a_.max_pairs_per_target))
                newly += 1
        say("  frontier        %d newly solved this pass (%d/%d total)"
            % (newly, len(solved), len(frontier)))
        say("  budget          %s" % budget)

        history.append(dict(pass_=k, certified=nc, bootstrap=nb,
                            newly_solved=newly, total_solved=len(solved),
                            steps_used=budget.used, **ev))

        if budget.exhausted:
            say("\n  *** STEP BUDGET EXHAUSTED -- stopping after pass %d ***" % k)
            break
        if newly == 0 and k > 1:
            say("\n  frontier did not move; further passes cannot add labels")
            break

    return dict(history=history, budget_used=budget.used,
                budget_cap=budget.cap, exhausted=budget.exhausted,
                n_seed=len(seed), n_frontier=len(frontier), n_held=len(held))


def evaluate(held, policy, a_, budget):
    """Mean expansions and optimality on held-out targets."""
    exps, opt, solved = [], 0, 0
    for t, d in held:
        if budget.exhausted:
            break
        L, exp = P5.guided_search(GAMMA, t, policy, a_.max_size, a_.edge_cap,
                                  min(a_.budget, budget.left), a_.lam)
        budget.spend(exp)
        exps.append(exp)
        if L is not None:
            solved += 1
            if L == d:
                opt += 1
    return dict(solved=solved, mean_exp=sum(exps) / max(len(exps), 1),
                optimal=opt / max(solved, 1))


# ===========================================================================
#  commands
# ===========================================================================
def cmd_run(a_):
    print("=" * 74)
    print("  PREDATOR_6 v%s  --  expert iteration, %d passes" % (VERSION, a_.passes))
    print("=" * 74)
    print("\n  Gamma = %s" % ",  ".join(show(t) for t in GAMMA))
    r = expert_iteration(a_)
    if not r:
        return
    print("\n" + "=" * 74)
    print("  SUMMARY")
    print("=" * 74)
    print("\n  %-5s %11s %11s %8s %9s %8s" %
          ("pass", "certified", "bootstrap", "solved", "mean exp", "optimal"))
    print("  " + "-" * 62)
    for h in r["history"]:
        print("  %-5d %11s %11s %8d %9.1f %7.0f%%"
              % (h["pass_"], f"{h['certified']:,}", f"{h['bootstrap']:,}",
                 h["solved"], h["mean_exp"], 100 * h["optimal"]))
    print("\n  steps used  %s of %s%s"
          % (f"{r['budget_used']:,}", f"{r['budget_cap']:,}",
             "   *** EXHAUSTED ***" if r["exhausted"] else ""))

    h = r["history"]
    if len(h) >= 2:
        f, l = h[0], h[-1]
        d_exp = l["mean_exp"] - f["mean_exp"]
        d_slv = l["solved"] - f["solved"]
        d_opt = l["optimal"] - f["optimal"]
        print("\n  pass 1 -> pass %d on held-out" % l["pass_"])
        print("    solved      %d -> %d   (%+d)" % (f["solved"], l["solved"], d_slv))
        print("    optimal     %.0f%% -> %.0f%%  (%+.0f pts)"
              % (100 * f["optimal"], 100 * l["optimal"], 100 * d_opt))
        print("    expansions  %.1f -> %.1f  (%+.1f)"
              % (f["mean_exp"], l["mean_exp"], d_exp))

        # Solve rate and optimality dominate.  A policy that returns fewer and
        # worse proofs has not improved, however few nodes it expanded getting
        # there -- expansions are only comparable among runs that solved the
        # same targets to the same quality.
        if d_slv < 0 or d_opt < -0.01:
            print("\n  VERDICT: expert iteration HURT.")
            print("  It solved %s and returned %s proofs.  The %.1f-expansion"
                  % ("fewer targets" if d_slv < 0 else "as many targets",
                     "less optimal" if d_opt < -0.01 else "equally optimal",
                     abs(d_exp)))
            print("  gain does not pay for that: expansions are only comparable")
            print("  between runs that solved the same set to the same quality.")
        elif d_slv > 0 or d_exp < -0.5:
            print("\n  VERDICT: expert iteration helped.")
        else:
            print("\n  VERDICT: no measurable change.")

        share = l["certified"] / max(l["certified"] + l["bootstrap"], 1)
        if share < 0.5:
            print("\n  Certified share fell to %.0f%%.  Most training pairs now come"
                  % (100 * share))
            print("  from proofs the policy found itself, which are upper bounds on")
            print("  the geodesic, not geodesics.  That is the same defect this")
            print("  project objected to in set.mm's human-written proofs.")

        moved = [x["newly_solved"] for x in h[1:]]
        if moved and max(moved) <= 1:
            print("\n  The frontier stopped moving after pass 1 (%s newly solved"
                  % ", ".join(str(m) for m in moved))
            print("  in later passes).  There was nothing past the horizon to")
            print("  bootstrap toward, which is what a BFS-exhaustible fragment")
            print("  predicts.  This measures the mechanism, not a capability.")
    if a_.out:
        json.dump(r, open(a_.out, "w"), indent=2, default=str)
        print("\n  wrote %s" % a_.out)
    print()


def _verdict(a5, a6):
    """Solve rate and optimality dominate; expansions break ties.

    Comparing mean expansions between runs that solved different sets to
    different quality is comparing two different quantities."""
    d_slv = a6["solved"] - a5["solved"]
    d_opt = a6["optimal"] - a5["optimal"]
    d_exp = a6["mean_exp"] - a5["mean_exp"]
    if d_slv < 0 or d_opt < -0.01:
        return "P5", d_slv, d_opt, d_exp
    if d_slv > 0 or d_exp < -0.5:
        return "P6", d_slv, d_opt, d_exp
    return "wash", d_slv, d_opt, d_exp


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def cmd_versus(a_):
    """Predator_5 (single pass) vs Predator_6 (n passes), PAIRED OVER SEEDS.

    Single-seed comparison of these two systems is worthless.  The seed-to-seed
    standard deviation of held-out expansions on this fragment is 2-9, and the
    difference between the systems is around 1-4.  A one-seed table shows
    whichever sign the noise happened to take, and an earlier version of this
    command did exactly that and produced a confident, wrong conclusion.

    So: run both systems on the SAME seed, take the difference, repeat over
    seeds, and report the mean difference against its standard error.  Declare
    a winner only when the interval excludes zero."""
    depths = ([int(x) for x in a_.depths.split(",")] if a_.depths
              else [a_.depth])
    seeds = [int(s) for s in a_.seeds.split(",")]
    print("=" * 74)
    print("  PREDATOR_5 vs PREDATOR_6   (paired, %d seeds)" % len(seeds))
    print("=" * 74)
    print("\n  p=%.2f   n=%d passes   lam=%.2f   budget=%d   seeds %s"
          % (a_.p, a_.passes, a_.lam, a_.budget, a_.seeds))

    rows = []
    for d in depths:
        print("\n  depth %d " % d, end="", flush=True)
        t0 = time.time()
        per = []
        for s in seeds:
            one = argparse.Namespace(**vars(a_))
            one.depth, one.passes, one.seed = d, 1, s
            six = argparse.Namespace(**vars(a_))
            six.depth, six.seed = d, s
            r5 = expert_iteration(one, say=lambda *x: None)
            r6 = expert_iteration(six, say=lambda *x: None)
            if not r5 or not r6:
                continue
            a5, a6 = r5["history"][-1], r6["history"][-1]
            nf = r6["n_frontier"]; g1 = r6["history"][0]["newly_solved"]
            per.append(dict(
                s5=a5["solved"], e5=a5["mean_exp"], o5=a5["optimal"],
                st5=r5["budget_used"],
                s6=a6["solved"], e6=a6["mean_exp"], o6=a6["optimal"],
                st6=r6["budget_used"],
                held=r6["n_held"], left=(nf - g1) / max(nf, 1)))
            print(".", end="", flush=True)
        if not per:
            print(" skipped (no held-out targets)")
            continue
        rows.append(dict(depth=d, per=per))
        print(" %.0fs" % (time.time() - t0))

    if not rows:
        print("\n  nothing to compare; raise --depth\n")
        return

    print("\n" + "=" * 74)
    print("  PAIRED DIFFERENCE   (Predator_6 minus Predator_5, same seed)")
    print("=" * 74)
    print("\n  %-6s %6s %7s   %-18s %-18s %-10s" %
          ("depth", "held", "front.", "d(solved)", "d(expansions)", "extra"))
    print("  %-6s %6s %7s   %-18s %-18s %-10s" %
          ("", "", "left", "mean +/- se", "mean +/- se", "steps"))
    print("  " + "-" * 72)

    verdicts = []
    for r in rows:
        P = r["per"]; n = len(P)
        ds = [p["s6"] - p["s5"] for p in P]
        de = [p["e6"] - p["e5"] for p in P]
        do = [p["o6"] - p["o5"] for p in P]
        ses, see = _sd(ds) / max(n ** 0.5, 1), _sd(de) / max(n ** 0.5, 1)
        extra = 100.0 * (_mean([p["st6"] for p in P])
                         - _mean([p["st5"] for p in P])) \
            / max(_mean([p["st5"] for p in P]), 1)
        print("  %-6d %6.0f %6.0f%%   %+6.2f +/- %-8.2f %+6.1f +/- %-8.1f %+7.0f%%"
              % (r["depth"], _mean([p["held"] for p in P]),
                 100 * _mean([p["left"] for p in P]),
                 _mean(ds), ses, _mean(de), see, extra))

        # a difference counts only if it clears its own standard error
        sig_s = abs(_mean(ds)) > 2 * ses and ses > 0
        sig_e = abs(_mean(de)) > 2 * see and see > 0
        sig_o = abs(_mean(do)) > 0.02
        if not (sig_s or sig_e or sig_o):
            v = "indistinguishable"
        elif _mean(ds) < 0 or _mean(do) < -0.02:
            v = "Predator_5"
        elif _mean(ds) > 0 or _mean(de) < 0:
            v = "Predator_6"
        else:
            v = "Predator_5"
        verdicts.append((r["depth"], v, extra))

    print("\n  %-6s  %-20s  %s" % ("depth", "verdict", "cost of the extra passes"))
    print("  " + "-" * 66)
    for d, v, extra in verdicts:
        print("  %-6d  %-20s  %+.0f%% steps" % (d, v, extra))

    print("\n" + "=" * 74)
    print("  HOW TO READ THIS")
    print("=" * 74)
    ind = [d for d, v, _ in verdicts if v == "indistinguishable"]
    w5 = [d for d, v, _ in verdicts if v == "Predator_5"]
    w6 = [d for d, v, _ in verdicts if v == "Predator_6"]
    print("""
  Each row pairs the two systems on the same seed and averages the difference,
  so the split is identical within a pair and only the number of passes varies.
  A difference is called only when it exceeds twice its standard error.
""")
    if ind:
        print("  Indistinguishable at depth %s.  The systems differ by less than"
              % ", ".join(map(str, ind)))
        print("  the seed-to-seed noise, so no claim either way is supported.")
    if w5:
        print("  Predator_5 wins at depth %s." % ", ".join(map(str, w5)))
    if w6:
        print("  Predator_6 wins at depth %s." % ", ".join(map(str, w6)))
    if not w6:
        print("""
  Predator_6 nowhere beats Predator_5 on this fragment, and it always costs
  more steps.  The frontier-survival hypothesis -- that extra passes pay when
  pass 1 leaves targets unsolved -- is NOT supported by these runs: the depth
  with the largest surviving frontier was not the depth where extra passes
  helped.

  That is a result about the fragment, not about expert iteration in general.
  Here breadth-first search can price every target, so the certified labels
  are already the best available and bootstrapping can only add upper-bound
  labels to a training set that did not need them.  The case for the loop is
  on set.mm, where most targets have no computed label at all -- and that case
  is now untested rather than supported.""")
    print()
    if a_.out:
        json.dump(rows, open(a_.out, "w"), indent=2, default=str)
        print("  wrote %s\n" % a_.out)


def _unused_old_versus(a_, r5, r6):
    a5, a6 = r5["history"][-1], r6["history"][-1]
    print("\n  %-14s %8s %8s %10s %9s %11s" %
          ("system", "passes", "solved", "mean exp", "optimal", "steps"))
    print("  " + "-" * 62)
    print("  %-14s %8d %8d %10.1f %8.0f%% %11s"
          % ("Predator_5", 1, a5["solved"], a5["mean_exp"],
             100 * a5["optimal"], f"{r5['budget_used']:,}"))
    print("  %-14s %8d %8d %10.1f %8.0f%% %11s"
          % ("Predator_6", len(r6["history"]), a6["solved"], a6["mean_exp"],
             100 * a6["optimal"], f"{r6['budget_used']:,}"))

    d_exp = a6["mean_exp"] - a5["mean_exp"]
    d_slv = a6["solved"] - a5["solved"]
    d_opt = a6["optimal"] - a5["optimal"]
    extra = 100.0 * (r6["budget_used"] - r5["budget_used"]) / max(r5["budget_used"], 1)
    print("\n  difference  %+d solved, %+.0f pts optimal, %+.1f expansions"
          % (d_slv, 100 * d_opt, d_exp))
    print("              %.0f%% more steps spent" % extra)

    # Same ordering as cmd_run: solve rate and optimality dominate.  Comparing
    # mean expansions between runs that solved different sets to different
    # quality is comparing two different quantities.
    if d_slv < 0 or d_opt < -0.01:
        print("\n  PREDATOR_5 WINS.  The extra passes solved %s and returned %s"
              % ("fewer targets" if d_slv < 0 else "as many targets",
                 "less optimal proofs" if d_opt < -0.01 else "equal proofs"))
        print("  while spending %.0f%% more steps.  The %.1f-expansion gain does"
              % (extra, abs(d_exp)))
        print("  not pay for that.\n")
    elif d_slv > 0 or d_exp < -0.5:
        print("\n  PREDATOR_6 WINS: %s, at %.0f%% more steps.\n"
              % ("solved more" if d_slv > 0 else "same set, fewer expansions",
                 extra))
    else:
        print("\n  A WASH.  The extra passes bought nothing for %.0f%% more"
              " steps.\n" % extra)


def cmd_sweep(a_):
    """Sweep p (and optionally n), paired over seeds, on a FIXED held-out set.

    'Predator_6.1' is nothing more than a cell of this table: p=0.9 with many
    passes.  Naming a hyperparameter setting as a new version hides that it is
    one point in a grid, and invites reading a noise fluctuation as a release.
    So it is run as a grid, against the same held-out targets, with the seed
    spread reported next to every cell."""
    ps = [float(x) for x in a_.ps.split(",")]
    ns = [int(x) for x in a_.ns.split(",")]
    seeds = [int(s) for s in a_.seeds.split(",")]

    print("=" * 74)
    print("  PREDATOR_6  --  p x n sweep, paired over %d seeds" % len(seeds))
    print("=" * 74)
    print("\n  depth %d   seed-depth %d   test-frac %.2f (FIXED)   budget %d"
          % (a_.depth, a_.seed_depth, a_.test_frac, a_.budget))
    print("  held-out targets do not change with p, so rows are comparable.\n")

    base = None
    cells = []
    for p in ps:
        for n in ns:
            got = []
            for s in seeds:
                cfg = argparse.Namespace(**vars(a_))
                cfg.p, cfg.passes, cfg.seed = p, n, s
                r = expert_iteration(cfg, say=lambda *x: None)
                if r:
                    h = r["history"][-1]
                    got.append((h["solved"], h["mean_exp"], h["optimal"],
                                r["budget_used"], h["certified"],
                                h["bootstrap"], r["n_held"]))
            if not got:
                continue
            solved = [g[0] for g in got]; exp = [g[1] for g in got]
            opt = [g[2] for g in got];    st = [g[3] for g in got]
            cert = _mean([g[4] for g in got]); boot = _mean([g[5] for g in got])
            cells.append(dict(p=p, n=n, held=got[0][6],
                              solved=_mean(solved), sd_solved=_sd(solved),
                              exp=_mean(exp), sd_exp=_sd(exp),
                              se_exp=_sd(exp) / max(len(exp) ** .5, 1),
                              opt=_mean(opt), steps=_mean(st),
                              cert=100 * cert / max(cert + boot, 1)))
            if n == 1 and base is None:
                base = cells[-1]
            print("  p=%.2f n=%d  done" % (p, n))

    if not cells:
        print("\n  nothing to report; raise --depth\n")
        return

    print("\n" + "=" * 74)
    print("  RESULTS   (held-out = %d targets, identical in every row)"
          % cells[0]["held"])
    print("=" * 74)
    print("\n  %-5s %-3s %9s %16s %8s %10s %8s" %
          ("p", "n", "solved", "expansions", "optimal", "steps", "cert%"))
    print("  " + "-" * 68)
    for c in cells:
        print("  %-5.2f %-3d %6.1f+/-%-2.1f %8.1f +/- %-5.1f %7.0f%% %10s %7.0f%%"
              % (c["p"], c["n"], c["solved"], c["sd_solved"],
                 c["exp"], c["sd_exp"], 100 * c["opt"],
                 f"{c['steps']:,.0f}", c["cert"]))

    # ---- is any cell distinguishable from the n=1 baseline? -------------
    print("\n" + "=" * 74)
    print("  AGAINST THE n=1 BASELINE (no expert iteration)")
    print("=" * 74)
    if base is None:
        print("\n  include n=1 in --ns to get a baseline row.\n")
        return
    print("\n  baseline: p=%.2f n=1, %.1f expansions, %.1f solved\n"
          % (base["p"], base["exp"], base["solved"]))
    print("  %-5s %-3s %14s %14s %s" %
          ("p", "n", "d(expansions)", "d(solved)", "verdict"))
    print("  " + "-" * 62)
    any_better = False
    for c in cells:
        if c["n"] == 1 and c["p"] == base["p"]:
            continue
        de = c["exp"] - base["exp"]
        ds = c["solved"] - base["solved"]
        pooled = (c["se_exp"] ** 2 + base["se_exp"] ** 2) ** 0.5
        if pooled > 0 and abs(de) > 2 * pooled:
            v = "FASTER" if de < 0 else "slower"
        else:
            v = "within noise"
        if ds < -0.5:
            v = "solves fewer"
        elif ds > 0.5 and v == "within noise":
            v = "solves more"
        if v in ("FASTER", "solves more"):
            any_better = True
        print("  %-5.2f %-3d %+13.1f %+14.1f  %s" % (c["p"], c["n"], de, ds, v))

    print("""
  A cell is called only when the difference exceeds twice the pooled standard
  error of the two means.  Everything else is 'within noise' -- which on this
  fragment, at these sample sizes, is most of the grid.""")
    if not any_better:
        print("""
  NO SETTING OF p OR n BEATS n=1.  Expert iteration is not helping here at any
  frontier size.  That is consistent with the paired versus-run: on a fragment
  breadth-first search can price completely, the certified labels are already
  optimal and bootstrapping can only dilute them.

  Raising p enlarges the frontier but does not create anything past the BFS
  horizon, because on this fragment there is nothing past it.  p is not the
  variable that matters; having unreachable targets is.""")
    print()
    if a_.out:
        json.dump(cells, open(a_.out, "w"), indent=2, default=str)
        print("  wrote %s\n" % a_.out)


def cmd_doctor(_):
    print("Predator_6 v%s" % VERSION)
    print("  python    %s" % platform.python_version())
    print("  numpy     %s" % ("yes" if HAVE_NUMPY else "no"))
    print("  sklearn   %s" % ("yes" if HAVE_SKLEARN else "no"))
    print("  predator5 %s" % ("found" if P5 else "MISSING"))
    print("\n  fragment: condensed detachment.  Not set.mm.")


def main():
    ap = argparse.ArgumentParser(prog="predator6", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(q):
        q.add_argument("-n", "--passes", type=int, default=3)
        q.add_argument("-p", type=float, default=0.7,
                       help="fraction of the non-held-out pool used as the "
                            "bootstrap frontier.  Does NOT affect held-out "
                            "size; see --test-frac")
        q.add_argument("--test-frac", type=float, default=0.3,
                       help="fraction of deep targets held out.  Fixed as p "
                            "varies, so p-sweeps are comparable")
        q.add_argument("--max-steps", type=int, default=2_000_000,
                       help="HARD cap on total node expansions; run quits here")
        q.add_argument("--depth", type=int, default=6)
        q.add_argument("--seed-depth", type=int, default=3,
                       help="BFS labels allowed only up to here; beyond is "
                            "the bootstrap frontier")
        q.add_argument("--max-size", type=int, default=14)
        q.add_argument("--edge-cap", type=int, default=12)
        q.add_argument("--state-budget", type=int, default=20000)
        q.add_argument("--budget", type=int, default=400,
                       help="per-target expansion cap")
        q.add_argument("--lam", type=float, default=0.5)
        q.add_argument("--seed", type=int, default=0)
        q.add_argument("--model", choices=["logistic", "forest"],
                       default="logistic")
        q.add_argument("--max-pairs-per-target", type=int, default=2000)
        q.add_argument("--n-estimators", type=int, default=60)
        q.add_argument("--max-depth", type=int, default=8)
        q.add_argument("--min-samples-leaf", type=int, default=4)
        q.add_argument("--out", default=None)

    common(sub.add_parser("run"))
    v = sub.add_parser("versus"); common(v)
    v.add_argument("--seeds", default="0,1,2,3,4",
                   help="comma-separated seeds; paired comparison over these")
    v.add_argument("--depths", default=None,
                   help="comma-separated depths, e.g. 4,5,6.  The answer "
                        "depends on depth, so one depth misleads.")
    w = sub.add_parser("sweep"); common(w)
    w.add_argument("--ps", default="0.5,0.7,0.9",
                   help="p values to sweep (held-out stays fixed)")
    w.add_argument("--ns", default="1,3,5",
                   help="pass counts to sweep; include 1 for the baseline")
    w.add_argument("--seeds", default="0,1,2,3,4")

    sub.add_parser("doctor")

    a_ = ap.parse_args()
    if getattr(a_, "edge_cap", None) == 0:
        a_.edge_cap = None
    if a_.cmd == "run":       cmd_run(a_)
    elif a_.cmd == "versus":  cmd_versus(a_)
    elif a_.cmd == "sweep":   cmd_sweep(a_)
    elif a_.cmd == "doctor":  cmd_doctor(a_)
    else:                     ap.print_help()


if __name__ == "__main__":
    main()
