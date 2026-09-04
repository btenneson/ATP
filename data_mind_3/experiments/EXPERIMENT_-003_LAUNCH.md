# DATA MIND 3.1 Experiment -003 — Ocean-150 Professional ATP Comparison

Authorized by user: 2026-09-03 America/Los_Angeles

## Purpose
Run a professional ATP comparison on frozen Ocean problems whose verified shortest proof depth is exactly 150.

## Frozen benchmark
- 10 previously unused deterministic seeds: 90315001, 90315002, 90315003, 90315004, 90315005, 90315006, 90315007, 90315008, 90315009, 90315010.
- Declared and independently BFS-checked shortest depth: L*=150.
- Each professional ATP receives only the generated TPTP problem file.
- Problem generation is deterministic from the frozen generator already in this repository.

## Lanes
Professional ATP lanes:
1. Vampire 5.0.1
2. E Prover 3.2.5 official source build
3. iProver current master build artifact (upstream revision recorded at run time)
4. SPASS from the Ubuntu 24.04 package repository (package version recorded at run time)
5. Prover9 current LADR-2026 source (exact commit recorded at run time)

Internal/calibration lanes:
6. Depths-F known-map calibration floor. It is explicitly non-general and is not ranked as a fair professional ATP competitor.
7. DATA MIND 3.1 Ocean adapter from the frozen Experiment 002 lineage, using only the public problem graph and the independent Ocean certificate verifier.

## Resources
- Hard per-lane wall-clock limit: 1,800 seconds.
- At most four seed jobs run in parallel.
- Each seed job runs all seven lanes and retains raw outputs/evidence.
- GitHub-hosted Ubuntu 24.04 runners.

## Acceptance and evidence
- Raw solver output is retained for every professional ATP lane.
- Professional ATP proof status requires a native theorem/proof success marker; faults, unavailable installations, and timeouts are recorded separately.
- DATA MIND 3.1 and Depths-F path certificates are checked by `data_mind_3.ocean.verifier.verify_ocean_certificate`.
- The manifest stores the generated problem SHA-256, seed, L*, source, target, vertex count, edge count, and BFS check.
- Environment/version evidence is stored with every seed artifact.

## Interpretation guard
Depths-F is a known-map calibration floor, not a general ATP. DATA MIND 3.1 is a separate internal lane. The headline professional comparison is among Vampire, E, iProver, SPASS, and Prover9 under the same 1,800-second wall-clock cap.
