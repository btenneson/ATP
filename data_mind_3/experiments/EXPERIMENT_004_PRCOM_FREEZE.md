# DATA MIND 3 — Experiment 004: PRCOM cold Metamath bridge

Status: frozen before execution.

## Question

How many DATA MIND 3 search-state expansions are required before the first independently verifier-accepted proof of the Metamath theorem `prcom`?

## Frozen target and source

- Target label: `prcom`.
- Target statement expected from source: `|- { A , B } = { B , A }`.
- Frozen historical set.mm commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`.
- Frozen set.mm SHA-256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`.
- Only assertions occurring before `prcom` are legal search assertions.
- The stored proof of `prcom` is parsed only far enough to skip it and is discarded; it is never exposed to the search/controller state.
- No PRCOM-derived BANK item, shortcut, learned model, or prior proof is loaded.

## Expansion metric

One expansion is exactly one nonterminal search state removed from the frontier and actually expanded by generating its legal successor states. Duplicate states discarded before successor generation are not counted as expansions. Generated children are reported separately.

The expansion counter stops only when an independently verifier-accepted proof is produced. A terminal candidate rejected by the verifier does not settle the target and search continues. Budget exhaustion or timeout is `UNKNOWN`.

## Fresh generalized bridge v0.1

The implementation is theorem-label parameterized rather than PRCOM-specific. It contains a fresh Metamath database parser, sequence-substitution matcher, legal-prefix assertion adapter, typed search states, structural Librarian, Partial Credit measurement, Scout successor scoring, Professor admission telemetry, Quicksand duplicate-state detection, Sentinel budgets, Historian trace, proof linearization, and an external verifier boundary.

Explicit v0.1 capability boundary: an assertion application is used only when every mandatory variable is constrained by matching the assertion conclusion to the current goal. This is a generic restriction, not a PRCOM special case.

## Primary configuration

- candidate shelf cap: 64
- match alternatives per candidate: 4
- maximum proof-search depth: 24
- maximum simultaneous open goals: 24
- maximum search expansions: 20,000
- maximum frontier: 200,000
- search timeout: 1,800 seconds
- verifier timeout per candidate: 600 seconds

## Authority and controls

Search heuristics cannot certify mathematics. The independent Metamath verifier is the sole settlement authority. Sentinel can stop computation but cannot convert exhaustion into refutation. Historian records expansion, retrieval, Scout/Professor decisions, Quicksand duplicate discards, Sentinel stops, and verifier decisions.

## Historical comparison

The earlier Predator 8.027 finite cap-8/depth-4/open-goal-8 exhaustive PRCOM bank found its first externally verified certificate at expansion 362 and exhausted that declared finite space after 2,577 nonterminal expansions and 48,224 generated children. Experiment 004 does not reuse its implementation or proof bank. The historical number is retained only as a comparison point; scheduler, candidate shelf and pruning differ, so any comparison must state those differences.
