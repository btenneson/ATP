# Predator 8.038 — `prcon` Real-Target Attempt History

This file is an append-only scientific history for the real-target `prcon` experiment described in `experiments/P8_038_PRCON_EXPERIMENT.md`.

The original protocol document is intentionally left unchanged. In particular, its wording says that a verified certificate causes the system to "stop that agent." The federation-wide halt rule described below was **not** present in that preregistered text.

## Attempt 1 — invalid implementation attempt

- Date: 2026-08-28
- GitHub Actions run: `33212395197`
- Source commit: `753748d659137b187672d7f1f8840e9d4c5b2425`
- Workflow: `Predator8 8.038 prcon revision prototype`
- Intended target: `prcon`
- Intended agents: `P1, P2, R1, R2, I1, I2, C1, C2`

### What actually happened

No theorem-search phase executed. Every matrix job failed during `Compile and self-test ATP` before Phase 1. The direct error was:

`predator8.py needs metamath.py and setmm_grammar.py in the same folder (No module named 'metamath')`

The required files were present in the repository root, but `predator 8/predator 8.001.py` places its own directory first on `sys.path`; the workflow did not also place the repository root on Python's import path. Therefore Attempt 1 produced **no scientific observation** about ordinary search, the diagnostic threshold, group-inverse revision, Phase 2, or the usefulness of the revision fallback.

Attempt 1 is retained as an invalid implementation attempt. It is not scored as a negative experimental result.

### Second defect discovered while auditing Attempt 1

Review of the workflow exposed a separate protocol/implementation omission. The real-target workflow used eight independent GitHub matrix jobs with `fail-fast: false`. A verified settlement by one agent would have stopped only that agent's own search path; there was no federation-wide rule or shared signal implementing

\[
\exists z\; V(z)=1 \quad\Longrightarrow\quad \mathrm{HALT\ ALL}.
\]

This omission was identified **before any valid real-target search result existed**. It is therefore being corrected prospectively, not in response to an observed scientific outcome.

## Amendment A1 — prospective correction before Attempt 2

Attempt 2 keeps the scientific controls already declared for Attempt 1 unless explicitly noted here:

- target remains `prcon`;
- agents remain `P1, P2, R1, R2, I1, I2, C1, C2`;
- seeds remain `2301` through `2308` as previously assigned;
- initial creativity coordinates remain `0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85`;
- each bounded phase remains at 12,000 expansions;
- maximum depth remains 12;
- maximum open goals remains 8;
- opener cap remains 64;
- the prototype diagnostic remains `D=0` after verified settlement and `D=1` after finite-resource UNKNOWN, with `tau=0.5`;
- when revision fires, the scalar logit-group inverse remains `c^{-1}=1-c`;
- the frozen `set.mm` source remains the same pinned revision used by Attempt 1.

Only implementation/protocol defects are corrected:

1. **Import-path repair.** The repository root is explicitly added to `PYTHONPATH`, allowing Predator 8.001 to import the already-versioned `metamath.py` and `setmm_grammar.py` dependencies.
2. **Preflight gate.** Compilation plus both verifier and ATP self-tests must pass before any of the eight search jobs start.
3. **Independent settlement verification.** A Predator return code of 0 is not by itself the federation halt signal. The emitted candidate is separately checked with the repository's Metamath verifier, restricted to the emitted `chk` theorem. A run-scoped settlement signal is published only after that independent check confirms exactly one verified proof.
4. **Federation-wide cooperative halt.** All search jobs poll for the run-scoped verified-settlement signal. Once one is published, active peer search processes are terminated and later phases are skipped. The signal is scoped to the current GitHub Actions run, so no prior experiment can trigger the halt.

### Distributed-run limitation

GitHub Actions matrix jobs execute on separate machines. The halt is therefore cooperative rather than atomic: another agent may perform a small amount of additional work during the interval between the first independent verification, publication of the settlement artifact, and the next peer poll. That race-window work is not treated as a continuation of the scientific search after settlement; it is recorded as coordination latency. The corrected workflow polls during each active search and checks again before Phase 2.

## Interpretation policy for Attempt 2

- If preflight fails, Attempt 2 is an invalid implementation attempt and yields no scientific result.
- If a search process returns an unexpected protocol code, that defect is reported separately and no unsupported theorem claim is made.
- `UNKNOWN` means only unknown under the declared finite controls.
- A settlement is counted only after independent Metamath verification.
- The first published verified-settlement signal is the federation settlement event; peer agents then halt cooperatively.
- Attempt 1 remains visible and is never rewritten as though these corrections had existed during that run.

This amendment was written before interpreting any valid `prcon` real-target result from Predator 8.038.
