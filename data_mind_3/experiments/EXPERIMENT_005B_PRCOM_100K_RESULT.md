# DATA MIND 3.1 Experiment 005B PRCOM — 100K Result

Date: 2026-09-03

GitHub Actions run: `33783278369`

Target: `prcom`, `|- { A , B } = { B , A }`

Frozen set.mm SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`

## Outcome

Status: `UNKNOWN`

Reason: `expansion_budget`

Verifier-accepted PRCOM proof: none

Verifier candidate checks: 0

Expansions: 100,000 / 100,000

Generated children: 349,906

Mean generated children per expansion: 3.49906

Final frontier: 121,331 / 200,000

Search time: 580.2709 s

Wall time: 590.03 s

Peak RSS: 801,564 KB

Adaptive-control updates: 6,250

Warm-start experience rows: 0

Final creativity vector was exactly the same as Experiment 005:

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

At expansion 100,000 the controller still reported recent branching near 1.25 children per expansion, drift error 0.0, stagnation error 1.0, frontier pressure 0.606655, and the same boundary-pinned creativity vector. The final expanded goal was `|- B = { A , B }` with 24 open goals.

## Comparison with Experiment 005

Experiment 005 stopped at 20,000 expansions with no proof and 149,277 generated children.

Experiment 005B increased only the expansion cap to 100,000. It executed the additional 80,000 expansions, did not hit the 200,000 frontier, did not time out, and did not run out of memory. It still produced no terminal proof candidate and no verifier check.

Therefore the 20,000-expansion budget was not the immediate bottleneck in the sense that a PRCOM proof was waiting modestly beyond that cap. A five-fold expansion increase preserved the same controller endpoint and the same high-relevance/open-goal stagnation mode.

This does not prove that no still-larger budget could ever succeed, but it substantially strengthens the diagnosis that the current objective/controller is stuck in an unproductive basin rather than merely under-budgeted.

The next defensible change is to alter the objective/controller, not simply raise the expansion cap again.
