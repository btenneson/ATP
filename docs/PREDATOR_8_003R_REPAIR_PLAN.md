# Predator 8.003R Repair Plan

**Status:** Planned controlled repair  
**Historical source:** Predator 8.003  
**Rule:** Never overwrite the original 8.003 files, model, logs, or reports.

## Objective

Create a repaired Predator 8.003 condition that uses the already trained and hashed `sgrpcl` model but corrects the search-control defects that invalidated the original five-expansion run.

Predator 8.003R is not a retrained model and not a dense-curriculum experiment. It is the valid broad-training control needed before interpreting Predator 8.004 or designing Predator 8.005.

## Frozen scientific elements

The following must remain unchanged for the primary repair comparison:

- target: `sgrpcl`
- frozen Metamath environment
- saved Predator 8.003 policy model
- model SHA-256: `90a1c0da192d76d4695ec11593dc58bff603939ca58fa05ef84d5913f60b084a`
- global expansion budget: 80,000 unless the historical protocol proves a different frozen value
- maximum logical depth: 10
- maximum open goals: 6
- opener cap: 48
- agents: 4
- creativity: 0.55
- seed: 2301
- independent Metamath verification requirement

Any necessary correction to an uncertain frozen value must be documented before the rerun rather than silently guessed.

## Defect 1: ranking and truncation before legality

### Historical behavior

```text
rough candidate retrieval
→ model ranking
→ candidate truncation
→ full unification
```

Inapplicable candidates could occupy the retained slots. When later unification rejected them, the search could produce no children and empty its frontier after only a few expansions.

### Required behavior

```text
rough candidate retrieval
→ rename assertion variables apart
→ full unification against the selected goal
→ instantiate and validate all required hypotheses
→ construct executable legal applications
→ score legal applications
→ truncate the legal list
→ generate and enqueue successor states
```

The learned model may order legal actions. It must not decide which actions are formally legal.

## Defect 2: exit-code misclassification

The runner must distinguish:

| Exit code | Meaning | Reported result |
|---|---|---|
| 0 | verified proof produced | `VERIFIED_PROOF` after independent verification |
| 1 | search completed without proof | `BOUNDED_UNKNOWN` or `FRONTIER_EMPTY`, according to diagnostics |
| 2+ | implementation or environment failure | `FAULT` or `PROTOCOL_FAILURE` |

A nonzero exit code is not automatically catastrophic.

## Required diagnostics

At minimum, record per expansion or at useful intervals:

- expansion number
- selected goal
- number of rough candidates
- number surviving rename-apart and unification
- number of constructed legal applications
- number retained after ranking and cap
- number of generated children
- duplicate-state rejections
- frontier size before and after expansion
- maximum frontier size
- current depth distribution
- elapsed wall time
- memory use when available
- termination reason

A five-expansion termination is not accepted without diagnostics showing why every legal route disappeared.

## Safety and preservation

Create a separate tree such as:

```text
versions/predator-8.003R/
experiments/sgrpcl/8.003R/
```

Do not modify:

```text
versions/predator-8.003-original/
original model files
original checkpoints
original reports
original autonomous logs
```

Copy required source files and record hashes of both source and repaired copies.

## Validation before the full rerun

1. Run Python syntax compilation on every changed file.
2. Run parser, unification, disjoint-variable, and certificate-verifier self-tests.
3. Construct a regression test where high-ranked rough candidates fail unification but a lower-ranked candidate is legal; confirm the legal candidate survives.
4. Confirm ordinary no-proof completion returns exit code 1 and is not labeled catastrophic.
5. Run small positive controls with known independently verifiable certificates.
6. Run a deliberately bounded negative/unknown control and confirm clean termination.
7. Freeze the repaired source commit and exact command.

## Primary rerun

Use the saved model without retraining. The expected command should point explicitly to the preserved 8.003 model, repaired search program, frozen environment, budget, report path, and certificate output path.

The run must continue until one of its declared stopping conditions occurs:

- verified proof
- expansion or other frozen budget exhausted
- legal frontier empty
- actual software/environment fault
- explicit user stop
- unavoidable session or machine loss

Do not invent a new wall-clock cutoff after the run starts.

## Hypothesis

The project hypothesis is:

> Predator 8.003R will not repeat the original trivial five-expansion bailout. It will search stably and terminate through proof, honest budget exhaustion, honest frontier exhaustion, or a clearly identified fault.

This is not yet a result.

## Relationship to Predator 8.005

Predator 8.003R is the planned stable software foundation for Predator 8.005.

Predator 8.005-A should add the existing Predator 8.004 density method to 8.003R without changing the mathematics or training technique. Predator 8.005-B may then add separately declared training improvements. This separation allows the project to determine whether gains come from the stable foundation, dense preparation, or the new training method.
