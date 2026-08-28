# Structural-width conjecture experiment (Predator 8.030)

## Conjecture

For a proof-search state there is a minimum effective structural future width D* required to preserve at least one proof-bearing continuation. Below D*, the useful future is pruned. Near D*, search should be most efficient. Far above D*, settlement may remain reliable while unnecessary search work increases.

## Controlled variable

`D` is the maximum number of structurally distinct successor classes retained per expanded state after primitive successors and shortcut-macro endpoints are combined and quotiented. One best-priority representative is retained per structural class before the D cap is applied.

The class key uses the instantiated selected goal plus the sorted multiset of remaining instantiated goals, matching the structural quotient idea in Predator 8.028/8.029.

## Fixed conditions

- `C = 0` throughout; H is telemetry only and does not alter priority.
- I-style profile changes are removed as the experimental variable. A fixed broad generator profile supplies candidates so D is intended to be the binding local structural-width control.
- Existing shortcut macros span at most three primitive proof inferences total (one ordinary child plus up to two internal legal steps).
- Every primitive proof step remains in the certificate trail.
- Final certificates are independently checked by the Metamath verifier.
- `scikit-learn==1.8.0` is pinned to match the saved policy artifact version.

## Sweep

- D in {8, 16, 24, 32, 48, 64, 96, 128}
- seeds 2301-2305
- target `prcom`
- 40 treatments total

## Primary predictions

1. Each seed has a threshold-like minimum D* at which settlement appears.
2. Expansion cost is lowest near the smallest sufficient D, rather than at the largest D.
3. Raising D well above D* increases macro/internal work and/or wall time without shortening the primitive certificate.
4. The hard seed 2304 should require a larger D* than seed 2302 if the earlier I-threshold pattern was genuinely a structural-diversity effect.

## Responses recorded

- verified settlement / timeout or bounded unknown
- outer expansions
- proof steps
- wall, user, and system time
- shortcut macro generation and internal primitive work
- quotient behavior
- generated versus retained structural classes
- local Shannon effective width `D_eff = exp(-sum p_i log p_i)` computed from retained priority mass for logged events

This is a falsification-oriented experiment: a lack of threshold behavior, or expansion minima unrelated to the smallest sufficient D, counts against the conjecture.
