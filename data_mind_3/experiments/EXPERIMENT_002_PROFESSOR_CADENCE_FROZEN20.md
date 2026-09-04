# DATA MIND 3.1 Experiment 002 — Professor Cadence Frozen-20

Status: PREREGISTERED RESEARCH ABLATION

This experiment follows DATA MIND 3.1 Experiment 001 and tests the specific failure hypothesis suggested by its results: Professor/self-awareness may be useful, but the active control channel may intervene too frequently and oversteer P1.

This is not an official DATA MIND 3.1 settlement run. `RUNTIME_CONFIG_001.json` remains intentionally unresolved for official execution. The experiment is additive, branch-isolated, verifier-gated, and uses the permanent `DATA-MIND set.mm Frozen-20 Benchmark 001` lock without changing the training split, targets, seed, proof-redaction policy, source `set.mm`, or verifier gate.

## Primary question

Does reducing Professor-to-P1 control-intervention frequency preserve the Experiment 001 rescue behavior while reducing regressions and runaway search?

The motivating Experiment 001 observations were:

- A-P1 proved 5/20.
- Active Professor/self-aware P1 also proved 5/20.
- Active P1 uniquely rescued `bj-cleljusti`.
- Active P1 lost `prmone0`, which fixed A-P1 proved.
- Active P1 drove `sbf2` and `pm5.62` to the full 50,000-expansion lane budget although fixed A-P1 stopped much earlier.

## Operational definition of communication

The current reflective controller computes Professor-grade information continuously, while creativity/search-control changes occur only when the inherited controller reaches its control interval. For this experiment, **Professor communication frequency means Professor-to-P1 control interventions that can change P1's creativity/search-control state**. Internal diagnostic measurement is not itself counted as a communication event.

No architecture source file is changed to obtain the cadence treatments. The cadence manipulation lives only in the Experiment 002 runner.

## Frozen arms

Every target receives the same six fresh-process lanes:

1. `off` — balanced P1, fixed 11D creativity vector, no Professor-driven control changes.
2. `p2` — the same theorem-independent fixed P2 strategy used in Experiment 001, derived from frozen split seed 271828.
3. `c16` — reflective P1, Child off, Professor control interval 16 expansions.
4. `c64` — reflective P1, Child off, Professor control interval 64 expansions.
5. `c256` — reflective P1, Child off, Professor control interval 256 expansions.
6. `event` — reflective P1, Child off, event-triggered control with a 128-expansion refractory period.

The `c16` arm is the direct replication cadence of Experiment 001's active P1 treatment.

### Event arm triggers

The event arm continuously measures the same Professor evidence but permits a search-changing intervention only when the 128-expansion cooldown has elapsed and at least one of these preregistered conditions holds:

- bootstrap at expansion 128 if no earlier intervention occurred;
- absolute raw structural partial-credit change of at least 0.05 since the previous intervention;
- at least 256 expansions without a new best raw structural partial credit;
- frontier occupancy at or above 75% of the frozen frontier ceiling;
- elapsed-time occupancy crossing 50% or 75% of the frozen lane timeout, each threshold firing at most once.

Trigger reasons are recorded in telemetry. This arm is exploratory; the fixed 16/64/256 cadence comparison is the cleaner test of the frequency hypothesis.

## Frozen budgets and search controls

Per lane:

- maximum expansions: 50,000
- timeout: 900 s
- candidate cap: 64
- maximum depth: 24
- maximum open goals: 24
- maximum frontier: 200,000
- Child knob play: disabled
- QH/trading: absent
- R/I/C agents: absent

The common P2 lane is retained only as the same independent strategy hedge used in Experiment 001. Primary cadence inference is based on P1-only outcomes so P2 cannot mask treatment differences.

## Proof isolation and certification

The exact Experiment 001 proof-isolation protocol is retained:

- reconstruct the permanent 95/5 split in a separate proof-aware preparation process;
- emit only ordered holdout labels and hashes, never hidden proof contents;
- settlement parser discards theorem proof text;
- remove every non-target held-out theorem from the legal search library;
- reject any candidate certificate that references a held-out theorem label;
- require fresh independent acceptance by `metamath.py` before counting a proof.

A green workflow job is not a theorem proof. Only verifier-accepted certificates count.

## Primary outcomes

For each P1 cadence arm, record:

- verifier-certified P1 settlements out of 20;
- settlement count after adding the same common P2 hedge;
- gains and losses relative to `off` on the exact same frozen targets;
- expansions and elapsed time on certified settlements;
- control-intervention count;
- number of lanes reaching the 50,000-expansion ceiling;
- final 11D creativity vector.

The most important qualitative diagnostic is whether a quieter Professor can retain a `bj-cleljusti`-type rescue without reproducing the `prmone0` regression or full-budget oversteering.

## Interpretation rule

The experiment does not claim that a cadence is universally optimal from n=20. A useful result is a reproducible direction-of-effect showing that changing only intervention cadence changes verifier-certified settlement, regressions, or runaway-resource behavior.

After selecting a defensible cadence from this experiment, the next planned benchmark is the separate P/R/I/C Four-Role Architecture Stress Test, where the chosen Professor cadence will be frozen before testing the non-ATP society components.
