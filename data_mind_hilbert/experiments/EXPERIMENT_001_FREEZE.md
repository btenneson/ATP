# DATA MIND Hilbert Ablation 001 — Frozen Pilot Specification

## Research question

Does Hilbert-addressed proof geometry, by itself, increase verifier-certified
settlement compared with matched search without Hilbert navigation?

This is the first geometry-only pilot.  It does **not** test learned numeric
federation, BANK advantage, Depth Charge, awareness controls, or oracle access.

## Frozen source and holdout

- Formal corpus: `set.mm` commit `f85a8edbb6df20dd5a64a9c159fa22944a3e54de`.
- Required SHA-256: `19cb1ec229f3f11e36ff439a6381878864d9f2d4906f20fc9401346b309894e3`.
- Parent split: the already-frozen DATA-MIND set.mm Frozen-20 95%/5% reverse-citation-leaf split.
- The canonical split is reconstructed and hash-checked by the existing preparation process.
- The settlement parser discards theorem proof text.
- Every non-target held-out theorem is removed from the legal search library.
- Any candidate proof containing a held-out theorem label is rejected before the independent verifier.

## New sealed target cohort

The target selector uses only proof-redacted parser structure after the canonical
holdout has been reconstructed.

- Selection seed: `314159`.
- Prior Frozen-20 targets are excluded.
- 50 targets total.
- 40 P targets: ordinary held-out theorem statements.
- 10 R targets: held-out theorem statements syntactically beginning `|- -.`.
- An R result is settled only by a verifier-accepted proof of that negation.
  Search failure is never interpreted as refutation.
- Targets with essential hypotheses are excluded from this first pilot.
- Target statement length is at most 60 tokens and target order is greater than 500.

The core search is deterministic in this experiment.  Therefore there is one
run per target per arm rather than five redundant copies called different
"seeds."  Repeated random seeds return when a stochastic controller is added.

## Arms

All arms use the same parser, legal assertions, matcher, syntax oracle, term
completion, state scoring, budgets, stopping rule, candidate verifier, and
independent final Metamath verifier.

### Arm A — OFF

Matched non-Hilbert search-order control.  The experimental search loop runs in
`off` mode and must match the production baseline on the frozen smoke fixture.

### Arm B — naive Hilbert

Every instantiated logical `$e` premise receives a deterministic 6-bit scalar
premise-slot coordinate from SHA-256.  For a rule with `k` logical premises,
the ordered tuple of `k` coordinates lies in a finite `k`-dimensional grid and
is mapped to a finite Hilbert traversal index.

The hash coordinate intentionally has no structural-locality hypothesis.  It is
the placebo geometry for testing Hilbert ordering without meaningful syntax
clustering.

### Arm C — structural Hilbert

The Hilbert machinery is identical to Arm B.  Only the premise-slot address map
changes.  A frozen theoremhood-independent structural basin is computed from
bounded syntactic features such as token count, parenthesis depth, variable
count, quantifier count, negation/connective/relation counts, and repetition.
A short SHA-256 microcode distinguishes premises inside the structural basin.

This is a fixed **structural-address prototype**, not a learned geometry.
Calling it learned geometry would overstate this pilot.

## Geometry convention

An individual WFF remains intrinsically zero-dimensional.  Its scalar address
is premise-slot metadata only.

For an inference rule with `k` logical `$e` premises, the action geometry has
intrinsic dimension `k`.  Floating `$f` syntax hypotheses are discharged by the
existing SyntaxOracle and are not counted as logical premise dimensions in this
pilot.

A legal successor receives a bounded Hilbert-locality bonus only **after** all
ordinary matching, substitution, distinct-variable, syntax-proof, depth, and
open-goal checks have passed.  Geometry cannot make an illegal action legal.

For B/C, the current goal supplies a local anchor.  The action premise tuple and
the `k`-fold goal-address anchor are compared along the finite Hilbert
traversal.  The frozen maximum navigation bonus is `0.75` added to the ordinary
Scout successor score.  Zero-premise rules receive no geometry bonus.

## Fixed budget and primary endpoint

- Maximum expansions: 20,000 per arm/target.
- Wall-clock tripwire: 300 seconds.
- Maximum depth: 24.
- Maximum open goals: 24.
- Candidate cap: 64.
- Maximum frontier: 200,000.
- Hilbert coordinate bits per premise slot: 6.

The **primary endpoint** is verifier-accepted settlement within the same
20,000-expansion budget.  Wall-clock time, generated children, proof length,
and memory/runtime effects are secondary or diagnostic.

## Primary comparisons

- `B - A`: effect of naive Hilbert navigation.
- `C - B`: effect of theoremhood-independent structural addressing given the
  same Hilbert mechanism.
- `C - A`: total effect of this first structural Hilbert pilot.

The desired pattern `C > B > A` is not assumed.  `B <= A`, `C <= B`, or no
settlement difference are valid results.

## Interpretation limits

This pilot cannot establish that Hilbert is superior to all locality-preserving
traversals, because Morton/Z-order is reserved for the next ablation if the
geometry shows signal.  It also cannot establish the value of the fuzzy-looking
numeric scheduler, verified BANK federation, or Depth Charge.  Those components
remain off so that the first treatment is identifiable.

The verifier, not the navigation score, decides settlement.
