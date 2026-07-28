#!/usr/bin/env python3
"""
python_rf.py -- Predator_4 with a random forest that is ACTUALLY FITTED.
Brian Tenneson.  Companion to predator4.py; requires it in the same directory.

WHY THIS FILE EXISTS
--------------------
predator4.py v4.0 accepts --model forest but never builds one.  The last line
of Predator4.train() is

    self.model = RankModel(seed=self.seed).fit_pairs(pairs)

unconditionally.  `model_kind` is stored on the object and read only by the
describe() label and the search branch; ForestModel and make_model() are
defined but unreachable from the training path.  Two consequences:

  * `--model forest` silently trains the linear ranker;
  * `--search` fits eight identical models and picks whichever noise won,
    which is why the grid rows come out within a few thousandths of each other.

This file fixes that by supplying a ranker with the same interface -- __init__,
fit_pairs, score, describe -- backed by a RandomForestClassifier, and binding
it in for the duration of the fit.  Everything else (parsing, features,
co-citation, evaluation, baselines) is imported from predator4.py unchanged, so
the two files cannot drift apart.

WHAT THE FOREST BUYS
--------------------
The linear ranker scores a candidate as a sum, w . x.  It cannot represent
"symbol overlap matters MORE for a heavily-cited lemma than for an obscure
one", because that is a product of two features.  A forest splits on
thresholds and combines them, so that conjunction is representable.  Whether it
HELPS is an empirical question this file lets you answer honestly for the first
time.

The training rows are the pairwise DIFFERENCES x_p - x_n, plus their negations
labelled 0, exactly as in rank_fit().  Fitting a classifier on differences is
still learning to rank: the forest is asked "is this difference vector
positively oriented?", and P(yes) is monotone in the ranking score.

DEFAULTS
--------
--limit 16000 and -p 0.9, the plateau located by the scaling run: recall@10
peaks at 16k and effort bottoms there, with both flat or slightly worse at 32k.
Training on more is paying for noise.

COST -- READ THIS BEFORE THE FIRST RUN
--------------------------------------
At 16k statements the pair set is ~1.5M pairs, so ~3.1M rows after the
antisymmetric copies.  A 400-tree forest on 3.1M x 12 float64 wants roughly a
gigabyte and tens of minutes.  --max-pairs subsamples before fitting and
defaults to 400,000 (800k rows), which fits comfortably and costs little
accuracy: the pairs are highly redundant, since every goal contributes
|premises| x |negatives| of them.  Raise it if you have the RAM and patience.

COMMANDS
    python python_rf.py train                    fit and score on held-out goals
    python python_rf.py prove --label prcom      one named theorem, ranks + effort
    python python_rf.py probe --encoding bare    an unproved goal (see probe_goal.py)
    python python_rf.py compare                  forest vs linear, same split
"""
from __future__ import annotations
import argparse, contextlib, math, os, random, sys, time
from collections import defaultdict

try:
    import predator4 as P4
except ImportError:
    sys.exit("python_rf.py needs predator4.py in the same directory.")

try:
    import numpy as np
except ImportError:
    sys.exit("python_rf.py needs numpy:  python -m pip install numpy")

try:
    from sklearn.ensemble import RandomForestClassifier
except ImportError:
    sys.exit("python_rf.py needs scikit-learn:\n"
             "    python -m pip install scikit-learn")

VERSION = "rf-1.0"

# The 14k-16k window the scaling run identified.  Stated as a constant so the
# provenance of the default is visible rather than buried in argparse.
PLATEAU_LIMIT = 16000
PLATEAU_P = 0.9


# ===========================================================================
#  the ranker predator4.py should have had
# ===========================================================================
class RankForestModel:
    """Random forest fitted on pairwise ranking differences.

    Interface-compatible with predator4.RankModel, which is what makes the
    swap below safe: Predator4.train() calls RankModel(seed=...).fit_pairs(...)
    and then only ever calls .score() and .describe().
    """
    name = "rank_forest"

    # Deliberately regularised.  The difference vectors are heavily redundant
    # -- one goal with 8 premises and 25 negatives yields 200 near-duplicate
    # rows -- so an unconstrained forest memorises goals rather than learning
    # the ordering rule.  Depth and leaf size are the two knobs that stop it.
    DEFAULTS = dict(n_estimators=400, max_depth=16, min_samples_leaf=4,
                    min_samples_split=10, max_features="sqrt")

    def __init__(self, seed=0, max_pairs=400_000, verbose=True, **params):
        self.seed = seed
        self.max_pairs = max_pairs
        self.verbose = verbose
        p = dict(self.DEFAULTS); p.update({k: v for k, v in params.items()
                                           if v is not None})
        p.update(random_state=seed, n_jobs=-1)
        self.params = p
        self.clf = None
        self.n_pairs_used = 0

    def fit_pairs(self, pairs):
        if not pairs:
            raise SystemExit("no training pairs")
        rng = random.Random(self.seed)
        if self.max_pairs and len(pairs) > self.max_pairs:
            if self.verbose:
                print("    subsampling %s pairs -> %s  (--max-pairs)"
                      % (f"{len(pairs):,}", f"{self.max_pairs:,}"))
            pairs = rng.sample(pairs, self.max_pairs)
        self.n_pairs_used = len(pairs)

        D = np.asarray([[a - b for a, b in zip(xp, xn)] for xp, xn in pairs],
                       dtype=np.float32)
        # antisymmetry, same reason as rank_fit(): without the negated copies
        # the fit can satisfy the objective by inflating every score.
        X = np.vstack([D, -D])
        y = np.concatenate([np.ones(len(D)), np.zeros(len(D))])
        if self.verbose:
            print("    fitting forest on %s x %d  (%s trees, depth %s)"
                  % (f"{X.shape[0]:,}", X.shape[1],
                     self.params["n_estimators"], self.params["max_depth"]))
        self.clf = RandomForestClassifier(**self.params).fit(X, y)
        return self

    def score(self, rows):
        return list(self.clf.predict_proba(
            np.asarray(rows, dtype=np.float32))[:, 1])

    def describe(self, names):
        return sorted(zip(names, self.clf.feature_importances_),
                      key=lambda kv: -kv[1])


@contextlib.contextmanager
def forest_ranker(**params):
    """Bind RankForestModel in place of predator4.RankModel for the fit.

    Predator4.train() hardcodes the ranker class, so rather than copy sixty
    lines of pair construction -- which would then drift from the original --
    we substitute the name it looks up.  Restored on exit, including on error.
    """
    original = P4.RankModel

    class _Bound(RankForestModel):
        def __init__(self, seed=0, **kw):
            super().__init__(seed=seed, **params)

    P4.RankModel = _Bound
    try:
        yield
    finally:
        P4.RankModel = original


def forest_params(a):
    return dict(n_estimators=a.n_estimators, max_depth=a.max_depth,
                min_samples_leaf=a.min_samples_leaf,
                max_features=a.max_features, max_pairs=a.max_pairs)


def load(a):
    if not os.path.exists(a.db):
        sys.exit("no such file: %s\n  python predator4.py fetch set.mm" % a.db)
    C = P4.parse_mm(a.db, a.limit)
    cut = int(len(C) * a.p)
    return C, cut


def banner(a, C, cut):
    print("=" * 74)
    print("  PYTHON_RF v%s  --  Predator_4 with a real random forest" % VERSION)
    print("=" * 74)
    print("  corpus %s statements from %s" % (f"{len(C):,}", a.db))
    print("  train 0..%d   test %d..   (p = %.2f)" % (cut - 1, cut, a.p))
    if a.limit and not (14000 <= a.limit <= 16000):
        print("  note: --limit %d is outside the 14k-16k plateau; recall@10 peaked"
              % a.limit)
        print("        at 16k and was flat or worse at 32k.")


# ===========================================================================
#  commands
# ===========================================================================
def cmd_train(a):
    C, cut = load(a)
    banner(a, C, cut)

    pred = P4.Predator4(seed=a.seed, model="forest")
    t0 = time.perf_counter()
    with forest_ranker(**forest_params(a)):
        info = pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals,
                          seed=a.seed)
    fit = time.perf_counter() - t0
    print("\n  %s goals, %s pairs generated, %s used, %.1fs"
          % (f"{info['goals']:,}", f"{info['pairs']:,}",
             f"{pred.model.n_pairs_used:,}", fit))

    print("\n  feature importances")
    for name, imp in pred.model.describe(P4.Predator4.FEATURES)[:8]:
        bar = "#" * int(round(imp * 60))
        print("    %-28s %.4f  %s" % (name, imp, bar))

    print("\n  evaluating on %d held-out goals (pool %d)" % (a.n_goals, a.pool))
    ev = P4.evaluate(C, cut, pred, a.n_goals, a.pool, seed=a.seed)
    report(ev)
    return ev


def report(ev):
    print("\n  results  (%d goals scored)" % ev["n_goals"])
    print("    %-10s %10s %10s %10s %10s"
          % ("", "forest", "frequency", "chrono", "FUSED"))
    for k in sorted(ev["recall"]):
        print("    recall@%-4d %10.3f %10.3f %10.3f %10.3f"
              % (k, ev["recall"][k], ev["recall_freq"][k],
                 ev["recall_chron"][k], ev["recall_fused"][k]))
    print("    MRR        %10.3f" % ev["mrr"])
    print("\n    EFFORT -- fraction of the pool read before every premise is found")
    print("      forest %.4f   brute force %.4f   FUSED %.4f"
          % (ev["effort_predator"], ev["effort_bruteforce"], ev["effort_fused"]))
    print("      -> forest %.2fx less of the library; fused %.2fx less"
          % (1 / ev["effort_ratio"],
             ev["effort_bruteforce"] / max(ev["effort_fused"], 1e-9)))


def cmd_compare(a):
    """Forest against linear on the SAME split, seed and pool.

    This is the comparison predator4.py could not make, and the only way to
    find out whether the interactions a forest can represent are interactions
    this task actually contains.
    """
    C, cut = load(a)
    banner(a, C, cut)

    print("\n[linear]")
    lin = P4.Predator4(seed=a.seed, model="logistic")
    t0 = time.perf_counter()
    li = lin.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
    lt = time.perf_counter() - t0
    lev = P4.evaluate(C, cut, lin, a.n_goals, a.pool, seed=a.seed)
    print("  %s goals, %s pairs, %.1fs" % (f"{li['goals']:,}", f"{li['pairs']:,}", lt))

    print("\n[forest]")
    frs = P4.Predator4(seed=a.seed, model="forest")
    t0 = time.perf_counter()
    with forest_ranker(**forest_params(a)):
        fi = frs.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
    ft = time.perf_counter() - t0
    fev = P4.evaluate(C, cut, frs, a.n_goals, a.pool, seed=a.seed)
    print("  %s goals, %s pairs, %.1fs" % (f"{fi['goals']:,}", f"{fi['pairs']:,}", ft))

    print("\n" + "=" * 74)
    print("  %-14s %10s %10s %10s" % ("", "linear", "forest", "delta"))
    for k in sorted(lev["recall"]):
        d = fev["recall"][k] - lev["recall"][k]
        print("  recall@%-8d %10.3f %10.3f %+10.3f" % (k, lev["recall"][k],
                                                       fev["recall"][k], d))
    print("  %-14s %10.3f %10.3f %+10.3f" % ("MRR", lev["mrr"], fev["mrr"],
                                             fev["mrr"] - lev["mrr"]))
    print("  %-14s %10.4f %10.4f %+10.4f" % ("effort", lev["effort_predator"],
                                             fev["effort_predator"],
                                             fev["effort_predator"] - lev["effort_predator"]))
    print("  %-14s %10.1f %10.1f" % ("fit seconds", lt, ft))
    print("=" * 74)
    better = fev["effort_predator"] < lev["effort_predator"]
    print("  effort: forest is %s (lower is better).  Cost: %.1fx the fit time."
          % ("BETTER" if better else "WORSE", ft / max(lt, 1e-9)))
    if not better:
        print("  A forest that loses on effort is evidence the task is close to")
        print("  linear in these features -- not evidence the forest is broken.")


def cmd_prove(a):
    C, cut_all = load(a)
    idx = next((i for i, t in enumerate(C) if t.label == a.label), None)
    if idx is None:
        print("no statement labelled %r in the first %s of %s"
              % (a.label, f"{len(C):,}", a.db))
        near = [t.label for t in C if a.label in t.label][:12]
        if near: print("similar labels: %s" % ", ".join(near))
        return
    g = C[idx]
    cut = int(idx * a.p)
    banner(a, C, cut)
    print("\n  PROVING %s  (statement %d)" % (g.label, idx))
    print("  %s" % " ".join(g.tokens))
    print("\n  its proof cites %d logical premises" % len(g.premises))

    pred = P4.Predator4(seed=a.seed, model="forest")
    with forest_ranker(**forest_params(a)):
        info = pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
    print("  trained on %s goals" % f"{info['goals']:,}")

    ranked, by_freq, by_chron, fused, gold, npool = P4.rank_for_goal(
        C, cut, pred, idx, a.pool)
    if not gold:
        print("\n  none of its premises precede it in the parsed fragment; "
              "raise --limit")
        return
    print("\n  pool %s statements" % f"{npool:,}")
    print("  %-14s %10s %10s %10s %10s"
          % ("premise", "forest", "frequency", "chrono", "FUSED"))
    for p in gold:
        print("  %-14s %10s %10s %10s %10s"
              % (p,
                 ranked.index(p) + 1 if p in ranked else "-",
                 by_freq.index(p) + 1 if p in by_freq else "-",
                 by_chron.index(p) + 1 if p in by_chron else "-",
                 fused.index(p) + 1 if p in fused else "-"))

    def eff(order):
        rs = [order.index(p) + 1 for p in gold if p in order]
        return max(rs) / len(order) if rs else 1.0
    e_p, e_f, e_c, e_x = eff(ranked), eff(by_freq), eff(by_chron), eff(fused)
    print("\n  EFFORT   forest %.4f   frequency %.4f   chrono %.4f   FUSED %.4f"
          % (e_p, e_f, e_c, e_x))
    base = min(e_f, e_c)
    print("  forest vs best baseline: %.1fx %s"
          % (max(base / e_p, e_p / base), "better" if e_p < base else "WORSE"))


def cmd_probe(a):
    """An unproved goal.  See probe_goal.py for the full discussion; this is
    the same idea with the forest bound in."""
    try:
        import probe_goal as PG
    except ImportError:
        sys.exit("probe needs probe_goal.py in the same directory.")

    C, cut = load(a)
    banner(a, C, cut)
    tokens = (a.goal or PG.ENCODINGS[a.encoding]).split()

    vocab = set()
    for t in C[:cut]: vocab |= t.symbols
    seen = [t for t in tokens if t in vocab]
    unseen = [t for t in tokens if t not in vocab]
    print("\n  goal: %s" % " ".join(tokens))
    print("  known tokens   : %s" % (" ".join(seen) or "(none)"))
    print("  unknown tokens : %s" % (" ".join(unseen) or "(none)"))
    if not seen:
        sys.exit("  every token unknown -- feature vector is zero; rewrite the goal.")

    pred = P4.Predator4(seed=a.seed, model="forest")
    with forest_ranker(**forest_params(a)):
        pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)

    goal = PG.build_goal(tokens, len(C))
    ranked, by_freq, fused, scores, pool, usage = PG.rank_probe(
        C, cut, pred, goal, a.pool, a.top)
    by_label = {t.label: t for t in C}
    print("\n  top %d by forest  (pool %s)" % (a.top, f"{len(pool):,}"))
    for r, lab in enumerate(ranked[:a.top], 1):
        s = " ".join(by_label[lab].tokens)
        print("  %4d  %-14s %8.4f  %s"
              % (r, lab, scores[lab], s[:46] + ("..." if len(s) > 46 else "")))
    print("\n  A ranking, not a proof.  A high-ranked lemma is a suggestion.")


# ===========================================================================
def main():
    ap = argparse.ArgumentParser(prog="python_rf", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p, limit=PLATEAU_LIMIT):
        p.add_argument("--db", default="set.mm")
        p.add_argument("--limit", type=int, default=limit,
                       help="statements to read; default %d, the plateau" % limit)
        p.add_argument("-p", type=float, default=PLATEAU_P)
        p.add_argument("--n-neg", type=int, default=25)
        p.add_argument("--max-goals", type=int, default=6000)
        p.add_argument("--n-goals", type=int, default=200)
        p.add_argument("--pool", type=int, default=3000)
        p.add_argument("--seed", type=int, default=0)
        # forest knobs
        p.add_argument("--n-estimators", type=int, default=400)
        p.add_argument("--max-depth", type=int, default=16)
        p.add_argument("--min-samples-leaf", type=int, default=4)
        p.add_argument("--max-features", default="sqrt")
        p.add_argument("--max-pairs", type=int, default=400_000,
                       help="subsample before fitting; 0 = use all (slow, RAM-hungry)")

    common(sub.add_parser("train", help="fit the forest and score held-out goals"))
    common(sub.add_parser("compare", help="forest vs linear on the same split"))

    pr = sub.add_parser("prove", help="one named theorem")
    common(pr)
    pr.add_argument("--label", default="prcom")

    pb = sub.add_parser("probe", help="an unproved goal (needs probe_goal.py)")
    common(pb)
    pb.add_argument("--encoding", default="bare")
    pb.add_argument("--goal", default=None)
    pb.add_argument("--top", type=int, default=50)

    a = ap.parse_args()
    if a.cmd == "train":     cmd_train(a)
    elif a.cmd == "compare": cmd_compare(a)
    elif a.cmd == "prove":   cmd_prove(a)
    elif a.cmd == "probe":   cmd_probe(a)
    else:                    ap.print_help()


if __name__ == "__main__":
    main()
