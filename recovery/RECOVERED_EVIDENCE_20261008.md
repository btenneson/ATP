# FORGE-6 recovery evidence — 2026-10-08

Scope: READ-ONLY tests on original Library research artifacts. This note is
evidence about archived components, not a claim of a running FORGE-6 system.

## A. Original single-target SAT audit: reproduced

Source Library artifact:
`/FORGE6_IAE20_Single_Target_Certificate_Package.zip`

- Archive size: 266,662 bytes.
- Archive SHA-256: `c1c9047dd151f3e49065146c19631a9a4ab19c5b78da89bffdafdf9f4f484dc4`.
- Embedded script: `forge6_iae20_single_target_checks.py`.
- Script SHA-256: `a750b33bbfc535f366867bf787da975040c71a1c190ed4d941ee9284b03752ab`.
- Executed unchanged using `python -I forge6_iae20_single_target_checks.py` in an isolated Python process.
- The complete stdout was byte-identical to the archive's
  `FORGE6_IAE20_Single_Target_Test_Output.txt`
  (both SHA-256:
  `faace62ba0af39c4974b533d415cc93ddba0f8490a30a22c379a6f4c252e15c8`).

Archived and reproduced output:

```text
STRUCTURAL_k_2_to_30_PASS: 29
OPPOSITE_LEDGER_MODELS_PASS: ({'x': 1, 'y': 2}, {'x': 1, 'y': 0})
EXACT_RANK_ARITHMETIC_k_2_to_40_PASS: 39
INDEXED_MODEL_TRIALS_PASS: 2900
NO_INDEX_ADVERSARIAL_k_2_to_30_PASS: 29
STATUS: finite checks only; universal claims require proofs.
```

This is a finite regression test for the previously published/audited
single-target SAT comparison. It is **not** a FORGE-6 federation, trained
creativity engine, general SAT solver, formal proof-assistant certificate,
or new discovery attributable to either experimental arm.

## B. Stage-1B replay records: integrity confirmed

Library directory: `/FORGE-6 Stage-1B/`.

Both batches were materialized without modifying their original Library copies.
SHA-256 hashes were computed on compressed bytes and checked against the
separately archived checkpoint JSON. The gzip records were parsed and each
`validated` flag was checked.

| Frozen chunk | Records | SHA-256 equals checkpoint | All validated | Recorded actions | Unique target labels |
|---|---:|---|---|---:|---:|
| 003000–003499 | 500 | YES | YES | 19,773 | 500 |
| 003500–003999 | 500 | YES | YES | 25,677 | 500 |
| Combined checked | 1,000 | Both YES | Both YES | 45,450 | 1,000 |

Original recorded source `set.mm` digest for both checkpoints:
`90de6bac87d549023fc83fb698a1baacfed3f99b71438722171674f16777c881`.

Checkpoint compressed-output hashes:
- 003000–003499: `6b5be630d82e56d4e6d3d4151ce8db728c90f8db706166962b0fc61efd791124`.
- 003500–003999: `e9ae050ecfe152b3bb0299f87a6eace7031dada46f289586ae3701c8110f7bdd`.

These checks establish internal integrity of the two archived batches and their
own validation records. They are not an independent Metamath re-verification of
all 45,450 actions and do not prove that trained weights or a FORGE-6 executable
were subsequently produced.

## C. GitHub search and authorization boundary

The current ATP main branch contains a standalone Metamath verifier.
The recovery branch runs its selftest successfully in GitHub Actions, with
`BLOCKED` reported as the six-board integration status and 16 unconfirmed
artifacts/contracts.

The main branches of ATP, Data-ATP, Hodge and selected development branches
contain components, learned creativity controller JSON, and historical
launchers but have not yielded an identified, exercised six-board B0–B5
launcher with the frozen SAT evaluator, recognition policy and verifier.

Historical eight-agent DATA-MIND settlement launchers and Hodge creativity
models may inform recovery, but cannot be silently substituted. No new or
existing repository file outside the recovery branch was edited.

## Next recovery decision

First locate the exact B0–B5 launcher and original trained-creativity
artifact, if stored outside inspected branches or in an unindexed source.
Then pin provenance and run a real integration test. Only after that start
any control/Eureka experimental trials.

**Official Eureka Prompt Experiment 1: 0 / 20 runs.**
