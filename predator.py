#!/usr/bin/env python3
"""
Predator -- a trainable automated theorem prover.   Brian Tenneson, v1.1
btenneson2301.substack.com    Copyright (c) 2026.  All Rights Reserved.

ONE FILE.  NO INSTALL.  NO DEPENDENCIES REQUIRED.

    python predator.py                 <- run this.  It will explain itself.

Everything is in this file: the formal system, the theorem graph, the Metamath
reader, the prover, the training loop and the plots.  numpy and matplotlib are
used when present and worked around when absent, so the script runs on a bare
Python 3.8+ install with nothing added.

COMMANDS
    python predator.py               interactive menu
    python predator.py demo          quick end-to-end run (30 seconds)
    python predator.py train         train and evaluate, with options
    python predator.py fetch         download a real Metamath corpus
    python predator.py metamath      run against a downloaded .mm file
    python predator.py figures       write the plots (needs matplotlib)
    python predator.py doctor        check the environment
    python predator.py <cmd> --help  options for any command

WHERE OUTPUT GOES
    A folder stamped to the minute, e.g.  runs/2026-07-27_2114/
    Change it with  --outdir "C:\\path\\with spaces"  or by setting the
    environment variable PREDATOR_OUT.  Nothing is ever overwritten.
"""

from __future__ import annotations
import argparse, csv, datetime, json, math, os, platform, random, re, sys, time
from collections import defaultdict, deque

VERSION = "1.1"

# ===========================================================================
#  0.  NUMERICS  --  use numpy if it is here, otherwise plain Python
# ===========================================================================
try:
    import numpy as _np
    HAVE_NUMPY = True
except ImportError:
    _np = None
    HAVE_NUMPY = False


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def median(xs):
    xs = sorted(xs)
    if not xs:
        return 0.0
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def stdev(xs):
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def standardise(X):
    """Centre and scale each column; constant columns are left alone.

    The features have very different natural ranges -- a recency term divided
    by 1000 reaches 44 on a large corpus while the rest stay inside [0,1] --
    and an unstandardised fit is dominated by whichever feature carries the
    largest units.  Returns (Xz, mu, sigma)."""
    if not X:
        return [], [], []
    k = len(X[0])
    mu = [mean(r[j] for r in X) for j in range(k)]
    sg = [stdev([r[j] for r in X]) for j in range(k)]
    mu = [0.0 if s < 1e-12 else m for m, s in zip(mu, sg)]
    sg = [1.0 if s < 1e-12 else s for s in sg]
    return ([[(r[j] - mu[j]) / sg[j] for j in range(k)] for r in X], mu, sg)


def logistic_fit(X, y, epochs=400, lr=0.5, l2=1e-4, seed=0):
    """Logistic regression by gradient descent.  Returns (w, mu, sigma).

    Two implementations of the same arithmetic.  The inner loop runs
    epochs x examples x features times -- tens of millions of operations on a
    modest corpus -- which is fast in numpy and slow in pure Python, so numpy
    is used when it is present.  The pure-Python path exists so the script
    still runs with nothing installed; it gives identical results and takes
    perhaps fifty times longer to train."""
    Xz, mu, sg = standardise(X)
    if HAVE_NUMPY:
        Xa = _np.asarray(Xz, dtype=float); ya = _np.asarray(y, dtype=float)
        rng = _np.random.default_rng(seed)
        w = rng.normal(0, 0.01, Xa.shape[1]); m = len(ya)
        for _ in range(epochs):
            z = _np.clip(Xa @ w, -30, 30)
            p = 1.0 / (1.0 + _np.exp(-z))
            w -= lr * (Xa.T @ (p - ya) / m + l2 * w)
        return [float(v) for v in w], mu, sg
    rng = random.Random(seed)
    k = len(Xz[0])
    w = [rng.gauss(0, 0.01) for _ in range(k)]
    m = len(y)
    for _ in range(epochs):
        grad = [0.0] * k
        for xi, yi in zip(Xz, y):
            z = dot(xi, w)
            z = 30.0 if z > 30 else (-30.0 if z < -30 else z)
            e = 1.0 / (1.0 + math.exp(-z)) - yi
            for j in range(k):
                grad[j] += e * xi[j]
        for j in range(k):
            w[j] -= lr * (grad[j] / m + l2 * w[j])
    return w, mu, sg


def rank_desc(scores):
    """Indices ordered by descending score."""
    return sorted(range(len(scores)), key=lambda i: -scores[i])


# ===========================================================================
#  1.  THE THEOREM GRAPH
# ===========================================================================
class Node:
    __slots__ = ("name", "kind", "statement", "premises", "rule", "order",
                 "proof_steps")

    def __init__(self, name, kind, statement, premises=None, rule="",
                 order=0, proof_steps=0):
        self.name, self.kind, self.statement = name, kind, statement
        self.premises = premises or []
        self.rule, self.order, self.proof_steps = rule, order, proof_steps


class TheoremGraph:
    """Vertices are statements; an edge p -> q means p is a premise of q.

    NOT ACYCLIC IN GENERAL.  A formula-level consequence relation can return to
    its own axiom -- in Hofstadter's MIU system MI does so in five steps:
        MI -II-> MII -II-> MIIII -I-> MIIIIU -III-> MIUU -IV-> MI
    What is acyclic is the graph as BUILT here, because each statement is
    recorded once with premises already present, so every edge runs from lower
    to higher order.  closure_depth() is a fixpoint and does not rely on it."""

    def __init__(self):
        self.nodes, self.out = {}, defaultdict(list)
        self._topo = self._depth = self._plen = None

    def add(self, node):
        self.nodes[node.name] = node
        for p in node.premises:
            self.out[p].append(node.name)
        self._topo = self._depth = self._plen = None

    def topological_order(self):
        if self._topo is not None:
            return self._topo
        indeg = {n: 0 for n in self.nodes}
        for n, nd in self.nodes.items():
            for p in nd.premises:
                if p in self.nodes:
                    indeg[n] += 1
        q = deque(sorted(n for n, d in indeg.items() if d == 0))
        order = []
        while q:
            n = q.popleft(); order.append(n)
            for m in self.out.get(n, []):
                indeg[m] -= 1
                if indeg[m] == 0:
                    q.append(m)
        if len(order) != len(self.nodes):
            raise ValueError("graph is cyclic; use closure_depth() instead")
        self._topo = order
        return order

    def closure_depth(self, max_iter=10000):
        """delta(phi) = fewest rounds of D_F needed.  Fixpoint, so cycles are
        fine: a statement reachable only around a cycle keeps depth infinity."""
        if self._depth is not None:
            return self._depth
        INF = float("inf")
        depth = {}
        for n, nd in self.nodes.items():
            depth[n] = 0 if not [p for p in nd.premises if p in self.nodes] else INF
        for _ in range(max_iter):
            changed = False
            for n, nd in self.nodes.items():
                ps = [p for p in nd.premises if p in depth]
                if not ps:
                    continue
                c = max(depth[p] for p in ps)
                if c < INF and c + 1 < depth[n]:
                    depth[n] = c + 1; changed = True
            if not changed:
                break
        self._depth = depth
        return depth

    def ancestors(self, name):
        seen, stack = set(), [name]
        while stack:
            for p in self.nodes[stack.pop()].premises:
                if p in self.nodes and p not in seen:
                    seen.add(p); stack.append(p)
        return seen

    def proof_length(self, exact_limit=20000):
        """One topological pass with memoised ancestor sets; calling
        ancestors() per node would be O(V*E) and unusable on set.mm."""
        if self._plen is not None:
            return self._plen
        need = [n for n, nd in self.nodes.items() if nd.proof_steps <= 0]
        if not need:
            self._plen = {n: nd.proof_steps for n, nd in self.nodes.items()}
            return self._plen
        if len(self.nodes) > exact_limit:
            d = self.closure_depth()
            self._plen = {n: (nd.proof_steps if nd.proof_steps > 0 else
                              (int(d[n]) + 1 if d[n] != float("inf") else 1))
                          for n, nd in self.nodes.items()}
            return self._plen
        anc = {}
        for n in self.topological_order():
            s = set()
            for p in self.nodes[n].premises:
                if p in self.nodes:
                    s.add(p); s |= anc[p]
            anc[n] = s
        self._plen = {n: (nd.proof_steps if nd.proof_steps > 0 else len(anc[n]) + 1)
                      for n, nd in self.nodes.items()}
        return self._plen

    def summary(self):
        d = self.closure_depth()
        fin = [v for v in d.values() if v != float("inf")]
        return dict(nodes=len(self.nodes),
                    edges=sum(len(nd.premises) for nd in self.nodes.values()),
                    axioms=sum(1 for nd in self.nodes.values() if nd.kind == "axiom"),
                    theorems=sum(1 for nd in self.nodes.values() if nd.kind == "theorem"),
                    max_depth=max(fin) if fin else 0,
                    unreachable=len(d) - len(fin))


# ===========================================================================
#  2.  A FORMAL SYSTEM, AND THE BRUTE-FORCE MACHINE OVER IT
# ===========================================================================
class Hilbert:
    """Propositional Hilbert system: modus ponens plus two axiom schemes read
    as generating rules, instantiating on formulas already derived.

    Instantiating the schemes only at atoms makes the consequence set saturate
    after one round -- every instance is an implication whose antecedent is not
    separately available, so modus ponens never detaches."""

    def __init__(self, n_atoms=3, max_depth=6, max_formula_size=7, cap=2000,
                 scheme_arg_size=3, pool_cap=26, ternary_cap=9, seed=0):
        self.atoms = [chr(ord('p') + i) for i in range(n_atoms)]
        self.max_depth, self.max_formula_size, self.cap = max_depth, max_formula_size, cap
        self.scheme_arg_size, self.pool_cap, self.ternary_cap = scheme_arg_size, pool_cap, ternary_cap
        self.rng = random.Random(seed)

    @staticmethod
    def imp(a, b): return "(%s -> %s)" % (a, b)

    @staticmethod
    def size(f): return f.count("->") + 1

    @staticmethod
    def split_imp(f):
        if not (f.startswith("(") and f.endswith(")")):
            return None
        inner, depth = f[1:-1], 0
        for i, ch in enumerate(inner):
            if ch == "(": depth += 1
            elif ch == ")": depth -= 1
            elif ch == "-" and depth == 0 and inner[i:i + 2] == "->":
                return inner[:i].strip(), inner[i + 2:].strip()
        return None

    def consequences(self, formulas):
        """One round of D_F.  ORDER MATTERS and must match everywhere: the
        scheme pools are truncated, so which instances appear depends on which
        formulas sit at the front.  Sorting by (size, text) in every caller is
        what keeps a target drawn from the corpus reachable by the search."""
        formulas = sorted(formulas, key=lambda f: (self.size(f), f))
        have, out = set(formulas), []
        for f in formulas:
            sp = self.split_imp(f)
            if sp and sp[0] in have:
                out.append(sp[1])
        pool = [f for f in formulas if self.size(f) <= self.scheme_arg_size][: self.pool_cap]
        for A in pool:
            for B in pool:
                out.append(self.imp(A, self.imp(B, A)))
        sub = pool[: self.ternary_cap]
        for A in sub:
            for B in sub:
                for C in sub:
                    out.append(self.imp(self.imp(A, self.imp(B, C)),
                                        self.imp(self.imp(A, B), self.imp(A, C))))
        seen, ded = set(), []
        for f in out:
            if f not in seen and self.size(f) <= self.max_formula_size:
                seen.add(f); ded.append(f)
        return ded

    def build_corpus(self):
        """Runs C(G,1)=G, C(G,m+1)=D_F(C(G,m)) and records every derivation."""
        g, order, state = TheoremGraph(), 0, {}
        for a in self.atoms:
            g.add(Node("hyp_%d" % order, "axiom", a, [], "hyp", order))
            state[a] = "hyp_%d" % order; order += 1
        stages = [len(state)]
        for _ in range(self.max_depth):
            fresh = [f for f in self.consequences(list(state)) if f not in state]
            if not fresh:
                break
            for f in fresh:
                if f in state or len(state) >= self.cap:
                    continue
                prem, rule = self._explain(f, state)
                g.add(Node("th_%d" % order, "theorem", f, prem, rule, order))
                state[f] = "th_%d" % order; order += 1
            stages.append(len(state))
            if len(state) >= self.cap:
                break
        return g, stages

    def _explain(self, f, state):
        """Which rule and premises produced f, for the graph's edge labels."""
        sp = self.split_imp(f)
        if sp:
            A, rest = sp
            sr = self.split_imp(rest)
            if sr and sr[1] == A and A in state and sr[0] in state:
                return [state[A], state[sr[0]]], "ax1"
        for cand, nm in state.items():
            sc = self.split_imp(cand)
            if sc and sc[1] == f and sc[0] in state:
                return [state[sc[0]], nm], "mp"
        return [], "gen"


def brute_force_search(sys_, gamma, target, budget=60000):
    """The canonical rule-enumeration machine: adjoin EVERY direct consequence
    at each stage.  This is the benchmark Predator is measured against."""
    state, exp = {f: 0 for f in gamma}, 0
    for stage in range(1, 64):
        fresh = [f for f in sys_.consequences(list(state)) if f not in state]
        if not fresh:
            return dict(found=False, expansions=exp, stages=stage)
        for f in fresh:
            state[f] = stage; exp += 1
            if f == target:
                return dict(found=True, expansions=exp, stages=stage)
            if exp >= budget:
                return dict(found=False, expansions=exp, stages=stage)
    return dict(found=False, expansions=exp, stages=stage)


# ===========================================================================
#  3.  PREDATOR
# ===========================================================================
class Predator:
    """A tagged ATP.  Identical to the brute-force machine except that it scores
    the available consequences and keeps only the best `beam` of them."""

    FEATURES = ["bias", "token overlap", "goal covers cand", "cand in goal",
                "size mismatch", "cand size", "cand depth", "cand <= goal",
                "IS goal antecedent", "detaches TO goal", "goal in consequent",
                "IS goal consequent"]

    def __init__(self, tag="Predator_1", beam=8, seed=0):
        self.tag, self.beam, self.seed = tag, beam, seed
        self.w = self.mu = self.sigma = None
        self.trained_on = 0

    @staticmethod
    def features(goal, cand, depth, sys_):
        gt, ct = set(goal.split()), set(cand.split())
        inter = len(gt & ct); union = len(gt | ct) or 1
        gs, cs = sys_.size(goal), sys_.size(cand)
        sg = sys_.split_imp(goal); sc = sys_.split_imp(cand)
        g_ante, g_cons = sg if sg else (None, None)
        c_ante, c_cons = sc if sc else (None, None)
        return [1.0, inter / union, inter / (len(ct) or 1),
                1.0 if cand in goal else 0.0, abs(gs - cs) / 10.0, cs / 10.0,
                depth / 10.0, 1.0 if cs <= gs else 0.0,
                1.0 if (g_ante is not None and cand == g_ante) else 0.0,
                1.0 if (c_cons is not None and c_cons == goal) else 0.0,
                1.0 if (c_cons is not None and goal in c_cons) else 0.0,
                1.0 if (g_cons is not None and cand == g_cons) else 0.0]

    def score_rows(self, rows):
        if self.w is None:
            return [0.0] * len(rows)
        return [dot([(v - m) / s for v, m, s in zip(r, self.mu, self.sigma)], self.w)
                for r in rows]

    def train(self, g, train_names, sys_, n_neg=12):
        """Positives: statements actually used in a training target's proof.
        Negatives: HARD ones -- competitors available at the same depth that the
        proof passed over -- plus a few random, for contrast.  Random negatives
        alone make the task too easy, since most of a corpus is irrelevant to
        any goal and rejecting the obviously unrelated teaches nothing about
        choosing among plausible candidates."""
        rng = random.Random(self.seed)
        depth = g.closure_depth()
        order = sorted(g.nodes.values(), key=lambda nd: nd.order)
        pos_of = {nd.name: i for i, nd in enumerate(order)}
        X, y = [], []
        for nm in train_names:
            tgt, i = g.nodes[nm], pos_of[g.nodes[nm].name]
            if i < n_neg + 2:
                continue
            anc = g.ancestors(nm)
            if not anc:
                continue
            for a in anc:
                da = depth[a] if depth[a] != float("inf") else 0
                X.append(self.features(tgt.statement, g.nodes[a].statement, da, sys_))
                y.append(1)
            dt = depth[nm] if depth[nm] != float("inf") else 0
            comp = [c for c in order[:i] if c.name not in anc
                    and depth[c.name] != float("inf") and depth[c.name] <= dt]
            hard = rng.sample(comp, min(int(n_neg * .75), len(comp))) if comp else []
            easy, tries = [], 0
            while len(easy) < n_neg - len(hard) and tries < 8 * n_neg:
                tries += 1
                c = order[rng.randrange(i)]
                if c.name not in anc and c.name != nm:
                    easy.append(c)
            for c in hard + easy:
                dc = depth[c.name] if depth[c.name] != float("inf") else 0
                X.append(self.features(tgt.statement, c.statement, dc, sys_))
                y.append(0)
        if not y or sum(y) in (0, len(y)):
            raise ValueError("degenerate training set")
        self.w, self.mu, self.sigma = logistic_fit(X, y, seed=self.seed)
        self.trained_on = len(train_names)
        return dict(examples=len(y), positives=sum(y))

    def search(self, sys_, gamma, target, budget=60000):
        state, exp = {f: 0 for f in gamma}, 0
        for stage in range(1, 64):
            fresh = [f for f in sys_.consequences(list(state)) if f not in state]
            if not fresh:
                return dict(found=False, expansions=exp, stages=stage)
            if target in fresh:
                chosen = [target]
            else:
                rows = [self.features(target, f, stage, sys_) for f in fresh]
                chosen = [fresh[i] for i in rank_desc(self.score_rows(rows))[:self.beam]]
            for f in chosen:
                state[f] = stage; exp += 1
                if f == target:
                    return dict(found=True, expansions=exp, stages=stage)
                if exp >= budget:
                    return dict(found=False, expansions=exp, stages=stage)
        return dict(found=False, expansions=exp, stages=stage)

    def to_dict(self):
        return dict(tag=self.tag, beam=self.beam, seed=self.seed, version=VERSION,
                    trained_on=self.trained_on, features=self.FEATURES,
                    weights=self.w, mu=self.mu, sigma=self.sigma)

    @classmethod
    def from_dict(cls, d):
        p = cls(d["tag"], d["beam"], d["seed"])
        p.trained_on = d.get("trained_on", 0)
        p.w, p.mu, p.sigma = d.get("weights"), d.get("mu"), d.get("sigma")
        return p


def evaluate(sys_, gamma, targets, pred, budget=60000):
    """Two numbers, always together.  Solve rate over ALL targets; effort ratio
    over JOINTLY solved ones only -- a ratio taken over targets Predator
    abandoned would reward abandoning them.  Wall clock beside expansions,
    because the two can point in opposite directions."""
    rows = []
    for t in targets:
        a = time.perf_counter(); bf = brute_force_search(sys_, gamma, t, budget)
        bt = time.perf_counter() - a
        a = time.perf_counter(); pr = pred.search(sys_, gamma, t, budget)
        pt = time.perf_counter() - a
        rows.append(dict(target=t, bf_found=bf["found"], bf_exp=bf["expansions"],
                         bf_stages=bf["stages"], bf_sec=bt,
                         pr_found=pr["found"], pr_exp=pr["expansions"],
                         pr_stages=pr["stages"], pr_sec=pt))
    both = [r for r in rows if r["bf_found"] and r["pr_found"]]
    ratios = [r["pr_exp"] / max(r["bf_exp"], 1) for r in both]
    bt = sum(r["bf_sec"] for r in both); pt = sum(r["pr_sec"] for r in both)
    be = sum(r["bf_exp"] for r in both); pe = sum(r["pr_exp"] for r in both)
    return dict(n_targets=len(rows),
                bf_solved=sum(1 for r in rows if r["bf_found"]),
                pr_solved=sum(1 for r in rows if r["pr_found"]),
                bf_solve_rate=sum(1 for r in rows if r["bf_found"]) / max(len(rows), 1),
                pr_solve_rate=sum(1 for r in rows if r["pr_found"]) / max(len(rows), 1),
                n_jointly_solved=len(both),
                effort_ratio_mean=mean(ratios) if ratios else None,
                effort_ratio_median=median(ratios) if ratios else None,
                speedup_mean=mean([1 / r for r in ratios]) if ratios else None,
                depth_floor_breaches=sum(1 for r in both if r["pr_stages"] < r["bf_stages"]),
                bf_seconds=bt, pr_seconds=pt,
                time_speedup=(bt / pt) if pt > 0 else None,
                us_per_exp_bf=1e6 * bt / max(be, 1), us_per_exp_pr=1e6 * pt / max(pe, 1),
                rows=rows)


# ===========================================================================
#  4.  METAMATH
# ===========================================================================
MM_URLS = {
    "iset.mm": "https://raw.githubusercontent.com/metamath/set.mm/develop/iset.mm",
    "set.mm":  "https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm",
    "nf.mm":   "https://raw.githubusercontent.com/metamath/set.mm/develop/nf.mm",
    "ql.mm":   "https://raw.githubusercontent.com/metamath/set.mm/develop/ql.mm",
}


def parse_metamath(path, limit=None):
    """A Metamath proof is a list of label references, so the dependency edges
    are written in the file and no proof reconstruction is needed."""
    txt = re.sub(r"\$\(.*?\$\)", " ", open(path, encoding="utf-8",
                                           errors="replace").read(), flags=re.S)
    toks = txt.split()
    g, known, i, order = TheoremGraph(), set(), 0, 0
    while i < len(toks):
        t = toks[i]
        if i + 1 < len(toks) and toks[i + 1] in ("$a", "$p"):
            try:
                j = toks.index("$.", i)
            except ValueError:
                break
            if toks[i + 1] == "$a":
                g.add(Node(t, "axiom", " ".join(toks[i + 2:j]), [], "axiom", order))
            else:
                body = toks[i + 2:j]
                k = body.index("$=") if "$=" in body else len(body)
                stmt, proof = body[:k], body[k + 1:]
                if proof and proof[0] == "(":
                    try:
                        e = proof.index(")"); refs = proof[1:e]
                        steps = max(1, len(proof) - e - 1)
                    except ValueError:
                        refs, steps = [], 1
                else:
                    refs, steps = proof, len(proof)
                prem = [r for r in dict.fromkeys(refs) if r in known]
                nd = Node(t, "theorem", " ".join(stmt), prem, "mm", order)
                nd.proof_steps = max(steps, len(prem) + 1)
                g.add(nd)
            known.add(t); order += 1; i = j + 1
            if limit and order >= limit:
                break
            continue
        i += 1
    return g


def fetch(name="iset.mm", dest=None):
    import urllib.request
    if name not in MM_URLS:
        raise SystemExit("unknown corpus %r; choose from %s" % (name, ", ".join(MM_URLS)))
    dest = dest or name
    print("downloading %s ..." % MM_URLS[name])
    urllib.request.urlretrieve(MM_URLS[name], dest)
    print("saved to %s (%.1f MB)" % (dest, os.path.getsize(dest) / 1e6))
    return dest


# ===========================================================================
#  5.  RUN ARTIFACTS
# ===========================================================================
class Run:
    """A fresh directory stamped to the minute.  A numeric suffix is appended
    if one of that minute exists, so nothing is ever overwritten."""

    def __init__(self, base=None):
        base = base or os.environ.get("PREDATOR_OUT", "runs")
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        path = os.path.join(base, stamp)
        k = 2
        while os.path.exists(path):
            path = os.path.join(base, "%s_%d" % (stamp, k)); k += 1
        os.makedirs(path, exist_ok=True)
        self.dir, self.stamp, self.lines = path, stamp, []

    def p(self, name): return os.path.join(self.dir, name)

    def log(self, *a):
        s = " ".join(str(x) for x in a); print(s); self.lines.append(s)

    def finish(self, results, g=None, pred=None, args=None):
        json.dump(dict(version=VERSION,
                       timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
                       python=platform.python_version(), numpy=HAVE_NUMPY,
                       platform=platform.platform(),
                       arguments=vars(args) if args else {}),
                  open(self.p("manifest.json"), "w"), indent=2)
        json.dump(results, open(self.p("results.json"), "w"), indent=2, default=str)
        if pred is not None:
            json.dump(pred.to_dict(), open(self.p("predator_1.json"), "w"), indent=2)
        if g is not None:
            d, L = g.closure_depth(), g.proof_length()
            with open(self.p("nodes.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["name", "kind", "rule", "order", "closure_depth",
                            "proof_length", "n_premises", "statement"])
                for nm in sorted(g.nodes, key=lambda x: g.nodes[x].order):
                    nd = g.nodes[nm]
                    w.writerow([nd.name, nd.kind, nd.rule, nd.order,
                                "" if d[nm] == float("inf") else d[nm],
                                L[nm], len(nd.premises), nd.statement])
            with open(self.p("edges.csv"), "w", newline="") as f:
                w = csv.writer(f); w.writerow(["premise", "conclusion", "rule"])
                for nm, nd in g.nodes.items():
                    for p in nd.premises:
                        w.writerow([p, nm, nd.rule])
        open(self.p("run.log"), "w").write("\n".join(self.lines) + "\n")
        self.log("\nartifacts in %s/" % self.dir)
        for f in sorted(os.listdir(self.dir)):
            self.log("   ", f)


# ===========================================================================
#  6.  COMMANDS
# ===========================================================================
def cmd_train(a):
    run = None if a.no_artifacts else Run(a.outdir)
    say = run.log if run else print
    say("=" * 70)
    say("  PREDATOR v%s   Brian Tenneson   btenneson2301.substack.com" % VERSION)
    if run:
        say("  output: %s" % run.dir)
    say("=" * 70)

    sys_ = Hilbert(max_depth=a.depth, cap=a.cap, seed=a.seed)
    g, stages = sys_.build_corpus()
    gamma = [nd.statement for nd in g.nodes.values() if nd.kind == "axiom"]
    say("\n[1] Corpus built by brute-force closure")
    say("    %d statements; stage sizes |D_F^(m-1)(G)| = %s" % (len(g.nodes), stages))

    th = sorted([nd for nd in g.nodes.values() if nd.kind == "theorem"],
                key=lambda n: n.order)
    cut = int(len(th) * a.p)
    train, test = th[:cut], th[cut:]
    say("\n[2] Temporal split at p = %.2f  (train on the past, test on the future)" % a.p)
    say("    train %d   held out %d" % (len(train), len(test)))

    pred = Predator(beam=a.beam, seed=a.seed)
    t0 = time.perf_counter()
    info = pred.train(g, [nd.name for nd in train], sys_, n_neg=a.n_neg)
    tt = time.perf_counter() - t0
    say("\n[3] Training <%s>" % pred.tag)
    say("    %d examples, %d positive; %.2fs" % (info["examples"], info["positives"], tt))
    top = sorted(zip(Predator.FEATURES, pred.w), key=lambda kv: -abs(kv[1]))[:4]
    say("    heaviest weights: " + ", ".join("%s %+.2f" % (k, v) for k, v in top))

    d = g.closure_depth()
    rng = random.Random(a.seed)
    pool = [nd for nd in test if d[nd.name] != float("inf") and d[nd.name] >= 2]
    tg = [nd.statement for nd in rng.sample(pool, min(a.n_test, len(pool)))]
    say("\n[4] Proving %d held-out targets (beam %d, budget %d)" % (len(tg), a.beam, a.budget))
    ev = evaluate(sys_, gamma, tg, pred, a.budget)

    say("\n[5] Results")
    say("    solve rate     brute %5.1f%%   Predator %5.1f%%   (jointly %d)"
        % (100 * ev["bf_solve_rate"], 100 * ev["pr_solve_rate"], ev["n_jointly_solved"]))
    if ev["effort_ratio_mean"] is not None:
        say("    EXPANSIONS   ratio %.4f  ->  %.1fx fewer  (hardware independent)"
            % (ev["effort_ratio_mean"], ev["speedup_mean"]))
        say("    WALL CLOCK   brute %.2fs  Predator %.2fs  ->  %.2fx%s"
            % (ev["bf_seconds"], ev["pr_seconds"], ev["time_speedup"],
               "   SLOWER" if ev["time_speedup"] < 1 else ""))
        say("    per expansion  brute %.0fus   Predator %.0fus   (%.0fx overhead)"
            % (ev["us_per_exp_bf"], ev["us_per_exp_pr"],
               ev["us_per_exp_pr"] / max(ev["us_per_exp_bf"], 1e-9)))
        bfp = ev["bf_seconds"] / max(ev["n_jointly_solved"], 1)
        prp = ev["pr_seconds"] / max(ev["n_jointly_solved"], 1)
        say("    break-even     %s" % ("N* = %.0f proofs" % (tt / (bfp - prp))
                                       if prp < bfp else
                                       "never at this scale (Predator slower per proof)"))
    say("    depth-floor breaches %d  (must be 0)" % ev["depth_floor_breaches"])
    if run:
        run.finish(dict(split=dict(p=a.p), training=info, evaluation=ev), g, pred, a)
    return ev


def cmd_metamath(a):
    if not os.path.exists(a.db):
        raise SystemExit("no such file: %s\nRun:  python predator.py fetch" % a.db)
    run = None if a.no_artifacts else Run(a.outdir)
    say = run.log if run else print
    say("Parsing %s ..." % a.db)
    g = parse_metamath(a.db, a.limit)
    s = g.summary()
    say("  %(nodes)d statements, %(edges)d edges, max closure depth %(max_depth)s" % s)
    d, L = g.closure_depth(), g.proof_length()
    below = [n for n in g.nodes if d[n] != float("inf") and L[n] < d[n] + 1]
    say("  compilation events: %d of %d" % (len(below), len(g.nodes)))
    say("    (a Metamath step may CITE an earlier theorem instead of re-deriving")
    say("     it, so its length is measured in F^D while depth is measured in F.")
    say("     These are not errors; they measure how much lemma reuse buys.)")
    if run:
        run.finish(dict(summary=s, compilation_events=len(below)), g, None, a)


def cmd_figures(a):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit("figures need matplotlib:  pip install matplotlib")
    out = a.outdir or "."
    os.makedirs(out, exist_ok=True)
    sys_ = Hilbert(max_depth=a.depth, cap=a.cap, seed=a.seed)
    g, _ = sys_.build_corpus()
    gamma = [nd.statement for nd in g.nodes.values() if nd.kind == "axiom"]
    th = sorted([nd for nd in g.nodes.values() if nd.kind == "theorem"], key=lambda n: n.order)
    cut = int(len(th) * a.p); train, test = th[:cut], th[cut:]
    pred = Predator(beam=a.beam, seed=a.seed)
    pred.train(g, [nd.name for nd in train], sys_)
    d = g.closure_depth()
    plt.rcParams.update({"font.size": 9, "font.family": "serif", "figure.dpi": 150,
                         "axes.spines.top": False, "axes.spines.right": False})

    tgt = max((n for n in test if d[n.name] != float("inf")),
              key=lambda n: d[n.name]).statement
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for ax, mode in zip(axes, ["brute", "predator"]):
        state, sizes = {f: 0 for f in gamma}, []
        for stage in range(1, 8):
            fresh = [f for f in sys_.consequences(list(state)) if f not in state]
            if not fresh: break
            if mode == "predator" and tgt not in fresh:
                rows = [pred.features(tgt, f, stage, sys_) for f in fresh]
                fresh = [fresh[i] for i in rank_desc(pred.score_rows(rows))[:pred.beam]]
            for f in fresh: state[f] = stage
            sizes.append(len(fresh))
            if tgt in state: break
        ax.bar(range(1, len(sizes) + 1), sizes, width=.62,
               color="#b0b0b0" if mode == "brute" else "#2166A8")
        ax.set_yscale("log"); ax.set_xlabel("stage"); ax.set_ylim(.7, 3000)
        ax.set_title("brute force: all of $D_F$" if mode == "brute"
                     else "Predator: top %d" % pred.beam, fontsize=9)
        if mode == "brute": ax.set_ylabel("formulas adjoined")
    fig.suptitle("What each prover materialises on the way to one target", fontsize=9.5)
    fig.tight_layout(); fig.savefig(os.path.join(out, "fig_frontier.pdf")); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    cols = ["#2166A8" if v > 0 else "#B03030" for v in pred.w]
    ax.barh(range(len(pred.w)), pred.w, color=cols)
    ax.set_yticks(range(len(pred.w))); ax.set_yticklabels(Predator.FEATURES, fontsize=7.5)
    ax.axvline(0, color="k", lw=.8); ax.invert_yaxis(); ax.axhline(7.5, color=".5", ls=":", lw=1)
    ax.set_xlabel("learned weight (standardised)")
    ax.set_title("What Predator learned: surface (top 8) vs structural (bottom 4)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(out, "fig_weights.pdf")); plt.close(fig)
    print("figures written to %s/" % out)


def cmd_doctor(a):
    print("Predator v%s" % VERSION)
    print("  python     %s  (%s)" % (platform.python_version(), sys.executable))
    print("  platform   %s" % platform.platform())
    print("  numpy      %s" % ("yes" if HAVE_NUMPY else "no  (not needed)"))
    try:
        import matplotlib; mpl = "yes"
    except ImportError:
        mpl = "no  (only needed for 'figures')"
    print("  matplotlib %s" % mpl)
    print("  output dir %s" % (os.environ.get("PREDATOR_OUT") or "runs  (set PREDATOR_OUT to change)"))
    for f in MM_URLS:
        if os.path.exists(f):
            print("  corpus     %s present (%.1f MB)" % (f, os.path.getsize(f) / 1e6))
    t = time.perf_counter()
    s = Hilbert(max_depth=3, cap=200); gg, _ = s.build_corpus()
    print("  self-test  built %d statements in %.2fs -- OK" % (len(gg.nodes), time.perf_counter() - t))


def cmd_menu(_):
    print(__doc__.split("COMMANDS")[0])
    print("  1  demo        quick end-to-end run, about 30 seconds")
    print("  2  train       train and evaluate, with options")
    print("  3  fetch       download a real Metamath corpus (needs internet)")
    print("  4  figures     write the plots (needs matplotlib)")
    print("  5  doctor      check this machine")
    print("  q  quit\n")
    try:
        c = input("choose: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    ns = argparse.Namespace(p=.9, beam=8, budget=60000, n_test=20, n_neg=12,
                            depth=5, cap=1200, seed=0, outdir=None,
                            no_artifacts=False, db="iset.mm", limit=6000)
    if c in ("1", "demo"):
        ns.n_test = 12; ns.depth = 5; ns.cap = 900; cmd_train(ns)
    elif c in ("2", "train"):
        try:
            ns.p = float(input("training fraction p [0.9]: ") or .9)
            ns.beam = int(input("beam width [8]: ") or 8)
            ns.n_test = int(input("held-out targets [20]: ") or 20)
        except ValueError:
            print("using defaults")
        cmd_train(ns)
    elif c in ("3", "fetch"):
        which = input("which corpus %s [iset.mm]: " % list(MM_URLS)) or "iset.mm"
        fetch(which.strip())
    elif c in ("4", "figures"):
        ns.outdir = input("folder for figures [.]: ") or "."
        cmd_figures(ns)
    elif c in ("5", "doctor"):
        cmd_doctor(ns)


def main():
    ap = argparse.ArgumentParser(
        prog="predator", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p, **kw):
        p.add_argument("-p", type=float, default=kw.get("p", .9), help="training fraction")
        p.add_argument("--beam", type=int, default=8, help="consequences kept per stage")
        p.add_argument("--budget", type=int, default=60000, help="node cap per proof")
        p.add_argument("--n-test", type=int, default=kw.get("n_test", 20))
        p.add_argument("--n-neg", type=int, default=12)
        p.add_argument("--depth", type=int, default=kw.get("depth", 5))
        p.add_argument("--cap", type=int, default=kw.get("cap", 1200))
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--outdir", default=os.environ.get("PREDATOR_OUT"),
                       help='where runs go; a folder stamped to the minute is '
                            'made inside it.  Quote paths with spaces.')
        p.add_argument("--no-artifacts", action="store_true")
        return p

    common(sub.add_parser("train", help="train and evaluate"))
    common(sub.add_parser("demo", help="quick end-to-end run"), n_test=12, cap=900)
    common(sub.add_parser("figures", help="write plots (needs matplotlib)"))
    d = sub.add_parser("metamath", help="run against a .mm corpus")
    d.add_argument("--db", default="iset.mm"); d.add_argument("--limit", type=int, default=6000)
    d.add_argument("--outdir", default=os.environ.get("PREDATOR_OUT"))
    d.add_argument("--no-artifacts", action="store_true")
    f = sub.add_parser("fetch", help="download a Metamath corpus")
    f.add_argument("name", nargs="?", default="iset.mm", choices=list(MM_URLS))
    f.add_argument("--dest")
    sub.add_parser("doctor", help="check the environment")

    a = ap.parse_args()
    if a.cmd in (None,):
        cmd_menu(a)
    elif a.cmd in ("train", "demo"):
        cmd_train(a)
    elif a.cmd == "metamath":
        cmd_metamath(a)
    elif a.cmd == "figures":
        cmd_figures(a)
    elif a.cmd == "fetch":
        fetch(a.name, a.dest)
    elif a.cmd == "doctor":
        cmd_doctor(a)


if __name__ == "__main__":
    main()
