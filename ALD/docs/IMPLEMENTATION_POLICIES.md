# ALD Implementation Policies — Code-Facing Contract

This file is the implementation-facing companion to the research policy document. It records the rules the current code must preserve while the architecture grows.

## Settlement integrity

1. `PROVED` requires a verifier-accepted certificate for `A ⊢ C`.
2. `REFUTED` requires a verifier-accepted certificate for `A ⊢ ¬C`.
3. `INDEPENDENT` requires an appropriate verifier-accepted metamathematical certificate.
4. Reaching a finite resource limit returns `BOUNDED_UNKNOWN`, never `INDEPENDENT`.
5. Software failures return `IMPLEMENTATION_FAILURE`, never a mathematical settlement.

## Shared-bank integrity

1. The bank is append-only during a run.
2. Nothing enters the bank before verification.
3. A reusable proof lemma must carry its proof certificate.
4. Reuse by another proof agent must be represented inside the new proof certificate, currently through an explicit verifier-checked `CUT`.
5. The verifier checks the composed proof again; prior acceptance of a bank record is not a bypass around verification.
6. Every accepted record preserves producer, objective, cost, verifier version, and parent-lemma provenance.
7. Productive reuse is logged separately, including producing and consuming objectives.

## Agent separation

1. P, R, and I retain distinct objective identifiers and private state.
2. Sharing a lemma makes it available; it does not force another agent to attend to it.
3. Search-control profiles are separate and reproducible for each role.
4. Profile values are logged and hashed so matched experiments can reproduce them exactly.

## Creativity-control discipline

1. Search controls are inputs, not measured creativity.
2. The current bootstrap operationalizes candidate width, lemma-construction budget fraction, and bank-reuse limit.
3. Temperature, breadth/depth balance, novelty pressure, restart rate, and counterfactual-admission rate are represented and logged but are not yet behaviorally active in the deterministic LK search.
4. The code and documentation must not claim those inactive controls are implemented until they actually alter search.
5. Architecture complexity must be charged against the same global benchmark budget when compared experimentally.

## Benchmark integrity

1. The formal environment and target are frozen and hashed before search.
2. The classical LEM sanity benchmark does not pass the known expected answer to search agents.
3. Auxiliary lemma generation excludes the benchmark conjecture and its negation, so the lemma mechanism cannot become a disguised answer channel.
4. Matched isolated-versus-shared experiments must use the same theorem set, seeds, verifier, hardware, and global resource accounting.

## Current acceptance checks

The bootstrap regression suite must continue to demonstrate:

- classical excluded middle can settle `PROVED` by checked proof;
- an atom over the empty classical theory can settle `INDEPENDENT` by checked model pair;
- the negation of excluded middle can settle `REFUTED`;
- a tiny budget returns `BOUNDED_UNKNOWN`;
- P/R/I profiles are distinct and logged;
- a verified lemma produced under one objective can be consumed under another objective through a verifier-checked proof composition, with provenance and cross-objective reuse recorded.

These are architecture tests. They do not by themselves establish that shared memory or heterogeneous profiles improve creative yield on held-out benchmarks.

## Next unsatisfied policies

The next code layers are ranked candidate selection, behaviorally active counterfactual admission, richer lemma mining, normalized proof-novelty measurement, adaptive creativity/scheduling, and the matched isolated-versus-shared creativity experiment.
