# Settlement Compass Implementation Status

**Date:** 13 August 2026  
**Research direction:** Brian Tenneson

The settlement compass is being implemented as a new ATP optimization strategy. The goal is to learn a potential or distance-to-settlement estimate from retained solved proof DAGs and use that estimate to prioritize the next admissible search tunnel while preserving verifier sovereignty.

## Implemented

- Frozen ten-DAG training set from the pre-Infinity `set.mm` development.
- Frozen Benchmark 001 target design: 49 downstream theorem targets plus one withheld Infinity formula under the declared no-Infinity base.
- Reproducible proof-dependency DAG extraction.
- Exact distance-to-training-settlement labels on solved DAGs.
- First learned theorem-landmark relevance model.
- First learned within-DAG distance estimator.
- Matched compass-versus-random navigation diagnostic on 49 held-out proof DAGs.
- Machine-readable JSON and CSV result outputs.

## Current empirical status

The first diagnostic found substantial held-out proof-DAG relevance signal (mean AUC approximately 0.788) and a weak positive distance signal (mean Spearman approximately 0.274). The compass brought the first genuine proof-DAG landmark to median rank 1 versus rank 4 for randomized ordering. It did **not** improve identification of exact distance-1 parents; on that measure it lost narrowly to random overall.

Accordingly, the current implementation is evidence for **global/mesoscopic attraction toward relevant proof territory**, not yet evidence for a reliable local gradient to the next optimal inference.

## Next implementation

The next race must operate inside an actual inference-generating proof search. Candidate generation, verifier, seed, and budget will be identical across arms. Only priority ordering will differ. Complete search DAGs, including failed branches, will be retained so that the learned compass can be trained on genuine alternatives rather than only the successful final dependency graph.

## Settlement invariant

Actual terminal settlement is mutually exclusive. For certified indicators `S_P,S_R,S_I,S_C`,

`S_P + S_R + S_I + S_C <= 1`.

At an unsettled state every certified indicator is zero. At a settled state exactly one is one. Any fractional `F_P,F_R,F_I,F_C` quantity is a navigation estimate and never a partial settlement certificate.

## AI Integrity Statement

Brian Tenneson set the research direction. OpenAI ChatGPT was used as an AI research and implementation consultant for mathematical formalization, coding, experimental design, execution, interpretation, and documentation. Experimental results are reported only from preserved computations. Mathematical settlement is accepted only from the designated verifier/certificate mechanism. Search failure is never treated as an independence certificate.

## References

1. N. D. Megill and D. A. Wheeler, *Metamath: A Computer Language for Mathematical Proofs*. https://us.metamath.org/downloads/metamath.pdf
2. S. Huang et al., “LeanProgress: Guiding Search for Neural Theorem Proving via Proof Progress Prediction,” 2025. https://arxiv.org/abs/2502.17925
3. Z. Goertzel, J. Jakubův, and J. Urban, “ENIGMAWatch: ProofWatch Meets ENIGMA,” 2019. https://arxiv.org/abs/1905.09565
4. M. Zinkevich, “Online Convex Programming and Generalized Infinitesimal Gradient Ascent,” *ICML*, 2003. https://www.cs.cmu.edu/~maz/publications/ICML03.pdf