# Experiment 004: Clean Settlement-Compass Shells with MAX Training Case

**Date:** August 13, 2026 (PDT)  
**Research direction:** Optimized tunneling / settlement-compass learning curves for automated theorem proving

## Purpose

This experiment restarts the shell study under a frozen protocol so that the principal manipulated variable is the amount of true proof-DAG training data. It is designed to measure whether the settlement compass improves with more verified proof DAGs, whether the gains show diminishing returns, and what happens in an intentionally oversized training condition where every eligible true DAG is used.

The experiment is retrospective proof-DAG navigation research. It is not, by itself, an end-to-end ATP proof race.

## Primary question

Holding the test set, candidate pools, negative examples, representation, model class, hyperparameters, proof corpus, and evaluation procedure fixed, how does compass quality change as the number of verified true training DAGs grows?

## Frozen source corpus

Use one frozen `set.mm` snapshot for every shell and every replicate.

The currently established snapshot hash from the prior shell workflow is:

`sha256 = 7b70cd8cca88aeb72a8dd97029d0b506015fb0325afec581cdc9add8ca0c8547`

The experiment must abort if the fetched corpus does not match this hash.

## Train/test separation

1. Construct the eligible theorem universe from the same frozen `set.mm` snapshot.
2. Select one sealed test set of 20 theorem targets before any training shell is formed.
3. The 20 test targets remain identical for every shell, every replicate, and the MAX condition.
4. No test theorem may be a training root.
5. No training root may have a sealed test theorem in its transitive proof-DAG dependency closure.
6. Test-derived performance information must not be used to alter shell composition, feature settings, hyperparameters, seeds, or stopping rules after the experiment begins.

## Clean shell design

Create one fixed random ordering of all eligible training roots after the sealed test set has been removed. Define nested positive-DAG shells from that ordering:

- `S10`: first 10 eligible roots
- `S20`: first 20 eligible roots
- `S40`: first 40 eligible roots
- `S80`: first 80 eligible roots
- `S160`: first 160 eligible roots, if at least 160 are available
- `MAX`: every eligible training root in the frozen universe

Thus:

`S10 ⊂ S20 ⊂ S40 ⊂ S80 ⊂ S160 ⊆ MAX`

If fewer than 160 eligible roots exist, omit `S160`; never replace it with a hand-picked size.

### Why MAX exists

`MAX` is the deliberately oversized or "stupid case." Its purpose is to answer a different but important question: when verified true proof DAGs are abundant, does the compass continue improving, saturate, become computationally inefficient, or even degrade because the representation/model cannot exploit the extra information cleanly?

`MAX` is not an arbitrary large number. It means **all eligible true training DAGs remaining after the sealed test set is removed**.

## Removal of the Experiment 003 confounds

Experiment 003 changed negative samples and parts of the test distractor population as shell size changed. Experiment 004 must not do that.

Before fitting any model:

1. Generate and save one frozen negative-example set for every eligible training root.
2. Generate and save one frozen candidate/distractor set for every sealed test theorem.
3. These sets must be independent of shell size.
4. A root appearing in a smaller shell must carry exactly the same positive and negative examples when it appears in every larger shell.
5. Every shell must rank exactly the same candidate set for each test theorem.

The only intended shell-dependent change is that additional verified positive proof DAGs are admitted into training.

## Independent training from scratch

Each shell is trained from scratch. Do not warm-start `S20` from `S10`, `S40` from `S20`, etc.

This avoids a training-history confound. Continual learning may be studied later as a separate experiment.

## Replicates

Run multiple model replicates per shell using a predeclared seed list. The default target is 10 independent model replicates per shell if computationally practical.

All non-model randomness remains frozen across replicates. Replicate seeds may affect only model initialization or another explicitly declared stochastic learner component.

If the current logistic-regression/ridge implementation is effectively deterministic under the frozen training matrix, report that fact rather than pretending the replicates are independent. In that case, use repeated **data-universe draws** only in a later second-stage experiment, not in this first clean shell run.

## Representation and models

For the first clean replication, retain the current settlement-compass representation and model family unless an implementation defect forces a documented correction:

- pair text: `ROOT <root statement> CAND <candidate statement>`
- TF-IDF unigrams and bigrams
- `lowercase=False`
- `min_df=2`
- `max_features=30000`
- `sublinear_tf=True`
- logistic regression for proof-DAG membership / usefulness classification
- ridge regression for graph-distance prediction
- same classifier/regressor hyperparameters across every shell

No shell-specific feature engineering is allowed.

## Important feature-space rule

To make shell size the cleanest possible causal variable, fit the vectorizer vocabulary **once from the complete training universe available to MAX**, without using test labels, and freeze that vocabulary for all shells.

This prevents the set of representable features from changing merely because `min_df=2` is crossed at a larger shell. The model coefficients may change with training size; the coordinate system itself should not.

A secondary analysis may later repeat the experiment with shell-local vocabularies to measure the practical effect of feature acquisition, but that must be labeled as a different experiment.

## Evaluation metrics

For each shell and each sealed test theorem record at minimum:

- ROC AUC for proof-DAG membership ranking
- Spearman correlation between predicted and true graph distance
- mean absolute error of graph-distance prediction
- rank of the first proof-DAG node
- rank of the first direct proof parent
- precision at 10
- compass-vs-random direct-parent comparison
- candidate count
- training-example count
- wall-clock training time
- wall-clock evaluation time
- peak memory if available

For optimized tunneling analysis, additionally record whenever the implementation supports it:

- number of tunnel restarts
- expansions to first useful DAG node
- expansions to first direct parent
- compass confidence / score margin at each successful tunnel decision
- rank of the ultimately successful direction at the time it was chosen

## Primary learning-curve statistics

For a metric `A(n)` where higher is better, report both raw gains and gain per added DAG:

`Δ10→20 = A(20) - A(10)`

`Δ20→40 = A(40) - A(20)`

`Δ40→80 = A(80) - A(40)`

`Δ80→160 = A(160) - A(80)` when `S160` exists.

Per-added-DAG marginal gains:

`M10→20 = [A(20)-A(10)] / 10`

`M20→40 = [A(40)-A(20)] / 20`

`M40→80 = [A(80)-A(40)] / 40`

`M80→160 = [A(160)-A(80)] / 80`

For the MAX step, report:

`MMAX = [A(MAX)-A(n_last)] / [N_MAX-n_last]`

where `n_last` is the largest ordinary shell available.

A consistent decline in these marginal values supports diminishing returns. A rebound is not to be hidden; it must be investigated.

## Curve fits

Fit at least these models to the ordinary shell points, not automatically to MAX:

1. Power-law saturation: `A(n) = A_inf - c n^{-alpha}`
2. Exponential saturation: `A(n) = A_inf - c exp(-n/tau)`
3. Linear trend in `log2(n)` as a non-saturating comparison

Report parameter estimates, residual error, and warnings about extrapolation.

Treat MAX primarily as an out-of-sample stress point against the curve fitted to ordinary shells. This makes MAX scientifically useful: it tests whether the apparent asymptote survives a huge increase in training data.

## Predeclared interpretations of MAX

The MAX outcome will be classified without changing the protocol:

- **Continued improvement:** MAX materially exceeds the largest ordinary shell.
- **Saturation:** MAX changes performance negligibly while computational cost rises.
- **Degradation:** MAX performs worse on held-out targets despite more true DAG data.
- **Representation ceiling:** ranking metrics flatten while training data continue to grow, suggesting the current feature/model family rather than data scarcity is limiting.
- **Computational ceiling:** predictive quality may improve but training or inference cost becomes impractical.

No one of these outcomes is to be treated as a failure of the experiment.

## Recovery and hiccup protection

The experiment must be restartable without silently changing the data split or random draws.

Before training begins, write a manifest containing:

- frozen `set.mm` SHA-256
- exact test-20 labels
- exact ordered eligible training-root list
- exact shell membership for every shell
- exact MAX size
- all frozen negative-sample sets or deterministic seeds sufficient to reproduce them exactly
- all frozen test candidate/distractor sets or deterministic seeds sufficient to reproduce them exactly
- vectorizer vocabulary hash
- all model hyperparameters
- all random seeds
- source-code commit SHA

Write results incrementally after each completed shell (and, if replicated, after each shell/replicate pair). Use atomic write/rename semantics where practical.

A rerun from the same manifest must reproduce the same data, candidates, and shell assignments exactly.

If a run stops midway, resume from the first incomplete shell/replicate rather than regenerating the experiment.

## Required output files

Recommended paths:

- `optimizations/settlement_compass/results/experiment_004_manifest.json`
- `optimizations/settlement_compass/results/experiment_004_shell_results.json`
- `optimizations/settlement_compass/results/experiment_004_rows.csv`
- `optimizations/settlement_compass/results/experiment_004_curve_fit.json`
- `optimizations/settlement_compass/docs/EXPERIMENT_004_RESULTS.md`

The manifest should be committed before or at the start of the first training run. Results should be committed after each recoverable stage when the workflow permits.

## Decision rule

The experiment is considered clean enough to interpret only if:

1. the sealed test set is unchanged across shells;
2. candidate sets are unchanged across shells;
3. negative examples for previously admitted roots are unchanged across shells;
4. representation coordinates are unchanged across shells;
5. hyperparameters and scoring rules are unchanged across shells;
6. every shell trains from scratch;
7. the only intentional shell variable is the number of admitted true proof DAGs.

If any condition fails, the run must be labeled exploratory rather than used as the principal diminishing-returns result.

## Relationship to Experiment 003

Experiment 003 provided evidence that more solved proof DAGs generally improve compass navigation, but its shell-dependent negative resampling and changing distractor pool prevented a strict one-variable interpretation. Experiment 004 is the corrected, restarted experiment intended to make the prediction curve as clean as practical.

## AI Integrity Statement

This protocol was designed with substantial assistance from OpenAI's ChatGPT in consultation with Brian Tenneson. The purpose of the redesign is to reduce confounding variables, preserve exact reproducibility, and predeclare the interpretation of the oversized MAX condition before seeing the new results. Empirical claims must come from the recorded computation; this document itself is not empirical evidence.