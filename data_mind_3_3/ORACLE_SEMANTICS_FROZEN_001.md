# DATA MIND 3.3 — Oracle Semantics Frozen 001

**Status:** FROZEN BEFORE CAUSAL DREAMER TESTING  
**Oracle implementation source at freeze:** `data_mind_3_3/oracles.py` blob `2342bba42523a00787c1c0d0888001a599e2e4c4`  
**Scope:** O1/O2/O3/O4 meanings and authority boundaries only. Throttle values are frozen separately for experiments.

## Common input boundary

All four finite oracles may inspect only a `DreamerSearchSnapshot` containing ordinary operational search telemetry such as target id, expansion count, generated count, frontier occupancy, elapsed/timeout, locally computed partial credit, target relevance, control-error telemetry, effective controller settings, creativity settings, and an optional already-existing candidate-certificate reference.

Forbidden common inputs include hidden theorem truth, hidden proof labels, future verifier outcome, BANK admission outcome not yet observed, or benchmark answer keys.

## O1 — role/type oracle

**Output type:** `RoleAdvice`.

O1 may report the configured settlement/search lane and a confidence/basis. In the Metamath proof-search lane the finite adapter returns `SettlementRole.PROVE` because that is the configured task role, not because it has discovered hidden theoremhood.

O1 may not read or infer a hidden ground-truth settlement label supplied by the benchmark.

## O2 — resource oracle

**Output type:** `ResourceAdvice`.

O2 may classify finite resource posture (`conserve`, `explore`, `balanced`) and recommend bounded breadth/depth factors using only observed resource, frontier, branching, and stagnation telemetry.

O2 advice is advisory. It may not override Sentinel, hard experiment budgets, oracle throttles, or promotion limits.

## O3 — strategy oracle

**Output type:** `StrategyAdvice`.

O3 may recommend one existing legal `EscapeAction` class using only current operational telemetry. Frozen finite rules may choose among actions such as local repair, fine tuning, lemma backfill, basin switching, or fallback.

O3 may not execute an action directly, certify an action, or bypass the promotion whitelist.

## O4 — certificate oracle

**Output type:** `CertificateAdvice`.

O4 is strictly candidate-only. It may surface an already-existing non-authoritative candidate-certificate reference and a readiness score derived from local partial credit.

O4 may not invent verifier acceptance, mark a candidate as proved, deposit to BANK, call the verifier as authority, or receive a hidden proof/certificate from the benchmark.

## Dreamer synthesis boundary

The four outputs are heterogeneous typed advice. They are not literally added as a linear combination. Dreamer may synthesize them into one speculative `FutureProposal` only.

The permitted authority path is:

`O1/O2/O3/O4 -> Dreamer -> FUTUREBANK -> promotion gate -> ordinary legal computation -> verifier -> BANK`

The following remain forbidden:

- `Oracle -> BANK`
- `Dreamer -> BANK`
- `Oracle -> verifier acceptance`
- `Dreamer -> verifier acceptance`

## Change control

Any semantic change to O1/O2/O3/O4 after this freeze requires a new semantics identifier (for example `ORACLE_SEMANTICS_FROZEN_002`) and may not be silently substituted into an experiment preregistered against Frozen 001.
