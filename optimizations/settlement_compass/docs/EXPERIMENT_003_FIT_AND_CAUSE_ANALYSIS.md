# Experiment 003: Learning-Curve Fit and Cause Analysis

**Date:** August 13, 2026 (PDT)  
**Research direction:** Settlement-compass optimization for automated theorem proving

## Question

For nested training shells of 10, 20, 40, and 80 verified pre-Infinity proof DAGs, does compass quality show diminishing returns, and why was the improvement from 40 to 80 larger than the improvement from 20 to 40 on some metrics?

## Observed aggregate data

On the same 20 held-out theorem targets, Experiment 003 reported:

| training DAGs `a` | mean AUC | mean Spearman distance correlation | mean distance MAE | median rank of first direct proof parent |
|---:|---:|---:|---:|---:|
| 10 | 0.78950 | 0.29007 | 3.18750 | 311.5 |
| 20 | 0.81637 | 0.32816 | 2.54741 | 283.0 |
| 40 | 0.82212 | 0.35064 | 2.46435 | 226.5 |
| 80 | 0.83697 | 0.42130 | 2.47883 | 129.0 |

The AUC increments were approximately +0.02687, +0.00574, and +0.01485 across the three doublings. Thus the observed curve is not monotonically diminishing in marginal gain.

## Tentative fits

Because there are only four shell points, every asymptotic fit is provisional. Three simple models were compared for AUC: a power-law saturation model, an exponential saturation model, and a linear model in log2(a).

The best least-squares fit among these three on the four AUC points was the power-law saturation form

`A(a) = A_inf - c a^{-alpha}`

with fitted values approximately

`A_inf = 0.84685`, `c = 0.31557`, `alpha = 0.74628`.

This gives fitted AUC values 0.79025, 0.81311, 0.82674, and 0.83486 at a = 10, 20, 40, and 80. The residual sum of squares is approximately 3.70e-5. The exponential-saturation fit had a larger residual sum of squares, approximately 7.02e-5, and the log-linear fit had approximately 8.18e-5.

This power-law fit suggests a possible ceiling near 0.85 **for the present representation and scoring rule**, but four points are far too few to regard that ceiling as established. In particular, the direct-parent rank continued to improve strongly at a = 80, so the system is not clearly at an operational search ceiling.

For Spearman distance correlation, an exponential saturation model fit the four points better than the tested power-law or log-linear alternatives, but the inferred asymptote was about 0.625 and is highly uncertain. For direct-parent rank, an exponential fit reproduces the four points extremely closely but implies a physically implausible negative asymptote if extrapolated indefinitely. That is evidence that the observed range is still pre-asymptotic for this metric; it should not be extrapolated as a literal limiting law.

## Why can 40 -> 80 improve more than 20 -> 40?

There are at least three mathematical/implementation reasons.

### 1. Feature-threshold effects

The compass uses TF-IDF unigrams and bigrams with `min_df=2`. A feature is absent until it occurs in at least two training examples. As more proof DAGs are added, structurally useful tokens and token pairs can suddenly cross this threshold. Therefore the learned feature space does not grow smoothly with `a`: some directions become representable only after enough DAGs have accumulated. A jump from 40 to 80 can therefore unlock useful proof-language features that were effectively invisible at 20 or 40.

### 2. Coverage of heterogeneous proof regions

The additional training DAGs are randomly drawn from a broad pre-Infinity region of `set.mm`. Twenty extra DAGs may add mostly redundant geometry, while the next forty may happen to cover proof patterns closer to several of the 20 test targets. With only 20 test theorems, this sampling effect can be substantial. The row-level results show that the 80-DAG shell produces very large direct-parent improvements on several individual targets even though not every target improves.

### 3. A confound in Experiment 003 that should be corrected

The shell code changes more than just the number of positive DAGs. For training, negative examples are resampled with a shell-dependent random seed (`SEED_MODEL + shell_n`). Thus the original 10 or 20 roots do not retain exactly the same negative training examples in every larger shell. Also, the test distractor pool excludes the current training roots, so the candidate set changes slightly as the shell grows.

Therefore Experiment 003 is a valid nested-positive-DAG experiment, but it is **not a perfectly controlled one-variable experiment** in which the only change is the addition of new positive proof DAGs. Part of the non-smooth 20 -> 40 -> 80 behavior may come from the changed negative samples and changed distractor pool.

This is the most important procedural explanation found in the audit.

## Corrected experiment recommended

Run Experiment 003B with the same 10/20/40/80 positive shells and the same 20 test targets, but freeze:

1. one negative-sample set for every possible training root before any shell is fit;
2. one test distractor set for every test theorem, independent of shell size;
3. one vectorization/scoring specification;
4. all model hyperparameters and seeds.

Then the only changing variable is the inclusion of additional solved proof DAGs. The resulting shell curve can legitimately be interpreted as the marginal value of training DAG count.

The most important quantities for diminishing returns should be reported both as raw increments and increments per added DAG:

`M_{10->20} = [A(20)-A(10)]/10`,

`M_{20->40} = [A(40)-A(20)]/20`,

`M_{40->80} = [A(80)-A(40)]/40`.

A consistent decrease in these marginal values across several independent test draws would support a genuine diminishing-returns law.

## Interpretation

The present evidence supports two statements simultaneously:

1. more solved proof DAGs improve the current compass on most broad navigation metrics;
2. the four observed shell points do not yet establish a smooth diminishing-returns law.

The tentative AUC power-law fit is compatible with saturation near 0.85, but the direct-parent ranking data indicate that useful search guidance may still be improving rapidly. The non-monotone marginal AUC increments are plausibly explained by thresholded feature acquisition, random coverage of proof regions, and a real experimental confound from shell-specific negative sampling.

## References

1. N. Metropolis and S. Ulam, "The Monte Carlo Method," *Journal of the American Statistical Association* 44 (1949), 335-341.
2. C. M. Bishop, *Pattern Recognition and Machine Learning*, Springer, 2006.
3. T. Hastie, R. Tibshirani, and J. Friedman, *The Elements of Statistical Learning*, 2nd ed., Springer, 2009.
4. F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," *Journal of Machine Learning Research* 12 (2011), 2825-2830.
5. N. Megill and D. A. Wheeler, *Metamath: A Computer Language for Mathematical Proofs*, 2019; Metamath Proof Explorer and `set.mm` project.

## AI Integrity Statement

This analysis was prepared with substantial assistance from OpenAI's ChatGPT. The AI inspected the recorded experiment outputs and implementation, performed the numerical curve fits, identified experimental confounds, and drafted this document. Numerical claims should be reproducible from the committed Experiment 003 results. No AI output is treated as a proof certificate or as independent empirical evidence beyond the recorded computation.