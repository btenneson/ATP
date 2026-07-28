#!/usr/bin/env python3
"""
Predator_5 -- learning a SEARCH POLICY from computed geodesics.
Brian Tenneson, v5.0.  btenneson2301.substack.com

ONE FILE.  numpy and scikit-learn optional (needed only for --model forest).

    python predator5.py                 <- run this.  It explains itself.

WHAT CHANGED FROM PREDATOR_4
----------------------------
Predator_4 ranks LEMMAS against a GOAL: of set.mm's 43,900 statements, which
does this proof cite?  It has no search.  It emits an ordering and stops.  Its
scores are trained on set.mm's premise lists.

Predator_5 ranks EDGES against a STATE: from proof state p, which admissible
one-step extension moves toward a SHORTEST proof?  That is a nondeterministic
proof-search policy Sigma, and it is consumed by a search that extends states
until the target appears.  Three differences follow, and all three matter.

  1. THE NEGATIVES ARE DIFFERENT.  Predator_4 samples non-premises from the
     whole library.  A policy cannot: its negatives must be the OTHER EDGES
     APPLICABLE AT THAT STATE, because those are the alternatives it actually
     has to rank against.  Ranking an edge against a lemma from a different
     part of the search is answering a question no search ever asks.

  2. THE LABELS ARE COMPUTED, NOT READ.  A set.mm proof is an UPPER BOUND on
     the shortest proof, not the shortest proof -- the repository's history is
     full of shorter proofs replacing longer ones.  Train on it and you learn
     what humans wrote.  Predator_5 runs breadth-first search first, which by
     the shortest-path ATP principle returns the true distance, then marks
     every edge lying on SOME shortest path.  The labels are correct by
     construction.  The price is that the fragment must be small enough for
     BFS to finish, which is why this file does not run on set.mm.

  3. THERE IS A COMPLETENESS THEOREM TO LOSE.  The Branch-Covering Theorem
     needs Sigma to be proof-covering: every finite proof shadowed by some
     branch.  Ordering Sigma(p,m) preserves that.  TRUNCATING IT DOES NOT --
     the deleted branches may be the only ones shadowing a shortest proof.
     So --mode reorder keeps the theorem and --mode prune surrenders it, and
     the program prints which guarantee is in force on every row of output.
     A speedup obtained by pruning is not the same kind of object as a speedup
     obtained by reordering, and reporting them in one column without saying
     so would be the single easiest way to mislead a reader here.

THE INTERPOLATION KNOB
----------------------
Search priority is

        f(q) = depth(q)  -  lambda * score(edge into q)

and lambda is not a free parameter, it interpolates between two things already
in the theory:

    lambda = 0     f = depth.  This IS breadth-first search, so it is the
                   canonical BFS search object: first proof found is shortest,
                   search is complete.
    lambda -> inf  f = -score.  Greedy descent.  No guarantee of any kind.

An earlier version of this program dropped the depth term, which is pure greedy
best-first.  Nothing in the priority then decreases with depth, so the search
chases high-scoring states downward and never returns to the breadth that BFS
gets for free.  It LOST a target that BFS reaches in twenty expansions, inside
a budget of four hundred.  The depth term is not a refinement; it is the thing
that makes the search work.

Between the endpoints, --mode reorder is still complete -- every state is
eventually popped -- but the FIRST proof found need not be shortest, because
the learned score is not an admissible heuristic and a fitted score essentially
never is.  So a length reported under a guided row is an upper bound on the
geodesic.  Only the BFS row reports the geodesic itself.  The output says so.

THE FRAGMENT
------------
Condensed detachment over implicational formulas: one rule, most-general
unification, the standard testbed.  From a major premise A -> B and a minor
premise C, unify A with C after renaming apart, return B under the unifier.
Sigma(p,m) is then every novel D(a,b) for ordered pairs in p, which is finite
and enumerable -- the property set.mm lacks, and precisely the reason
Predator_2 abandoned forward search for premise selection in the first place.

TARGETS ARE HARVESTED, NOT HAND-PICKED
--------------------------------------
One bounded breadth-first sweep from Gamma reaches many states.  Every formula
that first appears in a state at distance d has shortest-proof length exactly
d.  So a single sweep yields dozens of targets with EXACT geodesics, for free,
and they can be split into training and held-out sets.  Hand-picking four
famous theorems and then training and testing on the same four -- which is what
the first draft of this experiment did -- measures memorisation.

WORKING DIRECTORY
    All input and output files go to:  C:\google drive\Automated Theorem Proving
    Run predator5.py from anywhere; it will chdir there automatically.

COMMANDS
    python predator5.py harvest         sweep, list targets and their geodesics
    python predator5.py train           fit a policy on the training targets
    python predator5.py compare         logistic vs forest vs BFS, held-out
    python predator5.py doctor          check the environment
"""
from __future__ import annotations
import argparse, heapq, json, math, os, platform, random, sys, time
from collections import defaultdict, deque

# ===========================================================================
#  Working directory: all input and output to Google Drive
# ===========================================================================
WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)
# else silently use cwd (for testing in sandbox)

VERSION = "5.0"

try:
    import numpy as _np; HAVE_NUMPY = True
except ImportError:
    _np = None; HAVE_NUMPY = False
try:
    from sklearn.ensemble import RandomForestClassifier
    HAVE_SKLEARN = True
except ImportError:
    RandomForestClassifier = None; HAVE_SKLEARN = False


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

def subterms(t, acc=None):
    if acc is None: acc = set()
    acc.add(t)
    if not is_var(t): subterms(t[1], acc); subterms(t[2], acc)
    return acc

def show(t):
    if is_var(t): return "abcdefghijklmnopqrstuvwxyz"[t[1] % 26]
    return "(%s->%s)" % (show(t[1]), show(t[2]))

def apply_subst(t, s):
    if is_var(t):
        return apply_subst(s[t[1]], s) if t[1] in s else t
    return (">", apply_subst(t[1], s), apply_subst(t[2], s))

def unify(a, b, s=None):
    """Robinson unification with occurs check.

    The occurs check is not optional.  Without it condensed detachment produces
    cyclic terms, size() does not terminate on them, and the novelty state
    graph stops being acyclic."""
    if s is None: s = {}
    a = apply_subst(a, s); b = apply_subst(b, s)
    if a == b: return s
    if is_var(a):
        if a[1] in variables(b): return None
        s = dict(s); s[a[1]] = b; return s
    if is_var(b):
        if b[1] in variables(a): return None
        s = dict(s); s[b[1]] = a; return s
    s2 = unify(a[1], b[1], s)
    return None if s2 is None else unify(a[2], b[2], s2)

def rename_apart(t, off):
    if is_var(t): return ("v", t[1] + off)
    return (">", rename_apart(t[1], off), rename_apart(t[2], off))

def normalise(t):
    """Rename variables to 0,1,2,... in first-occurrence order, so terms equal
    up to renaming are equal as tuples.  Without this the state fills with
    alphabetic variants of one formula and the distance is meaningless."""
    m = {}
    def go(u):
        if is_var(u):
            if u[1] not in m: m[u[1]] = len(m)
            return ("v", m[u[1]])
        return (">", go(u[1]), go(u[2]))
    return go(t)

def detach(major, minor, max_size=40):
    """Condensed detachment D(major, minor)."""
    if is_var(major): return None
    off = max(variables(major), default=0) + 1
    s = unify(major[1], rename_apart(minor, off))
    if s is None: return None
    out = apply_subst(major[2], s)
    return None if size(out) > max_size else normalise(out)


# ===========================================================================
#  admissible one-step extensions  ==  edges of the novelty state graph
# ===========================================================================
class Edge:
    __slots__ = ("major", "minor", "concl")
    def __init__(self, major, minor, concl):
        self.major, self.minor, self.concl = major, minor, concl
    def key(self): return (self.major, self.minor, self.concl)
    def __repr__(self):
        return "D(%s,%s)=%s" % (show(self.major), show(self.minor), show(self.concl))


def admissible(state, max_size=40, cap=None):
    """Sigma_full(p): every NOVEL one-step extension at p.

    'Novel' means the conclusion is not already in p.  Restricting to novel
    edges is what makes the graph acyclic: every edge strictly grows the state
    by set inclusion, and a directed cycle would need a finite chain of strict
    inclusions returning to its start.

    Enumeration is in a fixed order -- by formula size, then by tuple -- so the
    edge list is deterministic.  With `cap` set, the SAME prefix is kept every
    time, which keeps BFS and guided search comparable; a random cap would make
    the two searches explore different graphs and the comparison meaningless.
    """
    out, seen = [], set()
    items = sorted(state, key=lambda t: (size(t), t))
    for major in items:
        if is_var(major): continue
        for minor in items:
            c = detach(major, minor, max_size)
            if c is None or c in state or c in seen: continue
            seen.add(c); out.append(Edge(major, minor, c))
            if cap and len(out) >= cap: return out
    return out


# ===========================================================================
#  the sweep:  ground truth for many targets at once
# ===========================================================================
def sweep(gamma, depth, max_size, edge_cap, state_budget=20000):
    """One bounded breadth-first sweep of the novelty state graph.

    Returns (dist, pred, targets) where

        dist[p]     graph distance of state p from Gamma
        pred[p]     ALL (parent, edge) pairs realising that distance -- all of
                    them, not one, so the backward pass can mark every edge on
                    SOME shortest path rather than one arbitrarily chosen path
        targets[f]  shortest-proof length of formula f

    By the shortest-path principle, a formula first appearing at BFS layer d has
    shortest-proof length exactly d.  So one sweep prices every target it
    reaches, and the prices are computed rather than assumed.
    """
    start = frozenset(gamma)
    dist = {start: 0}
    pred = defaultdict(list)
    targets = {}
    q = deque([start])
    while q:
        p = q.popleft(); d = dist[p]
        if d >= depth: continue
        if len(dist) > state_budget: break
        for e in admissible(p, max_size, edge_cap):
            qs = p | {e.concl}
            nd = d + 1
            if qs not in dist:
                dist[qs] = nd; pred[qs].append((p, e)); q.append(qs)
                if e.concl not in targets: targets[e.concl] = nd
            elif dist[qs] == nd:
                pred[qs].append((p, e))
    return dist, pred, targets


def geodesic_edges(dist, pred, target, d):
    """Edges lying on at least one shortest path to a state containing target.

    These are the positives.  Every OTHER edge offered at a state that lies on
    some geodesic is a negative -- which is the only sound notion of negative
    for a policy, since those are the alternatives it must rank against."""
    goals = [s for s, dd in dist.items() if dd == d and target in s]
    on, stack, seen = set(), list(goals), set(goals)
    while stack:
        s = stack.pop()
        for parent, e in pred.get(s, ()):
            on.add((parent, e.key()))
            if parent not in seen:
                seen.add(parent); stack.append(parent)
    return on


def bfs_to(gamma, target, max_size, edge_cap, budget):
    """Plain BFS for one target.  Returns (length, expansions).  This is the
    benchmark row: complete, and the length it returns IS the geodesic."""
    start = frozenset(gamma)
    if target in start: return 0, 0
    dist = {start: 0}; q = deque([start]); exp = 0
    while q:
        p = q.popleft(); d = dist[p]; exp += 1
        if exp > budget: return None, exp
        for e in admissible(p, max_size, edge_cap):
            qs = p | {e.concl}
            if qs in dist: continue
            dist[qs] = d + 1
            if e.concl == target: return d + 1, exp
            q.append(qs)
    return None, exp


# ===========================================================================
#  features of an EDGE at a STATE
# ===========================================================================
FEATURES = [
    "concl size", "concl size / max in state", "concl novel-var ratio",
    "major size", "minor size", "major in Gamma", "minor in Gamma",
    "unifier growth concl/major", "state size",
    "concl top-shape matches target", "concl subterm overlap w/ target",
    "concl var count",
]

def edge_features(state, e, gamma, target, _cache={}):
    """Every feature is a property of the (state, edge) PAIR.

    A feature constant across the edges offered at one state cannot change
    their order.  The fit will still assign it a weight, which is worse than
    useless because it then looks informative in the printout.  'state size' is
    kept only because in best-first mode states from different depths compete
    on one frontier, so it does vary where it is used."""
    ss = [size(t) for t in state]
    mx = max(ss) if ss else 1
    cs, ms, ns = size(e.concl), size(e.major), size(e.minor)
    tv = variables(target); cv = variables(e.concl)
    tk = id(target)
    if tk not in _cache: _cache[tk] = subterms(target)
    tsub = _cache[tk]; csub = subterms(e.concl)
    return [
        cs / 10.0,
        cs / mx,
        len(cv - tv) / max(len(cv), 1),
        ms / 10.0,
        ns / 10.0,
        1.0 if e.major in gamma else 0.0,
        1.0 if e.minor in gamma else 0.0,
        cs / max(ms, 1),
        len(state) / 10.0,
        1.0 if (not is_var(e.concl) and not is_var(target)
                and is_var(e.concl[1]) == is_var(target[1])) else 0.0,
        len(csub & tsub) / max(len(csub | tsub), 1),
        len(cv) / 5.0,
    ]


# ===========================================================================
#  the two rankers
# ===========================================================================
def dot(a, b): return sum(x * y for x, y in zip(a, b))


class LogisticRanker:
    """Linear scorer fitted by pairwise ranking loss.

    Cannot represent interactions: it cannot learn that subterm overlap with
    the target matters MORE when the conclusion is small than when it is large,
    because that is a product of two features and a linear score is a sum."""
    name = "logistic"

    def __init__(self, seed=0, epochs=400, lr=0.5, l2=1e-4, **kw):
        self.seed, self.epochs, self.lr, self.l2 = seed, epochs, lr, l2
        self.w = None

    def fit(self, pairs, say=print):
        D = [[a - b for a, b in zip(xp, xn)] for xp, xn in pairs]
        y = [1.0] * len(D)
        # antisymmetry: without the negated copies the fit can satisfy the
        # objective by inflating every score rather than by ordering anything
        D += [[-v for v in d] for d in D]; y += [0.0] * len(pairs)
        k = len(D[0]); m = len(y)
        if HAVE_NUMPY:
            X = _np.asarray(D, float); Y = _np.asarray(y, float)
            w = _np.random.default_rng(self.seed).normal(0, .01, k)
            for _ in range(self.epochs):
                pr = 1.0 / (1.0 + _np.exp(-_np.clip(X @ w, -30, 30)))
                w -= self.lr * (X.T @ (pr - Y) / m + self.l2 * w)
            self.w = [float(v) for v in w]
        else:
            rng = random.Random(self.seed)
            w = [rng.gauss(0, .01) for _ in range(k)]
            for _ in range(self.epochs):
                g = [0.0] * k
                for xi, yi in zip(D, y):
                    z = max(-30.0, min(30.0, dot(xi, w)))
                    err = 1.0 / (1.0 + math.exp(-z)) - yi
                    for j in range(k): g[j] += err * xi[j]
                for j in range(k): w[j] -= self.lr * (g[j] / m + self.l2 * w[j])
            self.w = w
        say("    fitted %s difference rows, %d features" % (f"{len(D):,}", k))
        return self

    def score_rows(self, rows): return [dot(r, self.w) for r in rows]

    def describe(self):
        return sorted(zip(FEATURES, self.w), key=lambda kv: -abs(kv[1]))

    def to_dict(self): return dict(model="logistic", weights=self.w)


class ForestRanker:
    """Random forest fitted on the same pairwise differences.

    Splits on thresholds and combines them, so interactions and non-monotone
    effects are representable.  Whether they HELP is the empirical question
    `compare` exists to answer, and the answer is allowed to be no: a forest
    that loses is evidence the policy signal in these features is close to
    linear, not evidence the forest is broken."""
    name = "forest"

    DEFAULTS = dict(n_estimators=300, max_depth=12, min_samples_leaf=4,
                    min_samples_split=10, max_features="sqrt")

    def __init__(self, seed=0, max_pairs=200_000, **params):
        if not HAVE_SKLEARN:
            raise SystemExit(
                "the forest ranker needs scikit-learn and numpy:\n"
                "    python -m pip install scikit-learn\n"
                "or run with  --model logistic")
        p = dict(self.DEFAULTS)
        p.update({k: v for k, v in params.items() if v is not None})
        p.update(random_state=seed, n_jobs=-1)
        self.params, self.seed, self.max_pairs = p, seed, max_pairs
        self.clf = None

    def fit(self, pairs, say=print):
        rng = random.Random(self.seed)
        if self.max_pairs and len(pairs) > self.max_pairs:
            say("    subsampling %s pairs -> %s"
                % (f"{len(pairs):,}", f"{self.max_pairs:,}"))
            pairs = rng.sample(pairs, self.max_pairs)
        D = _np.asarray([[a - b for a, b in zip(xp, xn)] for xp, xn in pairs],
                        dtype=_np.float32)
        X = _np.vstack([D, -D])
        Y = _np.concatenate([_np.ones(len(D)), _np.zeros(len(D))])
        say("    fitting %s trees, depth %s, on %s x %d"
            % (self.params["n_estimators"], self.params["max_depth"],
               f"{X.shape[0]:,}", X.shape[1]))
        self.clf = RandomForestClassifier(**self.params).fit(X, Y)
        return self

    def score_rows(self, rows):
        return list(self.clf.predict_proba(
            _np.asarray(rows, dtype=_np.float32))[:, 1])

    def describe(self):
        return sorted(zip(FEATURES, self.clf.feature_importances_),
                      key=lambda kv: -kv[1])

    def to_dict(self):
        return dict(model="forest", params={k: str(v) for k, v in self.params.items()},
                    importances=[float(v) for v in self.clf.feature_importances_])


def make_ranker(kind, seed=0, **kw):
    return ForestRanker(seed=seed, **kw) if kind == "forest" else LogisticRanker(seed=seed)


# ===========================================================================
#  the policy
# ===========================================================================
class Policy:
    """A nondeterministic proof-search policy with its nondeterminism ORDERED.

    mode='reorder'  Sigma(p,m) returned complete, permuted.  Proof-covering is
                    preserved, so the Branch-Covering Theorem still applies.
    mode='prune'    truncated to top k.  Proof-covering FAILS and the theorem
                    does not apply.  Faster, incomplete.
    """
    def __init__(self, ranker=None, mode="reorder", k=8):
        self.ranker, self.mode, self.k = ranker, mode, k

    @property
    def covering(self): return self.mode == "reorder"

    @property
    def guarantee(self):
        if self.ranker is None: return "geodesic, complete"
        return ("complete; length is an upper bound" if self.covering
                else "INCOMPLETE: proof-covering fails")

    def order(self, state, edges, gamma, target):
        if self.ranker is None or not edges: return edges, [0.0] * len(edges)
        rows = [edge_features(state, e, gamma, target) for e in edges]
        sc = self.ranker.score_rows(rows)
        idx = sorted(range(len(edges)), key=lambda i: -sc[i])
        if self.mode == "prune": idx = idx[:self.k]
        return [edges[i] for i in idx], [sc[i] for i in idx]


def guided_search(gamma, target, policy, max_size, edge_cap, budget, lam=1.0):
    """Weighted-A* on the novelty state graph:  f(q) = depth(q) - lam*score.

    The depth term is g and it is not optional; see the module docstring.
    Returns (length, expansions).  Under mode='reorder' the search is complete
    but the length is an UPPER BOUND on the geodesic, because a fitted score is
    not an admissible heuristic."""
    start = frozenset(gamma)
    if target in start: return 0, 0
    seen = {start}
    frontier = [(0.0, 0, 0, start)]
    exp = tie = 0
    while frontier:
        _, depth, _, p = heapq.heappop(frontier)
        exp += 1
        if exp > budget: return None, exp
        edges, sc = policy.order(p, admissible(p, max_size, edge_cap),
                                 gamma, target)
        for e, s in zip(edges, sc):
            qs = p | {e.concl}
            if qs in seen: continue
            seen.add(qs)
            if e.concl == target: return depth + 1, exp
            tie += 1
            heapq.heappush(frontier, (depth + 1 - lam * s, depth + 1, tie, qs))
    return None, exp


# ===========================================================================
#  training data:  pairs drawn from states on a geodesic
# ===========================================================================
def build_pairs(gamma, dist, pred, train_targets, max_size, edge_cap,
                max_pairs_per_target=4000, say=print):
    """For each training target, pair every on-geodesic edge against every
    off-geodesic edge OFFERED AT THE SAME STATE.

    Pairing within a state is what makes this a policy rather than a
    classifier: the model is never asked whether an edge is good in the
    abstract, only whether it beats the alternatives actually on offer."""
    pairs = 0; out = []
    for t, d in train_targets:
        on = geodesic_edges(dist, pred, t, d)
        states = {s for (s, _) in on}
        n = 0
        for s in states:
            edges = admissible(s, max_size, edge_cap)
            pos = [e for e in edges if (s, e.key()) in on]
            neg = [e for e in edges if (s, e.key()) not in on]
            if not pos or not neg: continue
            fp = [edge_features(s, e, gamma, t) for e in pos]
            fn = [edge_features(s, e, gamma, t) for e in neg]
            for xp in fp:
                for xn in fn:
                    out.append((xp, xn)); n += 1
                    if n >= max_pairs_per_target: break
                if n >= max_pairs_per_target: break
            if n >= max_pairs_per_target: break
        pairs += n
    say("    %s pairs from %d training targets" % (f"{pairs:,}", len(train_targets)))
    return out


# ===========================================================================
#  the fragment
# ===========================================================================
a, b, c = V(0), V(1), V(2)
AX_K = normalise(Imp(a, Imp(b, a)))
AX_S = normalise(Imp(Imp(a, Imp(b, c)), Imp(Imp(a, b), Imp(a, c))))
AX_W = normalise(Imp(Imp(Imp(a, b), a), a))
GAMMA = [AX_K, AX_S, AX_W]
NAMED = {normalise(Imp(a, a)): "identity",
         normalise(Imp(Imp(a, Imp(b, c)), Imp(b, Imp(a, c)))): "permute",
         normalise(Imp(Imp(a, b), Imp(Imp(b, c), Imp(a, c)))): "compose"}


def split_targets(targets, test_frac, seed, min_d=2):
    """Hold out a fraction of harvested targets.

    Targets at distance 1 are excluded: they are one edge from Gamma, every
    policy finds them immediately, and including them inflates every solve rate
    without distinguishing anything."""
    items = [(t, d) for t, d in targets.items() if d >= min_d]
    items.sort(key=lambda td: (td[1], show(td[0])))
    rng = random.Random(seed); rng.shuffle(items)
    n_test = max(1, int(len(items) * test_frac))
    return items[n_test:], items[:n_test]


def harvest(a_, say=print):
    t0 = time.perf_counter()
    dist, pred, targets = sweep(GAMMA, a_.depth, a_.max_size, a_.edge_cap,
                                a_.state_budget)
    say("  swept to depth %d: %s states, %d distinct targets, %.1fs"
        % (a_.depth, f"{len(dist):,}", len(targets), time.perf_counter() - t0))
    by = defaultdict(int)
    for f, d in targets.items(): by[d] += 1
    say("  targets by geodesic: %s" % dict(sorted(by.items())))
    return dist, pred, targets


# ===========================================================================
#  commands
# ===========================================================================
def cmd_harvest(a_):
    print("=" * 74)
    print("  PREDATOR_5 v%s  --  harvest: ground-truth geodesics" % VERSION)
    print("=" * 74)
    print("\n  Gamma = %s" % ",  ".join(show(t) for t in GAMMA))
    dist, pred, targets = harvest(a_)
    tr, te = split_targets(targets, a_.test_frac, a_.seed)
    print("\n  split: %d train, %d held out (seed %d)" % (len(tr), len(te), a_.seed))
    print("\n  held-out targets")
    print("    %-9s %-46s %s" % ("geodesic", "formula", "name"))
    for t, d in sorted(te, key=lambda td: td[1]):
        print("    %-9d %-46s %s" % (d, show(t)[:46], NAMED.get(t, "")))
    print("\n  These distances are computed by breadth-first search, not")
    print("  assumed from a human-written proof.")


def cmd_train(a_, say=print, quiet=False):
    if not quiet:
        print("=" * 74)
        print("  PREDATOR_5 v%s  --  train a search policy" % VERSION)
        print("=" * 74)
    dist, pred, targets = harvest(a_, say)
    tr, te = split_targets(targets, a_.test_frac, a_.seed)
    say("\n[1] %d training targets, %d held out" % (len(tr), len(te)))
    say("\n[2] building pairs from states on a geodesic")
    pairs = build_pairs(GAMMA, dist, pred, tr, a_.max_size, a_.edge_cap,
                        a_.max_pairs_per_target, say)
    if not pairs: sys.exit("no pairs; raise --depth or --edge-cap")
    say("\n[3] fitting <%s>" % a_.model)
    t0 = time.perf_counter()
    r = make_ranker(a_.model, seed=a_.seed, n_estimators=a_.n_estimators,
                    max_depth=a_.max_depth, min_samples_leaf=a_.min_samples_leaf,
                    max_pairs=a_.max_pairs).fit(pairs, say)
    say("    %.1fs" % (time.perf_counter() - t0))
    lbl = "weight" if a_.model == "logistic" else "importance"
    say("\n[4] %s" % lbl)
    for nm, v in r.describe():
        say("    %-34s %+7.3f  %s" % (nm, v, "#" * int(round(abs(v) * 18))))
    return r, dist, pred, tr, te


def evaluate(gamma, targets, policy, a_, lam, say=print):
    """Solve rate, mean expansions, and how often the returned length equals
    the geodesic.  The last column is the one that says whether a speedup cost
    you proof quality."""
    solved = opt = 0; exps = []; lens = []
    for t, d in targets:
        if policy.ranker is None:
            ln, exp = bfs_to(gamma, t, a_.max_size, a_.edge_cap, a_.budget)
        else:
            ln, exp = guided_search(gamma, t, policy, a_.max_size, a_.edge_cap,
                                    a_.budget, lam)
        exps.append(exp)
        if ln is not None:
            solved += 1; lens.append(ln)
            if ln == d: opt += 1
    n = len(targets)
    return dict(n=n, solved=solved, solve_rate=solved / n if n else 0.0,
                mean_exp=sum(exps) / len(exps) if exps else 0.0,
                mean_len=sum(lens) / len(lens) if lens else 0.0,
                optimal=opt, opt_rate=opt / solved if solved else 0.0)


def cmd_compare(a_):
    print("=" * 74)
    print("  PREDATOR_5 v%s  --  logistic vs forest vs breadth-first" % VERSION)
    print("  held-out targets only; policies never saw them in training")
    print("=" * 74)

    rows = []
    base = None
    for kind in ("logistic", "forest"):
        if kind == "forest" and not HAVE_SKLEARN:
            print("\n  [forest skipped: scikit-learn not installed]")
            continue
        print("\n" + "-" * 74)
        print("  MODEL: %s" % kind)
        print("-" * 74)
        a_.model = kind
        r, dist, pred, tr, te = cmd_train(a_, quiet=True)
        if base is None:
            print("\n[5] breadth-first benchmark on the same held-out targets")
            bfs = evaluate(GAMMA, te, Policy(None), a_, 0.0)
            base = bfs
            rows.append(("BFS (lam=0)", "geodesic, complete", bfs))
        for mode, k in (("reorder", None), ("prune", a_.k)):
            pol = Policy(r, mode, k or 8)
            ev = evaluate(GAMMA, te, pol, a_, a_.lam)
            rows.append(("%s %s%s" % (kind, mode,
                                      "" if k is None else " k=%d" % k),
                         pol.guarantee, ev))

    print("\n" + "=" * 74)
    print("  HELD-OUT RESULTS   (%d targets)" % base["n"])
    print("=" * 74)
    print("  %-22s %7s %9s %8s %9s  %s"
          % ("policy", "solved", "mean exp", "mean len", "optimal", "guarantee"))
    for label, guar, ev in rows:
        speed = (base["mean_exp"] / ev["mean_exp"]) if ev["mean_exp"] else 0.0
        print("  %-22s %6.0f%% %9.1f %8.2f %8.0f%%  %s"
              % (label, 100 * ev["solve_rate"], ev["mean_exp"],
                 ev["mean_len"], 100 * ev["opt_rate"], guar))
    print("\n  mean exp   nodes expanded to reach a target, lower is better")
    print("  optimal    share of solved targets whose returned length equals")
    print("             the geodesic.  Only the BFS row is optimal by theorem;")
    print("             every other row is optimal only by luck.")
    print("  guarantee  a prune row bought its speed by surrendering")
    print("             proof-covering.  That is not the same object as a")
    print("             reorder speedup and should not share a column with it.")
    if a_.out:
        json.dump({lab: ev for lab, _, ev in rows}, open(a_.out, "w"), indent=2)
        print("\n  wrote %s" % a_.out)


def cmd_doctor(_):
    print("Predator_5 v%s" % VERSION)
    print("  python    %s" % platform.python_version())
    print("  numpy     %s" % ("yes" if HAVE_NUMPY else "no  (logistic still works)"))
    print("  sklearn   %s" % ("yes" if HAVE_SKLEARN else
                              "no  -- needed for --model forest; "
                              "pip install scikit-learn"))
    print("\n  Gamma = %s" % ",  ".join(show(t) for t in GAMMA))
    print("  rule  = condensed detachment, one rule, MGU with occurs check")


def cmd_menu(_):
    print(__doc__.split("COMMANDS")[0])
    print("  1  harvest    sweep for targets and their true geodesics")
    print("  2  train      fit a policy (logistic or forest)")
    print("  3  compare    logistic vs forest vs BFS on held-out targets")
    print("  4  doctor     check this machine")
    print("  q  quit\n")
    try: ch = input("choose: ").strip().lower()
    except (EOFError, KeyboardInterrupt): return
    ns = argparse.Namespace(depth=4, max_size=14, edge_cap=15, state_budget=20000,
                            test_frac=0.3, seed=0, model="logistic", budget=400,
                            lam=0.5, k=6, max_pairs_per_target=4000,
                            n_estimators=300, max_depth=12, min_samples_leaf=4,
                            max_pairs=200000, out=None)
    if ch in ("1", "harvest"): cmd_harvest(ns)
    elif ch in ("2", "train"):
        ns.model = (input("model, logistic or forest [logistic]: ")
                    or "logistic").strip()
        cmd_train(ns)
    elif ch in ("3", "compare"): cmd_compare(ns)
    elif ch in ("4", "doctor"): cmd_doctor(ns)


def main():
    ap = argparse.ArgumentParser(prog="predator5", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--depth", type=int, default=4,
                       help="BFS sweep depth; targets found at layer d have "
                            "geodesic exactly d")
        p.add_argument("--max-size", type=int, default=14,
                       help="largest formula kept; bounds the branching")
        p.add_argument("--edge-cap", type=int, default=15,
                       help="edges enumerated per state; 0 = all")
        p.add_argument("--state-budget", type=int, default=20000)
        p.add_argument("--test-frac", type=float, default=0.3)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--budget", type=int, default=400,
                       help="node expansion budget per target at search time")
        p.add_argument("--lam", type=float, default=0.5,
                       help="heuristic weight; 0 = BFS = geodesic + complete")
        p.add_argument("-k", type=int, default=6, help="prune width")
        p.add_argument("--max-pairs-per-target", type=int, default=4000)
        p.add_argument("--n-estimators", type=int, default=300)
        p.add_argument("--max-depth", type=int, default=12)
        p.add_argument("--min-samples-leaf", type=int, default=4)
        p.add_argument("--max-pairs", type=int, default=200000)
        p.add_argument("--out", default=None, help="write results as JSON")

    h = sub.add_parser("harvest"); common(h)
    t = sub.add_parser("train");   common(t)
    t.add_argument("--model", choices=["logistic", "forest"], default="logistic")
    c = sub.add_parser("compare"); common(c)
    c.add_argument("--model", default="logistic", help=argparse.SUPPRESS)
    sub.add_parser("doctor")

    a_ = ap.parse_args()
    if getattr(a_, "edge_cap", None) == 0: a_.edge_cap = None
    if a_.cmd == "harvest":   cmd_harvest(a_)
    elif a_.cmd == "train":   cmd_train(a_)
    elif a_.cmd == "compare": cmd_compare(a_)
    elif a_.cmd == "doctor":  cmd_doctor(a_)
    else:                     cmd_menu(a_)


if __name__ == "__main__":
    main()
