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
- **Creativity-controlled proof search**: candidate caps, seeded temperature perturbation, and controlled counterfactual admission are wired through an experimental runner.
- **Matched sharing mode**: the same experimental runner can expose the full bank (`shared`) or only an agent's own records (`isolated`).
- **Scheduler**: auditable round-robin scheduling with a single global expansion budget.
- **Settlement statuses**: `PROVED`, `REFUTED`, `INDEPENDENT`, plus `BOUNDED_UNKNOWN` and `IMPLEMENTATION_FAILURE`.

For the classical LEM sanity environment, the expected *evaluation* outcome is known, but the answer is not passed to the agents. The Prover must construct a certificate and the verifier must accept it.

## Shared-bank soundness rule

A bank lemma is never trusted merely because another agent produced it. If an agent reuses lemma `L`, the new proof contains a CUT whose first premise is the previously verifier-accepted proof of `L` and whose second premise is the proof that uses `L`. The verifier checks the complete composed certificate again.

This makes sharing an attention/search mechanism rather than a relaxation of formal correctness.

## Counterfactual search

The proof-search primitive ranks legal actions with a small transparent structural heuristic. `candidate_width` defines the ordinary active set. A seeded counterfactual mechanism can admit one legal action from outside that cap and try it first. The regression suite contains a case where capped search fails within two expansions but the otherwise identical counterfactual condition finds a verifier-accepted proof.

This tests the counterfactual-rescue mechanism; it is not a claim that more counterfactual exploration is always better.

## Shared-versus-isolated microbenchmark

The repository now contains a matched A/B harness that holds the target, profiles, seeds, verifier, scheduler design, activation slice, and global budget fixed while changing only cross-agent bank visibility.

On one deliberately constructed plumbing benchmark, shared mode settles in **7 charged expansions** and isolated mode settles in **9**, a **2-expansion (22.2%) reduction**. Refuter produces the reusable lemma and Prover consumes it through CUT.

That number is intentionally **not** presented as an estimate of ALD's expected gain on the law of excluded middle or on real theorem families. It proves only that the implemented sharing mechanism can create a measurable resource gain on a controlled instance.

## Creativity profiles

The profile schema records temperature, candidate width, breadth/depth balance, novelty pressure, restart rate, lemma-construction budget fraction, bank-reuse limit, counterfactual-admission rate, and seed.

Currently behaviorally active in the creativity runner: temperature, candidate width, lemma-construction allocation, bank-reuse limit, counterfactual admission, and seed. Breadth/depth balance, novelty pressure, and restart rate remain recorded but inactive until the search architecture can implement them honestly. See `docs/CREATIVITY_PROFILES.md`.

## Run

From this `ALD` directory:

```bash
python run_lem.py
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

The current suite has nine tests covering all three settlement outcomes, bounded unknown, distinct profile logging, proof-carrying cross-objective lemma reuse, counterfactual rescue, profile-to-search wiring, and the matched shared-versus-isolated microbenchmark.

## Important limitations

This is **not yet a general-purpose logic decider**. The proof search currently supports only a small classical propositional LK fragment (`¬`, `∨`). Intermediate lemma generation is intentionally primitive: the bootstrap proposes simple atom-level excluded-middle tautologies so that shared-memory plumbing can be tested without confusing architecture validation with sophisticated lemma mining.

The next implementation layers are richer lemma mining, normalized proof-novelty measurement, breadth/depth control, restarts, adaptive creativity/scheduling, and repeated matched isolated-versus-shared experiments over held-out theorem sets.
