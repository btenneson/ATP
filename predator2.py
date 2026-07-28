#!/usr/bin/env python3
"""
Predator_2 -- premise selection over ZFC set theory.   Brian Tenneson, v1.0
btenneson2301.substack.com    Copyright (c) 2026.  All Rights Reserved.

ONE FILE.  NO INSTALL.  NO DEPENDENCIES REQUIRED.

    python predator2.py            <- run this.  It will explain itself.

WHY THE TASK IS DIFFERENT FROM PREDATOR_1
-----------------------------------------
Predator_1 searches forward: it applies rules and generates consequences, so
brute force means "adjoin every direct consequence" and effort means expansions.
That is available because the propositional system is small enough to enumerate.

ZFC as formalised in Metamath's set.mm is not.  Re-deriving a set.mm proof needs
the full substitution machinery of the language, and the corpus is ~43,900
proved theorems over a vocabulary of thousands of symbols.  What set.mm DOES
hand you, written in the file, is the premise structure: every proof names the
axioms and earlier theorems it invokes.

So Predator_2 answers the question a working prover actually faces:

    GIVEN a goal, WHICH of the tens of thousands of available theorems
    does its proof use?

Brute force here is examining candidates in corpus order and checking each.
Predator_2 ranks them and examines the ranked list.  Effort is how many
candidates you must look at before you have found the premises.  That is the
premise-selection analogue of expansions: same shape, same two-number scoring.

SCORING -- two numbers, because they measure different ends of the list
-----------------------------------------------------------------------
    recall@k   fraction of a goal's true premises inside the top k
               -- how good the TOP of the ranking is

    effort     rank of the LAST true premise, as a fraction of the pool
               -- how deep you must read before you can stop, i.e. how far
                  down the WORST premise is buried

These come apart, which is the whole reason both are reported.  A ranker that
puts four of five premises at ranks 1-4 and the fifth at rank 2000 has
excellent recall@5 and terrible effort.  One that puts all five at ranks 40-50
has poor recall@5 and good effort.  Neither number implies the other.

Observed on set.mm: the chronological baseline beats the learned ranker at
k = 1, 5 and 10 -- it is better at the top -- while needing 93% of the pool to
find every premise against the learned ranker's 35%.  Reporting either number
alone would have told the opposite story about which is better.

Both are shown against a frequency baseline and a chronological baseline.

COMMANDS
    python predator2.py                  interactive menu
    python predator2.py fetch            download set.mm (ZFC) or iset.mm
    python predator2.py train            train and evaluate on a corpus
    python predator2.py stats            describe a corpus without training
    python predator2.py doctor           check the environment
"""
from __future__ import annotations
import argparse, csv, datetime, json, math, os, platform, random, re, sys, time
from collections import defaultdict

VERSION = "1.0"
try:
    import numpy as _np; HAVE_NUMPY = True
except ImportError:
    _np = None; HAVE_NUMPY = False
try:
    from sklearn.ensemble import RandomForestClassifier
    HAVE_SKLEARN = True
except ImportError:
    RandomForestClassifier = None; HAVE_SKLEARN = False

MM_URLS = {
    "set.mm":  ("https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm",
                "ZFC set theory, classical logic -- about 43,900 theorems"),
    "iset.mm": ("https://raw.githubusercontent.com/metamath/set.mm/develop/iset.mm",
                "intuitionistic set theory -- smaller, good for a first run"),
    "nf.mm":   ("https://raw.githubusercontent.com/metamath/set.mm/develop/nf.mm",
                "New Foundations"),
    "ql.mm":   ("https://raw.githubusercontent.com/metamath/set.mm/develop/ql.mm",
                "quantum logic -- smallest"),
}


# ===========================================================================
#  numerics -- numpy when present, plain Python otherwise
# ===========================================================================
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

def standardise(X):
    if not X: return [], [], []
    k = len(X[0])
    mu = [mean(r[j] for r in X) for j in range(k)]
    sg = [stdev([r[j] for r in X]) for j in range(k)]
    mu = [0.0 if s < 1e-12 else m for m, s in zip(mu, sg)]
    sg = [1.0 if s < 1e-12 else s for s in sg]
    return [[(r[j]-mu[j])/sg[j] for j in range(k)] for r in X], mu, sg

def logistic_fit(X, y, epochs=300, lr=0.5, l2=1e-4, seed=0):
    Xz, mu, sg = standardise(X)
    if HAVE_NUMPY:
        Xa = _np.asarray(Xz, float); ya = _np.asarray(y, float)
        w = _np.random.default_rng(seed).normal(0, .01, Xa.shape[1]); m = len(ya)
        for _ in range(epochs):
            p = 1.0/(1.0+_np.exp(-_np.clip(Xa @ w, -30, 30)))
            w -= lr*(Xa.T @ (p-ya)/m + l2*w)
        return [float(v) for v in w], mu, sg
    rng = random.Random(seed); k = len(Xz[0])
    w = [rng.gauss(0, .01) for _ in range(k)]; m = len(y)
    for _ in range(epochs):
        grad = [0.0]*k
        for xi, yi in zip(Xz, y):
            z = max(-30.0, min(30.0, dot(xi, w)))
            e = 1.0/(1.0+math.exp(-z)) - yi
            for j in range(k): grad[j] += e*xi[j]
        for j in range(k): w[j] -= lr*(grad[j]/m + l2*w[j])
    return w, mu, sg


# ===========================================================================
#  the corpus
# ===========================================================================
class Theorem:
    r"""One Metamath statement.

    `typecode` is the first token of the assertion and is what separates
    mathematics from grammar.  In set.mm an assertion beginning '|-' claims
    something is PROVABLE; one beginning 'wff', 'class' or 'setvar' merely
    declares that a string is well formed.  Statements like

        wcel $a wff A e. B $.        <- syntax: "A e. B is a wff"
        wa   $a wff ( ph /\ ps ) $.  <- syntax: conjunction is a wff
        ax-mp $a |- ps $.            <- mathematics: modus ponens

    look identical in the file and are counted alike by a naive reader, but
    every proof must build its formulas before proving anything, so the syntax
    constructors are cited by nearly everything.  Left in, they dominate the
    premise relation: the eight most-cited labels in the first 8,000 statements
    of set.mm are all syntax, wcel alone appearing in 2,946 proofs.  A selector
    trained on that learns to predict grammar."""
    __slots__ = ("label", "kind", "tokens", "symbols", "premises",
                 "syntax_premises", "order", "steps", "typecode")
    def __init__(self, label, kind, tokens, premises, order, steps=0,
                 typecode=""):
        self.label, self.kind, self.tokens = label, kind, tokens
        self.symbols = set(tokens)
        self.premises, self.order, self.steps = premises, order, steps
        self.typecode = typecode or (tokens[0] if tokens else "")
        self.syntax_premises = []

    @property
    def is_logical(self):
        return self.typecode == "|-"


def parse_mm(path, limit=None, progress=True):
    """Reads a Metamath database into an ordered list of statements.

    A proof is a list of label references, so the premise structure is written
    in the file: no proof reconstruction, no natural-language processing.  The
    compressed format '( L1 L2 ... ) ABC..' names its references in the
    parenthesised list, which is all the premise structure needs."""
    if progress: print("  reading %s ..." % path)
    txt = re.sub(r"\$\(.*?\$\)", " ",
                 open(path, encoding="utf-8", errors="replace").read(), flags=re.S)
    toks = txt.split()
    if progress: print("  %s tokens; extracting statements ..." % f"{len(toks):,}")
    out, known, i, order = [], {}, 0, 0        # label -> is_logical
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
                # SPLIT the references: logical premises are the mathematics,
                # syntax references are grammar and are kept separately so they
                # can be counted but not learned from.
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
    syn_total = sum(len(t.syntax_premises) for t in C)
    log_total = sum(len(t.premises) for t in C)
    use = defaultdict(int)
    for t in C:
        for p in t.premises: use[p] += 1          # logical premises only
    npre = [len(t.premises) for t in th]
    vocab = set()
    for t in C: vocab |= t.symbols
    top = sorted(use.items(), key=lambda kv: -kv[1])[:8]
    return dict(statements=len(C),
                axioms=sum(1 for t in C if t.kind == "axiom"),
                logical=sum(1 for t in C if t.is_logical),
                syntax=sum(1 for t in C if not t.is_logical),
                logical_refs=log_total, syntax_refs=syn_total,
                theorems=len(th), vocabulary=len(vocab),
                premises_mean=mean(npre), premises_median=median(npre),
                premises_max=max(npre) if npre else 0,
                most_used=top)



# ===========================================================================
#  models
# ===========================================================================
class LogisticModel:
    """Linear.  Cannot represent interactions: it cannot learn that high symbol
    overlap matters MORE for a locally-used lemma than for an obscure one,
    because that is a product of two features and a linear score is a sum."""
    name = "logistic"

    def __init__(self, seed=0, **kw):
        self.seed = seed; self.w = self.mu = self.sigma = None

    def fit(self, X, y):
        self.w, self.mu, self.sigma = logistic_fit(X, y, seed=self.seed)
        return self

    def score(self, rows):
        return [dot([(v-m)/s for v, m, s in zip(r, self.mu, self.sigma)], self.w)
                for r in rows]

    def describe(self, feature_names):
        return sorted(zip(feature_names, self.w), key=lambda kv: -abs(kv[1]))


class ForestModel:
    """Random forest.  Splits on thresholds and combines them, so interactions
    and non-monotone effects are representable -- which is the reason to try it
    here, since 'cited often' and 'shares notation' plausibly matter jointly
    rather than additively.  Needs scikit-learn."""
    name = "forest"

    def __init__(self, seed=0, n_estimators=300, max_depth=None,
                 min_samples_leaf=2, max_features="sqrt", class_weight=None):
        if not HAVE_SKLEARN:
            raise SystemExit(
                "the forest model needs scikit-learn:\n"
                "    python -m pip install scikit-learn\n"
                "or run with  --model logistic")
        self.params = dict(n_estimators=n_estimators, max_depth=max_depth,
                           min_samples_leaf=min_samples_leaf,
                           max_features=max_features, class_weight=class_weight,
                           random_state=seed, n_jobs=-1)
        self.clf = None

    def fit(self, X, y):
        self.clf = RandomForestClassifier(**self.params).fit(
            _np.asarray(X, float), _np.asarray(y, float))
        return self

    def score(self, rows):
        # rank by P(premise), the second column of predict_proba
        return list(self.clf.predict_proba(_np.asarray(rows, float))[:, 1])

    def describe(self, feature_names):
        return sorted(zip(feature_names, self.clf.feature_importances_),
                      key=lambda kv: -kv[1])


def make_model(kind, seed=0, **kw):
    return ForestModel(seed=seed, **kw) if kind == "forest" else LogisticModel(seed=seed)

# ===========================================================================
#  Predator_2
# ===========================================================================
class Predator2:
    """A tagged premise selector.  Ranks the available theorems by how likely
    each is to appear in a given goal's proof."""

    # Every feature must be a property of the PAIR.  A feature depending only
    # on the goal is identical across candidates, shifts all scores equally and
    # cannot change the ranking -- it is dead weight that the fit will
    # nonetheless assign a weight to, which is worse than useless because it
    # looks informative in the printout.  'goal length' was such a feature and
    # has been replaced by the length RATIO, which varies with the candidate.
    FEATURES = ["bias", "symbol overlap (jaccard)", "goal covers cand",
                "cand covers goal", "log usage so far", "log recency",
                "cand length", "length ratio", "shares rare symbol",
                "is axiom", "local co-citation"]

    def __init__(self, tag="Predator_2", seed=0, model="logistic", **mkw):
        self.tag, self.seed = tag, seed
        self.model_kind, self.model_kw = model, mkw
        self.model = None
        self.trained_on = 0

    @staticmethod
    def features(goal, cand, usage, rare, order_gap, neigh):
        gs, cs = goal.symbols, cand.symbols
        inter = len(gs & cs); union = len(gs | cs) or 1
        return [1.0,
                inter/union,
                inter/(len(cs) or 1),
                inter/(len(gs) or 1),
                math.log1p(usage),
                math.log1p(max(order_gap, 0))/10.0,
                len(cand.tokens)/50.0,
                len(cand.tokens)/max(len(goal.tokens), 1),   # pairwise, not goal-only
                1.0 if (gs & cs & rare) else 0.0,
                1.0 if cand.kind == "axiom" else 0.0,
                math.log1p(neigh)/5.0]     # local co-citation; see build_neighbour_use

    def score(self, rows):
        if self.model is None: return [0.0]*len(rows)
        return self.model.score(rows)

    def train(self, C, cut, n_neg=25, max_goals=4000, seed=0):
        """Positives: the premises a proof actually cites.  Negatives: HARD
        ones -- theorems used by the goal's neighbours in the corpus but not by
        the goal itself -- plus random ones.  On a corpus of tens of thousands,
        random negatives are almost all trivially irrelevant, and a model
        trained only against them learns to reject the unrelated rather than to
        choose among the plausible."""
        rng = random.Random(seed)
        usage, rare = defaultdict(int), self._rare_symbols(C)
        pos_of = {t.label: i for i, t in enumerate(C)}
        neigh_use = defaultdict(int)
        X, y, goals = [], [], [t for t in C[:cut] if t.kind == "theorem" and t.premises]
        if len(goals) > max_goals:
            goals = rng.sample(goals, max_goals); goals.sort(key=lambda t: t.order)
        seen = 0
        for t in C[:cut]:
            for p in t.premises: usage[p] += 1
        for g in goals:
            i = pos_of[g.label]
            if i < n_neg+2: continue
            gold = set(g.premises)
            neigh_use = self.local_use(C, i)      # recomputed per goal
            for pl in g.premises:
                if pl in pos_of:
                    c = C[pos_of[pl]]
                    X.append(self.features(g, c, usage.get(pl, 0), rare,
                                           i-pos_of[pl], neigh_use.get(pl, 0)))
                    y.append(1)
            # HARD negatives must be plausible-but-wrong, and they must be
            # chosen by a criterion NONE OF THE FEATURES MEASURE.  Drawing them
            # from the premises of the 40 preceding theorems -- the obvious
            # choice -- is exactly the window `local_use` counts, so every hard
            # negative scored high on that feature while positives did so only
            # incidentally.  The feature then became a detector for the
            # sampling procedure rather than for mathematics, and the fit
            # assigned it a large NEGATIVE weight: -0.94 on set.mm, halving
            # every recall figure.  The label had leaked into a column.
            #
            # Negatives are therefore drawn by GLOBAL popularity instead:
            # frequently cited lemmas that this particular goal did not use.
            # They are plausible for a reason no feature computes from the
            # local window, so `local co-citation` is free to carry signal.
            pop = sorted(((usage.get(C[k].label, 0), C[k].label)
                          for k in range(i)), reverse=True)
            hard = [lab for _, lab in pop[:200] if lab not in gold]
            rng.shuffle(hard); hard = hard[:int(n_neg*0.6)]
            easy = []
            while len(easy) < n_neg-len(hard):
                c = C[rng.randrange(i)]
                if c.label not in gold: easy.append(c.label)
            for pl in hard+easy:
                c = C[pos_of[pl]]
                X.append(self.features(g, c, usage.get(pl, 0), rare,
                                       i-pos_of[pl], neigh_use.get(pl, 0)))
                y.append(0)
            seen += 1
        if not y or sum(y) in (0, len(y)):
            raise SystemExit("degenerate training set -- try a larger corpus or --limit")
        self.model = make_model(self.model_kind, self.seed, **self.model_kw).fit(X, y)
        self.trained_on = seen
        return dict(goals=seen, examples=len(y), positives=sum(y),
                    model=self.model_kind)

    @staticmethod
    def local_use(C, i, window=40):
        """How often each statement is cited by the `window` theorems
        immediately preceding position i.

        This is the signal the chronological baseline was exploiting and the
        model was not: set.mm is organised topically, so the lemmas in heavy
        use just before a goal are the ones its proof is most likely to reach
        for.  It is strictly more informative than either global frequency
        (which ignores where you are in the library) or recency (which ignores
        what is actually being cited), and on the first ZFC run those two
        baselines beat the model at every k below 50."""
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

    def to_dict(self):
        d = dict(tag=self.tag, version=VERSION, seed=self.seed,
                 model=self.model_kind, model_params=self.model_kw,
                 trained_on=self.trained_on, features=self.FEATURES)
        if isinstance(self.model, LogisticModel):
            d.update(weights=self.model.w, mu=self.model.mu, sigma=self.model.sigma)
        elif isinstance(self.model, ForestModel):
            d.update(importances=[float(v) for v in self.model.clf.feature_importances_])
        return d


def evaluate(C, cut, pred, n_goals=200, pool_cap=3000, ks=(1, 5, 10, 50), seed=0,
             goal_limit=None):
    """Held-out goals are those AFTER the cut, so training never sees a theorem
    that postdates a test goal.  For each goal the candidate pool is a capped
    sample of the statements available to it, always including its true
    premises so that recall is well defined."""
    rng = random.Random(seed)
    usage, rare = defaultdict(int), Predator2._rare_symbols(C)
    for t in C[:cut]:
        for p in t.premises: usage[p] += 1
    pos_of = {t.label: i for i, t in enumerate(C)}
    end = goal_limit if goal_limit is not None else len(C)
    test = [t for t in C[cut:end] if t.kind == "theorem" and t.premises]
    if len(test) > n_goals: test = rng.sample(test, n_goals)

    rec = {k: [] for k in ks}; base_f = {k: [] for k in ks}; base_c = {k: [] for k in ks}
    fus = {k: [] for k in ks}
    rr, eff_pr, eff_bf, eff_fu = [], [], [], []
    for g in test:
        i = pos_of[g.label]
        gold = [p for p in g.premises if p in pos_of]
        if not gold: continue
        pool_lbl = set(gold)
        while len(pool_lbl) < min(pool_cap, i):
            pool_lbl.add(C[rng.randrange(i)].label)
        pool = [C[pos_of[l]] for l in pool_lbl]
        neigh = Predator2.local_use(C, i)
        rows = [pred.features(g, c, usage.get(c.label, 0), rare,
                              i-pos_of[c.label], neigh.get(c.label, 0))
                for c in pool]
        s = pred.score(rows)
        ranked = [pool[j].label for j in sorted(range(len(pool)), key=lambda j: -s[j])]
        by_freq = [c.label for c in sorted(pool, key=lambda c: -usage.get(c.label, 0))]
        by_chron = [c.label for c in sorted(pool, key=lambda c: -c.order)]
        fused = rrf([ranked, by_freq])
        G = set(gold)
        for k in ks:
            rec[k].append(len(G & set(ranked[:k]))/len(G))
            base_f[k].append(len(G & set(by_freq[:k]))/len(G))
            base_c[k].append(len(G & set(by_chron[:k]))/len(G))
            fus[k].append(len(G & set(fused[:k]))/len(G))
        first = next((r+1 for r, l in enumerate(ranked) if l in G), None)
        rr.append(1.0/first if first else 0.0)
        last = max(r for r, l in enumerate(ranked) if l in G)+1
        last_b = max(r for r, l in enumerate(by_chron) if l in G)+1
        last_x = max(r for r, l in enumerate(fused) if l in G)+1
        eff_pr.append(last/len(pool)); eff_bf.append(last_b/len(pool))
        eff_fu.append(last_x/len(pool))
    return dict(n_goals=len(rr), pool_cap=pool_cap,
                recall={k: mean(rec[k]) for k in ks},
                recall_freq={k: mean(base_f[k]) for k in ks},
                recall_chron={k: mean(base_c[k]) for k in ks},
                recall_fused={k: mean(fus[k]) for k in ks},
                effort_fused=mean(eff_fu),
                mrr=mean(rr),
                effort_predator=mean(eff_pr), effort_bruteforce=mean(eff_bf),
                effort_ratio=(mean(eff_pr)/mean(eff_bf)) if mean(eff_bf) > 0 else None)



# ===========================================================================
#  hyperparameter search
# ===========================================================================
GRID_FULL = [
    dict(n_estimators=200, max_depth=None, min_samples_leaf=1,  max_features="sqrt"),
    dict(n_estimators=200, max_depth=None, min_samples_leaf=4,  max_features="sqrt"),
    dict(n_estimators=300, max_depth=12,   min_samples_leaf=2,  max_features="sqrt"),
    dict(n_estimators=300, max_depth=20,   min_samples_leaf=2,  max_features="sqrt"),
    dict(n_estimators=300, max_depth=None, min_samples_leaf=2,  max_features=0.5),
    dict(n_estimators=300, max_depth=None, min_samples_leaf=8,  max_features="sqrt"),
    dict(n_estimators=500, max_depth=None, min_samples_leaf=2,  max_features="sqrt",
         class_weight="balanced"),
    dict(n_estimators=300, max_depth=16,   min_samples_leaf=4,  max_features="log2"),
]

# --quick searches these two; the full grid above is the default.
GRID_QUICK = [GRID_FULL[1], GRID_FULL[2]]

# `GRID` is what search_hyperparameters reads; cmd_train rebinds it.
GRID = GRID_FULL


def search_hyperparameters(C, inner_cut, val_cut, args, say):
    """Grid search, selected on a VALIDATION split carved out of the training
    data -- never on the test set.

    The corpus is cut twice.  Statements before `inner_cut` train each
    candidate model; those between `inner_cut` and `val_cut` are the validation
    goals it is scored on; everything after `val_cut` is the test set and is not
    touched here at all.  Tuning on the test set would make every figure it
    later produces meaningless, and the temptation is real because the test
    split is already wired up.

    Selection is by validation recall@10 rather than by classification
    accuracy.  The task is ranking: a model can classify most pairs correctly
    and still order the plausible candidates badly, and it is the ordering that
    the prover consumes."""
    best, results = None, []
    for k, params in enumerate(GRID, 1):
        pred = Predator2(seed=args.seed, model="forest", **params)
        try:
            pred.train(C, inner_cut, n_neg=args.n_neg,
                       max_goals=min(args.max_goals, 1500), seed=args.seed)
        except SystemExit:
            raise
        ev = evaluate(C, inner_cut, pred, n_goals=min(args.n_goals, 80),
                      pool_cap=min(args.pool, 1500), seed=args.seed,
                      goal_limit=val_cut)
        sc = ev["recall"].get(10, 0.0)
        results.append((sc, params, ev["mrr"]))
        say("      %d/%d  recall@10 %.3f  MRR %.3f   %s"
            % (k, len(GRID), sc, ev["mrr"],
               ", ".join("%s=%s" % (a, b) for a, b in params.items())))
        if best is None or sc > best[0]:
            best = (sc, params)
    say("    chosen: %s   (validation recall@10 %.3f)"
        % (", ".join("%s=%s" % (a, b) for a, b in best[1].items()), best[0]))
    return best[1], results


# ===========================================================================
#  prove:  one named theorem, end to end
# ===========================================================================

def rrf(orderings, k=60):
    """Reciprocal-rank fusion of several rankings of the same items.

    Each ranking votes 1/(k + rank) for every item and the votes are summed.
    The constant k damps the top: without it a single ranker's first place
    would outweigh everything, and the point of fusing is that the rankers are
    right about different things.

    Used here because Predator and the frequency baseline fail in complementary
    ways on set.mm.  Predator places premises that share notation with the goal
    at ranks 1-6 and buries the generic logical lemmas -- orbi1i, 3bitrri and
    the rest of the propositional plumbing -- in the hundreds.  Frequency does
    the reverse: it finds the plumbing, because plumbing is by definition cited
    everywhere, and cannot see content at all.  Neither ordering dominates, so
    fusing them should beat both, and it costs one pass.
    """
    votes = defaultdict(float)
    for order in orderings:
        for r, item in enumerate(order, 1):
            votes[item] += 1.0/(k + r)
    return sorted(votes, key=lambda it: -votes[it])

def rank_for_goal(C, cut, pred, goal_idx, pool_cap=0):
    """Rank every statement available to a goal, under Predator and both
    baselines.  Returns (ranked, by_freq, by_chron, gold)."""
    usage, rare = defaultdict(int), Predator2._rare_symbols(C)
    for t in C[:cut]:
        for p in t.premises: usage[p] += 1
    g = C[goal_idx]
    gold = [p for p in g.premises if any(t.label == p for t in C[:goal_idx])]
    pos_of = {t.label: i for i, t in enumerate(C)}
    pool = [t for t in C[:goal_idx] if t.is_logical]
    if pool_cap and len(pool) > pool_cap:
        keep = {l for l in gold}
        import random as _r
        rr = _r.Random(0)
        while len(keep) < pool_cap:
            keep.add(pool[rr.randrange(len(pool))].label)
        pool = [t for t in pool if t.label in keep]
    neigh = Predator2.local_use(C, goal_idx)
    rows = [pred.features(g, c, usage.get(c.label, 0), rare,
                          goal_idx - pos_of[c.label], neigh.get(c.label, 0))
            for c in pool]
    s = pred.score(rows)
    ranked = [pool[j].label for j in sorted(range(len(pool)), key=lambda j: -s[j])]
    by_freq = [c.label for c in sorted(pool, key=lambda c: -usage.get(c.label, 0))]
    by_chron = [c.label for c in sorted(pool, key=lambda c: -c.order)]
    fused = rrf([ranked, by_freq])
    return ranked, by_freq, by_chron, fused, gold, len(pool)


def cmd_prove(a):
    """A single named theorem, shown in full: its statement, the premises its
    proof actually uses, and how deep each method must read to reach them."""
    run = None if a.no_artifacts else Run(a.outdir)
    say = run.log if run else print
    C = parse_mm(a.db, a.limit, progress=False)
    idx = next((i for i, t in enumerate(C) if t.label == a.label), None)
    if idx is None:
        say("no statement labelled %r in the first %d of %s"
            % (a.label, len(C), a.db))
        cands = [t.label for t in C if a.label in t.label][:12]
        if cands: say("similar labels present: %s" % ", ".join(cands))
        say("try a larger --limit, or 0 for the whole corpus")
        return
    g = C[idx]
    say("="*70)
    say("  PROVING  %s   (statement %d of %s)" % (g.label, idx, a.db))
    say("="*70)
    say("\n  %s" % " ".join(g.tokens))
    say("\n  its proof cites %d logical premises:" % len(g.premises))
    for p in g.premises:
        t = next((t for t in C if t.label == p), None)
        say("     %-12s %s" % (p, " ".join(t.tokens)[:56] if t else ""))

    cut = int(idx*a.p)
    say("\n  training on statements 0..%d  (p = %.2f of everything before it)"
        % (cut-1, a.p))
    pred = Predator2(seed=a.seed, model=a.model)
    info = pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
    say("  %s goals, %s examples, model %s"
        % (f"{info['goals']:,}", f"{info['examples']:,}", a.model))

    ranked, by_freq, by_chron, fused, gold, npool = rank_for_goal(C, cut, pred, idx, a.pool)
    if not gold:
        say("\n  none of its premises precede it in the parsed fragment; "
            "raise --limit"); return
    say("\n  candidate pool: %s statements" % f"{npool:,}")
    say("\n  rank of each true premise (lower is better):")
    say("     %-12s %10s %10s %10s %10s"
        % ("premise", "Predator", "frequency", "chrono", "FUSED"))
    for p in gold:
        say("     %-12s %10s %10s %10s %10s"
            % (p,
               ranked.index(p)+1 if p in ranked else "-",
               by_freq.index(p)+1 if p in by_freq else "-",
               by_chron.index(p)+1 if p in by_chron else "-",
               fused.index(p)+1 if p in fused else "-"))
    def eff(order):
        rs = [order.index(p)+1 for p in gold if p in order]
        return max(rs)/len(order) if rs else 1.0
    e_p, e_f, e_c, e_x = eff(ranked), eff(by_freq), eff(by_chron), eff(fused)
    say("\n  EFFORT -- fraction of the pool read before every premise is in hand")
    say("     Predator %.4f   frequency %.4f   chrono %.4f   FUSED %.4f"
        % (e_p, e_f, e_c, e_x))
    best_base = min(e_f, e_c)
    say("     Predator vs best baseline : %.1fx %s"
        % (max(best_base/e_p, e_p/best_base), "better" if e_p < best_base else "WORSE"))
    say("     FUSED    vs best baseline : %.1fx %s"
        % (max(best_base/e_x, e_x/best_base), "better" if e_x < best_base else "WORSE"))
    say("     FUSED    vs Predator      : %.1fx %s"
        % (max(e_p/e_x, e_x/e_p), "better" if e_x < e_p else "worse"))
    if run:
        run.finish(dict(label=a.label, statement=" ".join(g.tokens),
                        premises=gold, pool=npool,
                        effort=dict(predator=e_p, frequency=e_f,
                                    chronological=e_c, fused=e_x),
                        ranks={p: dict(predator=ranked.index(p)+1 if p in ranked else None,
                                       frequency=by_freq.index(p)+1 if p in by_freq else None,
                                       chronological=by_chron.index(p)+1 if p in by_chron else None)
                               for p in gold}), pred, a)


# ===========================================================================
#  sweep:  the training fraction p
# ===========================================================================
def cmd_sweep(a):
    run = None if a.no_artifacts else Run(a.outdir)
    say = run.log if run else print
    C = parse_mm(a.db, a.limit, progress=False)
    say("Corpus %s: %s statements\n" % (a.db, f"{len(C):,}"))
    say("   p   train   test   r@10  r@50    MRR  effort  vs.brute  best baseline r@10")
    rows = []
    for p in [float(x) for x in a.ps.split(",")]:
        cut = int(len(C)*p)
        pred = Predator2(seed=a.seed, model=a.model)
        pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
        ev = evaluate(C, cut, pred, a.n_goals, a.pool, seed=a.seed)
        base = max(ev["recall_freq"][10], ev["recall_chron"][10])
        say(" %.2f %7d %6d  %.3f %.3f  %.3f  %.4f    %.2fx   %.3f%s"
            % (p, cut, len(C)-cut, ev["recall"][10], ev["recall"][50], ev["mrr"],
               ev["effort_predator"], 1/ev["effort_ratio"], base,
               "   <-- beaten" if ev["recall"][10] > base else ""))
        rows.append(dict(p=p, **{k: v for k, v in ev.items() if k != "rows"}))
    if run: run.finish(dict(sweep=rows), None, a)

# ===========================================================================
#  artifacts, commands
# ===========================================================================
class Run:
    def __init__(self, base=None):
        base = base or os.environ.get("PREDATOR_OUT", "runs")
        st = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        p = os.path.join(base, st); k = 2
        while os.path.exists(p): p = os.path.join(base, "%s_%d" % (st, k)); k += 1
        os.makedirs(p, exist_ok=True); self.dir, self.lines = p, []
    def log(self, *a):
        s = " ".join(str(x) for x in a); print(s); self.lines.append(s)
    def finish(self, res, pred=None, args=None):
        json.dump(dict(version=VERSION, python=platform.python_version(),
                       numpy=HAVE_NUMPY, platform=platform.platform(),
                       timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
                       arguments=vars(args) if args else {}),
                  open(os.path.join(self.dir, "manifest.json"), "w"), indent=2)
        json.dump(res, open(os.path.join(self.dir, "results.json"), "w"),
                  indent=2, default=str)
        if pred: json.dump(pred.to_dict(),
                           open(os.path.join(self.dir, "predator_2.json"), "w"), indent=2)
        open(os.path.join(self.dir, "run.log"), "w").write("\n".join(self.lines)+"\n")
        self.log("\nartifacts in %s/" % self.dir)
        for f in sorted(os.listdir(self.dir)): self.log("   ", f)


def fetch(name="set.mm", dest=None):
    import urllib.request
    url, desc = MM_URLS[name]
    print("downloading %s\n  %s\n  %s" % (name, desc, url))
    print("  set.mm is about 40 MB; this may take a minute.")
    urllib.request.urlretrieve(url, dest or name)
    print("saved %s (%.1f MB)" % (dest or name, os.path.getsize(dest or name)/1e6))


def cmd_stats(a):
    C = parse_mm(a.db, a.limit)
    s = corpus_stats(C)
    print("\nCorpus: %s" % a.db)
    print("  statements %(statements)s   axioms %(axioms)s" % s)
    print("  of which  %(logical)s logical ('|-')   %(syntax)s syntax (wff/class/setvar)" % s)
    print("  references: %s logical, %s syntax (syntax excluded from premises)"
          % (f"{s['logical_refs']:,}", f"{s['syntax_refs']:,}"))
    print("  vocabulary %(vocabulary)s distinct symbols" % s)
    print("  LOGICAL premises per proof: mean %.1f  median %.0f  max %d"
          % (s["premises_mean"], s["premises_median"], s["premises_max"]))
    print("  most-cited logical statements:")
    for lab, n in s["most_used"]: print("     %-14s %6d citations" % (lab, n))


def cmd_train(a):
    run = None if a.no_artifacts else Run(a.outdir)
    say = run.log if run else print
    say("="*70); say("  PREDATOR_2 v%s  --  premise selection over ZFC" % VERSION)
    say("  Brian Tenneson   btenneson2301.substack.com")
    if run: say("  output: %s" % run.dir)
    say("="*70)
    if not os.path.exists(a.db):
        raise SystemExit("no such file: %s\nRun:  python predator2.py fetch set.mm" % a.db)
    t0 = time.perf_counter()
    C = parse_mm(a.db, a.limit)
    say("\n[1] Corpus %s parsed in %.1fs" % (a.db, time.perf_counter()-t0))
    s = corpus_stats(C)
    say("    %(statements)s statements: %(logical)s logical, %(syntax)s syntax" % s)
    say("    %s logical references kept; %s syntax references excluded"
        % (f"{s['logical_refs']:,}", f"{s['syntax_refs']:,}"))
    say("    logical premises per proof: mean %.1f  median %.0f  max %d"
        % (s["premises_mean"], s["premises_median"], s["premises_max"]))

    cut = int(len(C)*a.p)
    say("\n[2] Temporal split at p = %.2f" % a.p)
    say("    train on statements 0..%d, test on %d.." % (cut-1, cut))

    chosen = {}
    if a.search:
        if a.model != "forest":
            say("\n[2b] --search only applies to the forest model; ignoring")
        else:
            inner = int(cut*0.85)
            say("\n[2b] Hyperparameter search")
            say("     train 0..%d   validate %d..%d   test %d..  (test untouched)"
                % (inner-1, inner, cut-1, cut))
            t0 = time.perf_counter()
            global GRID
            GRID = GRID_QUICK if getattr(a, "quick", False) else GRID_FULL
            say("     grid: %d configurations%s" % (len(GRID),
                "  (--quick)" if getattr(a, "quick", False) else
                "  (use --quick for 2)"))
            chosen, _ = search_hyperparameters(C, inner, cut, a, say)
            say("     search took %.1fs" % (time.perf_counter()-t0))

    pred = Predator2(seed=a.seed, model=a.model, **chosen)
    t0 = time.perf_counter()
    info = pred.train(C, cut, n_neg=a.n_neg, max_goals=a.max_goals, seed=a.seed)
    tt = time.perf_counter()-t0
    say("\n[3] Training <%s>  [%s]:  %s goals, %s examples, %.1fs"
        % (pred.tag, a.model, f"{info['goals']:,}", f"{info['examples']:,}", tt))
    lbl = "weight" if a.model == "logistic" else "importance"
    for k, v in pred.model.describe(Predator2.FEATURES)[:6]:
        say("    %-28s %s%.3f" % (k, "+" if (a.model=="forest" or v>=0) else "", v))

    say("\n[4] Evaluating on %d held-out goals (pool %d)" % (a.n_goals, a.pool))
    ev = evaluate(C, cut, pred, a.n_goals, a.pool, seed=a.seed)
    say("\n[5] Results   (%d goals scored)" % ev["n_goals"])
    say("    %-10s %10s %10s %10s %10s"
        % ("", "Predator_2", "frequency", "chrono", "FUSED"))
    for k in sorted(ev["recall"]):
        say("    recall@%-4d %10.3f %10.3f %10.3f %10.3f"
            % (k, ev["recall"][k], ev["recall_freq"][k], ev["recall_chron"][k],
               ev["recall_fused"][k]))
    say("    MRR        %10.3f" % ev["mrr"])
    say("\n    EFFORT  fraction of the pool you must read to find every premise")
    say("      Predator_2 %.4f   brute force %.4f   FUSED %.4f"
        % (ev["effort_predator"], ev["effort_bruteforce"], ev["effort_fused"]))
    say("      -> Predator %.1fx less of the library;  fused %.1fx less"
        % (1/ev["effort_ratio"],
           ev["effort_bruteforce"]/max(ev["effort_fused"], 1e-9)))
    if run: run.finish(dict(corpus=s, split=dict(p=a.p, cut=cut),
                            training=info, evaluation=ev), pred, a)


def cmd_doctor(a):
    print("Predator_2 v%s" % VERSION)
    print("  python     %s" % platform.python_version())
    print("  numpy      %s" % ("yes" if HAVE_NUMPY else "no  (not needed)"))
    print("  sklearn    %s" % ("yes" if HAVE_SKLEARN else
                               "no  -- needed only for --model forest; "
                               "pip install scikit-learn"))
    print("  output     %s" % (os.environ.get("PREDATOR_OUT") or "runs"))
    for f, (u, d) in MM_URLS.items():
        print("  %-9s %s" % (f, ("PRESENT, %.1f MB" % (os.path.getsize(f)/1e6))
                             if os.path.exists(f) else "not downloaded -- %s" % d))


def cmd_menu(_):
    print(__doc__.split("COMMANDS")[0])
    print("  1  fetch set.mm    download ZFC set theory (~40 MB)")
    print("  2  stats           describe a downloaded corpus")
    print("  3  train           train and evaluate Predator_2")
    print("  4  prove prcom     one theorem end to end:  { A , B } = { B , A }")
    print("  5  sweep p         vary the training fraction")
    print("  6  doctor          check this machine")
    print("  q  quit\n")
    try: c = input("choose: ").strip().lower()
    except (EOFError, KeyboardInterrupt): return
    ns = argparse.Namespace(db="set.mm", limit=0, p=.8, n_neg=25, max_goals=4000,
                            n_goals=200, pool=3000, seed=0, outdir=None,
                            no_artifacts=False, model="logistic", search=False,
                            quick=False, label="prcom", ps="0.3,0.5,0.7,0.8,0.9")
    if c in ("1", "fetch"): fetch("set.mm")
    elif c in ("2", "stats"):
        ns.db = input("file [set.mm]: ") or "set.mm"
        ns.limit = int(input("statements to read, 0 = all [8000]: ") or 8000)
        cmd_stats(ns)
    elif c in ("3", "train"):
        ns.db = input("file [set.mm]: ") or "set.mm"
        ns.limit = int(input("statements to read, 0 = all [8000]: ") or 8000)
        m = (input("model, logistic or forest [forest]: ") or "forest").strip()
        ns.model = m if m in ("logistic", "forest") else "forest"
        if ns.model == "forest":
            ns.search = (input("search hyperparameters? y/n [y]: ") or "y").lower().startswith("y")
        cmd_train(ns)
    elif c in ("4", "prove"):
        ns.label = input("label [prcom]: ") or "prcom"
        ns.limit = 12000; cmd_prove(ns)
    elif c in ("5", "sweep"):
        ns.ps = input("values of p [0.3,0.5,0.7,0.8,0.9]: ") or "0.3,0.5,0.7,0.8,0.9"
        ns.limit = int(input("statements to read [8000]: ") or 8000)
        ns.n_goals = 150; cmd_sweep(ns)
    elif c in ("6", "doctor"): cmd_doctor(ns)


def main():
    ap = argparse.ArgumentParser(prog="predator2", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    for nm in ("train", "stats"):
        p = sub.add_parser(nm)
        p.add_argument("--db", default="set.mm")
        p.add_argument("--limit", type=int, default=0,
                       help="statements to read; 0 = all (set.mm is large)")
        if nm == "train":
            p.add_argument("-p", type=float, default=.8)
            p.add_argument("--n-neg", type=int, default=25)
            p.add_argument("--max-goals", type=int, default=4000)
            p.add_argument("--n-goals", type=int, default=200)
            p.add_argument("--pool", type=int, default=3000)
            p.add_argument("--seed", type=int, default=0)
            p.add_argument("--model", choices=["logistic", "forest"],
                           default="logistic",
                           help="forest needs scikit-learn; captures interactions")
            p.add_argument("--quick", action="store_true",
                           help="search a 2-point grid instead of 8")
            p.add_argument("--search", action="store_true",
                           help="grid-search forest hyperparameters on a "
                                "validation split carved from training data")
            p.add_argument("--outdir", default=os.environ.get("PREDATOR_OUT"))
            p.add_argument("--no-artifacts", action="store_true")
    pr = sub.add_parser("prove", help="one named theorem, ranks and effort")
    pr.add_argument("--label", default="prcom",
                    help="Metamath label; default prcom, i.e. { A , B } = { B , A }")
    pr.add_argument("--db", default="set.mm")
    pr.add_argument("--limit", type=int, default=12000)
    pr.add_argument("-p", type=float, default=.8)
    pr.add_argument("--model", choices=["logistic", "forest"], default="logistic")
    pr.add_argument("--n-neg", type=int, default=25)
    pr.add_argument("--max-goals", type=int, default=3000)
    pr.add_argument("--pool", type=int, default=0, help="0 = every available statement")
    pr.add_argument("--seed", type=int, default=0)
    pr.add_argument("--outdir", default=os.environ.get("PREDATOR_OUT"))
    pr.add_argument("--no-artifacts", action="store_true")

    sw = sub.add_parser("sweep", help="vary the training fraction p")
    sw.add_argument("--ps", default="0.3,0.5,0.7,0.8,0.9")
    sw.add_argument("--db", default="set.mm")
    sw.add_argument("--limit", type=int, default=8000)
    sw.add_argument("--model", choices=["logistic", "forest"], default="logistic")
    sw.add_argument("--n-neg", type=int, default=25)
    sw.add_argument("--max-goals", type=int, default=3000)
    sw.add_argument("--n-goals", type=int, default=150)
    sw.add_argument("--pool", type=int, default=3000)
    sw.add_argument("--seed", type=int, default=0)
    sw.add_argument("--outdir", default=os.environ.get("PREDATOR_OUT"))
    sw.add_argument("--no-artifacts", action="store_true")

    f = sub.add_parser("fetch"); f.add_argument("name", nargs="?", default="set.mm",
                                                choices=list(MM_URLS))
    f.add_argument("--dest")
    sub.add_parser("doctor")
    a = ap.parse_args()
    if a.cmd is None: cmd_menu(a)
    elif a.cmd == "train": cmd_train(a)
    elif a.cmd == "stats": cmd_stats(a)
    elif a.cmd == "prove": cmd_prove(a)
    elif a.cmd == "sweep": cmd_sweep(a)
    elif a.cmd == "fetch": fetch(a.name, a.dest)
    elif a.cmd == "doctor": cmd_doctor(a)


if __name__ == "__main__":
    main()
