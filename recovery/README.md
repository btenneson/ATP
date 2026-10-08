# FORGE-6 Eureka Experiment 1: read-only recovery

This recovery directory belongs only to branch
`recovery/forge6-eureka-exp1-20261008` in `btenneson/ATP`.
It does not replace, install, or claim to execute FORGE-6.

## Verified starting points

- `metamath.py` on ATP main is an independent **Metamath** verifier. Its
  selftest cannot certify the SAT `F_k` implementation or the six-board engine.
- The historical eight-agent DATA-MIND 3.1 branch
  `dm31-frozen20-training-settlement-dev` has a fail-closed official gate
  and unresolved runtime configuration. It is **not** FORGE-6 B0--B5.
- The Hodge repository contains distinct creativity programs and saved learned
  controller models. Their presence does not establish that FORGE-6 loaded or
  trained the correct creativity layer for this experiment.
- Previous `set.mm` Stage-1B checkpoints exist in the user's research
  Library, but a replay checkpoint is not a six-board launcher.

## Purpose and boundaries

The frozen pilot compares ten paired ordinary and Eureka Prompt runs on the
original `F_k` cost-implementation target. Each run allows at most 20
investigation iterations; both arms must use **the same** trained creativity
implementation and initial BANK. The Eureka arm is allowed exactly one
verbatim-recorded Scout hint before its first investigation iteration, charged
to the common total budget.

Existing conditional theorems, the two-candidate benchmark, and the prior
single-target underdetermination analysis are **known inputs**, not newly
discovered results. The original single-target recognition and fully charged
six-unit obligation remain distinct.

This branch is deliberately non-executable as a settlement system:
`forge6_exp1_manifest.json` leaves unverified paths unset rather than
inventing components or silently substituting a surrogate prover.

## Local diagnostic command

```bash
python recovery/forge6_readiness.py
```

The diagnostic executes `metamath.py selftest` with a 60-second timeout, scans
the manifest-listed local artifacts, checks SHA-256 when pinned, and writes
`recovery/forge6_readiness_report.json` (untracked output). It never
starts a FORGE-6 settlement trial. A successful diagnostic execution may still
correctly report `BLOCKED`.

The GitHub Actions workflow
`.github/workflows/forge6-recovery-preflight.yml` performs the same
diagnostic automatically on pushes to this recovery branch and uploads the
JSON report as an artifact. The workflow has read-only repository permissions.

## Recovery order

1. Identify the **actual six-board** executable launcher and one stable commit.
2. Bind each board B0--B5 and independently prove that the full federation
   is exercised, not merely named in a manifest.
3. Identify the exact trained creativity code, artifact hash, provenance, and
   loaded model. Do not quietly use ChatGPT text creativity.
4. Pin a verifier compatible with the frozen `F_k` cost problem, the
   total deterministic evaluator, recognition procedure, BANK, and ledger.
5. Produce a genuine live integration-test receipt showing consistent output
   from all six boards and certificate-gated BANK writes.
6. Freeze the input and cost interfaces, then and only then run the 10 paired
   comparisons under the original randomized schedule.

**Trial count: 0/20.** No repository or experiment is declared ready solely
because this branch or diagnostic exists.
