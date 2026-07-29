# Predator 7.1 Documentation and Cross-Branch Reuse Rate Theory

**with efforts toward lower bounds on the settlement length of P vs NP**

Brian Tenneson — July 2026 — **Revision 2**

![Theorem graph: the set of infinitesimals is equipollent to the set of real numbers](fig_theorem_graph_banner.png)

> **Editions.** The PDF carries the same text plus complete source listings for
> the four programs the results depend on (~2,900 lines). Code is referenced
> here rather than inlined, since duplicating it in a repository that already
> contains the `.py` files guarantees the two drift apart.
>
> **Revision 2 corrects nine errors in Revision 1**, three of them structural.
> They are itemised in [§1.4](#14-what-changed-in-revision-2) rather than
> silently repaired.

---

## Abstract

Part I documents Predator_7.1 and its certificate verifier (CV). All 47,572
`set.mm` proofs verify, and the four certificates Predator_7.1 has emitted
verify in full corpus context. It then reports a defect in those four results:
each is a one-step citation of a statement already present in the database under
a different label. The infrastructure is correct; the mathematical content of
the four proofs is zero. A corrected evaluation protocol is given, together with
the measurement that makes the defect a corpus-wide hazard rather than an
accident — **16.8% of `set.mm`'s logical assertions share their statement with
at least one other label.**

Part II introduces the **settlement machine** `M⊗`, which pursues a conjecture
*c* and its negation on alternating stages over a shared lemma store, and the
**cross-branch reuse rate** κ. Three theorems are proved. The first shows κ is a
property of the search policy and not of the theory. The second identifies
cross-branch insertion with the derived-rule construction of the Conservative
Compilation Theorem, so that the branch pursuing the false side of a conjecture
lowers the transaction count of the branch that will halt. The third reduces a
policy-relative speedup to a combinatorial condition on chains, and identifies
precisely the additional hypothesis — a proof-length lower bound — needed to
upgrade it to v45's Abstract Asymptotic Speedup Principle.

Part III observes that the CV is a polynomial-time verifier in the sense of the
definition of NP, making the enterprise reflexive. Four routes to a lower bound
on ‖P≠NP‖ are examined. Three fail, for reasons worth recording. The fourth, the
**definitional floor**, gives a soft but computable bound resting on a checkable
fact: `set.mm` contains no machine model, no time bound, and no complexity
class.

**The unifying observation:** the obstacle to completing Part II and the
obstacle to completing Part III are the same obstacle. Both require lower bounds
on proof length in a strong system, and no technique for obtaining those is
currently known.

---

## 1. Introduction

### 1.1 The question this document is about

An automated theorem prover that searches for a proof of *c* and fails tells you
almost nothing. It may have failed because *c* is false, because *c* is
independent, because the proof is longer than the budget, or because the policy
looked in the wrong place. A prover that searches for *c* and ¬*c* at once — a
**dovetailed** or **settlement** search — at least distinguishes the first case
from the others when the refutation is reachable.

That much is classical. The question taken up here is quantitative and, so far
as I have been able to determine, unasked: when a settlement search runs both
branches over a shared store of proved lemmas, **how often does a lemma proved
while pursuing *c* get used while pursuing ¬*c*?** Call that the cross-branch
reuse rate κ.

The question matters because the answer decides whether dovetailing is a bargain
or a tax. If κ = 0 the two searches are independent, dovetailing costs a factor
of two, and it buys only the ability to detect refutation. If κ > 0 the branch
that will never halt is nonetheless manufacturing lemmas for the branch that
will — and doing so is formally identical to compiling derived rules, which the
Conservative Compilation Theorem shows lowers transaction counts.

### 1.2 Contributions

1. **A working certificate verifier and prover** (Part I), with the trust
   asymmetry explicit: 916 lines are trusted, the rest is not.
2. **A negative result about the prover's demonstrated capability** (§5),
   including the corpus measurement that generalises it and a corrected
   evaluation protocol.
3. **The settlement machine and the reuse rate**, with v45's transaction count
   extended to two-sided targets as the **settlement count** σ.
4. **Three theorems** on κ, each tied to a specific result of v45.
5. **The definitional floor**, a lower bound on proof length that is soft but
   actually computable, where every sharp bound is out of reach.
6. **A unification**: the open problem in Part II and the open problem in
   Part III have the same shape.

### 1.3 Relation to *Depths of a Simulation*

References like `thm:compilation` are to labels in *Depths of a Simulation*
version 45, hereafter **v45**. This document is a companion, not a summary: it
uses v45's definitions unchanged wherever they exist and introduces new ones
only where a needed object is absent. [§17](#17-a-collection-of-objects-discussed-herein)
records, for every object used, whether it originates in v45 or here.

Two conventions of v45 are load-bearing:

- **‖φ‖_F(Γ) is the line count** of a shortest proof, min{|π|}. The
  size-relativised variant ‖φ‖^size sums formula lengths; v45 notes the entire
  apparatus relativises under |π| ↦ size(π).
- **⪯ without adornment means *clocked* simulation.** This matters more than it
  looks; see [§6](#6-the-preorder-on-sics-and-which-one-is-meant).

### 1.4 What changed in Revision 2

Revision 1 contained errors, all found by checking its claims against the text
of v45 and by recomputing from `set.mm`, rather than against memory.

| # | Error | Severity |
|---|---|---|
| a | **The preorder section was wrong.** Asserted every SIC simulates every other and the settlement programme is dead. True of *weak* simulation only; v45's principal relation is *clocked*, which provably does not collapse. Conclusion reversed. | structural |
| b | **Proof-Horizon Theorem attributed to the wrong machine.** Wrote τ = ‖φ‖ for `E_{F,Y}`, which has H ≡ 0 and never halts. The identity holds for `B_{F,Y,φ}`. | structural |
| c | **A qualifier was dropped.** v45 says no target-search SIC *based solely on shortest proof length* beats the horizon. | wording |
| d | **The third theorem did not witness what it claimed.** v45's speedup principle needs a lower bound on *every* proof in F — a proof-complexity statement. Revision 1's hypothesis was about a *policy*. | structural |
| e | **The settlement machine was not a target-search ATP.** v45 requires halting to imply the target is present; a machine halting on ¬c violates it. Fixed by introducing σ and verifying the SIC axioms. | structural |
| f | **κ was claimed to equal 1 where it is merely degenerate.** Availability and use must be distinguished. | math |
| g | **The "unit problem" overstated its novelty.** v45 already has a size-relativised measure. The correct claim concerns a third measure, logical-line count. | attribution |
| h | **Notation collision.** Revision 1 used ρ for the reuse rate; v45 uses ρ for an admissible clock. Now κ. | notation |
| i | **Three numerical errors.** Median raw proof length is **173**, not 183. The figure **21.4** was quoted as a ratio of medians when it is a ratio of aggregates, correct value **21.2**; the ratio of medians is **14.4**. The corpus has **1,441 syntax axioms**, the figure 1,445 being syntax *assertions*. | numbers |
| j | **A mislabelled column.** The certificate table's "Position" reported *line numbers in the file*, not ordinal positions among assertions, while a neighbouring table reported genuine ordinal positions. | numbers |

That three of these were found only by reading v45's actual text, and three more
only by recomputing from `set.mm`, is the argument for the provenance tables in
§17.

---

## 2. Corpus figures

| Quantity | Value |
|---|---:|
| Total assertions (`$a` and `$p`) | 50,572 |
| — Axioms and definitions (`$a`) | 3,000 |
| — — syntax axioms | 1,441 |
| — — logical `$a` (of which `ax-*`: 126; `df-*`: 1,433) | 1,559 |
| — Proved theorems (`$p`) | 47,572 |
| Logical assertions (conclusion begins `\|-`) | 49,127 |
| Syntax assertions (`$a` plus four syntax `$p`) | 1,445 |
| Constants | 1,439 |
| Distinct logical statements | 43,836 |
| Statements carried by more than one label | 2,946 |
| Labels involved in such a duplication | 8,237 |

The count of *true* axioms — the 126 `ax-*` statements — is worth separating
from the 3,000 `$a` total, since 1,441 of those are grammar and 1,433 are
definitions.

---

# Part I — Predator_7.1

## 3. Architecture

| Component | File | Role |
|---|---|---|
| Certificate verifier | `metamath_cv.py` | trusted, small, judges |
| Grammar | `setmm_grammar.py` | untrusted, parses |
| Search | `predator71.py` | untrusted, large, proposes |

This is the De Bruijn criterion: an arbitrarily large and clever searcher, and a
small verifier that does not trust it. The searcher may be wrong, unsound, a
neural network or a random number generator — nothing it reports is believed.
What is believed is the verifier's verdict on the artefact it emits.

**No result in this document depends on the correctness of `predator71.py`.** It
depends on `metamath_cv.py`, which is 916 lines, has a self-test, and reproduces
the accepted status of all 47,572 `set.mm` proofs.

### 3.1 The two-phase split

A Metamath proof is a sequence of labels consumed by a stack machine, and the
overwhelming majority of those labels are not inference — they are *formula
construction*. Over a random sample of 6,000 `set.mm` proofs decompressed by the
CV, the median raw proof length is **173** steps against a median logical length
of **12**, and **95.3%** of all steps executed are formula-building. See
[§15.1](#151-the-unit-problem-in-the-norm) for why the two ratios these figures
support — 14.4 by medians, 21.2 in aggregate — are different numbers.

This is exploitable because a parse tree *is* a Metamath syntax proof. A node
with rule `L` and children `k₁…kₙ` serialises in reverse Polish as
`proof(k1) ... proof(kn) L`. So the 95% of steps that are notation are
*generated* by walking a tree, and only the rest are searched for. The grammar
is extracted from the 1,441 syntax axioms already in the database.

### 3.2 What changed from 7.0: unification

Predator_7.0 searched by **matching**, one-way: the goal is ground and the
assertion's conclusion carries the variables. That works only for *determined*
assertions — every variable in a hypothesis also occurring in the conclusion.

`ax-mp` is not determined. Its conclusion is the bare variable `ps`, so matching
against goal *G* binds `ps := G` and leaves `ph` — the entire antecedent — with
no value. `syl` fails identically. These are the two most-cited logical labels
in `set.mm`.

7.1 uses unification over two namespaces: assertion variables renamed apart at
each use, and metavariables `?1`, `?2`, … standing for not-yet-known subterms.
Applying `ax-mp` to *G* turns `ph` into `?1`, so the second subgoal is
`( ?1 -> G )` — not unconstrained, since its consequent is fixed.

The principle: a free metavariable is harmless provided some later step
determines it. What must never happen is a step required to *invent* a formula
from nothing.

### 3.3 Search control

Three controls, each existing because its absence produced a specific failure.

- **Most-constrained goal first.** Expanding the leftmost open goal makes
  `ax-mp` an infinite regress. `pick_goal` orders goals by (bare metavariable
  last, fewest metavariables, largest term).
- **Indexed hypothesis slots.** Solving goals out of declaration order and
  appending in solution order emits them wrongly. The verifier caught this as
  `hypothesis mismatch at ax-mp`. `Step.subs` is a fixed-length list filled by
  index.
- **Closers before openers.** Ranking a mixed candidate list and truncating to
  fixed width silently discards closers past the cut — which made `prcom` fail
  after one expansion, since `pm2.01` sat past position 48.

## 4. The verification result

### 4.1 The verifier

`metamath_cv.py` verifies all 47,572 proofs, zero failures, ~178 seconds. Two
defects found during development produced *plausible* wrong answers rather than
crashes.

**The `Z` backreference defect.** Compressed proofs mark reusable subproofs with
`Z`. The first implementation appended on every step rather than only at a `Z`,
producing a decoding that was self-consistent and wrong. Caught only by a
cross-encoding test: three encodings of one proof must decode identically. They
gave 34, 34 and 26.

**The disjoint-variable defect.** A proof may introduce *dummy* variables
appearing in no hypothesis and no conclusion. Checking against the mandatory DV
set rather than every pair active in scope rejects five correct proofs: `equid`,
`ax7`, `exgen`, `spnfw`, `spsv`.

Both defects share a shape: neither crashed the verifier; each made it
confidently wrong on a small subset. A verifier right about 47,567 proofs and
wrong about 5 is not 99.99% correct, it is broken.

### 4.2 The certificate container, and the number 47,573

```
$( Predator_7.1 proof of axin1 $)
$[ set.mm $]
chk $p |- ( ( ph -> -. ph ) -> -. ph ) $= wph pm2.01 $.
```

The `$[ set.mm $]` line splices the entire database in, so the verifier reads all
of `set.mm` and then one further statement. Hence `47,573 = 47,572 + 1`. The
certificate is a one-statement extension: it modifies nothing, may cite only
what precedes it, and is checked by a program sharing no code with the search.

| Certificate | Parse (s) | Verify (s) | Result |
|---|---:|---:|---|
| `axin1_p71.mm` | 9.7 | 196.9 | 47,573 verified, 0 failed |
| `falanfal_p71.mm` | 9.1 | 254.2 | 47,573 verified, 0 failed |
| `tbw-ax4_p71.mm` | 11.7 | 195.0 | 47,573 verified, 0 failed |
| `axia1_p71.mm` | 8.9 | 165.8 | 47,573 verified, 0 failed |

> Each run re-verifies 47,572 proofs already known to check in order to check
> one that was not. A `--only` flag would cut each run from ~200 s to the 10 s
> parse. The declining throughput within a run — 11,235/s at position 2,000 down
> to 238/s at 46,000 — is not a defect but a consequence of `set.mm` being
> ordered roughly by difficulty.

## 5. The defect in the four results

### 5.1 What the four proofs actually are

| Target | Position | Cites | Position | Gap |
|---|---:|---|---:|---:|
| `axin1` | 2,720 | `pm2.01` | 189 | 2,531 |
| `falanfal` | 1,603 | `anidm` | 573 | 1,030 |
| `tbw-ax4` | 1,730 | `falim` | 1,584 | 146 |
| `axia1` | 2,717 | `simpl` | 486 | 2,231 |

"Position" means index among the 50,572 assertions in declaration order, which
is the ordering the searcher's cutoff respects. It is **not** the line number in
the file — Revision 1 conflated the two.

| Target statement | Cited statement | Relation |
|---|---|---|
| `\|- ( ( ph -> -. ph ) -> -. ph )` | `\|- ( ( ph -> -. ph ) -> -. ph )` | **identical** |
| `\|- ( ( F. /\ F. ) <-> F. )` | `\|- ( ( ph /\ ph ) <-> ph )` | instance |
| `\|- ( F. -> ph )` | `\|- ( F. -> ph )` | **identical** |
| `\|- ( ( ph /\ ps ) -> ph )` | `\|- ( ( ph /\ ps ) -> ph )` | **identical** |

Three of four are verbatim duplicates; the fourth is a one-variable substitution
instance. Every proof has logical depth 1: find the earlier label that already
says this, cite it. The proofs are valid and the verifier is right to accept
them — but what was discovered is that *the theorem was already in the database
under another name*. That is a lookup, not a proof.

### 5.2 Why the existing safeguard does not catch this

```python
cut = mm.order.index(a.label)
idx = Index(mm, by_tc, upto=cut, ...)
```

The searcher sees only assertions declared strictly before the target. That is
the correct and standard protocol, and it is necessary. **It is not sufficient.**
It excludes the *label*; it does not exclude the *statement*. `set.mm`
re-derives the axioms of several alternative propositional calculi in later
sections — which is why `axin1` at position 2,720 says exactly what `pm2.01`
said at position 189.

### 5.3 How large the hazard is

| | |
|---|---:|
| Logical assertions | 49,127 |
| Distinct logical statements | 43,836 |
| Statements carried by >1 label | 2,946 |
| Labels involved in a duplication | 8,237 |
| **Fraction so involved** | **16.8%** |

Roughly one in six logical assertions shares its exact statement with another
label. An evaluation sampling targets uniformly measures duplicate-lookup on
about a sixth of its sample — and, since duplicates are the easiest targets, on
a far larger share of its *successes*.

### 5.4 A corrected protocol

**Definition (Admissible index).** Let φ be a target at ordinal position *k*.
The index must exclude every label ℓ with position < *k* such that the
conclusion of ℓ is a substitution instance of φ, or φ is a substitution instance
of the conclusion of ℓ, under a renaming of variables.

**Definition (Non-trivial reach).** The number of targets a prover proves under
the admissible index, from a stated sample, within a stated budget.

Excluding only exact duplicates is not enough — `falanfal` would survive that
test — which is why the definition uses substitution instances in both
directions.

> **Current status.** Predator_7.1's non-trivial reach is **not yet measured**,
> and on the evidence the honest prior is that it is small, possibly zero. "Four
> theorems proved" should be read as "four theorems located".

---

# Part II — Cross-branch reuse rate theory

## 6. The preorder on SICs, and which one is meant

Revision 1 argued the settlement-region programme is vacuous, on the ground that
every SIC simulates every other. That argument was wrong.

### 6.1 Weak simulation does collapse

> **Theorem (`thm:weakcollapse`, v45).** Every SIC weakly simulates into every
> other SIC.

The proof takes the witness to be `R := S_M × S_N`, the *total* relation, and
observes the conditions hold because membership is automatic. The theorem is
correct — but it satisfies the definition by making the witness carry no
information. Weak simulation never requires N to track M's states, preserve its
theorems, or match its halting. **It is a degeneracy result about a definition,
not a fact about SICs.**

### 6.2 Clocked simulation does not

v45's principal relation is different, and it is the one written ⪯ unadorned:

> "Because this is the principal simulation relation in the remainder of the
> paper, the unadorned notation M ⪯ N abbreviates M ⪯_clk N."

**Definition (Clocked deterministic simulation, v45).** An *admissible clock* is
a nondecreasing unbounded ρ with ρ(1) = 1. A clocked simulation from M to N is a
pair (f, ρ) with f : S_M → S_N **injective**, ρ admissible, and for all p, m:

```
f(C_M(p,m)) = C_N(f(p), ρ(m))        H_M(p,m) = H_N(f(p), ρ(m))
```

Exact state and halting correspondence up to time rescaling. v45's remark is
explicit that this "repairs timing rigidity, not cardinality rigidity" and that
"lossy many-to-one comparisons remain state abstractions rather than
simulations."

**Proposition (Non-collapse).** There exist SICs M, N with M ⋠_clk N.

*Proof.* `prop:statespacesaturation` gives S_M = 𝒫(Y_M), since the stage-one
axiom C(Γ,1) = Γ makes every subset a state. `prop:cardinalityobstruction` then
observes an injective f : S_M → S_N is an injection 𝒫(Y_M) → 𝒫(Y_N), so in the
finite case |Y_M| ≤ |Y_N|. Injectivity is part of the definition and the clock
plays no role in the argument, so it applies to ⪯_clk verbatim. Take
Y_M = {a,b}, Y_N = {c}, both static and never halting. ∎

**Corollary.** The quotient (SIC/∼, ⪯_clk) is a partial order with more than one
element. So the settlement region U_c is a nontrivial construction, and the
questions of whether U_c has a least element, several minimal elements, or is
generated by an antichain are **open rather than degenerate.**

> **What survives of the criticism.** If `Settles(X,c)` means only that X
> eventually outputs a proof of *c* or ¬*c* by unbounded search from a *fixed*
> theory T, then halting depends on T and *c* alone, and U_c takes only the
> values ∅ and everything. Non-degeneracy of the preorder does not repair that;
> the predicate must additionally be **resource-bounded**. v45 supplies that too:
> its *p*-simulation relation, which it notes "does not collapse universally,
> because polynomial-time computability of h is a genuine restriction once size,
> rather than merely stage number, is being tracked."

> **A caution about five relations.** v45 defines weak, synchronous and clocked
> simulation, invertible recoding, and *p*-simulation. **Only the first
> collapses.** Any statement of the form "the preorder on SICs is X" is
> ambiguous, and Revision 1 fell into exactly that ambiguity.

## 7. Quantities

```
‖φ‖_F(Γ) = min{ |π| : π a proof from Γ with final line φ }
C(Γ,1) = Γ,   C(Γ,m+1) = D_F(C(Γ,m)),   τ_M(Γ,φ) = min{ m : φ ∈ C(Γ,m) }
```

> **Which machine realises the horizon.** v45 distinguishes two canonical
> machines that are easy to conflate, and Revision 1 conflated them.
> `E_{F,Y}` (rule-enumeration) has **H ≡ 0 and never halts**, so τ is not defined
> for it as a target-search count. `B_{F,Y,φ}` (breadth-first target-search) has
> C(Γ,m) = {ψ : ‖ψ‖ ≤ m} and halts exactly when ‖φ‖ ≤ m. The Proof-Horizon
> Theorem is about the latter: `τ_{B_{F,Y,φ}}(Γ,φ) = ‖φ‖_F(Γ)`. The canonical
> *target-search* machine `E_{F,Y,φ}` does halt and has the same stage sets, so
> the identity holds for it too.

> **The qualifier on the lower bound.** v45's corollary reads: "no target-search
> SIC *based solely on shortest proof length* can reach φ earlier than that
> stage." The italicised qualifier is not decoration — a machine given a
> compiled derived rule is not based solely on shortest proof length, which is
> why the Conservative Compilation Theorem is not in conflict with it.

To τ add the **materialisation count** μ, the number of distinct formulas built
before halting. Unlike τ it is bounded below by nothing, and is therefore where
a policy operates.

## 8. The settlement machine

**Definition (Settlement machine).** `M⊗ = (C⊗, H⊗)` maintains branch *A*
pursuing *c* and branch *B* pursuing ¬*c*, each policy-directed. Odd stages
advance *A*, even stages *B*. Both read from and write to a shared **lemma
store** Λ. Set `C⊗(Γ,m) := Λ_m ∪ A_m ∪ B_m`, and `H⊗ = 1` iff *c* or ¬*c* lies
in `C⊗(Γ,m)`, with all three frozen once `H⊗ = 1`.

**Proposition.** `M⊗` satisfies the six conditions of `def:sic`. *(Stage-one:
Λ₁ = ∅ and A₁ = B₁ = Γ. Monotone: stores only grow. Persistent halting: by
monotonicity. Frozen: by stipulation.)*

> **Why a new count is needed.** `M⊗` is **not** a target-search ATP for *c* in
> v45's sense, which requires H = 1 to imply the target is present. If ¬*c* is
> the provable side, `M⊗` halts with *c* ∉ C⊗. Revision 1 applied τ to it
> anyway. The repair is to extend the count, not distort the machine.

**Definition (Settlement count).** `σ_M(Γ,c) := min{ m : c ∈ C(Γ,m) or ¬c ∈ C(Γ,m) }`.

**Proposition.** `σ_M(Γ,c) = min(τ_M(Γ,c), τ_M(Γ,¬c))`, and if Γ is consistent
at most one is finite.

**Definition (Origin, crossing, reuse rate).** Each λ ∈ Λ carries an origin
o(λ) ∈ {A, B}. Say λ is **available-crossed** by stage *m* if it lies in the
candidate set of the other branch at some stage ≤ *m*; **use-crossed** if it
occurs as a premise of a step actually taken by the other branch. The rates
κ^av and κ^us are the corresponding fractions of Λ_m, and κ^us ≤ κ^av.

**Definition (Cross-branch insertion).** When a branch closes a ground lemma λ,
the nullary derived rule d_λ (empty premise tuple, value λ) is adjoined, making
λ available to both branches at unit cost.

## 9. First result: reuse is a property of the policy

**Theorem (Canonical degeneracy).** *Let both branches run the unrestricted
operator D_F with no targeting. Then for every Γ and c:*

1. *A_m = B_m = C(Γ,m) for all m, so the branches are indistinguishable and the
   origin function is not determined by the run;*
2. *under any origin convention, κ^av_m = 1 whenever Λ_m ≠ ∅;*
3. *neither quantity depends on c.*

*Proof.* (i) D_F does not mention a target, so both branches apply the same
operator to the same initial state; induction gives A_m = B_m = C(Γ,m). Anything
entering at stage *m* enters both simultaneously. (ii) Fix a convention and let
λ ∈ Λ_m with o(λ) = A. By (i) λ ∈ B_m, so it lies in B's candidate set and is
available-crossed. (iii) Neither argument mentions *c*; a quantity taking the
same value for every conjecture distinguishes no conjectures. ∎

> **Why availability and not use.** The corresponding claim for κ^us is **false**.
> A lemma may sit in both branches' states and never be a premise of any
> admissible rule instance — in condensed detachment, a formula unifying with no
> antecedent is available forever and used never. Revision 1 asserted κ = 1
> without the distinction.

**Corollary (The two degenerate regimes).** κ^av = 1 is the signature of no
targeting. κ^us = 0 is the signature of total separation: settlement costs a
factor of 2 in σ and buys only refutation detection. Both extremes are
uninformative; the empirical question is where a real policy falls between them.

> **Position in the v45 scheme.** The Proof-Horizon Theorem makes τ
> theory-determined and (subject to the qualifier) policy-invariant. μ is
> complementary: policy-determined, bounded below by nothing. κ joins μ on the
> policy side — both count what the machine *did*, not how deep it had to go.

## 10. Second result: cross-branch reuse is online compilation

**Theorem (Reuse as compilation).** *Let `M⊗` have cross-branch insertion and
`M^sep` be the same machine with the shared store removed. Then:*

1. *F^D is conservative over F;*
2. *σ(M⊗) ≤ σ(M^sep) ≤ 2·min(τ_{M_A}(Γ,c), τ_{M_B}(Γ,¬c));*
3. *writing Δ(c) := σ(M^sep) − σ(M⊗) for the **settlement dividend**, Δ(c) ≥ 0;
   and Δ(c) > 0 only if some lemma is use-crossed, so κ^us = 0 ⟹ Δ(c) = 0.*

*Proof.* (i) Each inserted λ was closed by a branch, so Γ ⊢_F λ, and d_λ is a
derived rule in the sense of v45's conservativity proposition. Nothing depends
on which branch produced λ — soundness is indifferent to intent. (ii) The right
inequality is the cost of alternation. For the left, adjoining a nullary rule
can only enlarge D_F(S), so induction gives C⊗(Γ,m) ⊇ C^sep(Γ,m). (iii) If
Δ(c) > 0 some stage was saved; since the machines differ only in the d_λ, some
d_λ fired in the halting branch, and it is available there only by insertion. ∎

> **The converse fails.** Δ(c) > 0 implies a use-crossed lemma, but not
> conversely: a crossed lemma that shortens nothing contributes nothing. So
> κ^us > 0 is necessary and **not sufficient**. Revision 1 asserted an
> equivalence.

**Corollary (No wasted branch).** If Γ is consistent, at most one of *c*, ¬*c*
is provable, so at least one branch never halts. Nevertheless every lemma it
closes is a theorem of Γ, sound to insert, and available to the other branch.
**The non-halting branch is a lemma generator, and its contribution to the
halting branch is exactly Δ(c).**

> **What this makes of "open-mindedness".** The motivating intuition was
> psychological. The corollary replaces it with an inequality: when Δ(c) > 0 the
> unbiased search is not merely fairer than the biased one, it reaches the
> provable side in **fewer** stages than the machine that separated the
> branches. The refutation attempt pays for itself, in the currency v45 already
> uses. When κ^us = 0 the dividend is zero and settlement is a pure
> factor-of-two loss.

## 11. Third result: chain deficits and speedup

### 11.1 What the speedup principle actually requires

v45's Abstract Asymptotic Speedup Principle has three hypotheses: (1)
τ ≤ p(n) in the augmented system; (2) **every** proof of φₙ from Γₙ **in F** has
length at least q(n); (3) q(n)/p(n) unbounded.

**Hypothesis (2) is a statement about the formal system, not about any policy.**
It is a proof-length lower bound of exactly the kind Part III shows is currently
unobtainable. Revision 1 claimed to witness this principle on the strength of a
hypothesis about a policy, which does not suffice.

**Definition (Chain deficit).** A family (Γₙ, cₙ) with Γₙ ⊢_F cₙ has a chain
deficit (ℓ, g, h) under policy Σ if there are λⁿ₁ … λⁿ_{ℓ(n)} with:

- **(a) Chain, not layer.** λⁿ_k occurs as a premise in *every* derivation of
  λⁿ_{k+1} from Γₙ of length below g(n).
- **(b) Cheap on the refutation side.** Σ pursuing ¬cₙ closes the whole chain
  within O(ℓ(n)) stages.
- **(c) Expensive on the proof side.** Σ pursuing cₙ does not close λⁿ_{ℓ(n)}
  before stage g(n).
- **(d) On the proof.** Some Σ-reachable shortest proof of cₙ cites λⁿ_{ℓ(n)},
  and given it, cₙ follows in h(n) further stages.

**Theorem (Deficit implies policy-relative speedup).**

```
σ⊗(Γₙ,cₙ) = O(ℓ(n) + h(n))        τ^Σ(Γₙ,cₙ) ≥ g(n) + h(n)

τ^Σ / σ⊗  =  Ω( (g(n)+h(n)) / (ℓ(n)+h(n)) )
```

*If ℓ, h = O(n) and g = ω(n) the ratio is unbounded, and the settlement machine
is asymptotically faster than the single-target machine **running the same
policy Σ**.*

> **What would upgrade this to `thm:asympspeedup`.** Condition (c) must become
>
> **(c′)** every F-proof of cₙ from Γₙ has length at least g(n) + h(n),
>
> whereupon v45's hypotheses hold with p(n) = O(ℓ+h) and q(n) = g+h. Condition
> (c′) is a genuine proof-complexity lower bound. On a fragment small enough for
> breadth-first search to terminate — the 287-state condensed-detachment
> fragment of Predator_5 — it can be **computed** for small *n* by exhaustive
> search, since BFS returns the true shortest-proof length. That is the
> practical route, and it does not scale, which is the honest statement of the
> difficulty.

**Corollary (Why the previous family could not separate).** Let D = {d₁…dₙ} be a
*layer*, each dₖ derivable without the others. Condition (a) fails outright, so
g(n) = O(ℓ(n)) and the ratio is Θ(1). This is the structural reason an earlier
attempt produced p(d) = d and q/p → 1. **Superlinear g requires the links to be
premises of one another — which is what makes a chain a chain.**

### 11.2 What a chain looks like, and what a layer looks like

![Lemma graph for |I| = |R|](fig_theorem_graph_plain.jpg)

The distinction is easier to see than to state. Above is the lemma graph of a
worked target from this program: the set of infinitesimals *I* in a nonstandard
extension is equipollent to ℝ, decomposed into seventeen lemmas.

The spine **L1 → L3 → L4 → L11 → L16 → L17** is a *chain* in the sense of
condition (a): each link is a premise of the next, and no link can be skipped.
The strands **L14 → L15** and **L12 → L13**, hanging off L4 and L5, are short
parallel branches — closer to a *layer*, and individually skippable.

Both structures are present, which is what makes the example useful. A
settlement search obtaining L11 from the refutation branch saves the whole
prefix L1, L3, L4 on the proof branch; one obtaining L15 saves one step, because
L14 is independently cheap. **Condition (a) is precisely the demand that the
crossed lemma sit on a spine rather than on a frond**, and g(n) grows
superlinearly only when the spine does.

The graph also supplies a concrete target for non-trivial reach: L17 has depth 6
and seventeen antecedents, none a duplicate of it under the admissible index. It
is an admissible non-trivial target of exactly the kind Part I found missing
from the four verified certificates.

**Conjecture (Chain deficits exist).** There is a recursive family (Γₙ, cₙ) over
the condensed-detachment fragment, Γₙ = {K, S, W} plus *n* auxiliary formulas,
admitting a chain deficit with ℓ(n) = Θ(n), h(n) = O(1), g(n) = Ω(n²) under the
size-ordered policy of Predator_5.

## 12. Measurement protocol

**Problem (the number nobody has).** Measure κ^us for a real policy on a real
corpus.

1. **One index, shared.** Building it costs 8–12 s and dominates short runs.
2. **Two goal stacks**, alternating on expansion.
3. **Cross-branch insertion.** When either branch closes a subgoal the result is
   a ground theorem with no free metavariables; adjoin it to the shared index as
   a new closer. This is online compilation.
4. **Log origins and uses.** κ is then a ratio of counters.

> **A distinction the implementation must respect.** The branches cannot share
> *substitutions* — their metavariable bindings are independent and unifying
> across them would be unsound. What they share is *closed lemmas*. An
> implementation sharing the substitution store will produce proofs the CV
> rejects, and that rejection will be correct.

Test set: any `set.mm` theorem of the form `|- -. phi` supplies a conjecture
whose refutation is known reachable. Targets must be filtered through the
admissible index, or the measurement is contaminated by the duplicate-lookup
effect of Part I.

---

# Part III — Lower bounds on the settlement length of P vs NP

## 13. The certificate verifier is an NP verifier

Not an analogy. NP is *defined* by certificate verification:
`x ∈ L ⟺ ∃w, |w| ≤ p(|x|), V(x,w) = 1`. `metamath_cv.py` is such a V.

**Definition (Verification transcript).** The sequence of stack contents
materialised during verification; T(π) is the total symbols pushed.

**Proposition.** Verification runs in time polynomial in |Σ| + T(π).

> **Why the transcript and not the proof.** Substitution can square a formula's
> size at a single step, so an *n*-step proof can materialise formulas
> exponential in *n*, and verification is not in general polynomial in the proof
> *file* length. For `set.mm` in practice the blowup does not occur — the corpus
> verifies in under 200 s — but a theoretical statement must respect the worst
> case. This is the same distinction v45 draws between ‖φ‖ and ‖φ‖^size.

**Proposition (Bounded provability is in NP).**
`Short-Proof_Σ = { (φ, 1ⁿ) : ∃π, T(π) ≤ n, π proves φ from Σ } ∈ NP`, with π the
certificate and `metamath_cv.py` the verifier.

> **The reflexive turn.** Settling P vs NP inside `set.mm` means exhibiting
> φ ≡ "P ≠ NP" with a certificate a polynomial-time verifier accepts. The CV is
> simultaneously the instrument of the project and an instance of the object
> quantified over in the statement being settled. Any claim about the difficulty
> of producing the certificate is a claim about an NP search problem, and v45's
> `def:automatizable` is the right frame.

> **Computation is proof, and where it stops.** v45's Turing-machine appendix
> takes the one-step function of a deterministic machine as its single inference
> rule, and `prop:reachability` identifies provability with reachability of
> configurations. A run of T is a proof *with proof length equal to the number
> of steps taken plus one*. Hence in F_T, **‖·‖ = running time and τ = time
> complexity.**
>
> It does not yet make NP expressible: the rule set is a single unary rule which
> is a *function*, and the appendix has no nondeterministic analogue. Two
> repairs — make the rule set relational, or go through certificates. The second
> is what the CV already instantiates, and is cheaper.

## 14. Four routes to a lower bound

### 14.1 Counting — fails, instructively

The number of proofs of length ≤ n is at most L^(n+1)/(L−1). With L = 50,572 at
the median raw length 173, that is ~10^821 against 43,836 distinct statements.
No constraint whatever.

The failure is structural: counting shows *most* statements require long proofs;
P ≠ NP is a single statement, and no counting principle can rule out its being
the exception.

### 14.2 The proof horizon — real, but bounds the machine

τ ≥ ‖φ‖ says that whatever ‖P ≠ NP‖ is, no policy *based solely on shortest
proof length* beats it, so no cleverness in Predator converts a long proof into
a short search. It rules out a class of hopes. It takes ‖φ‖ as given and says
nothing about its size.

### 14.3 The barriers — bound content, not length

| Barrier | Source | Excludes |
|---|---|---|
| Relativization | Baker–Gill–Solovay 1975 | proofs holding under all oracles |
| Natural proofs | Razborov–Rudich 1997 | large constructive circuit lower bounds |
| Algebrization | Aaronson–Wigderson 2009 | proofs surviving algebraic oracles |

Converting content into length requires a lower bound on the cost of
*expressing* a barrier-crossing ingredient, and no such bound is known.

### 14.4 The definitional floor — this one works

**Definition.** For φ not expressible in Σ, the **definitional floor** D_Σ(φ) is
the least number of new logical assertions that must be added before φ becomes
expressible and its notions usable — before the defining assertions are
accompanied by the elimination and congruence lemmas without which no proof can
manipulate them.

**Proposition.** ‖φ‖_Σ ≥ D_Σ(φ).

**Proposition (`set.mm` contains no complexity theory).** No machine model, no
time-bounded computation, no complexity class. The string `Turing` occurs
**zero** times. No label matches `turing`, `machin`, `halt`, `comput`, `decid`,
`recurs` or `complex`, except five topology labels whose match is coincidental.

So D(P ≠ NP) is the entire cost of building computability then complexity theory
on top. Note this is a **formalisation** cost, not a conceptual gap: v45's
appendix already supplies the machine model and the runtime↔proof-length
identification. What is missing is a `set.mm` development of it.

Calibrating against buildups `set.mm` has paid for — dep(φ) = logical assertions
in the transitive closure of φ's citations:

| Theorem | Position | dep | dep/position |
|---|---:|---:|---:|
| `pm2.01` | 189 | 37 | 0.20 |
| `simpl` | 486 | 44 | 0.09 |
| `falim` | 1,584 | 80 | 0.05 |
| `sbth` | 9,083 | 1,299 | 0.14 |
| `canth2` | 9,116 | 1,608 | 0.18 |
| `zorn` | 10,489 | 2,707 | 0.26 |
| `ruc` | 16,297 | 3,585 | 0.22 |
| `sqrt2irr` | 16,303 | 3,914 | 0.24 |
| `pythag` | 26,957 | 7,568 | 0.28 |
| `fta` | 27,219 | 7,839 | 0.29 |
| `bpos` | 27,432 | 8,271 | 0.30 |

A theorem at the depth of the fundamental theorem of algebra rests on roughly
8,000 logical assertions, and the ratio converges towards 0.30.

> **Estimate (not a theorem).** Computability theory is comparable in
> definitional depth to the construction of the reals, which `set.mm` reaches
> near position 16,000 with ~3,600 dependencies; complexity theory sits above
> it. Taking the calibration at face value,
>
> **D(P ≠ NP) ~ 10⁴ logical assertions**, hence **‖P ≠ NP‖ ≳ 10⁴ before a single
> step of the proof proper.**
>
> Soft in its constant, firm in its order of magnitude. What is rigorous is the
> floor proposition together with the zero-occurrences fact, checkable in one
> command.

## 15. What is actually known about proof length lower bounds

| Proof system | Best known lower bound | Status |
|---|---|---|
| Resolution | exponential (Haken 1985, PHP) | settled |
| Bounded-depth Frege | exponential (Ajtai 1988; later improvements) | settled |
| Frege | **none superpolynomial, for any tautology** | open |
| Extended Frege | **none superpolynomial, for any tautology** | open |
| ZFC / `set.mm` | **nothing** | open |

The gap between the third row and the first is the central open problem of proof
complexity. Nobody can exhibit a single tautology requiring superpolynomial
Frege proofs, and `set.mm` is far stronger than Frege.

> **No unconditional, nontrivial lower bound on ‖P ≠ NP‖ in a strong system is
> currently obtainable.** Producing one would itself be a major result in proof
> complexity, independent of anything it implied about P vs NP. The definitional
> floor is not an exception: it bounds the cost of *stating* the conjecture,
> which is a different and much easier quantity than the cost of proving it.

> **Where this belongs in v45**: beside `def:resolutionsystem`,
> `def:automatizable`, `def:polytimecheckable`, `def:feasibleinterp`,
> `def:interpolant`, `def:pigeonholefamily`, `cor:pigeonholespeedup`,
> `cor:nogbpoly` and the Cook–Reckhow `def:psim` — not beside the SIC
> definitions.

### 15.1 The unit problem in the norm

v45 defines two proof measures: ‖φ‖ (line count) and ‖φ‖^size (sum of formula
lengths), noting the apparatus relativises between them.

The observation here concerns a **third** measure v45 does not have. Define the
**logical-line count** ‖φ‖^log as |π| restricted to steps whose conclusion
begins `|-`. Over a Metamath corpus, on a 6,000-proof sample:

| | Raw steps | Logical steps |
|---|---:|---:|
| Median | 173 | 12 |
| Mean | 1,678 | 79.1 |

- **Ratio of medians: 14.4**
- **Ratio of aggregates: 21.2**
- **Share of executed steps that are formula-building: 95.3%**

These are three different numbers answering three different questions. 14.4 is
the correction for a *typical* proof; 21.2 for *total work* across the corpus;
95.3% is the fraction a two-phase prover generates rather than searches for. The
distributions are heavily right-skewed — mean 1,678 against median 173 — which
is why the aggregate and median ratios differ by 47%. **Revision 1 quoted a
median raw length alongside the aggregate ratio as though one followed from the
other. They do not.**

---

## 16. Conclusion

**What is proved.** Three theorems, conditional on nothing beyond v45's
definitions. The first shows κ is a property of the search policy. The second
identifies cross-branch insertion with v45's derived-rule construction, giving
Δ(c) ≥ 0 and the corollary that a branch which never halts is not thereby
wasted. The third shows a chain deficit produces an unbounded policy-relative
speedup, and explains why a layer of independent lemmas cannot. Alongside these,
the non-collapse of clocked simulation reverses Revision 1's verdict on the
settlement-region programme.

**What is measured.** The CV reproduces the accepted status of all 47,572
`set.mm` proofs, and the four certificates verify in full corpus context.
Against that, all four are one-step citations of pre-existing duplicates, and
16.8% of the corpus is vulnerable to the same effect.

**What is conjectured.** That chain deficits exist. That κ^us is measurable and
nonzero. Non-trivial reach for Predator_7.1 is, on present evidence, plausibly
zero.

### The unifying observation

> The third theorem gives a **policy-relative** separation. Upgrading it to
> v45's Abstract Asymptotic Speedup Principle requires condition (c′): *every*
> F-proof of cₙ has length at least g(n) + h(n). §15 records that no technique
> is known for establishing lower bounds of that form in a strong system — not
> even for a single tautology in Frege.
>
> **So the obstacle to finishing Part II is the obstacle to finishing Part III.**
> Both need a proof-length lower bound. The speedup principle is not blocked by
> a lack of ingenuity in constructing families; it is blocked by proof
> complexity, and it will stay blocked until proof complexity moves.

Constructively: on a fragment small enough for BFS to terminate, ‖cₙ‖ is
*computable* rather than merely bounded, so a candidate family can be verified
outright for small *n*. That is why the toy fragment remains useful.
Deflationarily: no amount of work on the search side will settle a Clay problem,
and the framework's own Proof-Horizon Theorem is what says so.

### Next steps, in order of tractability

1. **Measure κ^us.** Shared index and origin logging; no new theory.
2. **Measure non-trivial reach.** A substitution check against a corpus prefix.
3. **Restore the Predator_4 ranker** to Predator_7.1, which runs with
   `rank=None`.
4. **Search for a chain deficit** on the condensed-detachment fragment,
   verifying (c′) by exhaustive search for small *n*.
5. **Re-express measurements in logical-line units**, applying 14.4 where a
   typical proof is meant and 21.2 where total work is meant.

---

## 17. A Collection of Objects Discussed Herein

Following the format of the corresponding tables in v45. **First defined** names
the originating document; **here** marks the only objects for which this
document claims priority.

### Machines and search objects

| Name | Type | First defined | Role |
|---|---|---|---|
| `E_{F,Y}` | SIC; enumerating ATP | v45 §2 (`def:canonicalenum`) | Canonical brute-force benchmark; H ≡ 0, never halts |
| `E_{F,Y,φ}` | SIC; target-search ATP | v45 §2 (`def:canonicaltarget`) | Canonical target benchmark |
| `B_{F,Y}` | SIC; breadth-first ATP | v45 §2 | Shortest-proof horizon machine |
| `B_{F,Y,φ}` | SIC; breadth-first target-search | v45 §2 | The machine realising τ = ‖φ‖ |
| `F_T` | Configuration formal system | v45 App. (`def:configsys`) | One computation step as one inference |
| `E_T`, `M_T` | Trace SICs | v45 App. | Turing machine as SIC; enumerating and halting |
| `M_K` | Non-computable SIC | v45 App. (`ex:beyondturing`) | Witness that SICs exceed Turing machines |
| **`M⊗`** | **Settlement machine** | **here** | Two branches, shared store, alternating stages |
| `M^sep` | Separated settlement machine | **here** | Control: same branches, no shared store |
| **Λ_m** | **Lemma store** | **here** | Ground lemmas closed by either branch |

### Simulation relations and search policies

| Name | Type | First defined | Role |
|---|---|---|---|
| `S_M × S_N` | Weak simulation witness | v45 §3 (`thm:weakcollapse`) | Witness for universal weak simulation; the collapse |
| `id_{S_M}` | Synchronous simulation map | v45 §3 | Reflexive strong simulation |
| **`(f, ρ)`** | **Clocked simulation pair** | **v45 §3** | **The principal relation**; f injective, ρ an admissible clock |
| `(g∘f, σ∘ρ)` | Clocked simulation pair | v45 §3 | Transitivity construction |
| ρ | Admissible clock | v45 §3 | Nondecreasing, unbounded, ρ(1) = 1 |
| ⪯_clk, written ⪯ | Preorder on SICs | v45 §3 | Does **not** collapse |
| ⪯_p | *p*-simulation preorder | v45 §10 (`def:psim`) | Cook–Reckhow; tracks size, not stages |
| t, f_t | Recoding and its witness | v45 §4 | Invertible coding isomorphism |
| Σ | Nondeterministic search policy | v45 §5 | Branch generator / heuristic |
| Proof-covering | Property of a policy | v45 §5 | Every finite proof shadowed by a branch |

### Metrics for automated theorem proving

| Name | Type | First defined | Role |
|---|---|---|---|
| ‖φ‖_F(Γ) | Proof-length measure | v45 §2 | Line count of a shortest proof; the proof horizon |
| ‖φ‖^size | Size-relativised measure | v45 §10 (`def:sizefunction`) | Sum of formula lengths |
| **‖φ‖^log** | **Logical-line count** | **here** §15.1 | Restricted to `\|-` steps; 14.4× smaller by medians, 21.2× in aggregate |
| `L_F(Γ,m)` | Proof layer | v45 §2 | Exact shortest-proof stratum |
| τ_M(Γ,φ) | Search-cost measure | v45 §7 | Target transaction count; counts stage advances |
| **σ_M(Γ,c)** | **Settlement count** | **here** | Stages until *c* or ¬*c* appears; extends τ to two-sided targets |
| μ | Materialisation count | **here** (cf. v45 §7 remark) | Distinct formulas built before halting |
| **κ^av, κ^us** | **Cross-branch reuse rates** | **here** | Fraction of lemmas crossing the divide, by availability and by use |
| **Δ(c)** | **Settlement dividend** | **here** | Stages saved by sharing the store |
| **Non-trivial reach** | **Evaluation metric** | **here** | Targets proved under the admissible index |
| **σ > ω** | **Break-even rule** | **here** | Node speedup against per-node overhead |
| `P_F(Γ,φ,n)` | Counting function | v45 §8 | Number of length-*n* proofs |
| `s_F(Γ)` | Proof-complexity function | v45 §10 | Size of a shortest refutation of ⊥ |
| **T(π)** | **Verification transcript size** | **here** | Symbols materialised; the right unit for NP membership |
| **D_Σ(φ)** | **Definitional floor** | **here** | Assertions needed before φ is expressible |

### Formal systems, rules, and results invoked

| Name | Type | First defined | Role |
|---|---|---|---|
| Con_F(Γ) | Consequence operator | v45 §1 | Least inference-closed extension |
| D_F | One-step closure operator | v45 §1 | Direct-consequence expansion |
| F^D | Macro-augmented system | v45 §7 | F plus derived rules; conservative |
| **d_λ** | **Nullary derived rule** | **here** | Cross-branch insertion of a closed lemma |
| Proof-Horizon Thm. | Theorem | v45 (`thm:proofhorizon`) | First halting stage of `B_{F,Y,φ}` is ‖φ‖ |
| Branch-Covering Thm. | Theorem | v45 (`thm:branchcovering`) | Proof-covering policies reach φ by ‖φ‖ |
| Branch Soundness Thm. | Theorem | v45 (`thm:branchsoundness`) | p_m ⊆ Con_F(Γ) ∩ Y |
| Conservative Compilation | Theorem | v45 (`thm:compilation`) | Finite workloads compile to τ ≤ 2 |
| Abstract Asymptotic Speedup | Theorem | v45 (`thm:asympspeedup`) | Needs q(n) bounding **all** F-proofs |
| **Chain deficit** | **Hypothesis on a family** | **here** | Sufficient for policy-relative speedup |
| **Admissible index** | **Evaluation protocol** | **here** | Excludes duplicate statements, not merely labels |
| **Short-Proof_Σ** | **Language in NP** | **here** | Bounded provability, certified by the CV |

---

# Appendix A — History of Predator

Each version exists because the previous one hit a specific wall. The walls are
more informative than the versions.

| Version | File | Lines | Wall it hit |
|---|---|---:|---|
| Predator_1 | `predator.py` | 876 | The propositional fragment is a toy |
| Predator_2 | `predator2.py` | 960 | Ranks, cannot prove |
| Predator_3 | `predator3.py` | 1,128 | Unchanged — still no search |
| Predator_4 | `predator4.py` | 1,226 | Still no search. A ranking is not a proof |
| Predator_5 | `predator5.py` | 794 | Runs on a 287-state fragment, not `set.mm` |
| Predator_6 | `predator6.py` | 772 | The fragment cannot show what expert iteration is for |
| Predator_7 | `predator7.py` | 726 | Matching confines it to determined assertions |
| Predator_7.1 | `predator71.py` | 689 | Ranker dropped; results are duplicate lookups |

**Predator_2's contribution** was noticing that `set.mm` hands you the premise
structure for free — every proof names what it cites — so premise selection is
answerable without the substitution machinery. Scored with recall@k and
*effort*, the rank of the last true premise.

**Predator_4** trained on **903,356** logical references extracted from all of
`set.mm` (verified by recount). The strongest component of the line and the one
still worth reviving.

**Predator_5** was the pivot, with three load-bearing changes:

1. *The negatives change.* A policy's negatives must be the other edges
   applicable **at that state**, not lemmas sampled from elsewhere. Ranking an
   edge against a lemma from a different part of the search answers a question
   no search ever asks.
2. *The labels are computed, not read.* A `set.mm` proof is an upper bound on
   the shortest proof. Predator_5 runs BFS first, which returns the true
   distance, and marks every edge on some shortest path.
3. *There is a completeness theorem to lose.* Reordering Σ preserves
   proof-covering; truncating does not. `--mode reorder` keeps the
   Branch-Covering Theorem, `--mode prune` surrenders it.

**Measured:** every discarding strategy lost to unguided BFS on both time and
solve rate. Beam search expanded *more* nodes than BFS (114.5 vs 90.0), solved
70% against 100%, and ran 6.6× slower.

**Predator_6** found no improvement on the fragment — *as predicted*, because
BFS already prices every target there, so the certified labels are already
optimal. A hypothesis of mine about the expert-iteration frontier was refuted by
a controlled sweep and withdrawn.

### The break-even rule

Proof-covering says which policies are *sound*; nothing in v45 says which are
*worth running*. With σ_be = E_BFS/E_π the node speedup and ω = c_π/c_BFS the
per-node overhead, π is faster in real time iff **σ_be > ω**. Predator_1 had
σ_be = 18.1, ω = 41 → 2.5× *slower*. Predator_5 had σ_be = 2.14, ω = 1.2 →
1.76× faster. The smaller node advantage won, because a precomputed graph makes
nodes cheap — but a precomputed graph means the proofs are already known.

---

# Appendix B — The four certificates in full

```
$( Predator_7.1 proof of axin1 $)
$[ set.mm $]
chk $p |- ( ( ph -> -. ph ) -> -. ph ) $= wph pm2.01 $.

$( Predator_7.1 proof of falanfal $)
$[ set.mm $]
chk $p |- ( ( F. /\ F. ) <-> F. ) $= wfal anidm $.

$( Predator_7.1 proof of tbw-ax4 $)
$[ set.mm $]
chk $p |- ( F. -> ph ) $= wph falim $.

$( Predator_7.1 proof of axia1 $)
$[ set.mm $]
chk $p |- ( ( ph /\ ps ) -> ph ) $= wph wps simpl $.
```

Each verifies. Each is a single citation. See §5.

---

# Appendix C — Source code

Complete listings are in the **PDF edition**. In this repository the
authoritative copies are the files themselves.

| File | Lines | Contains |
|---|---:|---|
| `metamath_cv.py` | 916 | `MM`, `Toks`, `FrameStack`, `make_assertion`, `all_dvs`, `decompress`, `verify`; commands `selftest` / `search` / `verify` / `stats` / `show` |
| `setmm_grammar.py` | 578 | `Tree`, `build_grammar`, `build_index`, `parse`, `match_tree`, `_run_with_big_stack` |
| `predator71.py` | 689 | `fresh`, `is_meta`, `rename_apart`, `walk`, `apply_sub`, `occurs`, `unify`, `ground`, `tree_proof`, `Step`, `Index`, `pick_goal`, `prove` |
| `tau.py` | 706 | `sic_stages`, `tau`, `compile_rules`, `search_with_path`, `check_proof`, `mu_sic`, `search_mu`; commands `sic` / `compile` / `prove` / `axes` / `measure` / `family` |

**Files I do not have.** No trained model weights; the Predator_4 ranker's fitted
parameters were not preserved across the rewrite and would have to be retrained.
**The settlement machine of Part II is not implemented** — Part II is theory and
a measurement protocol, and no code for it exists yet.

### The two load-bearing excerpts

The disjoint-variable fix, without which five correct `set.mm` proofs are
rejected:

```python
def all_dvs(self):
    """EVERY disjoint pair active here, not just those on mandatory vars.
    A theorem's own proof may introduce DUMMY variables...
    Using the mandatory set here rejects equid, ax7, exgen, spnfw and spsv
    -- correct proofs, wrong reader."""
    return {(x, y) for fr in self for (x, y) in fr.d}
```

The goal-ordering rule, without which `ax-mp` regresses forever:

```python
def pick_goal(goals, sub):
    """Choose the MOST CONSTRAINED open goal, not simply the first.
    ...ax-mp turns goal G into ( ?1 -> G ) with ?1 free, and ?1 can be
    attacked by ax-mp again, giving an infinite regress..."""
```
