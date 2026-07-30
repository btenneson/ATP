#!/usr/bin/env python3
r"""
audit.py -- adversarial audit of the Ascent kernels.

Three independent checks, none of which trusts the implementation's own
opinion of itself:

 1. FUZZ THE DECISION PROCEDURE.  Generate random formulas over symbolic
    constants; wherever decide() commits to True or False, verify by brute
    force over every assignment in a finite box.  A single mismatch is an
    unsoundness, because decide() is what the `calc` rule trusts.

 2. EXPLOIT THE FRESHNESS CONDITIONS.  gen and exE both introduce a constant
    that is supposed to be arbitrary.  Try to smuggle in a constant that is
    already committed elsewhere -- in the goal, the context, or the LEMMA
    STORE -- and derive something false.

 3. CERTIFY-THEN-RECHECK.  Re-verify every certificate the search produces
    against a kernel built from scratch, and additionally check that the
    certified formula is true under brute-force evaluation wherever it is
    checkable.  A prover that proves a falsehood must be caught here even if
    its own kernel accepted it.

    python audit.py
"""
from __future__ import annotations
import itertools, random, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.setrecursionlimit(100000)

import ascent as A1
import ascent2 as A2
from ascent import sub, poly, show, X

BOX = 6          # brute-force each symbol over 0..BOX-1
random.seed(20260730)


# ---------------------------------------------------------------------------
# 1. fuzz the decision procedure
# ---------------------------------------------------------------------------
def rnd_term(symbols, d=2):
    if d == 0 or random.random() < 0.4:
        if symbols and random.random() < 0.6:
            return ('c', random.choice(symbols))
        return ('n', random.randint(0, 4))
    k = random.choice(['+', '*', 's'])
    if k == 's':
        return ('s', rnd_term(symbols, d - 1))
    return (k, rnd_term(symbols, d - 1), rnd_term(symbols, d - 1))


def rnd_formula(symbols, d=2):
    if d == 0 or random.random() < 0.5:
        op = random.choice(['=', '<', '<='])
        return (op, rnd_term(symbols, 2), rnd_term(symbols, 2))
    k = random.choice(['not', 'and', 'or', 'imp'])
    if k == 'not':
        return ('not', rnd_formula(symbols, d - 1))
    return (k, rnd_formula(symbols, d - 1), rnd_formula(symbols, d - 1))


def ground_eval(p, env):
    """Truth of p under a total assignment env of constants to naturals."""
    k = p[0]
    if k == 'bot':
        return False
    if k in ('=', '<', '<='):
        a, b = term_val(p[1], env), term_val(p[2], env)
        return a == b if k == '=' else (a < b if k == '<' else a <= b)
    if k == 'not':
        return not ground_eval(p[1], env)
    if k == 'and':
        return ground_eval(p[1], env) and ground_eval(p[2], env)
    if k == 'or':
        return ground_eval(p[1], env) or ground_eval(p[2], env)
    if k == 'imp':
        return (not ground_eval(p[1], env)) or ground_eval(p[2], env)
    raise ValueError("ground_eval: %r" % (k,))


def term_val(t, env):
    k = t[0]
    if k == 'n':
        return t[1]
    if k in ('c', 'v'):
        return env[t[1]]
    if k == 's':
        return term_val(t[1], env) + 1
    if k == '+':
        return term_val(t[1], env) + term_val(t[2], env)
    return term_val(t[1], env) * term_val(t[2], env)


def fuzz_decide(decide, label, trials=6000):
    syms = ['a', 'b']
    bad = []
    committed = 0
    for _ in range(trials):
        p = rnd_formula(syms, 2)
        v = decide(p)
        if v is None:
            continue
        committed += 1
        for vals in itertools.product(range(BOX), repeat=len(syms)):
            env = dict(zip(syms, vals))
            if ground_eval(p, env) != v:
                bad.append((p, v, env))
                break
    print("  %-28s %5d/%d committed, %d WRONG"
          % (label, committed, trials, len(bad)))
    for p, v, env in bad[:4]:
        print("      claimed %-5s for  %s   at %s"
              % (v, show(p), env))
    return len(bad)


# ---------------------------------------------------------------------------
# 2. exploit the freshness conditions
# ---------------------------------------------------------------------------
def exploit_freshness():
    print("\n  freshness exploits (each MUST be rejected)")
    fails = 0

    # (a) gen re-using a constant that is committed in the STORE
    K = A2.Kernel(A2.TAG, {}, set(A2.BASE_RULES) | A2.NEG_RULES)
    store = {'committed': ('=', ('c', 'k'), ('n', 0))}   # k = 0 is a lemma
    goal = ('all', 'x', ('=', X('x'), ('n', 0)))         # false: not all x = 0
    cert = ('gen', 'k', ('lemma', 'committed'))
    try:
        K.check(store, [], goal, cert)
        print("      gen over a store constant     ACCEPTED  <-- UNSOUND")
        fails += 1
    except A2.Reject as e:
        print("      gen over a store constant     rejected (%s)"
              % str(e)[:34])

    # (b) exE re-using a constant that is committed in the STORE.
    #     The store asserts ~(w = 0).  Ex.x=0 is TRUE, so exE is entitled to
    #     open it -- but only over a FRESH constant.  If it may re-use w, the
    #     opened hypothesis w = 0 clashes with the stored lemma and bot
    #     follows from a perfectly consistent store, i.e. everything does.
    ex = ('ex', 'x', ('=', X('x'), ('n', 0)))
    Lw = ('not', ('=', ('c', 'w'), ('n', 0)))
    store2 = {'L': Lw}
    cert2 = ('exE', ex, 'w',
             ('wit', ('n', 0), ('calc',)),
             ('cut', Lw, ('lemma', 'L'), ('clash', 1, 0)))
    try:
        K.check(store2, [], A2.BOT, cert2)
        print("      exE over a store constant     ACCEPTED  <-- UNSOUND")
        fails += 1
    except A2.Reject as e:
        print("      exE over a store constant     rejected (%s)"
              % str(e)[:34])

    # (c) exE re-using a constant already in the context
    ctx = [('=', ('c', 'w'), ('n', 3))]
    try:
        K.check({}, list(ctx), A2.BOT,
                ('exE', ex, 'w', ('wit', ('n', 0), ('calc',)),
                 ('contra', 0)))
        print("      exE over a context constant   ACCEPTED  <-- UNSOUND")
        fails += 1
    except A2.Reject as e:
        print("      exE over a context constant   rejected (%s)"
              % str(e)[:34])
    return fails


# ---------------------------------------------------------------------------
# 3. certify-then-recheck the whole suite
# ---------------------------------------------------------------------------
def recheck_suite():
    print("\n  independent re-verification of every certificate")
    bad = 0
    for label, cfg in A2.REGIMES:
        rules = set(A2.BASE_RULES) | (A2.NEG_RULES if cfg["neg"] else set())
        K = A2.Kernel(A2.TAG, {}, rules)
        store = {}
        S = A2.Search(K, store, 4, 12, neg=cfg["neg"], rank=cfg["rank"])
        n_ok = n_bad = 0
        for name, group, phi in A2.SUITE:
            C = S.prove(phi)
            if C is None:
                continue
            fresh = A2.Kernel(A2.TAG, {}, rules)   # brand-new kernel
            try:
                fresh.check(store, [], phi, C)
            except A2.Reject:
                n_bad += 1
                continue
            # and is the formula actually TRUE?
            cs = sorted(A2.consts(phi))
            truth = True
            if len(cs) <= 2:
                for vals in itertools.product(range(BOX), repeat=len(cs)):
                    env = dict(zip(cs, vals))
                    try:
                        if not closed_truth(phi, env):
                            truth = False
                            break
                    except (ValueError, KeyError):
                        truth = None
                        break
            else:
                truth = None
            if truth is False:
                print("      %-10s CERTIFIED A FALSEHOOD: %s"
                      % (name, show(phi)))
                n_bad += 1
            else:
                n_ok += 1
                if cfg["pool"]:
                    store[name] = phi
        print("      %-9s %2d certificates re-verified, %d bad"
              % (label, n_ok, n_bad))
        bad += n_bad
    return bad


def closed_truth(p, env, box=BOX):
    """Brute-force truth over the box, quantifiers included."""
    k = p[0]
    if k == 'bot':
        return False
    if k in ('=', '<', '<='):
        return ground_eval(p, env)
    if k == 'not':
        return not closed_truth(p[1], env, box)
    if k == 'and':
        return closed_truth(p[1], env, box) and closed_truth(p[2], env, box)
    if k == 'or':
        return closed_truth(p[1], env, box) or closed_truth(p[2], env, box)
    if k == 'imp':
        return (not closed_truth(p[1], env, box)) \
            or closed_truth(p[2], env, box)
    if k in ('all', 'ex', 'allb', 'exb'):
        # unbounded quantifiers cannot be settled in a finite box; report
        # unknown rather than guessing
        raise ValueError("quantified")
    raise ValueError(k)


# ---------------------------------------------------------------------------
def main():
    print("=" * 74)
    print("  ASCENT AUDIT")
    print("=" * 74)
    print("\n  fuzzing the decision procedure (%d assignments per formula)"
          % (BOX ** 2))
    n = 0
    n += fuzz_decide(A1.decide, "ascent.decide")
    n += fuzz_decide(A2.decide, "ascent2.decide")
    n += exploit_freshness()
    n += recheck_suite()
    print("\n" + "=" * 74)
    print("  %s" % ("ALL CHECKS PASSED" if n == 0
                    else "%d PROBLEM(S) FOUND" % n))
    print("=" * 74)
    return 0 if n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
