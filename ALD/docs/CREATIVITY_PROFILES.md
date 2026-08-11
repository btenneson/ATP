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

Three controls currently change behavior:

1. `candidate_width` limits how many generated lemma candidates an agent considers.
2. `lemma_construction_budget_fraction` controls how much of an activation may be spent constructing a reusable verified lemma before returning to the settlement target.
3. `bank_reuse_limit` limits how many verifier-certified bank lemmas are offered to a proof search activation.

The initial lemma generator is deliberately simple. For atoms appearing in a target it proposes atom-level classical excluded-middle tautologies. The benchmark conjecture and its negation are excluded from this lemma-proposal path so the auxiliary lemma mechanism is not a disguised answer channel.

## Recorded but not yet behaviorally active

The following controls are present in the schema and frozen in logs, but the current deterministic LK search does not yet have the ranked stochastic machinery required to use them honestly:

- `temperature`
- `breadth_depth_balance`
- `novelty_pressure`
- `restart_rate`
- `counterfactual_admission_rate`

They should not be described as implemented merely because values exist in the profile.

## Default heterogeneous roles

The bootstrap deliberately gives the three objectives different profiles:

- **P — focused-prover**: lower exploratory settings and modest lemma-construction allocation.
- **R — exploratory-refuter**: broader candidate/reuse limits and larger lemma-construction allocation.
- **I — model-diversity-independence**: highest declared exploratory settings; its current finite model-pair search does not yet consume all of those controls.

The purpose is to preserve a stable heterogeneous configuration interface while keeping claims about realized creativity empirical.

## Shared-bank reuse

A reusable theorem lemma contains its proof certificate. A consuming proof agent may use it only by constructing an explicit `CUT` certificate. The verifier checks both the stored lemma proof and the proof that uses the lemma. Productive reuse records:

- producing agent and objective,
- consuming agent and objective,
- lemma identifier,
- activation number,
- whether the reuse entered an accepted contribution.

`RunResult.cross_objective_reuse_count` counts productive uses whose producing and consuming objectives differ. `cross_objective_reuse_efficiency` divides that count by verified intermediate-lemma production cost. This is an instrumentation statistic, not yet a general creativity metric.

## Experimental rule

A future claim that a profile, shared bank, or adaptive controller increases creativity requires matched trials. At minimum compare isolated agents against shared-bank agents with the same theorem set, seeds, verifier, hardware, and global charged budget. Report success, discovery cost, verified novelty, reusable lemma yield, cross-objective reuse, and overhead separately before combining them into a utility score.
