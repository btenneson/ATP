# prcom quicksand-revision experiment (Predator 8.039)

## Status

Preregistered experiment design. Creating or editing this document is not a scored run.

## Question

Can a verifier-gated controller reduce waste from long nonsettling search basins by combining the existing structural settlement heuristic `H_hat` with a certificate-complexity signal and applying a bounded group-inverse revision before blacklisting the basin?

The motivating failure mode is a run that consumes approximately 30,000 expansions without a verifier-accepted settlement while `H_hat` remains near the same apparently favorable value.

## Important distinction about certificate length

The raw compressed length `l(q)` of a forward partial certificate is naturally nondecreasing as proof labels are appended. Therefore this experiment does **not** treat raw `l(q)` as a quantity that should monotonically decrease.

The secondary coordinate is

```text
z_l(q) = log((l(q) + 1) / (depth(q) + 1))
```

where `l(q)` is measured by the frozen lossless `FirstOccurrenceGammaV1` codec already used in Predator 8.033. `z_l` is a compressed-bit-density diagnostic. It can rise or fall even when raw `l(q)` rises. It is not claimed to equal remaining certificate complexity.

## Treatment controller

Predator 8.039 starts from the 8.019 selective-sink architecture and keeps:

- the same frozen theorem/verifier boundary;
- the same recovered 8.002 learned legal-move ranker;
- the same full-open-goal exactification graph;
- per-basin accounting;
- bounded diagnostic exactification;
- candidate verification before settlement;
- persistent basin suppression after bailout.

It adds a joint stagnation condition. For a basin, ordinary optimization continues while either:

1. `H_hat` improves by the declared epsilon; or
2. `z_l` improves by the declared epsilon.

If neither improves for the basin patience tranche, the controller enters a bounded revision phase.

## Group-inverse revision

The certificate-complexity **pressure**, not the certificate itself, is group-valued.

Normal search uses a positive coefficient `beta_l` on local change in `z_l`. The coefficient lives in the additive group `(R,+)`. Revision applies

```text
beta_l -> -beta_l
```

for a bounded window, so the search temporarily prefers the opposite local compression behavior.

At the same time the creativity control uses the logit-addition group already used by the inverse-revision line, with

```text
c -> 1 - c.
```

If either `H_hat` or `z_l` improves in the triggering basin during revision, ordinary controls are restored. If the revision window expires without benefit, the basin prefix is blacklisted and search moves elsewhere.

## Operational quicksand definition

For this experiment, a **joint-stall basin** is a first-proof-choice-prefix basin that consumes its patience tranche without either `H_hat` improvement or `z_l` improvement.

This is an operational search diagnosis only. It is not a claim that the basin contains no proof.

The treatment is designed so that one unchanged first-prefix basin cannot consume the entire 30,000-expansion budget without one of the following happening:

- measured `H_hat` or `z_l` benefit;
- bounded inverse revision;
- bailout and subtree suppression.

It does **not** guarantee that the overall theorem will settle before 30,000 expansions.

## A/B comparison

Baseline: Predator 8.019 selective sink.

Treatment: Predator 8.039 joint H/compression quicksand revision.

Use the same:

- `set.mm` commit/hash;
- frozen model/hash;
- theorem target `prcom`;
- random seed;
- total expansion budget;
- brute reserve;
- depth/open-goal limits;
- exactification caps;
- hardware class;
- independent external certificate verifier.

Initial pilot seed: `2301`.

Initial total budget: `30000` expansions.

## Primary endpoint

First verifier-accepted settlement resource

```text
tau_0 = expansions to first accepted certificate.
```

A run without an accepted certificate remains `UNKNOWN`/no settlement within budget. Neither a small `H_hat` nor a favorable `z_l` counts as settlement.

## Secondary diagnostics

Record:

- final certified status;
- best observed `H_hat`;
- raw partial compressed bits `l(q)` in progress telemetry;
- `z_l(q)`;
- number of inverse revisions;
- number of basin bailouts;
- blocked basin count;
- exactification lower-bound events;
- false-zero events;
- wall time;
- emitted certificate and independent verifier result.

## Interpretation

The strongest positive result is treatment settlement with fewer expansions than baseline under the frozen comparison.

If neither arm settles, a reduction in maximum unchanged-basin dwell or successful revision/bailout is evidence about search control only, not theorem-solving success.

If treatment settles but baseline does not, replicate across additional frozen seeds before making a broad performance claim.

## Guards

- No target proof is installed as a rule or replay path.
- The verifier remains authoritative.
- `H_hat` and `z_l` are non-authoritative search measurements.
- The codec is frozen for the comparison.
- Budget exhaustion is not a proof of non-theoremhood.
