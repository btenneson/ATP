#!/usr/bin/env python3
"""
predator.py  --  Predator_1, a trainable automated theorem prover.

Brian Tenneson.  Companion to ML-SIC-ATP-Theory v001.

WHAT PREDATOR IS
----------------
A tagged ATP in the sense of the self-awareness framework: it carries a
designated formal name <Predator_1>, and it is a semi-ideal computer over the
formula set of a formal system F = (x,y,z).  Its stage map is a guided
best-first search; its halting map fires when the target appears.

Predator differs from the canonical rule-enumeration machine in exactly one
respect.  Brute force computes D_F(S) at every stage, adjoining EVERY direct
consequence.  Predator scores the available consequences with a learned model
and adjoins only the best `beam` of them.  It is, in the vocabulary of the
theory, a nondeterministic proof-search policy whose choice function was fitted
to data rather than fixed in advance.

TRAINING AND TESTING
--------------------
The corpus is split by corpus order: the first p fraction of theorems is
training data, the remaining (1-p) is held out.  The split is TEMPORAL rather
than random -- train on the past, test on the future -- because a random split
lets the model see theorems that postdate its test targets, which is how these
numbers usually get inflated.

HOW PERFORMANCE IS SCORED
-------------------------
Two numbers, always reported together:

  solve rate     fraction of held-out targets proved within the node budget;
  effort ratio   expansions(Predator) / expansions(brute force), computed ONLY
                 over targets that BOTH provers solved.

Reporting the ratio alone would reward failure: a prover that expands three
nodes and finds nothing scores an unbeatable ratio.  Conditioning on joint
success is what makes "further from brute force" mean "better" rather than
"lazier".  The headline figure is the speedup, brute force divided by Predator,
on jointly solved targets.

One thing Predator cannot do, whatever it learns: reach a target at a stage
below its closure depth.  Learning buys breadth, never depth, so the effort
ratio can approach zero while the stage count cannot fall below delta+1.  The
harness checks this and reports any breach as a bug rather than a result.

Copyright (c) 2026 Brian Tenneson.  All Rights Reserved.
btenneson2301.substack.com
"""

from __future__ import annotations
import argparse, json, math, os, random, sys, time
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ml_sic_atp import (Node, TheoremGraph, PropositionalSIC, parse_metamath,
                        standardise, logistic_fit, Run)


# ============================================================================
# 1.  THE PROVER
# ============================================================================

class Predator:
    """
    A tagged ATP.  `tag` is its designated formal name, in the sense of the
    self-awareness framework: a syntactic object denoting the machine, not the
    machine itself.
    """

    def __init__(self, tag="Predator_1", beam=8, seed=0):
        self.tag = tag
        self.beam = beam
        self.seed = seed
        self.w = self.mu = self.sigma = None
        self.trained_on = 0

    # -- features ---------------------------------------------------------
    N_FEATURES = 12

    @staticmethod
    def features(goal: str, cand: str, depth: int, size_fn,
                 split_imp=None) -> list:
        """
        Features of (goal, candidate formula).

        The first eight are surface statistics.  The last four are structural,
        and they were added after inspecting what the surface-only model had
        learned: its heaviest weight fell on "candidate occurs literally in the
        goal", which on this corpus identifies instances of the weakening
        scheme A -> (B -> A) and little else.  A model that has learned one
        axiom's silhouette is not learning to search.

        The structural features name the relations modus ponens actually
        consumes.  To detach the goal from an implication one needs that
        implication and its antecedent, so whether the candidate IS the goal's
        antecedent, or an implication whose consequent is the goal, is the
        question a policy has to answer.  Those are cheap to compute and are
        about the inference rather than about the string.
        """
        gt, ct = set(goal.split()), set(cand.split())
        inter, union = len(gt & ct), len(gt | ct) or 1
        gs, cs = size_fn(goal), size_fn(cand)
        f = [
            1.0,                                  # bias
            inter / union,                        # token overlap with the goal
            inter / (len(ct) or 1),               # how much of cand the goal covers
            1.0 if cand in goal else 0.0,         # cand occurs literally in goal
            abs(gs - cs) / 10.0,                  # size mismatch
            cs / 10.0,                            # candidate size
            depth / 10.0,                         # how deep cand already sits
            1.0 if cs <= gs else 0.0,             # cand no larger than goal
        ]
        # -- structural: what modus ponens would do with this candidate ------
        g_ante = g_cons = None
        c_ante = c_cons = None
        if split_imp is not None:
            sg = split_imp(goal);  g_ante, g_cons = sg if sg else (None, None)
            sc = split_imp(cand);  c_ante, c_cons = sc if sc else (None, None)
        f += [
            1.0 if (g_ante is not None and cand == g_ante) else 0.0,   # cand IS the goal's antecedent
            1.0 if (c_cons is not None and c_cons == goal) else 0.0,   # cand detaches TO the goal
            1.0 if (c_cons is not None and goal in c_cons) else 0.0,   # goal inside cand's consequent
            1.0 if (g_cons is not None and cand == g_cons) else 0.0,   # cand IS the goal's consequent
        ]
        return f

    def score(self, F: np.ndarray) -> np.ndarray:
        if self.w is None:                        # untrained: no preference
            return np.zeros(len(F))
        return ((F - self.mu) / self.sigma) @ self.w

    # -- training ---------------------------------------------------------
    def train(self, g: TheoremGraph, train_names: list, size_fn,
              n_neg=12, split_imp=None):
        """
        Positive examples: formulas that actually appear in the proof of a
        training target (its ancestors).  Negatives: formulas available at the
        time that the proof did not use.  The model therefore learns to
        recognise "this is on the way to that", which is what a search policy
        needs to decide.
        """
        rng = random.Random(self.seed)
        depth = g.closure_depth()
        order = sorted(g.nodes.values(), key=lambda nd: nd.order)
        pos_of = {nd.name: i for i, nd in enumerate(order)}
        X, y = [], []
        for nm in train_names:
            tgt = g.nodes[nm]
            i = pos_of[nm]
            if i < n_neg + 2:
                continue
            anc = g.ancestors(nm)
            if not anc:
                continue
            d = depth
            for a in anc:
                da = d[a] if d[a] != float("inf") else 0
                X.append(self.features(tgt.statement, g.nodes[a].statement,
                                       da, size_fn, split_imp)); y.append(1)
            # HARD negatives.  Sampling any earlier statement makes the task
            # too easy: most of the corpus is irrelevant to any given goal, so
            # a model can score well by rejecting the obviously unrelated and
            # never learn to choose among plausible candidates.  The decision a
            # search policy faces is between formulas available at the SAME
            # stage, so negatives are drawn from statements whose closure depth
            # is no greater than the target's -- the competitors the proof
            # passed over -- with a few random ones retained for contrast.
            dtgt = d[nm] if d[nm] != float("inf") else 0
            competitors = [c for c in order[:i]
                           if c.name not in anc
                           and d[c.name] != float("inf")
                           and d[c.name] <= dtgt]
            hard = rng.sample(competitors, min(int(n_neg * 0.75), len(competitors))) \
                   if competitors else []
            easy_n = n_neg - len(hard)
            easy, tries = [], 0
            while len(easy) < easy_n and tries < 8 * n_neg:
                tries += 1
                c = order[rng.randrange(i)]
                if c.name not in anc and c.name != nm:
                    easy.append(c)
            for c in hard + easy:
                dc = d[c.name] if d[c.name] != float("inf") else 0
                X.append(self.features(tgt.statement, c.statement,
                                       dc, size_fn, split_imp)); y.append(0)
        if not y or sum(y) == 0 or sum(y) == len(y):
            raise ValueError("degenerate training set")
        self.w, self.mu, self.sigma = logistic_fit(
            np.array(X, float), np.array(y, float), seed=self.seed)
        self.trained_on = len(train_names)
        return dict(examples=len(y), positives=int(sum(y)))

    # -- serialisation: the "tagged copy" ---------------------------------
    def to_dict(self) -> dict:
        return dict(tag=self.tag, beam=self.beam, seed=self.seed,
                    trained_on=self.trained_on,
                    weights=None if self.w is None else [float(v) for v in self.w],
                    mu=None if self.mu is None else [float(v) for v in self.mu],
                    sigma=None if self.sigma is None else [float(v) for v in self.sigma])

    @classmethod
    def from_dict(cls, d: dict) -> "Predator":
        p = cls(tag=d["tag"], beam=d["beam"], seed=d["seed"])
        p.trained_on = d.get("trained_on", 0)
        if d.get("weights") is not None:
            p.w = np.array(d["weights"]); p.mu = np.array(d["mu"])
            p.sigma = np.array(d["sigma"])
        return p


# ============================================================================
# 2.  SEARCH:  BRUTE FORCE  AND  PREDATOR
# ============================================================================

def brute_force_search(sic: PropositionalSIC, gamma: list, target: str,
                       budget=20000):
    """
    The canonical rule-enumeration machine: at each stage adjoin EVERY direct
    consequence of the current state.  This is the benchmark, and by the
    Proof-Horizon Theorem it reaches the target exactly at its closure depth.
    """
    state = {f: 0 for f in gamma}
    expansions = 0
    for stage in range(1, 64):
        new = _consequences(sic, list(state))
        fresh = [f for f in new if f not in state]
        if not fresh:
            return dict(found=False, expansions=expansions, stages=stage)
        for f in fresh:
            state[f] = stage
            expansions += 1
            if f == target:
                return dict(found=True, expansions=expansions, stages=stage)
            if expansions >= budget:
                return dict(found=False, expansions=expansions, stages=stage)
    return dict(found=False, expansions=expansions, stages=stage)


def predator_search(sic: PropositionalSIC, gamma: list, target: str,
                    pred: Predator, budget=20000):
    """
    Same rules, same starting hypotheses.  The only difference: at each stage
    the available consequences are scored and only the top `beam` are adjoined.
    Everything else is discarded, which is why Predator can miss proofs that
    brute force finds -- the reason solve rate must be reported.
    """
    state = {f: 0 for f in gamma}
    expansions = 0
    for stage in range(1, 64):
        new = [f for f in _consequences(sic, list(state)) if f not in state]
        if not new:
            return dict(found=False, expansions=expansions, stages=stage)
        if target in new:                       # take the target the moment it appears
            chosen = [target]
        else:
            F = np.array([pred.features(target, f, stage, sic.size, sic.split_imp)
                          for f in new], dtype=float)
            s = pred.score(F)
            chosen = [new[i] for i in np.argsort(-s)[:pred.beam]]
        for f in chosen:
            state[f] = stage
            expansions += 1
            if f == target:
                return dict(found=True, expansions=expansions, stages=stage)
            if expansions >= budget:
                return dict(found=False, expansions=expansions, stages=stage)
    return dict(found=False, expansions=expansions, stages=stage)


def _consequences(sic: PropositionalSIC, formulas: list) -> list:
    """
    One round of D_F: modus ponens plus scheme instantiation, size-bounded.

    The ordering matters and must match the one used to BUILD the corpus.  The
    scheme pools are truncated at `pool_cap` and `ternary_cap`, so which
    instances get generated depends on which formulas sit at the front of the
    list.  Sorting by (size, text) here, exactly as the generator does, is what
    makes a target drawn from the corpus reachable by this search.  Without it
    the two disagree about what D_F contains and better than half the corpus
    becomes underivable -- which looks like a weak prover and is really a
    mismatched reconstruction.
    """
    formulas = sorted(formulas, key=lambda f: (sic.size(f), f))
    have = set(formulas)
    out = []
    for f in formulas:                                   # modus ponens
        sp = sic.split_imp(f)
        if sp and sp[0] in have:
            out.append(sp[1])
    small = [f for f in formulas if sic.size(f) <= sic.scheme_arg_size]
    pool = small[: sic.pool_cap]
    for A in pool:                                       # ax1
        for B in pool:
            out.append(sic.imp(A, sic.imp(B, A)))
    sub = pool[: sic.ternary_cap]
    for A in sub:                                        # ax2
        for B in sub:
            for C in sub:
                out.append(sic.imp(sic.imp(A, sic.imp(B, C)),
                                   sic.imp(sic.imp(A, B), sic.imp(A, C))))
    seen, ded = set(), []
    for f in out:
        if f not in seen and sic.size(f) <= sic.max_formula_size:
            seen.add(f); ded.append(f)
    return ded


# ============================================================================
# 3.  EVALUATION
# ============================================================================

def evaluate(sic, gamma, targets, pred, budget=20000):
    """
    Runs both provers on each held-out target and scores them.

    Solve rates are computed over ALL targets.  The effort ratio is computed
    only over targets both provers solved, because a ratio taken over targets
    Predator abandoned would reward abandoning them.
    """
    rows = []
    for t in targets:
        a = time.perf_counter(); bf = brute_force_search(sic, gamma, t, budget)
        bf_t = time.perf_counter() - a
        a = time.perf_counter(); pr = predator_search(sic, gamma, t, pred, budget)
        pr_t = time.perf_counter() - a
        rows.append(dict(target=t,
                         bf_found=bf["found"], bf_exp=bf["expansions"],
                         bf_stages=bf["stages"], bf_sec=round(bf_t, 6),
                         pr_found=pr["found"], pr_exp=pr["expansions"],
                         pr_stages=pr["stages"], pr_sec=round(pr_t, 6)))
    both = [r for r in rows if r["bf_found"] and r["pr_found"]]
    ratios = [r["pr_exp"] / max(r["bf_exp"], 1) for r in both]
    bft = sum(r["bf_sec"] for r in both); prt = sum(r["pr_sec"] for r in both)
    bfe = sum(r["bf_exp"] for r in both); pre = sum(r["pr_exp"] for r in both)
    deeper = [r for r in both if r["pr_stages"] < r["bf_stages"]]
    return dict(
        n_targets=len(rows),
        bf_solved=sum(1 for r in rows if r["bf_found"]),
        pr_solved=sum(1 for r in rows if r["pr_found"]),
        bf_solve_rate=round(sum(1 for r in rows if r["bf_found"]) / max(len(rows), 1), 4),
        pr_solve_rate=round(sum(1 for r in rows if r["pr_found"]) / max(len(rows), 1), 4),
        n_jointly_solved=len(both),
        effort_ratio_mean=round(float(np.mean(ratios)), 4) if ratios else None,
        effort_ratio_median=round(float(np.median(ratios)), 4) if ratios else None,
        speedup_mean=round(float(np.mean([1 / r for r in ratios])), 3) if ratios else None,
        depth_floor_breaches=len(deeper),
        # Wall clock, reported beside expansions because the two can point in
        # OPPOSITE directions.  Predator scores every candidate it declines to
        # keep, so it pays a per-expansion cost brute force does not, and a
        # large reduction in expansions can still be a loss in seconds.
        # Reporting only the expansion figure overstates the prover.
        bf_seconds=round(bft, 4), pr_seconds=round(prt, 4),
        time_ratio=round(prt / bft, 4) if bft > 0 else None,
        time_speedup=round(bft / prt, 3) if prt > 0 else None,
        us_per_expansion_bf=round(1e6 * bft / max(bfe, 1), 1),
        us_per_expansion_pr=round(1e6 * prt / max(pre, 1), 1),
        rows=rows,
    )


# ============================================================================
# 4.  DRIVER
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--train-frac", type=float, default=0.7,
                    help="fraction of theorems used for training (default 0.7)")
    ap.add_argument("--n-neg", type=int, default=12,
                    help="negatives sampled per training target")
    ap.add_argument("--beam", type=int, default=8,
                    help="how many consequences Predator keeps per stage")
    ap.add_argument("--budget", type=int, default=20000, help="node budget per proof")
    ap.add_argument("--n-test", type=int, default=40, help="held-out targets to try")
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--cap", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--no-artifacts", action="store_true")
    a = ap.parse_args()

    run = None if a.no_artifacts else Run(a.outdir)
    def out(*x): (run.log if run else print)(*x)

    out("=" * 74)
    out("  PREDATOR_1  --  a trainable ATP")
    out("  Brian Tenneson    btenneson2301.substack.com")
    if run: out(f"  run directory: {run.dir}")
    out("=" * 74)

    sic = PropositionalSIC(max_depth=a.depth, cap=a.cap, seed=a.seed)
    g, stage_sizes = sic.run()
    gamma = [nd.statement for nd in g.nodes.values() if nd.kind == "axiom"]
    out(f"\n[1] Corpus: {len(g.nodes)} statements, stages {stage_sizes}")

    theorems = sorted([nd for nd in g.nodes.values() if nd.kind == "theorem"],
                      key=lambda nd: nd.order)
    cut = int(len(theorems) * a.train_frac)
    train, test = theorems[:cut], theorems[cut:]
    out(f"\n[2] Temporal split at p = {a.train_frac}")
    out(f"    train {len(train)} theorems   |   held out {len(test)}")

    pred = Predator(beam=a.beam, seed=a.seed)
    _t0 = time.perf_counter()
    info = pred.train(g, [nd.name for nd in train], sic.size,
                      n_neg=a.n_neg, split_imp=sic.split_imp)
    out(f"\n[3] Training <{pred.tag}>")
    out(f"    {info['examples']} examples, {info['positives']} positive")
    _train_sec = time.perf_counter() - _t0
    out(f"    weights: {[round(float(v),3) for v in pred.w]}")
    out(f"    one-time training cost: {_train_sec:.3f}s")

    rng = random.Random(a.seed)
    pool = [nd for nd in test if g.closure_depth()[nd.name] >= 2]
    tgts = [nd.statement for nd in rng.sample(pool, min(a.n_test, len(pool)))]
    out(f"\n[4] Evaluating on {len(tgts)} held-out targets (beam {a.beam}, "
        f"budget {a.budget})")
    ev = evaluate(sic, gamma, tgts, pred, a.budget)

    out(f"\n[5] Results")
    out(f"    brute force solved : {ev['bf_solved']}/{ev['n_targets']}  "
        f"({ev['bf_solve_rate']:.1%})")
    out(f"    Predator_1 solved  : {ev['pr_solved']}/{ev['n_targets']}  "
        f"({ev['pr_solve_rate']:.1%})")
    out(f"    jointly solved     : {ev['n_jointly_solved']}")
    if ev["effort_ratio_mean"] is not None:
        out(f"    -- expansions (hardware independent) --")
        out(f"    effort ratio       : mean {ev['effort_ratio_mean']:.4f}   "
            f"median {ev['effort_ratio_median']:.4f}   (lower is better)")
        out(f"    speedup vs brute   : {ev['speedup_mean']:.2f}x")
        out(f"    -- wall clock (what a user actually waits) --")
        out(f"    seconds            : brute {ev['bf_seconds']:.3f}   "
            f"predator {ev['pr_seconds']:.3f}")
        out(f"    time speedup       : {ev['time_speedup']:.2f}x"
            + ("   <-- SLOWER despite fewer expansions"
               if ev['time_speedup'] < 1 else ""))
        out(f"    cost per expansion : brute {ev['us_per_expansion_bf']:.0f}us   "
            f"predator {ev['us_per_expansion_pr']:.0f}us   "
            f"({ev['us_per_expansion_pr']/max(ev['us_per_expansion_bf'],1e-9):.0f}x overhead)")
    out(f"    depth-floor breaches: {ev['depth_floor_breaches']}  "
        f"(must be 0; anything else is a bug)")

    out("\n" + "=" * 74)
    if run:
        json.dump(pred.to_dict(), open(run.path("predator_1.json"), "w"), indent=2)
        run.write_manifest(a)
        run.write_graph(g)
        run.close(dict(split=dict(p=a.train_frac, train=len(train), test=len(test)),
                       training=info, evaluation=ev, predator=pred.to_dict()))
        out(f"artifacts written to {run.dir}/")
        for f in sorted(os.listdir(run.dir)): out(f"    {f}")


if __name__ == "__main__":
    main()
