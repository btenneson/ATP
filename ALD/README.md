# ALD — Automatic Logic Decider

This directory contains the executable implementation of the **Automatic Logic Decider (ALD)**. The first benchmark is **ALD-LEM-01**, the law of excluded middle:

\[
C := \varphi \lor \neg \varphi.
\]

The implementation follows the project policies: three distinct settlement objectives, verifier-certified append-only shared memory, private agent state, fair scheduling, certificate-based stopping, frozen resource accounting, and `BOUNDED_UNKNOWN` rather than false claims of independence when a finite budget expires.

## Current milestone

The current bootstrap implements:

- **Prover P**: searches for a classical LK sequent-calculus proof of `A ⊢ C`.
- **Refuter R**: searches for a classical LK proof of `A ⊢ ¬C`.
- **Independence I**: for finite classical propositional problems, searches for a model pair satisfying `A ∪ {C}` and `A ∪ {¬C}`.
- **Verifier**: independently checks every LK proof, shared lemma proof, CUT composition, or model-pair certificate before it can affect settlement.
- **Operational shared bank**: verified intermediate theorem lemmas are proof-carrying and can be consumed by another proof agent through an explicit verifier-checked CUT.
- **Provenance and reuse logging**: every bank record stores its producer/objective, proof certificate, cost, and parent lemma IDs; productive cross-objective reuse is logged separately.
- **Heterogeneous creativity profiles**: P, R, and I have distinct reproducible profile configurations and hashes.
- **Scheduler**: auditable round-robin scheduling with a single global expansion budget.
- **Settlement statuses**: `PROVED`, `REFUTED`, `INDEPENDENT`, plus `BOUNDED_UNKNOWN` and `IMPLEMENTATION_FAILURE`.

For the classical LEM sanity environment, the expected *evaluation* outcome is known, but the answer is not passed to the agents. The Prover must construct a certificate and the verifier must accept it.

## Shared-bank soundness rule

A bank lemma is never trusted merely because another agent produced it. If an agent reuses lemma `L`, the new proof contains a CUT whose first premise is the previously verifier-accepted proof of `L` and whose second premise is the proof that uses `L`. The verifier checks the complete composed certificate again.

This makes sharing an attention/search mechanism rather than a relaxation of formal correctness.

## Cross-objective creativity instrumentation

`RunResult` now exposes:

- `reuse_events`
- `cross_objective_reuse_count`
- `verified_lemma_cost`
- `cross_objective_reuse_efficiency`

The regression suite includes a small controlled benchmark where Refuter constructs a reusable classical tautology and Prover later consumes it through CUT to settle the target. This is an instrumentation test, not yet evidence that shared memory improves performance on held-out theorem families.

## Creativity profiles

The profile schema records temperature, candidate width, breadth/depth balance, novelty pressure, restart rate, lemma-construction budget fraction, bank-reuse limit, counterfactual-admission rate, and seed.

In this bootstrap, **candidate width, lemma-construction budget fraction, and bank-reuse limit are operational**. The other fields are already frozen/logged so later ranked-search experiments can activate them without changing the experimental record format. See `docs/CREATIVITY_PROFILES.md`.

## Run

From this `ALD` directory:

```bash
python run_lem.py
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

The current suite has six tests covering all three settlement outcomes, bounded unknown, distinct profile logging, and cross-objective proof-carrying lemma reuse.

## Important limitations

This is **not yet a general-purpose logic decider**. The proof search currently supports only a small classical propositional LK fragment (`¬`, `∨`). Intermediate lemma generation is intentionally primitive: the bootstrap proposes simple atom-level excluded-middle tautologies so that shared-memory plumbing can be tested without confusing architecture validation with sophisticated lemma mining.

The next implementation layers are ranked candidate selection, controlled counterfactual admission, richer lemma mining, novelty measurement, adaptive creativity/scheduling, and matched isolated-versus-shared experiments under identical global budgets.
