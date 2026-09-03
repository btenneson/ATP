# DATA MIND 3.1 Experiment 005 PRCOM — Result

Date: 2026-09-03

Official GitHub Actions run: `33782512472`

Accidental non-preregistered replication: `33782557915`

Target: `prcom`, `|- { A , B } = { B , A }`

Frozen set.mm SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`

## Official outcome

Status: `UNKNOWN`

Reason: `expansion_budget`

Verifier-accepted PRCOM proof: none

Verifier candidate checks: 0

Expansions: 20,000 / 20,000

Generated children: 149,277

Mean generated children per expansion: 7.46385

Final frontier: 104,233 / 200,000

Search time: 138.0365 s

Wall time: 143.60 s

Peak RSS: 494,760 KB

Adaptive control updates: 1,250 at interval 16

Warm-start experience rows: 0

## Comparison with DATA MIND 3.0 Experiment 004

Experiment 004 stopped at 192 expansions because the frontier exceeded 200,000 after generating 201,521 children. That is approximately 1,049.59 children per expansion.

Experiment 005 reached the full 20,000 expansion budget while generating only 149,277 children, or 7.46385 per expansion.

Thus Experiment 005 achieved about a 140.6x reduction in children per expansion, executed about 104.2x as many actual expansions, and generated about 25.9% fewer total children than Experiment 004.

This is strong evidence that the adaptive controller corrected the catastrophic branching-factor failure observed in Experiment 004.

## Controller trajectory

All eleven creativity coordinates began at 0.5.

The controller reacted strongly to early branching pressure:

- expansion 16: recent branching = 639.8125 children/expansion; breadth moved 0.50 -> 0.38.
- search breadth reached 0.0 by expansion 256.
- heuristic weighting reached 1.0 by expansion 288.
- risk tolerance reached 0.0 by expansion 352.
- search depth and node selection reached 1.0 by expansion 432.
- divergence reached 0.0 by expansion 528.
- resource bias reached 1.0 by expansion 208.

Final creativity vector:

- lemma_direction = 0.3455034722222221
- search_breadth = 0.0
- search_depth = 1.0
- heuristic_weighting = 1.0
- term_ordering = 0.5107291666666667
- goal_selection = 0.5214583333333334
- node_selection = 1.0
- divergence = 0.0
- abstraction_level = 0.7393750000000002
- risk_tolerance = 0.0
- resource_bias = 1.0

Final effective low-level controls included candidate_cap = 8, match_cap_per_candidate = 3, free_var_completion_cap = 17, and max_depth = 33.

## New failure mode

Experiment 005 did not reproduce Experiment 004's T./F. propositional drift. Across 20,000 expanded states:

- 0 expanded goals contained `T.` or `F.`.
- all 20,000 expanded goals retained `A` or `B`.
- 19,987 / 20,000 expanded goals retained pair-brace syntax.
- mean target-relevance score was approximately 0.9975.

However, this did not mean the search was making proof progress.

The number of open goals rose until it hit the configured maximum of 24 by roughly expansion 512 and remained there. Partial Credit consequently fell from about 0.489 at the initial target to roughly 0.039 in the long-run search. No complete candidate proof ever reached the verifier.

The search therefore moved from a **breadth-explosion failure** in 3.0 to a **high-relevance stagnation / open-goal saturation failure** in 3.1.

The current structural relevance measure is too coarse: token overlap can rate states such as `|- { A , B } = A`, `|- A = { A , B }`, and repeated pair equalities as highly target-relevant even when the unresolved proof state is worsening.

Professor also remained insufficiently discriminating: of 149,277 prioritized successors, 148,053 were classified `high` and 1,224 `normal`.

## Important control-loop diagnosis

Once the early search had accumulated a frontier near half the allowed maximum, the controller's absolute-frontier pressure remained above the threshold that permits stagnation-driven re-expansion of creativity. As a result, even after recent branching had fallen to near 1 child/expansion, breadth, divergence, and risk remained pinned at their lower bounds while depth, heuristic weighting, node selection, and resource bias remained pinned at their upper bounds.

This suggests that the next controller should distinguish **frontier size** from **frontier growth rate / recent branching pressure**. A large historical backlog should not permanently prevent a stagnating search from reopening creativity.

A second correction is needed to the objective: target relevance should incorporate proof-state quality (especially open-goal count and progress) rather than mostly token overlap.

## Replication

The accidental second run `33782557915` used the same core search/controller hashes and reproduced the scientific outcome exactly:

- status `UNKNOWN`
- reason `expansion_budget`
- 20,000 expansions
- 149,277 generated children
- 1,250 control updates
- exactly the same final 11D creativity vector

Only runtime/resource noise differed slightly: search time was 136.7190 s and peak RSS was 494,724 KB.

This gives an unplanned but useful determinism/reproducibility check.

## Defensible next experiment

Do not simply raise the expansion budget.

For DATA MIND 3.1 Experiment 006, keep the frozen PRCOM problem and verifier boundary, but modify only the control objective/controller so that:

1. branching pressure depends primarily on recent frontier growth / generated-per-expansion rather than absolute frontier occupancy;
2. stagnation can reopen breadth/divergence after branching is controlled even if a large old frontier remains;
3. relevance incorporates open-goal burden and demonstrable partial progress, preventing token-overlap fixation;
4. creativity coordinates are discouraged from remaining pinned at 0 or 1 for long periods unless the measured error continues to justify the boundary;
5. Professor priority is made materially selective while retaining the protected non-destructive search baseline.

Experiment 005 therefore counts as a successful control-engineering result but not a theorem-settlement result.
