# DATA MIND 3.0 / 3.1 Project State — 2026-09-03

This note is a continuity checkpoint. It records what has actually run, what the current code does, and the proposed DATA MIND 3.1 direction. It is not a code change.

## Current implementation location

Repository: `btenneson/ATP`

Current experiment branch: `dm3-prcom-exp004`

Core implementation:
- `data_mind_3/metamath/`
- `run_dm3_metamath_target.py`
- `.github/workflows/dm3-prcom-exp004.yml`

## Latest PRCOM experiment actually run

Workflow: `DATA MIND 3 Experiment 004 PRCOM`

GitHub Actions run: `33768832046`

Date: 2026-09-03

Target: `prcom`, statement `|- { A , B } = { B , A }`

Frozen `set.mm` commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`

Configured bounds:
- candidate cap: 64
- max expansions: 20,000
- max depth: 24
- max open goals: 24
- timeout: 1,800 s
- max frontier: 200,000

Observed result:
- status: `UNKNOWN`
- reason: `frontier_budget`
- actual expansions: 192
- generated children: 201,521
- frontier at stop: about 200,732
- elapsed search: about 27.29 s
- wall clock: about 33.19 s
- peak RSS: about 577,148 KB
- verifier candidate checks: 0
- verifier-accepted PRCOM proof: none

Interpretation: this was primarily a search-control / branching-factor failure, not a timeout, RAM failure, verifier failure, or evidence that PRCOM is too deep for DATA MIND 3.0. The system generated roughly 1,050 children per actual expansion and saturated the frontier before using even 1% of its nominal 20,000-expansion budget.

Historian inspection showed strong target drift: approximately 188 of 192 expanded states contained `T.` or `F.`, while only a few retained direct `A`/`B` pair structure. Professor currently records `admit_successor` for every legal successor reaching it; it is not yet a discriminating admission controller.

## Important current limitation: no persistent experience

A rerun of Experiment 004 is cold. `run_dm3_metamath_target.py` writes the historian only after a run and does not load prior historian/results before searching. `search_target` initializes a fresh frontier, counters, historian, and `best_seen` map.

Therefore a plain rerun does not learn from the first PRCOM attempt.

## DATA MIND 3.1 proposed defining feature

Proposed thesis:

> DATA MIND 3.1 minimizes observed search error by adaptively controlling an 11-dimensional creativity vector while preserving a protected proof-search baseline and an immutable external verifier boundary.

### The 11 knobs are creativity knobs

The 11 high-level knobs should remain the conceptual creativity/search-strategy coordinates, not be confused with low-level `SearchConfig` fields.

Current working 11-dimensional creativity vector:
1. Lemma Direction
2. Search Breadth
3. Search Depth
4. Heuristic Weighting
5. Term Ordering
6. Goal Selection
7. Clause / Node Selection
8. Creativity / Divergence
9. Abstraction Level
10. Risk Tolerance
11. Time / Resource Bias

Represent them numerically as

`C = (c_1, ..., c_11)`, typically with each coordinate bounded, e.g. `[0,1]`.

The low-level implementation parameters are a separate vector, for example candidate caps, matching caps, free-variable completion caps, term-pool limits, depth limits, frontier limits, etc. A mapping `F` translates the 11 creativity knobs into those concrete settings:

`C -> F(C) -> low-level search controls`.

## Error-driven optimization idea

Define an error vector from observed search behavior, for example:
- frontier error
- branching-factor error
- target-drift error
- stagnation error
- resource error
- progress / partial-credit error

A scalar objective can combine these:

`J = w_b E_branch + w_f E_frontier + w_d E_drift + w_s E_stagnation + w_r E_resource + w_p (1 - C_partial)`

with proof settlement handled lexicographically or by a dominating penalty/reward so that a verified proof always dominates merely cheap unsuccessful search.

The adaptive controller updates the creativity vector:

`C_{t+1} = Controller(C_t, e_t, H_t)`

where `e_t` is current error and `H_t` is experience/history.

For the 2026-09-03 PRCOM run, the dominant observed errors were frontier growth, branching explosion, and target drift. A plausible controller response would be lower breadth/divergence/risk and greater target-relevance weighting while preserving or increasing depth willingness. This response should be learned/tested rather than hard-coded as a theorem-specific rule.

## Protected baseline / completeness principle

Do not initially make the adaptive controller permanently destroy low-ranked legal branches. Prefer reordering, deferral, and protected-baseline search over aggressive irreversible pruning. Earlier project evidence found weighted-A* reordering preserved completeness and outperformed incomplete pruning/beam strategies on the benchmark where they were directly compared.

Suggested conceptual frontier:

`Q = Q_adaptive union Q_protected`

The adaptive layer changes priority; the protected layer preserves a route to completeness under the applicable finite-budget assumptions.

## Professor in 3.1

Professor should evolve from passive `admit_successor` logging into a soft ranking/admission controller. Candidate states can receive categories such as high priority / normal priority / defer rather than an unsafe binary truth-like judgment.

Potential score inputs:
- partial credit
- structural target relevance
- useful novelty
- target drift
- estimated branching cost

The 11 creativity knobs can modulate the weights on these factors.

## Persistent experience in 3.1

3.1 should save compact experience records, not just raw historian logs. Example record:

`{error_pattern, creativity_vector, delta_creativity, delta_objective, outcome}`

Experience may guide future search but never certify truth. Final proof authority remains the independent Metamath verifier.

## Governance / provenance

Maintain explicit distinctions between:
- ideas proposed by the user
- designs proposed by the assistant
- code changes actually made
- changes explicitly approved
- experiments actually run
- verifier-accepted results

Do not silently modify DATA MIND architecture and later treat those modifications as if they were part of the previously approved system.

At the time this checkpoint was written, no DATA MIND 3.1 adaptive-control code had been added. This file itself is only a continuity note.