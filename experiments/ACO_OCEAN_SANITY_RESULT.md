# ACO Ocean known-theorem sanity result

Date: 2026-08-28
GitHub Actions run: `33218782182`
Source commit: `2a6013bc76db46559fa8f533ac7788be5c8907d8`

This is Experiment 1 from `experiments/ACO_NOTALD_TRANSFER_PLAN.md`. It is an implementation sanity check, not the NOTALD transfer claim.

## Ground truth

The repository Ocean generator produced one frozen implication instance at `L*=20`, seed 1. Its independent BFS check reported exactly 20 as the shortest source-to-target distance. The generated graph had 459 vertices and 461 directed implication edges.

## ACO outcome

The ant-colony solver settled the instance and emitted a 20-step chain. The independent checker re-parsed the TPTP problem and verified that the chain began at the declared source, ended at the declared target, and that every step was one of the declared implication axioms.

Recorded ACO metrics:

- solved: yes;
- independently verified proof-chain length: 20;
- successful ants: 192/192 over the full sanity run;
- first success: colony iteration 1;
- total expansions: 6,178;
- total edge-selection/search transactions: 6,178;
- final mean pheromone on the best verified path divided by global mean pheromone: 16.6769551230.

The preregistered sanity criteria therefore passed.

## No-learning control

Under the otherwise identical run with pheromone learning disabled:

- solved: yes;
- best proof-chain length: 20;
- successful ants: 192/192;
- first success: iteration 1;
- total expansions: 14,168;
- total transactions: 14,168;
- reinforcement ratio: 1.0.

Thus the learning run used fewer aggregate expansions in this sanity run. That comparison remains descriptive because Experiment 1 was preregistered only to establish implementation plausibility.

## Important limitation exposed by the sanity run

Both ACO and the no-learning control found a proof in the first colony iteration. In the initial implementation, pheromone is deposited from complete successful paths only after a colony iteration. Consequently, complete-path pheromone cannot improve the time to the *first* settlement if the proof is already found before the first update.

Before the high-n transfer experiment, the search therefore needs a prospectively documented partial-progress reinforcement rule if ant-colony learning is intended to help *before* the first proof is found. A suitable rule must not use the hidden planted route or BFS distance.
