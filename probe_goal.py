#!/usr/bin/env python3
"""
probe_goal.py -- run Predator_4 against a goal that is NOT in the corpus.

WHY THIS FILE EXISTS
--------------------
`predator4.py prove --label X` requires X to be a statement already in set.mm:
it looks the label up, reads the premises the proof actually cites, and scores
the ranking against them.  For a goal you are *proposing* -- one with no proof
in the library, and possibly no proof anywhere -- there is no gold set, so
recall@k and effort are undefined.

What remains defined, and what this script measures, is the ranking itself:
given a goal expressed in the corpus vocabulary, which statements does
Predator_4 put at the top?  That is the only question a premise selector can
answer about an unproved goal, and it is a fair test: a good selector should
surface the lemmas a human would reach for.

THE NOTATION PROBLEM
--------------------
Every Predator_4 feature is a function of TOKEN OVERLAP between goal and
candidate.  A token the corpus has never seen contributes nothing -- it cannot
match anything, so it neither helps nor hurts, it is simply invisible.  A goal
written entirely in unseen tokens gets a feature vector of near-zeros and the
ranking degenerates to the usage prior.

set.mm contains no nonstandard analysis: there is no ultrapower, no `*RR`, no
class of infinitesimals.  It DOES contain:

    ~~      equinumerosity        (df-en:  A ~~ B  iff  some bijection A-1-1-onto->B)
    RR      the reals
    RR*     the EXTENDED reals    (note: not the hyperreals; different object)
    ~<_     dominance             (df-dom)
    sbth    Schroeder-Bernstein
    cardval, pwcda, rpnnen, ...   cardinality machinery

So `|- ( Inf ~= RR )` has to be rewritten in those tokens before it means
anything to the model.  Three encodings are offered below; --goal takes any
whitespace-separated token string, so you can write your own.

USAGE
    python probe_goal.py --db set.mm --limit 16000 -p 0.9
    python probe_goal.py --db set.mm --limit 16000 --goal "|- S ~~ RR"
    python probe_goal.py --db set.mm --limit 16000 --encoding dominance
    python probe_goal.py --db set.mm --limit 16000 \
        --gold sbth,rpnnen,endom,domen        # score against a hand-made gold set

Requires predator4.py in the same directory.
"""
from __future__ import annotations
import argparse, math, os, sys
from collections import defaultdict

try:
    import predator4 as P4
except ImportError:
    sys.exit("probe_goal.py needs predator4.py in the same directory.")


# ===========================================================================
#  candidate encodings of "the infinitesimals are equinumerous with RR"
# ===========================================================================
#
# None of these say what the informal statement says, because set.mm cannot
# say it.  Each keeps the SHAPE of the claim -- a class is equinumerous with
# the reals -- and differs in how much of the surrounding notation is spelled
# out.  More tokens means more surface for the overlap features to grip, but
# also more chance of pulling in lemmas about the wrong thing.
#
ENCODINGS = {
    # 1.  Bare shape.  A class variable against RR.  Maximally generic: this is
    #     the query "what does the library know about being equinumerous with
    #     the reals?"  Nothing about infinitesimals survives, which is honest --
    #     the corpus has nothing about infinitesimals.
    "bare": "|- S ~~ RR",

    # 2.  With the two-sided bound made explicit.  The actual proof is
    #     Schroeder-Bernstein applied to two dominances, so writing the goal
    #     in dominance notation should pull `sbth` and the ~<_ lemmas up.
    "dominance": "|- ( S ~<_ RR /\\ RR ~<_ S )",

    # 3.  Spelled out with the absolute-value/positive-real apparatus that an
    #     infinitesimal's DEFINITION would need, so the ranker sees the
    #     analytic vocabulary too.  This is the closest set.mm can come to
    #     naming the set { x | x is smaller than every positive real }.
    "analytic": "|- { x | A. y e. RR+ ( abs ` x ) < y } ~~ RR",
}


def build_goal(tokens, order):
    """Wrap a token list as a Theorem the model can score against.

    kind='theorem' and premises=[] -- it is a goal, not a candidate, so its own
    premise list is never read.  typecode is taken from tokens[0], which must
    be '|-' for the statement to count as logical rather than syntactic.
    """
    t = P4.Theorem("PROBE-GOAL", "theorem", tokens, [], order, steps=0)
    return t


def rank_probe(C, cut, pred, goal, pool_cap=0, top=50):
    """Rank every logical statement in C[:cut] against `goal`.

    The goal sits at index len(C) -- after everything -- so `order_gap` is
    measured from the end of the corpus and `local_use` reads the window of
    statements immediately preceding it.  That is the correct convention for a
    goal being posed NOW, against a library that is already complete.
    """
    st = getattr(pred, "stats", None)
    if st:
        usage, rare, pair_tab = st["usage"], st["rare"], st["pair"]
    else:
        usage, rare = defaultdict(int), P4.Predator4._rare_symbols(C[:cut])
        for t in C[:cut]:
            for p in t.premises: usage[p] += 1
        pair_tab = P4.Predator4.cocitation(C, cut)

    goal_idx = len(C)
    pos_of = {t.label: i for i, t in enumerate(C)}
    pool = [t for t in C if t.is_logical]
    if pool_cap and len(pool) > pool_cap:
        pool = sorted(pool, key=lambda c: -usage.get(c.label, 0))[:pool_cap]

    neigh = P4.Predator4.local_use(C, goal_idx)
    anchors = [c.label for c in sorted(pool, key=lambda c: -usage.get(c.label, 0))[:3]]

    rows = [pred.features(goal, c, usage.get(c.label, 0), rare,
                          goal_idx - pos_of[c.label], neigh.get(c.label, 0),
                          P4.Predator4.cocite_score(pair_tab, c.label, anchors))
            for c in pool]
    s = pred.score(rows)
    order = sorted(range(len(pool)), key=lambda j: -s[j])
    ranked = [pool[j].label for j in order]
    scores = {pool[j].label: s[j] for j in order}
    by_freq = [c.label for c in sorted(pool, key=lambda c: -usage.get(c.label, 0))]
    fused = P4.rrf([ranked, by_freq])
    return ranked, by_freq, fused, scores, pool, usage


def main():
    ap = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="set.mm")
    ap.add_argument("--limit", type=int, default=16000,
                    help="statements to read; 16000 is the plateau found by the "
                         "scaling run")
    ap.add_argument("-p", type=float, default=0.9,
                    help="fraction of the read corpus used for training")
    ap.add_argument("--encoding", choices=sorted(ENCODINGS), default="bare",
                    help="which set.mm rendering of the goal to use")
    ap.add_argument("--goal", default=None,
                    help="explicit token string, overrides --encoding")
    ap.add_argument("--gold", default=None,
                    help="comma-separated labels you BELIEVE the proof needs; "
                         "if given, recall@k and effort are reported against it")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--pool", type=int, default=0, help="0 = every statement")
    ap.add_argument("--model", choices=["logistic", "forest"], default="logistic")
    ap.add_argument("--n-neg", type=int, default=25)
    ap.add_argument("--max-goals", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    if not os.path.exists(a.db):
        sys.exit("no such file: %s\n  python predator4.py fetch set.mm" % a.db)

    tokens = (a.goal or ENCODINGS[a.encoding]).split()
    if tokens[0] != "|-":
        print("WARNING: goal does not begin with '|-'; it will be treated as a\n"
              "         syntax statement and the premise relation will not apply.\n")

    print("=" * 74)
    print("  PROBE  --  an unproved goal against a trained Predator_4")
    print("=" * 74)

    C = P4.parse_mm(a.db, a.limit)
    cut = int(len(C) * a.p)
    print("\n[1] corpus %s statements, training on 0..%d (p = %.2f)"
          % (f"{len(C):,}", cut - 1, a.p))

    # --- which of the goal's tokens the corpus has ever seen -----------------
    vocab = set()
    for t in C[:cut]:
        vocab |= t.symbols
    seen = [tk for tk in tokens if tk in vocab]
    unseen = [tk for tk in tokens if tk not in vocab]
    print("\n[2] goal:  %s" % " ".join(tokens))
    print("    tokens the corpus knows   : %s" % (" ".join(seen) or "(none)"))
    print("    tokens the corpus has NOT : %s" % (" ".join(unseen) or "(none)"))
    if not seen:
        sys.exit("\n    every token is unknown -- the feature vector is all zeros and\n"
                 "    the ranking would be the usage prior.  Rewrite the goal.")
    if unseen:
        print("    (unseen tokens contribute nothing; they cannot match a candidate)")

    pred = P4.Predator4(seed=a.seed, model=a.model)
    info = pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
    print("\n[3] trained on %s goals, %s examples, model %s"
          % (f"{info['goals']:,}", f"{info['examples']:,}", a.model))

    goal = build_goal(tokens, len(C))
    ranked, by_freq, fused, scores, pool, usage = rank_probe(
        C, cut, pred, goal, a.pool, a.top)
    print("    pool: %s logical statements" % f"{len(pool):,}")

    by_label = {t.label: t for t in C}
    print("\n[4] top %d by Predator_4" % a.top)
    print("    %4s  %-14s %9s  %s" % ("rank", "label", "score", "statement"))
    for r, lab in enumerate(ranked[:a.top], 1):
        stmt = " ".join(by_label[lab].tokens)
        print("    %4d  %-14s %9.4f  %s"
              % (r, lab, scores[lab], stmt[:44] + ("..." if len(stmt) > 44 else "")))

    print("\n[5] top 15 by FUSED (Predator + frequency)")
    for r, lab in enumerate(fused[:15], 1):
        stmt = " ".join(by_label[lab].tokens)
        print("    %4d  %-14s %s"
              % (r, lab, stmt[:52] + ("..." if len(stmt) > 52 else "")))

    # --- optional scoring against a hand-supplied gold set -------------------
    if a.gold:
        gold = [g.strip() for g in a.gold.split(",") if g.strip()]
        missing = [g for g in gold if g not in scores]
        gold = [g for g in gold if g in scores]
        print("\n[6] against your hand-supplied gold set")
        if missing:
            print("    not in the pool (bad label, or postdates the cut): %s"
                  % ", ".join(missing))
        if not gold:
            print("    nothing to score.")
        else:
            print("    %-14s %10s %10s %10s" % ("premise", "Predator", "frequency", "FUSED"))
            for g in gold:
                print("    %-14s %10d %10d %10d"
                      % (g, ranked.index(g) + 1, by_freq.index(g) + 1, fused.index(g) + 1))
            G = set(gold)
            for k in (5, 10, 50, 100):
                print("    recall@%-4d %.3f" % (k, len(G & set(ranked[:k])) / len(G)))
            last = max(ranked.index(g) for g in gold) + 1
            last_x = max(fused.index(g) for g in gold) + 1
            print("    effort  Predator %.4f   FUSED %.4f"
                  % (last / len(pool), last_x / len(pool)))
            print("\n    NOTE: this gold set is your hypothesis about the proof, not")
            print("    ground truth.  The number measures agreement with you.")

    print("\n" + "=" * 74)
    print("  Predator_4 ranked the library.  It did not prove anything, and a")
    print("  high-ranked lemma is a suggestion, not a step.")
    print("=" * 74)


if __name__ == "__main__":
    main()
