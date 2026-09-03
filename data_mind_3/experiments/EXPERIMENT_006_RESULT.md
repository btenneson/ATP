# DATA MIND 3.1 Experiment 006 — PRCOM Child Knob Play Result

Date: 2026-09-03

GitHub Actions run: `33785435595`

Target: `prcom`, `|- { A , B } = { B , A }`

Frozen set.mm SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`

## Outcome

- status: `UNKNOWN`
- reason: `expansion_budget`
- verifier-accepted PRCOM proof: none
- terminal PRCOM verifier candidates: 0
- expansions: 20,000 / 20,000
- generated children: 238,364
- mean children/expansion: 11.9182
- final frontier: 192,748 / 200,000
- search time: 143.9994 s
- wall time: 151.26 s
- peak RSS: 676,956 KB
- control updates: 1,250
- experience input: none

The run therefore did not settle PRCOM.

## Child-play outcomes

The child started 7 knob trials:

- kept: 2
- rolled back: 5
- group-inverse trials: 0

The inverse operator did not fire because the preregistered extreme condition required at least 8 rejected fine-tuning trials plus severe stagnation and low branching. Only 5 trial results were rollbacks before frontier-emergency pressure prevented additional play. This is expected behavior: group inversion was intentionally rare rather than forced.

### Trial history

1. `search_breadth +0.06`, expansion 240-304: rollback.
2. `divergence +0.06`, expansion 336-400: keep.
3. `risk_tolerance +0.06`, expansion 400-464: rollback.
4. `abstraction_level +0.06`, expansion 672-736: rollback.
5. `heuristic_weighting +0.06`, expansion 736-800: rollback.
6. `goal_selection +0.06`, expansion 800-864: keep.
7. `node_selection +0.06`, expansion 864-928: rollback.

Thus the first empirical child-play signal on PRCOM favored increased divergence and increased goal-selection emphasis, while the tested positive moves in breadth, risk, abstraction, heuristic weighting, and node selection did not improve the local play loss in their trial windows.

## Comparison with Experiment 005

Experiment 005 at the same 20,000-expansion cap generated 149,277 children (7.46385 per expansion) and ended with frontier 104,233.

Experiment 006 generated 238,364 children (11.9182 per expansion) and ended with frontier 192,748. Child play therefore spent more search breadth than Experiment 005, while remaining dramatically below Experiment 004's approximately 1,049.6 children per expansion.

The increased breadth was not enough to prove PRCOM and brought the search close to the 200,000 frontier limit.

## Open-goal trajectory

Experiment 006 delayed open-goal saturation substantially:

- first state with >= 8 open goals: expansion 875
- >= 12: expansion 1,023
- >= 16: expansion 1,059
- >= 20: expansion 1,091
- >= 24: expansion 1,123

Experiment 005 first reached 24 open goals at expansion 339. Thus child play delayed 24-goal saturation by a factor of about 3.31.

However, after saturation, Experiment 006 remained overwhelmingly at 24 open goals. Mean open-goal count across the run was approximately 22.94, and the final expanded state still had 24 open goals.

Partial Credit still collapsed from approximately 0.48924 initially to approximately 0.03917 at the end.

## Relevance / drift

The child-play run did not reintroduce the Experiment 004 T./F. drift:

- 0 / 20,000 expanded goals contained `T.` or `F.`
- 20,000 / 20,000 retained `A` or `B`
- 20,000 / 20,000 retained pair-brace syntax
- mean logged target relevance was approximately 0.99917

So the remaining problem is still not gross syntactic target drift. The search remains highly target-looking while accumulating unresolved obligations.

## Professor selectivity

Professor remained weakly discriminating:

- total prioritized successors: 238,364
- `high`: 237,140
- `normal`: 1,224
- `low`: 0

Thus almost every generated child was still categorized as high priority.

## Why play stopped before an inverse

At expansion 928, frontier occupancy had reached about 87.3%, crossing the child-play emergency-frontier threshold of 85%. The child therefore stopped initiating new playful trials while the ordinary safety controller tightened the search.

By expansion 2,000, recent branching had fallen near 1 child/expansion, but the large historical frontier backlog remained above the emergency threshold. At expansion 20,000 the frontier was still about 96.37% of its limit. Consequently no further child trials were permitted and the inverse threshold was never reached.

## Important reversibility caveat discovered by Experiment 006

The current child implementation is **knob-reversible but not fully search-state-reversible**.

When a trial is rolled back, the creativity vector is restored to its pre-trial value. However, children generated during that 64-expansion trial have already been inserted into the global frontier. Rolling the knob back does not remove those speculative frontier states.

Therefore it would be inaccurate to call the present micro-experiment fully reversible at the search-process level.

A genuinely reversible child trial should use a sandbox/transactional frontier:

1. snapshot the incumbent creativity state;
2. route states generated by the trial into a trial-local frontier or tagged transaction;
3. evaluate the trial;
4. if kept, commit/merge the useful trial states;
5. if rejected, discard the trial-local states and restore the incumbent knobs;
6. keep the independent verifier and protected baseline unchanged.

This transactional interpretation fits the user's requirement that the child be allowed to play without irreversibly contaminating the main search when an experiment is rejected.

## Interpretation

Experiment 006 is evidence that child knob play can alter the trajectory in a measurable way: it delayed open-goal saturation and identified two locally beneficial knob directions. But the current trial mechanics did not escape the stagnation basin, did not reach the rare inverse regime, and consumed enough speculative frontier capacity that play was shut down early by the emergency guard.

The next defensible child-play change is not to force a group inverse. It is to make child trials genuinely transactional/reversible so rejected experiments do not leave frontier debris. Once that is in place, rare group-inverse trials can occur under the originally intended extreme conditions without permanently contaminating the main search.
