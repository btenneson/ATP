# `prcom` full-toolbox portfolio — protocol

## Purpose

This experiment asks whether the strongest currently implemented ATP tool families in this repository can settle the Metamath theorem `prcom` when deployed as a verifier-gated portfolio.

Target: `prcom`, the commutative law for unordered pairs, informally `{A,B}={B,A}`.

This is an engineering portfolio, not a claim that every historical controller can be merged into one mathematically coherent state machine.  Mature components remain in the implementations where their invariants have already been tested; the portfolio gives each tool family an independent attack on the same frozen target and lets the unchanged Metamath verifier decide theoremhood.

## Protected invariant

The verifier is never revised, optimized, voted on, or overridden.  A certificate counts only when the frozen Metamath verifier accepts it.  Search tools may choose where to look; they cannot create theoremhood.

## Tool families included

The portfolio contains the following arms.

### 1. Guided ACO

`experiments/aco_prcom_guided.py`

Uses:
- ant-colony pheromone memory,
- structural `h_hat` guidance,
- epsilon exploration,
- elite partial-state retention,
- staged proof depth/open-goal limits,
- per-batch checkpoints,
- independent certificate verification.

The ACO arm does not read the historical `prcom` proof.

### 2. Adaptive Predator awareness/shortcut arm

`predator8_030_prcom_adaptive_shortcut.py`

This is the mature adaptive path that carries forward:
- learned pre-target policy guidance,
- control/imagination awareness,
- bidirectional attention,
- exactification/full-graph exactification,
- bailout and selective-sink behavior,
- quotient awareness,
- shortcut macros,
- adaptive awareness switching,
- brute-force reserve,
- independent external certificate verification.

The adaptive awareness path is `(C,I)=(0,5)->(2,5)->(0,4)->(0,3)->brute`.

### 3. C3 creativity / verified pre-target BANK arm

`predator8_035_c3_conservative_compilation.py`

Uses the ten certified creativity coordinates
`(cT,cW,cN,cR,cL,c_lemma,cS,cB,cD,cM)` for policy dispersion, width, novelty, route independence, length tolerance, lemma speculation, restart diversity, breadth, retrieval diversity, and macro compilation.  It mines only verified proofs strictly before `prcom`; no target route is supplied.

### 4. Inverse-revision fixed-point arm

`predator8_037_inverse_revision_fixedpoint.py`

Uses group-structured creativity coordinates, coordinatewise and full inversion, conservative compilation, verified-result BANKing, and repeated revision until the inverse-neighborhood protected objective reaches an experimental fixed point.

Important interpretation: this arm is target-experienced.  Its existing implementation starts from a previously verified `prcom` incumbent *metric/result record*.  It does not replay the historical certificate, but results from this arm must not be described as a fresh target-blind discovery.  They are optimization/revision evidence.

### 5. Bit-incumbent coupled revision arm

`predator8_034_prcom_bit_incumbent_revision.py`

Uses generalized training, bit-aware certificate objectives, coupled adaptive revision, multi-seed search and verifier-gated incumbent replacement.

Important interpretation: this is also theorem-specific adaptation and therefore belongs in the experienced/optimization category rather than the clean fresh-discovery category.

### 6. Finite exhaustive proof-BANK arm

`predator8_026_prcom_finite_exhaustive_bank.py`

Enumerates a declared finite `prcom` search region and banks proof-space records.  Completeness claims apply only to the explicitly bounded finite region, never to theoremhood outside that region.

## Eight-agent revision architecture

The repository's eight-agent AMLD revision fallback remains an architectural invariant/gate:
`{P1,P2,R1,R2,I1,I2,C1,C2}` with thresholded optimization versus coordinatewise group inversion and protected `V(z)=1`.

The portfolio does not pretend these eight roles are interchangeable with the internal state objects of every historical solver.  Instead, the same principle is enforced at portfolio level: search-control policies may revise; verification cannot.

## Clean versus target-experienced evidence

Final reporting must separate:

- **clean/search evidence**: guided ACO, adaptive awareness/shortcut, C3 pre-target BANK, finite exhaustive BANK;
- **target-experienced optimization evidence**: 8.034 bit-incumbent revision and 8.037 inverse-revision fixed point.

A proof found by either category is a valid proof if externally verified, but the scientific interpretation differs.

## Budgets

Each portfolio arm receives a GitHub Actions ceiling of 360 minutes.  Search implementations may impose smaller internal safety ceilings.  Long-running arms must preserve logs/artifacts so timeout is reported as bounded UNKNOWN rather than logical failure.

## Outcome rule

For every arm report:
- VERIFIED or bounded UNKNOWN,
- wall time,
- expansions/applications/transactions when available,
- certificate length/bits/steps when available,
- best partial-distance statistic when available,
- whether target-specific prior experience was used,
- external-verifier result.

The portfolio-level outcome is VERIFIED if at least one emitted certificate passes the independent verifier.  Otherwise it is bounded UNKNOWN under the declared portfolio budget.
