#!/usr/bin/env python3
"""
Predator_5 Transfer: testing a condensed-detachment policy on set.mm theorems.

The ranker is trained on the CD fragment. To transfer, we must:

  1. Reframe features to work on ANY set.mm formula, not just implicational ones
  2. Load set.mm and extract a corpus of theorems
  3. For each theorem, score its proof steps using the learned ranker
  4. Measure: does the policy rank on-geodesic steps higher than off-geodesic?

SYMBOL-AGNOSTIC FEATURES
------------------------
The CD fragment features are:
  - size (just tree depth * 2 - 1; works everywhere)
  - variable counts (works everywhere)
  - subterm overlap (works everywhere; Jaccard)
  - "top-shape matches target" (A->B vs C->D; needs generalization)

For set.mm formulas:
  - "top-shape" becomes "head constructor matches":
    If target is (∃x. φ), score edges concluding (∃y. ψ) higher
    If target is (A ∈ B), score edges concluding (C ∈ D) higher
    If target is (A ∧ B), score edges concluding (C ∧ D) higher
  - Same logic for ∀, →, ∨, ¬, class operators, etc.

PROOF LABELS: THE HARD PART
----------------------------
set.mm proofs are WRITTEN PROOFS: human-authored step sequences that are upper
bounds on the shortest proof. We CANNOT run BFS on set.mm to get true geodesics
because enumeration doesn't terminate.

Workaround: use the WRITTEN PROOF as the only available ground truth. Mark
steps that appear in the proof as "on-geodesic" (they are on A geodesic, though
not necessarily THE shortest). Mark steps that DON'T appear as "off-geodesic."

This is noisier than computed labels (some off-geodesic steps are actually on
an equally short path), but it's the only signal available.

COMMANDS
    python predator5_transfer.py load-set-mm   parse set.mm, extract theorems
    python predator5_transfer.py label-proofs  mark steps on written proofs
    python predator5_transfer.py test          score held-out theorems
"""

import argparse, gzip, json, math, os, re, sys, time
from collections import defaultdict

# ===========================================================================
#  Working directory
# ===========================================================================
WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)

# ===========================================================================
#  set.mm parsing:  minimal, just enough to extract theorems
# ===========================================================================

class Tok:
    """A token from a Metamath file."""
    def __init__(self, val, kind):
        self.val = val
        self.kind = kind  # 'word', 'symbol'
    def __repr__(self):
        return self.val

def tokenize_setmm(text):
    """Minimal Metamath tokenizer: just split on whitespace and braces."""
    tokens = []
    i = 0
    while i < len(text):
        if text[i] in ' \t\n\r': i += 1
        elif text[i] in '{}': tokens.append(Tok(text[i], 'brace')); i += 1
        elif text[i] == '$':
            j = i + 1
            while j < len(text) and text[j] not in ' \t\n\r{}': j += 1
            tokens.append(Tok(text[i:j], 'command')); i = j
        elif text[i] == '(':
            tokens.append(Tok('(', 'paren')); i += 1
        elif text[i] == ')':
            tokens.append(Tok(')', 'paren')); i += 1
        else:
            j = i
            while j < len(text) and text[j] not in ' \t\n\r{}()$': j += 1
            tokens.append(Tok(text[i:j], 'word')); i = j
    return tokens

def parse_setmm(tokens):
    """Extract all $a assertions and their proofs from a token stream.

    Returns list of dicts: {name, hypothesis, concl, proof_labels}
    proof_labels[step_idx] = 1 if step appears in proof, 0 otherwise.
    """
    theorems = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.val == '$a':
            # Assertion: $a <hyp>* <concl> $.
            i += 1
            hyps = []
            while i < len(tokens) and tokens[i].val != '$.':
                hyps.append(tokens[i].val)
                i += 1
            concl = hyps[-1] if hyps else None
            hyps = hyps[:-1] if hyps else []
            i += 1  # skip $.
            theorems.append({'name': None, 'hyp': hyps, 'concl': concl,
                            'proof': []})
        elif t.val == '$p':
            # Proof: $p <name> <concl> $= <proof-labels> $;
            i += 1
            name = tokens[i].val if i < len(tokens) else None
            i += 1
            concl_list = []
            while i < len(tokens) and tokens[i].val != '$=':
                concl_list.append(tokens[i].val)
                i += 1
            i += 1  # skip $=
            proof = []
            while i < len(tokens) and tokens[i].val != '$;':
                if tokens[i].val not in '()':
                    proof.append(tokens[i].val)
                i += 1
            i += 1  # skip $;
            if theorems:
                theorems[-1]['name'] = name
                theorems[-1]['proof'] = proof
        else:
            i += 1
    return theorems

def load_setmm(path, limit=None):
    """Load set.mm and return theorems with named proofs."""
    if not os.path.exists(path):
        print(f"set.mm not found at {path}")
        return []

    print(f"  loading {path}...")
    t0 = time.time()

    if path.endswith('.gz'):
        with gzip.open(path, 'rt') as f:
            text = f.read()
    else:
        with open(path) as f:
            text = f.read()

    tokens = tokenize_setmm(text)
    theorems = parse_setmm(tokens)

    # Keep only named theorems with proofs
    named = [th for th in theorems
             if th.get('name') and th.get('proof')]

    if limit:
        named = named[:limit]

    elapsed = time.time() - t0
    print(f"    {len(named)} theorems with proofs in {elapsed:.1f}s")
    return named

# ===========================================================================
#  Symbol-agnostic features for set.mm formulas
# ===========================================================================

def head_constructor(formula_tokens):
    """Extract the top-level constructor of a formula.

    E.g. "( A e. B )" -> "e."
         "( A -> B )" -> "->"
         "A" -> None (atom)
    """
    if not isinstance(formula_tokens, (list, tuple)):
        return None
    if len(formula_tokens) == 0:
        return None
    if formula_tokens[0] != '(':
        return None
    if len(formula_tokens) < 2:
        return None
    # Return second token (first infix operator or prefix)
    return formula_tokens[1] if len(formula_tokens) > 1 else None

def formula_size(formula_tokens):
    """Count tokens (a rough proxy for formula complexity)."""
    if isinstance(formula_tokens, str):
        return 1
    return sum(formula_size(t) for t in formula_tokens) if isinstance(formula_tokens, list) else 1

def formula_vars(formula_tokens):
    """Extract variable tokens (lowercase, typically)."""
    if isinstance(formula_tokens, str):
        # Heuristic: single lowercase letter is a variable
        return {formula_tokens} if len(formula_tokens) == 1 and formula_tokens.islower() else set()
    vars_set = set()
    if isinstance(formula_tokens, list):
        for t in formula_tokens:
            vars_set.update(formula_vars(t))
    return vars_set

def formula_subterms(formula_tokens):
    """Extract subformulas for Jaccard overlap."""
    subs = set()
    if isinstance(formula_tokens, str):
        subs.add(formula_tokens)
    elif isinstance(formula_tokens, list):
        subs.add(tuple(formula_tokens))
        for t in formula_tokens:
            subs.update(formula_subterms(t))
    return subs

def feature_vec_setmm(formula_toks, target_toks):
    """Extract features from a formula for transfer learning.

    Inputs are token lists representing set.mm formulas.
    Returns a vector compatible with the CD ranker (12 features).
    """
    fsize = formula_size(formula_toks)
    tsize = formula_size(target_toks)

    fvars = formula_vars(formula_toks)
    tvars = formula_vars(target_toks)

    fsubs = formula_subterms(formula_toks)
    tsubs = formula_subterms(target_toks)
    jaccard = len(fsubs & tsubs) / max(len(fsubs | tsubs), 1)

    head_match = 1.0 if head_constructor(formula_toks) == head_constructor(target_toks) else 0.0

    # 12 features (matching CD ranker):
    # Placeholder: for now, just minimal versions
    return [
        fsize / 10.0,           # concl size
        1.0,                    # concl size / max in state (unknown)
        len(fvars - tvars) / max(len(fvars), 1),  # novel-var ratio
        fsize / 10.0,           # major size (unknown)
        fsize / 10.0,           # minor size (unknown)
        0.0,                    # major in Gamma (unknown)
        0.0,                    # minor in Gamma (unknown)
        1.0,                    # unifier growth (unknown)
        1.0,                    # state size (unknown)
        head_match,             # top-shape matches
        jaccard,                # subterm overlap
        len(fvars) / 5.0,       # var count
    ]

# ===========================================================================
#  Main commands
# ===========================================================================

def cmd_load_setmm():
    """Load set.mm and save theorem corpus."""
    path = "set.mm"
    if not os.path.exists(path):
        print(f"ERROR: {path} not found in {os.getcwd()}")
        print("Download from https://github.com/metamath/set.mm/blob/develop/set.mm")
        return

    theorems = load_setmm(path, limit=1000)  # First 1000

    # Save as JSON
    out_path = "theorems_setmm.json"
    with open(out_path, 'w') as f:
        json.dump(theorems, f, indent=2)
    print(f"  saved {len(theorems)} theorems to {out_path}")

def cmd_label_proofs():
    """Mark steps in proofs as on- or off-geodesic."""
    path = "theorems_setmm.json"
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run 'load-set-mm' first.")
        return

    with open(path) as f:
        theorems = json.load(f)

    for th in theorems:
        proof = th.get('proof', [])
        # For now: a step is "on-geodesic" if it appears in the proof
        # In reality, we'd need to validate that proofs only reference
        # earlier steps, not future ones.
        th['on_geodesic'] = {str(i): 1 for i in range(len(proof))}

    with open(path, 'w') as f:
        json.dump(theorems, f, indent=2)
    print(f"  labelled {len(theorems)} proofs")

def cmd_test():
    """Test the ranker on held-out set.mm theorems.

    For now, this is a stub: it loads the theorems and prints statistics.
    Once we train a ranker, this will score each conclusion and measure
    whether on-geodesic steps rank higher than off-geodesic.
    """
    path = "theorems_setmm.json"
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run 'load-set-mm' first.")
        return

    with open(path) as f:
        theorems = json.load(f)

    print(f"\n  {len(theorems)} theorems loaded")
    print(f"  proof lengths: {[len(th.get('proof', [])) for th in theorems[:10]]}")
    print(f"  first theorem: {theorems[0].get('name')}")
    print(f"    conclusion: {' '.join(theorems[0].get('concl', []))}")
    print(f"    proof steps: {len(theorems[0].get('proof', []))}")

    # Once ranker exists:
    #   for each theorem:
    #     for each step in proof:
    #       score the step using the ranker
    #     measure: fraction of top-10 steps that are on-geodesic

def main():
    ap = argparse.ArgumentParser(prog="predator5_transfer",
                                 description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("load-set-mm", help="Load and parse set.mm")
    sub.add_parser("label-proofs", help="Mark on/off-geodesic steps")
    sub.add_parser("test", help="Test ranker on held-out theorems")

    args = ap.parse_args()
    if args.cmd == "load-set-mm": cmd_load_setmm()
    elif args.cmd == "label-proofs": cmd_label_proofs()
    elif args.cmd == "test": cmd_test()
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
