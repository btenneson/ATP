# Settlement Compass Experiment 003 — Nested Training Shells and Diminishing Returns

**Date:** August 13, 2026 (PDT)  
**Research owner:** Brian Tenneson

## Question

Does the settlement-compass strategy exhibit diminishing returns as the number of retained proof DAGs used for training increases?

The experiment used cumulative shells

\[
S_{10}\subset S_{20}\subset S_{40}\subset S_{80},
\]

so no previously learned DAG was discarded when the training set doubled. All four models were tested on the same frozen set of 20 held-out theorem proof-DAG targets. This is a retrospective proof-navigation diagnostic, **not** an end-to-end ATP proof race.

## Results

| Training DAGs | Mean AUC | Mean Spearman distance | Mean distance MAE | Median rank: first DAG node | Median rank: direct parent | Precision@10 | Compass beats random on direct parent |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.78950 | 0.29007 | 3.18750 | 1.5 | 311.5 | 0.460 | 9/20 |
| 20 | 0.81637 | 0.32816 | 2.54741 | 2.5 | 283.0 | 0.390 | 11/20 |
| 40 | 0.82212 | 0.35064 | 2.46435 | 9.0 | 226.5 | 0.370 | 11/20 |
| 80 | 0.83697 | 0.42130 | 2.47883 | 1.0 | 129.0 | 0.505 | 15/20 |

For the direct-parent rank, lower is better. For AUC, Spearman correlation, and Precision@10, higher is better. For MAE, lower is better.

## Marginal gains by shell

For AUC, the raw gains are

\[
\Delta_{10\to20}=+0.02687,
\]
\[
\Delta_{20\to40}=+0.00574,
\]
\[
\Delta_{40\to80}=+0.01485.
\]

Per additional training DAG, these are approximately

\[
0.002687,
\quad 0.000287,
\quad 0.000371.
\]

Thus AUC shows a large initial return from 10 to 20 DAGs, a strong drop in marginal return from 20 to 40, and then a modest rebound from 40 to 80. The sequence is **not strictly diminishing**.

For mean distance correlation, the gains are

\[
+0.03809,
\quad +0.02248,
\quad +0.07066.
\]

Again, this is not a strictly diminishing sequence; the 80-DAG shell produced the largest raw improvement.

For mean distance error, training from 10 to 20 improved MAE by about 0.6401, 20 to 40 improved it by only about 0.0831, and 40 to 80 slightly worsened it by about 0.0145. This metric is the clearest sign of early saturation.

For the median rank of the first direct proof parent, the sequence improved monotonically:

\[
311.5\to283.0\to226.5\to129.0.
\]

The improvement per newly added DAG is approximately 2.85, 2.83, and 2.44 rank positions respectively. On this particular metric there is evidence consistent with diminishing marginal return, although the total improvement remains substantial through 80 DAGs.

## Interpretation

The data do **not** support a single simple statement that “accuracy has already entered a smooth diminishing-returns regime.” Some measures show early saturation, while others improve strongly again at 80 DAGs. The strongest conclusion is that more training DAGs continue to add useful geometric information, but different aspects of the compass learn at different rates.

The 80-DAG compass is the strongest overall shell in this experiment: it has the highest AUC, highest distance correlation, best direct-parent median rank, highest Precision@10, and beats random on direct-parent ranking in 15 of 20 targets. Its one small regression is mean distance MAE relative to the 40-DAG shell.

A larger shell sequence, for example 160 and 320 DAGs on a larger fixed held-out set, is needed before fitting a reliable asymptotic learning curve such as

\[
A(n)=A_\infty-cn^{-\alpha}
\]

or

\[
A(n)=A_\infty-ce^{-kn}.
\]

With only four shell sizes and 20 held-out targets, estimating a ceiling \(A_\infty\) would be premature.

## Scientific limitation

These scores measure ranking and distance-to-proof geometry on known proof DAGs. They do not equal the fraction of conjectures an ATP would prove end-to-end. A subsequent proof race must hold generated candidates, verifier, hardware, random seed, and resource budget fixed while changing only compass ordering.

## AI Integrity Statement

OpenAI's ChatGPT was used as a research and implementation assistant to formalize the experiment, generate code and workflow documentation, inspect machine-produced results, perform arithmetic comparisons, and draft this report. Brian Tenneson directed the research questions, experimental constraints, and interpretation goals. Numerical results reported here come from the repository's reproducible GitHub Actions experiment and are not presented as independently replicated external findings.

## References

1. Metamath Proof Explorer, `set.mm`, Metamath project: https://us.metamath.org/mpeuni/mmset.html
2. G. H. Hardy, J. E. Littlewood, and G. Pólya, *Inequalities*, Cambridge University Press. (General background on monotonicity and quantitative comparison.)
3. T. Hastie, R. Tibshirani, and J. Friedman, *The Elements of Statistical Learning*, 2nd ed., Springer, 2009. (Learning curves, generalization, and model assessment.)
4. K. P. Murphy, *Probabilistic Machine Learning: An Introduction*, MIT Press, 2022. (Statistical learning and held-out evaluation.)
5. Metamath project source repository: https://github.com/metamath/set.mm
