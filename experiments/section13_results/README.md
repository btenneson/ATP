# Section 13 cross-branch reuse pilot

Date: 2026-08-14

This directory contains a first empirical attempt to answer Problem 13.1 in *Predator 7.1 Documentation and Cross-Branch Reuse Rate Theory*: measure the cross-branch use rate `kappa_us` for a real proof-search policy on the real `set.mm` corpus.

## Protocol used

The run used one chronological `set.mm` prefix per target and two branch-local backward-search frontiers. Branch A pursued `c`; branch B pursued `not c`; one frontier expansion was alternated at a time. Metavariable/substitution namespaces were kept separate between A and B. Whenever a completed proof subtree became free of search metavariables, its conclusion was placed in a shared lemma bank. The other branch could use that lemma as a nullary compiled rule. Direct one-step closer cases were filtered before target admission to reduce duplicate/lookup contamination.

Pilot settings were deliberately small: two targets, 1,500 total alternating stages per target, maximum search depth 6, maximum 5 open goals, and 12 opener assertions per selected goal. The current `set.mm` downloaded by the workflow contained 47,672 theorems; 41 candidate negative theorems occurred in the first 5,000 scanned theorems before the direct-closer filter.

## Result

| target | shared lemmas | use-crossed | kappa_us | available-crossed | settled? |
|---|---:|---:|---:|---:|---|
| `notnoti` | 118 | 32 | 0.271186 | 118 | no, budget ended |
| `pm2.01i` | 209 | 50 | 0.239234 | 209 | no, budget ended |
| **pooled** | **327** | **82** | **0.250765** | **327** | **0/2** |

Thus the first pilot estimate is

`pooled kappa_us = 82 / 327 = 0.2507645...`

and `kappa_av = 1.0` on these two tiny early-corpus instances.

This is evidence against the degenerate empirical hypothesis `kappa_us = 0` for this particular pilot controller and these targets: the false-side/other branch did in fact produce lemmas that were consumed across the branch boundary. It is **not** yet evidence for a settlement speedup, because neither target settled inside the deliberately small stage budget. Hence the settlement dividend `Delta(c)` was not measured here.

## Important limitations

1. This is a pilot controller modeled on the documented Predator 7.1 search shape, not a byte-for-byte execution of the historical `predator71.py` binary.
2. Dynamically deposited derived lemmas are generated from verifier-backed source assertions, but the pilot does not yet export and independently replay each dynamic derived lemma as a standalone Metamath certificate. A stricter certified replication should add that gate before calling the number final.
3. The sample has only two targets and both are early, two-logical-step negative theorems. The estimate is therefore descriptive, not a corpus-wide estimate.
4. `kappa_us > 0` is necessary for a positive reuse dividend in the paper's Theorem 11.1 framework, but it is not sufficient. A separate shared-vs-independent matched race is needed to estimate `Delta(c)`.

## Files

- `section13_kappa_results.json` -- full machine-readable summary.
- `section13_kappa_rows.csv` -- one row per measured target.
- `../section13_cross_branch_reuse.py` -- experiment implementation.

The natural next experiment is a frozen target set with the same controller and budget run twice: shared bank ON versus OFF, with every deposited lemma independently certificate-checked. That would estimate both `kappa_us` and the actual settlement dividend under one controlled protocol.
