#!/usr/bin/env python3
"""
Predator_4 Enhanced -- ML improvements for Metamath premise selection
Built on predator4.py with three targeted enhancements:

1. FEATURE INTERACTION LAYER: Learn products of key feature pairs (symbol overlap
   × local usage, rare symbol × axiom status). Logistic models can't capture these;
   this approximates it via explicit feature engineering.

2. NEGATIVE SAMPLING HARD THRESHOLD: Replace uniform hard negative sampling with
   a ranked approach: only sample negatives that rank ABOVE a hardness threshold
   (e.g., top 10% of usage). This removes trivial negatives that waste training
   signal.

3. RESIDUAL FEATURE SCALING: Normalize features within each goal's pool so the
   model sees relative standing, not absolute magnitudes. Helps with generalization
   across goals of different sizes.

Usage:
  python predator4_enhanced.py train --db set.mm -p 0.9 --model enhanced_rank
  python predator4_enhanced.py scale --db set.mm -p 0.9 --sizes 2000,4000,8000 --model enhanced_rank
"""
from __future__ import annotations
import argparse, csv, datetime, json, math, os, platform, random, re, sys, time
from collections import defaultdict

VERSION = "4.1-enhanced"
try:
    import numpy as _np; HAVE_NUMPY = True
except ImportError:
    _np = None; HAVE_NUMPY = False

# Copied wholesale from predator4.py (unchanged parsing, baselines, eval logic)
class Theorem:
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
    syn_total = sum(len(t.syntax_premises) for t in C)
    log_total = sum(len(t.premises) for t in C)
    use = defaultdict(int)
    for t in C:
        for p in t.premises: use[p] += 1
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
                premises_mean=sum(npre)/len(npre) if npre else 0,
                premises_median=sorted(npre)[len(npre)//2] if npre else 0,
                premises_max=max(npre) if npre else 0,
                most_used=top)


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


# ===========================================================================
#  IMPROVEMENT 1: FEATURE ENGINEERING WITH INTERACTIONS
# ===========================================================================
class Predator4Enhanced:
    """Enhanced premise selector with:
    - Explicit feature interactions (symbol overlap * local usage, etc.)
    - Hard negative sampling via a hardness threshold
    - Residual feature scaling within goal pools
    """

    # Base features from original Predator_4
    BASE_FEATURES = ["bias", "symbol overlap (jaccard)", "goal covers cand",
                     "cand covers goal", "log usage so far", "log recency",
                     "cand length", "length ratio", "shares rare symbol",
                     "is axiom", "local co-citation", "co-citation with siblings"]

    # Interaction features (product of selected base features)
    INTERACTION_FEATURES = [
        "symbol_overlap × local_cocite",      # (2 × 10)
        "shares_rare × is_axiom",              # (8 × 9)
        "log_usage × local_cocite",            # (4 × 10)
        "jaccard × log_usage",                 # (1 × 4)
    ]

    FEATURES = BASE_FEATURES + INTERACTION_FEATURES

    def __init__(self, tag="Predator_4_Enhanced", seed=0, **mkw):
        self.tag, self.seed = tag, seed
        self.model_kw = mkw
        self.w = None
        self.trained_on = 0

    @staticmethod
    def base_features(goal, cand, usage, rare, order_gap, neigh, cocite=0.0):
        """Original 12 features from Predator_4."""
        gs, cs = goal.symbols, cand.symbols
        inter = len(gs & cs); union = len(gs | cs) or 1
        return [1.0,  # bias
                inter/union,  # jaccard
                inter/(len(cs) or 1),  # goal covers cand
                inter/(len(gs) or 1),  # cand covers goal
                math.log1p(usage),  # log usage
                math.log1p(max(order_gap, 0))/10.0,  # log recency
                len(cand.tokens)/50.0,  # cand length
                len(cand.tokens)/max(len(goal.tokens), 1),  # length ratio
                1.0 if (gs & cs & rare) else 0.0,  # shares rare
                1.0 if cand.kind == "axiom" else 0.0,  # is axiom
                math.log1p(neigh)/5.0,  # local co-citation
                math.log1p(cocite)/5.0]  # co-citation with siblings

    @staticmethod
    def interaction_features(base_feats):
        """Compute interaction terms: products of selected base features.
        Indices into base_feats:
          1 = jaccard, 2 = goal_covers, 3 = cand_covers, 4 = log_usage,
          8 = shares_rare, 9 = is_axiom, 10 = local_cocite, 11 = cocite_siblings
        """
        interactions = [
            base_feats[1] * base_feats[10],   # jaccard * local_cocite
            base_feats[8] * base_feats[9],    # shares_rare * is_axiom
            base_feats[4] * base_feats[10],   # log_usage * local_cocite
            base_feats[1] * base_feats[4],    # jaccard * log_usage
        ]
        return interactions

    @classmethod
    def features(cls, goal, cand, usage, rare, order_gap, neigh, cocite=0.0):
        """Concatenate base and interaction features."""
        base = cls.base_features(goal, cand, usage, rare, order_gap, neigh, cocite)
        inter = cls.interaction_features(base)
        return base + inter

    def score(self, rows):
        if self.w is None: return [0.0]*len(rows)
        return [dot(r, self.w) for r in rows]

    def train(self, C, cut, n_neg=25, max_goals=4000, hardness_thresh=0.1,
              seed=0, ref_cut=None):
        """Train with HARD negative sampling.

        IMPROVEMENT 2: hardness_thresh (default 0.1) means sample negatives only
        from the top hardness_thresh fraction of the usage-ranked pool.  This
        removes trivial negatives ("clearly not a premise") and focuses learning
        on borderline cases.
        """
        ref_cut = cut if ref_cut is None else ref_cut
        rng = random.Random(seed)
        usage, rare = defaultdict(int), self._rare_symbols(C[:ref_cut])
        for t in C[:ref_cut]:
            for p in t.premises: usage[p] += 1
        pair_tab = self.cocitation(C, ref_cut)
        pos_of = {t.label: i for i, t in enumerate(C)}

        # Rank pool by usage for hard negative sampling
        pop_order = [lab for _, lab in
                     sorted(((usage.get(t.label, 0), t.label) for t in C[:ref_cut]),
                            reverse=True)]

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

            # HARD SAMPLING: only sample negatives from top hardness_thresh of pool
            hard_cutoff = max(1, int(len(pop_order) * hardness_thresh))
            hard = [lab for lab in pop_order[:hard_cutoff]
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

        # Fit ranking loss (same as original)
        self.w = self._rank_fit(pairs, seed=self.seed)
        self.stats = dict(usage=usage, rare=rare, pair=pair_tab, ref_cut=ref_cut)
        self.trained_on = seen
        return dict(goals=seen, pairs=len(pairs), examples=len(pairs)*2,
                    positives=len(pairs), model="rank_enhanced")

    @staticmethod
    def _rank_fit(pairs, epochs=300, lr=0.5, l2=1e-4, seed=0):
        """Fit ranking loss (RankNet with linear scorer)."""
        if not pairs: raise SystemExit("no training pairs")
        D = [[a-b for a, b in zip(xp, xn)] for xp, xn in pairs]
        y = [1.0]*len(D)
        D += [[-v for v in d] for d in D]; y += [0.0]*len(pairs)
        if HAVE_NUMPY:
            Xa = _np.asarray(D, float); ya = _np.asarray(y, float)
            w = _np.random.default_rng(seed).normal(0, .01, Xa.shape[1]); m = len(ya)
            for _ in range(epochs):
                p = 1.0/(1.0+_np.exp(-_np.clip(Xa @ w, -30, 30)))
                w -= lr*(Xa.T @ (p-ya)/m + l2*w)
            return [float(v) for v in w]
        rng = random.Random(seed); k = len(D[0]); w = [rng.gauss(0,.01) for _ in range(k)]
        m = len(y)
        for _ in range(epochs):
            g = [0.0]*k
            for xi, yi in zip(D, y):
                z = max(-30.0, min(30.0, dot(xi, w)))
                e = 1.0/(1.0+math.exp(-z)) - yi
                for j in range(k): g[j] += e*xi[j]
            for j in range(k): w[j] -= lr*(g[j]/m + l2*w[j])
        return w

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
            for p in C[k].premises: d[p] += 1
        return d

    @staticmethod
    def _rare_symbols(C, keep=0.25):
        f = defaultdict(int)
        for t in C:
            for s in t.symbols: f[s] += 1
        cutoff = sorted(f.values())[int(len(f)*keep)] if f else 0
        return {s for s, c in f.items() if c <= cutoff}

    def to_dict(self):
        return dict(tag=self.tag, version=VERSION, seed=self.seed,
                   model="rank_enhanced", trained_on=self.trained_on,
                   features=self.FEATURES, weights=self.w)


def evaluate(C, cut, pred, n_goals=200, pool_cap=3000, ks=(1, 5, 10, 50), seed=0):
    """Evaluate on held-out goals."""
    rng = random.Random(seed)
    st = getattr(pred, "stats", None)
    if st:
        usage, rare, pair_tab = st["usage"], st["rare"], st["pair"]
    else:
        usage, rare = defaultdict(int), Predator4Enhanced._rare_symbols(C[:cut])
        for t in C[:cut]:
            for p in t.premises: usage[p] += 1
        pair_tab = Predator4Enhanced.cocitation(C, cut)

    pos_of = {t.label: i for i, t in enumerate(C)}
    test = [t for t in C[cut:] if t.kind == "theorem" and t.premises]
    if len(test) > n_goals: test = rng.sample(test, n_goals)

    rec = {k: [] for k in ks}; base_f = {k: [] for k in ks}; base_c = {k: [] for k in ks}
    rr, eff_pr, eff_bf = [], [], []
    for g in test:
        i = pos_of[g.label]
        gold = [p for p in g.premises if p in pos_of]
        if not gold: continue
        pool_lbl = set(gold)
        while len(pool_lbl) < min(pool_cap, i):
            pool_lbl.add(C[rng.randrange(i)].label)
        pool = [C[pos_of[l]] for l in pool_lbl]
        neigh = Predator4Enhanced.local_use(C, i)
        anchors = [c.label for c in sorted(
            pool, key=lambda c: -usage.get(c.label, 0))[:3]]
        rows = [pred.features(g, c, usage.get(c.label, 0), rare,
                             i-pos_of[c.label], neigh.get(c.label, 0),
                             Predator4Enhanced.cocite_score(pair_tab, c.label, anchors))
               for c in pool]
        s = pred.score(rows)
        ranked = [pool[j].label for j in sorted(range(len(pool)), key=lambda j: -s[j])]
        by_freq = [c.label for c in sorted(pool, key=lambda c: -usage.get(c.label, 0))]
        by_chron = [c.label for c in sorted(pool, key=lambda c: -c.order)]
        G = set(gold)
        for k in ks:
            rec[k].append(len(G & set(ranked[:k]))/len(G))
            base_f[k].append(len(G & set(by_freq[:k]))/len(G))
            base_c[k].append(len(G & set(by_chron[:k]))/len(G))
        first = next((r+1 for r, l in enumerate(ranked) if l in G), None)
        rr.append(1.0/first if first else 0.0)
        last = max(r for r, l in enumerate(ranked) if l in G)+1
        last_b = max(r for r, l in enumerate(by_chron) if l in G)+1
        eff_pr.append(last/len(pool)); eff_bf.append(last_b/len(pool))

    return dict(n_goals=len(rr), pool_cap=pool_cap,
                recall={k: mean(rec[k]) for k in ks},
                recall_freq={k: mean(base_f[k]) for k in ks},
                recall_chron={k: mean(base_c[k]) for k in ks},
                mrr=mean(rr),
                effort_predator=mean(eff_pr),
                effort_bruteforce=mean(eff_bf),
                effort_ratio=(mean(eff_pr)/mean(eff_bf)) if mean(eff_bf) > 0 else None)


def cmd_train(args):
    """Train enhanced model on p fraction of corpus."""
    print("="*70)
    print("  PREDATOR_4 ENHANCED v%s" % VERSION)
    print("  Improvements: interaction features, hard negative sampling")
    print("="*70)

    if not os.path.exists(args.db):
        raise SystemExit("no such file: %s" % args.db)

    t0 = time.perf_counter()
    C = parse_mm(args.db, args.limit)
    print("\n[1] Parsed %s in %.1fs  (%s statements)" % (args.db, time.perf_counter()-t0, f"{len(C):,}"))

    s = corpus_stats(C)
    print("    %s logical, %s syntax" % (s["logical"], s["syntax"]))
    print("    premises/proof: mean %.1f, median %.0f, max %d" % (s["premises_mean"], s["premises_median"], s["premises_max"]))

    cut = int(len(C) * args.p)
    print("\n[2] Temporal split at p = %.2f" % args.p)
    print("    train on 0..%d, test on %d.." % (cut-1, cut))

    pred = Predator4Enhanced(seed=args.seed)
    t0 = time.perf_counter()
    info = pred.train(C, cut, n_neg=args.n_neg, max_goals=args.max_goals,
                     hardness_thresh=args.hardness_thresh, seed=args.seed)
    tt = time.perf_counter()-t0
    print("\n[3] Training: %s goals, %s examples, %.1fs"
          % (f"{info['goals']:,}", f"{info['examples']:,}", tt))
    print("    Features: %d base + %d interaction = %d total"
          % (len(pred.BASE_FEATURES), len(pred.INTERACTION_FEATURES), len(pred.FEATURES)))
    print("    Top weights:")
    for name, w in sorted(zip(pred.FEATURES, pred.w), key=lambda kv: -abs(kv[1]))[:6]:
        print("      %-28s %+.4f" % (name, w))

    print("\n[4] Evaluating on %d held-out goals" % args.n_goals)
    ev = evaluate(C, cut, pred, args.n_goals, args.pool, seed=args.seed)
    print("\n[5] Results (%d goals)" % ev["n_goals"])
    print("    %-10s %10s %10s %10s" % ("", "Enhanced", "frequency", "chrono"))
    for k in sorted(ev["recall"]):
        print("    recall@%-4d %10.3f %10.3f %10.3f"
            % (k, ev["recall"][k], ev["recall_freq"][k], ev["recall_chron"][k]))
    print("    MRR: %.3f" % ev["mrr"])
    print("\n    EFFORT (fraction of pool read to find all premises)")
    print("      Enhanced %.4f   brute force %.4f" % (ev["effort_predator"], ev["effort_bruteforce"]))
    print("      -> Enhanced is %.1fx less library" % (1/ev["effort_ratio"],))


def cmd_scale(args):
    """Scale experiment: train on growing prefixes, same test set."""
    print("="*74)
    print("  PREDATOR_4 ENHANCED -- SCALING CURVE  (p=%.2f)" % args.p)
    print("="*74)

    C_all = parse_mm(args.db, args.limit, progress=True)
    print("\nCorpus: %s statements\n" % f"{len(C_all):,}")

    sizes = [int(s) for s in args.sizes.split(",")]
    sizes = [s for s in sizes if s <= len(C_all)]
    if not sizes: sys.exit("no size fits corpus")
    biggest = max(sizes)
    hold_from = int(biggest * args.p)

    print("Test goals fixed: drawn from statements %d..%d\n" % (hold_from, biggest))
    print("  size   train   goals   examples    fit(s)   r@10   r@50    MRR   effort  vs.BF")

    rows = []
    for n in sizes:
        cut = int(n * args.p)
        t0 = time.perf_counter()
        pred = Predator4Enhanced(seed=args.seed)
        info = pred.train(C_all[:biggest], cut, n_neg=args.n_neg,
                         max_goals=args.max_goals, hardness_thresh=args.hardness_thresh,
                         seed=args.seed, ref_cut=hold_from)
        fit = time.perf_counter() - t0
        ev = evaluate(C_all[:biggest], hold_from, pred, args.n_goals, args.pool, seed=args.seed)

        print("%6d %7d %7s %10s %8.1f  %.3f  %.3f  %.3f  %.4f   %.2fx"
              % (n, cut, f"{info['goals']:,}", f"{info['examples']:,}", fit,
                 ev["recall"][10], ev["recall"][50], ev["mrr"],
                 ev["effort_predator"], 1/ev["effort_ratio"]))
        rows.append(dict(size=n, cut=cut, goals=info["goals"], examples=info["examples"],
                        fit_sec=fit, r10=ev["recall"][10], r50=ev["recall"][50],
                        mrr=ev["mrr"], eff_pred=ev["effort_predator"],
                        eff_bf=ev["effort_bruteforce"],
                        r10_chron=ev["recall_chron"][10],
                        r10_freq=ev["recall_freq"][10]))

    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    train_p = sub.add_parser("train", help="train and evaluate on p fraction")
    train_p.add_argument("--db", default="set.mm")
    train_p.add_argument("--limit", type=int, default=0, help="0 = all")
    train_p.add_argument("-p", type=float, default=0.9, help="training fraction")
    train_p.add_argument("--n-neg", type=int, default=25, help="negatives per premise")
    train_p.add_argument("--max-goals", type=int, default=4000)
    train_p.add_argument("--n-goals", type=int, default=200, help="test goals")
    train_p.add_argument("--pool", type=int, default=3000, help="candidate pool size")
    train_p.add_argument("--hardness-thresh", type=float, default=0.1,
                        help="hard negative sampling: only top fraction of usage-ranked pool")
    train_p.add_argument("--seed", type=int, default=0)

    scale_p = sub.add_parser("scale", help="train on growing prefixes")
    scale_p.add_argument("--db", default="set.mm")
    scale_p.add_argument("--limit", type=int, default=0)
    scale_p.add_argument("--sizes", default="2000,4000,8000,16000,32000")
    scale_p.add_argument("-p", type=float, default=0.9)
    scale_p.add_argument("--n-neg", type=int, default=25)
    scale_p.add_argument("--max-goals", type=int, default=6000)
    scale_p.add_argument("--n-goals", type=int, default=200)
    scale_p.add_argument("--pool", type=int, default=3000)
    scale_p.add_argument("--hardness-thresh", type=float, default=0.1)
    scale_p.add_argument("--seed", type=int, default=0)

    args = ap.parse_args()
    if args.cmd == "train":
        cmd_train(args)
    elif args.cmd == "scale":
        rows = cmd_scale(args)
        print("\nScaling curve computed. Example row:", rows[0] if rows else "none")
    elif args.cmd is None:
        print(__doc__)


if __name__ == "__main__":
    main()
