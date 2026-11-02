# DATA MIND 3.1 Experiment 005 — Adaptive Creativity Control on PRCOM

Status: **PREREGISTERED / NOT YET RUN**

Date frozen: 2026-09-03

## Question

Under the exact bounded PRCOM conditions used by DATA MIND 3 Experiment 004, does the DATA MIND 3.1 error-driven 11-dimensional creativity controller improve search behavior and/or settlement without changing the independent verifier boundary?

## Baseline being compared

Experiment 004 (`33768832046`) used the frozen historical `set.mm`, target `prcom`, candidate cap 64, max depth 24, max open goals 24, max expansions 20,000, timeout 1,800 s, and max frontier 200,000.

Its scientifically relevant bounded outcome was `UNKNOWN / frontier_budget`: 192 actual expansions generated 201,521 children and saturated the frontier before a candidate proof reached the verifier.

## Frozen source

- target: `prcom`
- target statement: `|- { A , B } = { B , A }`
- `set.mm` commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`
- frozen `set.mm` SHA-256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`
- independent verifier: repository `metamath.py`; its hash is recorded at run time

## Frozen search envelope

- candidate cap: 64 before creativity mapping
- max expansions: 20,000
- max depth: 24 before creativity mapping
- max open goals: 24
- timeout: 1,800 s
- max frontier: 200,000
- control interval: 16 actual expansions
- initial 11D creativity vector: all coordinates 0.5
- prior 3.1 experience: none for the first Experiment 005 run

## 11D creativity vector

All coordinates lie in `[0,1]`:

1. lemma direction
2. search breadth
3. search depth
4. heuristic weighting
5. term ordering
6. goal selection
7. node selection
8. creativity/divergence
9. abstraction level
10. risk tolerance
11. time/resource bias

The vector is conceptual. It maps to implementation settings, and the mapping plus every adaptive update is logged.

## Error objective

The controller observes bounded error terms for branching, frontier occupancy, structural target drift, stagnation, resource use, and lack of partial progress. The dense objective guides search only. It does **not** certify truth and does not alter the verifier.

## Controller restrictions

- deterministic bounded update rule for Experiment 005
- each coordinate movement is capped in magnitude per control update
- no black-box optimizer, CMA-ES, or reinforcement learner in this experiment
- no beam search added
- no new post-generation destructive pruning rule
- the independent Metamath verifier remains the only proof authority

## Primary outcomes

1. `PROVED` versus bounded `UNKNOWN`.
2. Expansions to first verifier-accepted proof if proved.
3. Generated children per actual expansion.
4. Whether the 200,000-state frontier bound is reached.
5. Number and trajectory of control updates.
6. Structural target-relevance/drift trajectory.
7. Wall time and peak RSS.

## Success interpretation

A verifier-accepted PRCOM proof is the strongest outcome. However, the controller is also considered experimentally informative if, under the same bounded envelope, it substantially reduces the Experiment-004 branching/frontier pathology and reaches materially deeper useful search without merely hiding work through unreported pruning.

## Experience artifact

The run writes a portable `dm31_prcom_exp005_experience.jsonl` containing the error pattern, creativity vector before/after each update, objective value, generated-per-expansion rate, and effective low-level settings. A later experiment may explicitly warm-start from this artifact; Experiment 005 itself starts without prior 3.1 experience.

## Governance

This file freezes the experiment before execution. The 3.0 baseline branch remains unchanged. Code changes, experiment execution, and verifier-accepted mathematical outcomes must be reported as separate facts.
