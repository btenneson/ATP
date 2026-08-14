# Settlement Compass Experiment 001: First Distance-Learning Diagnostic

**Date:** 13 August 2026  
**Research direction:** Brian Tenneson

## Purpose

The settlement-compass hypothesis proposes that retained proof DAGs may contain transferable geometry. On a solved DAG, exact graph distance to the certified terminal theorem can be computed. A model trained on several solved DAGs can then be asked whether features visible in a new theorem neighborhood predict (i) whether a candidate landmark belongs to the held-out proof DAG and (ii) how far that landmark lies from the held-out settlement vertex.

This first experiment is deliberately a **navigation diagnostic, not an ATP proof race**. The held-out proof DAGs are used after selection as ground truth for scoring. They are not treated as newly discovered proofs. The test therefore asks whether the proposed compass contains measurable navigational signal before the more difficult step of integrating it into an inference-generating prover.

## Frozen training data

Ten proof-dependency DAGs from the pre-Infinity portion of Metamath `set.mm` were used as training data:

`pwidg, axreplem, f1ores, fiinf2g, eqop, frpomin, rabab, rabun2, eusn, elun2`.

Across the ten DAGs, 6,793 theorem-node examples were available for distance regression. A matched set of off-DAG theorem nodes was sampled for proof-DAG relevance classification, giving 13,586 binary training examples.

For each training DAG, the root theorem has exact distance 0. Distances for dependency theorem nodes were computed by backward breadth-first traversal of the retained dependency graph.

## Held-out test

The diagnostic used the 49 theorem targets in Benchmark 001. For each held-out theorem, the known dependency DAG was reconstructed strictly for evaluation. Its theorem nodes were mixed with at least 100 and generally five times as many randomly selected pre-Infinity distractor theorem nodes.

The model received the root formula and a candidate formula. A TF-IDF representation of Metamath tokens and token bigrams was used. Logistic regression estimated whether the candidate belonged to the held-out proof DAG. Ridge regression estimated distance to settlement for nodes known to lie in the proof DAG. These are intentionally simple models: the purpose is to test for signal, not to maximize machine-learning performance.

The compass score combined high estimated proof-DAG relevance with low estimated remaining distance. The control used the identical candidate pool but random ordering. Seeds and target labels are frozen in the source code.

## Results

Across 49 held-out theorem targets:

- Mean proof-DAG relevance AUC: **0.7880**.
- Median proof-DAG relevance AUC: **0.7853**.
- Mean Spearman correlation between predicted and exact within-DAG distance: **0.2742**.
- Median Spearman correlation: **0.2581**.
- Mean absolute distance error: **3.394 graph steps**.
- Median rank of the first genuine proof-DAG node under compass ordering: **1**.
- Median rank of the first genuine proof-DAG node under random ordering: **4**.
- Mean precision among the compass's top 10 candidates: **0.5429**.

The result is more mixed at the hardest local question: identifying a theorem node at exact distance 1 from the target. The median compass rank of the first direct parent was **483**, compared with **429** for the randomized control. On the 49 targets, the compass beat random on this measure 23 times and lost 26 times.

## Interpretation

The first diagnostic therefore supports a **limited but nontrivial claim**: ten solved proof DAGs contain transferable information sufficient for a simple model to distinguish held-out proof-relevant landmarks from unrelated distractors substantially better than chance. The model also recovers a weak positive signal about remaining graph distance.

The stronger claim that the current compass knows the *best immediate tunnel* is **not supported by this run**. Direct-parent ranking was no better than random overall. This distinction is important. The experiment has found evidence for a broad attraction field toward relevant proof territory, but it has not yet demonstrated a reliable local gradient all the way to the settlement vertex.

That negative component is useful. It suggests that formula text alone is insufficient for the final-step compass. The next model should add structural features that the theory already predicts may matter: current frontier state, inference-edge type, shared-bank landmarks, agent identity, cross-agent transfer, local proof-DAG topology, and calibrated uncertainty. Retaining complete search DAGs, including failed branches, becomes especially important because successful proof dependency DAGs alone contain too few genuine alternative tunnels.

## Why this is not yet the requested ATP race

A proof-dependency DAG is a post hoc record of the dependencies appearing in a completed proof. An ATP search DAG is richer: it contains candidates that were tried and failed, candidates never used in the final certificate, frontier states, inference costs, and branch competition. A fair race between “compass enabled” and “compass disabled” requires those search alternatives to exist before the answer is known.

Consequently, these results must not be reported as an improvement in theorem-proving success rate or proof-search cost. They justify proceeding to the next stage: instrument an actual verifier-backed search so that both arms see exactly the same candidate generation and differ only in the compass ordering policy.

## Next controlled experiment

The next implementation step is to run matched searches with:

1. identical target, axioms, inference generator, verifier, resource budget, random seed, and retained candidate set;
2. baseline arm: ordinary/FIFO or frozen existing priority rule;
3. compass arm: the same search with only candidate priority changed by the learned settlement potential;
4. complete retention of generated search DAGs and unsuccessful branches;
5. scoring by verified expansions-to-settlement, wall time, memory, and certificate length;
6. no credit for independence from search failure alone.

The four actual terminal classes remain mutually exclusive: proof (`P`), refutation (`R`), independence (`I`), or contradiction/inconsistent-base detection (`C`). Fractional compass scores are navigation estimates only; they are never partial certificates.

## AI Integrity Statement

Brian Tenneson set the research direction and requested the settlement-compass experiment. OpenAI ChatGPT was used as an AI research and implementation consultant to formalize the diagnostic, write and execute the reproducible Python analysis, interpret the resulting measurements, and prepare this documentation. The numerical results in this document are outputs of the stated reproducible computation, not estimates supplied from language-model memory. No theorem, proof, independence claim, or experimental superiority is accepted solely because it was proposed by an AI system. Formal mathematical settlement requires a verifier-accepted certificate, and empirical claims require preserved code, frozen data, and reproducible outputs.

## References

1. N. D. Megill and D. A. Wheeler, *Metamath: A Computer Language for Mathematical Proofs*. https://us.metamath.org/downloads/metamath.pdf
2. Z. Goertzel, J. Jakubův, and J. Urban, “ENIGMAWatch: ProofWatch Meets ENIGMA,” 2019. https://arxiv.org/abs/1905.09565
3. S. Huang, P. Song, R. J. George, and A. Anandkumar, “LeanProgress: Guiding Search for Neural Theorem Proving via Proof Progress Prediction,” 2025. https://arxiv.org/abs/2502.17925
4. C. Kaliszyk, J. Urban, H. Michalewski, and M. Olšák, “Reinforcement Learning of Theorem Proving,” *NeurIPS*, 2018. https://arxiv.org/abs/1805.07563
5. J. Urban and J. Jakubův, related ENIGMA literature on learning from proof-search traces; overview entry point: https://arxiv.org/abs/2403.04017