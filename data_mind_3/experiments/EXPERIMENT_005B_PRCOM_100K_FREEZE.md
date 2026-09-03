# DATA MIND 3.1 Experiment 005B PRCOM — 100K Expansion Budget Test

Date: 2026-09-03

Purpose: test whether the 20,000-expansion cap in Experiment 005 was the immediate limiting factor.

This is a strict budget-extension replication from the pre-Experiment-005 DATA MIND 3.1 snapshot. No controller, objective, search-ranking, verifier, target, source corpus, initial creativity vector, frontier limit, time limit, or warm-start experience is changed.

## Frozen target and source

Target: `prcom`

Statement: `|- { A , B } = { B , A }`

set.mm commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`

set.mm SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`

## Experimental change

Experiment 005: `max_expansions = 20,000`

Experiment 005B: `max_expansions = 100,000`

This is the only intended scientific parameter change.

## Held constant

- candidate_cap = 64
- max_depth = 24
- max_open_goals = 24
- max_frontier = 200,000
- timeout_s = 1,800
- control_interval = 16
- initial creativity vector = all eleven coordinates 0.5
- experience_in = NONE
- independent Metamath verifier unchanged

## Interpretation rule

If PRCOM is verifier-proved between expansions 20,001 and 100,000, then the 20,000-expansion cap was an immediate blocker for this exact DATA MIND 3.1 controller.

If the run stops for another reason before 100,000 expansions (for example frontier or timeout), that identifies a different active constraint.

If the run reaches 100,000 expansions without a verified proof, then 20,000 was not merely too small in the sense of a proof lying close beyond the previous cap; the search/control objective remains the stronger diagnosis. A failure at 100,000 does not prove that no larger budget could ever work.
