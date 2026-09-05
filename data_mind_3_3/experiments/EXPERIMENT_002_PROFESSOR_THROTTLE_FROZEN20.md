# DATA MIND 3.3 Experiment 002 — Professor Actual-Call Throttle Frozen-20

**Status:** PREREGISTERED BEFORE LAUNCH

## Question

How rarely can the Professor be actually invoked while preserving verifier-accepted settlement performance?

## Frozen benchmark

Use `DATA-MIND set.mm Frozen-20 Benchmark 001` with the same proof-safe held-out reconstruction, exact frozen `set.mm`, and independent `metamath.py` verification protocol used by Experiment 001.

## Arms

The ordinary controller observation/update interval is fixed at 16 in every arm. Dreamer is OFF in every arm. Child play is OFF in every arm. Only the actual Professor-call cadence varies:

- `prof-off`: Professor is never actually called; before any grade the controller uses the locally checked raw partial-credit signal.
- `prof-16`: actual Professor call interval 16 expansions.
- `prof-64`: actual Professor call interval 64 expansions.
- `prof-256`: actual Professor call interval 256 expansions.

Between actual Professor calls, the most recent Professor grade is reused exactly as implemented by the frozen `ReflectiveP1Controller` semantics. `prof-off` is implemented by an experiment-only subclass whose `_professor_due` predicate is always false; it does not modify verifier or search semantics.

## Primary endpoint

`verified_settlements` per arm over the 20 frozen targets.

A target counts as settled only when the independent Metamath verifier accepts the produced proof certificate. Workflow/job success is not theorem success.

## Secondary endpoints

For each arm record expansions, wall time, generated children, actual Professor calls, Professor updates, accounted resource units, proof length when verified, and target-level paired differences versus `prof-256` and `prof-off`.

## Frozen search budget

- controller interval: 16
- maximum expansions: 100000
- timeout: 1800 seconds per arm/target
- candidate cap: 64
- maximum depth: 24
- maximum open goals: 24
- maximum frontier: 200000
- experiment seed: 330002

## Proof-safety / verifier boundary

The settlement parser is proof-redacted. Every non-target held-out theorem is removed from the legal search library. Any candidate referencing a held-out theorem label is rejected before the independent verifier. No held-out proof text, hidden theorem truth, or future verifier outcome is supplied to Professor or controller.

## Interpretation

The experiment isolates Professor actual-call cadence. A reduction in actual calls without loss of verified settlements is evidence that Professor can be more aggressively throttled under this benchmark and budget. A settlement change is interpreted only through paired verifier-accepted outcomes. Normalized accounted units are bookkeeping and do not assert CPU equivalence across operation classes.

No parameters may be changed after launch without creating a separately named experiment.
