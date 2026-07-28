#!/usr/bin/env python3
"""
Bridge: load a ranker trained on the CD fragment, apply it to set.mm theorems.

Workflow:
  1. Train on CD fragment: python predator5.py compare --out ranker.json
  2. Parse set.mm: python predator5_transfer.py load-set-mm
  3. Bridge to set.mm: python predator5_bridge.py evaluate --ranker ranker.json

The bridge:
  - Loads the trained ranker (logistic or forest)
  - For each set.mm theorem, extracts the conclusion and proof steps
  - Scores each step using the CD ranker + symbol-agnostic features
  - Measures: do on-geodesic steps rank higher on average?
"""

import argparse, json, math, os, pickle, sys, time
from collections import defaultdict

# ===========================================================================
#  Working directory
# ===========================================================================
WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)

# ===========================================================================
#  Load ranker from JSON
# ===========================================================================

def load_ranker(path):
    """Load a ranker saved by predator5.py compare."""
    if not os.path.exists(path):
        print(f"ERROR: ranker file {path} not found")
        return None

    with open(path) as f:
        data = json.load(f)

    if isinstance(data, dict) and 'results' in data:
        # Full compare output: extract just the logistic ranker
        # (future: allow forest)
        for result in data.get('results', []):
            if result.get('policy') == 'logistic' and result.get('mode') == 'reorder':
                ranker_data = result.get('ranker')
                break
        else:
            print("ERROR: no logistic reorder ranker found in results")
            return None
    else:
        ranker_data = data

    if ranker_data.get('model') != 'logistic':
        print(f"ERROR: expected logistic, got {ranker_data.get('model')}")
        return None

    return {
        'model': 'logistic',
        'weights': ranker_data.get('weights', [])
    }

def score_features(ranker, features):
    """Apply ranker to a feature vector."""
    if ranker is None or ranker['model'] != 'logistic':
        return 0.0
    w = ranker['weights']
    s = sum(f * wf for f, wf in zip(features, w))
    # Logistic sigmoid for interpretability
    return 1.0 / (1.0 + math.exp(-max(-30, min(30, s))))

# ===========================================================================
#  Symbol-agnostic features (copied from predator5_transfer.py)
# ===========================================================================

def head_constructor(formula_tokens):
    if not isinstance(formula_tokens, (list, tuple)):
        return None
    if len(formula_tokens) < 2:
        return None
    if formula_tokens[0] != '(':
        return None
    return formula_tokens[1] if len(formula_tokens) > 1 else None

def formula_size(formula_tokens):
    if isinstance(formula_tokens, str):
        return 1
    return sum(formula_size(t) for t in formula_tokens) if isinstance(formula_tokens, list) else 1

def formula_vars(formula_tokens):
    if isinstance(formula_tokens, str):
        return {formula_tokens} if len(formula_tokens) == 1 and formula_tokens.islower() else set()
    vars_set = set()
    if isinstance(formula_tokens, list):
        for t in formula_tokens:
            vars_set.update(formula_vars(t))
    return vars_set

def formula_subterms(formula_tokens):
    subs = set()
    if isinstance(formula_tokens, str):
        subs.add(formula_tokens)
    elif isinstance(formula_tokens, list):
        subs.add(tuple(formula_tokens))
        for t in formula_tokens:
            subs.update(formula_subterms(t))
    return subs

def feature_vec_setmm(formula_toks, target_toks):
    """Extract 12 features from a formula for the CD ranker."""
    fsize = formula_size(formula_toks)
    tsize = formula_size(target_toks)
    fvars = formula_vars(formula_toks)
    tvars = formula_vars(target_toks)
    fsubs = formula_subterms(formula_toks)
    tsubs = formula_subterms(target_toks)
    jaccard = len(fsubs & tsubs) / max(len(fsubs | tsubs), 1)
    head_match = 1.0 if head_constructor(formula_toks) == head_constructor(target_toks) else 0.0

    return [
        fsize / 10.0,           # concl size
        1.0,                    # concl size / max (unknown for set.mm)
        len(fvars - tvars) / max(len(fvars), 1),
        fsize / 10.0,           # major size (unknown)
        fsize / 10.0,           # minor size (unknown)
        0.0,                    # major in Gamma
        0.0,                    # minor in Gamma
        1.0,                    # unifier growth (unknown)
        1.0,                    # state size (unknown)
        head_match,
        jaccard,
        len(fvars) / 5.0,
    ]

# ===========================================================================
#  Evaluation
# ===========================================================================

def cmd_evaluate(ranker_path, theorems_path, top_k=10):
    """Evaluate ranker on held-out theorems.

    Metric: for each theorem, score all proof steps, measure the rank of
    on-geodesic steps (those in the written proof).
    """
    ranker = load_ranker(ranker_path)
    if ranker is None:
        return

    if not os.path.exists(theorems_path):
        print(f"ERROR: {theorems_path} not found. Run predator5_transfer.py load-set-mm first.")
        return

    with open(theorems_path) as f:
        theorems = json.load(f)

    print(f"\n  evaluating {len(theorems)} theorems")
    print(f"  ranker: {ranker_path}")

    ranks_of_on_geodesic = []
    scores_on = []
    scores_off = []

    for i, th in enumerate(theorems):
        name = th.get('name', f"theorem_{i}")
        concl = th.get('concl', [])
        proof = th.get('proof', [])

        if not proof or not concl:
            continue

        # Score each proof step
        step_scores = []
        for j, step in enumerate(proof):
            # step is a label string; we treat it as a formula token
            fvec = feature_vec_setmm([step], concl)
            score = score_features(ranker, fvec)
            step_scores.append((score, j, j < len(proof)))  # (score, idx, is_on_geodesic)
            if j < len(proof):
                scores_on.append(score)
            else:
                scores_off.append(score)

        # Rank steps by score (higher = better)
        step_scores.sort(key=lambda x: -x[0])

        # Find rank of first on-geodesic step
        for rank, (score, idx, on_geo) in enumerate(step_scores):
            if on_geo:
                ranks_of_on_geodesic.append(rank)
                break

        if (i + 1) % 100 == 0:
            print(f"    {i+1}/{len(theorems)}")

    if ranks_of_on_geodesic:
        mean_rank = sum(ranks_of_on_geodesic) / len(ranks_of_on_geodesic)
        frac_top_k = sum(1 for r in ranks_of_on_geodesic if r < top_k) / len(ranks_of_on_geodesic)
        print(f"\n  TRANSFER RESULTS")
        print(f"    theorems scored: {len(ranks_of_on_geodesic)}")
        print(f"    mean rank of on-geodesic step: {mean_rank:.1f}")
        print(f"    fraction in top {top_k}: {frac_top_k:.1%}")
        if scores_on and scores_off:
            print(f"    mean score (on-geodesic): {sum(scores_on) / len(scores_on):.3f}")
            print(f"    mean score (off-geodesic): {sum(scores_off) / len(scores_off):.3f}")
    else:
        print("  no theorems scored (empty proofs?)")

# ===========================================================================
#  Main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(
        prog="predator5_bridge",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd")

    ev = sub.add_parser("evaluate", help="Score set.mm theorems with trained ranker")
    ev.add_argument("--ranker", default="ranker.json",
                    help="ranker file from predator5.py compare --out")
    ev.add_argument("--theorems", default="theorems_setmm.json",
                    help="theorems file from predator5_transfer.py load-set-mm")
    ev.add_argument("--top-k", type=int, default=10,
                    help="rank threshold for 'in top-k' metric")

    args = ap.parse_args()
    if args.cmd == "evaluate":
        cmd_evaluate(args.ranker, args.theorems, args.top_k)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
