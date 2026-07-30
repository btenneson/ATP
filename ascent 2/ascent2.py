#!/usr/bin/env python3
r"""
ASCENT 2 -- staged regimes.  Change, test, repeat.

ascent.py is frozen as the note's appendix.  This file evolves it in stages,
each stage gated by a flag so every earlier stage stays measurable on the
same suite.  The point is the DELTA, not the final number.

    R0  base      the rules ascent.py ships with
    R1  +neg      bot, notI, raa, absurd, orI, orE, exE, cut, contra, clash
    R2  +pool     every certified theorem is carried into the store, so a
                  later target can cite it in ONE node
    R3  +rank     hand-written candidate ordering -- the baseline any
                  learned policy has to beat

Knobs, unchanged in meaning:  -t depth, -u witness bound, -v reflection.

WHAT EACH STAGE IS SUPPOSED TO SHOW
-----------------------------------
R1 exists because P != NP is a NEGATION and the base rule set has no rule
that introduces one.  No setting of t, u, v repairs that: parameters bound
the search, they do not enlarge the calculus.  The negated targets in the
suite must fail at R0 and pass at R1, or the stage did nothing.

R2 is the "learn all the tier-2 theorems and their proofs" question made
measurable.  Citing a stored lemma costs one node no matter how expensive
the lemma was, which is cut, which is the only mechanism here that changes
proof LENGTH rather than search time.  The lemma-dependent targets must fail
at R0/R1 and pass at R2.

R3 is a policy, not a rule.  It can only reorder what R0-R2 already made
reachable, so it must move NODES and not COVERAGE.  If R3 changes coverage,
something is wrong with R0-R2's search, not with the heuristic.

SOUNDNESS IS RE-CHECKED AT EVERY STAGE.  Adding rules is exactly where a
kernel breaks, and a coverage gain bought with an unsound rule is worse than
no gain.  Every regime runs the probe battery before it runs the suite.

Brian Tenneson.  Implementation by Claude (Anthropic).
"""
from __future__ import annotations
import argparse, itertools, json, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.setrecursionlimit(100000)

from ascent import (sub, tsub, teval, poly, padd, pneg, show, showt,
                    tier, tier_name, syms, occurs_sym, X)     # noqa: E402

BOT = ('bot',)
TAG = "<Ascent2>"
_eigen = itertools.count(1)


# ===========================================================================
#                        DECISION PROCEDURE (extended)
# ===========================================================================
def always_pos(d):
    """Is the polynomial d strictly positive for every assignment over N?

    Sufficient: every non-constant coefficient is non-negative and the
    constant term is positive.  Sound, incomplete."""
    return all(c > 0 for m, c in d.items() if m != ()) and d.get((), 0) > 0


def always_nonneg(d):
    return all(c > 0 for m, c in d.items() if m != ()) and d.get((), 0) >= 0


def decide(p, fuel=10000):
    """Three-valued.  Extends ascent.decide with two things R1 needs:

      * bot is False;
      * an equality is FALSE when one side strictly dominates the other over
        N -- so Sx = 0 is refutable for symbolic x, which is what makes
        ~(Ex. Sx = 0) reachable at all."""
    k = p[0]
    if k == 'bot':
        return False
    if k in ('=', '<', '<='):
        pa, pb = poly(p[1]), poly(p[2])
        d = padd(pb, pneg(pa))          # rhs - lhs
        dn = padd(pa, pneg(pb))         # lhs - rhs
        if k == '=':
            if pa == pb:
                return True
            if always_pos(d) or always_pos(dn):
                return False            # one side strictly dominates
            if all(m == () for m in d):
                return False
            return None
        if k == '<':
            if always_pos(d):
                return True
            if always_nonneg(dn):
                return False            # lhs >= rhs always
            return None
        if always_nonneg(d):
            return True
        if always_pos(dn):
            return False
        return None
    if k == 'not':
        v = decide(p[1], fuel)
        return None if v is None else not v
    if k in ('and', 'or', 'imp'):
        a, b = decide(p[1], fuel), decide(p[2], fuel)
        if k == 'and':
            if a is False or b is False:
                return False
            return True if (a and b) else None
        if k == 'or':
            if a is True or b is True:
                return True
            return False if (a is False and b is False) else None
        if a is False or b is True:
            return True
        return False if (a is True and b is False) else None
    if k in ('allb', 'exb'):
        n = teval(p[2])
        if n is None or n > fuel:
            return None
        for i in range(n):
            v = decide(sub(p[3], p[1], ('n', i)), fuel)
            if v is None:
                return None
            if k == 'allb' and not v:
                return False
            if k == 'exb' and v:
                return True
        return k == 'allb'
    return None


# ===========================================================================
#                                 KERNEL
# ===========================================================================
class Reject(Exception):
    pass


BASE_RULES = {'calc', 'hyp', 'lemma', 'impI', 'impE', 'andI', 'andE',
              'gen', 'inst', 'wit', 'allbI', 'exbI', 'ind', 'nec'}
NEG_RULES = {'notI', 'raa', 'absurd', 'orI', 'orE', 'exE', 'cut',
             'contra', 'clash'}


class Kernel:
    def __init__(self, tag, names, rules=None):
        self.tag = tag
        self.names = names
        self.rules = set(rules) if rules else set(BASE_RULES)
        self.calls = 0

    def check(self, store, ctx, phi, C):
        self.calls += 1
        if not isinstance(C, tuple) or not C:
            raise Reject("malformed certificate")
        k = C[0]
        if k not in self.rules:
            raise Reject("rule %r not enabled in this regime" % (k,))

        if k == 'calc':
            if decide(phi) is not True:
                raise Reject("calc: %s is not decided true" % show(phi))
            return True
        if k == 'hyp':
            if not (0 <= C[1] < len(ctx)) or ctx[C[1]] != phi:
                raise Reject("hyp: not in context")
            return True
        if k == 'lemma':
            if store.get(C[1]) != phi:
                raise Reject("lemma %s is not %s" % (C[1], show(phi)))
            return True
        if k == 'impI':
            if phi[0] != 'imp':
                raise Reject("impI: goal is not an implication")
            return self.check(store, ctx + [phi[1]], phi[2], C[1])
        if k == 'impE':
            self.check(store, ctx, ('imp', C[1], phi), C[2])
            return self.check(store, ctx, C[1], C[3])
        if k == 'andI':
            if phi[0] != 'and':
                raise Reject("andI: goal is not a conjunction")
            self.check(store, ctx, phi[1], C[1])
            return self.check(store, ctx, phi[2], C[2])
        if k == 'andE':
            i, conj = C[1], C[2]
            if conj[0] != 'and' or conj[1 + i] != phi:
                raise Reject("andE: projection mismatch")
            return self.check(store, ctx, conj, C[3])
        if k == 'gen':
            if phi[0] != 'all':
                raise Reject("gen: goal is not universal")
            nm = C[1]
            if occurs_sym(nm, phi) or any(occurs_sym(nm, h) for h in ctx) \
                    or any(occurs_sym(nm, f) for f in store.values()):
                raise Reject("gen: eigenvariable %s is not fresh" % nm)
            return self.check(store, ctx, sub(phi[2], phi[1], ('c', nm)),
                              C[2])
        if k == 'inst':
            t, univ = C[1], C[2]
            if univ[0] != 'all' or sub(univ[2], univ[1], t) != phi:
                raise Reject("inst: instance mismatch")
            return self.check(store, ctx, univ, C[3])
        if k == 'wit':
            if phi[0] != 'ex':
                raise Reject("wit: goal is not existential")
            return self.check(store, ctx, sub(phi[2], phi[1], C[1]), C[2])
        if k == 'allbI':
            if phi[0] != 'allb':
                raise Reject("allbI: goal is not bounded-universal")
            n = teval(phi[2])
            if n is None or n != len(C[1]):
                raise Reject("allbI: wrong number of instances")
            for i, Ci in enumerate(C[1]):
                self.check(store, ctx, sub(phi[3], phi[1], ('n', i)), Ci)
            return True
        if k == 'exbI':
            if phi[0] != 'exb':
                raise Reject("exbI: goal is not bounded-existential")
            n = teval(phi[2])
            if n is None or not (0 <= C[1] < n):
                raise Reject("exbI: index out of range")
            return self.check(store, ctx, sub(phi[3], phi[1], ('n', C[1])),
                              C[2])
        if k == 'ind':
            if phi[0] != 'all':
                raise Reject("ind: goal is not universal")
            x, psi = phi[1], phi[2]
            self.check(store, ctx, sub(psi, x, ('n', 0)), C[1])
            step = ('all', x, ('imp', psi, sub(psi, x, ('s', ('v', x)))))
            return self.check(store, ctx, step, C[2])
        if k == 'nec':
            if phi[0] != 'pr' or phi[1] != self.tag:
                raise Reject("nec: goal is not Pr(<A>, -)")
            psi = self.names.get(phi[2])
            if psi is None:
                raise Reject("nec: %s names no formula" % phi[2])
            return self.check(store, [], psi, C[1])

        # ---------------- R1 -------------------------------------------
        if k == 'contra':
            # a decidably FALSE hypothesis entails anything
            i = C[1]
            if not (0 <= i < len(ctx)) or decide(ctx[i]) is not False:
                raise Reject("contra: ctx[%r] is not decidably false" % (i,))
            return True
        if k == 'clash':
            i, j = C[1], C[2]
            if not (0 <= i < len(ctx) and 0 <= j < len(ctx)):
                raise Reject("clash: index out of range")
            if ctx[i] != ('not', ctx[j]):
                raise Reject("clash: ctx[%d] is not the negation of ctx[%d]"
                             % (i, j))
            return True
        if k == 'notI':
            if phi[0] != 'not':
                raise Reject("notI: goal is not a negation")
            return self.check(store, ctx + [phi[1]], BOT, C[1])
        if k == 'raa':
            # classical reductio
            return self.check(store, ctx + [('not', phi)], BOT, C[1])
        if k == 'absurd':
            A = C[1]
            self.check(store, ctx, A, C[2])
            return self.check(store, ctx, ('not', A), C[3])
        if k == 'orI':
            if phi[0] != 'or':
                raise Reject("orI: goal is not a disjunction")
            if C[1] not in (0, 1):
                raise Reject("orI: bad side")
            return self.check(store, ctx, phi[1 + C[1]], C[2])
        if k == 'orE':
            disj = C[1]
            if disj[0] != 'or':
                raise Reject("orE: not a disjunction")
            self.check(store, ctx, disj, C[2])
            self.check(store, ctx + [disj[1]], phi, C[3])
            return self.check(store, ctx + [disj[2]], phi, C[4])
        if k == 'exE':
            exphi, nm = C[1], C[2]
            if exphi[0] != 'ex':
                raise Reject("exE: not an existential")
            # The STORE must be checked as well as the goal and the context.
            # Omitting it is a genuine unsoundness, not a technicality: if the
            # store holds ~(w = 0) and exE may re-bind w while opening the
            # true statement Ex. x = 0, the opened hypothesis w = 0 clashes
            # with the lemma and bot follows from a consistent store.  The
            # kernel must not rely on the search's habit of generating fresh
            # names -- that is precisely what a trusted kernel is for.
            if occurs_sym(nm, phi) or occurs_sym(nm, exphi) \
                    or any(occurs_sym(nm, h) for h in ctx) \
                    or any(occurs_sym(nm, f) for f in store.values()):
                raise Reject("exE: witness constant %s is not fresh" % nm)
            self.check(store, ctx, exphi, C[3])
            return self.check(store,
                              ctx + [sub(exphi[2], exphi[1], ('c', nm))],
                              phi, C[4])
        if k == 'cut':
            A = C[1]
            self.check(store, ctx, A, C[2])
            return self.check(store, ctx + [A], phi, C[3])

        raise Reject("unknown certificate form %r" % (k,))


# ===========================================================================
#                                 SEARCH
# ===========================================================================
class Search:
    def __init__(self, kernel, store, t, u, neg=False, rank=False):
        self.K = kernel
        self.store = store
        self.t = t
        self.u = u
        self.neg = neg
        self.rank = rank
        self.nodes = 0

    # -- candidate witness terms ----------------------------------------
    def witnesses(self, phi, ctx, mode='wit'):
        out = [('n', n) for n in range(self.u + 1)]
        inscope = sorted(syms(phi) | {s for h in ctx for s in syms(h)})
        for s in inscope:
            base = ('c', s)
            out.append(base)
            tt = base
            for _ in range(min(self.u, 3)):
                tt = ('s', tt)
                out.append(tt)
            out.append(('*', ('n', 2), base))
        if self.rank:
            out.sort(key=lambda tm: self._score(tm, phi, mode))
        return out

    def _score(self, tm, phi, mode):
        """R3 heuristic -- pure policy, reorders only, admits nothing new.

        It has to be CONTEXT-SENSITIVE, and discovering that is the entire
        value of hand-building a baseline before reaching for a model.  There
        are three regimes, not one, and the first version of this function
        collapsed them into a single rule and made the suite SLOWER:

          refuting a universal hypothesis -- knocked down by a small
            numeral almost every time, so size ascending;

          witnessing under a symbol in scope -- the goal sits under a gen,
            the witness is nearly always a term in the eigenconstant, so
            overlap descending (this is what buys pi3 and pi4);

          witnessing a CLOSED goal -- no eigenconstant exists to build
            from, so a symbolic term is dead weight; numerals first.

        Sorting all three the second way cost +50 nodes on min_exists alone,
        whose witness is the numeral 0.  A learned policy will have to
        rediscover this split; the point of the baseline is that we now know
        what it has to beat, and why."""
        size = term_size(tm)
        if mode == 'refute':
            return (size, 0)
        goal_c = consts(phi)
        if not goal_c:
            return (0 if tm[0] == 'n' else 1, size)
        return (-len(tconsts(tm, set()) & goal_c), size)

    # -- main -----------------------------------------------------------
    def prove(self, phi, depth=None, ctx=()):
        if depth is None:
            depth = self.t
        self.nodes += 1
        if depth < 0 or self.nodes > 200000:
            return None
        ctx = tuple(ctx)

        if decide(phi) is True:
            return ('calc',)
        for i, h in enumerate(ctx):
            if h == phi:
                return ('hyp', i)
        for nm, f in self.store.items():
            if f == phi:
                return ('lemma', nm)
        if depth == 0:
            return None

        k = phi[0]

        if k == 'bot' and self.neg:
            return self.prove_bot(depth, ctx)

        if k == 'imp':
            c = self.prove(phi[2], depth - 1, ctx + (phi[1],))
            return ('impI', c) if c else None
        if k == 'and':
            c1 = self.prove(phi[1], depth - 1, ctx)
            if not c1:
                return None
            c2 = self.prove(phi[2], depth - 1, ctx)
            return ('andI', c1, c2) if c2 else None
        if k == 'or' and self.neg:
            for i in (0, 1):
                c = self.prove(phi[1 + i], depth - 1, ctx)
                if c:
                    return ('orI', i, c)
            return None
        if k == 'not' and self.neg:
            c = self.prove_bot(depth - 1, ctx + (phi[1],))
            return ('notI', c) if c else None
        if k == 'exb':
            n = teval(phi[2])
            if n is None:
                return None
            for i in range(min(n, self.u)):
                c = self.prove(sub(phi[3], phi[1], ('n', i)), depth - 1, ctx)
                if c:
                    return ('exbI', i, c)
            return None
        if k == 'allb':
            n = teval(phi[2])
            if n is None or n > self.u:
                return None
            cs = []
            for i in range(n):
                c = self.prove(sub(phi[3], phi[1], ('n', i)), depth - 1, ctx)
                if not c:
                    return None
                cs.append(c)
            return ('allbI', cs)
        if k == 'ex':
            for tm in self.witnesses(phi, ctx):
                c = self.prove(sub(phi[2], phi[1], tm), depth - 1, ctx)
                if c:
                    return ('wit', tm, c)
            return None
        if k == 'all':
            nm = "e%d" % next(_eigen)
            c = self.prove(sub(phi[2], phi[1], ('c', nm)), depth - 1, ctx)
            if c:
                return ('gen', nm, c)
            x, psi = phi[1], phi[2]
            c0 = self.prove(sub(psi, x, ('n', 0)), depth - 1, ctx)
            if c0:
                step = ('all', x, ('imp', psi, sub(psi, x, ('s', ('v', x)))))
                cs = self.prove(step, depth - 1, ctx)
                if cs:
                    return ('ind', c0, cs)
            return None

        # atoms: last resort, classical reductio
        if self.neg and depth >= 2:
            c = self.prove_bot(depth - 2, ctx + (('not', phi),))
            if c:
                return ('raa', c)
        return None

    # -- deriving absurdity ---------------------------------------------
    def prove_bot(self, depth, ctx):
        self.nodes += 1
        if depth < 0 or self.nodes > 200000:
            return None
        ctx = tuple(ctx)

        # 1. a hypothesis that is outright false
        for i, h in enumerate(ctx):
            if decide(h) is False:
                return ('contra', i)
        # 2. an explicit contradictory pair
        for i, h in enumerate(ctx):
            if h[0] == 'not':
                for j, g in enumerate(ctx):
                    if h[1] == g:
                        return ('clash', i, j)
        if depth == 0:
            return None

        # 3. instantiate a universal hypothesis and look for falsity
        for i, h in enumerate(ctx):
            if h[0] != 'all':
                continue
            for tm in self.witnesses(h, ctx, mode='refute'):
                inst = sub(h[2], h[1], tm)
                if decide(inst) is False:
                    return ('cut', inst,
                            ('inst', tm, h, ('hyp', i)),
                            ('contra', len(ctx)))
        # 4. open an existential hypothesis and recurse
        for i, h in enumerate(ctx):
            if h[0] != 'ex':
                continue
            nm = "w%d" % next(_eigen)
            body = sub(h[2], h[1], ('c', nm))
            c = self.prove_bot(depth - 1, ctx + (body,))
            if c:
                return ('exE', h, nm, ('hyp', i), c)
        # 5. a negated hypothesis whose subject we can now prove
        for i, h in enumerate(ctx):
            if h[0] != 'not':
                continue
            c = self.prove(h[1], depth - 1, ctx)
            if c:
                return ('absurd', h[1], c, ('hyp', i))
        return None


def tconsts(t, acc):
    """Eigenconstants only -- ('c', name).  NOT bound variables.

    syms() from ascent.py collects ('v', x) as well, so on a closed goal like
    Ex.Ay. x <= y it returns {'x','y'}: the binder names.  Scoring witness
    overlap against those is meaningless, and it silently disabled the
    closed-goal branch of the heuristic below.  What a witness can usefully
    be built from is the eigenconstants actually in scope, nothing else."""
    if t[0] == 'c':
        acc.add(t[1])
    elif t[0] == 's':
        tconsts(t[1], acc)
    elif t[0] in ('+', '*'):
        tconsts(t[1], acc)
        tconsts(t[2], acc)
    return acc


def consts(p, acc=None):
    if acc is None:
        acc = set()
    k = p[0]
    if k in ('=', '<', '<='):
        tconsts(p[1], acc)
        tconsts(p[2], acc)
    elif k == 'not':
        consts(p[1], acc)
    elif k in ('and', 'or', 'imp'):
        consts(p[1], acc)
        consts(p[2], acc)
    elif k in ('all', 'ex'):
        consts(p[2], acc)
    elif k in ('allb', 'exb'):
        tconsts(p[2], acc)
        consts(p[3], acc)
    return acc


def tsyms_local(t, acc=None):
    if acc is None:
        acc = set()
    if t[0] in ('v', 'c'):
        acc.add(t[1])
    elif t[0] == 's':
        tsyms_local(t[1], acc)
    elif t[0] in ('+', '*'):
        tsyms_local(t[1], acc)
        tsyms_local(t[2], acc)
    return acc


def term_size(t):
    if t[0] in ('n', 'v', 'c'):
        return 1
    if t[0] == 's':
        return 1 + term_size(t[1])
    return 1 + term_size(t[1]) + term_size(t[2])


# ===========================================================================
#                              TARGET SUITE
# ===========================================================================
# group: what stage is supposed to unlock it
SUITE = [
    # --- base arithmetic, tier 0-2 -----------------------------------
    ("add_closed",  'base', ('=', ('+', ('n', 2), ('n', 2)), ('n', 4))),
    ("bnd_lt",      'base', ('allb', 'x', ('n', 5), ('<', X('x'), ('n', 5)))),
    ("ex_solve",    'base', ('ex', 'x', ('=', ('+', X('x'), ('n', 3)),
                                         ('n', 7)))),
    ("ex_square",   'base', ('ex', 'x', ('=', ('*', X('x'), X('x')),
                                         ('n', 49)))),
    ("all_succ",    'base', ('all', 'x', ('<', X('x'), ('s', X('x'))))),
    ("all_add0",    'base', ('all', 'x', ('=', ('+', X('x'), ('n', 0)),
                                          X('x')))),
    ("unbounded",   'base', ('all', 'x', ('ex', 'y', ('<', X('x'), X('y'))))),
    ("min_exists",  'base', ('ex', 'x', ('all', 'y', ('<=', X('x'), X('y'))))),
    # --- tier 3 and 4 ------------------------------------------------
    ("pi3",         'base', ('all', 'x', ('ex', 'y', ('all', 'z',
                     ('<', X('x'), ('+', X('y'), X('z'))))))),
    ("pi4",         'base', ('all', 'x', ('ex', 'y', ('all', 'z', ('ex', 'u',
                     ('<=', X('x'), ('+', X('y'), ('+', X('z'), X('u'))))))))),
    # --- negated: must FAIL at R0, PASS at R1 -------------------------
    ("no_pred_0",   'neg', ('not', ('ex', 'x', ('=', ('s', X('x')),
                                                ('n', 0))))),
    ("not_all_0",   'neg', ('not', ('all', 'x', ('=', X('x'), ('n', 0))))),
    ("no_self_lt",  'neg', ('not', ('ex', 'x', ('<', X('x'), X('x'))))),
    ("no_max",      'neg', ('not', ('ex', 'x', ('all', 'y',
                                                ('<', X('y'), X('x')))))),
    ("disj",        'neg', ('or', ('=', ('n', 1), ('n', 2)),
                            ('<', ('n', 1), ('n', 2)))),
    # --- lemma-dependent: must FAIL at R0/R1, PASS at R2 --------------
    # Each is a conjunction of targets proved EARLIER in the suite.  From
    # scratch the andI node plus the deepest conjunct exceeds t; with the
    # pool each conjunct is a one-node citation, so the whole thing fits in
    # depth 2.  That gap is cut buying proof LENGTH, which is the only
    # mechanism here that can.
    ("pool_2",      'pool', ('and',
                             ('all', 'x', ('ex', 'y', ('all', 'z',
                              ('<', X('x'), ('+', X('y'), X('z')))))),
                             ('all', 'x', ('ex', 'y', ('all', 'z',
                              ('ex', 'u', ('<=', X('x'),
                               ('+', X('y'), ('+', X('z'), X('u'))))))))
                             )),
    ("pool_3",      'pool', ('and',
                             ('all', 'x', ('ex', 'y', ('all', 'z',
                              ('ex', 'u', ('<=', X('x'),
                               ('+', X('y'), ('+', X('z'), X('u')))))))),
                             ('and',
                              ('all', 'x', ('ex', 'y', ('all', 'z',
                               ('<', X('x'), ('+', X('y'), X('z')))))),
                              ('all', 'x', ('ex', 'y', ('<', X('x'),
                                                        X('y'))))))),
    # --- out of reach at t=4 for every regime: tier 5 -----------------
    ("pi5",         'ceiling', ('all', 'x', ('ex', 'y', ('all', 'z',
                     ('ex', 'u', ('all', 'w',
                      ('<=', X('x'), ('+', X('y'), ('+', X('z'),
                       ('+', X('u'), X('w'))))))))))),
]


def probes():
    """Malformed certificates that must be rejected in every regime."""
    return [
        ("false by calc", ('=', ('n', 0), ('n', 1)), ('calc',)),
        ("unstored lemma", ('=', ('n', 0), ('n', 1)), ('lemma', 'nope')),
        ("nec for unproved", ('pr', TAG, "<f>"), ('nec', ('calc',))),
        ("nec wrong tag", ('pr', "<Other>", "<f>"), ('nec', ('calc',))),
        ("gen from instance", ('all', 'x', ('=', X('x'), ('n', 0))),
         ('gen', 'z', ('calc',))),
        ("gen captured eigen", ('all', 'x', ('=', X('x'), ('c', 'k'))),
         ('gen', 'k', ('calc',))),
        ("wit with no witness",
         ('ex', 'x', ('<', ('s', X('x')), X('x'))),
         ('wit', ('n', 3), ('calc',))),
        ("ind without base", ('all', 'x', ('<', X('x'), ('n', 0))),
         ('ind', ('calc',), ('calc',))),
        # R1-specific
        ("contra on a true hyp", BOT, ('contra', 0)),
        ("clash on unrelated", BOT, ('clash', 0, 1)),
        ("exE captured witness",
         ('=', ('c', 'w'), ('n', 0)),
         ('exE', ('ex', 'x', ('=', X('x'), ('n', 0))), 'w',
          ('calc',), ('calc',))),
        ("raa proving falsehood", ('=', ('n', 0), ('n', 1)),
         ('raa', ('contra', 0))),
        # Regression probe.  This one was NOT in the original battery, the
        # battery reported 12/12, and the hole was real: exE checked the goal
        # and the context for freshness but not the store, so bot followed
        # from a consistent store and the kernel could prove anything.
        # Found by audit.py, not by the battery.
        ("exE over a store constant", BOT,
         ('exE', ('ex', 'x', ('=', X('x'), ('n', 0))), 'w',
          ('wit', ('n', 0), ('calc',)),
          ('cut', ('not', ('=', ('c', 'w'), ('n', 0))),
           ('lemma', 'L'), ('clash', 1, 0)))),
    ]


def run_probes(K):
    ctx = [('=', ('n', 1), ('n', 1)), ('<', ('n', 0), ('n', 1))]
    # a NON-EMPTY store, so store-freshness probes can actually bite
    store = {'L': ('not', ('=', ('c', 'w'), ('n', 0)))}
    caught = total = 0
    detail = []
    for label, phi, C in probes():
        total += 1
        try:
            K.check(store, list(ctx), phi, C)
            detail.append((label, "ACCEPTED"))
        except Reject as e:
            caught += 1
            detail.append((label, str(e)[:38]))
    return caught, total, detail


# ===========================================================================
#                               REGIMES
# ===========================================================================
REGIMES = [
    ("R0 base",  dict(neg=False, pool=False, rank=False)),
    ("R1 +neg",  dict(neg=True,  pool=False, rank=False)),
    ("R2 +pool", dict(neg=True,  pool=True,  rank=False)),
    ("R3 +rank", dict(neg=True,  pool=True,  rank=True)),
]


def run_regime(cfg, t, u, verbose=False):
    rules = set(BASE_RULES) | (NEG_RULES if cfg["neg"] else set())
    K = Kernel(TAG, {"<f>": ('=', ('n', 0), ('n', 1))}, rules)
    caught, total, pdetail = run_probes(K)

    store = {}
    S = Search(K, store, t, u, neg=cfg["neg"], rank=cfg["rank"])
    rows, solved = [], 0
    for name, group, phi in SUITE:
        S.nodes = 0
        t0 = time.perf_counter()
        C = S.prove(phi)
        dt = time.perf_counter() - t0
        ok = False
        note = ""
        if C is not None:
            try:
                K.check(store, [], phi, C)
                ok = True
            except Reject as e:
                note = "REJECTED: %s" % str(e)[:40]
        solved += ok
        # R2: carry the certified theorem forward as a citable lemma
        if ok and cfg["pool"]:
            store[name] = phi
        rows.append(dict(target=name, group=group, tier=tier_name(phi),
                         certified=ok, nodes=S.nodes,
                         seconds=round(dt, 4), note=note))
        if verbose:
            print("      %-12s %-6s %-7s %s  %s nodes"
                  % (name, group, tier_name(phi),
                     "OK " if ok else " . ", f"{S.nodes:,}"))
    # Nodes on CERTIFIED targets is the number a policy can move.  Nodes
    # burned on a target that fails is just how long exhaustion takes, and
    # no reordering shortens an exhaustive search -- pi5 costs 4,417 in
    # every regime and swamps the total if you report it undivided.
    return dict(solved=solved, rows=rows,
                nodes=sum(r["nodes"] for r in rows),
                nodes_certified=sum(r["nodes"] for r in rows
                                    if r["certified"]),
                probes_caught=caught, probes_total=total,
                probe_detail=pdetail, unsound=(caught != total))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-t", "--depth", type=int, default=4)
    ap.add_argument("-u", "--witness", type=int, default=12)
    ap.add_argument("-v", "--reflect", type=int, default=3)
    ap.add_argument("--out", default="results_ascent2")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print("  ASCENT 2 -- staged regimes   t=%d  u=%d  v=%d"
          % (a.depth, a.witness, a.reflect))
    print("=" * 78)

    results, prev = [], None
    for label, cfg in REGIMES:
        r = run_regime(cfg, a.depth, a.witness, a.verbose)
        r["regime"] = label
        results.append(r)
        by_group = defaultdict(lambda: [0, 0])
        for row in r["rows"]:
            by_group[row["group"]][1] += 1
            if row["certified"]:
                by_group[row["group"]][0] += 1
        gsum = "  ".join("%s %d/%d" % (g, v[0], v[1])
                         for g, v in sorted(by_group.items()))
        delta = "" if prev is None else "  (%+d)" % (r["solved"] -
                                                     prev["solved"])
        ndelta = ""
        if prev is not None and prev["nodes_certified"]:
            pct = 100.0 * (prev["nodes_certified"] - r["nodes_certified"]) \
                / prev["nodes_certified"]
            ndelta = "  (%+.0f%%)" % (-pct)
        print("\n  %-9s  certified %2d/%-2d%-7s  nodes-on-certified %5s%-8s"
              "  soundness %d/%d%s"
              % (label, r["solved"], len(SUITE), delta,
                 f"{r['nodes_certified']:,}", ndelta,
                 r["probes_caught"], r["probes_total"],
                 "  <-- UNSOUND" if r["unsound"] else ""))
        print("             %s" % gsum)
        if prev is not None:
            gained = [x["target"] for x, y in zip(r["rows"], prev["rows"])
                      if x["certified"] and not y["certified"]]
            lost = [x["target"] for x, y in zip(r["rows"], prev["rows"])
                    if y["certified"] and not x["certified"]]
            if gained:
                print("             gained: %s" % ", ".join(gained))
            if lost:
                print("             LOST:   %s   <-- regression"
                      % ", ".join(lost))
        prev = r

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "regimes.json"), "w") as f:
        json.dump(dict(params=dict(t=a.depth, u=a.witness, v=a.reflect),
                       results=results), f, indent=2)
    print("\n  wrote %s/regimes.json" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
