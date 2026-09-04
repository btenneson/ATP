# DATA MIND 3.2 Architecture Contract — Hyperfinite Epistemic Oracle Layer

Status: IMPLEMENTED AS A REVERSIBLE RESEARCH INTERFACE / NO SCIENTIFIC EXPERIMENT LAUNCHED

Base: DATA MIND 3.1 clean pre-Experiment-007 freeze `1f4f7c6134be0daeb9bd37904b8bb561960bf9c8`.

This layer is additive. It does not modify the DATA MIND 3.1 files, completed experiments, verifier semantics, BANK admission policy, Professor grading semantics, protected partner lanes, or Sentinel authority.

## 1. Mathematical specification

For a resource-indexed epistemic relation

`K_i^{<=r} phi`,

let an unlimited hypernatural `H` be used only in the mathematical nonstandard specification. If `phi_0, phi_1, ...` enumerates the relevant sentences, define the conceptual internal hyperfinite horizon

`F_H = {phi_n : n <= H}`.

The corresponding hyperfinite omniscience statement is

`Omn_i(H) := AND_{n<=H, T |- phi_n} K_i^{<=H} phi_n`.

Under truth-set semantics the hyperfinite conjunction is represented by the corresponding intersection of truth sets.

If `c_i(phi)` is the least resource cost of acquiring/certifying `phi`, define the conceptual hyperfinite epistemic closure cost

`O_i(H) := max_{n<=H, T |- phi_n} *c_i(phi_n)`.

When `O_i(H)/H` is limited, its standard part may be studied mathematically. There is no largest hypernatural, and this contract does not identify a hyperfinite conjunction with an ordinary external infinitary conjunction without an additional argument.

## 2. Executable honesty: finite proxy, not a fake hypernatural

A conventional computer cannot literally instantiate an unlimited hypernatural. DATA MIND 3.2 therefore implements only finite truncations `N` of the specification.

The executable objects are named `FiniteHorizonOracle` and `FiniteHorizonReport`. For finite `N`, the code may compute:

- settlement coverage over a frozen finite horizon;
- the finite analogue `O_i(N)` when every required item has an observed least cost;
- the normalized ratio `O_i(N)/N` when defined;
- whether the finite horizon is completely covered within budget `N`.

These are finite proxies. They must never be reported as an actual nonstandard standard-part/shadow calculation.

## 3. Oracle domain and answer type

The runtime oracle is a frozen map over a finite horizon. Each indexed target may have a gold settlement role in

`{P, R, I, C}`

or an undefined/withheld answer represented by no role (`U` conceptually).

The existing DATA MIND 3.1 `SettlementRole` type is reused rather than silently changing the 3.1 enum.

## 4. Three oracle-use modes

### Hidden ground truth — default

The oracle is invisible to the AMLD search society. It may be queried only by the evaluator after or outside search to score the reported settlement role. This is the default scientific mode.

### Professor role hint — counterfactual

The oracle may expose only the correct settlement role to the 3.2 awareness bridge. The bridge converts that role into an advisory awareness/routing cue for the Professor-facing member of the corresponding couple (`P1`, `R1`, `I1`, or `C1`). The protected partner lane remains unhinted.

This mode asks: how much performance is lost because the society must identify the correct settlement role for itself?

### Direct role hint — stronger counterfactual

The oracle may expose the correct role to both members of the matching couple. This deliberately removes more of the role-recognition problem and must be labeled as an oracle-assisted counterfactual, never ordinary DATA MIND performance.

## 5. Oracle knowledge does not become certified AMLD knowledge

An oracle answer is neither a theorem certificate nor a BANK deposit. Every oracle-derived cue is marked

- `asserted_truth = False`
- `certified = False`.

The oracle layer has no BANK-deposit method and no verifier-bypass method.

The permitted direction is

`oracle -> hidden evaluation OR awareness/routing cue -> P/R/I/C attempt -> verifier -> BANK`.

It is forbidden to implement

`oracle -> BANK`

or

`oracle -> verifier acceptance`.

## 6. Professor remains an awareness/advice mechanism

DATA MIND 3.2 does not redefine the Professor as omniscient. In Professor-hint mode, the oracle supplies an experimental role cue to the 3.2 bridge; the cue changes what becomes salient to one Professor-facing agent. It does not modify `ProfessorGrade`, does not assert a mathematical proposition, and does not force an action.

Thus the conceptual division remains:

- Oracle: idealized gold information for measurement/counterfactuals.
- Professor: attention/advice.
- P/R/I/C agents: settlement attempts.
- Verifier: certification authority.
- BANK: shared verified knowledge.
- FUTUREBANK: speculative possibilities only.

## 7. Protected independent lane

In `PROFESSOR_ROLE_HINT` mode, `P2/R2/I2/C2` remain protected from the oracle signal, matching the anti-herding principle of 3.1. Only the explicit stronger `DIRECT_ROLE_HINT` counterfactual may address both members of a couple.

## 8. Scientific use

No experiment number is assigned by this wiring commit. A later preregistered experiment should compare at least:

1. hidden-ground-truth AMLD;
2. Professor-role-hint AMLD;
3. optionally direct-role-hint AMLD.

The same frozen cases, seeds, budgets, verifier, and stopping rules should be used across arms. Primary outputs should include verifier-certified settlement, settlement-role confusion matrices, false-positive rates, resource cost, and oracle-gap quantities.

A useful finite diagnostic is

`Delta_N = O_normal(N) - O_role_hint(N)`

when both costs are defined. Its interpretation is the finite observed cost attributable to role identification under the frozen benchmark, not a proof of a nonstandard theorem.

## 9. What this commit does not claim

This wiring does not claim:

- existence or construction of a real logically omniscient machine;
- literal execution at an unlimited hypernatural budget;
- a proof of transfer for any new AMLD theorem;
- a solution to Gödel-style limitations;
- that an oracle hint is true merely because code labels it an oracle;
- any new verifier-certified mathematical settlement.

Ground-truth records used in a scientific experiment must themselves have explicit provenance and a defensible certification procedure appropriate to P/R/I/C.
