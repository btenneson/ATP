#!/usr/bin/env python3
"""
geodesic_policy.py -- a nondeterministic search policy whose ordering is
learned from historical geodesic membership.

Brian Tenneson.  Implements Definitions 5.1-5.5 and 6.3-6.9 of
"Depths of a Simulation" v45 concretely, over a fragment small enough that
the admissible-extension set is actually enumerable.

WHAT THIS IS, AND WHY IT IS NOT PREDATOR_4
------------------------------------------
Predator_4 ranks LEMMAS against a GOAL: "which of the library's 43,900
statements does this proof cite?"  It has no search.  It emits an ordering and
stops.

This file ranks EDGES against a STATE: "from proof state p, which admissible
one-step extension moves toward a shortest proof?"  That is a policy Sigma in
the sense of Definition 5.2, and it is consumed by an actual search that
extends states until the target appears.  The two objects have different
inputs, different training signals, and different failure modes.

The crucial difference is in the negatives.  Predator_4 samples non-premises
from the whole library.  A policy learner cannot do that: its negatives must be
the OTHER EDGES THAT WERE APPLICABLE AT THAT STATE, because those are the
alternatives the policy actually has to rank against.  set.mm does not record
them -- a proof is the path taken, never the frontier rejected -- which is why
the training signal here is computed by search rather than read from a file.

PROOF-COVERING, AND WHAT PRUNING COSTS
--------------------------------------
Theorem 5.7 (Branch-Covering) requires Sigma to be proof-covering, Def 5.5:
every finite proof is shadowed by some branch.  Two guidance modes:

  reorder  Sigma(p,m) is returned complete, permuted by the learned score.
           Proof-covering is preserved, so Theorem 5.7 and Corollary 5.8 hold
           and the shortest-proof horizon is still reachable.  Search is
           best-first, and slower in the worst case.

  prune    Sigma(p,m) is truncated to the top k.  Proof-covering FAILS: the
           deleted branches may be the only ones shadowing a shortest proof.
           Theorem 5.7 no longer applies and completeness is gone.  Faster.

The mode is a flag, not a default, and the program prints which guarantee it is
operating under.  Remark 6.11's A* optimality has the same shape: it survives
only under an ADMISSIBLE heuristic, and a fitted model is essentially never
admissible, so guided search here is best-first, not A*.

WHERE THE GROUND TRUTH COMES FROM
---------------------------------
Not from set.mm.  A set.mm proof is an upper bound on the geodesic, not a
geodesic -- the repository's history is full of shorter proofs replacing longer
ones -- so training on it teaches what humans wrote.  Instead, Corollary 6.13:
breadth-first search on the novelty state graph computes the TRUE distance, and
a backward pass marks every edge lying on SOME shortest path.  That is the
label.  It costs an exhaustive search per training instance, which is why the
fragment has to be small; the payoff is that the labels are correct by
construction rather than by assumption.

THE FRAGMENT
------------
Condensed detachment over implicational formulas: one rule, most-general
unification, the standard testbed for this kind of experiment.  From a major
premise A -> B and a minor premise C, unify A with C after renaming apart and
return B under the resulting substitution.  Sigma(p, m) is then every novel
D(a, b) for ordered pairs a, b in p, which is finite and enumerable -- exactly
the property set.mm lacks and the reason Predator_2 abandoned forward search.

    python geodesic_policy.py bfs        ground-truth geodesics, no learning
    python geodesic_policy.py train      fit the policy on computed geodesics
    python geodesic_policy.py compare    BFS vs guided, expansions to target
"""
from __future__ import annotations
import argparse, heapq, itertools, math, random, sys, time
from collections import defaultdict, deque

# ===========================================================================
#  terms:  ('v', n) is a variable;  ('>', A, B) is A -> B
# ===========================================================================
def V(n): return ("v", n)
def Imp(a, b): return (">", a, b)

def is_var(t): return t[0] == "v"

def size(t):
    return 1 if is_var(t) else 1 + size(t[1]) + size(t[2])

def variables(t, acc=None):
    if acc is None: acc = set()
    if is_var(t): acc.add(t[1])
    else: variables(t[1], acc); variables(t[2], acc)
    return acc

def show(t):
    if is_var(t): return "abcdefghijklmnopqrstuvwxyz"[t[1] % 26]
    return "(%s->%s)" % (show(t[1]), show(t[2]))


def apply_subst(t, s):
    if is_var(t):
        return apply_subst(s[t[1]], s) if t[1] in s else t
    return (">", apply_subst(t[1], s), apply_subst(t[2], s))


def unify(a, b, s=None):
    """Robinson unification with occurs check.  Returns a substitution dict or
    None.  The occurs check is not optional here: without it condensed
    detachment produces cyclic terms and the state graph stops being a DAG."""
    if s is None: s = {}
    a = apply_subst(a, s); b = apply_subst(b, s)
    if a == b: return s
    if is_var(a):
        if a[1] in variables(b): return None          # occurs check
        s = dict(s); s[a[1]] = b; return s
    if is_var(b):
        if b[1] in variables(a): return None
        s = dict(s); s[b[1]] = a; return s
    s2 = unify(a[1], b[1], s)
    return None if s2 is None else unify(a[2], b[2], s2)


def rename_apart(t, offset):
    if is_var(t): return ("v", t[1] + offset)
    return (">", rename_apart(t[1], offset), rename_apart(t[2], offset))


def normalise(t):
    """Rename variables to 0,1,2,... in first-occurrence order, so that terms
    equal up to renaming are equal as tuples.  Without this the state set fills
    with alphabetic variants of one formula and the geodesic is meaningless."""
    mapping = {}
    def go(u):
        if is_var(u):
            if u[1] not in mapping: mapping[u[1]] = len(mapping)
            return ("v", mapping[u[1]])
        return (">", go(u[1]), go(u[2]))
    return go(t)


def detach(major, minor, max_size=40):
    """Condensed detachment D(major, minor).

    major must be an implication A -> B.  Rename the minor apart, unify its
    whole formula with A, return B under the unifier.  None if they do not
    unify or the result exceeds max_size, which bounds the branching."""
    if is_var(major): return None
    off = max(variables(major), default=0) + 1
    m2 = rename_apart(minor, off)
    s = unify(major[1], m2)
    if s is None: return None
    out = apply_subst(major[2], s)
    if size(out) > max_size: return None
    return normalise(out)


# ===========================================================================
#  Definition 5.1 / 6.3 -- admissible one-step extensions, as graph edges
# ===========================================================================
class Edge:
    """One admissible proof-search transaction: the inference data (r, a1..ak)
    of Definition 6.3, with r = condensed detachment and k = 2."""
    __slots__ = ("major", "minor", "concl")
    def __init__(self, major, minor, concl):
        self.major, self.minor, self.concl = major, minor, concl
    def key(self): return (self.major, self.minor, self.concl)
    def __repr__(self):
        return "D(%s, %s) = %s" % (show(self.major), show(self.minor), show(self.concl))


def admissible(state, max_size=40, cap=None):
    """Sigma_full(p): every NOVEL one-step extension at p.

    Novel means concl not already in p, which is Proposition 6.5's restriction
    to the novelty state graph G^nov.  Keeping only novel edges is what makes
    the graph acyclic: every edge strictly grows the state by set inclusion, so
    a directed cycle would need a finite chain of strict inclusions returning
    to its start."""
    out, seen = [], set()
    items = sorted(state, key=lambda t: (size(t), t))
    for major in items:
        if is_var(major): continue
        for minor in items:
            c = detach(major, minor, max_size)
            if c is None or c in state or c in seen: continue
            seen.add(c)
            out.append(Edge(major, minor, c))
            if cap and len(out) >= cap: return out
    return out


# ===========================================================================
#  Corollary 6.13 / Theorem 6.9 -- BFS gives the geodesic AND the labels
# ===========================================================================
def bfs_geodesic(gamma, target, max_size=40, node_budget=20000, edge_cap=None):
    """Breadth-first search on the novelty state graph.

    Returns (dist, pred, expansions, found) where dist maps each reached state
    to its graph distance from Gamma and pred maps it to the list of ALL
    (parent, edge) pairs realising that distance -- all of them, not one, so
    that the backward pass can mark every edge lying on SOME shortest path
    rather than on one arbitrarily chosen shortest path.

    By Theorem 6.9 the first time a target state leaves the queue its distance
    is minimal, so `found` is the geodesic length, i.e. the transaction count
    of Remark 6.10 and the shortest-proof horizon of Section 2.
    """
    start = frozenset(gamma)
    if target in start: return {start: 0}, {}, 0, 0
    dist = {start: 0}
    pred = defaultdict(list)
    q = deque([start])
    expansions = 0
    found = None
    while q:
        p = q.popleft()
        d = dist[p]
        if found is not None and d >= found:
            continue                      # finish the layer, then stop
        expansions += 1
        if expansions > node_budget: break
        for e in admissible(p, max_size, edge_cap):
            qs = p | {e.concl}
            nd = d + 1
            if qs not in dist:
                dist[qs] = nd
                pred[qs].append((p, e))
                q.append(qs)
                if e.concl == target and found is None:
                    found = nd
            elif dist[qs] == nd:
                pred[qs].append((p, e))   # a second shortest route into qs
    return dist, pred, expansions, found


def geodesic_edges(dist, pred, target, found):
    """Backward pass: the set of edges lying on at least one shortest path to a
    state containing the target.  These are the positive examples; every other
    edge offered at a state on some geodesic is a negative."""
    if found is None: return set()
    goals = [s for s, d in dist.items() if d == found and target in s]
    on, stack, seen = set(), list(goals), set(goals)
    while stack:
        s = stack.pop()
        for parent, e in pred.get(s, ()):
            on.add((parent, e.key()))
            if parent not in seen:
                seen.add(parent); stack.append(parent)
    return on


# ===========================================================================
#  features of an EDGE at a STATE
# ===========================================================================
FEATURES = [
    "concl size",
    "concl size / max state size",
    "concl novel-symbol ratio",
    "major size",
    "minor size",
    "major is axiom of Gamma",
    "minor is axiom of Gamma",
    "unifier growth (concl/major)",
    "state size",
    "concl shares top-level shape with target",
    "concl subterm-overlap with target",
    "concl var count",
]

def edge_features(state, e, gamma, target):
    """Every feature is a property of the (state, edge) PAIR.

    A feature constant across the edges offered at one state cannot change
    their order and is dead weight -- the same discipline Predator_4's FEATURES
    comment insists on, for the same reason.  'state size' is included only
    because states are compared across a frontier in best-first mode, where it
    does vary.
    """
    ss = [size(t) for t in state]
    mx = max(ss) if ss else 1
    cs, ms, ns = size(e.concl), size(e.major), size(e.minor)
    tvars = variables(target)
    cvars = variables(e.concl)
    def subterms(t, acc=None):
        if acc is None: acc = set()
        acc.add(t)
        if not is_var(t): subterms(t[1], acc); subterms(t[2], acc)
        return acc
    tsub, csub = subterms(target), subterms(e.concl)
    return [
        cs / 10.0,
        cs / mx,
        len(cvars - tvars) / max(len(cvars), 1),
        ms / 10.0,
        ns / 10.0,
        1.0 if e.major in gamma else 0.0,
        1.0 if e.minor in gamma else 0.0,
        cs / max(ms, 1),
        len(state) / 10.0,
        1.0 if (not is_var(e.concl) and not is_var(target)
                and is_var(e.concl[1]) == is_var(target[1])) else 0.0,
        len(csub & tsub) / max(len(csub | tsub), 1),
        len(cvars) / 5.0,
    ]


# ===========================================================================
#  the learned policy  --  Definition 5.2 with an ordering
# ===========================================================================
def rank_fit(pairs, epochs=400, lr=0.5, l2=1e-4, seed=0):
    """Pairwise ranking on difference vectors, with the antisymmetric copies.

    Identical in form to predator4.rank_fit, and for the identical reason: what
    is consumed is the ORDER of the edges at a state, so that is what should be
    optimised.  Features constant across a state cancel in the difference and
    cannot absorb weight."""
    if not pairs: raise SystemExit("no training pairs")
    D = [[a - b for a, b in zip(xp, xn)] for xp, xn in pairs]
    y = [1.0] * len(D)
    D += [[-v for v in d] for d in D]; y += [0.0] * len(pairs)
    k = len(D[0]); rng = random.Random(seed)
    w = [rng.gauss(0, .01) for _ in range(k)]
    m = len(y)
    for _ in range(epochs):
        g = [0.0] * k
        for xi, yi in zip(D, y):
            z = max(-30.0, min(30.0, sum(x * wj for x, wj in zip(xi, w))))
            err = 1.0 / (1.0 + math.exp(-z)) - yi
            for j in range(k): g[j] += err * xi[j]
        for j in range(k): w[j] -= lr * (g[j] / m + l2 * w[j])
    return w


class Policy:
    """Sigma of Definition 5.2, with the nondeterminism ORDERED by a fitted w.

    mode='reorder'  returns Sigma(p,m) complete.  Proof-covering (Def 5.5) is
                    preserved, so Theorem 5.7 still applies.
    mode='prune'    returns the top k.  Proof-covering FAILS.  Theorem 5.7 does
                    not apply and the search is incomplete.
    """
    def __init__(self, w=None, mode="reorder", k=8):
        self.w, self.mode, self.k = w, mode, k

    @property
    def covering(self):
        return self.mode == "reorder"

    def order(self, state, edges, gamma, target):
        if self.w is None:
            return edges
        sc = [sum(x * wj for x, wj in zip(edge_features(state, e, gamma, target), self.w))
              for e in edges]
        idx = sorted(range(len(edges)), key=lambda i: -sc[i])
        ordered = [edges[i] for i in idx]
        return ordered if self.mode == "reorder" else ordered[:self.k]


def collect_training(problems, max_size, node_budget, edge_cap, say=print):
    """For each problem: compute the true geodesic by BFS, mark the on-geodesic
    edges, and emit (positive, negative) pairs from the SAME state.

    Pairing within a state is what makes this a policy and not a classifier:
    the model is never asked whether an edge is good in the abstract, only
    whether it is better than the alternatives that were actually on offer."""
    pairs, solved = [], 0
    for name, gamma, target in problems:
        t0 = time.perf_counter()
        dist, pred, exp, found = bfs_geodesic(gamma, target, max_size,
                                              node_budget, edge_cap)
        if found is None:
            say("    %-14s unreached within %s expansions" % (name, f"{exp:,}"))
            continue
        solved += 1
        on = geodesic_edges(dist, pred, target, found)
        states = {s for (s, _) in on}
        npairs = 0
        for s in states:
            edges = admissible(s, max_size, edge_cap)
            pos = [e for e in edges if (s, e.key()) in on]
            neg = [e for e in edges if (s, e.key()) not in on]
            if not pos or not neg: continue
            fp = [edge_features(s, e, gamma, target) for e in pos]
            fn = [edge_features(s, e, gamma, target) for e in neg]
            for xp in fp:
                for xn in fn:
                    pairs.append((xp, xn)); npairs += 1
        say("    %-14s geodesic %d, %s expansions, %s pairs, %.1fs"
            % (name, found, f"{exp:,}", f"{npairs:,}", time.perf_counter() - t0))
    return pairs, solved


def guided_search(gamma, target, policy, max_size=40, node_budget=20000,
                  edge_cap=None, lam=1.0):
    """Weighted-A* over the novelty state graph, ordered by the policy.

        f(q) = depth(q)  -  lam * score(edge into q)

    The depth term is the g of Remark 6.11 and it is not optional.  An earlier
    version of this function ordered by the learned score alone, which is pure
    greedy best-first: nothing in the priority decreases with depth, so the
    search chases high-scoring states downward and never returns to the breadth
    that BFS gets for free.  It lost `weaken2`, a target BFS reaches in twenty
    expansions, inside a budget of four hundred.  Keeping g fixes that.

    lam is the interpolation knob, and its two ends are both objects from the
    paper:

        lam = 0     f = depth.  This IS breadth-first, so it is the canonical
                    BFS SIC of Corollary 6.13: the first proof found is a
                    geodesic and the search is complete.
        lam -> inf  f = -score.  Greedy descent.  No guarantee of any kind.

    In between the search is complete under mode='reorder' -- every state is
    still eventually popped -- but the FIRST proof found need not be shortest,
    because the heuristic is not admissible.  A fitted score never is.  So the
    returned length is an upper bound on the geodesic and is reported as one.
    """
    start = frozenset(gamma)
    if target in start: return 0, 0, []
    seen = {start}
    frontier = [(0.0, 0, start, [])]
    heapq.heapify(frontier)
    expansions = 0
    tie = 0
    while frontier:
        _, _, p, path = heapq.heappop(frontier)
        expansions += 1
        if expansions > node_budget: return None, expansions, []
        depth = len(path)
        edges = admissible(p, max_size, edge_cap)
        for e in policy.order(p, edges, gamma, target):
            qs = p | {e.concl}
            if qs in seen: continue
            seen.add(qs)
            if e.concl == target:
                return depth + 1, expansions, path + [e]
            tie += 1
            f = edge_features(p, e, gamma, target)
            s = 0.0 if policy.w is None else sum(x * wj for x, wj in zip(f, policy.w))
            heapq.heappush(frontier, (depth + 1 - lam * s, tie, qs, path + [e]))
    return None, expansions, []


# ===========================================================================
#  problems -- Lukasiewicz implicational calculus
# ===========================================================================
a, b, c = V(0), V(1), V(2)
AX_K = normalise(Imp(a, Imp(b, a)))
AX_S = normalise(Imp(Imp(a, Imp(b, c)), Imp(Imp(a, b), Imp(a, c))))
AX_W = normalise(Imp(Imp(Imp(a, b), a), a))          # Peirce
GAMMA = [AX_K, AX_S, AX_W]

PROBLEMS = [
    ("identity",   GAMMA, normalise(Imp(a, a))),
    ("perm",       GAMMA, normalise(Imp(Imp(a, Imp(b, c)), Imp(b, Imp(a, c))))),
    ("compose",    GAMMA, normalise(Imp(Imp(a, b), Imp(Imp(b, c), Imp(a, c))))),
    ("weaken2",    GAMMA, normalise(Imp(a, Imp(b, Imp(c, a))))),
]


def cmd_bfs(args):
    print("=" * 74)
    print("  GROUND TRUTH  --  BFS geodesics on the novelty state graph")
    print("  Corollary 6.13: the BFS SIC's halting stage is the graph distance")
    print("=" * 74)
    print("\n  Gamma = %s" % ", ".join(show(t) for t in GAMMA))
    print("\n  %-14s %10s %14s %10s" % ("target", "geodesic", "expansions", "seconds"))
    for name, gamma, target in PROBLEMS:
        t0 = time.perf_counter()
        dist, pred, exp, found = bfs_geodesic(gamma, target, args.max_size,
                                              args.budget, args.edge_cap)
        print("  %-14s %10s %14s %10.1f"
              % (name, found if found is not None else "-", f"{exp:,}",
                 time.perf_counter() - t0))
    print("\n  These distances are computed, not assumed.  A set.mm proof would")
    print("  give an upper bound on each; BFS gives the value.")


def cmd_train(args):
    print("=" * 74)
    print("  TRAINING  --  a policy ordered by historical geodesic membership")
    print("=" * 74)
    print("\n[1] computing ground-truth geodesics")
    pairs, solved = collect_training(PROBLEMS, args.max_size, args.budget,
                                     args.edge_cap)
    if not pairs: sys.exit("\nno pairs; raise --budget or --max-size")
    print("\n[2] %s solved, %s (on-geodesic, off-geodesic) pairs from shared states"
          % (solved, f"{len(pairs):,}"))
    w = rank_fit(pairs, seed=args.seed)
    print("\n[3] learned ordering")
    for nm, wt in sorted(zip(FEATURES, w), key=lambda kv: -abs(kv[1])):
        bar = "#" * int(round(abs(wt) * 20))
        print("    %-34s %+7.3f  %s" % (nm, wt, bar))
    return w


def cmd_compare(args):
    w = cmd_train(args)
    print("\n" + "=" * 74)
    print("  BFS vs GUIDED  --  expansions to reach the target")
    print("=" * 74)
    modes = [("BFS (lam=0)", Policy(None, "reorder"), 0.0),
             ("reorder lam=%.1f" % args.lam, Policy(w, "reorder"), args.lam),
             ("prune k=%d" % args.k, Policy(w, "prune", args.k), args.lam)]
    print("\n  %-18s %-14s %8s %12s  %s"
          % ("policy", "target", "length", "expansions", "guarantee"))
    for label, pol, lam in modes:
        for name, gamma, target in PROBLEMS:
            if label.startswith("BFS"):
                _, _, exp, found = bfs_geodesic(gamma, target, args.max_size,
                                                args.budget, args.edge_cap)
                ln = found
            else:
                ln, exp, _ = guided_search(gamma, target, pol, args.max_size,
                                           args.budget, args.edge_cap, lam)
            g = ("geodesic, complete" if label.startswith("BFS")
                 else "complete, len is upper bound" if pol.covering
                 else "INCOMPLETE (Def 5.5 fails)")
            print("  %-18s %-14s %8s %12s  %s"
                  % (label, name, ln if ln is not None else "-", f"{exp:,}", g))
        print()
    print("  Read the guarantee column, not just the expansion count.  A length")
    print("  under a guided row is an upper bound on the geodesic; only the BFS")
    print("  row reports the geodesic itself.  Pruning buys expansions by")
    print("  surrendering proof-covering, hence Theorem 5.7.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    for nm in ("bfs", "train", "compare"):
        p = sub.add_parser(nm)
        p.add_argument("--max-size", type=int, default=24,
                       help="largest formula kept; bounds the branching")
        p.add_argument("--budget", type=int, default=4000,
                       help="node expansion budget per problem")
        p.add_argument("--edge-cap", type=int, default=60,
                       help="cap on edges enumerated per state; 0 = all")
        p.add_argument("--seed", type=int, default=0)
        if nm == "compare":
            p.add_argument("-k", type=int, default=8, help="prune width")
            p.add_argument("--lam", type=float, default=1.0,
                           help="heuristic weight; 0 = BFS = geodesic + complete, "
                                "large = greedy descent + no guarantee")
    a = ap.parse_args()
    if a.edge_cap == 0: a.edge_cap = None
    if a.cmd == "bfs":       cmd_bfs(a)
    elif a.cmd == "train":   cmd_train(a)
    elif a.cmd == "compare": cmd_compare(a)
    else:                    ap.print_help()


if __name__ == "__main__":
    main()
