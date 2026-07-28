#!/usr/bin/env python3
"""
ml_sic_atp.py  --  Labeled theorem graphs, closure depth, and premise selection
                   in the SIC-ATP framework.

Brian Tenneson.  Companion code to
"Learned Search Policies for Proof Search" (ML-SIC-ATP-Theory, v001).

WHAT THIS DOES
--------------
Builds a *labeled theorem graph* -- vertices are statements, edges run from a
premise to a conclusion, edge labels name the inference rule -- and then:

  1. computes closure depth  delta_F(Gamma, phi)  and proof length  ||phi||,
  2. empirically checks the theorem  delta_F(Gamma,phi) + 1 <= ||phi||_F(Gamma),
  3. measures the breadth ratio  |p_m| / |D_F^{m-1}(Gamma)|,
  4. trains and tests a premise-selection policy under a TEMPORAL split.

Two data sources, one downstream pipeline:

  --mode synth      Runs the canonical rule-enumeration SIC E_{F,Y} on a
                    propositional Hilbert system.  Every proof is genuinely
                    searched for, so delta and ||.|| are exact ground truth.
                    No network needed.

  --mode miu        Builds Hofstadter's MIU system, whose consequence relation
                    is CYCLIC -- MI returns to itself in five steps.  Present as
                    a standing check that nothing here assumes acyclicity.

  --mode metamath   Parses a real Metamath database (.mm).  Metamath is the
                    recommended real corpus: every proof is literally a list of
                    label references, so the dependency DAG needs no NLP.
                    Databases, smallest first:  ql.mm < nf.mm < iset.mm < set.mm
                    (set.mm holds ~43,900 proved theorems).
                    Get one with:
                      curl -O https://raw.githubusercontent.com/metamath/set.mm/develop/iset.mm
                    then:  python3 ml_sic_atp.py --mode metamath --db iset.mm

ARTIFACTS
---------
Each run writes to a fresh directory stamped to the minute, e.g.
runs/2026-07-27_1843/, holding manifest.json (arguments, versions, host),
run.log, results.json, nodes.csv and edges.csv.  A numeric suffix is appended
if a directory of that minute already exists, so nothing is overwritten.
Suppress with --no-artifacts; relocate with --outdir.

DEPENDENCIES
------------
numpy only.  Graph algorithms and logistic regression are implemented here so
the script runs on a bare Python install.

LICENCE
-------
Copyright (c) 2026 Brian Tenneson.  All Rights Reserved.
btenneson2301.substack.com
"""

from __future__ import annotations
import argparse, math, random, re, sys, json, csv, os, platform, datetime
from collections import defaultdict, deque
from dataclasses import dataclass, field
import numpy as np


# ============================================================================
# 1.  THE LABELED THEOREM GRAPH
# ============================================================================

@dataclass
class Node:
    """One statement in the theorem graph."""
    name: str
    kind: str                      # 'axiom' | 'theorem'
    statement: str                 # the formula, as a token string
    premises: list = field(default_factory=list)   # names of nodes used
    rule: str = ""                 # edge label: which rule produced it
    order: int = 0                 # position in the corpus (for temporal split)
    proof_steps: int = 0           # linear proof length, if known from source


class TheoremGraph:
    """
    Vertices are statements; an edge  p -> q  means p is a premise of q.
    Edge labels are inference-rule names.

    THIS GRAPH IS NOT ACYCLIC IN GENERAL.  The formula-level consequence
    relation of a formal system can and does contain cycles.  In Hofstadter's
    MIU system, for instance,

        MI --II--> MII --II--> MIIII --I--> MIIIIU --III--> MIUU --IV--> MI

    returns to its own starting formula in five steps, and the two-step cycle
    MUU -> MUUUU -> MUU is shorter still.  Any construction here that needs
    acyclicity must therefore either establish it or avoid needing it.

    What IS acyclic is the graph as BUILT by this module, for a specific
    reason: each formula is recorded once, at its first derivation, with
    premises that were already present.  Every edge therefore runs from a lower
    to a higher `order`, which forbids cycles.  The same holds for a parsed
    Metamath database, where a proof may cite only earlier theorems.  Acyclicity
    is a property of the recording discipline, not of the underlying relation.

    Accordingly `topological_order` is available but optional, and
    `closure_depth` does not use it: the depth computation below is a
    fixpoint iteration that terminates on cyclic input as well.
    """

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.out: dict[str, list] = defaultdict(list)   # premise -> [conclusions]
        self._topo: list | None = None
        self._depth: dict | None = None
        self._plen: dict | None = None
        self.plen_exact: bool = True

    def add(self, node: Node):
        self.nodes[node.name] = node
        for p in node.premises:
            self.out[p].append(node.name)
        self._topo = self._depth = self._plen = None    # invalidate caches

    # ---- basic graph algorithms (no networkx) ----------------------------

    def topological_order(self) -> list:
        """Kahn's algorithm.  Raises if the graph has a cycle."""
        if self._topo is not None:
            return self._topo
        indeg = {n: 0 for n in self.nodes}
        for n, nd in self.nodes.items():
            for p in nd.premises:
                if p in self.nodes:
                    indeg[n] += 1
        q = deque(sorted([n for n, d in indeg.items() if d == 0]))
        order = []
        while q:
            n = q.popleft()
            order.append(n)
            for m in self.out.get(n, []):
                indeg[m] -= 1
                if indeg[m] == 0:
                    q.append(m)
        if len(order) != len(self.nodes):
            raise ValueError(
                f"the graph is cyclic: ordered {len(order)} of {len(self.nodes)}. "
                "This is legitimate -- formula-level consequence relations may "
                "contain cycles (see the class docstring) -- so use "
                "closure_depth(), which does not require a topological order.")
        self._topo = order
        return order

    def closure_depth(self, max_iter: int = 10000) -> dict:   # cached
        """
        delta_F(Gamma, phi) = min m with phi in D_F^m(Gamma).

        One round of D_F fires every available rule at once, so a statement is
        available at round 1 + max(rounds of its premises): every premise must
        be present before the rule applies.  Minimising over the available
        derivations gives delta.

        Computed as a fixpoint rather than by topological order, so that cyclic
        inputs are handled: depths start at infinity, statements with no
        premises start at 0, and the min-max relaxation is iterated to
        stability.  A statement reachable only through a cycle keeps depth
        infinity, which is correct -- it is never actually derived.
        """
        if self._depth is not None:
            return self._depth
        INF = float("inf")
        # A node counts as a leaf when it has no premises IN THIS GRAPH.  Having
        # premises that were never recorded (a Metamath proof citing a syntactic
        # hypothesis, say) must not leave it stranded at infinity.
        depth = {}
        for n, nd in self.nodes.items():
            usable = [p for p in nd.premises if p in self.nodes]
            depth[n] = 0 if not usable else INF
        for _ in range(max_iter):
            changed = False
            for n, nd in self.nodes.items():
                ps = [p for p in nd.premises if p in depth]
                if not ps:
                    continue
                cand = max(depth[p] for p in ps)
                if cand < INF and cand + 1 < depth[n]:
                    depth[n] = cand + 1
                    changed = True
            if not changed:
                break
        self._depth = depth
        return depth

    def ancestors(self, name: str) -> set:
        """All statements transitively used in proving `name`."""
        seen, stack = set(), [name]
        while stack:
            cur = stack.pop()
            for p in self.nodes[cur].premises:
                if p in self.nodes and p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    def proof_length(self, exact_limit: int = 20000) -> dict:
        """
        ||phi||_F(Gamma), the length of a shortest linear proof.

        A linear proof must list every distinct statement it uses, so for the
        recorded derivation the length is |ancestors(phi)| + 1.  Where the
        source supplies a real step count -- Metamath does -- that is used
        instead and no ancestor computation is needed.

        Computed in ONE topological pass with memoised ancestor sets.  Calling
        ancestors() per node instead would traverse the graph once per vertex,
        which is O(V*E) and unusable on a corpus the size of set.mm.

        Above `exact_limit` vertices the exact ancestor sets are too large to
        hold in memory, so the closure depth plus one is reported instead.  That
        is a lower bound on the true length, and the fact is recorded in
        `self.plen_exact` so callers can say which they have.
        """
        if self._plen is not None:
            return self._plen

        need = [n for n, nd in self.nodes.items() if nd.proof_steps <= 0]
        if not need:                                  # e.g. a Metamath corpus
            self.plen_exact = True
            self._plen = {n: nd.proof_steps for n, nd in self.nodes.items()}
            return self._plen

        if len(self.nodes) > exact_limit:
            self.plen_exact = False
            d = self.closure_depth()
            self._plen = {
                n: (nd.proof_steps if nd.proof_steps > 0
                    else (int(d[n]) + 1 if d[n] != float("inf") else 1))
                for n, nd in self.nodes.items()}
            return self._plen

        self.plen_exact = True
        anc: dict[str, set] = {}
        for n in self.topological_order():            # premises first
            s: set = set()
            for p in self.nodes[n].premises:
                if p in self.nodes:
                    s.add(p)
                    s |= anc[p]
            anc[n] = s
        self._plen = {n: (nd.proof_steps if nd.proof_steps > 0
                          else len(anc[n]) + 1)
                      for n, nd in self.nodes.items()}
        return self._plen

    def usage_counts(self) -> dict:
        c = defaultdict(int)
        for nd in self.nodes.values():
            for p in nd.premises:
                c[p] += 1
        return c

    def summary(self) -> dict:
        d = self.closure_depth()
        fin = [v for v in d.values() if v != float("inf")]
        return dict(
            nodes=len(self.nodes),
            edges=sum(len(nd.premises) for nd in self.nodes.values()),
            axioms=sum(1 for nd in self.nodes.values() if nd.kind == "axiom"),
            theorems=sum(1 for nd in self.nodes.values() if nd.kind == "theorem"),
            max_depth=max(fin) if fin else 0,
            unreachable=len(d) - len(fin),
        )


# ============================================================================
# 2.  DATA SOURCE A -- run the canonical SIC on a real formal system
# ============================================================================

class PropositionalSIC:
    """
    A concrete formal system F = (x, y, z) and the canonical rule-enumeration
    SIC E_{F,Y} over it.

    Formulas are implications built from atoms.  The single rule is modus
    ponens, a binary partial function.  Running the SIC forward from the axiom
    set produces genuine proofs -- each new formula records the rule and the
    exact premises that produced it -- so closure depth and proof length are
    ground truth rather than estimates.
    """

    def __init__(self, n_atoms=3, max_depth=6, max_formula_size=7, cap=4000,
                 scheme_arg_size=3, pool_cap=26, ternary_cap=9,
                 per_round=4000, seed=0):
        self.atoms = [chr(ord('p') + i) for i in range(n_atoms)]
        self.max_depth = max_depth
        self.max_formula_size = max_formula_size
        self.cap = cap
        self.scheme_arg_size = scheme_arg_size   # only instantiate on small args
        self.pool_cap = pool_cap                 # cap binary scheme pool
        self.ternary_cap = ternary_cap           # cap ternary scheme pool
        self.per_round = per_round               # work budget per stage
        self.rng = random.Random(seed)

    # -- syntax -----------------------------------------------------------
    @staticmethod
    def imp(a, b):  return f"({a} -> {b})"

    @staticmethod
    def size(f):    return f.count("->") + 1

    @staticmethod
    def split_imp(f):
        """If f is (A -> B) return (A, B), else None.  Paren-matching split."""
        if not (f.startswith("(") and f.endswith(")")):
            return None
        inner, depth = f[1:-1], 0
        for i, ch in enumerate(inner):
            if ch == "(":   depth += 1
            elif ch == ")": depth -= 1
            elif ch == "-" and depth == 0 and inner[i:i+2] == "->":
                return inner[:i].strip(), inner[i+2:].strip()
        return None

    def schemes(self):
        """
        The axiom schemes, as generating rules.

        A Hilbert system's axioms are schemes: (A -> (B -> A)) is an axiom for
        EVERY pair of formulas A, B, not merely for atoms.  Modelling them as
        rules that instantiate on formulas already derived is what a real
        prover does, and it is what makes the consequence set deep rather than
        saturating after one round.  Each is a finitary rule in the sense of
        Definition (finitary rule), so F = (x, y, z) is well formed.
        """
        return {
            "ax1": (2, lambda A, B: self.imp(A, self.imp(B, A))),
            "ax2": (3, lambda A, B, C: self.imp(self.imp(A, self.imp(B, C)),
                                                self.imp(self.imp(A, B),
                                                         self.imp(A, C)))),
        }

    # -- the SIC ----------------------------------------------------------
    def run(self) -> tuple[TheoremGraph, list]:
        """
        Executes  C(Gamma,1) = Gamma,  C(Gamma,m+1) = D_F(C(Gamma,m)).

        Gamma is the atom set.  Each round applies every rule to every
        available tuple, subject to a formula-size bound that keeps Y finite,
        and records for each new formula the rule and the exact premises that
        produced it.  Those records are the labelled edges of the theorem
        graph, and they make closure depth and proof length ground truth
        rather than estimates.

        Returns the graph and the stage sizes |C(Gamma,m)| = |D_F^(m-1)(Gamma)|,
        the denominator of the breadth ratio.
        """
        g = TheoremGraph()
        order = 0
        state: dict[str, str] = {}          # formula -> node name

        for a in self.atoms:                # Gamma
            nm = f"hyp_{order}"
            g.add(Node(nm, "axiom", a, [], "hyp", order))
            state[a] = nm
            order += 1

        stage_sizes = [len(state)]
        schemes = self.schemes()

        for m in range(self.max_depth):
            have = list(state.keys())
            have.sort(key=lambda f: (self.size(f), f))
            small = [f for f in have if self.size(f) <= self.scheme_arg_size]
            new: list[tuple] = []
            seen_new: set[str] = set()

            def offer(formula, prem, rule):
                if (formula in state or formula in seen_new
                        or self.size(formula) > self.max_formula_size):
                    return False
                seen_new.add(formula)
                new.append((formula, prem, rule))
                return len(new) + len(state) < self.cap

            # -- scheme instantiation --------------------------------------
            budget = self.per_round
            for name, (ar, fn) in schemes.items():
                pool = small[: self.pool_cap]
                if ar == 2:
                    for A in pool:
                        for B in pool:
                            if budget <= 0: break
                            if not offer(fn(A, B), [state[A], state[B]], name):
                                if len(new) + len(state) >= self.cap: break
                            budget -= 1
                        if budget <= 0: break
                else:
                    sub = pool[: self.ternary_cap]
                    for A in sub:
                        for B in sub:
                            for C in sub:
                                if budget <= 0: break
                                if not offer(fn(A, B, C),
                                             [state[A], state[B], state[C]], name):
                                    if len(new) + len(state) >= self.cap: break
                                budget -= 1
                            if budget <= 0: break
                        if budget <= 0: break

            # -- modus ponens ----------------------------------------------
            hset = set(have)
            for f in have:
                s = self.split_imp(f)
                if s is None:
                    continue
                ante, cons = s
                if ante in hset:
                    offer(cons, [state[ante], state[f]], "mp")
                if len(new) + len(state) >= self.cap:
                    break

            if not new:
                break
            for f, prem, rule in new:
                if f in state:
                    continue
                nm = f"th_{order}"
                g.add(Node(nm, "theorem", f, prem, rule, order))
                state[f] = nm
                order += 1
            stage_sizes.append(len(state))
            if len(state) >= self.cap:
                break

        return g, stage_sizes



# ============================================================================
# 2b.  MIU -- a deliberately CYCLIC formal system, as a check on assumptions
# ============================================================================

def miu_graph(max_len: int = 10, max_nodes: int = 4000):
    """
    Hofstadter's MIU system:  axiom MI, rules
        I.   xI     -> xIU
        II.  Mx     -> Mxx
        III. xIIIy  -> xUy
        IV.  xUUy   -> xy

    Included because it is a counterexample to the tempting assumption that a
    theorem graph is acyclic.  It returns to its own axiom:

        MI -II-> MII -II-> MIIII -I-> MIIIIU -III-> MIUU -IV-> MI

    Returns (graph, cyclic_pairs) where cyclic_pairs lists observed 2-cycles.
    The graph records first derivations only, so it is itself acyclic; the
    cycles live in the underlying relation and are reported separately.
    """
    def succ(s):
        out = []
        if s.startswith("M"):
            x = s[1:]
            if s.endswith("I"): out.append((s + "U", "I"))
            if x:               out.append(("M" + x + x, "II"))
        for i in range(len(s) - 2):
            if s[i:i+3] == "III": out.append((s[:i] + "U" + s[i+3:], "III"))
        for i in range(len(s) - 1):
            if s[i:i+2] == "UU": out.append((s[:i] + s[i+2:], "IV"))
        return out

    g = TheoremGraph()
    order = 0
    g.add(Node("MI", "axiom", "MI", [], "axiom", order)); order += 1
    name = {"MI": "MI"}
    frontier, relation = ["MI"], {}
    while frontier and len(g.nodes) < max_nodes:
        nxt = []
        for s in frontier:
            tg = [(t, r) for t, r in succ(s) if len(t) <= max_len]
            relation[s] = tg
            for t, r in tg:
                if t not in name:
                    name[t] = t
                    g.add(Node(t, "theorem", t, [s], r, order)); order += 1
                    nxt.append(t)
        frontier = nxt

    # Find statements lying on a cycle of the consequence relation.  Cycles of
    # any length count; restricting to 2-cycles would miss the MI cycle, which
    # has length 5.
    # Iterative depth-first search.  A recursive version overflows the C stack
    # on deep graphs however high the Python recursion limit is set.
    colour, on_cycle, stack, path = {}, set(), [], []
    for root in list(relation):
        if colour.get(root, 0) != 0:
            continue
        stack.append((root, iter(relation.get(root, []))))
        colour[root] = 1
        path.append(root)
        while stack:
            u, it = stack[-1]
            advanced = False
            for v, _ in it:
                c = colour.get(v, 0)
                if c == 1:
                    on_cycle.update(path[path.index(v):])
                elif c == 0:
                    colour[v] = 1
                    path.append(v)
                    stack.append((v, iter(relation.get(v, []))))
                    advanced = True
                    break
            if not advanced:
                colour[u] = 2
                stack.pop()
                if path and path[-1] == u:
                    path.pop()
    return g, sorted(on_cycle, key=len)[:8]

# ============================================================================
# 3.  DATA SOURCE B -- parse a real Metamath database
# ============================================================================

def parse_metamath(path: str, limit: int | None = None) -> TheoremGraph:
    """
    Minimal Metamath reader.

    Metamath is chosen because its proofs are already dependency lists: a
    '$p ... $= L1 L2 ... $.' statement names exactly the axioms and earlier
    theorems it invokes.  Converting to a labeled theorem graph therefore
    needs no natural-language processing and no proof reconstruction.

    Handles both normal proofs and the compressed format '( L1 L2 ... ) AB..'
    -- in the compressed case the parenthesised list is precisely the set of
    referenced labels, which is all the graph needs.
    """
    txt = open(path, "r", encoding="utf-8", errors="replace").read()
    txt = re.sub(r"\$\(.*?\$\)", " ", txt, flags=re.S)          # strip comments
    toks = txt.split()

    g = TheoremGraph()
    known: set[str] = set()
    i, order = 0, 0
    while i < len(toks):
        t = toks[i]
        if i + 1 < len(toks) and toks[i + 1] == "$a":
            try:
                j = toks.index("$.", i)
            except ValueError:
                break            # unterminated statement: stop, keep what we have
            g.add(Node(t, "axiom", " ".join(toks[i + 2:j]), [], "axiom", order))
            known.add(t); order += 1; i = j + 1; continue
        if i + 1 < len(toks) and toks[i + 1] == "$p":
            try:
                j = toks.index("$.", i)
            except ValueError:
                break
            body = toks[i + 2:j]
            if "$=" in body:
                k = body.index("$=")
                stmt, proof = body[:k], body[k + 1:]
            else:
                stmt, proof = body, []
            if proof and proof[0] == "(":
                # compressed: labels live between the parentheses
                try:
                    e = proof.index(")")
                    refs = proof[1:e]
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


# ============================================================================
# 4.  THEORY CHECKS
# ============================================================================

def check_depth_vs_length(g: TheoremGraph, regime: str = "same-system") -> dict:
    """
    Compares closure depth with proof length.  WHICH SYSTEM each quantity is
    measured in decides what the comparison means, and the two data sources
    differ on exactly this point.

    regime = "same-system"  (synthetic mode)
        delta and ||.|| are both measured in F.  The inequality

            delta_F(Gamma,phi) + 1  <=  ||phi||_F(Gamma)

        is then a genuine test: a linear proof must list every statement it
        uses, so its length is at least the number of closure rounds needed.
        A violation would refute the proposition or reveal a bug.

    regime = "compiled"  (Metamath mode)
        A Metamath proof step may CITE an earlier theorem instead of
        re-deriving it, so the step count is a proof length in F^D, the system
        augmented by every previously proved theorem as a derived rule, while
        the dependency-DAG depth is still measured in F.  The inequality is
        then NOT expected to hold, and where it fails it is measuring the
        Conservative Compilation Theorem: reuse of earlier lemmas collapses
        proof length below closure depth.  Such cases are reported as
        compilation events, not violations.
    """
    d, L = g.closure_depth(), g.proof_length()
    below, gaps, comp = [], [], []
    unreachable = 0
    for n in g.nodes:
        if d[n] == float("inf"):
            # Reachable only around a cycle, hence never actually derived.  The
            # bound says nothing about it, and scoring it would report a
            # spurious violation of magnitude infinity.
            unreachable += 1
            continue
        slack = L[n] - (d[n] + 1)
        gaps.append(slack)
        if slack < 0:
            below.append((n, d[n], L[n]))
            comp.append(-slack)
    gaps = np.array(gaps, dtype=float)
    out = dict(
        regime=regime,
        checked=len(g.nodes) - unreachable,
        unreachable=unreachable,
        below_bound=len(below),
        examples=below[:5],
        gap_mean=float(gaps.mean()) if len(gaps) else 0.0,
        gap_median=float(np.median(gaps)) if len(gaps) else 0.0,
        gap_max=float(gaps.max()) if len(gaps) else 0.0,
    )
    if regime == "compiled":
        out["compilation_events"] = len(below)
        out["compilation_saving_mean"] = float(np.mean(comp)) if comp else 0.0
        out["compilation_saving_max"] = float(max(comp)) if comp else 0.0
    else:
        out["violations"] = len(below)
    return out


def breadth_ratios(stage_sizes: list, g: TheoremGraph) -> dict:
    """
    |p_m| / |D_F^{m-1}(Gamma)|.

    The unguided canonical machine materialises all of D_F^{m-1}(Gamma).  A
    policy that only ever expands the ancestors of a fixed target materialises
    a much thinner set; the ratio between them is the quantity a learned
    policy can actually improve.
    """
    d = g.closure_depth()
    by_depth = defaultdict(int)
    for n in g.nodes:
        if d[n] != float("inf"):
            by_depth[d[n]] += 1
    cum, cums = 0, []
    for m in sorted(by_depth):
        cum += by_depth[m]
        cums.append(cum)

    deep = [n for n in g.nodes
            if g.nodes[n].kind == "theorem" and d[n] != float("inf")]
    deep.sort(key=lambda n: -d[n])
    rows = []
    for tgt in deep[:5]:
        anc = g.ancestors(tgt) | {tgt}
        m = d[tgt] + 1
        denom = cums[min(m - 1, len(cums) - 1)]
        rows.append(dict(target=tgt, depth=d[tgt], focused=len(anc),
                         unguided=denom, ratio=len(anc) / max(denom, 1)))
    return dict(stage_sizes=stage_sizes, per_target=rows)


# ============================================================================
# 5.  PREMISE SELECTION  (the learned policy)
# ============================================================================

def featurise(g: TheoremGraph, target: Node, cand: Node,
              usage: dict, depth: dict) -> list:
    """
    Features of the pair (goal, candidate premise).  Deliberately cheap and
    syntactic: the point is to test whether local structure is predictable
    (Hypothesis: local structure is learnable), not to win a benchmark.
    """
    ts = set(target.statement.split())
    cs = set(cand.statement.split())
    inter = len(ts & cs)
    union = len(ts | cs) or 1
    return [
        1.0,                                        # bias
        inter / union,                              # Jaccard overlap
        inter / (len(cs) or 1),                     # coverage of candidate
        math.log1p(usage.get(cand.name, 0)),        # how often used so far
        depth.get(cand.name, 0) / 10.0,             # candidate closure depth
        (target.order - cand.order) / 1000.0,       # recency in the corpus
        1.0 if cand.kind == "axiom" else 0.0,
        len(cs) / 20.0,                             # candidate size
    ]


def standardise(X):
    """
    Centre and scale each column, returning (Xz, mu, sigma).

    This is not cosmetic.  The features have very different natural ranges: the
    recency term is (goal order - candidate order) / 1000, which on a corpus the
    size of set.mm reaches about 44 while every other feature stays inside
    [0, 1].  A feature forty times larger than its neighbours dominates the
    gradient and leaves the fit badly conditioned, so the model would be
    reporting the corpus size rather than the data.  Constant columns -- the
    bias term -- are left alone.
    """
    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    const = sigma < 1e-12
    mu = np.where(const, 0.0, mu)
    sigma = np.where(const, 1.0, sigma)
    return (X - mu) / sigma, mu, sigma


def logistic_fit(X, y, epochs=400, lr=0.5, l2=1e-4, seed=0):
    """
    Plain logistic regression by gradient descent.  No sklearn required.

    Returns (w, mu, sigma): the weights together with the standardisation the
    training data was fitted under, so that scoring applies the SAME transform.
    Re-standardising on the test set would leak information about it.
    """
    Xz, mu, sigma = standardise(X)
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 0.01, Xz.shape[1])
    m = len(y)
    for _ in range(epochs):
        z = Xz @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        w -= lr * (Xz.T @ (p - y) / m + l2 * w)
    return w, mu, sigma


def premise_selection_experiment(g: TheoremGraph, n_neg=20, split=0.7,
                                 topk=(1, 5, 10), cand_cap=400, seed=0):
    """
    TEMPORAL split, as the evaluation protocol requires: train on statements
    appearing EARLIER in the corpus, test on ones appearing LATER.  A random
    split lets the model see the future and is the usual way these numbers get
    inflated.

    Complexity note.  The set of statements available to a goal is an INITIAL
    SEGMENT of the corpus order, so it is obtained by slicing a sorted list.
    Rebuilding it by filtering the whole corpus per goal would make the routine
    quadratic -- about 1.9 billion node visits on set.mm's ~43,900 theorems --
    which is the difference between a run that finishes and one that does not.
    """
    rng = random.Random(seed)
    depth = g.closure_depth()
    order = sorted(g.nodes.values(), key=lambda nd: nd.order)
    pos = {nd.name: i for i, nd in enumerate(order)}      # O(1) initial segments
    theorems = [nd for nd in order if nd.kind == "theorem" and nd.premises]
    if len(theorems) < 20:
        return dict(error="too few theorems with premises")

    cut = int(len(theorems) * split)
    train_th, test_th = theorems[:cut], theorems[cut:]
    cutoff_order = train_th[-1].order

    # usage counts restricted to the training prefix, so no future leaks in
    usage = defaultdict(int)
    for nd in order:
        if nd.order <= cutoff_order:
            for p in nd.premises:
                usage[p] += 1

    def sample_negatives(i, gold, k):
        """k statements strictly before position i, none of them gold."""
        if i <= 0:
            return []
        out, tries = [], 0
        seen = set()
        while len(out) < k and tries < 8 * k:
            tries += 1
            j = rng.randrange(i)
            nm = order[j].name
            if nm in gold or nm in seen:
                continue
            seen.add(nm)
            out.append(order[j])
        return out

    X, y = [], []
    for tgt in train_th:
        i = pos[tgt.name]
        if i < n_neg + 1:
            continue
        gold = set(tgt.premises)
        for pname in tgt.premises:
            if pname in g.nodes:
                X.append(featurise(g, tgt, g.nodes[pname], usage, depth)); y.append(1)
        for nd in sample_negatives(i, gold, n_neg):
            X.append(featurise(g, tgt, nd, usage, depth)); y.append(0)
    if not y or sum(y) == 0:
        return dict(error="no training data")
    Xtr, ytr = np.array(X, dtype=float), np.array(y, dtype=float)
    w, mu, sigma = logistic_fit(Xtr, ytr, seed=seed)

    # ---- ranking evaluation on the held-out (later) statements -------------
    hits = {k: [] for k in topk}
    base = {k: [] for k in topk}
    rr, rr_base = [], []
    for tgt in test_th:
        i = pos[tgt.name]
        if i < 10:
            continue
        gold = {p for p in tgt.premises if p in g.nodes}
        if not gold:
            continue
        # a capped random pool of available statements, plus the gold premises
        pool = sample_negatives(i, gold, min(cand_cap, i))
        cands = pool + [g.nodes[p] for p in gold]
        F = np.array([featurise(g, tgt, c, usage, depth) for c in cands], dtype=float)
        Fz = (F - mu) / sigma                     # the training transform
        names = [cands[j].name for j in np.argsort(-(Fz @ w))]
        bnames = [cands[j].name for j in
                  sorted(range(len(cands)), key=lambda j: -usage.get(cands[j].name, 0))]
        for k in topk:
            hits[k].append(len(gold & set(names[:k])) / len(gold))
            base[k].append(len(gold & set(bnames[:k])) / len(gold))
        first = next((r + 1 for r, nm in enumerate(names) if nm in gold), None)
        rr.append(1.0 / first if first else 0.0)
        firstb = next((r + 1 for r, nm in enumerate(bnames) if nm in gold), None)
        rr_base.append(1.0 / firstb if firstb else 0.0)

    return dict(
        n_train_pairs=int(len(ytr)), n_train_theorems=len(train_th),
        n_test_theorems=len(test_th), n_scored=len(rr),
        weights=[round(float(v), 4) for v in w],
        recall_at={k: round(float(np.mean(hits[k])), 4) for k in topk if hits[k]},
        baseline_at={k: round(float(np.mean(base[k])), 4) for k in topk if base[k]},
        mrr=round(float(np.mean(rr)), 4) if rr else None,
        mrr_baseline=round(float(np.mean(rr_base)), 4) if rr_base else None,
    )


# ============================================================================
# 6.  RUN ARTIFACTS
# ============================================================================

class Run:
    """
    Every invocation writes its artifacts to a fresh directory stamped with the
    date and time to the minute:

        runs/2026-07-27_1834/
            manifest.json   arguments, versions, host, timestamp
            run.log         everything printed to the console
            results.json    the measured quantities
            nodes.csv       one row per statement
            edges.csv       one row per premise -> conclusion edge

    Two runs in the same minute would collide, so a numeric suffix is appended
    when the directory exists.  Nothing is ever overwritten.
    """

    def __init__(self, base="runs", stamp=None):
        stamp = stamp or datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        path = os.path.join(base, stamp)
        if os.path.exists(path):
            k = 2
            while os.path.exists(f"{path}_{k}"):
                k += 1
            path = f"{path}_{k}"
        os.makedirs(path, exist_ok=True)
        self.dir, self.stamp, self.lines = path, stamp, []

    def path(self, name):
        return os.path.join(self.dir, name)

    def log(self, *args):
        s = " ".join(str(a) for a in args)
        print(s)
        self.lines.append(s)

    def write_manifest(self, args):
        json.dump(dict(
            timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
            stamp=self.stamp, arguments=vars(args),
            python=platform.python_version(), numpy=np.__version__,
            platform=platform.platform(), cwd=os.getcwd(),
        ), open(self.path("manifest.json"), "w"), indent=2)

    def write_graph(self, g: TheoremGraph):
        d, L = g.closure_depth(), g.proof_length()
        with open(self.path("nodes.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["name", "kind", "rule", "order", "closure_depth",
                        "proof_length", "n_premises", "statement"])
            for nm in sorted(g.nodes, key=lambda x: g.nodes[x].order):
                nd = g.nodes[nm]
                w.writerow([nd.name, nd.kind, nd.rule, nd.order,
                            "" if d[nm] == float("inf") else d[nm],
                            L[nm], len(nd.premises), nd.statement])
        with open(self.path("edges.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["premise", "conclusion", "rule"])
            for nm, nd in g.nodes.items():
                for p in nd.premises:
                    w.writerow([p, nm, nd.rule])

    def close(self, results):
        json.dump(results, open(self.path("results.json"), "w"),
                  indent=2, default=str)
        open(self.path("run.log"), "w").write("\n".join(self.lines) + "\n")


# ============================================================================
# 7.  DRIVER
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["synth", "metamath", "miu"], default="synth")
    ap.add_argument("--db", help="path to a .mm file (metamath mode)")
    ap.add_argument("--limit", type=int, default=6000,
                    help="max statements to read from a .mm file")
    ap.add_argument("--depth", type=int, default=6, help="SIC stages (synth mode)")
    ap.add_argument("--cap", type=int, default=3000, help="formula cap (synth mode)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="runs",
                    help="base directory for timestamped run folders "
                         "(default: runs)")
    ap.add_argument("--no-artifacts", action="store_true",
                    help="print only; do not create a run directory")
    a = ap.parse_args()

    run = None if a.no_artifacts else Run(a.outdir)

    def out(*x):
        (run.log if run else print)(*x)

    if run:
        out(f"run directory: {run.dir}")

    out("=" * 74)
    out("  ML-SIC-ATP  --  labeled theorem graphs and learned search policies")
    out("  Brian Tenneson    btenneson2301.substack.com")
    out("=" * 74)

    stage_sizes = []
    if a.mode == "synth":
        out("\n[1] Running the canonical rule-enumeration SIC  E_{F,Y}")
        out("    F = propositional Hilbert system, rule = modus ponens")
        sic = PropositionalSIC(max_depth=a.depth, cap=a.cap, seed=a.seed)
        g, stage_sizes = sic.run()
        out(f"    stage sizes |C(Gamma,m)| = |D_F^(m-1)(Gamma)|: {stage_sizes}")
    elif a.mode == "miu":
        out("\n[1] Building the MIU system (a CYCLIC formal system)")
        g, cyc = miu_graph()
        out(f"    statements lying on a cycle: {len(cyc)}"
              f"{' (showing shortest)' if cyc else ''}")
        if cyc:
            out(f"      {', '.join(cyc[:8])}")
        out("    MI returns to itself in 5 steps:")
        out("      MI -II-> MII -II-> MIIII -I-> MIIIIU -III-> MIUU -IV-> MI")
        out("    The graph recorded here keeps first derivations only, so it is")
        out("    acyclic by construction; the cycles are in the relation itself.")
    else:
        if not a.db:
            sys.exit("metamath mode needs --db path/to/file.mm")
        out(f"\n[1] Parsing Metamath database: {a.db}")
        g = parse_metamath(a.db, limit=a.limit)

    s = g.summary()
    out(f"\n[2] Labeled theorem graph")
    out(f"    vertices {s['nodes']}   edges {s['edges']}   "
          f"axioms {s['axioms']}   theorems {s['theorems']}   "
          f"max closure depth {s['max_depth']}")

    regime = "compiled" if a.mode == "metamath" else "same-system"
    out(f"\n[3] Closure depth against proof length   (regime: {regime})")
    chk = check_depth_vs_length(g, regime)
    out(f"    statements checked : {chk['checked']}")
    out(f"    slack (length - depth - 1): mean {chk['gap_mean']:.2f}  "
          f"median {chk['gap_median']:.1f}  max {chk['gap_max']:.0f}")
    if regime == "same-system":
        out(f"    violations of delta+1 <= ||.||  : {chk['violations']}")
        if chk["violations"]:
            out(f"    !! examples: {chk['examples']}")
        else:
            out("    -> none.  The bound holds on every statement, as proved.")
    else:
        out(f"    compilation events (length below depth): "
              f"{chk['compilation_events']} of {chk['checked']}")
        if chk["compilation_events"]:
            out(f"    mean saving {chk['compilation_saving_mean']:.2f} steps, "
                  f"max {chk['compilation_saving_max']:.0f}")
            out("    -> these are NOT violations.  A Metamath step may cite an")
            out("       earlier theorem rather than re-derive it, so the count is")
            out("       a proof length in F^D while the depth is measured in F.")
            out("       This is the Conservative Compilation Theorem, measured.")

    out(f"\n[4] Breadth ratio  |p_m| / |D_F^(m-1)(Gamma)|")
    br = breadth_ratios(stage_sizes, g)
    for r in br["per_target"]:
        out(f"    target {r['target']:>10s}  depth {r['depth']:>2d}   "
              f"focused {r['focused']:>5d} / unguided {r['unguided']:>6d}  "
              f"= {r['ratio']:.4f}")

    out(f"\n[5] Premise selection under a TEMPORAL split (train early, test late)")
    ex = premise_selection_experiment(g, seed=a.seed)
    if "error" in ex:
        out(f"    skipped: {ex['error']}")
    else:
        out(f"    train {ex['n_train_theorems']} theorems "
              f"({ex['n_train_pairs']} pairs) -> test {ex['n_test_theorems']}")
        for k in sorted(ex["recall_at"]):
            out(f"    recall@{k:<3d} learned {ex['recall_at'][k]:.4f}   "
                  f"frequency baseline {ex['baseline_at'][k]:.4f}")
        out(f"    MRR         learned {ex['mrr']:.4f}   "
              f"frequency baseline {ex['mrr_baseline']:.4f}")

    out("\n" + "=" * 74)
    if run:
        run.write_manifest(a)
        run.write_graph(g)
        run.close(dict(summary=s, depth_check=chk, breadth=br, premise=ex))
        out(f"artifacts written to {run.dir}/")
        for fn in sorted(os.listdir(run.dir)):
            out(f"    {fn}")


if __name__ == "__main__":
    main()
