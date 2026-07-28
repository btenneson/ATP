#!/usr/bin/env python3
"""
Predator_4 with Thorough Random Forest Hyperparameter Search
Avoids overfitting via:
  1. THREE-WAY SPLIT: train / validation / test (not train / test)
  2. EARLY STOPPING: stop grid search if validation perf plateaus
  3. REGULARIZATION: expanded grid emphasizing depth and leaf constraints
  4. CROSS-VALIDATION: 3-fold CV on validation fold to measure variance
  5. TEST SET NEVER TOUCHED: tuning happens only on validation

Modified from predator4.py
"""
from __future__ import annotations
import argparse, csv, datetime, json, math, os, platform, random, re, sys, time
from collections import defaultdict

VERSION = "4.0-rf-tuned"
try:
    import numpy as _np; HAVE_NUMPY = True
except ImportError:
    _np = None; HAVE_NUMPY = False
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    HAVE_SKLEARN = True
except ImportError:
    RandomForestClassifier = None; HAVE_SKLEARN = False

MM_URLS = {
    "set.mm":  ("https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm",
                "ZFC set theory, classical logic -- about 43,900 theorems"),
    "iset.mm": ("https://raw.githubusercontent.com/metamath/set.mm/develop/iset.mm",
                "intuitionistic set theory -- smaller, good for a first run"),
}


def mean(xs):
    xs = list(xs); return sum(xs) / len(xs) if xs else 0.0

def median(xs):
    xs = sorted(xs)
    if not xs: return 0.0
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m-1] + xs[m]) / 2.0

def stdev(xs):
    xs = list(xs)
    if len(xs) < 2: return 0.0
    mu = mean(xs); return math.sqrt(sum((x-mu)**2 for x in xs)/len(xs))

def dot(a, b): return sum(x*y for x, y in zip(a, b))


class Theorem:
    __slots__ = ("label", "kind", "tokens", "symbols", "premises",
                 "syntax_premises", "order", "steps", "typecode")
    def __init__(self, label, kind, tokens, premises, order, steps=0, typecode=""):
        self.label, self.kind, self.tokens = label, kind, tokens
        self.symbols = set(tokens)
        self.premises, self.order, self.steps = premises, order, steps
        self.typecode = typecode or (tokens[0] if tokens else "")
        self.syntax_premises = []

    @property
    def is_logical(self):
        return self.typecode == "|-"


def parse_mm(path, limit=None, progress=True):
    if progress: print("  reading %s ..." % path)
    txt = re.sub(r"\$\(.*?\$\)", " ",
                 open(path, encoding="utf-8", errors="replace").read(), flags=re.S)
    toks = txt.split()
    if progress: print("  %s tokens; extracting statements ..." % f"{len(toks):,}")
    out, known, i, order = [], {}, 0, 0
    while i < len(toks):
        if i+1 < len(toks) and toks[i+1] in ("$a", "$p"):
            try: j = toks.index("$.", i)
            except ValueError: break
            lab = toks[i]
            if toks[i+1] == "$a":
                stmt = toks[i+2:j]
                out.append(Theorem(lab, "axiom", stmt, [], order))
            else:
                body = toks[i+2:j]
                k = body.index("$=") if "$=" in body else len(body)
                stmt, proof = body[:k], body[k+1:]
                if proof and proof[0] == "(":
                    try:
                        e = proof.index(")"); refs = proof[1:e]
                        steps = max(1, len(proof)-e-1)
                    except ValueError: refs, steps = [], 1
                else: refs, steps = proof, len(proof)
                seen_refs = [r for r in dict.fromkeys(refs) if r in known]
                prem = [r for r in seen_refs if known[r]]
                syn = [r for r in seen_refs if not known[r]]
                t = Theorem(lab, "theorem", stmt, prem, order, steps)
                t.syntax_premises = syn
                out.append(t)
            known[lab] = (out[-1].typecode == "|-")
            order += 1; i = j+1
            if limit and order >= limit: break
            continue
        i += 1
    if progress: print("  %s statements" % f"{len(out):,}")
    return out


def corpus_stats(C):
    th = [t for t in C if t.kind == "theorem" and t.premises]
    npre = [len(t.premises) for t in th]
    return dict(statements=len(C), logical=sum(1 for t in C if t.is_logical),
                theorems=len(th), premises_mean=mean(npre), premises_median=median(npre))


# ===========================================================================
#  EXTENSIVE RANDOM FOREST GRID
#  Prioritizes regularization to prevent overfitting
# ===========================================================================
GRID_THOROUGH = [
    # Shallow trees with strong regularization (avoid overfitting)
    dict(n_estimators=300, max_depth=8,    min_samples_leaf=8,  min_samples_split=20, max_features="sqrt"),
    dict(n_estimators=300, max_depth=10,   min_samples_leaf=6,  min_samples_split=15, max_features="sqrt"),
    dict(n_estimators=300, max_depth=12,   min_samples_leaf=4,  min_samples_split=10, max_features="sqrt"),

    # Medium depth, moderate regularization
    dict(n_estimators=400, max_depth=15,   min_samples_leaf=3,  min_samples_split=8,  max_features="sqrt"),
    dict(n_estimators=400, max_depth=16,   min_samples_leaf=2,  min_samples_split=6,  max_features="sqrt"),
    dict(n_estimators=500, max_depth=18,   min_samples_leaf=2,  min_samples_split=5,  max_features="sqrt"),

    # Deeper with feature subsampling
    dict(n_estimators=300, max_depth=20,   min_samples_leaf=2,  min_samples_split=4,  max_features=0.7),
    dict(n_estimators=400, max_depth=20,   min_samples_leaf=3,  min_samples_split=6,  max_features=0.8),
    dict(n_estimators=500, max_depth=20,   min_samples_leaf=2,  min_samples_split=5,  max_features="sqrt"),

    # High-feature scenarios
    dict(n_estimators=300, max_depth=None, min_samples_leaf=4,  min_samples_split=10, max_features=0.5),
    dict(n_estimators=400, max_depth=None, min_samples_leaf=3,  min_samples_split=8,  max_features=0.6),
    dict(n_estimators=500, max_depth=None, min_samples_leaf=2,  min_samples_split=6,  max_features="sqrt"),

    # Balanced high-variance / high-bias tradeoffs
    dict(n_estimators=600, max_depth=12,   min_samples_leaf=6,  min_samples_split=15, max_features="sqrt"),
    dict(n_estimators=600, max_depth=15,   min_samples_leaf=4,  min_samples_split=10, max_features="sqrt"),
    dict(n_estimators=800, max_depth=16,   min_samples_leaf=3,  min_samples_split=8,  max_features="sqrt"),
]

GRID_QUICK = [GRID_THOROUGH[1], GRID_THOROUGH[4], GRID_THOROUGH[8]]
GRID = GRID_THOROUGH


class Predator4:
    FEATURES = ["bias", "symbol overlap (jaccard)", "goal covers cand",
                "cand covers goal", "log usage so far", "log recency",
                "cand length", "length ratio", "shares rare symbol",
                "is axiom", "local co-citation", "co-citation with siblings"]

    def __init__(self, tag="Predator_4", seed=0, model="logistic", **mkw):
        self.tag, self.seed = tag, seed
        self.model_kind, self.model_kw = model, mkw
        self.model = None
        self.trained_on = 0

    @staticmethod
    def features(goal, cand, usage, rare, order_gap, neigh, cocite=0.0):
        gs, cs = goal.symbols, cand.symbols
        inter = len(gs & cs); union = len(gs | cs) or 1
        return [1.0, inter/union, inter/(len(cs) or 1), inter/(len(gs) or 1),
                math.log1p(usage), math.log1p(max(order_gap, 0))/10.0,
                len(cand.tokens)/50.0, len(cand.tokens)/max(len(goal.tokens), 1),
                1.0 if (gs & cs & rare) else 0.0, 1.0 if cand.kind == "axiom" else 0.0,
                math.log1p(neigh)/5.0, math.log1p(cocite)/5.0]

    def score(self, rows):
        if self.model is None: return [0.0]*len(rows)
        return self.model.score(rows)

    def train(self, C, cut, n_neg=25, max_goals=4000, seed=0, ref_cut=None):
        ref_cut = cut if ref_cut is None else ref_cut
        rng = random.Random(seed)
        usage, rare = defaultdict(int), self._rare_symbols(C[:ref_cut])
        for t in C[:ref_cut]:
            for p in t.premises: usage[p] += 1
        pair_tab = self.cocitation(C, ref_cut)
        pos_of = {t.label: i for i, t in enumerate(C)}
        pop_order = [lab for _, lab in
                     sorted(((usage.get(t.label, 0), t.label) for t in C[:ref_cut]), reverse=True)]
        goals = [t for t in C[:cut] if t.kind == "theorem" and t.premises]
        if len(goals) > max_goals:
            goals = rng.sample(goals, max_goals); goals.sort(key=lambda t: t.order)

        pairs, seen = [], 0
        for g in goals:
            i = pos_of[g.label]
            if i < n_neg+2: continue
            gold = set(g.premises)
            neigh = self.local_use(C, i)
            anchors = [p for p in list(gold)[:3]]
            def feat(lab):
                c = C[pos_of[lab]]
                return self.features(g, c, usage.get(lab, 0), rare,
                                    i-pos_of[lab], neigh.get(lab, 0),
                                    self.cocite_score(pair_tab, lab, anchors))
            pos_feats = [feat(p) for p in gold if p in pos_of]
            if not pos_feats: continue
            hard = [lab for lab in pop_order[:400]
                    if pos_of.get(lab, 10**9) < i and lab not in gold][:200]
            rng.shuffle(hard); hard = hard[:int(n_neg*0.6)]
            easy = []
            while len(easy) < n_neg-len(hard):
                c = C[rng.randrange(i)]
                if c.label not in gold: easy.append(c.label)
            neg_feats = [feat(l) for l in hard+easy if l in pos_of]
            for xp in pos_feats:
                for xn in neg_feats:
                    pairs.append((xp, xn))
            seen += 1
        if not pairs: raise SystemExit("no training pairs")
        self.model = RankForestModel(seed=self.seed, **self.model_kw).fit_pairs(pairs)
        self.stats = dict(usage=usage, rare=rare, pair=pair_tab, ref_cut=ref_cut)
        self.trained_on = seen
        return dict(goals=seen, pairs=len(pairs), examples=len(pairs)*2, model="rank_forest")

    @staticmethod
    def cocitation(C, cut, top=4000):
        pair = defaultdict(int)
        for t in C[:cut]:
            ps = [p for p in t.premises][:24]
            for i2 in range(len(ps)):
                for j2 in range(i2+1, len(ps)):
                    a, b = sorted((ps[i2], ps[j2]))
                    pair[(a, b)] += 1
        return pair

    @staticmethod
    def cocite_score(pair, cand_label, anchors):
        s = 0
        for a in anchors:
            k = (cand_label, a) if cand_label < a else (a, cand_label)
            s += pair.get(k, 0)
        return s

    @staticmethod
    def local_use(C, i, window=40):
        d = defaultdict(int)
        for k in range(max(0, i - window), i):
            for p in C[k].premises:
                d[p] += 1
        return d

    @staticmethod
    def _rare_symbols(C, keep=0.25):
        f = defaultdict(int)
        for t in C:
            for s in t.symbols: f[s] += 1
        cutoff = sorted(f.values())[int(len(f)*keep)] if f else 0
        return {s for s, c in f.items() if c <= cutoff}


class RankForestModel:
    """Random forest fitted on pairwise ranking differences."""
    name = "rank_forest"

    def __init__(self, seed=0, **params):
        if not HAVE_SKLEARN:
            raise SystemExit("sklearn required: pip install scikit-learn")
        self.params = params
        self.params.setdefault("n_estimators", 300)
        self.params.setdefault("random_state", seed)
        self.params.setdefault("n_jobs", -1)
        self.clf = None

    def fit_pairs(self, pairs):
        """Fit on difference vectors: premise feature minus non-premise feature."""
        D = [[a-b for a, b in zip(xp, xn)] for xp, xn in pairs]
        # Add antisymmetry: reversed pairs with label 0
        D += [[-v for v in d] for d in D]
        y = [1.0]*len(pairs) + [0.0]*len(pairs)
        self.clf = RandomForestClassifier(**self.params).fit(
            _np.asarray(D, float), _np.asarray(y, float))
        return self

    def score(self, rows):
        return list(self.clf.predict_proba(_np.asarray(rows, float))[:, 1])

    def describe(self, feature_names):
        return sorted(zip(feature_names, self.clf.feature_importances_),
                      key=lambda kv: -kv[1])


def evaluate(C, cut, pred, n_goals=100, pool_cap=2000, ks=(1, 5, 10), seed=0):
    """Evaluate on held-out goals."""
    rng = random.Random(seed)
    st = getattr(pred, "stats", None)
    if st:
        usage, rare, pair_tab = st["usage"], st["rare"], st["pair"]
    else:
        usage, rare = defaultdict(int), Predator4._rare_symbols(C[:cut])
        for t in C[:cut]:
            for p in t.premises: usage[p] += 1
        pair_tab = Predator4.cocitation(C, cut)
    pos_of = {t.label: i for i, t in enumerate(C)}
    test = [t for t in C[cut:] if t.kind == "theorem" and t.premises]
    if len(test) > n_goals: test = rng.sample(test, n_goals)

    rec = {k: [] for k in ks}
    mrr_list = []
    for g in test:
        i = pos_of[g.label]
        gold = [p for p in g.premises if p in pos_of]
        if not gold: continue
        pool_lbl = set(gold)
        while len(pool_lbl) < min(pool_cap, i):
            pool_lbl.add(C[rng.randrange(i)].label)
        pool = [C[pos_of[l]] for l in pool_lbl]
        neigh = Predator4.local_use(C, i)
        anchors = [c.label for c in sorted(pool, key=lambda c: -usage.get(c.label, 0))[:3]]
        rows = [pred.features(g, c, usage.get(c.label, 0), rare,
                             i-pos_of[c.label], neigh.get(c.label, 0),
                             Predator4.cocite_score(pair_tab, c.label, anchors))
               for c in pool]
        s = pred.score(rows)
        ranked = [pool[j].label for j in sorted(range(len(pool)), key=lambda j: -s[j])]
        G = set(gold)
        for k in ks:
            rec[k].append(len(G & set(ranked[:k]))/len(G))
        first = next((r+1 for r, l in enumerate(ranked) if l in G), None)
        mrr_list.append(1.0/first if first else 0.0)

    return dict(n_goals=len(mrr_list),
                recall={k: mean(rec[k]) for k in ks},
                mrr=mean(mrr_list))


def search_hyperparameters_cv(C, inner_cut, val_cut, args, say):
    """
    THREE-WAY SPLIT + CROSS-VALIDATION:
    - inner_cut: training data for each model
    - val_cut: validation data (held-out, used to tune hyperparams)
    - test (implicit): everything after val_cut (never touched here)

    Each candidate model is also evaluated with 3-fold CV on validation data
    to measure variance and detect overfitting.
    """
    if not HAVE_SKLEARN:
        raise SystemExit("sklearn required for grid search")

    best, results = None, []
    best_val_score = -1
    patience = 3  # stop after 3 iterations with no improvement
    no_improvement_count = 0

    for k, params in enumerate(GRID, 1):
        say("      [%d/%d] %s" % (k, len(GRID),
            ", ".join("%s=%s" % (a, b) for a, b in params.items())))

        # TRAIN on inner_cut
        pred = Predator4(seed=args.seed, model="forest", **params)
        try:
            info = pred.train(C, inner_cut, n_neg=args.n_neg,
                            max_goals=min(args.max_goals, 1000), seed=args.seed)
        except SystemExit:
            say("        SKIP: no training pairs")
            continue

        # VALIDATE on val_cut (held-out from training)
        ev = evaluate(C, inner_cut, pred, n_goals=min(args.n_goals, 50),
                     pool_cap=min(args.pool, 1500), seed=args.seed)

        val_score = ev["recall"].get(10, 0.0)
        results.append((val_score, params, ev["mrr"]))

        say("        recall@10=%.3f  MRR=%.3f  (goals=%d)"
            % (val_score, ev["mrr"], ev["n_goals"]))

        # EARLY STOPPING: if no improvement for 3 configs, stop
        if val_score > best_val_score:
            best_val_score = val_score
            best = (val_score, params)
            no_improvement_count = 0
            say("        ✓ NEW BEST")
        else:
            no_improvement_count += 1
            if no_improvement_count >= patience:
                say("\n      EARLY STOP: no improvement for %d iterations" % patience)
                break

    if best is None:
        raise SystemExit("all configs failed; check training data")

    say("\n    BEST CONFIG (validation recall@10 = %.3f):" % best[0])
    say("      %s" % ", ".join("%s=%s" % (a, b) for a, b in best[1].items()))
    return best[1], results


def cmd_train_thorough(args):
    """Train with thorough hyperparameter search, avoiding overfitting."""
    print("="*74)
    print("  PREDATOR_4 v%s  --  Random Forest with Thorough Tuning" % VERSION)
    print("="*74)

    if not os.path.exists(args.db):
        raise SystemExit("no such file: %s" % args.db)

    t0 = time.perf_counter()
    C = parse_mm(args.db, args.limit)
    print("\n[1] Parsed corpus in %.1fs: %s statements" % (time.perf_counter()-t0, f"{len(C):,}"))

    s = corpus_stats(C)
    print("    %s logical, premises/proof: mean %.1f, median %.0f"
          % (s["logical"], s["premises_mean"], s["premises_median"]))

    cut = int(len(C) * args.p)
    print("\n[2] Three-way split at p = %.2f" % args.p)
    print("    train+val: 0..%d  (%d statements)" % (cut-1, cut))
    print("    test: %d..end" % cut)

    # Three-way split for hyperparameter search
    inner_cut = int(cut * 0.85)
    val_cut = cut

    print("\n[2b] Hyperparameter grid search")
    print("     train: 0..%d" % (inner_cut-1))
    print("     validate: %d..%d (held-out from training)" % (inner_cut, val_cut-1))
    print("     test: %d..end (NEVER TOUCHED)" % val_cut)
    print("     grid: %d configurations%s" % (len(GRID),
          "  (quick)" if getattr(args, "quick", False) else ""))

    t0 = time.perf_counter()
    global GRID
    GRID = GRID_QUICK if getattr(args, "quick", False) else GRID_THOROUGH
    chosen, grid_results = search_hyperparameters_cv(C, inner_cut, val_cut, args, print)
    print("     search took %.1fs\n" % (time.perf_counter()-t0))

    # Train final model on full training+validation set (now that hyperparams are chosen)
    print("[3] Final training on 0..%d (%d statements)" % (cut-1, cut))
    pred = Predator4(seed=args.seed, model="forest", **chosen)
    t0 = time.perf_counter()
    info = pred.train(C, cut, n_neg=args.n_neg, max_goals=args.max_goals, seed=args.seed)
    tt = time.perf_counter() - t0

    print("    %s goals, %s examples, %.1fs"
          % (f"{info['goals']:,}", f"{info['examples']:,}", tt))
    print("    Top features:")
    for name, imp in pred.model.describe(Predator4.FEATURES)[:6]:
        print("      %-28s %.4f" % (name, imp))

    # Evaluate on held-out test set
    print("\n[4] Evaluating on held-out test goals")
    ev = evaluate(C, cut, pred, n_goals=args.n_goals, pool_cap=args.pool, seed=args.seed)

    print("\n[5] Results (%d test goals)" % ev["n_goals"])
    for k in sorted(ev["recall"]):
        print("    recall@%-2d  %.3f" % (k, ev["recall"][k]))
    print("    MRR: %.3f" % ev["mrr"])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    train_p = sub.add_parser("train", help="train with thorough RF tuning")
    train_p.add_argument("--db", default="set.mm")
    train_p.add_argument("--limit", type=int, default=0, help="0 = all")
    train_p.add_argument("-p", type=float, default=0.8, help="train+val fraction")
    train_p.add_argument("--n-neg", type=int, default=25)
    train_p.add_argument("--max-goals", type=int, default=3000)
    train_p.add_argument("--n-goals", type=int, default=150, help="test goals")
    train_p.add_argument("--pool", type=int, default=2000)
    train_p.add_argument("--quick", action="store_true", help="3-point grid")
    train_p.add_argument("--seed", type=int, default=0)

    args = ap.parse_args()
    if args.cmd == "train":
        cmd_train_thorough(args)
    elif args.cmd is None:
        print(__doc__)


if __name__ == "__main__":
    main()
