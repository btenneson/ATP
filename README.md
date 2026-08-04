# Predator Automated Theorem Proving

Research and reproducibility repository for Brian Tenneson's Predator automated-theorem-proving project.

Predator combines symbolic Metamath proof search, machine-learned action ranking, controlled exploration, and independent certificate verification. Search software may propose a proof, but only the verifier may certify it.

## Current research sequence

1. Preserve the ongoing Predator 8.004 `sgrpcl` experiment without interruption.
2. Build Predator 8.003R from the historical 8.003 source, repairing search control without retraining its saved model.
3. Compare repaired broad training with the 8.004 dense subject-conditioned experiment.
4. Build Predator 8.005 on the repaired 8.003R foundation, port the 8.004 density technique, and test separately declared training improvements.

## Project documentation

- [Predator lineage and roadmap](docs/PREDATOR_LINEAGE_AND_ROADMAP.md) — Predator 7.1, early Predator 8, 8.001, 8.002, 8.003, 8.003R, 8.004, and the planned 8.005 conditions.
- [Predator 8.003R repair plan](docs/PREDATOR_8_003R_REPAIR_PLAN.md) — frozen controls, legal-first candidate handling, exit-code correction, diagnostics, tests, and rerun protocol.
- [Metamath verifier notes](METAMATH_VERIFIER.md) — certificate-verification documentation already preserved in this repository.

## Current interpretation

- **Predator 8.003 training completed**, but its first `sgrpcl` search trial was invalidated by a five-expansion frontier collapse and incorrect exit-code classification.
- **Predator 8.003R is planned**, using the same saved model with repaired legal-first search.
- **Predator 8.004 is experimental.** Its `prcom` pilot produced verified certificates under dense methods; the `sgrpcl` outcome remains unresolved until the run reaches its declared stopping condition.
- **Predator 8.005 is planned** as a controlled reconstruction on the repaired 8.003R foundation, with the 8.004 density method and separately identified training improvements.

## Outcome discipline

- `VERIFIED_PROOF`: an independent verifier accepts the certificate.
- `BOUNDED_UNKNOWN`: the configured budget ended without a certificate.
- `FRONTIER_EMPTY`: no legal search states remained under the frozen bounds.
- `FAULT`: an implementation or environment problem invalidated the run.
- `RUNNING`: a process status only, not evidence of mathematical success.

A timeout or failed search is not a refutation, and a long-running process is not yet a proof.

## Attribution

Project lead and original research direction: **Brian Tenneson**  
Contact: **btenneson2301@baypath.edu**
