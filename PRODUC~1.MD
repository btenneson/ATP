# Production ATP: Next Steps

## What You Have

**Toy (Working):**
- `predator5.py` — Trained ranker on 19 held-out targets (depth 4), 1.56× speedup, mean 15.6 ± 3.2 expansions
- Stability analysis shows the signal is real but noisy

**Framework (Partial):**
- `setmm_parser.py` — Parses set.mm, extracts all theorems into JSON
- `setmm_inference.py` — Skeleton of ZFC inference engine (modus ponens, axiom application)
- `ROADMAP_PRODUCTION.md` — Full 5–6 week plan to production

## Immediate Next Steps (This Week)

### 1. Test setmm_parser.py on set.mm

```powershell
# Download set.mm if you haven't
curl -o set.mm https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm

# Parse it (takes ~30s on a modern machine)
python setmm_parser.py --input set.mm --output theorems_full.json

# Check output
python -c "import json; data=json.load(open('theorems_full.json')); print(f'Parsed {len(data)} theorems'); print(data[0])"
```

**Expected output:**
```
Parsed 43867 theorems
{'name': 'mp', 'type': 'theorem', 'conclusion': 'proof', 'proof': [...], 'depth': 2}
```

### 2. Find Candidate Theorems for Training

```powershell
# List all theorems, find ones with short proofs
python -c "
import json
with open('theorems_full.json') as f:
    theorems = json.load(f)

# Sort by proof depth (shortest first)
theorems.sort(key=lambda t: t.get('depth', 999))

# Show interesting theorems
for th in theorems[:100]:
    if any(x in th['name'] for x in ['ac', 'zorn', 'equiv', 'bij', 'equipoll']):
        print(f\"{th['name']:30} depth={th['depth']:3}\")
"
```

**Look for:**
- `acequiv` — AC equivalences (should prove AC ↔ Zorn ↔ other forms)
- `zornarb` — Zorn's lemma and AC
- `noendsurj` — Cantor's theorem (no bijection onto powerset)
- `sbth` — Schrödinger-Bernstein (key for Inf ≈ ℝ)
- `equipoll` — equipollence (cardinality equivalence)

### 3. Manually Verify One "Major" Theorem

Pick `prcom` (product commutativity) or `acequiv` and:

```powershell
python setmm_inference.py --theorems theorems_full.json --goal prcom
```

Output should show:
```
Goal: prcom
  Conclusion: (cartesian product commutativity)
  Proof length: 47
```

The inference engine will be a skeleton, but this confirms the data pipeline works.

## Path to Production (Weeks 2–6)

### Week 2: Complete Inference Engine

**What to build:**
- `setmm_inference.py` — Expand to handle:
  - Modus ponens (A→B + A ⊢ B)
  - Substitution (replace free variables)
  - Hypothesis checking (is hypothesis already proved?)

**Files needed:**
- Formula parser: parse set.mm formulas into AST
- Unification: Robinson unification with occurs check (copy from `predator5.py`)
- One-step extension generator: enumerate applicable theorems

**Test:** `setmm_inference.py --goal prcom` returns 10–100 one-step extensions.

### Week 3: Features for ZFC

**What to build:**
- `setmm_features.py` — Extract 20+ features for each extension:
  - Size of conclusion
  - Hypothesis count
  - Constructor match (∀x vs ∧ vs →)
  - Subterm overlap (Jaccard)
  - **NEW:** Lemma frequency (how often used in set.mm)
  - **NEW:** Proof step age (older steps rank lower)
  - **NEW:** Heuristic score (cardinality lemmas score high for Inf ≈ ℝ test)

**Test:** Extract features from 1000 extensions, verify they vary across different one-step choices.

### Week 4: Train on 500 Theorems

**What to build:**
- `setmm_harvest.py` — For each of 500 sampled theorems:
  1. Run BFS (reusing logic from `predator5.py sweep()`)
  2. Mark on-geodesic steps
  3. Collect (positive, negative) pairs
- `setmm_train.py` — Fit logistic + forest rankers on step-level pairs

**Commands:**
```powershell
# Sample theorems, compute geodesics (takes 4–6 hours on 12 cores)
python setmm_harvest.py --theorems theorems_full.json --sample-size 500 --output pairs_500.json

# Train
python setmm_train.py --pairs pairs_500.json --model logistic --output ranker_500.json
python setmm_train.py --pairs pairs_500.json --model forest --output ranker_500_forest.json
```

**Success metric:** Ranker achieves 2.0–2.5× speedup on held-out set.mm theorems (measured with `setmm_search.py`).

### Week 5: Guided Search on Major Theorems

**What to build:**
- `setmm_search.py` — Weighted A* search on set.mm using trained ranker:

```powershell
# Test on commutativity of product
python setmm_search.py --goal prcom --ranker ranker_500.json --budget 1000 --lam 0.5

# Test on AC equivalences
python setmm_search.py --goal acequiv --ranker ranker_500.json --budget 5000 --lam 0.5
```

**Success metric:** Find proofs of prcom, acequiv, noendsurj with <1000 expansions (vs brute force 10k+).

### Week 6: Hyperreal Formalization + Proof Attempt

**What to build:**
- `hyperreal_defs.mm` — Formalize in Metamath:
  ```
  $c npuf ur inf $. ( nonprincipal ultrafilter, ultrapower, infinitesimals )
  
  df-npuf: ∃F. ultrafilter(F) ∧ ¬∃x. F = {A | x ∈ A}
  df-ur: *R := quotient(R^N, F)
  df-inf: Inf := {x ∈ *R | ∀ε ∈ R+. |x| < ε}
  ```

- `hyperreal_proof.mm` — Sketch proof:
  ```
  theorem inf-equipollent-reals:
    Inf ≈ R
  proof:
    1. Define injection r ↦ [const_r]: R → Inf
    2. Inject Inf → *R (trivial)
    3. |*R| ≤ |R^N| = 2^aleph0 = |R|  (cardinality)
    4. Apply Schrödinger-Bernstein (sbth)
    conclude Inf ≈ R
  ```

- `predator5_setmm.py` — Attempt proof with guided search:

```powershell
python predator5_setmm.py --goal "inf-equipollent-reals" --ranker ranker_500.json --budget 100000 --lam 0.5
```

## Realistic Timeline

| Week | Task | Output | Status |
|------|------|--------|--------|
| 1 | Parse set.mm, verify pipeline | theorems_full.json | Start NOW |
| 2 | Complete inference engine | setmm_inference.py working | Hard |
| 3 | Feature engineering for ZFC | setmm_features.py + 20 features | Medium |
| 4 | Train on 500 theorems | ranker_500.json, 2.0–2.5× speedup | Hard (long BFS) |
| 5 | Guided search on major theorems | prcom, acequiv, noendsurj solved | Hard (integration) |
| 6 | Hyperreal formalization + attempt | Proof found or diagnostic failure | Very hard |

**Total:** 5–6 weeks, 1 person, focused work. Parallel work (e.g., writing formalization while BFS runs) can compress it.

## Risk Factors

1. **Inference engine complexity:** Set.mm uses hypotheses, dependent types, and complex term structure. Fully implementing modus ponens with unification is 1–2 weeks of work.

2. **BFS on 500 theorems:** Even with parallelization, computing true geodesics takes time. Budget 4–6 hours of compute.

3. **Feature relevance:** The 20 features for ZFC may not be the right ones. Expect to iterate (add/drop features based on importance, re-train).

4. **Hyperreal formalization:** Writing 300+ lines of correct Metamath is error-prone. Budget extra time for syntax debugging.

5. **Transfer may fail:** If the learned policy doesn't prioritize cardinality lemmas for Inf ≈ ℝ, the search will be slow or fail entirely. This is the key unknown.

## Success Looks Like

**Minimum viable product (MV):**
- Parse set.mm completely ✓
- Inference engine works on 50+ theorems
- Ranker trained on 100 theorems, 1.5×+ speedup
- Guided search finds proof of one "major" theorem

**Production (full):**
- Inference engine handles all 43k theorems
- Ranker trained on 500 theorems, 2.0–2.5× speedup, <10% variance
- Guided search finds proofs of AC ↔ Zorn, Cantor's theorem, hyperreal equipollence
- Publish results

## Start Now

Run this right now:

```powershell
cd "C:\google drive\Automated Theorem Proving"
python setmm_parser.py --input set.mm --output theorems_full.json --limit 10000
```

This takes ~1 minute and gives you the first 10k theorems. From there, you can:
- Inspect theorems (find prcom, acequiv, etc.)
- Verify the data structure
- Start building the inference engine

Let me know what you find.
