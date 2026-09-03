# DATA MIND 3.1 Experiment 006 — PRCOM Child Knob Play Freeze

Date: 2026-09-03

## Question

Can reversible child experimentation over the 11-dimensional creativity vector escape the high-relevance/open-goal stagnation basin observed in Experiments 005 and 005B, while preserving the branching control gained by DATA MIND 3.1?

## Frozen target and verifier boundary

- target: `prcom`
- statement: `|- { A , B } = { B , A }`
- frozen set.mm commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`
- frozen set.mm SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`
- independent verifier: `metamath.py`
- verifier semantics are unchanged from Experiments 004/005/005B.

## Search budget

For direct comparison with Experiment 005:

- candidate cap: 64
- max expansions: 20,000
- max depth: 24
- max open goals: 24
- max frontier: 200,000
- timeout: 1,800 seconds
- control interval: 16 expansions
- initial creativity vector: all eleven coordinates = 0.5
- experience input: none

## Scientific change from Experiment 005

Enable `--child-knob-play`.

The child performs reversible micro-experiments over the 11 creativity knobs:

1. Under controlled branching and sustained stagnation, choose one knob from a deterministic round-robin schedule across three groups: exploration, guidance, commitment.
2. Ordinary play is fine tuning: one knob moves by +/-0.06 for four control intervals (64 expansions).
3. The trial is evaluated by a play loss emphasizing current partial credit, stagnation, recent branching, and drift; absolute frontier backlog is excluded from the trial score.
4. If loss improves, keep the move. If not, restore the complete pre-trial creativity vector.
5. Absolute frontier occupancy no longer acts as ordinary creativity pressure in child-play mode. Recent branching is the normal safety signal; frontier occupancy above 85% becomes an emergency brake.
6. After at least eight rejected fine-tuning trials, with stagnation >= 0.95 and recent branch error <= 0.05, one selected knob becomes eligible for an extreme group-inverse trial.

## Group inverse definition

A normalized knob `c in [0,1]` is embedded into the ambient additive group `(R,+)` by

`x = 2c - 1`.

The additive inverse is

`x -> -x`.

Mapping back to normalized knob coordinates gives the involution

`c -> 1 - c`.

This is explicitly an extreme escape operator, not a large fine-tuning step. It is subject to the same keep-or-rollback evaluation as every other child trial.

## Integrity constraints

- no target proof is exposed to the search;
- no PRCOM-derived experience is loaded;
- no verifier rule is changed;
- Sentinel remains authoritative for hard budgets;
- the child may alter search behavior but can never certify truth;
- all child trial starts, results, inversions, keeps, and rollbacks are historian-visible.

## Primary outcomes

1. verifier-accepted PRCOM proof or not;
2. expansions and generated children;
3. children per expansion;
4. final frontier and resource use;
5. number of child trials;
6. number of kept vs rolled-back trials;
7. number and identity of group-inverse trials;
8. final 11D creativity vector;
9. open-goal trajectory and whether the 24-open-goal stagnation basin is escaped;
10. whether any terminal proof candidate reaches the verifier.

This experiment is a child-play architecture test, not a shortcut/trading experiment. Certified shortcut machinery is not newly added here.
