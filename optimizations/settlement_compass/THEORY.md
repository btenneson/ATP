# Formal Strategy: Settlement Compass and One-Hot Terminal Geometry

## 1. Certified terminal partition

For a target WFF `w` over a frozen base theory `T`, define four terminal certificate classes:

- `C_P`: a verified certificate of `T |- w`, without simultaneous contradiction classification;
- `C_R`: a verified certificate of `T |- not w`, without simultaneous contradiction classification;
- `C_I`: a valid metatheoretic independence certificate for `w` relative to `T`;
- `C_C`: verified derivability of both `w` and `not w` in the declared base/context.

The implementation assigns at most one terminal label. Thus the certified settlement set is the disjoint union

```text
C = C_P ⊔ C_R ⊔ C_I ⊔ C_C.
```

For indicator coordinates `S_k(x) in {0,1}`,

```text
S_P + S_R + S_I + S_C <= 1,
```

with equality exactly at a settled state. This separates **actual settlement** from predictive quantities.

## 2. Proof ocean and exact compass

Represent admissible search as a directed graph `G=(V,E)`. Let `d_C(v)` be shortest directed distance from `v` to any certified terminal vertex, with infinity when none is reachable. On a solved retained DAG, `d_C` is computable exactly by backward search.

The exact compass is

```text
N(v) = v,                                  if v in C;
N(v) in argmin_{u: (v,u) in E} d_C(u),   otherwise.
```

If every considered vertex has finite distance to `C`, then every nonterminal compass move decreases `d_C` by one, so no nonterminal fixed point exists and

```text
Fix(N) = C.
```

This is the clean pairing of a halting/fixed-point set with a well-founded monotone ranking function.

## 3. Predictive direction field

Before certification, the navigator may maintain fractional directional estimates

```text
F(x) = (F_P, F_R, F_I, F_C),     F_k >= 0,     sum F_k <= 1.
```

These are not settlement states. They are calibrated estimates or features used to predict distance-to-settlement or expected value of an outgoing tunnel. The unused mass can represent unresolved direction. At terminal certification, the **certified state** is one-hot regardless of the predictive field.

## 4. Settlement density and tensor

“Settlement density” is a proposed measurement concept: weighted certificate-relevant information discovered per unit search volume or cost. The tensor `S_{a,b,r,c}` can encode source agent, recipient agent/certifier, search region, and terminal class. A contracted tensor can feed the directional field or a scalar potential.

A candidate tunnel score is conceptually

```text
Q(e) = expected settlement gain + landmark value + exploration value
       + cross-agent transfer value - computational cost.
```

The exact solved-DAG target for learning is simpler: predict the tunnel that most decreases true `d_C`.

## 5. Optimization regimes

For continuously divisible resource allocations, a concave settlement objective with convex constraints permits Lagrange/KKT optimization. Strict concavity gives a unique allocation; strong concavity gives stability bounds. For discrete computational quanta, adaptive greedy methods become relevant if diminishing-return assumptions such as adaptive submodularity are supported.

## 6. Experimental discipline

Training uses only information available at each historical state. Future proof-path information supplies labels but is hidden from the predictor. Evaluation must ultimately use fresh counterfactual searches and verifier-backed settlement, not merely agreement with one historical proof path. Search DAGs, failures, random seeds, budgets, and verifier outputs must be retained.

## AI Integrity Statement

Brian Tenneson is responsible for the research direction, mathematical claims, interpretation, and release of this material. OpenAI ChatGPT was used as an AI research and drafting consultant for mathematical formalization, literature search, exposition, figure preparation, benchmark design, and repository documentation. No theorem, benchmark result, or claim of independence is accepted solely because it was suggested by an AI system. Formal claims require the stated definitions and proofs; experimental claims require preserved data, frozen protocols, and verifier-backed certificates. Proposed terminology and architecture remain research proposals unless independently validated.

## References

1. S. Boyd and L. Vandenberghe, *Convex Optimization*. Cambridge University Press, 2004. https://web.stanford.edu/~boyd/cvxbook/
2. M. Zinkevich, “Online Convex Programming and Generalized Infinitesimal Gradient Ascent,” *ICML*, 2003. https://www.cs.cmu.edu/~maz/publications/ICML03.pdf
3. D. Golovin and A. Krause, “Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization,” *JAIR* 42 (2011), 427–486. https://arxiv.org/abs/1003.3967
4. Z. Goertzel, J. Jakubův, and J. Urban, “ENIGMAWatch: ProofWatch Meets ENIGMA,” 2019. https://arxiv.org/abs/1905.09565
5. S. Huang, P. Song, R. J. George, and A. Anandkumar, “LeanProgress: Guiding Search for Neural Theorem Proving via Proof Progress Prediction,” 2025. https://arxiv.org/abs/2502.17925
6. N. D. Megill and D. A. Wheeler, *Metamath: A Computer Language for Mathematical Proofs*. https://us.metamath.org/downloads/metamath.pdf
