# ALD Creativity Profiles — Bootstrap Contract

This note records how creativity controls are represented in the ALD-LEM-01 codebase so later experiments do not silently change what a profile means.

## Principle

The profile is a vector of **search controls**, not a measured creativity score. Measured creativity must come from verified outcomes under frozen information, verifier, hardware, seeds, and resource budgets.

The current profile fields are:

- `temperature`
- `candidate_width`
- `breadth_depth_balance`
- `novelty_pressure`
- `restart_rate`
- `lemma_construction_budget_fraction`
- `bank_reuse_limit`
- `counterfactual_admission_rate`
- `seed`

Every profile is hashable and its name/hash is written to the run log.

## Operational now

The creativity-controlled runner now makes these controls behavioral:

1. `candidate_width` caps ordinary legal proof actions and also limits generated lemma candidates.
2. `temperature` adds seeded stochastic perturbation to the transparent structural action ranking.
3. `counterfactual_admission_rate` controls whether a legal action outside the ordinary candidate cap is admitted and tried first.
4. `lemma_construction_budget_fraction` controls how much of an activation may be spent constructing a reusable verified lemma before returning to the settlement target.
5. `bank_reuse_limit` limits how many verifier-certified bank lemmas are offered to a proof search activation.
6. `seed` makes the stochastic action ranking and counterfactual choices reproducible.

The initial lemma generator is deliberately simple. For atoms appearing in a target it proposes atom-level classical excluded-middle tautologies. The benchmark conjecture and its negation are excluded from this lemma-proposal path so the auxiliary lemma mechanism is not a disguised answer channel.

## Recorded but not yet behaviorally active

These controls remain in the schema but are not yet implemented honestly by the current depth-first LK search:

- `breadth_depth_balance`
- `novelty_pressure`
- `restart_rate`

They should not be described as implemented merely because values exist in the profile.

## Counterfactual-rescue check

The regression suite contains a two-expansion capped-search case. With candidate width 1 and counterfactual admission disabled, the structurally top-ranked action consumes the budget and no proof is found. With the same target, budget, ranker, and seed but counterfactual admission forced on, an otherwise excluded legal action is tried first and a verifier-accepted proof is found. This checks the rescue mechanism; it is not a performance claim about theorem families.

## Default heterogeneous roles

The bootstrap deliberately gives the three objectives different profiles:

- **P — focused-prover**: lower exploratory settings and modest lemma-construction allocation.
- **R — exploratory-refuter**: broader candidate/reuse limits and larger lemma-construction allocation.
- **I — model-diversity-independence**: highest declared exploratory settings; its current finite model-pair search does not yet consume every profile field.

The purpose is to preserve a stable heterogeneous configuration interface while keeping claims about realized creativity empirical.

## Shared-bank reuse

A reusable theorem lemma contains its proof certificate. A consuming proof agent may use it only by constructing an explicit `CUT` certificate. The verifier checks both the stored lemma proof and the proof that uses the lemma. Productive reuse records producer, consumer, objectives, lemma identifier, activation, and whether the reuse entered an accepted contribution.

`RunResult.cross_objective_reuse_count` counts productive uses whose producing and consuming objectives differ. `cross_objective_reuse_efficiency` divides that count by verified intermediate-lemma production cost. This is an instrumentation statistic, not yet a general creativity metric.

## Matched sharing mode

`CreativityALDRunner` supports `sharing_mode="shared"` and `sharing_mode="isolated"`. Shared mode exposes the whole verifier-certified bank to each agent. Isolated mode exposes only records produced by that same agent. The formal target, profiles, seeds, scheduler design, verifier, activation slice, and global budget can therefore be held fixed while changing only cross-agent information flow.

A deliberately constructed microbenchmark currently settles in 7 charged expansions with sharing and 9 without sharing, a 2-expansion or 22.2% reduction. That result establishes that the implemented mechanism can create a measurable resource gain on one designed instance. It is **not** an estimate of expected ALD gain on LEM, HaloProof, or any held-out theorem distribution.

## Experimental rule

A future claim that a profile, shared bank, or adaptive controller increases creativity requires repeated matched trials. At minimum compare isolated agents against shared-bank agents with the same theorem set, seeds, verifier, hardware, and global charged budget. Report success, discovery cost, verified novelty, reusable lemma yield, cross-objective reuse, and overhead separately before combining them into a utility score.
