# DATA MIND 3.1 Experiment 007 Result

Status: RUN / VERIFIED WHERE CLAIMED

This result note is post-run documentation. It does not change the frozen official run configuration.

## Official record

- official workflow head: `f71bb3de1a9da526b485530a3947aa9a40ea6762`
- workflow run: `33794623666`
- workflow conclusion: `success`
- artifact ID: `9908843355`
- artifact name: `data-mind-31-exp007-professor-p1-prcom-f10000-33794623666`
- artifact size: `6,052,409` bytes
- artifact SHA256 digest: `0e8ec1e367f3818f6abd4637643729d3d41e1c91b9543ce8b036bcac64307166`
- artifact expiry: `2026-12-02`

A green workflow here means the preregistered protocol completed correctly. It does not convert PRCOM UNKNOWN into a proof.

## Summary

| Stage | Outcome |
|---|---|
| PRCOM P1: Professor-facing, self-aware, advisory Child | `UNKNOWN` (`expansion_budget`) |
| PRCOM P2: protected non-Professor adaptive fallback | `UNKNOWN` (`expansion_budget`) |
| Conditional Ocean `F(10,000)` | `PROVED`, independently verified |

## PRCOM P1

Frozen per-lane budget:

- 20,000 expansions
- candidate cap 64
- max depth 24
- max open goals 24
- max frontier 200,000
- timeout 1,800 s
- control interval 16
- cold start

Outcome:

- status: `UNKNOWN`
- reason: `expansion_budget`
- expansions: `20,000`
- generated children: `238,291`
- search elapsed: `145.278607588 s`
- wall: `152.34 s`
- max RSS: `678,868 KB`
- verifier-accepted PRCOM candidate: none
- proof labels: none

Reflective/Professor telemetry:

- Professor updates: `1,250`
- P1 self-awareness updates: `1,250`
- repair half-distance fixed from the first positive burden proxy: `1.044`
- final Professor credit: `0.019734812829709125`
- Professor scalarization: `0.50*q_raw + 0.50*repair_proximity`
- repair proxy: `H_hat=max(0,1/q_raw-1)`; this is a burden proxy, not an exact repair horizon

Child telemetry:

- trial starts: `8`
- kept: `4`
- rolled back: `4`
- group-inverse trials: `0`

Kept fine-tune trials were:

- `divergence`
- `heuristic_weighting`
- `goal_selection`
- `lemma_direction`

Rolled-back trials were:

- `search_breadth`
- `risk_tolerance`
- `abstraction_level`
- `node_selection`

Final creativity:

- abstraction_level `0.5`
- divergence `0.0`
- goal_selection `0.56`
- heuristic_weighting `1.0`
- lemma_direction `0.56`
- node_selection `1.0`
- resource_bias `1.0`
- risk_tolerance `0.0`
- search_breadth `0.0`
- search_depth `1.0`
- term_ordering `0.5`

## P1 versus Experiment 006

Experiment 006 and Experiment 007 P1 used the same frozen `set.mm` and the same core 20,000-expansion PRCOM limits. Experiment 007 changed the P1 evaluation/control wiring.

The new Professor signal did alter local decisions:

- Experiment 006: 7 Child trials, 2 kept, 5 rolled back.
- Experiment 007 P1: 8 Child trials, 4 kept, 4 rolled back.
- In particular, P1 kept `heuristic_weighting` at the trial ending at expansion 800, where Experiment 006 rolled that trial back.
- P1 then reached and kept a `lemma_direction` trial ending at expansion 1008; Experiment 006 did not reach that trial.
- The two search trajectories first differ at expansion 803.

However, the macroscopic search geometry remained strikingly similar:

- generated children: `238,291` (P1) versus `238,364` (Experiment 006), a difference of only 73 children out of about 238k;
- first open-goal saturation at 24: expansion `1,123` in both runs;
- fraction of expanded states with 24 open goals: about `87.055%` for P1 versus `86.915%` for Experiment 006;
- no verifier candidate in either run.

Thus the Professor-mediated signal changed the detailed trajectory and Child accept/reject decisions but did **not** escape the same high-open-goal PRCOM basin.

A crucial interpretation is that the Experiment 007 Professor signal is still built from the old `q_raw`, whose principal information is weighted residual open-goal burden. Adding an exponential repair-proximity transform makes the evaluation more structured, but it does not yet supply the full advanced theory of verified substructure, actual repair transactions, local proof density, or neighborhood repair quality. In the official P1 run, Professor credit was about `0.44965` at expansion 16 and fell to about `0.01973` by the end as obligation burden grew.

This is evidence for changing the *content of the Professor's evidence*, not merely rescaling the old partial-credit proxy.

## PRCOM P2 protected fallback

P2 ran only after P1 remained UNKNOWN.

Outcome:

- status: `UNKNOWN`
- reason: `expansion_budget`
- expansions: `20,000`
- generated children: `149,277`
- search elapsed: `136.456538229 s`
- wall: `142.15 s`
- max RSS: `495,436 KB`
- Child play: off
- Professor/self-awareness: off
- verifier candidate: none

Its core deterministic output reproduces the earlier ordinary adaptive PRCOM behavior: `149,277` generated children and the same final creativity vector seen in Experiment 005. The protected lane therefore preserved a genuinely different search regime from P1, but it did not solve PRCOM.

Because P2 is a conditional additional 20,000-expansion lane, the combined P1+P2 portfolio is not an equal-total-budget comparison against Experiment 006.

## Conditional Ocean F(10,000)

Both PRCOM lanes were unproved, so the preregistered fallback ran.

Generator:

- depth: `10,000`
- seed: `1`
- generated instances: `1`
- generator independently BFS-checked the declared minimum depth before the solver ran

Solver disclosure:

- plain breadth-first search over the serialized directed implication graph
- hidden/planted route access: `false`
- historical `Depths-F` claim: `false`

Outcome:

- status: `PROVED`
- declared depth: `10,000`
- certificate transitions: `10,000`
- certificate nodes: `10,001`
- independent Ocean verifier accepted: `true`
- edge count: `220,021`
- visited nodes: `219,838`
- peak BFS frontier: `46`
- search elapsed: `0.263387569 s`
- wall: `1.04 s`
- max RSS: `116,028 KB`
- problem SHA256: `fc42e1c914c63a58f9ab705895c71f43315db5caf1be854442d607e7675db309`

The independent verifier reparsed the serialized TPTP problem, checked the source and target, checked every consecutive certificate edge against an input implication, and confirmed exactly `10,000` transitions.

## Scientific interpretation

Experiment 007 separates two phenomena cleanly.

1. **PRCOM remains a search-geometry/stagnation problem.** More nuanced Professor mediation changed local decisions but did not change the dominant high-open-goal basin enough to produce a verifier candidate.
2. **Very large proof depth is not itself the present limitation.** On the structured Ocean family, DATA MIND's fallback could discover, emit, and independently verify a 10,000-transition certificate quickly. This does not imply general ATP speedup; the Ocean graph is deliberately transparent to breadth-first graph search.

The most defensible next PRCOM engineering target is therefore not another expansion-budget increase. It is to replace the current open-goal-derived Professor evidence with more genuinely transaction-geometric information: verified useful substructure, explicit repair operations/defects, local repair density or neighborhood quality, and transactional FUTUREBANK/backfill experiments that can be discarded without contaminating the live frontier.

## Frozen-source hashes from the official manifest

- `search.py`: `225229ce69fbbdb8911ff8702fbd5a6bbd7d53973e4bc8b24c1bc97ea7db035d`
- `controller.py`: `570f57289eae80146337026fa3dc2bfe613cefaa2404a0a37a07c9db3fa4cfb3`
- `reflective.py`: `1274bafcf2949a5dac909da37f2eea09918346cc0a98de01651a5b44ad8468d8`
- `professor.py`: `c14716ae8c11578d38c8ce419b12766a81f7e273c2437587e09dfad7e37f27ed`
- `agents.py`: `8c148e70515b9d02f1c8692243ddc0bb49b6f451fb143efee7a2869509497a74`
- `futurebank.py`: `bbf5dd5ffaded308456d5bb7218ced9a0716d46f92ac42b4dc48a2e9e1c6028e`
- `child.py`: `b74758619793012d9524e5daafb74cbe130888c8628cbd72217bed6c0f8c7947`
- `knobs.py`: `f7717abc7531a7daa72cb4d0a3b62c6b52e466cfb5899de33a7f91c40ba8f256`
- Metamath runner: `b7e97a8ff0a9aab74c8977154c6e8240108229dbe798a216b7458d86df94183c`
- verifier adapter: `65dd4633ea6f8dd36d5849a069c1ccc50fd3283adfe36917ba36820c4e45ce44`
- independent `metamath.py`: `6e6d5f08083eaa788cd39eca486eff69de37a71e213e74edc77f20da23c381a4`
- Ocean generator: `b75ab1a30c875f4f3de678d76ee56355086a96501d8b52b19a3748d57f0491cc`
- Ocean solver: `01756069ef451aa37b583bba87596220cf19464b15f0de5d335028b73431bcbf`
- Ocean verifier: `8d8fd4c8dc0caacede925c727d69567f7852ff0c335513c3cb659aca9f46a375`
- Ocean runner: `9dccd47a6bf87bb4752ede1f085e24ca3a9579428c832cd777b0d7d5f7ce14ef`
