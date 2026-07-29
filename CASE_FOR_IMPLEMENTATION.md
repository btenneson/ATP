# The case for implementing *Depths of a Simulation* v45

References are to the labels in `Depths of a Simulation 45.tex`.

---

## 1. The paper already asks for this

`thm:pythonatp` is an **existence theorem**:

> Let `Y ⊆ y` be finite and effectively coded... If the direct-consequence
> relation of `F` restricted to `Y` is decidable, then there exists a concrete
> breadth-first Python procedure that halts with success if and only if
> `Γ ⊢_F φ` inside `Y`.

The proof is a construction sketch — represent states as sets of codes,
enumerate premise tuples, compute the next layer. The accompanying remark says
the paper "abstracts away from low-level programming detail."

`predator5.py`'s `sweep()` is that procedure, for `F` = condensed detachment and
`Y` = formulas under a size bound. `admissible()` decides direct consequence;
`sweep()` iterates `D_F`; the layers are `C(Γ,m)`.

So the first argument is not that implementation would be nice. **The paper
asserts a witness exists and the implementation is that witness.** An existence
theorem with an exhibited witness is in better shape than one without.

---

## 2. The theory made predictions; they were tested

| Paper result | Prediction | Measured |
|---|---|---|
| `thm:branchcovering` + proof-covering | a policy that *discards* loses the covering hypothesis | every discarding strategy lost to unguided BFS on **both** time and solve rate |
| `thm:branchsoundness` | `p_m ⊆ Con_F(Γ) ∩ Y` | `metamath.py verify`: 47,572/47,572 |
| `thm:proofhorizon` (2) | first halting stage is exactly `‖φ‖_F(Γ)` | BFS layer index used as the label source; a budget below the horizon yields silence regardless of policy |
| `thm:compilation` | citing derived rules collapses `τ` | measured as *compilation events* in Metamath mode, where a proof cites earlier theorems |

The first row deserves emphasis. Proof-covering (line 1748) requires a branch
shadowing every finite proof. Reordering `Σ(p,m)` preserves that, since a branch
depends on which extensions are *present*, not their order. Truncating does not.

The measurement went further than the theorem. Beam search expanded **more**
nodes than plain breadth-first search (114.5 vs 90.0), solved 70% against 100%,
and ran **6.6× slower** in wall clock. The theory predicted a forfeited
guarantee; there was no compensating speed at all.

---

## 3. The sharpest finding: two orthogonal speedup axes

This is the contribution most worth folding back into the paper.

The paper's speedup metric is the **transaction count**

```
τ_M(Γ,φ) = min{ m : φ ∈ C(Γ,m) }
```

which counts *stage advances*. For the canonical SIC each stage adjoins **every**
direct consequence at once, so `τ` is a count of breadth layers, and by
`thm:proofhorizon` the canonical machine has `τ = ‖φ‖_F(Γ)`.

`thm:compilation` reduces `τ` — derived rules collapse a finite workload to
`τ ≤ 2`. `thm:asympspeedup` compares families along the same axis.

**But Predator_5 does not reduce `τ` at all.** Reordering `Σ` cannot: the proof
found sits at the same depth, and the corollary to `thm:branchcovering` says
nothing can beat `‖φ‖_F(Γ)`. What it reduces is the **work performed inside a
stage** — how many states are materialised before the target appears.

So there are two axes, and the paper formalises one:

| axis | quantity | reduced by | paper coverage |
|---|---|---|---|
| **stages** | `τ = ‖φ‖` | derived rules, lemma caching | `thm:compilation`, `thm:asympspeedup` |
| **work per stage** | expansions, seconds | reordering `Σ` | **not formalised** |

The remark following `cor:tagtransactions` says real speedup must come from
"adding derived rules, changing the search policy, mining a proof for explicit
data, or otherwise changing the proof-search structure." The measurements say
which of those work and by how much:

- **derived rules** → `τ` falls to ≤ 2 (theorem, and observed in set.mm)
- **reordering the policy** → work per stage falls 2.14×, wall clock 1.76×
- **discarding within the policy** → nothing; strictly worse than BFS

A second transaction-like quantity — call it the *materialisation count* — would
give the framework a home for the second axis.

---

## 4. Implementation produced two results the paper does not contain

### The break-even rule

Proof-covering says which policies are **sound**. Nothing in v45 says which are
**worth running**. Measurement supplied it:

```
σ = E_BFS / E_π      node speedup
ω = c_π / c_BFS      per-node overhead
                     π is faster in real time  iff  σ > ω
```

Predator_1: σ = 18.1, ω = 41 → **2.5× slower**. Predator_5: σ = 2.14, ω = 1.2 →
**1.76× faster**. The smaller node advantage won, because the domains differ:
Predator_1 searched a precomputed graph (21 µs/node, scoring dominates),
Predator_5 generates extensions on demand (1083 µs/node, visiting dominates).

Which yields a statement in the paper's own idiom:

> A precomputed graph makes nodes cheap — but a precomputed graph means the
> proofs are already known. Generating `D_F` on demand makes nodes expensive and
> is what genuine search costs. The regimes are not freely choosable.

### The unit problem in ‖φ‖

`‖φ‖_F(Γ)` counts proof *lines*. In set.mm, **95% of lines are formula
construction, not inference** — median raw length 183, median logical length 12,
a 21.4× factor.

So `‖φ‖` over a Metamath corpus is largely counting notation, and every
downstream quantity inherits it: the proof horizon, `τ`, the closure-depth
comparison, the breadth ratio. Either `y` should be taken to exclude syntax
constructors, or `‖·‖` needs a logical-lines variant. This is a correction to a
central definition, and it was invisible until someone counted.

---

## 5. The framework earns its keep on failures

- Beam search losing — **predicted**: it discards, so `thm:branchcovering` does
  not apply.
- Expert iteration adding nothing on the fragment — **predicted**: breadth-first
  prices every target there, so certified labels are already optimal.
- Predator_7 failing on `prcom` — **predicted**: `3eqtr4i`'s conclusion drops
  variables its hypotheses use, so no admissible extension is determined by
  matching.

Without the framework, three unrelated disappointments. With it, three instances
of one distinction — what a policy may discard — each diagnosable before the run.

---

## 6. Coverage

| v45 | Implementation | Status |
|---|---|---|
| `F = (x,y,z)`, `D_F` | `admissible()` | done |
| `C(Γ,m)`, stages | `sweep()` layers | done |
| `E_{F,Y}` canonical enumeration | BFS sweep | done |
| `E_{F,Y,φ}` canonical target search | `guided_search(λ=0)` | done |
| `Σ(p,m)` policy | `Policy.order()` | done |
| proof-covering | `mode='reorder'` vs `'prune'` | done, **and measured** |
| `thm:branchsoundness` | `metamath.py verify` | done, 47,572/47,572 |
| `thm:branchcovering` | guarantee column per row | done |
| `thm:proofhorizon` | BFS layer = `‖φ‖` | done |
| `thm:pythonatp` | `sweep()` **is the witness** | done |
| `τ_M(Γ,φ)` | not separately reported | **gap** |
| `thm:compilation` | compilation events, Metamath mode | partial |
| `thm:asympspeedup` | not attempted | open |
| **σ > ω break-even** | `arena.py` | **new** |
| **syntax/logic split** | `metamath.py stats --logical` | **new** |

---

## The case, once

1. `thm:pythonatp` asserts a Python witness exists; the implementation **is**
   that witness, for a real formal system.
2. Four results were tested. One held more strongly than stated.
3. Two findings emerged that v45 does not contain, and one of them corrects the
   units of `‖φ‖` — a central definition.
4. The measurements identify **a second speedup axis** the paper does not
   formalise: `τ` counts stages and is lowered by derived rules; work-per-stage
   is lowered by reordering `Σ`. They are independent, and only the first has a
   theorem.
5. Three separate failures collapse into one predicted distinction.

The remaining work is not "write code." It is to add the materialisation count
alongside `τ`, state the break-even condition as a proposition, and fix the
units of `‖·‖` — three additions the implementation has already argued for.
