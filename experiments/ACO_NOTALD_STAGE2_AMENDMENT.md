# ACO -> NOTALD Stage 2 amendment

Date: 2026-08-28

This amendment is written after Experiment 1's implementation-sanity result and before any high-n transfer instance is run with the Stage 2 controller.

## Why an amendment is needed

Experiment 1 exposed a limitation of the first ACO implementation: both the learning and no-learning searches found a complete proof during the first colony iteration, while pheromone was deposited only after complete successful paths. Such reinforcement cannot improve the time to the first settlement when the first proof arrives before the first pheromone update.

For Stage 2, the ACO mechanism is therefore changed prospectively so that bounded unsuccessful ants can reinforce *partial progress* before any complete proof exists.

## Partial-progress reinforcement

An ant performs bounded stochastic depth-first proof search with backtracking. During its search it records the deepest simple source-rooted prefix it reached. This depth is observable from the search trajectory itself and does not use the planted route, target distance, reverse reachability, BFS ground truth, or any hidden benchmark solution.

If a whole colony batch finishes without a verified settlement, the four deepest partial prefixes in the batch deposit pheromone. For a selected prefix p of depth d, with d_max the greatest partial depth in that batch, the per-edge deposit is

    Delta tau_e = q_partial * (d / d_max) / |p|,  for each e in p.

Pheromone then affects the edge ordering seen by later batches. If a complete source-to-goal chain is found, the solver halts immediately; the chain is independently checked before it is counted as a settlement.

The Ocean-local destination heuristic is disabled in Stage 2 (`beta=0`) so that the transfer comparison isolates colony memory rather than a hand-designed target-independent graph heuristic.

## What is learned from all of set.mm

Stage 2 learns a representation-independent *colony-memory prior* from every complete logical proof in one pinned `set.mm` revision. It does not attempt to transplant set.mm symbol names into Ocean.

For every decompressed theorem proof, retain only logical assertion steps. Let c_t(j) be the number of previous occurrences of logical assertion j before step t.

### Pheromone exponent alpha

Condition on proof steps that reuse an assertion already seen earlier in the same proof. Fit alpha by maximum likelihood under the reinforcement model

    P_alpha(j at t | reuse, history)
      = c_t(j)^alpha / sum_k c_t(k)^alpha,

where the denominator ranges over assertions already used in that proof. Alpha is selected on a frozen grid from 0.0 through 3.0 in increments of 0.1 using the entire complete logical-proof corpus.

### Evaporation rho

For each repeated logical assertion, record the gap g in logical proof steps since its preceding occurrence. Let g_bar be the mean reuse gap over the entire corpus. Define the learned evaporation prior

    rho = 1 - exp(-1 / g_bar).

This makes longer empirical reuse memory correspond to slower pheromone evaporation.

The resulting `alpha` and `rho`, the pinned set.mm SHA-256, corpus counts, and fit diagnostics are written to a JSON artifact and hashed. That artifact is frozen before the high-n problem is generated or searched.

Other ACO parameters are held fixed between transfer and control: partial-progress rule, partial deposit strength, colony size, ant budget, number of batches, random seed, beta=0, and independent verification.

## Stage 2A high-n feasibility pilot

Before touching the planned primary seeds 1-20, run one separate high-n pilot:

- Ocean shortest proof length: `L*=4000`;
- pilot generator seed: `2301`;
- colony batches: 40;
- ants per batch: 8;
- maximum expansions per ant: 8,000;
- partial elite prefixes per unsuccessful batch: 4;
- `beta=0`;
- identical random seed for trained and control search;
- trained search uses the frozen set.mm-derived alpha and rho;
- control search uses alpha=1.0 and rho=0.15.

The pilot seed 2301 is not one of the planned primary seeds 1-20. Its outcome is a feasibility result and will not be pooled into the primary 20-instance inference. If the pilot motivates implementation changes, those changes must be documented before running primary seeds 1-20.

## Measurements

Record independently verified settlement, proof length, expansions to first settlement, edge-selection/search transactions, ants consumed, colony batches consumed, deepest partial prefix before settlement/timeout, wall time, and the frozen learned prior.

A bounded failure is `UNKNOWN`, not false. Infrastructure/protocol failures are recorded separately and are not scored as scientific negative results.
