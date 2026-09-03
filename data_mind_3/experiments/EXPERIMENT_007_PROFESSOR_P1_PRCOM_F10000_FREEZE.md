# DATA MIND 3.1 Experiment 007 Freeze

Status: FROZEN / PREREGISTERED / NOT YET RUN at this commit

## Question

Can the DATA MIND 3.1 Professor-facing, operationally self-aware P1 lane make new progress on `prcom` under the same 20,000-expansion primary budget used in Experiment 006, while retaining a protected non-Professor P2 fallback; and, if PRCOM remains unresolved in both lanes, can the 3.1 Ocean adapter emit and independently verify the exact-depth certificate for F(10,000)?

## Frozen lineage

- Development checkpoint: `dm31-professor-reflective-agents`
- Pre-experiment checkpoint: `dm31-pre-exp007-freeze`
- Experiment branch: `dm31-exp007-professor-p1-prcom-f10000`
- Runtime base commit before this preregistration: `1f4f7c6134be0daeb9bd37904b8bb561960bf9c8`
- Architecture remains DATA MIND **3.1**. The experiment number changes; the DATA MIND version number does not.

## Primary target: PRCOM

Metamath label: `prcom`

Target statement:

`|- { A , B } = { B , A }`

Frozen `set.mm`:

- commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`
- SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`

The independent Metamath verifier remains sovereign. Professor scores, self-awareness, Child proposals, and control values cannot make a candidate valid.

## Condition P1: primary scientific condition

P1 is Professor-facing and operationally self-aware. The Child is advisory creativity under P1; it is not the global scheduler.

Frozen search budget and limits:

- candidate cap: 64
- max expansions: 20,000
- max depth: 24
- max open goals: 24
- max frontier: 200,000 (SearchConfig default)
- timeout: 1,800 seconds
- control interval: 16 expansions
- cold start: no experience input
- initial creativity: all 11 normalized coordinates = 0.5
- Child knob play: enabled
- Child fine step and inverse rules: unchanged from Experiment 006 implementation

### Professor-mediated P1 partial credit

The existing raw structural score `q_raw` is explicitly treated as a locally checked structural proxy, **not** as terminal verifier acceptance and **not** as an exact transaction-geometric repair distance.

Define the repair-burden proxy

`H_hat = max(0, 1/q_raw - 1)`.

The first positive `H_hat` fixes the run-specific proof half-distance scale `h_P = H_hat_root`, so one `h_P` of proxy burden halves repair proximity:

`repair_proximity = 2^(-H_hat/h_P)`.

The frozen Professor scalarization used by P1 is

`PC_prof = 0.50*q_raw + 0.50*repair_proximity`.

Target relevance remains a separate successor-ranking signal and is not counted again in `PC_prof`.

Professor grades; P1 owns the control response. The inherited Child receives P1's Professor-mediated progress signal for keep/rollback decisions.

### Primary endpoint

- `PROVED` only if the emitted PRCOM certificate is accepted by the independent Metamath verifier.
- Otherwise `UNKNOWN` with the exact stop reason.
- Record expansions, generated children, elapsed time, peak RSS, controller updates, Professor grades, self-observations, Child trials, inverse trials, final creativity, and verifier calls.

The primary comparison to Experiment 006 is **P1 alone at 20,000 expansions**. This is not a one-variable ablation because several related architecture changes are intentionally activated together; causal claims must remain limited.

## Condition P2: protected fallback lane

P2 runs **only if P1 is not PROVED**.

P2 is deliberately not Professor-facing and not self-aware in this experiment. It uses the ordinary DATA MIND 3.1 adaptive controller with no Child knob play.

P2 receives the same per-lane PRCOM limits:

- candidate cap: 64
- max expansions: 20,000
- max depth: 24
- max open goals: 24
- max frontier: 200,000
- timeout: 1,800 seconds
- control interval: 16
- cold start

P2 is a protected diversity/fallback lane, not an equal-budget comparator to P1. If P2 runs, the maximum combined PRCOM portfolio budget is 40,000 expansions. Therefore the combined portfolio result must **not** be compared to Experiment 006 as an equal-total-budget ablation.

## Conditional fallback: Ocean F(10,000)

F(10,000) runs only if both PRCOM lanes remain unproved.

Generation is frozen to:

- `benchmarks/ocean/generate_ocean_tptp.py`
- length `L*=10000`
- one instance
- seed `1`

The generator independently checks that the shortest graph distance is exactly 10,000 before emitting the TPTP problem.

The DATA MIND 3.1 Ocean adapter then sees **only the serialized TPTP problem**. It does not read the planted route, generator internal graph object, hidden solution, or precomputed certificate. The disclosed search policy is plain breadth-first search over the serialized directed implication graph.

This is a deep-certificate calibration fallback, not a claim that the historical specialized `Depths-F` implementation was run.

The emitted certificate must:

1. begin at the serialized start node,
2. end at the serialized target node,
3. use only implication edges present in the TPTP file,
4. contain exactly 10,000 transitions,
5. pass the separate Ocean certificate verifier.

Outcome is `PROVED` only after that independent verification; otherwise `UNKNOWN` or protocol failure as appropriate.

## Sequential stopping rule

1. Run PRCOM P1.
2. If P1 is `PROVED`, stop scientific search; do not run P2 or F(10,000).
3. If P1 is not `PROVED`, run PRCOM P2.
4. If P2 is `PROVED`, stop scientific search; do not run F(10,000).
5. If both are unproved, generate and run F(10,000).

No parameter tuning, rerun, alternate seed, or threshold change is permitted after observing P1 or P2 in this official Experiment 007 run.

## Workflow semantics

Scientific `UNKNOWN` is valid data and must not be converted into a red workflow failure. A workflow failure is reserved for implementation/protocol errors such as malformed inputs, unexpected return codes, hash mismatch, failed preflight, missing artifacts, or rejected claims of verification.

All source hashes, frozen input hashes, runner return codes, timing/RSS records, result JSON, Historian JSONL, experience logs, PRCOM proof labels (if any), Ocean problem/certificate (if reached), and verification records will be uploaded as the official Experiment 007 artifact.
