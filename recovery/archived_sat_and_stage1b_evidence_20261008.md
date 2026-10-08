# FORGE-6 recovery: archived SAT finite-check harnesses and Stage-1B corpus inventory

Date: 2026-10-08
Scope: Non-destructive recovery evidence, **not** scientific Eureka Experiment 1.
Experiment trials: **0 / 20**. Original frozen pilot prompts/seeds/target unchanged.

## A. Recovered original research archives (from user's ChatGPT Library)

These three original archives were inspected without altering their bytes:

| Library archive | SHA-256 |
|---|---|
| `Exact_Addressing_3_3_FORGE6_Package.zip` | `69ffa4a340589f5985378251513fa61e7e1e6e1249f6579bfa9b21cb6dc5abab` |
| `FORGE6_IAE20_Section4_Certificate_Package.zip` | `0f7c803fe3eb73d33e984b29a7b56d80d0b749fc7a0e063f540b996fb31e1e07` |
| `FORGE6_IAE20_Single_Target_Certificate_Package.zip` | `c1c9047dd151f3e49065146c19631a9a4ab19c5b78da89bffdafdf9f4f484dc4` |

The two Section 4 archives both contain a byte-identical
`FORGE6_IAE20_Reproducibility.py` with SHA-256
`b317dea4412014ac727b68418f3650311408ff41478b3f1cbd8356fc9c184635`.
The single-target archive contains `forge6_iae20_single_target_checks.py`
with SHA-256
`a750b33bbfc535f366867bf787da975040c71a1c190ed4d941ee9284b03752ab`.

The scripts were extracted into a separate, disposable local working folder
for syntax-checking and **finite** test execution. Their original archives
remain unchanged and are **not** automatically loaded into FORGE-6 BANK.

## B. Actual local test results, not FORGE-6 execution trials

```
python -m py_compile section4_repro.py single_target_checks.py
# succeeded, no syntax errors

python single_target_checks.py
STRUCTURAL_k_2_to_30_PASS: 29
OPPOSITE_LEDGER_MODELS_PASS: ({'x': 1, 'y': 2}, {'x': 1, 'y': 0})
EXACT_RANK_ARITHMETIC_k_2_to_40_PASS: 39
INDEXED_MODEL_TRIALS_PASS: 2900
NO_INDEX_ADVERSARIAL_k_2_to_30_PASS: 29
STATUS: finite checks only; universal claims require proofs.

python section4_repro.py
PASS: k=2..15 candidate count, residual-cover classifier, fallback (B,U) minima
PASS: exact two-target order-statistic and positive margin for all symbolic k>=2
PASS: both algorithms return the identical branch optimum on sampled random permutations
STATUS: finite tests support the model-specific weaker theorem, not formal proof verification.
PASS: paired executable algorithms, identical independently verified output, charged setup boundary
```

**Interpretation:** The last script's phrasing "independently verified
output" means an **embedded deterministic correctness check** for its toy
candidate optimization. It is **not** a separate proof-assistant certificate
or a tested complete six-board FORGE-6 runtime.

The original Release 3.3 distinction remains: the two-candidate indexed
comparison is model-relative and does **not** settle the unqualified original
single-target six-unit claim or establish SAT speedups.

## C. Candidate-cost ledger incompatibility

The two recovered harnesses implement different auxiliary `E` accounting
even though they return the same `(B,U)` and the same `E` on the
special candidates `(x,1),(y,1)`. A bounded cross-check compared **all**
`4+6k` actions at k=2,3,5,10:

| k | Actions checked | Differing actions | Single-target E(y=0) | Supplementary E(y=0) |
|---:|---:|---|---:|---:|
| 2 | 16 | only (y,0) | 10 | 13 |
| 3 | 22 | only (y,0) | 15 | 21 |
| 5 | 34 | only (y,0) | 25 | 40 |
| 10 | 64 | only (y,0) | 50 | 105 |

Those finite observations are not a proof of the pattern for all k.
The SAT-cost target requires **one frozen evaluator and one consistent charge
model**, not an interchangeable mix of the two scripts. Neither script is
a complete proof of the original six-unit implementation bound.

## D. Stage-1B replay is data, not trained creativity weights

The Library folder `/FORGE-6 Stage-1B` contains archived replay builders,
compressed proof-action records, and checkpoint reports. Samples:

- Initial `stage1b_checkpoint.json`: 500 requested, 500 validated, 1,987
  action records, zero recorded first failure.
- Chunk 001000--001499: 500/500 validated.
- Chunk 001500--001999: **408/500 validated**; recorded failures include
  Metamath proof-replay stack underflows. This is an incomplete batch.
- Chunks 002000--002499, 002500--002999, 003000--003499,
  003500--003999: each report 500/500 validated.
- The chunk 000500--000999 was **not identified among listed checkpoints**.
- Some archive scripts were built at different development stages; archived
  validation claims must not replace an independent full-corpus verification.

A `stage1b_checkpoint.json` verifying proof replays is **not** a trained
creative policy checkpoint. Do not treat its contents as model weights,
or assume every replay is valid because other batches report passing.

## E. Integration gaps remain

The recovered SAT scripts are **bounded reproducibility harnesses**, not
the six-board executable B0--B5, trained creativity implementation and
checkpoint, independently specified SAT certificate verifier, persistent
BANK, or end-to-end charged cost ledger.

Safe next steps:
1. Preserve pinned sources and results without editing them.
2. Select the **exact** evaluator/input representation for the original
   single-target Section 4 implementation claim, with the user approving any
   previously unresolved modeling decision. Do not redefine the target.
3. Independently confirm validity of archived replay corpus before any
   retraining and keep incomplete batches separate.
4. Find or recover the six-board coordinator/launcher and its trained
   creativity checkpoint; demonstrate live integration and BANK isolation.
5. Only after these gates are discharged begin 10 preregistered paired
   Eureka Prompt Experiment 1 comparisons.

**Classification: RECOVERY ADVANCED, SIX-BOARD INTEGRATION NOT YET VERIFIED.**
