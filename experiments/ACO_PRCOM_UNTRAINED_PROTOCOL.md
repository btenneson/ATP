# Untrained ACO on `prcom` — preregistered pilot

## Question

Can the same **untrained ant-colony optimization idea** that succeeded on the Ocean `L*=4000` benchmark settle the Metamath theorem `prcom`, without any learned prior, revision controller, target-proof replay, or downstream theorem access?

## Frozen scientific design

This is an ACO-only pilot. It does **not** use:

- set.mm training or a learned model,
- dissatisfaction / revision / group inversion,
- the historical proof of `prcom`,
- any theorem after `prcom`,
- a BFS or shortest-proof oracle.

The pinned historical `set.mm` file is used only as the formal environment and source of legal assertions preceding `prcom`.

### ACO parameters carried over from the successful Ocean control

- `alpha = 1.0`
- `beta = 0.0` (no heuristic term in move selection)
- `rho = 0.15`
- `partial_q = 5.0`
- `partial_elite = 4`
- seed `2301`

Domain-sized finite controls:

- 200 batches
- 8 ants per batch
- 64 proof-state applications per ant
- maximum 16 simultaneously open goals

At a proof state, the ant enumerates only legal prefix assertions that unify with the selected open goal. It samples among those legal successors with probability proportional to `pheromone[label]^alpha`. Since `beta=0`, no target-distance or structural heuristic affects the actual move probability.

### Pre-settlement reinforcement

Because a theorem prover may have no complete proof in the first batch, unsuccessful ants may reinforce partial proof prefixes. The progress signal is the repository's simple structural proof-distance proxy

`h_hat = 1 + open_goal_count + 0.015 * total_goal_token_count + 0.02 * tanh(meta_variable_count / 8)`.

This signal is computed only from the ant's current legal proof state. It does not inspect `prcom`'s historical proof. The best prefix of each ant is the prefix attaining its lowest `h_hat`. After each unsuccessful batch, pheromone evaporates by `rho`; the four ants with lowest best `h_hat` reinforce the labels in their best prefixes in proportion to their improvement from the initial `h_hat`.

### Control

Run an otherwise identical stochastic proof search with pheromone learning disabled. This distinguishes the effect of colony memory from repeated randomized proof attempts.

## Verification and leakage guard

The search index and grammar stop strictly before `prcom`. Access to `mm.proofs['prcom']` is guarded and raises an exception. If an ant closes all goals, its emitted Metamath certificate is checked independently by the frozen verifier under a fresh synthetic label carrying the exact `prcom` assertion and DV conditions.

## Outcomes

Report separately for ACO and no-learning control:

- VERIFIED settlement or bounded UNKNOWN,
- total ant proof-state applications,
- candidate-unification transactions,
- batch / ant of first settlement,
- emitted proof length if verified,
- best structural `h_hat` reached.

A bounded UNKNOWN is not a theorem failure. Infrastructure or verifier errors are not scientific outcomes.
