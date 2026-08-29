# Guided verifier-gated ACO on `prcom` — revision 2 protocol

## Why this revision exists

The frozen untrained ACO pilot (`aco-prcom-untrained`) reached the GitHub Actions 60-minute limit before producing a final result file. The pilot is preserved unchanged. This revision is a new experiment, not a post-hoc rewrite of the original preregistration.

The revision addresses four limitations of the pilot:

1. the structural progress coordinate `h_hat` was measured but did not guide move choice (`beta=0`);
2. every ant restarted from the root, so useful partial proof states were discarded;
3. the depth and open-goal caps were fixed at 64 applications and 16 open goals;
4. quantitative results were written only after an entire arm finished, so a hard timeout could erase the scientific record.

## Scientific question

Can an untrained, target-proof-blind ACO controller make measurable or verified progress on the Metamath theorem `prcom` when it is allowed to use only the current legal proof state, prefix assertions before `prcom`, verifier feedback, and colony memory?

This experiment still uses **no**:

- set.mm training or learned model,
- historical proof of `prcom`,
- theorem after `prcom`,
- revision / dissatisfaction / group-inversion controller,
- shortest-proof oracle or target-distance oracle.

The pinned historical `set.mm` is only the formal environment and source of legal assertions preceding `prcom`.

## Revision-2 controller

### Structural guidance

For a proof state `s`, retain the same frozen structural coordinate

`h_hat(s) = 1 + open_goal_count + 0.015 * total_goal_token_count + 0.02 * tanh(meta_variable_count / 8)`.

For legal successors `a` from state `s`, let `s_a` be the successor state. The exploitation score is

`score(a|s) = pheromone[a]^alpha * exp(-beta * (h_hat(s_a) - min_b h_hat(s_b)))`.

The subtraction of the minimum is only numerical stabilization. It does not change the ranking induced by the exponential factor.

Frozen defaults:

- `alpha = 1.0`
- `beta = 1.25`
- `rho = 0.15`
- `epsilon = 0.10`
- `partial_q = 5.0`
- `partial_elite = 4`
- elite partial-state pool size `4`
- seed `2301`

### Epsilon exploration

Move probability is the mixture

`P(a|s) = (1-epsilon) * score(a|s)/sum_b score(b|s) + epsilon/|A(s)|`,

where `A(s)` is the set of legal successors enumerated at `s`.

Therefore every legal successor has probability at least `epsilon/|A(s)|`, regardless of pheromone or structural score.

### Elite partial-state retention

After an unsuccessful batch, the best actual partial proof states may seed later ants. This differs from merely reinforcing theorem labels: a later ant may continue from a verified-legal partial construction rather than restarting every time.

At least one ant in every batch is forced to start from the original root goal. This root-restart condition is retained specifically so the completeness statement below is not destroyed by elite-state exploitation.

### Iterative resource expansion

The run uses the frozen stage schedule

- stage 1: `ant_budget=64`, `max_open=16`
- stage 2: `ant_budget=128`, `max_open=32`
- stage 3: `ant_budget=256`, `max_open=64`
- stage 4: `ant_budget=512`, `max_open=128`

The finite GitHub experiment is still bounded; these values are not claimed sufficient for `prcom`. The mathematical completeness statement below concerns the natural unbounded continuation in which the resource schedule eventually dominates every finite proof depth and width.

### Checkpointing and graceful wall-clock stop

ACO and the no-learning control run as separate workflow jobs. Each batch appends a JSON checkpoint containing at least:

- batch and stage,
- best `h_hat` in the batch and globally,
- applications and unification transactions,
- number of root ants,
- retained elite-state count,
- observed branching diagnostics,
- elapsed wall time.

The Python process has an internal wall-clock limit shorter than the GitHub job limit so it can write a final bounded result before the runner is killed.

## No-learning control

The control receives the same theorem prefix, verifier, seed family, stage schedule, application limits, and wall-clock rule, but disables colony learning:

- no pheromone update,
- `beta=0`,
- no elite partial-state continuation.

Thus it is a repeated randomized legal proof search baseline rather than another adaptive controller.

## Verification and leakage guard

The grammar and theorem index stop strictly before `prcom`. Any access to `mm.proofs['prcom']` after the guard is installed raises an exception. If an ant closes every goal, the emitted Metamath certificate is checked by a fresh verifier under a synthetic label carrying the exact `prcom` assertion and DV conditions.

A verifier-rejected closed-goal construction is an infrastructure/algorithm error, not a scientific settlement.

## Mathematical result: relative probabilistic completeness

### Theorem (epsilon-ACO probabilistic completeness relative to the frozen legal-move enumerator)

Fix a target that has a finite verifier-accepted proof represented by a legal move sequence of length `m`. Assume:

1. along that proof route, the legal-move enumerator returns every required move;
2. at each state on that route there are at most `B < infinity` legal successors;
3. the resource schedule eventually permits at least `m` applications and at least the maximum open-goal width `W` attained by the route;
4. `epsilon > 0`;
5. after resources are sufficient, infinitely many ants are forced to restart from the root.

Then the probability that the epsilon-ACO search eventually constructs that proof is `1`, independently of the pheromone history and independently of the accuracy of `h_hat`.

More precisely, every sufficiently resourced root ant has conditional probability at least

`q = (epsilon / B)^m > 0`

of selecting the fixed proof route. After `N` such root ants, the probability of no success is at most

`(1-q)^N`,

which tends to `0` as `N -> infinity`.

### Proof

At any state on the fixed proof route, epsilon exploration assigns each legal successor probability at least `epsilon/|A(s)| >= epsilon/B`. Hence, conditional on any prior history of pheromone values, elite states, or failed ants, a sufficiently resourced root ant follows all `m` required moves with probability at least `(epsilon/B)^m = q`.

Let `F_N` be the event that the first `N` sufficiently resourced root ants all fail to traverse that route. Since the conditional failure probability of the next root ant is at most `1-q`, induction gives

`P(F_N) <= (1-q)^N`.

Because `q>0`, the right side converges to zero. Therefore the probability of eventually constructing the fixed proof is one. Independent verifier acceptance then gates whether a constructed closed-goal object is reported as settlement. QED.

### Scope of the theorem

This is **not** a claim that finite revision-2 budgets will prove `prcom`, nor that ACO decides arbitrary mathematical theories. It is a relative search theorem: if a finite proof exists in the frozen representation, the enumerator exposes its moves, resources eventually become sufficient, and root exploration continues forever with a positive exploration floor, pheromone cannot permanently suppress that proof route.

## Finite-run outcomes

For each arm report:

- VERIFIED or bounded UNKNOWN,
- proof length if VERIFIED,
- batches and ants run,
- mandatory root ants run,
- total proof-state applications,
- candidate-unification transactions,
- best structural `h_hat`,
- maximum observed legal branching as a diagnostic only,
- whether the internal wall-clock stop was reached,
- complete checkpoint trace.

A bounded UNKNOWN is not a theorem failure.