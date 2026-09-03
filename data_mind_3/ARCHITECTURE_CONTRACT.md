# DATA MIND 3.1 Architecture Contract

Status: IMPLEMENTED AS INTERFACES / NOT YET AN EXPERIMENT

This document is a durability contract for the DATA MIND 3.1 architecture. It records the intended separation of roles before the next experiment is frozen. No new DATA MIND version number and no new experiment number are assigned by this wiring work.

## 1. Eight principal search agents remain four couples

The principal search agents are

- `(P1, P2)` for proof-directed search,
- `(R1, R2)` for refutation-directed search,
- `(I1, I2)` for independence-directed search,
- `(C1, C2)` for contradiction/integrity-directed search.

The two members of a couple are intentionally allowed to differ. They may use different policies, seeds, representations, novelty levels, or advice. A couple is not two copies that must agree.

## 2. Initial Professor-facing choice

The initial DATA MIND 3.1 wiring designates exactly one member of each couple as Professor-facing:

`P1, R1, I1, C1`.

The partner lane

`P2, R2, I2, C2`

remains deliberately less coached. This is an anti-herding / diversity protection. It can be disabled or changed in a later frozen experiment, but it must not disappear silently.

## 3. At least one principal agent is self-aware

The initial wiring marks `P1, R1, I1, C1` as operationally self-aware and the second member of each couple as non-self-aware.

Operational self-awareness is search information, not mathematical authority. A self-aware agent may represent facts about its own current strategy, resource use, stagnation, recent marginal progress, BANK/FUTUREBANK use, and available escape actions. It may use those facts to choose what to attempt next.

Self-awareness may never make an unverified statement true and may never alter verifier acceptance semantics.

## 4. The Professor teaches; it does not command

The Professor supplies evaluation information to the Professor-facing agents. The Professor does not own the global scheduler and does not directly choose the next theorem-search action.

The advanced Professor grade is a vector rather than a forced scalar. Candidate components include:

- verified target-relevant structure already present `q`,
- repair proximity derived from an estimated repair horizon `H`,
- local proof/repair density `rho`,
- smoothed neighborhood quality `G`,
- target relevance,
- marginal partial-credit gain per unit resource,
- uncertainty / calibration information.

No universal scalar weights are frozen here. A later experiment may preregister a scalarization or ranking rule.

## 5. Main agents choose what to attempt next

Professor-facing principal agents receive advice and grades, but the agent remains the actor. An agent may accept or reject Professor advice, ask its partner, continue its own route, or select an escape action.

This means the control relation is approximately:

`Professor -> advice/grade -> principal agent -> attempted action`.

It is not:

`Professor -> command -> search`.

## 6. The Child is advisory creativity, not the executive

The Child remains an experimental creativity mechanism with relatively little direct authority over what happens next. It may propose local knob trials, unusual strategies, rare group inversions, counterfactual branches, or other creative deviations.

The Child does not sit above all eight agents as a sovereign executive. A principal agent may reject a Child proposal. Sentinel may veto an unsafe/resource-pathological proposal. The verifier remains outside the control hierarchy.

The older operational Child pair is retained conceptually as

`(c_control, i_imagination)`.

- `c_control` concerns strategy/control experimentation.
- `i_imagination` concerns reasoned counterfactual exploration through FUTUREBANK.

This operational pair is not to be conflated with any separate formal reflection/controller rank notation used in later self-awareness theory.

## 7. FUTUREBANK is the transactional imagination boundary

FUTUREBANK stores represented possibilities, not accepted mathematics. Speculative branches may include hypothetical lemmas, alternative strategies, presentation changes, quotient ideas, macro ideas, or knob regimes.

A rejected speculative trial should be discardable as a transaction. Rolling back a parameter while leaving its speculative descendants in the live frontier is not a full rollback.

Therefore future experimentation should prefer:

`live state -> isolated FUTUREBANK trial -> evaluate -> discard OR propose promotion`.

A proposal leaving FUTUREBANK still does not enter verified BANK merely because it was promising.

## 8. BANK and verifier sovereignty

BANK contains only material admitted under the declared verification policy. FUTUREBANK contents, Professor scores, Child confidence, self-awareness, and agent votes do not bypass verification.

The verifier is sovereign and fixed for a frozen run. Search intelligence may change what is attempted, but not what counts as a valid certificate.

## 9. Sentinel remains a veto, not a mathematical authority

Sentinel may quarantine or stop actions because of resource or safety limits. It does not determine truth. A principal agent's autonomy does not override Sentinel limits.

## 10. Stagnation escape menu

The interface exposes the following candidate escape actions without forcing any one policy:

- repair a promising partial proof,
- backfill a hypothetical lemma,
- ask the partner agent,
- switch basin,
- fine-tune controls,
- apply a rare group inverse / regime inversion,
- try a certified presentation trade,
- try a quotient / state aggregation,
- compile or acquire a reusable verified macro/lemma,
- restart/diversify,
- protected fallback.

A self-aware agent may use Professor grades, FUTUREBANK forecasts, partner information, BANK contents, and resource observations to choose among these.

## 11. Protected independent lane

At least one member of each P/R/I/C couple should retain some path not directly optimized by the same Professor signal. This is intended to protect against systematic Professor miscalibration and premature convergence.

The exact budget share is intentionally not specified here. It must be set and frozen only when an experiment is preregistered.

## 12. Current implementation status

This commit adds interfaces and tests for the architecture above. It does not activate a new multi-agent experiment and does not silently alter the completed Experiment 006 result.

Before a scientific run, we must separately:

1. finish runtime wiring to the selected P/R/I/C orchestration,
2. choose which features are enabled,
3. freeze all thresholds/weights/budgets/seeds,
4. preregister the comparison and stopping rules,
5. assign the next experiment number only then,
6. run and report VERIFIED / PROVED / UNKNOWN outcomes without conflating workflow success with mathematical success.
