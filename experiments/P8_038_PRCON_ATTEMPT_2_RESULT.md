# Predator 8.038 — `prcon` Attempt 2 Result

## Primary corrected run

- Date: 2026-08-28
- GitHub Actions run: `33215923133`
- Source commit: `6b7106a87d90859f95dc43bf02f12c058344934d`
- Workflow: `Predator8 8.038 prcon revision corrected`
- Status: completed successfully as an execution protocol

This is the primary scientific run for Attempt 2 under Amendment A1 in `P8_038_PRCON_ATTEMPT_HISTORY.md`.

## Preflight

The preflight job passed all required gates before search began:

- dependency and ATP compilation passed;
- the independent Metamath verifier self-test passed;
- the Predator 8.001 self-test passed.

Therefore Attempt 2 reached the intended real-target search and is not classified as an infrastructure-invalid attempt.

## Phase 1 — ordinary search

All eight agents completed Phase 1 without an emitted verified certificate:

- `P1`, initial creativity `0.15`: bounded `UNKNOWN`;
- `P2`, initial creativity `0.25`: bounded `UNKNOWN`;
- `R1`, initial creativity `0.35`: bounded `UNKNOWN`;
- `R2`, initial creativity `0.45`: bounded `UNKNOWN`;
- `I1`, initial creativity `0.55`: bounded `UNKNOWN`;
- `I2`, initial creativity `0.65`: bounded `UNKNOWN`;
- `C1`, initial creativity `0.75`: bounded `UNKNOWN`;
- `C2`, initial creativity `0.85`: bounded `UNKNOWN`.

Under the preregistered prototype diagnostic this means `D=1 > tau=0.5` for every agent, so revision fired for every agent.

## Phase 2 — group-inverse revision

The scalar logit-group inverse `c^{-1}=1-c` produced the following revised coordinates:

- `P1`: `0.15 -> 0.85`;
- `P2`: `0.25 -> 0.75`;
- `R1`: `0.35 -> 0.65`;
- `R2`: `0.45 -> 0.55`;
- `I1`: `0.55 -> 0.45`;
- `I2`: `0.65 -> 0.35`;
- `C1`: `0.75 -> 0.25`;
- `C2`: `0.85 -> 0.15`.

All eight agents then completed Phase 2 with bounded `UNKNOWN`. No agent emitted a certificate that reached independent Metamath acceptance.

## Federation halt behavior

No `p8-038-SETTLED-*` artifact was published by the primary run. Therefore the condition

\[
\exists z\;V(z)=1 \Longrightarrow \mathrm{HALT\ ALL}
\]

was never satisfied, and no peer agent was halted by a verified settlement. This is the correct behavior for a run in which no verified settlement occurs.

## Scientific interpretation

Within the exact finite controls declared for Attempt 2, group-inverse revision did **not** rescue any of the eight tested `prcon` search configurations.

This result does not show that `prcon` is unprovable, does not show that inverse revision is useless in general, and does not invalidate the group-based revision mechanism. It shows only that, for these eight seeds, these initial creativity coordinates, the 12,000-expansion phase budgets, and the other fixed search controls, the inverse-revised second basin did not produce a verified certificate.

The scientifically relevant observation is therefore a bounded negative result for the proposed rescue mechanism on this particular real target and parameter set.

## Administrative duplicate excluded before outcome inspection

A later history-file commit (`e05273efb3716141c9630401f3ab9454ace853b4`) was made because the primary corrected workflow run had not yet appeared in the Actions listing at the moment it was checked. The primary run subsequently appeared and had already completed successfully. That history-file commit queued workflow run `33215974573` unnecessarily.

Run `33215974573` is designated **an administrative duplicate, not a planned replicate**, and is excluded from the primary Attempt 2 inference before its outcome is inspected. Its result, whatever it is, must not be pooled with or substituted for run `33215923133` without a separately documented replication decision.
