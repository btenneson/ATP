# sgrpcl C5 Control-Awareness Experiment — False Zero Result

Date: 2026-08-26
Target: `sgrpcl`
Global expansion budget: 30,000
Seed: 2301
Search condition: NO-ML, target proof guarded, same historical `set.mm` baseline as the prior 8.019 transfer run.

## Control-awareness ablation

The experiment changed only the control-awareness coordinate while leaving the imagination/search profiles unchanged from the 8.019 mode profiles:

- native: (C,I) = (5,3)
- surge: (C,I) = (5,4)
- torpor: (C,I) = (1,2)
- brute: (C,I) = (0,0)

Operational control weights were native=0.50, surge=0.50, torpor=0.10, brute=0.00.

## Observed result

The controller drove the heuristic settlement distance from 2.345 to 0.000 after only 557 total guided+probe expansions, with no brute-force phase. The apparent zero occurred in the `sylibr` basin.

However, the emitted candidate failed both the in-process Metamath verification and the independent external verification with the same error:

`type mismatch at wal: setvar vs wff`

Therefore this run did NOT settle `sgrpcl` and must be recorded as a false-zero event, not as a proof.

## Programmer note — preserve the mathematical direction

**H = 0 is a necessary condition for settlement in the settlement-distance formulation. Do not weaken or remove that requirement merely because a heuristic implementation can produce a false zero.**

The bug/lesson is not that a genuine settlement may have H > 0. Rather, the current heuristic `h_hat` can report 0 before the candidate has satisfied the exact proof/certificate semantics. The implementation must distinguish an apparent/heuristic zero from a certified zero.

Required semantic discipline:

- Settlement => H = 0.
- Heuristic H = 0 does not by itself imply settlement.
- A candidate at heuristic H = 0 must pass exact certificate construction and verification before the system may declare settlement.
- If verification fails, record `FALSE_ZERO`, preserve the verifier failure reason, and continue search rather than treating the state as settled.

The intended future invariant is therefore:

`SETTLED => H = 0`

with a verification gate ensuring that only verifier-accepted zero candidates count as settlement.

## Comparison with prior 8.019 sgrpcl run

The prior 30,000-expansion 8.019 run stalled near best heuristic H = 2.015 and exhausted the full budget. The C5 ablation reached heuristic H = 0 in 557 expansions, but the candidate was invalid. This is evidence that stronger control influence substantially changed the search trajectory, while also exposing that the current zero condition is not yet certificate-authoritative.
