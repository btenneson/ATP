# Predator ATP Lineage and Roadmap

**Project lead:** Brian Tenneson  
**Repository:** `btenneson/ATP`  
**Research record date:** August 4, 2026  

This page records the Predator automated-theorem-proving lineage, separates established results from hypotheses, and preserves the intended development path through Predator 8.005.

## Scientific reporting rule

A search result and a mathematical result are different things.

- `VERIFIED_PROOF` means an independently checked Metamath certificate exists.
- `BOUNDED_UNKNOWN` means the configured search budget ended without a certificate.
- `FRONTIER_EMPTY` means no legal search states remained under the configured bounds.
- `FAULT` means an implementation problem prevented a valid experiment.
- `RUNNING` is only a process status.

A timeout, budget exhaustion, frontier collapse, or software fault is never evidence that the target theorem is false or independent.

## Version lineage

### Predator 7.1

Predator 7.1 is the principal symbolic baseline. Its important engineering features include Metamath parsing, formula construction from grammar trees, logical proof search, Robinson-style unification, ordered essential-hypothesis handling, disjoint-variable checking, and independent certificate verification.

Predator 7.1 established the project's baseline methodology: search may be heuristic, but acceptance must be formal and reproducible.

Historical records include both verified positive controls and bounded-unknown targets. Resource settings, hardware, seeds, environment hashes, and verifier results should accompany every comparison.

### Early Predator 8 and Predator 8.001

The early Predator 8 line introduced the population-search concept: multiple agents or search profiles, learned ranking, controlled creativity, shared verified information, and formal verification as final authority.

These versions are preserved as historical source artifacts. They should not silently replace later experimental implementations.

### Predator 8.002

Predator 8.002 provided the first concrete ML-guided proof-search evidence in the current line. In the recorded `prcom` experiment, Predator 8.002 produced an independently verified proof at 2,633 expansions, while the matched unguided bounded condition remained unknown at 5,000 expansions.

This was evidence that learned ranking could improve the allocation of a fixed search budget. It was not evidence that every target or every trained model would improve.

### Predator 8.003

Predator 8.003 added an autonomous train-checkpoint-search-document workflow. For the `sgrpcl` experiment it completed broad chronological training and saved a model.

Recorded training statistics:

- 131,078 trace events processed
- 129,269 retained policy events
- 764,438 labeled examples
- model SHA-256: `90a1c0da192d76d4695ec11593dc58bff603939ca58fa05ef84d5913f60b084a`
- validation MRR approximately 0.97056
- test MRR approximately 0.95689

The first `sgrpcl` search attempt ended after only five expansions. That result is not accepted as a meaningful 80,000-expansion comparison.

Two software-control problems were identified:

1. rough candidates were ranked and capped before full unification, so inapplicable candidates could consume the cap and leave no executable successors;
2. the wrapper classified ordinary exit code 1, meaning completed without proof, as a catastrophic error.

Therefore the historical 8.003 result is classified as an invalidated search trial caused by implementation/control behavior, not as evidence against the trained model.

### Predator 8.003R — planned repaired control

Predator 8.003R will preserve the saved 8.003 model and broad chronological training condition. It will change only the search-control defects required to produce a valid run.

Required repair:

```text
rough retrieval
→ rename variables apart
→ full unification
→ construct legal applications
→ rank legal applications
→ apply candidate cap
→ generate successor states
```

It must also distinguish ordinary no-proof completion from an actual fault and record frontier diagnostics.

The primary hypothesis is that 8.003R will not bail after a trivial number of expansions. A weaker model should ordinarily search less efficiently, reach its budget, empty its legal frontier, or find a proof—not be mislabeled as a crash. This remains a hypothesis until the repaired rerun is completed.

### Predator 8.004 — dense subject-conditioned experiment

Predator 8.004 tests subject-conditioned blind preparation. The visible target statement may be used to identify the mathematical subject and select chronologically legal prior material, while the withheld proof, proof-derived route, downstream declarations, and target-search feedback remain inaccessible.

The preliminary `sgrpcl` dense curriculum contains:

- 2,075 selected pre-target theorems
- 47,780 logical transitions
- 23,892 distinct exact intermediate goals
- 50 directly relevant magma, semigroup, submagma, or homomorphism theorems
- 1,238 logical transitions from those 50 local-algebra theorems

This is substantially denser local preparation than the six theorem-level semigroup examples identified in the 8.003 broad-training condition. The counts are not perfectly interchangeable because the 8.004 local category deliberately includes neighboring algebraic material.

The `prcom` calibration produced verified certificates under both dense-uniform and dense-balanced training. The ongoing `sgrpcl` experiment must be allowed to reach its own proof, budget, frontier, or fault condition. Long runtime alone does not establish correctness or progress.

Predator 8.004 may contain multiple implementation changes mixed together. Its final result, whether success or failure, must therefore be interpreted alongside 8.003R and the planned controlled reconstruction.

### Predator 8.005 — planned controlled reconstruction and improvement

Predator 8.005 will be built on the repaired 8.003R software foundation rather than directly inheriting the historically defective 8.003 search behavior.

Planned architecture:

```text
Predator 8.003R stable legal-first foundation
+ Predator 8.004 subject-conditioned density
+ auditable training improvements
= Predator 8.005
```

The first 8.005 condition should port the existing 8.004 mathematical curriculum and training method as faithfully as possible. A separately named condition may then improve training—for example, source-theorem balancing, same-goal legal-action negatives, hard-negative mining, a proof-depth value model, local readiness tests, symbol-renaming controls, and protection against catastrophic forgetting.

Recommended controlled comparison:

| Condition | Search foundation | Preparation/training | Purpose |
|---|---|---|---|
| Original 8.003 | historical defective ordering | broad chronological model | historical diagnostic only |
| 8.003R | repaired legal-first search | same saved broad model | valid broad-transfer control |
| 8.004 | current 8.004 implementation | dense subject-conditioned curriculum | prototype dense experiment |
| 8.005-A | repaired 8.003R foundation | unchanged 8.004 density method | controlled reconstruction |
| 8.005-B | repaired 8.003R foundation | density plus declared training improvement | next experimental advance |

If 8.004 fails, that does not invalidate density. It may expose another implementation defect, insufficient search, or inadequate training. If 8.004 succeeds, 8.005 remains necessary to test whether the result is reproducible on the cleaner foundation.

## Immediate sequence

1. Preserve the ongoing Predator 8.004 run without interruption.
2. Preserve all original source bundles, logs, reports, manifests, models, certificates, and hashes.
3. Build Predator 8.003R in a separate directory; never overwrite historical 8.003.
4. Run the saved 8.003 model under repaired legal-first search with frozen controls.
5. Record proof, budget, frontier, or fault outcome honestly.
6. Audit the actual source-level differences between 8.003, 8.003R, and 8.004.
7. Build Predator 8.005-A from 8.003R plus the unchanged 8.004 density technique.
8. Add any improved training method only as a separately named 8.005-B condition.

## Reproducibility requirements

Every published run should preserve:

- exact command
- start and end timestamps with timezone
- source commit
- target and formal-environment hash
- model and manifest hashes
- random seed
- hardware and software environment
- expansion, depth, width, memory, and wall-clock limits
- progress and frontier diagnostics
- raw certificate
- independent-verifier output
- final outcome category

The project should prefer a clean negative or fault report over an inflated performance claim. Historical failures are useful when preserved precisely enough to guide the next controlled experiment.
