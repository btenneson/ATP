# DATA MIND 3.3 — Logical Dreamer Architecture Contract

**Status:** IMPLEMENTED AS A REVERSIBLE RESEARCH SCAFFOLD  
**Scientific experiment status:** NO SCIENTIFIC EXPERIMENT LAUNCHED  
**Base:** `dm32-oracle-atp-ifs-abel` at `a352c0f2384a41d30b9f7766fb7301860b889679`

## 1. Purpose

DATA MIND 3.3 introduces a Logical Dreamer as a formally reflective ATP component with controlled access to the four DATA MIND 3.2 oracle faculties:

- O1 — role/type
- O2 — resource allocation
- O3 — strategy/action class
- O4 — certificate candidate

The ideal four-type hyperfinite omniscience theory remains a mathematical limit object. The executable 3.3 system implements only finite, gated, throttled oracle interfaces.

## 2. Oracle access mask

Dreamer carries four independent binary access gates in canonical order O1/O2/O3/O4.

`(s1, s2, s3, s4) in {0,1}^4`

A bit value of 1 means Dreamer may attempt to consult that oracle interface. A bit value of 0 means the interface must not be invoked.

There are 15 nonempty access masks. These 15 subsets are not the same mathematical objects as the 15 Bell(4) set partitions implemented in DATA MIND 3.2.

## 3. Hard throttling

Every oracle interface is guarded at the actual call site. A throttle may impose:

- a maximum total call count;
- a minimum number of Dreamer/search steps between calls.

A disabled or throttled oracle is not invoked. Telemetry counts actual invocations separately from skipped opportunities.

FUTUREBANK promotion has an independent hard throttle. Promotion means only a request for external computation/checking.

## 4. Dreamer synthesis

Dreamer receives heterogeneous oracle responses and synthesizes them into one speculative `FutureProposal`.

Oracle outputs are not added together as a literal linear combination. The four access bits are gates; synthesis is a separate operation.

Each proposal records:

- Dreamer oracle access mask;
- oracle facets actually consulted;
- reported oracle cost;
- target and step provenance;
- speculative action/payload.

## 5. FUTUREBANK and verifier sovereignty

The only direct storage destination exposed by the Logical Dreamer is FUTUREBANK.

Allowed path:

`O1/O2/O3/O4 -> Dreamer -> FUTUREBANK -> promotion gate -> real search/checking -> verifier -> BANK`

Forbidden paths:

`Dreamer -> BANK`

`Oracle -> BANK`

`Dreamer -> verifier acceptance`

`Oracle -> verifier acceptance`

The Dreamer class intentionally has no verifier, certification, or BANK-deposit method.

## 6. Initial formal self-awareness

The initial Dreamer is operationally reflective at a level-2 interpretation: it can represent its own access, actual oracle usage, remaining call allowance, reported resource cost, proposal history, promotion history, and observed verified contribution.

The four oracle implementations themselves are initially treated as level-0 specialized faculties. They need not represent themselves.

For each oracle, Dreamer reflection records:

- enabled/disabled state;
- actual call count;
- remaining call allowance;
- last call step;
- total reported cost;
- disabled/throttled skips;
- number of Dreamer proposals supported;
- number of externally reported verified contributions;
- empirical verified contribution yield.

This is search-control self-knowledge only. It is never certificate knowledge.

## 7. Initial implementation scope

Implemented now:

1. four-bit oracle access mask;
2. enumeration of the 15 nonempty masks;
3. actual-call-site oracle throttling;
4. separate FUTUREBANK promotion throttle;
5. heterogeneous oracle response interface;
6. Dreamer synthesis into speculative FUTUREBANK proposals;
7. proposal provenance/cost logging;
8. operational self-reflection over access, usage, cost, and observed consequence;
9. tests asserting no verifier/BANK authority surface;
10. typed finite O1 role, O2 resource, O3 strategy, and O4 certificate-candidate adapters;
11. a non-privileged `DreamerSearchSnapshot` populated from ordinary search-control telemetry;
12. a Metamath shadow bridge that invokes Dreamer only on genuine controller update events;
13. forced no-promotion shadow execution, with no causal effect on search decisions.

Not yet implemented:

- a scientific benchmark of Dreamer effectiveness;
- promoted Dreamer actions that can affect the live search;
- adaptive O2 control of oracle throttles;
- self-aware oracle implementations;
- full Dreamer/oracle awareness matrix;
- executable hypernatural or standard-part machinery;
- learned weighted embeddings/linear mixtures of oracle outputs;
- modification of frozen DATA MIND 3.1 experiment protocols.

## 8. Experimental principle

The first scientific question for DATA MIND 3.3 is intended to be:

> Under equal externally enforced resource budgets, does a formally reflective Logical Dreamer with controlled access to selected subsets of O1/O2/O3/O4 improve verifier-certified settlement performance?

No result is claimed until a separately frozen and launched experiment answers that question.

## 9. Milestone 2 — four-oracle installation in shadow mode

The first finite oracle installation uses typed advice rather than treating oracle outputs as interchangeable scalars:

- O1 returns task-role advice. In the present Metamath proof-search lane it identifies the configured lane as `P` but explicitly does not infer hidden theorem truth.
- O2 reads checked resource/frontier/branch/stagnation telemetry and returns a conservative finite resource posture.
- O3 reads checked search telemetry and returns one existing `EscapeAction` class.
- O4 may surface an already-existing candidate certificate reference and readiness signal, but it cannot invent verifier acceptance or certify a proof.

The `ShadowDreamerController` wraps an inherited DATA MIND controller by delegation. Ordinary goal selection, successor scoring, creativity, effective search settings, Sentinel behavior, verifier behavior, and BANK semantics remain owned by the inherited system.

Dreamer is called only after the inherited controller emits a real control-update event. The bridge then creates a speculative FUTUREBANK proposal and closes the transaction without requesting promotion.

Therefore Milestone 2 establishes the executable path

`live ATP telemetry -> O1/O2/O3/O4 -> Dreamer -> FUTUREBANK -> discard/audit`

while deliberately not yet establishing

`FUTUREBANK -> promoted live search action`.

This shadow phase is architecture validation only and is not a scientific settlement experiment.
