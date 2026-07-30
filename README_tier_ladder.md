# Predator 7.1 Tier Ladder — instructions and use

Answers one question: **what tier is Predator 7.1?** The prover is rated tier *N*
if there exists a tier-*N* target it genuinely proves.

---

## 1. Prerequisites

| Need | Notes |
|---|---|
| Python 3.9+ | dataclasses with `from __future__ import annotations`; no third-party packages |
| `set.mm` | the database itself, for screening |
| `predator71.py` | the searcher |
| `metamath_cv.py` | the verifier |

Screening reads `set.mm` directly. Without it the harness still runs, but prints a
warning and the results are not trustworthy.

---

## 2. Quick start

Exercise the whole flow with no prover attached:

```
python predator_tier_ladder.py --dry-run
```

Outcomes are simulated. Use this to see the pacing, the pause prompts, and the
report format before wiring anything up. Nothing is executed and nothing is
written except a results log.

---

## 3. Configuration

Two blocks near the top of the file.

### Paths and commands

```python
CONFIG = {
    "setmm":    "set.mm",
    "predator": "predator71.py",
    "verifier": "metamath_cv.py",
    "workdir":  "runs",

    "predator_cmd": "python {predator} --db {setmm} --target {target} "
                    "--budget {budget} --emit {out}",
    "verify_cmd":   "python {verifier} {out}",

    "budget":    200_000,
    "timeout_s": 3600,
}
```

`{predator} {setmm} {target} {budget} {out}` are substituted. **The two command
templates are guesses at your CLI** — correct them before a live run.

### Output patterns

```python
PATTERNS = {
    "expansions":    re.compile(r"expansions[:=]\s*(\d+)", re.I),
    "raw_steps":     re.compile(r"raw[ _]steps[:=]\s*(\d+)", re.I),
    "logical_steps": re.compile(r"logical[ _]steps[:=]\s*(\d+)", re.I),
    "cv_ok":         re.compile(r"(\d+)\s+verified,\s*0\s+failed", re.I),
    "cv_fail":       re.compile(r"(\d+)\s+failed", re.I),
}
```

`cv_ok` already matches the CV's real output format. The three prover patterns
need to match whatever `predator71.py` prints. If a pattern misses, that field
shows `-` and pass/fail still works — only the stats are lost.

---

## 4. Flags

| Flag | Effect |
|---|---|
| `--dry-run` | simulate; no prover needed |
| `--auto` | no pauses, run the whole ladder |
| `--budget N` | expansions per target (default 200,000) |
| `--from T4` | resume at a tier |
| `--skip-screen` | run screened-out targets anyway — **unsound**, diagnostics only |

---

## 5. The interactive loop

Before each target you get its card:

```
==========================================================================
  NEXT: T8   sqrt2irr
==========================================================================
  track        main
  position     16,303
  dep          3,914
  regime       search-hard
  expectation  fail

  THE DISCRIMINATING TARGET. Short logical proof, enormous applicable
  lemma pool at this position. Check hard for an ALT sibling.

  Proceed?  [y] yes  [s] skip  [q] quit :
```

- **y** — screen, run, verify, report
- **s** — record as `not-run` and move on
- **q** — stop; the verdict still prints for everything completed

After each target you get the result block and a **running rating**, so you can
stop as soon as the ladder plateaus rather than sitting through predictable
failures at T9–T11.

---

## 6. Reading the stats

| Field | Meaning |
|---|---|
| `outcome` | `PASS` / `FAIL` / `SCREENED OUT` / `ERROR` |
| `wall time` | informational only — never rate on it |
| `expansions` | the real budget unit |
| `logical steps` | steps concluding `\|-`; the unit that matters |
| `raw steps` | includes formula construction |
| `raw/logical` | sanity check — expect roughly 14 (median) to 21 (aggregate) |
| `horizon ratio` | expansions ÷ logical steps |
| `verifier` | CV verdict. **A PASS requires this line.** |

### On the horizon ratio

By the Proof-Horizon Theorem, `τ_BF = ‖φ‖`, and by Branch-Covering no
target-search SIC based solely on shortest proof length beats it. So
breadth-first is a *theoretically characterised* baseline, not an arbitrary one.

The field printed here is `expansions ÷ logical steps`, which is a **proxy** —
the true denominator is `‖φ‖_F(Γ)` under the admissible index, which the harness
does not compute. Treat it as a relative measure across targets, not an absolute
verdict on whether the horizon was beaten.

By Remark 8.2 the horizon does not bind machines with compiled side information,
so beating it is possible and is exactly the compilation advantage worth
measuring.

---

## 7. The ladder

**T1–T11** are the dep/position calibration table, ordered by dependency count:

| Tier | Label | pos | dep | Regime |
|---|---|---|---|---|
| T1 | `pm2.01` | 189 | 37 | deterministic |
| T2 | `simpl` | 486 | 44 | deterministic |
| T3 | `falim` | 1,584 | 80 | deterministic |
| T4 | `sbth` | 9,083 | 1,299 | witness-requiring |
| T5 | `canth2` | 9,116 | 1,608 | witness-requiring |
| T6 | `zorn` | 10,489 | 2,707 | witness-requiring |
| T7 | `ruc` | 16,297 | 3,585 | search-hard |
| T8 | `sqrt2irr` | 16,303 | 3,914 | **search-hard — the discriminator** |
| T9 | `pythag` | 26,957 | 7,568 | deep chain |
| T10 | `fta` | 27,219 | 7,839 | deep chain |
| T11 | `bpos` | 27,432 | 8,271 | deep chain |

**X1 / X2** are the out-of-distribution infinitesimals targets. They are reported
separately and **excluded from the tier rating** — averaging a retrieval-solvable
tier with an order-dependent one produces an uninterpretable number.

**T0** is `axin1`, one of the four Section 5 certificates shown to be duplicate
lookups. See below.

---

## 8. T0 — the control that tests the harness

T0 **must be screened out**. It is not a target; it is a probe of the screening.

If T0 comes back `PASS`, the harness prints:

```
*** SCREENING FAILURE: a known duplicate-lookup target was
    proved rather than screened out. Every result below this
    line is uninterpretable until the screening is fixed. ***
```

and the final verdict is marked void. Run T0 first, every session.

---

## 9. Screening

Implements Definition 5.2: exclude any label whose conclusion is a substitution
instance of the target, **or** of which the target is a substitution instance,
under variable renaming. Both directions — exact-duplicate exclusion alone would
not have caught `falanfal`.

| Check | Status |
|---|---|
| ALT / OLD sibling labels | implemented |
| Exact conclusion duplicate at lower position | implemented |
| Alpha-renamed duplicate (`normalise()`) | implemented |
| **Substitution instance, both directions** | **hook only — not implemented** |

> **The C3 gap is the known weakness.** A real substitution-instance check needs a
> matcher. Wire `setmm_grammar.py` into `screen()` before treating a clean screen
> as meaningful. Until then, screening catches syntactic duplicates but not
> semantic ones.

`T8 sqrt2irr` is the target most at risk — famous theorems attract alternative
developments, and an `ALT` sibling in the prefix means Predator can return a
valid proof that demonstrates nothing.

---

## 10. Output

Certificates land in `runs/<label>_p71.mm`. Each is a one-statement extension of
set.mm that cites only what precedes it.

Every session writes `runs/ladder-YYYYMMDD-HHMMSS.json`:

```json
{
  "tier": "T8", "label": "sqrt2irr", "outcome": "failed",
  "screened": [], "expansions": 200000, "budget": 200000,
  "raw_steps": null, "logical_steps": null, "wall_s": 1841.2,
  "cv_verdict": "n/a", "horizon_ratio": null,
  "note": "budget exhausted"
}
```

Keep these. Fix the budget *before* seeing results, and report it with every
number — "failed" without a stated budget is uninterpretable.

---

## 11. Suggested first session

1. `--dry-run` — confirm the flow reads the way you want.
2. Fix `CONFIG` paths; fix `PATTERNS` against one real prover run.
3. Live, interactive, `--budget 50000`. Confirm **T0 screens out** and T1 passes.
   Stop there.
4. If both behave, `--from T4 --budget 200000` and walk up until it plateaus.
5. Run X1 and X2 in a separate session. Never merge the numbers.

---

## 12. Troubleshooting

| Symptom | Cause |
|---|---|
| `prover not found` | `predator_cmd` template or path wrong |
| Everything `FAIL`, `no certificate emitted` | `--emit` flag name differs from your CLI |
| Stats all `-` | `PATTERNS` don't match your prover's output |
| `CV: unparsed` | verifier output format differs from `cv_ok` |
| `WARNING: could not read set.mm` | screening disabled — fix before trusting anything |
| T0 passes | screening broken; stop and fix before continuing |

---

## 13. Related files

| File | Contents |
|---|---|
| `atp_benchmark_protocol.pdf` | prefix holdout, the five screening checks, reporting format |
| `infinitesimal_benchmark_spec.pdf` | the X1/X2 targets, full definitions, Tier A/B suite |
| `infinitesimals_setmm.pdf` | four grades of "isomorphic" and what each costs |

---

## 14. Caveat

Positions and dep counts are from the Part III calibration table. All `set.mm`
label references are unverified against the current database — recompute before
publishing any of them. Three numerical errors in Revision 1 were found exactly
that way.

---

## 15. All commands

Everything, in order of use. Copy from here.

```bash
# ---------------------------------------------------------------
# SETUP — put these four in the same directory
#   predator_tier_ladder.py   set.mm
#   predator71.py             metamath_cv.py
# ---------------------------------------------------------------

python --version                       # need 3.9+
ls set.mm predator71.py metamath_cv.py # confirm all present


# ---------------------------------------------------------------
# STEP 1 — dry run. No prover touched. Learn the flow.
# ---------------------------------------------------------------

python predator_tier_ladder.py --dry-run          # interactive
python predator_tier_ladder.py --dry-run --auto   # straight through


# ---------------------------------------------------------------
# STEP 2 — calibrate PATTERNS against one real prover run.
#          Run your prover by hand, read what it prints, then edit
#          the regexes at the top of the script to match.
# ---------------------------------------------------------------

python predator71.py --db set.mm --target pm2.01 --budget 50000 --emit /tmp/t.mm
python metamath_cv.py /tmp/t.mm


# ---------------------------------------------------------------
# STEP 3 — first live session. Small budget. Stop after T1.
#          Confirm: T0 SCREENS OUT, T1 PASSES.
# ---------------------------------------------------------------

python predator_tier_ladder.py --budget 50000


# ---------------------------------------------------------------
# STEP 4 — walk the ladder until it plateaus.
# ---------------------------------------------------------------

python predator_tier_ladder.py --from T4 --budget 200000


# ---------------------------------------------------------------
# STEP 5 — out-of-distribution track. SEPARATE SESSION.
#          Never merge these numbers with the tier rating.
# ---------------------------------------------------------------

python predator_tier_ladder.py --from X1 --budget 200000


# ---------------------------------------------------------------
# OTHER RUNS
# ---------------------------------------------------------------

python predator_tier_ladder.py --auto --budget 200000   # whole ladder, no pauses
python predator_tier_ladder.py --from T8                # just the discriminator
python predator_tier_ladder.py --from T8 --skip-screen  # UNSOUND: diagnostics only
python predator_tier_ladder.py --help


# ---------------------------------------------------------------
# RESULTS
# ---------------------------------------------------------------

ls runs/                                        # certificates + session logs
cat runs/ladder-*.json                          # raw results
python -m json.tool runs/ladder-*.json          # pretty-printed

# highest genuine pass across every session
python - <<'EOF'
import json, glob
best = 0
for f in glob.glob("runs/ladder-*.json"):
    for r in json.load(open(f)):
        t = r["tier"]
        if (t.startswith("T") and t != "T0"
                and r["outcome"] == "proved" and not r["screened"]):
            best = max(best, int(t[1:]))
print(f"Predator 7.1 is TIER {best}")
EOF
```

**Interactive keys:** `y` proceed · `s` skip · `q` quit (verdict still prints)
