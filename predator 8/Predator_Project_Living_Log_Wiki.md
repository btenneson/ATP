# Predator ATP Project — Living Log and Wiki

**Project lead:** Brian Tenneson  
**Snapshot date:** August 2, 2026, 12:26 PM Pacific Time  
**Scope:** Predator 7.1, Predator 8.002, Predator 8.003, current experiments, and planned benchmarks.

> This is a living research log. “Completed” means supported by an independently verified certificate or a recorded experiment. “Planned” means not yet performed. A timeout or exhausted budget is recorded as **bounded unknown**, never as a mathematical failure.

---

## Current status

### Predator 8.003 — `sgrpcl` experiment

**Target theorem:** closure of a semigroup operation.

\[
((G \in \mathrm{Smgrp} \land X \in B \land Y \in B) \to (X \, .o. \, Y) \in B),
\]

where \(B = \operatorname{Base}(G)\).

**Last observed screen status at approximately noon PT:**

- Trace events processed: **110,000 / 131,078**
- Preprocessing completion: **83.9%**
- Retained policy events: **108,568**
- Training examples saved: **649,094**
- Atomic checkpoint: **110,000**
- Stage: building the training dataset before final model fitting and proof search

The autonomous runner is designed to resume from checkpoints, train the sparse logistic policy, save the model and report, launch the `sgrpcl` search, verify any certificate, and update its notebook, status, logs, and final summary.

Expected output folder:

```text
sgrpcl_8_003\
├── Predator_8.003_policy_sgrpcl.joblib
├── Predator_8.003_training_report.json
├── research_notebook.md
├── status.json
├── autonomous.log
├── final_summary.json
└── checkpoints\
```

The screenshot is evidence of active training/preprocessing, not evidence that `sgrpcl` has already been proved.

---

## Version comparison

| Version | Main idea | Learning | Key record | Status |
|---|---|---|---|---|
| **Predator 7.1** | Symbolic Metamath search using unification and independent verification | None | Exposed duplicate-theorem contamination; later cross-subject controls produced two verified proofs and three one-minute bounded unknowns | Historical baseline |
| **Predator 8.002** | Population search with learned ranking and controlled creativity | Sparse logistic policy | `prcom`: independently verified proof at 2,633 expansions; matched unguided search bounded unknown at 5,000 | Proof of concept |
| **Predator 8.003** | Autonomous train → checkpoint → search → document protocol | Sparse logistic policy trained at the `sgrpcl` cutoff | Today’s transfer experiment on semigroup closure | Running / outcome pending |

---

## Predator 7.1

### Architecture

Predator 7.1 separated formula construction from logical proof search. It extracted the grammar from `set.mm`, generated syntax proof steps from parse trees, and searched for logical assertion applications.

Its major advance over 7.0 was **unification**, allowing use of assertions such as `ax-mp` whose hypotheses are not completely determined by the conclusion.

Important controls included:

- expanding the most constrained open goal first;
- preserving essential-hypothesis order;
- treating branch-closing and branch-extending assertions separately;
- checking completed certificates with an independent Metamath verifier.

### Duplicate-theorem protocol lesson

Four early certificates verified formally, but later analysis found that they were one-step citations of duplicate or immediate-instance statements already present earlier in the database. The proofs were valid but scientifically trivial. This led to stronger controls excluding the target, downstream results, exact duplicates, and immediate substitution instances.

### Cross-subject one-minute controls

| Theorem | Subject | Outcome |
|---|---|---|
| `pm2.27` | Propositional logic | Verified proof; 369 expansions; about 18 seconds |
| `dfsymdif2` | Set theory | Verified proof; 379 expansions; about 33 seconds |
| `0cn` | Complex numbers | Bounded unknown at about 60 seconds |
| `sgrpcl` | Group theory | Bounded unknown at about 60 seconds |
| `topopn` | Topology | Bounded unknown at about 60 seconds |

---

## Predator 8.002

The ML component ranks legal pairs of the form:

```text
(current open goal, candidate assertion application)
```

It is a sparse logistic classifier trained by stochastic gradient descent, not a neural network. Machine learning changes search priority; the symbolic engine still creates proof states and the independent verifier still decides correctness.

### Controlled `prcom` result

\[
\texttt{prcom} \qquad \vdash \{A,B\} = \{B,A\}.
\]

| Condition | Outcome | Expansions |
|---|---|---:|
| Unguided population | Bounded unknown | 5,000 |
| Predator 8.002 ML-guided population | Independently verified proof | 2,633 |

At the root, `3eqtr4i` moved from unguided rank 134 of 150 to learned rank 64. Controlled counterfactual exploration admitted it, and the completed proof verified. This is a finite-instance proof of concept, not a universal speedup theorem.

---

## Predator 8.003

### Autonomous pipeline

```text
verified pre-target proofs
        ↓
trace replay and example generation
        ↓
atomic checkpoints every 5,000 trace events
        ↓
FeatureHasher + logistic SGD training
        ↓
saved .joblib policy and JSON report
        ↓
four-agent sgrpcl proof search
        ↓
certificate verification and final records
```

### Recorded training configuration

| Setting | Value |
|---|---|
| Cutoff | Immediately before `sgrpcl` |
| Maximum eligible training theorems | 2,000 |
| Alternative samples per event | Up to 8 |
| Feature dimensions | 131,072 |
| Epoch ceiling | 35 |
| Seed | 2301 |
| Checkpoint segment | 5,000 events |
| Default proof-search budget | 80,000 expansions |

The model is:

```text
FeatureHasher + SGDClassifier(loss="log_loss")
```

The experiment’s automatic run notebook is:

```text
sgrpcl_8_003\research_notebook.md
```

This project wiki is the higher-level history; the automatic notebook is the detailed machine-generated record for one run.

---

## Planned work

### Immediately after the current run

1. Archive the complete output folder before changing code.
2. Classify the result precisely: verified proof, bounded unknown, interruption, overflow, or actual fault.
3. Verify any proof in a fresh process.
4. Record database/model hashes, wall time, expansions, certificate length, and logs.
5. Correct two runner/reporting issues before benchmarking:
   - ordinary budget exhaustion must be recorded as bounded unknown rather than catastrophic error;
   - a Metamath certificate should have an `.mm` filename, with JSON reserved for structured reports.

### Phase 1 — pilot the benchmark code

Run **10 pilot theorems** to test random selection, one-minute timeouts, process isolation, logging, certificate verification, and result-table generation. Exclude pilot targets from the final scientific sample.

### Final comparison

Use the locked **50-theorem benchmark** unless a new protocol is frozen before final results are inspected.

Controls:

- same frozen `set.mm` file and hash;
- same theorem manifest for every version;
- seed 2301;
- fresh process for every theorem–prover pair;
- no parallel runs;
- one-minute wall-clock ceiling;
- timeout = bounded unknown;
- no substitutions, rerolls, or cherry-picking;
- independent certificate verification;
- report wall time, expansions, proof length, memory, and outcome;
- alternate run order to reduce caching and thermal bias.

For the first frozen 8.003 transfer test, sample eligible theorems declared after `sgrpcl`, because the current model was trained only from proofs before that cutoff.

### Longer-term direction

- Test whether the `prcom` improvement transfers across a theorem sample.
- Measure run-to-run variation across seeds.
- Separate expansion efficiency from wall-clock model-scoring cost.
- Add stronger learned models only after the logistic baseline is measured.
- Use Predator variants as verified proposal agents in the Automated Logical Decider framework.
- Progress toward HaloProof after smaller transfer experiments are stable.

---

## Experimental vocabulary

| Term | Meaning |
|---|---|
| **Verified proof** | Complete certificate accepted by the declared independent verifier |
| **Bounded unknown** | No verified proof found before the declared resource limit |
| **Fault** | Program, parser, verifier, or protocol error |
| **Expansion** | One proof-search state expansion; not the same as proof length |
| **Training cutoff** | Declaration position after which theorem proofs are hidden from training |
| **Leakage** | Target proof, duplicate, downstream route, or equivalent target-specific information entering training |
| **ML guidance** | Learned prioritization of legal search moves |
| **Creativity** | Protected exploration of lower-ranked legal alternatives |

---

## Update template

```text
Date and time:
Predator version:
Target:
Database filename and SHA-256:
Model filename and SHA-256:
Seed:
Wall-clock limit:
Expansion budget:
Outcome:
Wall time:
Expansions:
Certificate filename:
Fresh-process verifier result:
Faults or warnings:
Interpretation:
Files archived at:
```

---

## Source record used for this snapshot

- *Predator 7.1 Documentation and Cross-Branch Reuse Rate Theory*, Revision 2.
- *Predator 7.1 Cross-Subject Control Run Summary*.
- *Depths of Induction, ML-Guided Proof Search, and Formalized Self-Awareness*, Version 47.
- *Section 8 — Predator 8.002 Connection*.
- `Predator_8.003_Autonomous_sgrpcl_Bundle`.
- The noon screenshot showing active 8.003 preprocessing.
- Frozen benchmark decisions recorded in the project conversation.

---

## Revision history

### Snapshot 001 — August 2, 2026

Created the first consolidated past–present–future project log. The current Predator 8.003 outcome remains pending.
