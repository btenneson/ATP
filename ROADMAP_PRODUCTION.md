# From Toy to Production: Predator_5 on ZFC

## Goal

Train a learned proof-search policy on set.mm's 43k theorems, prove it works on major theorems (AC ↔ Zorn's Lemma), then attempt the hyperreal theorem.

## Three Phases

### Phase 1: Integrate with set.mm (1–2 weeks)

**Problem:** Current Predator_5 works on condensed detachment (287 states). set.mm has 43,900 theorems and uses ZFC inference (modus ponens + substitution, not just detachment).

**Solution:** Build a Metamath inference engine that:
1. Parses set.mm's full theorem corpus
2. For a given goal, enumerates ONE-STEP EXTENSIONS (like admissible(state) but for ZFC)
3. Extracts features from each extension
4. Scores with the learned ranker
5. Runs weighted A* search

**What to build:**
- `setmm_parser.py` — Parse set.mm completely (names, hypotheses, proofs)
- `setmm_inference.py` — One-step extension engine (modus ponens + unification on set.mm)
- `setmm_features.py` — Extract 12+ features from each proof step in ZFC context
- `setmm_search.py` — Guided search on set.mm (weighted A* with learned ranker)

**Test target:** Prove a known theorem like `noendsurj` (Cantor's theorem) or `prcom` (commutativity of products) with speedup measured against unguided search.

**Success metric:** Search finds proof in <1000 expansions (vs brute force 10k+).

---

### Phase 2: Train on Major Theorems (2–3 weeks)

**Problem:** Training on 63 CD-fragment targets is tiny. set.mm has 43k theorems, but computing geodesics requires BFS on each, which is expensive for large theorems.

**Solution:** Stratified sampling:
1. Sample ~500 theorems uniformly from set.mm
2. For each, run BFS up to depth 20 (compute true shortest proofs for tractable ones)
3. Mark on-geodesic steps for training
4. Train logistic + forest rankers on step-level pairs
5. Cross-validate on held-out theorems

**Theorems to include:**
- Basic set theory: `0ex`, `opeq`, `snex` (existence lemmas)
- Cardinality: `sbth` (Schrödinger-Bernstein), `nnennn` (countability)
- **Major equivalences:** `acequiv` (AC equivalences), `zornarb` (Zorn's lemma and AC), `prcom` (product commutativity)
- Order theory: `wlem` (well-founded recursion)

**Feature engineering:** Expand from 12 to 20+ features:
- Proof step size, hypothesis count
- Constructor match (A→B vs ∀x.φ)
- Subterm overlap (Jaccard on formal terms)
- **NEW:** Graph distance to goal (approximation)
- **NEW:** Lemma age (older lemmas score higher)
- **NEW:** Frequency in proofs (popular lemmas score higher)

**Success metric:** Logistic ranker achieves 2.0–2.5× speedup on held-out theorems, with <10% variance across random seeds.

---

### Phase 3: Hyperreal Formalization + Proof Attempt (3–4 weeks)

**Problem:** The hyperreal theorem (Inf ≈ ℝ) isn't expressible in set.mm yet. No definitions for nonprincipal ultrafilter, ultrapower, or infinitesimals.

**Solution:** Build the formalization:

1. **Define nonprincipal ultrafilter on ℕ** (~50 lines Metamath)
   ```
   df-npuf: ∃F. (ultrafilter F ∧ ¬∃x. F = {A ⊆ ℕ | x ∈ A})
   ```

2. **Define ultrapower ℝ^ℕ/F** (~100 lines)
   ```
   df-ur: *ℝ := {[(f ∈ ℝ^ℕ)] : (f, g) ∈ F ↔ {n | f(n) = g(n)} ∈ F}
   ```

3. **Define infinitesimals** (~30 lines)
   ```
   df-inf: Inf := {x ∈ *ℝ | ∀ε ∈ ℝ+. |x| < ε}
   ```

4. **Prove Inf ≈ ℝ** (~200 lines, structured proof)
   ```
   Lemma: injection ℝ → Inf via r ↦ [(const_r)]
   Lemma: |*ℝ| ≤ |ℝ^ℕ| = |ℝ|^|ℕ| = |ℝ|
   Lemma: |Inf| ≤ |*ℝ| ≤ |ℝ|
   Apply Schrödinger-Bernstein (sbth) → Inf ≈ ℝ
   ```

5. **Attempt with Predator_5:**
   ```powershell
   python predator5_setmm.py --goal "inf-equipollent-reals" --ranker trained_ranker.json --budget 100000
   ```

**Success metric:** Either:
- **(A) Proof found:** Predator_5 guided search discovers a proof within 100k expansions (1–5 min runtime).
- **(B) Proof not found but informative:** Analyze which lemmas ranked high (did it prioritize cardinality arguments?).

---

## Implementation Roadmap

### Week 1: Phase 1 (set.mm Integration)

| Task | File | LOC | Effort |
|------|------|-----|--------|
| Parse set.mm corpus | `setmm_parser.py` | 300 | 1 day |
| Metamath inference engine | `setmm_inference.py` | 500 | 2 days |
| Feature extraction for ZFC | `setmm_features.py` | 200 | 1 day |
| Guided search on set.mm | `setmm_search.py` | 400 | 1.5 days |
| **Test on known theorem** | test script | 100 | 0.5 day |

**Checkpoint:** `python setmm_search.py --goal prcom --ranker old_ranker.json` finds proof.

### Week 2–3: Phase 2 (Training at Scale)

| Task | File | LOC | Effort |
|------|------|-----|--------|
| Theorem sampling & BFS | `setmm_harvest.py` | 400 | 2 days |
| Build training corpus | script | 200 | 1 day |
| Enhanced feature set | `setmm_features.py` (expand) | 200 | 1 day |
| Ranker training | `setmm_train.py` | 300 | 1 day |
| Cross-validation | `setmm_validate.py` | 250 | 1 day |

**Checkpoint:** Trained ranker with 2.0–2.5× speedup on 50 held-out theorems.

### Week 3–4: Phase 3 (Hyperreal)

| Task | File | LOC | Effort |
|------|------|-----|--------|
| Formalize ultrafilter | `hyperreal_defs.mm` | 50 | 1 day |
| Formalize ultrapower | `hyperreal_defs.mm` | 100 | 2 days |
| Formalize infinitesimals | `hyperreal_defs.mm` | 30 | 0.5 day |
| Prove Inf ≈ ℝ (skeleton) | `hyperreal_proof.mm` | 200 | 2 days |
| Integrate with Predator_5 | `predator5_setmm.py` | 300 | 1.5 days |
| **Attempt proof** | — | — | 2 days (search time) |

**Checkpoint:** `python predator5_setmm.py --goal "inf-equipollent-reals"` either finds proof or provides diagnostic output.

---

## Technical Challenges

### 1. Inference Engine Complexity

set.mm uses modus ponens (if `A→B` and `A` are proved, conclude `B`) plus substitution (replace free variables). The one-step extension set is not finite like CD; you must:
- Index all theorems (~43k)
- For each theorem, check if its hypotheses are already proved
- Compute unification carefully (occurs check, variable renaming)
- Cache results

**Solution:** Build incrementally. Start with theorems that have 0–2 hypotheses (easy), then scale to harder ones.

### 2. Training on 500 Theorems

Computing BFS geodesics for 500 theorems is expensive if each takes 30s. But:
- Most theorems have short proofs (<10 steps)
- Run BFS in parallel (Python multiprocessing)
- Cache results

**Solution:** Parallelize `setmm_harvest.py`, expect 4–6 hours total (12 cores).

### 3. Feature Relevance at Scale

The 12 CD features (size, overlap, etc.) are syntactic. At ZFC scale, semantic features matter:
- Is this lemma about cardinality? (→ rank high for Inf ≈ ℝ)
- Is this lemma about functions/bijections? (→ rank high for AC ↔ Zorn)
- Is this an axiom vs derived? (→ axioms rank lower)

**Solution:** Add heuristic features (lemma type, keyword matching). Learn which matter via feature importance.

### 4. Hyperreal Formalization

Defining *ℝ is subtle. The standard ultrapower construction requires:
- Nonprincipal ultrafilter (axiom of choice, nontrivial to formalize)
- Quotient of ℝ^ℕ by the equivalence relation induced by F
- Order and arithmetic on the quotient

**Solution:** Use existing lemmas in set.mm (`df-fil`, `df-ufil`, `ax-ac`). Reference papers on ultrapower construction in formal logic.

---

## Success Criteria

### Phase 1: ✓ If
- Can parse set.mm (all 43k theorems)
- Can extract one-step extensions for a given goal
- Can score steps with learned ranker
- Can find a proof of `prcom` in <1000 expansions

### Phase 2: ✓ If
- Train on 500 theorems (with parallel BFS)
- Logistic ranker beats unguided search by 2.0–2.5×
- Hold-out validation shows <10% variance across random seeds
- Speedup holds on "major" theorems (AC equivalences, cardinality)

### Phase 3: ✓ If
- Hyperreal definitions are formalized and type-check in Metamath
- Skeleton proof of Inf ≈ ℝ can be sketched (may need manual guidance)
- `predator5_setmm.py --goal "inf-equipollent-reals"` either:
  - **(A)** Finds a proof (win)
  - **(B)** Fails but prioritizes lemmas correctly (partial win)
  - **(C)** Fails and ranks randomly (loss, but you learn transfer doesn't work)

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1 | 1 week | Working inference engine on set.mm |
| 2 | 2 weeks | Trained ranker with 2.0×+ speedup |
| 3 | 2–3 weeks | Hyperreal formalization + proof attempt |
| **Total** | **5–6 weeks** | Production ATP on ZFC |

---

## Resources Needed

- **Hardware:** 12-core machine for parallel BFS (you have this)
- **set.mm:** Download once (~20 MB)
- **Metamath tooling:** mmj2 or Ghilbert for syntax checking (free, open-source)
- **Knowledge:** ZFC axioms, ultrapower construction (papers available)

---

## Why This Works

1. **Grounded in theory:** Proof-covering, Branch-Covering Theorem, shortest-path principle all apply to set.mm search.
2. **Learnable signal:** Human-written proofs in set.mm encode heuristics; the ranker learns them.
3. **Clear evaluation:** Major theorems (AC ↔ Zorn) have known short proofs; compare guided vs unguided.
4. **Ambitious but feasible:** 5–6 weeks is realistic for one person with focused work.

---

## Next Step

Start Phase 1: build `setmm_parser.py` to load set.mm and extract theorems with full structure (hypotheses, conclusions, proof labels).
