# Predator 8.001 ATP status report

Test date: 2026-08-01 (America/Los_Angeles)  
Author: Brian Tenneson

## Conclusion

**Predator 8.001 qualifies as a bounded, certificate-producing automated
theorem prover on the tested controls.**

This conclusion is operational and deliberately limited. Predator receives a
formal target, searches only the strict pre-target formal environment, emits
an explicit Metamath certificate when it succeeds, and treats the independent
Metamath verifier as final authority. It is heuristic and incomplete: finite
failure means unknown under the declared bounds.

This report does not claim that Predator 8.001 proves every set.mm theorem,
outperforms Predator 7.1, or already contains the planned ML model and shared
verified-lemma system.

## Frozen identities

| Artifact | SHA-256 |
|---|---|
| `Predator_8.001_FROZEN.py` | `d9c914fdc68cf0f19d3b4da75ea502843ca5747fce66853a14804dba2c6d682b` |
| `set.mm` | `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5` |
| `metamath.py` | `6e6d5f08083eaa788cd39eca486eff69de37a71e213e74edc77f20da23c381a4` |
| `setmm_grammar.py` | `eaf0c270c736b3798d3bbc8af6a70258cb3a57ebf4dd83fc823633e13026783c` |
| qualification harness | `bb193b1845917ad88fcc5d66958a2b20526d4d4f1c7fd2a47e7e3a0773fd5c44` |
| independent-CV adapter | `25f8140014db1259f54e023cb111537bf4ab4f40e89fc3f67acd4cabaf5b7817` |

The qualification harness and independent-CV hashes identify the exact files
used in this report. Any later edit creates a new experimental condition and
requires updated hashes.

## Why this is an ATP test

For each positive control, the test harness:

1. supplied the theorem statement as the formal goal;
2. rebuilt grammar from labels declared strictly before the target;
3. indexed only logical assertions declared strictly before the target;
4. installed a trap that raises if search touches the stored target proof;
5. ran population-based backward proof search under a finite global expansion
   budget;
6. emitted a Metamath proof-token certificate; and
7. started a fresh process that imported the Metamath verifier but no Predator
   search code.

The external checker also rejects every proof token not declared before the
target. An adversarial certificate containing only `idd` as the proof of `idd`
was rejected with:

`certificate uses labels not declared before idd: idd`

## Mandatory qualification results

Budget: 5,000 global expansions per target. Creativity: 0.55. Seed: 881.

| Control | Search outcome | Expansions | Certificate steps | External CV |
|---|---:|---:|---:|---:|
| `idd` | verified proof | 16 | 7 | PASS |
| `axin1` | verified proof | 2 | 2 | PASS |
| toy unproved conjunction | unknown under bounds | 32 | none | PASS (no claim) |

All mandatory controls passed. The negative control is important: the engine
exhausted its finite search without inventing a certificate or converting
failure to a counterexample.

## Extended blind capability ladder

The same isolation and external verification were applied with a 5,000
expansion budget per target.

| Target | Domain | Search outcome | Expansions | Certificate steps | Winner |
|---|---|---:|---:|---:|---|
| `biid` | biconditional | verified proof | 114 | 7 | conservative |
| `ancom` | conjunction commutativity | verified proof | 1,228 | 13 | balanced |
| `orcom` | disjunction commutativity | verified proof | 21 | 13 | conservative |
| `uncom` | union commutativity | unknown under bounds | 5,000 | none | none |

Every claimed proof passed the external CV. The `uncom` outcome is a measured
search boundary, not a denial of the theorem and not evidence that Predator is
not an ATP.

The `ancom` result is also evidence that the population is not merely four
names for one trajectory: the conservative share exhausted, and the balanced
agent found the verified certificate.

## `prcom` controls

Both `prcom` runs were blind: the stored target proof was not supplied to
search, and only assertions before `prcom` were indexed.

| Condition | Global budget | Creativity | Seed | Elapsed | Outcome |
|---|---:|---:|---:|---:|---|
| original population control | 80,000 | 0.55 | 0 | 1,863.7 s | unknown under bounds |
| maximum-creativity control | 80,000 | 1.00 | 2301 | 1,545.1 s | unknown under bounds |

The second trial changed creativity and seed while preserving budget, depth,
candidate cap, maximum open goals, and lack of ML guidance. It finished about
17.1% faster in wall time but did not find a certificate. Wall time is not a
proof-search transaction count and should not be treated as an algorithmic
success metric by itself.

## What is established and what remains

Established:

- target-blind bounded proof search;
- explicit certificate production;
- fresh-process independent verification;
- strict declaration-order isolation;
- honest unknown outcomes;
- global population budget conservation;
- verified proofs across several propositional forms.

Not yet established:

- performance parity or superiority relative to Predator 7.1 on an identical
  benchmark panel;
- success on `uncom`, `prcom`, or a separately formalized HaloProof target;
- trained policy/value guidance;
- shared verified intermediate-lemma memory;
- adaptive scheduling or parallel agents;
- completeness under unbounded resources.

## Correct next order

1. Preserve this untrained qualification as the control condition.
2. Attach and freeze the exact Predator 7.1 executable for a same-target,
   same-budget comparison.
3. Freeze a leakage-controlled training split that excludes each benchmark
   proof, downstream theorems, exact structural duplicates, and route hints.
4. Train policy guidance for legal assertion ranking and value guidance for
   remaining logical cost.
5. Integrate the model in a new 8.002 line without altering the verifier or the
   ATP acceptance criteria.
6. Add read-only budget telemetry, then verified lemma memory, with separate
   tests for each mechanism.

