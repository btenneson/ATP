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
2. The creativity runner currently activates temperature, candidate width, lemma-construction budget fraction, bank-reuse limit, counterfactual-admission rate, and seed.
3. Breadth/depth balance, novelty pressure, and restart rate remain represented and logged but are not yet behaviorally active.
4. A counterfactual action may be admitted only from the set of legal proof actions; verification is unchanged.
5. The code and documentation must not claim inactive controls are implemented until they actually alter search.
6. Architecture complexity must be charged against the same global benchmark budget when compared experimentally.

## Matched sharing experiments

1. `shared` and `isolated` conditions must use fresh runners with the same formal target, profiles, seeds, verifier, scheduler design, activation slice, and global budget.
2. Shared mode exposes the full verifier-certified bank to each agent.
3. Isolated mode exposes only records produced by the consuming agent itself.
4. The global audit bank may still record all verified contributions in both conditions; only information visibility changes.
5. A gain on a constructed microbenchmark is an implementation result, not a population-level estimate of creativity gain.

## Benchmark integrity

1. The formal environment and target are frozen and hashed before search.
2. The classical LEM sanity benchmark does not pass the known expected answer to search agents.
3. Auxiliary lemma generation excludes the benchmark conjecture and its negation, so the lemma mechanism cannot become a disguised answer channel.
4. Repeated matched experiments over theorem families must use predeclared seeds, budgets, and outcome metrics.

## Current acceptance checks

The bootstrap regression suite must continue to demonstrate:

- classical excluded middle can settle `PROVED` by checked proof;
- an atom over the empty classical theory can settle `INDEPENDENT` by checked model pair;
- the negation of excluded middle can settle `REFUTED`;
- a tiny budget returns `BOUNDED_UNKNOWN`;
- P/R/I profiles are distinct and logged;
- a verified lemma produced under one objective can be consumed under another objective through verifier-checked proof composition;
- a capped proof search can be rescued by a seeded legal counterfactual admission while the verifier remains unchanged;
- profile counterfactual settings are actually wired into the controlled proof agent;
- a matched shared-versus-isolated microbenchmark can reproduce the current 7-versus-9 expansion result.

These are architecture tests. The 7-versus-9 result is a deliberately constructed instance and does not establish an expected ALD creativity gain on held-out theorem families.

## Next unsatisfied policies

The next code layers are richer lemma mining, normalized proof-novelty measurement, behaviorally active breadth/depth and restart controls, adaptive creativity/scheduling, and repeated matched isolated-versus-shared creativity experiments on held-out theorem sets.
