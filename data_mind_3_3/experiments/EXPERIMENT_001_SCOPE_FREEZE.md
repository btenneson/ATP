# DATA MIND 3.3 Experiment 001 — Scope Freeze Addendum

**Status:** FROZEN BEFORE SCIENTIFIC LAUNCH  
**Applies to:** `DATA MIND 3.3 Experiment 001 — Logical Dreamer Frozen-20 Mechanism`

## Learner scope

The permanent Frozen-20 training/holdout split, target set, split seed and hashes are preserved exactly. However, this first DATA MIND 3.3 mechanism experiment does **not** load the older `setmm_count_priors_v1` trained learner artifact into the proof-search lane.

The frozen training split is used here to preserve holdout integrity and target identity. Settlement search uses the proof-safe legal-prefix Metamath search representation inherited by the 3.3 Dreamer bridge.

Therefore Experiment 001 must not be interpreted as a test of Dreamer combined with the previously trained count-prior learner. A later experiment may test that combination, but it must receive a new preregistration/experiment identifier.

## Formal self-awareness scope

The implemented Logical Dreamer maintains an operational self-model of its own oracle access, actual oracle calls, remaining call allowances, reported costs, proposal counts, promotions and externally recordable outcomes.

Experiment 001 does **not** use outcome history to learn or update a new Dreamer policy during the run. In particular, the experiment does not adapt oracle throttles, access bits, promotion limits or synthesis policy from previous target outcomes.

Accordingly, the self-awareness tested here is best described as **operational self-observation / reflective state representation under fixed policy**, not outcome-trained reflective policy learning.

This qualification is frozen before launch and will not be relaxed after results are visible.
