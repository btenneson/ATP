#!/usr/bin/env python3
"""
Predator_7 -- Predator_4's ranking coupled to Predator_5's search, over set.mm.
Brian Tenneson, v7.0.

    python predator7.py selftest                 no files needed
    python predator7.py determined set.mm        how much of set.mm is reachable
    python predator7.py prove set.mm --label ...  attempt a proof

WHAT IS COUPLED
---------------
    Predator_4      ranks candidates.  Trained on 903,356 logical references
                    from all of set.mm.  Ranks, cannot prove.
    Predator_5      weighted-A* with f(q) = depth(q) - lambda*score.  Proves,
                    but only over a 287-state fragment.
    metamath.py     verifies.  Any proof emitted here is handed back to it.
    setmm_grammar   parses statements into trees, so candidates can be FOUND.

Predator_4 and Predator_5 were never able to be combined because step two was
missing.  A set.mm statement is a flat token sequence,

    |- ( ( A ~<_ B /\\ B ~<_ A ) -> A ~~ B )

with nothing marking which tokens group.  Asking "which assertions could
conclude this?" requires a parse, and the grammar for it is the 1,441 syntax
axioms already in the file.

HOW A PROOF IS EMITTED, AND WHY IT IS CHECKABLE
-----------------------------------------------
A parse tree IS a Metamath syntax proof.  A node with rule L and children
k1..kn serialises in RPN as  proof(k1) ... proof(kn) L.  So the 95% of proof
steps that are formula construction are GENERATED from the tree rather than
searched for -- the two-phase split, made concrete.

A logical step applying assertion A under substitution sigma emits

    [ trees for A's mandatory $f hypotheses, under sigma ]
    [ recursive proofs of A's $e hypotheses ]
    A

which is exactly the RPN the verifier consumes.  Nothing here reports its own
success: `prove` writes the proof and runs metamath.py's verifier over it.

THE LIMITATION, STATED UP FRONT
-------------------------------
This searches by MATCHING, which is one-way: the goal is ground and the
assertion's conclusion carries the variables.  That works only when the
assertion is DETERMINED -- every variable in its $e hypotheses also occurs in
its conclusion, so matching the conclusion pins down the subgoals.

ax-mp is not determined.  Its conclusion is the bare variable `ps`, so matching
it against any goal leaves `ph` -- the whole antecedent -- unconstrained. The
same holds for syl. Those are the two most-cited logical labels in set.mm.

So Predator_7 can prove goals reachable through determined assertions and will
fail on anything needing a free antecedent to be invented. That is a real
ceiling, not a tuning problem; lifting it needs metavariables and full
unification rather than matching. `determined` reports what fraction of the
corpus sits below the ceiling, so the ceiling is measured rather than guessed.
"""
from __future__ import annotations
import argparse, heapq, json, math, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from metamath import MM, Toks, load, MMError, apply_subst
    import setmm_grammar as G
except ImportError as e:
    raise SystemExit("predator7.py needs metamath.py and setmm_grammar.py "
                     "in the same folder (%s)" % e)
try:
    import predator4 as P4
    HAVE_P4 = True
except ImportError:
    HAVE_P4 = False

VERSION = "7.0"
WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)
# 30000 without a matching C stack is a segfault waiting to
# happen; _run_with_big_stack below supplies the stack.
sys.setrecursionlimit(8000)


# ===========================================================================
#  which assertions can be used by a matching search
# ===========================================================================
def is_determined(data):
    """True when matching the conclusion pins down every subgoal.

    Every variable occurring in an $e hypothesis must also occur in the
    conclusion.  Otherwise the subgoal contains a variable the match never
    bound, and the searcher would have to INVENT a formula for it -- which
    matching cannot do."""
    dvs, f_hyps, e_hyps, concl = data
    cvars = {t for t in concl if t in G.VARTYPE}
    for _, stat in e_hyps:
        for t in stat:
            if t in G.VARTYPE and t not in cvars:
                return False
    return True


def survey(mm):
    """Count determined vs not WITHOUT parsing anything.

    is_determined only compares variable occurrences, so the ceiling can be
    measured in a second.  Parsing 49,127 conclusions takes an hour and is not
    needed to answer 'how much is reachable'."""
    det, undet = [], []
    for lab in mm.order:
        typ, data = mm.labels[lab]
        if typ not in ("$a", "$p"):
            continue
        concl = data[3]
        if not concl or concl[0] != "|-":
            continue
        (det if is_determined(data) else undet).append(lab)
    return det, undet


class LazyIndex:
    """Assertions bucketed by the FIRST TOKEN of their conclusion, parsed only
    when a goal actually reaches into their bucket.

    Two assertions can only match if their conclusions begin with the same
    token, and that test needs no parse.  So instead of parsing every
    conclusion up front -- an hour -- bucket on the first token and parse a
    bucket the first time a goal lands in it.  A goal touches one bucket, so
    the cost falls from 49,127 parses to a few hundred."""

    def __init__(self, mm, by_tc, say=None):
        self.mm, self.by_tc, self.say = mm, by_tc, say
        self.buckets = defaultdict(list)     # first token -> [(label, data)]
        self.parsed = {}                     # first token -> [(label, tree, data)]
        self.n_det = self.n_undet = 0
        for lab in mm.order:
            typ, data = mm.labels[lab]
            if typ not in ("$a", "$p"):
                continue
            concl = data[3]
            if not concl or concl[0] != "|-" or len(concl) < 2:
                continue
            if not is_determined(data):
                self.n_undet += 1
                continue
            self.n_det += 1
            # A conclusion beginning with a VARIABLE can match a goal beginning
            # with anything -- eqtri concludes "|- A = C", which starts with the
            # variable A and must be offered to every goal.  Bucketing it under
            # 'A' hides it from a goal starting with '{', which is why prcom
            # died after one expansion.
            first = concl[1]
            self.buckets[None if first in G.VARTYPE else first].append(
                (lab, data))

    def _bucket(self, key, say=None):
        hit = self.parsed.get(key)
        if hit is None:
            todo = self.buckets.get(key, ())
            if say and len(todo) > 200:
                say("    parsing %s conclusions in bucket %r (once)..."
                    % (f"{len(todo):,}", key if key is not None else "<var>"))
            hit = []
            for lab, data in todo:
                try:
                    t = G.parse(data[3][1:], "wff", self.by_tc)
                except (RecursionError, MMError):
                    t = None
                if t is not None:
                    hit.append((lab, t, data))
            self.parsed[key] = hit
        return hit

    def for_goal(self, goal_tree):
        """Candidates: those whose conclusion starts with the goal's first
        token, PLUS those whose conclusion starts with a variable and so can
        match anything."""
        toks = goal_tree.tokens()
        say = self.say
        if not toks:
            return self._bucket(None, say)
        return self._bucket(toks[0], say) + self._bucket(None, say)


def index_assertions(mm, by_tc, say=print):
    """Eager version, kept for the selftest where the corpus is tiny."""
    out, unparsed, undet = [], 0, 0
    for lab in mm.order:
        typ, data = mm.labels[lab]
        if typ not in ("$a", "$p"):
            continue
        concl = data[3]
        if not concl or concl[0] != "|-":
            continue
        if not is_determined(data):
            undet += 1
            continue
        try:
            t = G.parse(concl[1:], "wff", by_tc)
        except (RecursionError, MMError):
            t = None
        if t is None:
            unparsed += 1
            continue
        out.append((lab, t, data))
    say("    %s usable, %s not determined, %s unparsed"
        % (f"{len(out):,}", f"{undet:,}", f"{unparsed:,}"))
    return out


# ===========================================================================
#  emitting a Metamath proof
# ===========================================================================
def tree_proof(t, fvar):
    """RPN proof of a parse tree: children first, then the rule label.

    This is the 95% of a set.mm proof that is formula construction, produced
    by walking a tree instead of searching for it."""
    if t.var is not None:
        return [fvar[t.var]]
    out = []
    for k in t.kids:
        out.extend(tree_proof(k, fvar))
    out.append(t.label)
    return out


class Step:
    """One applied assertion: label, substitution, and proofs of its $e hyps."""
    __slots__ = ("label", "subst", "subs", "data")

    def __init__(self, label, subst, data):
        self.label, self.subst, self.data = label, subst, data
        self.subs = []

    def emit(self, fvar):
        _, f_hyps, e_hyps, _ = self.data
        out = []
        for _, tc, var in f_hyps:
            t = self.subst.get(var)
            if t is None:
                raise MMError("step %s: unbound %s" % (self.label, var))
            out.extend(tree_proof(t, fvar))
        for s in self.subs:
            out.extend(s.emit(fvar))
        out.append(self.label)
        return out


def instantiate(stat, subst):
    """Apply a tree substitution to a statement, returning tokens."""
    out = []
    for tok in stat:
        t = subst.get(tok)
        out.extend(t.tokens() if t is not None else [tok])
    return out


# ===========================================================================
#  the coupled search:  Predator_5's weighted-A*, Predator_4's ranking
# ===========================================================================
class Node:
    """One search state.

    `trail` records (parent_step, step) decisions but does NOT wire them
    together.  An earlier version appended each candidate to its parent's
    .subs as it was tried, so a parent accumulated all 64 candidates and emit()
    serialised every one of them instead of the single step on the successful
    path.  The selftest missed it by succeeding on the first candidate.  The
    tree is now assembled once, from the winning trail only."""
    __slots__ = ("goals", "trail", "depth", "score")

    def __init__(self, goals, trail, depth, score):
        self.goals, self.trail, self.depth, self.score = goals, trail, depth, score


def prove(goal_tokens, index, by_tc, rank, budget, lam, max_depth, say=print):
    """Backward best-first search.  Returns (root Step, expansions) or (None, n).

    A state is a list of open goals.  Expanding replaces the first open goal by
    the $e hypotheses of a chosen assertion, under the substitution the match
    forced.  Priority is Predator_5's:  f = depth - lambda * score,  with the
    score supplied by Predator_4."""
    goal_tree = G.parse(goal_tokens, "wff", by_tc)
    if goal_tree is None:
        say("    goal does not parse")
        return None, 0

    start = Node([(goal_tree, None)], (), 0, 0.0)
    frontier = [(0.0, 0, start)]
    exp = tie = 0
    seen = set()

    while frontier:
        _, _, node = heapq.heappop(frontier)
        exp += 1
        if exp > budget:
            return None, exp
        if not node.goals:
            root = None
            for parent, st in node.trail:      # wire up the winner only
                if parent is None:
                    root = st
                else:
                    parent.subs.append(st)
            return root, exp
        if node.depth >= max_depth:
            continue

        (gt, slot) = node.goals[0]
        rest = node.goals[1:]
        key = (node.depth, tuple(" ".join(g.tokens()) for g, _ in node.goals))
        if key in seen:
            continue
        seen.add(key)

        pool = index.for_goal(gt) if hasattr(index, "for_goal") else index
        cands = []
        for lab, ct, data in pool:
            s = {}
            if G.match_tree(ct, gt, s):
                cands.append((lab, s, data))
        if not cands:
            continue

        scored = rank(gt, [c[0] for c in cands])
        order = sorted(range(len(cands)), key=lambda i: -scored[i])

        for i in order[:64]:
            lab, s, data = cands[i]
            step = Step(lab, s, data)
            _, _, e_hyps, _ = data
            newgoals = []
            ok = True
            for _, stat in e_hyps:
                toks = instantiate(stat[1:], s)
                sub = G.parse(toks, "wff", by_tc)
                if sub is None:
                    ok = False; break
                newgoals.append((sub, step))
            if not ok:
                continue
            tie += 1
            nxt = Node(newgoals + rest, node.trail + ((slot, step),),
                       node.depth + 1, scored[i])
            heapq.heappush(frontier,
                           (node.depth + 1 - lam * scored[i], tie, nxt))
    return None, exp


# ===========================================================================
#  ranking
# ===========================================================================
def make_ranker(mm, corpus=None, pred=None, cut=0):
    """Predator_4's score if a trained model is supplied, else symbol overlap.

    The fallback is deliberately weak so that a coupled run and an uncoupled
    run are distinguishable: if Predator_4's ranking is doing nothing, the two
    will expand the same number of nodes."""
    if pred is None or corpus is None:
        symb = {}
        for lab in mm.order:
            typ, data = mm.labels[lab]
            if typ in ("$a", "$p") and data[3]:
                symb[lab] = set(data[3])

        def rank(goal_tree, labels):
            gs = set(goal_tree.tokens())
            out = []
            for l in labels:
                cs = symb.get(l, set())
                out.append(len(gs & cs) / max(len(gs | cs), 1))
            return out
        return rank, "symbol overlap (untrained)"

    by_label = {t.label: t for t in corpus}
    usage = defaultdict(int)
    for t in corpus[:cut]:
        for p in t.premises:
            usage[p] += 1

    def rank(goal_tree, labels):
        gtok = goal_tree.tokens()
        goal = P4.Theorem("__goal__", "theorem", ["|-"] + gtok, [], cut)
        rows = []
        for l in labels:
            c = by_label.get(l)
            if c is None:
                rows.append([0.0] * len(P4.Predator4.FEATURES)); continue
            rows.append(P4.Predator4.features(
                goal, c, usage.get(l, 0), set(), max(cut - c.order, 0), 0, 0.0))
        return pred.score(rows)
    return rank, "Predator_4 (trained)"


# ===========================================================================
#  commands
# ===========================================================================
SELFTEST = r"""
$c wff |- ( ) -> /\ $.
$v ph ps ch $.
wph $f wff ph $.
wps $f wff ps $.
wch $f wff ch $.
wi $a wff ( ph -> ps ) $.
wa $a wff ( ph /\ ps ) $.
ax1 $a |- ( ph -> ( ps -> ph ) ) $.
${ sim $e |- ( ph /\ ps ) $.
   simpl $a |- ph $. $}
${ ai $e |- ph $.
   adds $a |- ( ph -> ( ps -> ph ) ) $. $}
conj $a |- ( ph /\ ( ps -> ph ) ) $.
"""


def cmd_selftest(a):
    print("\n" + "=" * 74)
    print("  PREDATOR_7 v%s  --  selftest" % VERSION)
    print("=" * 74 + "\n")
    mm = MM(); mm.read(Toks(SELFTEST))
    by_tc = G.build_grammar(mm)
    fvar = {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar[d[1]] = lab

    print("  grammar %d rules; assertions:" % len(G.RULES))
    index = index_assertions(mm, by_tc, say=lambda s: print("  " + s))
    for lab, _, data in index:
        print("      usable   %-8s %s" % (lab, " ".join(data[3])))
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ in ("$a", "$p") and d[3] and d[3][0] == "|-" \
                and not is_determined(d):
            print("      NOT det. %-8s %s   <- hypothesis variable not in "
                  "conclusion" % (lab, " ".join(d[3])))

    rank, how = make_ranker(mm)
    print("\n  ranker: %s" % how)

    bad = 0

    # (1) a goal reachable through a determined assertion
    goal = "( ph -> ( ps -> ph ) )".split()
    print("\n  [1] goal  |- %s" % " ".join(goal))
    root, exp = prove(goal, index, by_tc, rank, 400, 0.5, 6,
                      say=lambda s: print("   " + s))
    if root is None:
        print("      NOT PROVED after %d expansions  <-- FAILED" % exp); bad += 1
    else:
        proof = root.emit(fvar)
        print("      proved in %d expansions, %d proof steps" % (exp, len(proof)))
        print("      root step: %s" % root.label)
        # hand it to the independent verifier
        src = SELFTEST + "\nchk $p |- %s $= %s $.\n" % (
            " ".join(goal), " ".join(proof))
        m2 = MM()
        try:
            m2.read(Toks(src))
            r = m2.verify("chk")
            print("      metamath.py verify: %s" % r.upper())
            bad += (r != "ok")
        except MMError as e:
            print("      metamath.py verify: FAILED -- %s" % e); bad += 1

    # (2) the known ceiling: simpl is not determined, so a goal needing it fails
    print("\n  [2] goal  |- ph        (needs simpl, which is NOT determined)")
    root2, exp2 = prove(["ph"], index, by_tc, rank, 200, 0.5, 4,
                        say=lambda s: None)
    if root2 is None:
        print("      not proved (%d expansions) -- expected, this is the"
              " matching ceiling" % exp2)
    else:
        print("      unexpectedly proved  <-- the determinedness filter is"
              " wrong"); bad += 1

    print("\n  %s\n" % ("all checks passed" if not bad
                        else "%d CHECK(S) FAILED" % bad))
    return 0 if not bad else 1


def cmd_determined(a):
    print("\n" + "=" * 74)
    print("  PREDATOR_7  --  how much of set.mm a matching search can reach")
    print("=" * 74 + "\n")
    mm = load(a.file)
    # is_determined() consults G.VARTYPE, which build_grammar populates.
    # Without this call VARTYPE is empty, every "t in VARTYPE" test is False,
    # and is_determined returns True for EVERYTHING -- the filter silently
    # passes the whole corpus.  That is how targets reported 47,550 of 47,572
    # reachable while prove, which does build the grammar, reported 81%.
    G.build_grammar(mm)
    det, undet = survey(mm)
    tot = len(det) + len(undet)
    print("""
  %s of %s '|-' assertions are DETERMINED (%.0f%%) -- every variable in their
  hypotheses also occurs in their conclusion, so matching the conclusion pins
  down the subgoals.

  %s are not.  Matching cannot invent a value for a variable it never bound,
  so those are unavailable until the searcher carries metavariables.
""" % (f"{len(det):,}", f"{tot:,}", 100.0 * len(det) / max(tot, 1),
       f"{len(undet):,}"))

    famous = [l for l in ("ax-mp", "syl", "mpbi", "eqtri", "3eqtr4i", "adantr",
                          "a1i", "simpr", "mpbird", "sylib") if l in set(undet)]
    if famous:
        print("  Excluded, and heavily used:  %s" % ", ".join(famous))
    reach = [l for l in ("eqid", "id", "vex", "sbth", "canth") if l in set(det)]
    if reach:
        print("  Reachable:                   %s" % ", ".join(reach))
    print("\n  This percentage is the ceiling on what Predator_7 can prove in\n"
          "  this form.  It is a property of the method, not of the budget.\n")
    return 0


def cmd_targets(a):
    """List theorems every one of whose cited premises is determined.

    Choosing a first target by fame is a mistake: prcom cites 3eqtr4i, whose
    conclusion "C = D" omits the A and B appearing in its hypotheses, so it is
    exactly the case matching cannot handle.  A goal is only worth attempting
    when a route to it exists inside the reachable fragment, and the recorded
    proof's premises are the cheapest evidence of that."""
    print("\n" + "=" * 74)
    print("  PREDATOR_7  --  goals actually within reach")
    print("=" * 74 + "\n")
    mm = load(a.file)
    # is_determined() consults G.VARTYPE, which build_grammar populates.
    # Without this call VARTYPE is empty, every "t in VARTYPE" test is False,
    # and is_determined returns True for EVERYTHING -- the filter silently
    # passes the whole corpus.  That is how targets reported 47,550 of 47,572
    # reachable while prove, which does build the grammar, reported 81%.
    G.build_grammar(mm)
    det, undet = survey(mm)
    dset, uset = set(det), set(undet)

    rows = []
    for lab in mm.order:
        typ, data = mm.labels[lab]
        if typ != "$p" or lab not in dset:
            continue
        proof = mm.proofs.get(lab) or []
        if proof and proof[0] == "(":
            try:
                refs = proof[1:proof.index(")")]
            except ValueError:
                continue
        else:
            refs = [t for t in proof if t in mm.labels]
        cited = [r for r in dict.fromkeys(refs)
                 if r in mm.labels and mm.labels[r][0] in ("$a", "$p")
                 and mm.labels[r][1][3] and mm.labels[r][1][3][0] == "|-"]
        if not cited:
            continue
        blockers = [r for r in cited if r in uset]
        if blockers:
            continue
        rows.append((len(cited), lab, " ".join(mm.labels[lab][1][3])))

    rows.sort()
    print("  %s theorems have ALL cited premises determined." % f"{len(rows):,}")
    print("  Those are the goals a matching search could reach.\n")
    print("  %-5s %-14s %s" % ("prem", "label", "statement"))
    print("  " + "-" * 68)
    for n, lab, stat in rows[:a.limit]:
        print("  %-5d %-14s %s" % (n, lab, stat[:48]))
    print("""
  Start at the top.  Few premises, all reachable, is the easiest thing this
  method can be asked to do -- and if it fails there, the problem is the
  search or the ranker rather than the ceiling.
""")
    return 0


def cmd_prove(a):
    print("\n" + "=" * 74)
    print("  PREDATOR_7 v%s  --  prove %s" % (VERSION, a.label))
    print("=" * 74 + "\n")
    mm = load(a.file)
    by_tc = G.build_grammar(mm)
    if a.label not in mm.labels:
        print("\n  %s not found\n" % a.label); return 1
    stat = mm.labels[a.label][1][3]
    print("\n  goal  %s" % " ".join(stat))

    fvar = {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar[d[1]] = lab

    print("\n  indexing assertions strictly before %s..." % a.label)
    cut_order = mm.order.index(a.label)
    sub = MM()
    sub.constants, sub.variables = mm.constants, mm.variables
    sub.labels = {l: mm.labels[l] for l in mm.order[:cut_order]}
    sub.order = mm.order[:cut_order]
    index = LazyIndex(sub, by_tc, say=print)
    print("    %s determined, %s not; conclusions parsed on demand"
          % (f"{index.n_det:,}", f"{index.n_undet:,}"))

    pred, corpus = None, None
    if a.train and HAVE_P4:
        print("\n  training Predator_4 on statements before the goal...")
        corpus = P4.parse_mm(a.file, limit=None, progress=False)
        cut = min(cut_order, len(corpus))
        pred = P4.Predator4(seed=a.seed, model="logistic")
        pred.train(corpus, cut, max_goals=a.max_goals, seed=a.seed)
    rank, how = make_ranker(mm, corpus, pred, cut_order)
    print("  ranker: %s" % how)

    print("\n  searching (budget %s, lambda %.2f, max depth %d)..."
          % (f"{a.budget:,}", a.lam, a.max_depth))
    t0 = time.time()
    root, exp = prove(stat[1:], index, by_tc, rank, a.budget, a.lam,
                      a.max_depth)
    dt = time.time() - t0

    if root is None:
        print("\n  NOT PROVED.  %s expansions, %.1fs" % (f"{exp:,}", dt))
        print("""
  A failure here means one of three things, and they are worth separating:
    * the goal needs an assertion that is not determined (see `determined`),
    * the budget ran out, or
    * the proof is deeper than --max-depth.
  Only the second and third are tuning problems.
""")
        return 1

    proof = root.emit(fvar)
    print("\n  PROVED.  %s expansions, %.1fs, %s proof steps"
          % (f"{exp:,}", dt, f"{len(proof):,}"))
    print("  root step: %s" % root.label)

    out = a.out or ("%s_predator7.mm" % a.label)
    with open(out, "w") as f:
        f.write("$( Predator_7 proof of %s $)\n" % a.label)
        f.write("chk $p %s $= %s $.\n" % (" ".join(stat), " ".join(proof)))
    print("  wrote %s" % out)
    print("""
  Verify it independently -- this program's word is not evidence:

      python metamath.py verify %s
""" % out)
    return 0


def main():
    ap = argparse.ArgumentParser(prog="predator7", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest")
    d = sub.add_parser("determined"); d.add_argument("file", nargs="?",
                                                     default="set.mm")
    tg = sub.add_parser("targets"); tg.add_argument("file", nargs="?",
                                                    default="set.mm")
    tg.add_argument("--limit", type=int, default=30)
    p = sub.add_parser("prove"); p.add_argument("file", nargs="?",
                                                default="set.mm")
    p.add_argument("--label", required=True)
    p.add_argument("--budget", type=int, default=20000)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--max-depth", type=int, default=8)
    p.add_argument("--train", action="store_true",
                   help="fit Predator_4 and rank with it (slower, the point)")
    p.add_argument("--max-goals", type=int, default=4000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=None)

    a = ap.parse_args()
    if a.cmd == "selftest":     sys.exit(cmd_selftest(a))
    elif a.cmd == "determined": sys.exit(cmd_determined(a))
    elif a.cmd == "targets":    sys.exit(cmd_targets(a))
    elif a.cmd == "prove":      sys.exit(cmd_prove(a))
    else:                       ap.print_help()


def _run_with_big_stack(fn):
    """Run fn on a thread with a large stack.

    sys.setrecursionlimit only raises PYTHON's guard; the C stack is a separate
    and much harder limit.  Raising the first without the second converts a
    clean RecursionError into a process-killing stack overflow -- no traceback,
    the shell simply exits.  That is what a deeply nested set.mm statement did
    to this parser.  A 256 MB thread stack makes the raised limit honest."""
    import threading
    try:
        threading.stack_size(256 * 1024 * 1024)
    except (ValueError, RuntimeError):
        try:
            threading.stack_size(64 * 1024 * 1024)
        except Exception:
            pass
    box = {}

    def target():
        try:
            box["rc"] = fn()
        except SystemExit as e:
            box["rc"] = e.code
        except RecursionError:
            print("\n  RecursionError: a statement nested deeper than the "
                  "stack allows.\n  This is the CLEAN failure -- the process "
                  "survived.\n")
            box["rc"] = 2
    t = threading.Thread(target=target, daemon=True)
    t.start()
    # join in slices so Ctrl-C reaches the main thread.  A bare join() blocks
    # uninterruptibly and a non-daemon worker keeps the process alive after it,
    # which is why Ctrl-C did nothing during a long search.
    try:
        while t.is_alive():
            t.join(0.2)
    except KeyboardInterrupt:
        print("\n  interrupted.\n")
        return 130
    return box.get("rc", 0)


if __name__ == "__main__":
    sys.exit(_run_with_big_stack(main) or 0)
