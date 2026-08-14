# Settlement Compass Optimization

**Status:** new ATP optimization strategy, initiated 13 August 2026.

This folder develops a discrete **settlement compass** for proof-ocean navigation. The optimization problem is not “which statement is true?”—that remains the job of verifier-backed certifiers—but **which admissible next tunnel should receive computation so that search is drawn toward a certified settlement state as efficiently as possible**.

The four terminal classes are proof (`P`), refutation (`R`), independence (`I`), and contradiction (`C`, meaning both the target and its negation are certified in the declared base). Actual settlement is mutually exclusive and one-hot. If `S_k(x)` is the certified settlement indicator,

```text
S_P(x) + S_R(x) + S_I(x) + S_C(x) <= 1.
```

At a settled state exactly one coordinate equals 1. Before settlement all four certified-state indicators equal 0. Fractional quantities such as `F_P, F_R, F_I, F_C` are **navigation estimates**, not settlement certificates.

The ideal compass on a solved proof DAG uses exact graph distance to the nearest certified settlement. With a deterministic tie-break, the next vertex is the outgoing neighbor minimizing that distance. Under finite reachability, the exact compass has the fundamental property

```text
Fix(N) = C_settlement,
```

and distance strictly decreases outside the settlement set. On solved DAGs this ideal distance can be computed exactly by backward graph search; on unseen proof oceans it must be predicted from features such as prior proof geometry, landmarks, settlement-density measurements, and tensor-valued cross-agent information.

The discrete settlement tensor is the companion resource-allocation model. It estimates direct progress, reusable lemma value, and transfer value among agents/search modes. Under concavity assumptions the resulting allocation problem can be treated with Lagrange/KKT methods; under discrete diminishing-return assumptions, adaptive greedy/submodular methods are another candidate.

### Repository contents

- `docs/pdf/AMLD_Compass_Fixed_Point_and_Proof_Ocean_Navigation.pdf` — formal fixed-point, monotonicity, distance-to-settlement, and proof-DAG compass paper, generated from LaTeX.
- `docs/pdf/DATA_3_AMLD_Settlement_Tensor_Optimization_Expanded_Illustrated.pdf` — illustrated settlement-density/tensor and constrained optimization paper, generated from LaTeX.
- `docs/latex/` — canonical LaTeX sources for both papers.
- `THEORY.md` — compact formal specification of the strategy.
- `BENCHMARK_001.md` — frozen benchmark protocol for 10 training DAGs, 49 downstream theorem targets, and one hidden Infinity target under the deliberately weakened no-Infinity base.

The PDF files are built and committed by `.github/workflows/settlement-compass-docs.yml`. The first benchmark's binary fixture package is retained separately from this source folder; the GitHub protocol document is the authoritative description until that fixture package is imported into the repository.

### Current research objective

The central empirical question is whether geometry learned from retained solved proof DAGs can reduce verified search cost on unseen related targets. The benchmark must compare the compass against the identical search with compass guidance disabled and must retain complete search DAGs, including failed branches, so that tunnel choices can later be audited.

## AI Integrity Statement

Brian Tenneson is responsible for the research direction, mathematical claims, interpretation, and release of this material. OpenAI ChatGPT was used as an AI research and drafting consultant for mathematical formalization, literature search, exposition, figure preparation, benchmark design, and repository documentation. No theorem, benchmark result, or claim of independence is accepted solely because it was suggested by an AI system. Formal claims require the stated definitions and proofs; experimental claims require preserved data, frozen protocols, and verifier-backed certificates. Proposed terminology and architecture remain research proposals unless independently validated.

## References

1. S. Boyd and L. Vandenberghe, *Convex Optimization*. Cambridge University Press, 2004. https://web.stanford.edu/~boyd/cvxbook/
2. M. Zinkevich, “Online Convex Programming and Generalized Infinitesimal Gradient Ascent,” *ICML*, 2003. https://www.cs.cmu.edu/~maz/publications/ICML03.pdf
3. D. Golovin and A. Krause, “Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization,” *JAIR* 42 (2011), 427–486. https://arxiv.org/abs/1003.3967
4. Z. Goertzel, J. Jakubův, and J. Urban, “ENIGMAWatch: ProofWatch Meets ENIGMA,” 2019. https://arxiv.org/abs/1905.09565
5. S. Huang, P. Song, R. J. George, and A. Anandkumar, “LeanProgress: Guiding Search for Neural Theorem Proving via Proof Progress Prediction,” 2025. https://arxiv.org/abs/2502.17925
6. N. D. Megill and D. A. Wheeler, *Metamath: A Computer Language for Mathematical Proofs*. https://us.metamath.org/downloads/metamath.pdf
