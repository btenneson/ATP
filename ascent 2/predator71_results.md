# Measuring Predator 7.1

*Draft results section for Part I. All figures reproducible from the scripts and CSVs in this folder.*

---

## 1. A correction to the previously reported figure

An earlier run of this system reported **4/11 on a named propositional ladder**, concluded that "everything requiring ax-3 failed," and inferred that negation was the boundary of the prover's competence. That inference does not survive inspection of the base it was measured against.

The base was `predator71.SELFTEST`, which declares

```
$c wff |- ( ) -> /\ $.
```

and the assertions `ax1`, `ax2`, `ax-mp`. **There is no `-.` in the language and no ax-3 among the axioms.** Targets such as `notnot1`, `notnot2`, `con3`, `pm2.18` and `peirce` were therefore not unprovable on that base — they were *unstatable*. The reported result conflated a language defect with a search ceiling, and the causal story ("negation is where it stops") was an artifact of the instrument.

Everything below is measured against set.mm's actual propositional core, with negation present:

```
ax-1  |- ( ph -> ( ps -> ph ) )
ax-2  |- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) )
ax-3  |- ( ( -. ph -> -. ps ) -> ( ps -> ph ) )
ax-mp
```

Every target in §3 is a theorem of this system, so every failure is a search failure and nothing else.

---

## 2. Method

**Chronological prefix.** For a target theorem *t* at position *i* in the database, the prover is given an index over `order[:i]` only — every assertion the human author had available at that point, and nothing later. This is the `upto=` argument `cmd_prove` already uses, applied systematically. `bench_p71.py` builds this index incrementally, so the whole sweep costs one pass over the database rather than one pass per target.

**Ground-truth difficulty.** `metamath.classify` separates `|-` steps from formula construction, which is roughly 95% of raw Metamath proof length. The independent variable is the number of *logical* steps in the human proof. This is base-relative and padding-proof, which the arithmetical tier of the target is not (see §6).

**Graded sweep.** Each target is attempted across budgets {1k, 5k, 20k, 60k} × depths {6, 12}, stopping at the cheapest setting that succeeds. `prove()` returns `(None, exp)` on failure, and two failures that look alike are not:

| condition | reading |
|---|---|
| `exp > budget` | **budget-bound** — frontier still had nodes; more budget may help |
| `exp <= budget` | **exhausted** — frontier emptied; no route exists within `max_depth`, so more budget cannot help |
| wall-clock hit | **wall-bound** — neither limit reached in time |

`prove()` has no timeout of its own. The harness passes a `say` callable that raises at a deadline, so the prover source is untouched.

**Certification.** Every proof found is emitted as a Metamath certificate and handed to `metamath.py`, which knows nothing about how it was produced. Soundness is measured as the CV rejection rate, and it is the only soundness number that means anything — a prover that proves nothing scores perfectly on any "never asserts a falsehood" metric.

---

## 3. Result: the named ladder, axioms only

Sixteen classical propositional theorems, base = the four primitives above, no derived lemmas.

**4/16 proved. 0 CV rejections.**

| target | statement | outcome | expansions | logic steps | CV |
|---|---|---|---|---|---|
| `id` | `( ph -> ph )` | **proved** | 36 | 5 | ok |
| `a1i-cl` | `( ph -> ( ps -> ph ) )` | **proved** | 2 | 1 | ok |
| `imim2` | `( ( ph -> ps ) -> ( ( ch -> ph ) -> ( ch -> ps ) ) )` | **proved** | 217 | 7 | ok |
| `pm2.21` | `( -. ph -> ( ph -> ps ) )` | **proved** | 197 | 7 | ok |
| `pm2.27` | `( ph -> ( ( ph -> ps ) -> ps ) )` | exhausted | 18,480 | — | — |
| `imim1` | `( ( ph -> ps ) -> ( ( ps -> ch ) -> ( ph -> ch ) ) )` | exhausted | 19,508 | — | — |
| `pm2.04` | `( ( ph -> ( ps -> ch ) ) -> ( ps -> ( ph -> ch ) ) )` | exhausted | 20,478 | — | — |
| `pm2.24` | `( ph -> ( -. ph -> ps ) )` | exhausted | 18,368 | — | — |
| `con3` | `( ( ph -> ps ) -> ( -. ps -> -. ph ) )` | exhausted | 18,867 | — | — |
| `notnot1` | `( ph -> -. -. ph )` | exhausted | 15,877 | — | — |
| `notnot2` | `( -. -. ph -> ph )` | exhausted | 15,885 | — | — |
| `con1` | `( ( -. ph -> ps ) -> ( -. ps -> ph ) )` | exhausted | 18,880 | — | — |
| `con2` | `( ( ph -> -. ps ) -> ( ps -> -. ph ) )` | exhausted | 18,860 | — | — |
| `pm2.01` | `( ( ph -> -. ph ) -> -. ph )` | exhausted | 16,411 | — | — |
| `pm2.18` | `( ( -. ph -> ph ) -> ph )` | exhausted | 16,410 | — | — |
| `peirce` | `( ( ( ph -> ps ) -> ph ) -> ph )` | exhausted | 16,502 | — | — |

`a1i-cl` is degenerate — it is ax-1 restated, closed in one step — and should be excluded from any headline rate. The honest figure is **3/15 on non-trivial targets.**

### 3.1 Negation is not the boundary

`pm2.21` is `( -. ph -> ( ph -> ps ) )`. It requires ax-3, it contains negation, and it is proved in 197 expansions and 7 logical steps with a CV-accepted certificate. The previously reported causal story is therefore false. Conversely `imim1` and `pm2.04` are negation-free and both fail. **The proved/failed split does not follow the presence of negation, and it does not follow ax-3 usage.**

### 3.2 The failures are not budget failures

Every one of the twelve failures is **exhausted**, not budget-bound: the frontier emptied between 15,877 and 20,478 expansions against a 60,000 budget. Raising the budget to 200,000 changes nothing, because there is nothing left to expand.

Two ablations locate the actual constraint:

| condition | `pm2.27` | `peirce` |
|---|---|---|
| depth 12, max_open 6 | exhausted, 18,480 | exhausted, 16,502 |
| depth 12, max_open 12 | exhausted, 23,806 | exhausted, 21,817 |
| depth 20, max_open 6 | no exhaustion in 7 s | no exhaustion in 7 s |
| depth 30, max_open 6 | no exhaustion in 7 s | no exhaustion in 7 s |

Relaxing `max_open` from 6 to 12 enlarges the searched space by ~30% and finds nothing. Raising the depth limit past 12 makes the frontier explode without terminating. **The binding constraint is depth, and depth is unreachable because the search has no way to prefer one branch over another.**

### 3.3 Root cause, from the source

Two facts in `predator71.py` account for the shape of these results.

1. `prove()` accepts a `rank` parameter, but **no caller ever passes it** — not `cmd_prove`, not `cmd_selftest`, not this harness (there is nothing to pass). With `rank=None`, `sc_c` and `sc_o` are all-zero and the candidate ordering at the assertion-selection step is inert.
2. The frontier priority is `node.depth + 1 - 0.0`.

Together these make the search **breadth-first with an unused heuristic slot**. Cost is exponential in depth with no branch preference, which predicts exactly the observed profile: everything shallow succeeds cheaply, everything deep exhausts its depth-bounded space and then becomes unreachable. The heuristic slot is the single highest-value place to intervene.

---

## 4. Result: soundness

| run | certificates emitted | CV rejections |
|---|---|---|
| named ladder, axioms only | 4 | **0** |
| fixture, chronological prefix | 60 | **0** |
| fixture, axioms only | 60 | **0** |
| **total** | **124** | **0** |

The ATP/CV split holds. No proof Predator emitted was rejected by `metamath.py`, and the CV was run in a separate process state with no knowledge of the search. This is the strongest result in the set, and it is a property of the architecture rather than of the search.

---

## 5. Result: the lemma-availability confound

A validation database of 60 theorems was generated by forward condensed detachment over the same four primitives (`make_fixture.py`); all 60 human proofs are CV-verified. Running the harness against it in both base modes:

| base mode | solved | proofs shorter than human | solved in one logical step |
|---|---|---|---|
| chronological prefix | 60/60 | 55 | **19** |
| axioms only | 60/60 | 12 | 0 |

**The 60/60 under a chronological prefix is largely not search.** Nineteen targets were closed in a single logical step because an earlier theorem in the database already unified with the goal, and 55 of 60 "proofs" are shorter than the human's. Any solve rate reported over a chronological prefix must be accompanied by the found-vs-human step ratio, or it measures the density of the library rather than the power of the prover.

This generalises: it is the same failure mode as grading a prover by the highest-tier statement it can reach in the database (§6), and the same failure mode as reporting `lev` against a fixed tagged base — in each case the number is a property of the base, and every prover on that base returns it.

### 5.1 Saturation bias — a threat to validity

The fixture gives 60/60 from axioms alone while the named ladder gives 4/16 from the same axioms. The fixture is not easier by accident: its targets were *generated* by four rounds of forward saturation under a formula-size cap of 15, so by construction they are exactly the theorems a shallow search can reach. **A benchmark generated by saturation is biased toward what shallow search finds, and will systematically overstate a shallow prover.** The named ladder, chosen independently of the prover, is the trustworthy measurement; the fixture's role is harness validation, not evaluation.

---

## 6. Why no tier is reported

The natural question is what arithmetical tier this places the prover at. The measurement answers it, in the strongest possible way: **every one of the sixteen targets is a quantifier-free propositional wff, so all sixteen are at tier 0.** The four it proves and the twelve it fails are at the identical tier. The tier column has no variance across a 4-versus-12 split in outcome, so it has no explanatory power over anything the prover does.

This is not specific to the propositional fragment. Two general obstructions:

- **Syntactic tier is padding-degenerate.** For every *n* there is a Σ⁰ₙ sentence with an O(1)-step proof. If a prover can prove anything at all, the supremum over provable targets is unbounded.
- **Semantic tier is truth-degenerate on sentences.** Every provable sentence is true, and every true sentence is equivalent to `0 = 0`. Semantic tier only carries information on formulas with free variables, i.e. on the set `{n : φ(n)}`, not on a closed target.

Neither reading survives contact with a prover, so tier is not reported. Search power is indexed by proof depth (§3) and certificate power by p-simulation, which is a separate and independent axis: Predator's certificates are Frege proofs and are as strong as the base permits, while its search stalls at depth 12. **Certificate power and search power must be reported separately; the 4/16 constrains only the latter.**

---

## 7. Reproduction

```
python make_fixture.py  --out fixture.mm --rounds 4 --cap 15 --limit 60
python metamath.py      verify fixture.mm

python named_ladder.py  --out results_ladder --budgets 1000 5000 20000 60000 \
                        --depths 6 12 --wall 25

python bench_p71.py     --db fixture.mm --out results_prefix --base-mode prefix
python bench_p71.py     --db fixture.mm --out results_axioms --base-mode axioms
```

Against set.mm, the same two commands run the real protocol unchanged:

```
python bench_p71.py --db set.mm --out setmm_prefix --base-mode prefix \
                    --scan 4000 --max-logic 6 --per-depth 12
python bench_p71.py --db set.mm --out setmm_axioms --base-mode axioms \
                    --scan 4000 --max-logic 6 --per-depth 12
```

Data: `data/named_ladder.csv`, `data/fixture_prefix.csv`, `data/fixture_axioms.csv` and the matching `*_summary.json`.

---

## 7a. Result: set.mm

The protocol has since been run against the real database (47,572 theorems, 3,000 primitive assertions). Targets: closed theorems only, human logical depth 1–5, chronological prefix, budget 5,000, depth 6.

**15/52 certified. 0 CV rejections. But 12 of the 15 were single-logic-step lemma lookups — genuine multi-step search solves: 3/52.**

The lemma-availability confound of §5 is therefore not an artifact of the generated fixture; it dominates on the real corpus too. Note that Revision 2 of the companion document reaches the same conclusion independently by a different route, measuring that 4.7% of set.mm's logical assertions share both conclusion and hypotheses with another label and 2.9% are hypothesis-free duplicates.

Caveat on failure attribution: many set.mm failures were wall-bound at under a second rather than exhausted, so the budget/depth/no-route decomposition is weaker here than in the propositional run, where all twelve failures were true frontier exhaustion.

### 7b. The CV caught an unsound harness

Worth recording as a result rather than an incident. Theorems such as `a1i` (`ph ⊢ ( ps -> ph )`) have `$e` hypotheses, and their bare conclusion is not a theorem — so the first version of the harness was scoring the prover for failing unprovable goals. The obvious repair, adjoining each hypothesis to the index as a closer, is **wrong**: Predator renames every candidate's variables apart at each use, which turns the hypothesis into a schema, so `ph` becomes universally quantified and unifies with anything.

Under that repair the harness reported **8/8 solved**. `metamath.py` rejected 7 of the 8 certificates with *"proved the wrong statement."* The score went from 1/6 to a false 8/8, and the CV was the only thing that noticed.

Targets are now restricted to closed theorems. This is the strongest available evidence for the architecture: the untrusted component was made to look four times stronger by a subtle harness bug, and the trusted component caught it without knowing anything about the search.

## 8. What is still missing
1. **A comparison baseline.** 3/52 and 4/16 are uninterpretable in isolation. On the Metamath test-set task, Holophrasm reported 14.3% over 2,720 set.mm theorems and GPT-f roughly 56%. Those are full-database numbers with learned premise selection and are not directly comparable to these conditions, but no figure here should be quoted without a baseline beside it.
2. **A cactus plot.** Requires enough solved instances to have a distribution. Fifteen, twelve of them one-step lookups, is not enough.
3. **Cleaner failure attribution on set.mm.** The wall-bound failures need re-running with a longer per-target budget to separate exhausted from budget-bound.
4. **The `rank` intervention.** The dead heuristic slot is identified but still not filled *in Predator*. It has now been filled in the successor system, where a hand-written ordering cut nodes-on-certified-targets by 48% at unchanged coverage — and where the first version of the heuristic made things *slower*, and the second silently did nothing because the feature it keyed on collected bound-variable names. Both were found by measurement, not by reading. That is the argument for establishing a hand baseline before fitting a model to the same slot.

---

*Computational experiments and implementation by Claude (Anthropic); all definitions, theorems, and framing by the author. Note that arXiv and most journals require AI contribution to be disclosed in Acknowledgments rather than as authorship.*
