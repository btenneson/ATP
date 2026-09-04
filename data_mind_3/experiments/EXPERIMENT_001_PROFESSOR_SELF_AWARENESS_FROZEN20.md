# DATA MIND 3.1 Experiment 001 — Professor/Self-Awareness Frozen-20 Ablation

Status: **PREREGISTERED RESEARCH ABLATION; NOT AN OFFICIAL DATA MIND 3.1 SETTLEMENT RUN**

Approved by the user on 2026-09-03 with the instruction: `permission granted, proceed`.

## Frozen provenance

- Base branch at preregistration: `dm31-frozen20-training-settlement-dev`
- Base commit: `38ffb06356f4a5eb0b7b2b8dbafc7370ffcea409`
- Canonical architecture snapshot SHA-256: `e1dd2785b83415a930b23bf432830444b637a61ee4266e710c3c1a41c666a8b0`
- Benchmark: `DATA-MIND set.mm Frozen-20 Benchmark 001`
- Split seed: `271828`
- Training theorems: 45,410
- Held-out theorems: 2,390
- Frozen targets: 20
- Frozen set.mm commit: `f85a8edbb6df20dd5a64a9c159fa22944a3e54de`
- Frozen set.mm SHA-256: `19cb1ec229f3f11e36ff439a6381878864d9f2d4906f20fc9401346b309894e3`

`RUNTIME_CONFIG_001.json` remains unresolved and is not modified by this experiment. Therefore these results must not be described as an official complete eight-agent DATA MIND 3.1 settlement run.

## Question

Does adding the current Professor signal plus operational self-awareness to P1 improve certified proof-side settlement performance, while an independent P2 lane is preserved as a hedge/control?

The experiment is deliberately smaller than the full eight-agent architecture because the frozen set.mm corpus supplies proof-side supervision but not equivalent successful R/I/C trajectories.

## Hypotheses

Primary null:

`H0`: Professor/self-awareness does not improve verifier-accepted settlement within the fixed proof-couple budget.

Primary alternative:

`H1`: Professor/self-awareness increases verifier-accepted settlement or reduces the search cost of settlement within the same budget.

Secondary calibration question: on the unchanged Arm-A trajectory, are higher/rising shadow Professor scores associated with later verifier-accepted proof settlement?

## Arms

### Arm A — fixed proof-couple control

- P1: balanced 11D creativity vector `(0.5,...,0.5)`.
- P1 controller updates are disabled by setting the update interval beyond the experiment budget. The ordinary search mapping/scoring interface remains present so Arm C begins from the same P1 control surface.
- P2: a fixed theorem-independent creativity vector generated once from `random.Random(271828)` with each coordinate drawn uniformly from `[0.25,0.75]`.
- No Professor-driven P1 updates.
- No Child play.

Frozen P2 vector, in `CreativityVector` coordinate order:

1. lemma_direction = 0.592296
2. search_breadth = 0.736838
3. search_depth = 0.704512
4. heuristic_weighting = 0.444473
5. term_ordering = 0.703784
6. goal_selection = 0.586104
7. node_selection = 0.675007
8. divergence = 0.253289
9. abstraction_level = 0.256563
10. risk_tolerance = 0.357390
11. resource_bias = 0.395406

The seed-derived partner vector is not tuned to any Frozen-20 target.

### Arm B — exact shadow-Professor replay

Arm B does **not** rerun search. It computes Professor telemetry from the exact Arm-A P1 trajectory after the fact.

- Search decisions are byte-for-byte unaffected by Professor measurement.
- The shadow calculation uses the currently implemented research proxy `H_hat=max(0,1/q_raw-1)` and the current experimental 50/50 Professor scalarization over verified-structure proxy and repair proximity.
- The first positive `H_hat` supplies the run-local repair half-distance, matching the current reflective P1 research implementation.
- This is explicitly a burden proxy, not a claim to exact global repair distance.

By construction, Arm B must have exactly the same settlement outcome as Arm A. Its purpose is calibration/mechanism measurement, not a second causal treatment.

### Arm C — active Professor/self-aware P1

- P1: `ReflectiveP1Controller`, starting from the same balanced vector as Arm A.
- Professor signal active.
- P1 operational self-awareness active.
- Adaptive response interval: 16 expansions.
- Child knob play: **disabled** to avoid confounding this mechanism test.
- P2: the exact same frozen independent P2 lane used in Arm A; its result is reused as a common control.

## Fixed resource budget

Each conceptual proof-couple arm receives at most:

- **100,000 total expansions** = 50,000 P1 + 50,000 P2.
- **1,800 total lane-seconds** = 900 s P1 + 900 s P2.
- base candidate cap: 64.
- max depth: 24.
- max open goals: 24.
- max frontier: 200,000.

The two lanes are executed independently rather than by a live interleaving scheduler. Therefore per-lane wall time is recorded, but no claim is made that sequential GitHub job wall time equals wall-clock time to first settlement in a physically parallel proof couple.

## Holdout isolation

The permanent 95/5 split is reconstructed and hash-checked in a separate preparation process. That process emits only the ordered holdout labels and hashes—never hidden proofs.

Each settlement lane then runs in a fresh Python process. The DATA MIND parser discards theorem proof text. Every non-target held-out theorem is removed from the legal search library before search begins. Candidate proof labels are additionally rejected before verifier invocation if they reference any held-out theorem label.

A final candidate is accepted only if the independent `metamath.py` verifier accepts it.

## Primary outcomes

1. Verifier-accepted proof settlement count out of the same 20 frozen targets.
2. Arm-C minus Arm-A settlement count.
3. P1-only verifier-accepted settlement count in A versus C.

Arm B settlement count must equal A by construction.

## Secondary outcomes

- expansions to verifier-accepted proof per lane;
- generated children;
- per-lane search wall time;
- Professor credit trajectory in shadow B;
- active Professor/self-awareness update counts in C;
- final 11D P1 creativity vector in C;
- number of targets on which common independent P2 settles when A-P1 fails;
- number of targets on which common independent P2 settles when C-P1 fails;
- descriptive comparison of shadow Professor scores on A-P1 solved versus unsolved targets.

Professor score is never a settlement certificate and never replaces the primary verifier outcome.

## Mechanisms deliberately excluded

To preserve causal interpretability, Experiment 001 does not activate:

- Child knob play or group-inverse trials;
- bounded partner-awareness `awa(P1,P2)`;
- marginal-value proof-couple controller;
- R/I/C couples;
- Quotient Hunter intervention;
- Presentation Manager/trading intervention;
- any modification to verifier acceptance semantics;
- any modification to the frozen canonical architecture snapshot or benchmark lock.

Those are candidates for later experiments after this mechanism test.

## Interpretation rules

- If C settles more targets than A, that supports deeper testing of the Professor/self-awareness feedback path, but does not isolate Professor from self-awareness individually.
- If C settles fewer, the feedback path is harmful under this frozen proxy/calibration and should be revised rather than protected by theory.
- If shadow B scores are high on A-P1 failures, the Professor signal is likely miscalibrated even if C occasionally wins.
- If P2 rescues targets missed by P1, that is direct evidence for the value of preserving an independent partner lane.
- Negative results are valid results.
