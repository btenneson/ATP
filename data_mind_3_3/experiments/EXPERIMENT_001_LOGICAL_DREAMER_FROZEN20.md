# DATA MIND 3.3 Experiment 001 — Logical Dreamer Frozen-20 Mechanism

**Status:** PREREGISTERED; DO NOT INTERPRET PRE-LAUNCH ENGINEERING RUNS AS SCIENTIFIC RESULTS  
**Experiment seed:** `330001`  
**Benchmark:** `DATA-MIND set.mm Frozen-20 Benchmark 001`  
**Canonical benchmark lock:** `benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json`  
**Canonical benchmark lock Git blob:** `2725ae80c22bf0dd74a38ed1ba4ffb21a7ad7b9c`  
**Oracle semantics:** `ORACLE_SEMANTICS_FROZEN_001`  
**Oracle semantics implementation blob:** `2342bba42523a00787c1c0d0888001a599e2e4c4`  
**Experiment configuration blob at preregistration:** `b9c2fb7af257d7d693deb8c9e4bfd775d17cfb24`  
**Promotion implementation blob:** `c2d8b5c7092ea0b6b24f583cd6a714b58d85f3ac`  
**Causal bridge implementation blob:** `043c4e1f0e3f510620bf7967edad57684c5e6eba`  
**Professor actual-call-throttled implementation blob:** `5227de6409f0008257f6eb11a579d387ae261df6`

## 1. Scientific question

Under the same proof-safe Frozen-20 target set and the same externally enforced search budgets, does a bounded formally reflective Logical Dreamer improve verifier-certified settlement performance when given controlled access to selected finite oracle faculties?

This is a **mechanism study on the Metamath proof lane**. It is not a claim about full P/R/I/C settlement, not a proof of logical omniscience, and not a full causal attribution study of all four oracle faculties.

## 2. Permanent benchmark lock

The experiment reuses the pre-existing Frozen-20 benchmark without resampling targets.

Frozen source:

- set.mm commit: `f85a8edbb6df20dd5a64a9c159fa22944a3e54de`
- set.mm SHA-256: `19cb1ec229f3f11e36ff439a6381878864d9f2d4906f20fc9401346b309894e3`
- complete theorem count: 47,800
- training count: 45,410
- holdout count: 2,390
- holdout fraction: 0.05
- split seed: 271828
- training-label SHA-256: `bde7e08351f352e702e4222e19d3defae5373dbcea59131446b55ea78c8be57b`
- training-corpus-record SHA-256: `aaf3faa6f1e501504b0fe6ba590a8f2fd5a442833a447066cf81895b70fa7827`
- holdout-label SHA-256: `cc2ed0d0209615e80a2f10373a14804b3c43a366758f5d77288263bc9c1d10ba`
- target-label SHA-256: `cf20b02de6113ab6a05c178624e410d0b67baa46a5ac75d2eb99fdda330a22d5`

Frozen targets, in ordinal order:

0. `ax13dgen4`
1. `abrexdom2jm`
2. `pm14.18`
3. `bj-xpima1snALT`
4. `isfin3-4`
5. `prmone0`
6. `1sdom2ALT`
7. `afv2eq2`
8. `sbf2`
9. `ex-eprel`
10. `pm5.62`
11. `nelbrnelim`
12. `2exnexn`
13. `pred0`
14. `sq7`
15. `sigaclfu`
16. `prprc`
17. `bj-cleljusti`
18. `trggrp`
19. `cjex`

No target may be substituted after results are visible.

## 3. Proof-access discipline

Split reconstruction occurs in a separate preparation process. That process may inspect source proofs only to reconstruct and hash-check the already-frozen split. It emits holdout labels and hashes, not held-out proof text.

Each treatment lane runs in a fresh Python process. The settlement parser does not expose source proof text to search. Every non-target held-out theorem is removed from the legal search library. If a candidate certificate references any held-out theorem label, it is rejected before independent verification.

A `PROVED` result counts only if the candidate certificate passes a fresh `metamath.py` verifier subprocess. Workflow completion or a generated candidate is not theorem success.

## 4. Treatment arms

The five arms are fixed before launch.

| Arm | Dreamer | Access bits O1/O2/O3/O4 | Meaning |
|---|---|---|---|
| `off` | disabled | `(0,0,0,0)` | strict baseline; zero oracle calls and zero Dreamer work |
| `placebo-o3` | enabled | `(0,0,1,0)` | deterministic theorem-independent legal perturbation at the O3 call surface |
| `o3` | enabled | `(0,0,1,0)` | real finite strategy oracle only |
| `o34` | enabled | `(0,0,1,1)` | real strategy plus candidate-only certificate oracle |
| `o1234` | enabled | `(1,1,1,1)` | all four finite oracle interfaces |

All arms use the same inherited controller class, search implementation, verifier path, target order and budgets. Child play is disabled to isolate Dreamer mechanism effects.

The placebo uses SHA-256 of `(experiment seed, target id, expansion)` to choose deterministically among the same whitelisted legal action classes. It therefore introduces perturbation without using the real O3 operational rule.

## 5. Frozen finite oracle semantics

The experiment uses `ORACLE_SEMANTICS_FROZEN_001` without modification.

- O1: configured role/type advice only; on this proof lane it reports PROVE because that is the configured lane, not because it sees hidden theoremhood.
- O2: resource posture derived from ordinary finite resource/frontier/branch/stagnation telemetry.
- O3: strategy/action-class advice derived from ordinary finite operational telemetry.
- O4: candidate-only certificate advice. It may surface an already-existing non-authoritative candidate reference but may not invent or verify a certificate.

The first experiment does not pass a hidden candidate proof to O4. O4 may therefore be sparse or inert before terminal candidate construction. This behavior is part of the preregistered treatment and will not be changed after results are seen.

## 6. Dreamer and authority boundary

The allowed path remains:

`O1/O2/O3/O4 -> Dreamer -> FUTUREBANK -> promotion gate -> bounded legal controller action -> ordinary search -> verifier -> BANK`

Forbidden:

- Oracle -> BANK
- Dreamer -> BANK
- Oracle -> verifier acceptance
- Dreamer -> verifier acceptance

Individual Dreamer proposals will not be declared causally responsible for a proof merely because a proof occurs later in the same run.

## 7. Frozen controller and search settings

All five arms use:

- controller update interval: 16 expansions
- Professor actual-call interval: 256 expansions
- Child play: disabled
- initial 11D creativity vector: all coordinates 0.5
- candidate cap: 64
- maximum depth: 24
- maximum open goals: 24
- maximum frontier: 200,000
- 3.3 expansion safety cap: 100,000
- scientific wall-time budget per arm/target: 1,800 seconds

The 1,800-second wall-time budget preserves the permanent Frozen-20 evaluation protocol. The common expansion/frontier limits are 3.3 implementation safety limits and are reported whenever they terminate a lane.

## 8. Frozen oracle-call throttles

Actual calls, not merely recorded interventions, are throttled.

| Oracle | Maximum calls | Minimum expansions between calls |
|---|---:|---:|
| O1 role | 128 | 64 |
| O2 resource | 512 | 16 |
| O3 strategy | 128 | 64 |
| O4 certificate | 32 | 256 |

Promotion throttle:

- maximum promotions: 64
- minimum expansions between promotions: 64
- maximum absolute per-coordinate creativity change per promotion: 0.05

## 9. Frozen promotion whitelist

Only the following existing legal controller actions may have causal effect in Experiment 001:

- `REPAIR`
- `FINE_TUNE`
- `BACKFILL_LEMMA`
- `SWITCH_BASIN`
- `FALLBACK`

Each is translated only into bounded changes of the existing 11D creativity vector. Promotion cannot alter proof state directly, bypass Sentinel, change verifier semantics, or write to BANK. Every applied promotion records exact before/after state and is mechanically reversible.

## 10. Resource accounting

The experiment separately records:

- search expansions
- wall time
- actual oracle calls
- oracle reported cost
- Dreamer proposal count
- normalized Dreamer synthesis cost
- promotions granted
- applied promotion executions
- promotion reported cost
- actual Professor calls

A normalized bookkeeping quantity is also reported:

`accounted_units = search expansions + oracle cost + Dreamer synthesis cost + promotion cost + Professor cost`.

This prevents advisory work from being silently treated as free. It is **not** interpreted as saying that one oracle call, one Professor call and one search expansion consume equal physical CPU time. Wall time and search expansions remain separately reported primary resource measures.

## 11. Outcomes and comparisons

### Primary endpoint

For each arm:

**number of the 20 targets receiving an independently verifier-accepted `PROVED` settlement.**

### Preregistered paired comparisons against OFF

For each non-OFF arm:

- gain target: treatment PROVED, OFF not PROVED
- loss target: OFF PROVED, treatment not PROVED
- net verified settlement gain: gains minus losses

For targets proved by both treatment and OFF, report paired differences in:

- expansions
- wall time
- accounted units

### Placebo comparison

Compare `o3` with `placebo-o3` in verified settlement count and resource measures. This is intended to distinguish informative O3 strategy guidance from the mere fact of receiving matched legal perturbations. The comparison is descriptive at n=20 and is not by itself treated as a general causal theorem.

### Mechanism telemetry

Also report by arm:

- oracle calls
- Dreamer proposals
- promotions granted
- applied promotion executions
- actual Professor calls
- number of verified settlements occurring in runs that had at least one promotion

The last quantity is an association, not individual-proposal causal attribution.

## 12. Interpretation rules fixed before launch

1. A GitHub Actions green check is infrastructure success, not mathematical success.
2. `UNKNOWN`, timeout, expansion cap and frontier cap are scientific data unless caused by an infrastructure failure.
3. A candidate not accepted by the independent verifier is not a proof.
4. No arm, target, throttle, whitelist entry, budget or oracle rule may be changed after results are visible and still be reported as this experiment.
5. If all five arms fail all targets, that is a valid result.
6. If all five arms solve the same targets, that is a valid result.
7. If placebo matches or beats real O3, that is a valid result.
8. O4 inactivity under the frozen candidate-only interface is a valid result and will not be repaired mid-experiment.
9. No result from this experiment establishes literal logical omniscience or the nonstandard four-type omniscience theorem; the experiment concerns finite approximations only.
10. The experiment is a proof-lane mechanism study and does not establish performance of the full P/R/I/C settlement architecture.

## 13. Launch rule

The scientific experiment is not launched by this preregistration file. It becomes **LAUNCHED** only when the dedicated frozen workflow is triggered by the explicit `EXPERIMENT_001_LAUNCH` marker and a GitHub Actions run ID is observed.
