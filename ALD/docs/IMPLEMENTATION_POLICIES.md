# ALD implementation policies — initial code contract

This file mirrors the implementation commitments established before coding. The longer rationale is preserved in the project policy document; this Markdown version is the code-facing contract.

## Settlement semantics

1. Freeze the formal environment, target, negated target, inference rules, parser/normalizer version, verifier version, and background assumptions before search.
2. Emit `PROVED`, `REFUTED`, or `INDEPENDENT` only with a verifier-accepted certificate.
3. A finite resource limit returns `BOUNDED_UNKNOWN`, never `INDEPENDENT`.
4. Crashes or invalid runtime conditions return `IMPLEMENTATION_FAILURE` rather than a mathematical conclusion.

## Agent architecture

5. Maintain distinct Prover (P), Refuter (R), and Independence (I) objectives.
6. Preserve private search state for each agent.
7. Permit heterogeneous search profiles; do not equate raw exploration with measured creativity.

## Shared verified bank

8. The bank is append-only and monotonic during a run.
9. No candidate enters the bank without verification.
10. Share verified mathematics, not mandatory attention: agents may rank shared lemmas differently.
11. Record provenance, production cost, verifier version, reuse, and cross-objective reuse.

## Creativity and search

12. Optimize verified creative yield and proof-search utility, not temperature or entropy alone.
13. Support controlled, logged counterfactual admission outside ordinary candidate caps.
14. Introduce adaptive creativity only through explicit, predeclared signals.
15. Preserve a diversity reserve so the shared bank does not collapse all agents onto one route.
16. Measure system-level and cross-agent creative contribution in addition to per-agent outcomes.

## Scheduler and resources

17. Begin with a simple fair scheduler.
18. Charge meaningful computation to one frozen global budget.
19. Stop immediately when the first valid settlement certificate is accepted.

## ALD-LEM-01 benchmark

20. Represent `C := φ ∨ ¬φ` and `¬C := ¬(φ ∨ ¬φ)` explicitly and hash the target.
21. Start in an explicitly classical propositional environment as a sanity test.
22. Do not expose the expected answer or a target-specific proof route to the search agents.
23. Independence requires its own machine-checkable certificate class; search failure is never enough.

## Acceptance criteria represented in this bootstrap

- environment and target hashes are logged;
- P, R, and I are distinct objects;
- all deposits are verifier-approved;
- the shared bank is monotonic and provenance-bearing;
- a global budget is enforced;
- budget exhaustion returns `BOUNDED_UNKNOWN`;
- settlement requires a machine-checkable certificate;
- classical LEM can reach `PROVED` without an answer flag;
- an atom over the empty classical theory can reach `INDEPENDENT` using a verified model pair;
- a negated LEM target can reach `REFUTED` through a verified proof of its negation.

## Not yet satisfied

The bootstrap does not yet implement meaningful shared-lemma reuse, creativity-profile sweeps, counterfactual search toggles, adaptive creativity, or the matched isolated-versus-shared experiment. Those are intentionally deferred until the verifier/search/budget spine is stable.
