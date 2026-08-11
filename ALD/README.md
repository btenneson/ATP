# ALD — Automatic Logic Decider

This directory starts the executable implementation of the **Automatic Logic Decider (ALD)**. The first benchmark is **ALD-LEM-01**, the law of excluded middle:

\[
C := \varphi \lor \neg \varphi.
\]

The implementation follows the project policies: three distinct settlement objectives, a verifier-certified append-only shared bank, private agent state, fair scheduling, certificate-based stopping, frozen resource accounting, and `BOUNDED_UNKNOWN` rather than false claims of independence when a finite budget expires.

## Current milestone

The first code is intentionally small and auditable. It implements:

- **Prover P**: searches for a classical LK sequent-calculus proof of `A ⊢ C`.
- **Refuter R**: searches for a classical LK proof of `A ⊢ ¬C`.
- **Independence I**: for finite classical propositional problems, searches for a model pair satisfying `A ∪ {C}` and `A ∪ {¬C}`.
- **Verifier**: independently checks every LK proof or model-pair certificate before settlement.
- **Shared bank**: accepts only verifier-approved records and preserves provenance.
- **Scheduler**: auditable round-robin scheduling with a single global expansion budget.
- **Settlement statuses**: `PROVED`, `REFUTED`, `INDEPENDENT`, plus `BOUNDED_UNKNOWN` and `IMPLEMENTATION_FAILURE`.

For the classical LEM sanity environment, the expected *evaluation* outcome is known, but the answer is not passed to the agents. The Prover must construct a certificate and the verifier must accept it.

## Run

From this `ALD` directory:

```bash
python run_lem.py
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Important limitations

This is **not yet a general-purpose logic decider**. The proof search currently supports only the propositional fragment needed for the first benchmark (`¬`, `∨`) in a small classical sequent calculus. The shared-bank interface is present, but the minimal searcher does not yet mine deposited lemmas as premises. Creativity controls, heterogeneous search profiles, counterfactual admissions, adaptive scheduling, and cross-objective reuse metrics are next implementation layers.

The point of ALD-LEM-01 is to establish the trusted execution spine before adding those mechanisms.
