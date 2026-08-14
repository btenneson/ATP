# Compass Benchmark 001

**Frozen:** 13 August 2026.

## Purpose

This first deliberately generous experiment asks whether a compass trained on ten solved proof DAGs can reduce verified search cost on related unseen targets while preserving the mutually exclusive `P/R/I/C` settlement semantics.

## Training set

Ten randomly drawn Metamath theorems from the pre-Infinity ZF development were retained as complete dependency DAGs. The frozen roots are:

`pwidg, axreplem, f1ores, fiinf2g, eqop, frpomin, rabab, rabun2, eusn, elun2`.

The training draw seed is `20260813`. Exact distance to each training terminal can be computed backward on the retained DAG and used as a ground-truth compass label.

## Test set

There are 50 opaque target IDs. Forty-nine are randomly sampled downstream theorem/corollary-style targets whose existing Metamath proofs transitively use at least one training root. One additional target is an unlabeled copy of the Axiom of Infinity statement. The 49 ordinary targets plus the single special target are shuffled with seed `20260815`.

The benchmark base deliberately withholds Infinity. Therefore the special target is intended to test the independence agent `I`, but **failure of P and R is not an independence certificate**. Full credit requires a legitimate model-theoretic or relative-consistency certificate relative to the precisely frozen base.

## Terminal scoring

Each target receives exactly one submitted outcome: `P`, `R`, `I`, `C`, or `UNKNOWN`. Certified terminal outcomes are mutually exclusive. The primary score is fully correct certified classifications out of 50, with the 49 ordinary-target score and the special independence target reported separately.

## Required comparisons

The same underlying search machinery should be run with and without compass guidance under identical resource limits. Record expansions, wall time, peak memory, certificate size, and full search DAGs including failed branches. A later benchmark should remove the generous “downstream of training roots” conditioning and sample more broadly.

## Anti-leakage rule

The navigator receives formulas and permitted base information only. It must not receive hidden outcome labels, source theorem names used only for audit, or future proof-path data. The audit manifest remains separate from navigator inputs.

## AI Integrity Statement

Brian Tenneson is responsible for the research direction, mathematical claims, interpretation, and release of this material. OpenAI ChatGPT was used as an AI research and drafting consultant for mathematical formalization, literature search, exposition, figure preparation, benchmark design, and repository documentation. No theorem, benchmark result, or claim of independence is accepted solely because it was suggested by an AI system. Formal claims require the stated definitions and proofs; experimental claims require preserved data, frozen protocols, and verifier-backed certificates. Proposed terminology and architecture remain research proposals unless independently validated.

## References

1. S. Boyd and L. Vandenberghe, *Convex Optimization*. Cambridge University Press, 2004. https://web.stanford.edu/~boyd/cvxbook/
2. M. Zinkevich, “Online Convex Programming and Generalized Infinitesimal Gradient Ascent,” *ICML*, 2003. https://www.cs.cmu.edu/~maz/publications/ICML03.pdf
3. D. Golovin and A. Krause, “Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization,” *JAIR* 42 (2011), 427–486. https://arxiv.org/abs/1003.3967
4. Z. Goertzel, J. Jakubův, and J. Urban, “ENIGMAWatch: ProofWatch Meets ENIGMA,” 2019. https://arxiv.org/abs/1905.09565
5. S. Huang, P. Song, R. J. George, and A. Anandkumar, “LeanProgress: Guiding Search for Neural Theorem Proving via Proof Progress Prediction,” 2025. https://arxiv.org/abs/2502.17925
6. N. D. Megill and D. A. Wheeler, *Metamath: A Computer Language for Mathematical Proofs*. https://us.metamath.org/downloads/metamath.pdf
