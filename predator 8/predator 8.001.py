#!/usr/bin/env python3
r"""
Predator 8.001 -- a population-based nondeterministic prover for set.mm.
Brian Tenneson.

    python predator8.py selftest
    python predator8.py prove set.mm --label prcom
    python predator8.py prove set.mm --label prcom --agents 8 \
        --creativity 0.8 --budget 200000 --seed 2301

IMPLEMENTED IN 8.001
--------------------
* A population of independent backward-search agents.
* Conservative, balanced, exploratory, and lemma-seeking creativity profiles.
* Seeded nondeterministic assertion ordering using temperature and Gumbel noise.
* Novelty and global rarity bonuses that diversify agents' search trajectories.
* Counterfactual exploration: part of each opener cap is reserved for
  unification-compatible lower-ranked alternatives rather than only the
  current best-looking route.
* A resource scheduler that divides one global expansion budget among agents.
* The 7.1 unification/metavariable search and independent Metamath verification.

The population shares search statistics (not proof certificates) so later
agents can favor assertion labels underused by earlier agents.  Every reported
proof is still emitted as a Metamath certificate and checked by the verifier.

NOT YET IMPLEMENTED
-------------------
* A trained policy/value model.  Version 8.001 uses explicit heuristic features.
* Persistent shared verified-lemma memory.
* Online learning or expert iteration.

These omissions are intentional: 8.001 is the first testable architectural
step, not a claim that the entire Predator 8 research plan is complete.

BENCHMARK DISCIPLINE
--------------------
The prover is target-generic.  It contains no HaloProof-specific rule, route,
lemma list, training example, or reference proof.  "Blind" means blind to the
benchmark solution, not untrained: a future ML-guided Predator may learn from a
frozen permitted corpus of other set.mm proofs.  Relevant patterns learned from
that corpus are heuristic transfer, not parroting, provided the benchmark proof,
near-duplicates, benchmark-specific hints, and downstream leakage are excluded
and the training split is recorded.  Version 8.001 itself has no trained model.

An arbitrary ATP is not expected to know how Hal(0) ~ R is proved merely from
receiving the formal target and frozen prior environment.  Failure to find a
checked certificate under finite controls is reported only as UNKNOWN UNDER
THE DECLARED RESOURCE BOUNDS.

PROOFS ARE EMITTED AND CHECKED
------------------------------
A parse tree is a Metamath syntax proof: a node with rule L and children k1..kn
serialises in RPN as  proof(k1) ... proof(kn) L.  So the 95% of set.mm proof
steps that are formula construction are GENERATED from the tree rather than
searched for.

A logical step applying assertion A under substitution sigma emits

    [ trees for A's mandatory $f hypotheses, under sigma ]
    [ recursive proofs of A's $e hypotheses ]
    A

which is exactly what the verifier consumes.  `prove` writes a .mm file;
nothing here reports its own success.

WHAT IS STILL NOT DONE
----------------------
Disjoint-variable conditions are checked by the verifier but are not used to
PRUNE the search, so 8.001 can spend effort on branches the verifier will later
reject.  An emitted candidate is reported as a proof only after the verifier
accepts it; otherwise the outcome is PROTOCOL FAILURE.  The search is therefore
sound in what it claims, though not yet as sharp as it could be.
"""
from __future__ import annotations
import argparse, heapq, itertools, math, os, random, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from metamath import MM, Toks, load, MMError
    import setmm_grammar as G
except ImportError as e:
    raise SystemExit("predator8.py needs metamath.py and setmm_grammar.py "
                     "in the same folder (%s)" % e)

VERSION = "8.001"
# NB: this used to chdir into a hard-coded absolute path when that folder
# happened to exist, which silently broke every relative path for callers
# that import predator71 as a library.  Opt in with PREDATOR_WORKDIR instead.
WORKDIR = os.environ.get("PREDATOR_WORKDIR", "")
if WORKDIR and os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)
sys.setrecursionlimit(8000)


# ===========================================================================
#  trees with two flexible namespaces
# ===========================================================================
_counter = itertools.count(1)


def fresh(tc):
    """A new metavariable of the given typecode."""
    return G.Tree(None, tc, (), "?%d" % next(_counter))


def is_meta(t):
    return t.var is not None and t.var.startswith("?")


def rename_apart(t, mapping):
    """Fresh metavariables for an assertion's own variables.

    Without this, two uses of the same assertion in one proof would share
    variable names and unify with each other by accident."""
    if t.var is not None:
        if t.var not in mapping:
            mapping[t.var] = fresh(t.typecode)
        return mapping[t.var]
    return G.Tree(t.label, t.typecode, [rename_apart(k, mapping) for k in t.kids])


def walk(t, sub):
    while is_meta(t) and t.var in sub:
        t = sub[t.var]
    return t


def apply_sub(t, sub):
    t = walk(t, sub)
    if t.var is not None:
        return t
    return G.Tree(t.label, t.typecode, [apply_sub(k, sub) for k in t.kids])


def occurs(v, t, sub):
    t = walk(t, sub)
    if t.var is not None:
        return t.var == v
    return any(occurs(v, k, sub) for k in t.kids)


def unify(a, b, sub):
    """Robinson unification over metavariables, with occurs check.

    Only metavariables are flexible.  A statement's ordinary variables have
    already been renamed to metavariables by rename_apart, so everything
    flexible is a metavariable and everything else is rigid."""
    a, b = walk(a, sub), walk(b, sub)
    if a is b:
        return sub
    if is_meta(a):
        if is_meta(b) and a.var == b.var:
            return sub
        if a.typecode != b.typecode:
            return None
        if occurs(a.var, b, sub):
            return None
        s = dict(sub); s[a.var] = b; return s
    if is_meta(b):
        return unify(b, a, sub)
    if a.var is not None or b.var is not None:
        return sub if (a.var == b.var and a.typecode == b.typecode) else None
    if a.label != b.label or len(a.kids) != len(b.kids):
        return None
    for x, y in zip(a.kids, b.kids):
        sub = unify(x, y, sub)
        if sub is None:
            return None
    return sub


def ground(t, sub, fallback):
    """Instantiate any surviving metavariable.

    A metavariable never determined by the search is genuinely unconstrained --
    it is filled with a declared variable of its typecode so a complete
    candidate certificate can be emitted.  This does not waive disjoint-
    variable or other formal conditions; the verifier remains authoritative.
    """
    t = walk(t, sub)
    if t.var is not None:
        return fallback[t.typecode] if is_meta(t) else t
    return G.Tree(t.label, t.typecode, [ground(k, sub, fallback) for k in t.kids])


# ===========================================================================
#  emitting Metamath proofs
# ===========================================================================
def tree_proof(t, fvar):
    """RPN for a parse tree: children first, then the rule label.

    This is the formula-construction majority of a set.mm proof, produced by
    walking a tree instead of searching for it."""
    if t.var is not None:
        if t.var not in fvar:
            raise MMError("no $f hypothesis for variable %s" % t.var)
        return [fvar[t.var]]
    out = []
    for k in t.kids:
        out.extend(tree_proof(k, fvar))
    out.append(t.label)
    return out


class Step:
    __slots__ = ("label", "fmap", "subs", "data")

    def __init__(self, label, fmap, data):
        self.label, self.fmap, self.data = label, fmap, data
        # One slot per $e hypothesis, filled BY INDEX.  Appending in the order
        # subgoals happen to be solved is wrong once the search picks the most
        # constrained goal first rather than the leftmost: emit() must lay the
        # hypotheses out in declaration order or the verifier reports a
        # hypothesis mismatch.
        self.subs = [None] * len(data[2])

    def emit(self, sub, fvar, fallback):
        _, f_hyps, e_hyps, _ = self.data
        out = []
        for _, tc, var in f_hyps:
            t = self.fmap.get(var)
            if t is None:
                raise MMError("%s: unbound %s" % (self.label, var))
            out.extend(tree_proof(ground(t, sub, fallback), fvar))
        for i, s in enumerate(self.subs):
            if s is None:
                raise MMError("%s: hypothesis %d never solved" % (self.label, i))
            out.extend(s.emit(sub, fvar, fallback))
        out.append(self.label)
        return out


# ===========================================================================
#  the index
# ===========================================================================
class Index:
    """Assertions with their conclusion parsed, bucketed by conclusion head.

    Unlike 7.0 this excludes nothing: an assertion whose hypotheses mention
    variables absent from its conclusion is exactly the case metavariables
    exist to handle."""

    def __init__(self, mm, by_tc, upto=None, say=None):
        self.by_tc = by_tc
        self.closers = defaultdict(list)   # no $e hypotheses: end a branch
        self.openers = defaultdict(list)   # have $e hypotheses: extend it
        self.n = 0
        order = mm.order[:upto] if upto is not None else mm.order
        for lab in order:
            typ, data = mm.labels[lab]
            if typ not in ("$a", "$p"):
                continue
            concl = data[3]
            if not concl or concl[0] != "|-" or len(concl) < 2:
                continue
            try:
                t = G.parse(concl[1:], "wff", by_tc)
            except (RecursionError, MMError):
                t = None
            if t is None:
                continue
            self.n += 1
            head = None if t.var is not None else t.label
            # Split on whether the assertion has $e hypotheses.  One with none
            # that unifies CLOSES the search goal syntactically in one step,
            # subject to final verification.  Those must never be missed to a
            # candidate cap, and
            # there are few of them, so they are kept separate and always tried
            # in full.  axin1, falanfal and tbw-ax4 each need exactly one such
            # assertion (pm2.01, anidm, falim) and all three failed at 20,000
            # expansions because the cap took an arbitrary 48 of thousands.
            (self.closers if not data[2] else self.openers)[head].append(
                (lab, t, data))
        if say:
            nc = sum(len(v) for v in self.closers.values())
            say("    %s assertions indexed (%s close a goal outright)"
                % (f"{self.n:,}", f"{nc:,}"))

    def candidates(self, goal):
        """(closers, openers) that could unify with this goal.

        A conclusion headed by a rule can only meet a goal headed by the same
        rule.  A conclusion that is a bare variable -- ax-mp -- meets anything,
        and so does any goal that is itself a metavariable.

        Closers are returned separately because they are tried exhaustively:
        a closer that unifies finishes the candidate branch, so skipping one
        loses that direct route, whereas skipping an opener loses an extended
        route."""
        def grab(d):
            if goal.var is not None:
                return [x for b in d.values() for x in b]
            return d.get(goal.label, []) + d.get(None, [])
        return grab(self.closers), grab(self.openers)


# ===========================================================================
#  Predator 8 population and creativity controls
# ===========================================================================
class Profile:
    """One proof-search personality.

    Temperature controls stochastic ordering.  Novelty rewards labels the
    current agent has not used.  Rarity rewards labels underused by the whole
    population.  Lemma seeking prefers assertions with fewer logical
    hypotheses.  Exploration reserves part of the branch cap for
    counterfactual alternatives outside the highest-scoring prefix.
    """
    __slots__ = ("name", "temperature", "novelty", "rarity", "lemma",
                 "exploration", "opener_cap", "resource")

    def __init__(self, name, temperature, novelty, rarity, lemma,
                 exploration, opener_cap, resource=1.0):
        self.name = name
        self.temperature = max(0.0, float(temperature))
        self.novelty = max(0.0, float(novelty))
        self.rarity = max(0.0, float(rarity))
        self.lemma = max(0.0, float(lemma))
        self.exploration = min(1.0, max(0.0, float(exploration)))
        self.opener_cap = max(1, int(opener_cap))
        self.resource = max(0.01, float(resource))

    def summary(self):
        return ("%s(T=%.2f novelty=%.2f rarity=%.2f explore=%.0f%%)"
                % (self.name, self.temperature, self.novelty, self.rarity,
                   100.0 * self.exploration))


def make_profiles(n, creativity, opener_cap=48):
    """Build a reproducible heterogeneous population.

    ``creativity`` is deliberately unitless and clamped to [0, 1].  More than
    four agents cycles the four base personalities with small deterministic
    perturbations; their random choices still depend only on ``--seed``.
    """
    n = max(1, int(n))
    c = min(1.0, max(0.0, float(creativity)))
    specs = [
        ("conservative", 0.02 + 0.10*c, 0.05*c, 0.02*c, 0.25,
         0.02 + 0.08*c, max(12, opener_cap // 2), 0.90),
        ("balanced", 0.10 + 0.55*c, 0.35*c, 0.25*c, 0.35,
         0.08 + 0.22*c, opener_cap, 1.10),
        ("explorer", 0.25 + 1.20*c, 0.90*c, 0.65*c, 0.15,
         0.20 + 0.45*c, max(opener_cap, int(1.25*opener_cap)), 1.20),
        ("lemma-seeker", 0.08 + 0.45*c, 0.45*c, 0.45*c, 1.00,
         0.10 + 0.20*c, opener_cap, 1.00),
    ]
    out = []
    for i in range(n):
        name, temp, nov, rare, lemma, explore, cap, resource = specs[i % 4]
        generation = i // 4
        if generation:
            name = "%s-%d" % (name, generation + 1)
            temp *= 1.0 + min(0.50, 0.08 * generation)
            explore = min(0.85, explore + 0.03 * generation)
        out.append(Profile(name, temp, nov, rare, lemma, explore, cap,
                           resource))
    return out


def schedule_budgets(total, profiles):
    """Divide a single global expansion budget without silently multiplying it."""
    total = max(0, int(total))
    weights = [p.resource for p in profiles]
    z = sum(weights) or 1.0
    exact = [total * w / z for w in weights]
    shares = [int(x) for x in exact]
    left = total - sum(shares)
    order = sorted(range(len(profiles)),
                   key=lambda i: (exact[i] - shares[i], -i), reverse=True)
    for i in order[:left]:
        shares[i] += 1
    return shares


def _gumbel(rng):
    """Standard Gumbel noise for sampling a ranking without replacement."""
    u = min(1.0 - 1e-12, max(1e-12, rng.random()))
    return -math.log(-math.log(u))


def _candidate_scores(goal, items, base_scores, profile, rng,
                      local_use, shared_use):
    scored = []
    for item, base in zip(items, base_scores):
        lab, ct, data = item
        logical_hyps = len(data[2])
        structural = -0.12 * logical_hyps - 0.002 * ct.size()
        novelty = profile.novelty if local_use[lab] == 0 else 0.0
        rarity = profile.rarity / math.sqrt(1.0 + shared_use[lab])
        lemma = profile.lemma / (1.0 + logical_hyps)
        noise = profile.temperature * _gumbel(rng)
        scored.append((float(base) + structural + novelty + rarity + lemma
                       + noise, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _counterfactual_slice(scored, cap, exploration, rng):
    """Keep strong routes while reserving slots for lower-ranked alternatives."""
    if len(scored) <= cap:
        return scored
    explore_n = min(cap - 1, int(round(cap * exploration)))
    exploit_n = cap - explore_n
    chosen = list(scored[:exploit_n])
    tail = scored[exploit_n:]
    if explore_n:
        chosen.extend(rng.sample(tail, min(explore_n, len(tail))))
    return chosen


# ===========================================================================
#  the search
# ===========================================================================
class Node:
    __slots__ = ("goals", "sub", "trail", "depth")

    def __init__(self, goals, sub, trail, depth):
        self.goals, self.sub, self.trail, self.depth = goals, sub, trail, depth


def n_metas(t, sub, acc=None):
    """How many distinct metavariables survive in this goal."""
    if acc is None:
        acc = set()
    t = walk(t, sub)
    if t.var is not None:
        if is_meta(t):
            acc.add(t.var)
        return acc
    for k in t.kids:
        n_metas(k, sub, acc)
    return acc


def pick_goal(goals, sub):
    """Choose the MOST CONSTRAINED open goal, not simply the first.

    A goal that is a bare metavariable constrains nothing -- every assertion in
    the corpus unifies with it -- so expanding it is pure guessing.  Left to
    itself the search does exactly that: ax-mp turns goal G into ( ?1 -> G )
    with ?1 free, and ?1 can be attacked by ax-mp again, giving an infinite
    regress that breadth-first order explores forever.

    Deferring under-constrained goals lets a SIBLING goal bind their
    metavariables first.  This is the standard fix for backward modus ponens
    and it is what makes the difference between thrashing and terminating."""
    best, bi = None, 0
    for i, (g, slot, _hix) in enumerate(goals):
        gg = walk(g, sub)
        bare = 1 if (gg.var is not None and is_meta(gg)) else 0
        key = (bare, len(n_metas(gg, sub)), -gg.size())
        if best is None or key < best:
            best, bi = key, i
    return bi


def prove(goal_tree, index, budget, max_depth, rank=None, say=print,
          progress=2000, max_open=6, profile=None, seed=0,
          shared_use=None, agent_name=None):
    """Backward search with metavariables.

    A state is (open goals, substitution).  Expanding the first goal picks an
    assertion, unifies its renamed conclusion with the goal, and replaces the
    goal by that assertion's hypotheses under the resulting substitution.  Any
    variable of the assertion not determined by the unification survives as a
    metavariable in those subgoals, to be determined by a later step.

    The substitution is threaded through every open goal, so binding a
    metavariable in one branch constrains the others.  That is what stops the
    search inventing formulas.

    Creativity changes only which unification-compatible assertion
    applications are examined first.  It never adds an inference rule or
    relaxes unification.  The final verifier rejects any remaining formal
    side-condition violation.
    """
    if profile is None:
        profile = Profile("deterministic", 0.0, 0.0, 0.0, 0.0,
                          0.0, 48, 1.0)
    rng = random.Random(seed)
    local_use = defaultdict(int)
    if shared_use is None:
        shared_use = defaultdict(int)
    agent_name = agent_name or profile.name
    start = Node([(goal_tree, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    exp = tie = 0
    seen = set()
    t0 = time.perf_counter()
    while frontier and exp < budget:
        priority, _, node = heapq.heappop(frontier)
        exp += 1
        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open goals, %.0fs"
                % (agent_name, f"{exp:,}", len(node.goals),
                   time.perf_counter() - t0))
        if not node.goals:
            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            return (root, node.sub), exp
        if node.depth >= max_depth:
            continue

        if len(node.goals) > max_open:
            continue                      # too many speculative subgoals open
        gi = pick_goal(node.goals, node.sub)
        (gt, slot, hix) = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = apply_sub(gt, node.sub)

        key = (node.depth, " ".join(gt.tokens()),
               tuple(sorted(" ".join(apply_sub(g, node.sub).tokens())
                            for g, _, _ in rest)))
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        # Every closer is retained.  Openers are capped because they extend the
        # search rather than finish this goal.  A profile keeps a strong prefix
        # and reserves some of that cap for counterfactual alternatives.
        sc_c = rank(gt, closers) if rank else [0.0] * len(closers)
        sc_o = rank(gt, openers) if rank else [0.0] * len(openers)
        ranked_c = _candidate_scores(gt, closers, sc_c, profile, rng,
                                     local_use, shared_use)
        ranked_o = _candidate_scores(gt, openers, sc_o, profile, rng,
                                     local_use, shared_use)
        pick = ranked_c + _counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng)

        for candidate_score, (lab, ct, data) in pick:
            m = {}
            c2 = rename_apart(ct, m)
            s2 = unify(c2, gt, node.sub)
            if s2 is None:
                continue
            _, f_hyps, e_hyps, _ = data
            fmap = {var: m.get(var, fresh(tc)) for _, tc, var in f_hyps}
            for _, tc, var in f_hyps:
                m.setdefault(var, fmap[var])
            step = Step(lab, fmap, data)
            newgoals = []
            ok = True
            for hj, (_, stat) in enumerate(e_hyps):
                try:
                    ht = G.parse(stat[1:], "wff", index.by_tc)
                except (RecursionError, MMError):
                    ht = None
                if ht is None:
                    ok = False; break
                newgoals.append((rename_apart(ht, m), step, hj))
            if not ok:
                continue
            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1
            # Every edge still costs positively, so creativity cannot turn the
            # queue into an endlessly improving deep path.  The bounded score
            # only breaks ties among nearby candidate proof states.
            guide = math.tanh(candidate_score / 2.0)
            edge_cost = (0.25 if not e_hyps else 1.0) - 0.20 * guide
            state_cost = 0.02 * len(newgoals + rest)
            heapq.heappush(frontier,
                           (priority + edge_cost + state_cost, tie,
                            Node(newgoals + rest, s2,
                                 node.trail + ((slot, hix, step),),
                                 node.depth + 1)))
    return None, exp


def prove_population(goal_tree, index, budget, max_depth, agents=4,
                     creativity=0.55, seed=0, rank=None, say=print,
                     progress=2000, max_open=6, opener_cap=48):
    """Run independent certificate-producing searches under one shared budget.

    Agents share only assertion-usage counts.  Those counts can affect search
    order but cannot enter an emitted proof.  No theorem or intermediate lemma
    is accepted into memory without a Metamath certificate.  ``rank`` is the
    policy-scoring interface for a future leakage-controlled learned model;
    the 8.001 command line intentionally supplies no trained model.
    """
    profiles = make_profiles(agents, creativity, opener_cap)
    shares = schedule_budgets(budget, profiles)
    shared_use = defaultdict(int)
    total_exp = 0

    for i, (profile, share) in enumerate(zip(profiles, shares), 1):
        if say:
            say("    agent %d/%d: %-46s budget %s"
                % (i, len(profiles), profile.summary(), f"{share:,}"))
        if share <= 0:
            continue
        result, used = prove(
            goal_tree, index, share, max_depth, rank=rank, say=say,
            progress=progress, max_open=max_open, profile=profile,
            seed=int(seed) + 1000003 * (i - 1), shared_use=shared_use,
            agent_name=profile.name)
        total_exp += used
        if result is not None:
            return result, total_exp, profile.name
    return None, total_exp, None


# ===========================================================================
#  selftest
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
ax2 $a |- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) $.
${ mpmin $e |- ph $.
   mpmaj $e |- ( ph -> ps ) $.
   ax-mp $a |- ps $. $}
"""


def cmd_selftest(a):
    print("\n" + "=" * 74)
    print("  PREDATOR 8 v%s  --  selftest" % VERSION)
    print("=" * 74 + "\n")
    mm = MM(); mm.read(Toks(SELFTEST))
    by_tc = G.build_grammar(mm)
    fvar, fallback = {}, {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar[d[1]] = lab
            fallback.setdefault(d[0], G.Tree(None, d[0], (), d[1]))

    idx = Index(mm, by_tc, say=lambda s: print("  " + s))
    print("  ax-mp is included: its conclusion is the bare variable `ps`,")
    print("  which 7.0 excluded as undetermined.\n")

    bad = 0

    # (1) the identity  |- ( ph -> ph ).  Its only route is two applications of
    #     ax-mp, which 7.0 could not use at all.
    goal_toks = "( ph -> ph )".split()
    gt = G.parse(goal_toks, "wff", by_tc)
    print("  [1] goal  |- %s" % " ".join(goal_toks))
    print("      route requires ax-mp twice; 7.0 could not attempt this")
    t0 = time.perf_counter()
    res, exp = prove(gt, idx, 20000, 8)
    dt = time.perf_counter() - t0
    if res is None:
        print("      NOT PROVED, %s expansions  <-- FAILED" % f"{exp:,}"); bad += 1
    else:
        root, sub = res
        proof = root.emit(sub, fvar, fallback)
        print("      candidate: %s expansions, %.2fs, %d proof steps"
              % (f"{exp:,}", dt, len(proof)))
        src = SELFTEST + "\nchk $p |- %s $= %s $.\n" % (
            " ".join(goal_toks), " ".join(proof))
        m2 = MM()
        try:
            m2.read(Toks(src))
            r = m2.verify("chk")
            print("      metamath.py verify: %s" % r.upper())
            if r == "ok":
                print("      verified proof")
            bad += (r != "ok")
        except MMError as e:
            print("      metamath.py verify: FAILED -- %s" % e); bad += 1

    # The population scheduler must conserve the global budget exactly; an
    # agent count must never multiply the experiment's declared resources.
    profiles = make_profiles(4, 0.55, 48)
    shares = schedule_budgets(20000, profiles)
    scheduler_ok = (len(shares) == 4 and sum(shares) == 20000
                    and all(x > 0 for x in shares))
    print("\n  [2] population scheduler conserves the global budget")
    print("      allocations: %s" % ", ".join(f"{x:,}" for x in shares))
    print("      %s" % ("passed" if scheduler_ok else "FAILED"))
    bad += (not scheduler_ok)

    # A fixed seed must reproduce the same counterfactual choices.  Different
    # seeds are permitted to explore different compatible routes.
    pool = [(float(100 - i), i) for i in range(100)]
    c1 = _counterfactual_slice(pool, 20, 0.40, random.Random(2301))
    c2 = _counterfactual_slice(pool, 20, 0.40, random.Random(2301))
    counterfactual_ok = (c1 == c2 and len(c1) == 20
                         and any(item >= 12 for _, item in c1))
    print("\n  [3] seeded counterfactual exploration is reproducible")
    print("      %s" % ("passed" if counterfactual_ok else "FAILED"))
    bad += (not counterfactual_ok)

    print("\n  %s\n" % ("all checks passed" if not bad
                        else "%d CHECK(S) FAILED" % bad))
    return 0 if not bad else 1


# ===========================================================================
#  prove
# ===========================================================================
def cmd_easiest(a):
    """Rank set.mm theorems by LOGICAL proof length, shortest first.

    Raw proof length is 95% formula construction, so sorting by it ranks
    theorems by how verbose their notation is.  Counting only |- steps ranks
    them by how much reasoning they need, which is what a prover faces.

    A theorem needing one logical step is the easiest thing this program can
    be asked to do.  If it fails there, the problem is not the budget."""
    from metamath import classify
    print("\n" + "=" * 74)
    print("  EASIEST TARGETS  --  by logical proof length")
    print("=" * 74 + "\n")
    mm = load(a.file)
    kind = classify(mm)

    thms = [l for l in mm.order if mm.labels[l][0] == "$p"]
    if a.scan:
        thms = thms[:a.scan]
    print("\n  measuring %s proofs..." % f"{len(thms):,}")
    rows = []
    for i, lab in enumerate(thms, 1):
        try:
            proof = mm.decompress(lab, mm.proofs[lab])
        except (MMError, RecursionError, ValueError):
            continue
        if "?" in proof:
            continue
        n = sum(1 for st in proof if kind.get(st) == "logic")
        if 0 < n <= a.max_steps:
            rows.append((n, len(proof), lab))
        if a.progress and i % a.progress == 0:
            print("    %s/%s" % (f"{i:,}", f"{len(thms):,}"))

    rows.sort()
    print("\n  %s theorems need %d or fewer logical steps\n"
          % (f"{len(rows):,}", a.max_steps))
    print("  %-5s %-7s %-14s %s" % ("logic", "raw", "label", "statement"))
    print("  " + "-" * 68)
    for n, raw, lab in rows[:a.limit]:
        stat = " ".join(mm.labels[lab][1][3])
        print("  %-5d %-7d %-14s %s" % (n, raw, lab, stat[:40]))
    print("""
  The `logic` column is the number of reasoning steps; `raw` includes the
  formula construction.  Their ratio is the notation factor for that theorem.

  Start at the top.  A one-logical-step theorem is one assertion applied once,
  and if the search cannot find that, no budget will help.

  `easiest` reads stored reference proofs to rank diagnostic targets.  It must
  not be run on a held-out benchmark target during a blind experiment.
""")
    return 0


def cmd_prove(a):
    print("\n" + "=" * 74)
    print("  PREDATOR 8 v%s  --  prove %s" % (VERSION, a.label))
    print("=" * 74 + "\n")
    mm = load(a.file)
    by_tc = G.build_grammar(mm)
    if a.label not in mm.labels:
        print("\n  %s not found\n" % a.label); return 1
    stat = mm.labels[a.label][1][3]
    print("\n  goal  %s" % " ".join(stat))

    fvar, fallback = {}, {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar.setdefault(d[1], lab)
            fallback.setdefault(d[0], G.Tree(None, d[0], (), d[1]))

    # Blind benchmark condition: the search sees only assertions declared
    # before the target.  It never reads mm.proofs[a.label] and cannot use the
    # target's stored reference proof as guidance or training data.
    cut = mm.order.index(a.label)
    print("\n  indexing assertions before %s (parses conclusions once)..." % a.label)
    print("  blind mode: the target's stored proof, if any, is not inspected")
    t0 = time.perf_counter()
    idx = Index(mm, by_tc, upto=cut, say=lambda s: print("  " + s))
    print("    %.1fs" % (time.perf_counter() - t0))

    gt = G.parse(stat[1:], "wff", by_tc)
    if gt is None:
        print("\n  goal does not parse\n"); return 1

    print("\n  population search (global budget %s, agents %d, creativity %.2f,"
          " seed %d, max depth %d)..."
          % (f"{a.budget:,}", a.agents, a.creativity, a.seed,
             a.max_depth))
    t0 = time.perf_counter()
    res, exp, winner = prove_population(
        gt, idx, a.budget, a.max_depth, agents=a.agents,
        creativity=a.creativity, seed=a.seed, progress=a.progress,
        max_open=a.max_open, opener_cap=a.opener_cap)
    dt = time.perf_counter() - t0

    if res is None:
        print("\n  OUTCOME: UNKNOWN UNDER THE DECLARED RESOURCE BOUNDS")
        print("  %s expansions, %.1fs; no verified certificate was found."
              % (f"{exp:,}", dt))
        print("""
  This is not a denial, a counterexample, or evidence that the target is
  unprovable.  The budget, depth limit, open-goal limit, candidate cap, and
  search policy are all finite experimental controls.
""")
        return 1

    root, sub = res
    try:
        proof = root.emit(sub, fvar, fallback)
    except MMError as e:
        print("\n  OUTCOME: PROTOCOL FAILURE")
        print("  A search derivation was found but no certificate could be emitted:")
        print("  %s\n" % e)
        return 2

    print("\n  candidate certificate found by %s after %s expansions, %.1fs;"
          " %s proof steps"
          % (winner, f"{exp:,}", dt, f"{len(proof):,}"))
    print("  no theorem claim is made until the certificate verifier accepts it.")
    out = a.out or ("%s_p8.mm" % a.label)
    with open(out, "w") as f:
        f.write("$( Predator 8.001 candidate certificate for %s; "
                "agent %s, seed %d $)\n" % (a.label, winner, a.seed))
        f.write("$[ %s $]\n" % a.file)
        f.write("chk $p %s $= %s $.\n" % (" ".join(stat), " ".join(proof)))
    print("  wrote %s" % out)

    # Verify immediately, in process.  This is not self-reporting: it is the
    # CV's own stack machine, which knows nothing about how the proof was
    # found.  Writing the file and telling the user to check it is still the
    # primary claim; this just fails fast when the proof is wrong.
    print("\n  handing the certificate to the CV...")
    try:
        chk = MM()
        chk.labels = dict(mm.labels)
        chk.order = list(mm.order)
        chk.proofs = dict(mm.proofs)
        chk.constants, chk.variables = mm.constants, mm.variables
        chk.scope_dvs = dict(mm.scope_dvs)
        dvs, f_hyps, e_hyps, _ = mm.labels[a.label][1]
        chk.labels["__chk__"] = ("$p", (dvs, f_hyps, e_hyps, stat))
        chk.proofs["__chk__"] = proof
        chk.scope_dvs["__chk__"] = mm.scope_dvs.get(a.label, dvs)
        r = chk.verify("__chk__")
        print("  CV verdict: %s" % r.upper())
        if r != "ok":
            print("  OUTCOME: PROTOCOL FAILURE -- not a proof")
            return 2
    except MMError as e:
        print("  CV verdict: FAILED -- %s" % e)
        print("  OUTCOME: PROTOCOL FAILURE -- not a proof")
        return 2
    print("\n  OUTCOME: VERIFIED PROOF")
    print("  The target is proved in the loaded formal environment.")
    print("""
  Predator's word is not evidence.  Independently check the certificate:

      python metamath.py verify %s
""" % out)
    return 0


def main():
    ap = argparse.ArgumentParser(prog="predator8", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest")
    e = sub.add_parser("easiest")
    e.add_argument("file", nargs="?", default="set.mm")
    e.add_argument("--max-steps", type=int, default=2,
                   help="keep theorems needing at most this many logical steps")
    e.add_argument("--scan", type=int, default=8000,
                   help="how many theorems to measure (0 = all)")
    e.add_argument("--limit", type=int, default=30)
    e.add_argument("--progress", type=int, default=2000)
    p = sub.add_parser("prove")
    p.add_argument("file", nargs="?", default="set.mm")
    p.add_argument("--label", required=True)
    p.add_argument("--budget", type=int, default=80000,
                   help="global expansion budget shared by every agent")
    p.add_argument("--max-depth", type=int, default=10)
    p.add_argument("--agents", type=int, default=4)
    p.add_argument("--creativity", type=float, default=0.55,
                   help="unitless population creativity in [0, 1]")
    p.add_argument("--seed", type=int, default=0,
                   help="seed for reproducible nondeterministic search")
    p.add_argument("--opener-cap", type=int, default=48,
                   help="maximum extending assertions retained per state")
    p.add_argument("--max-open", type=int, default=6,
                   help="prune states with more than this many open goals")
    p.add_argument("--progress", type=int, default=2000)
    p.add_argument("--out", default=None)

    a = ap.parse_args()
    if a.cmd == "prove":
        if a.budget < 1:
            ap.error("--budget must be positive")
        if a.agents < 1:
            ap.error("--agents must be positive")
        if not 0.0 <= a.creativity <= 1.0:
            ap.error("--creativity must be between 0 and 1")
        if a.opener_cap < 1 or a.max_open < 1 or a.max_depth < 1:
            ap.error("depth, opener-cap, and max-open must be positive")
    if a.cmd == "selftest":  sys.exit(cmd_selftest(a))
    elif a.cmd == "easiest": sys.exit(cmd_easiest(a))
    elif a.cmd == "prove":   sys.exit(cmd_prove(a))
    else:                    ap.print_help()


def _big_stack(fn):
    import threading
    try:
        threading.stack_size(256 * 1024 * 1024)
    except (ValueError, RuntimeError):
        pass
    box = {}

    def target():
        try:
            box["rc"] = fn()
        except SystemExit as e:
            box["rc"] = e.code
        except RecursionError:
            print("\n  RecursionError -- a term nested deeper than the stack.\n")
            box["rc"] = 2
    t = threading.Thread(target=target, daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(0.2)
    except KeyboardInterrupt:
        print("\n  interrupted.\n")
        return 130
    return box.get("rc", 0)


if __name__ == "__main__":
    sys.exit(_big_stack(main) or 0)