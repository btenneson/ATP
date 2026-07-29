# Every Predator, head to head

All numbers are from runs on this machine, 2026-07-27/28. Nothing is estimated.

---

## The thing to get straight first

**Most of these versions cannot be compared to each other.** They rank different
objects, on different corpora, measured in different units.

| version | ranks | corpus | metric |
|---|---|---|---|
| Predator_1 | proof-graph nodes | synthetic, 789 stmts | expansions, wall clock |
| Predator_2 | **lemmas** | set.mm, 8k | recall@k, effort |
| Predator_3 | **lemmas** | set.mm, 2k–32k | recall@k, effort |
| Predator_4 | **lemmas** | set.mm, 50k | recall@k, effort |
| python_rf | **lemmas** | set.mm, 16k | recall@k, effort |
| Predator_5 | **edges** | CD fragment | expansions vs BFS |
| Predator_6 / 6.1 | **edges** | CD fragment | expansions vs BFS |

Predator_4's "3.5×" is *fraction of the library you must read*. Predator_5's
"1.8×" is *nodes expanded before the target appears*. One column headed
"speedup" would be the most misleading thing this project could publish.

Three leagues, judged separately.

---

## League A — premise selection over set.mm

| version | corpus | recall@10 | recall@50 | MRR | effort | vs brute |
|---|---|---|---|---|---|---|
| Predator_2 (early features) | 8k | 0.160 | 0.333 | 0.436 | 0.3513 | 2.6× |
| Predator_2 (later features) | 8k | 0.232 | 0.491 | 0.479 | 0.3871 | 2.4× |
| Predator_2 (bad feature set) | 8k | 0.059 | 0.147 | 0.159 | 0.7470 | 1.2× |
| Predator_3 | 32k | 0.275 | 0.600 | 0.668 | 0.6417 | 1.5× |
| **Predator_4** | **50k** | **0.419** | **0.730** | **0.885** | **0.2866** | **3.5×** |
| python_rf (forest) | 16k | 0.163 | 0.497 | 0.567 | 0.7007 | 1.4× |

**Predator_4 wins League A on every metric.**

**Feature choice dominates model choice.** The same Predator_2 code scored
recall@10 of 0.059 and 0.232 depending only on which features were active — a 4×
swing, larger than any gap between versions. The bad run's top weights were
`local co-citation −0.94`, `length ratio −0.64`; the good run's were `local
co-citation +0.586`, `goal covers cand +0.336`. A sign flip on one feature cost
more than three versions of progress.

**Predator_3's scaling curve was noise; Predator_4's is real.**

```
Predator_3   r@10 at 2k/4k/8k/16k/32k:  0.326  0.253  0.143  0.228  0.275
Predator_4   r@10 at 2k/4k/8k/16k/32k:  0.336  0.412  0.413  0.431  0.414
```

Predator_3 swings by 2.3× with no mechanism. Predator_4 is flat to ±0.02 from 4k
onward — and a flat curve is a real finding: performance holds as the library
grows.

**Linear beats forest, three times.** `python_rf` swapped in a real random
forest and lost everything: recall@10 0.319 → 0.163, effort 0.2898 → 0.7007, fit
time 54.7 s → 350.4 s. Predator_3's forest lost the same way. So did
Predator_5's (47.0 vs 34.9 expansions). Three independent settings agree: **the
signal is close to linear in these features.** A fact about the features, not a
broken forest.

---

## League B — search policy over the condensed-detachment fragment

| version | depth 4 | depth 5 |
|---|---|---|
| BFS (λ=0) | 25.6 exp | 75.5 exp |
| **Predator_5** | **15.5 ± 2.6** (1.60×) | **42.3 ± 8.6** (1.78×) |
| Predator_6 (p=0.7) | indistinguishable | indistinguishable |
| Predator_6.1 (p=0.9) | indistinguishable | — |

p × n sweep, paired over seeds, on a held-out set that no longer moves with p:

```
p     n    d(expansions)   d(solved)   verdict
0.50  3            +0.6         +0.0   within noise
0.70  1            +0.0         +0.0   within noise
0.70  3            +0.2         +0.0   within noise
0.90  1            +0.0         +0.0   within noise
0.90  3            -0.5         +0.0   within noise
```

**No setting of p or n beats n=1.** Predator_6.1 came in 0.5 expansions faster
against a seed-to-seed σ of 2.6. Not a result. Predator_6 also costs 30–139%
more expansions to reach the same place.

Raising p enlarges the frontier but creates nothing past the BFS horizon, and on
this fragment BFS prices *every* target. Certified labels are already geodesics;
bootstrapping can only add upper bounds to a set that did not need them.
Certified share fell to 22% at depth 5, 10% at depth 6.

**A retraction.** I claimed expert iteration pays when pass 1 leaves a frontier,
from a depth-5 vs depth-6 comparison. The controlled sweep refuted it: depth 6
had 35% of its frontier surviving — the most favourable case the theory allows —
and Predator_6 lost there, 22 solved against 24. Depth 4 had 0% surviving and
Predator_6 nominally won. The correlation runs backwards, and all three
differences were inside seed noise anyway.

---

## League C — search strategies, timed in seconds

`arena.py`, depth 5, 30 held-out targets, mean over 5 seeds. Same ranker, same
targets, same split; only the strategy varies. First time Predator_1's beam
search and Predator_5's weighted-A* have shared a benchmark, and first time
League B has been measured in seconds.

| strategy | solved | expansions | seconds | µs/exp | optimal | guarantee |
|---|---|---|---|---|---|---|
| BFS (λ=0) | 100% | 90.0 ± 11.7 | 2.92 | 1083 | 100% | geodesic, complete |
| **weighted-A\* reorder** | **100%** | **42.0 ± 6.7** | **1.66** | 1328 | **99%** | complete |
| A\* prune k=4 | 91% | 77.8 ± 14.0 | 3.48 | 1487 | 91% | INCOMPLETE |
| beam W=8 | 70% | 114.5 ± 27.2 | 19.09 | 5483 | 80% | INCOMPLETE |
| beam W=1 (hill) | 35% | 29.4 ± 2.4 | 4.02 | 4564 | 41% | INCOMPLETE |

Break-even — Predator_1's test applied to each:

| strategy | node speedup | overhead | **real speedup** |
|---|---|---|---|
| **weighted-A\* reorder** | 2.14× | 1.2× | **1.76× faster** |
| A\* prune k=4 | 1.16× | 1.4× | 0.84× slower |
| beam W=8 | 0.79× | 5.1× | **0.15× slower** |
| beam W=1 | 3.06× | 4.2× | 0.73× slower |

### Predator_5 wins in real time

2.14× fewer nodes at 1.2× overhead gives **1.76× faster in seconds**, at 100%
solved, 99% optimal, completeness intact. The worry that its node advantage would
evaporate under timing was reasonable — Predator_1 found exactly that trap — but
it does not happen here.

### Beam search is the worst strategy tested

Predator_1's strategy solved 70%, expanded **more** nodes than plain BFS (114.5
vs 90.0), and finished **6.6× slower in seconds**. Strictly dominated by doing
nothing clever. W=1 solves 35%.

The 5.1× overhead is structural: beam scores every child of every state in a
level, sorts them, then discards most. It pays for scoring it never uses.

### Every incomplete strategy lost

Prune, beam-8 and beam-1 all discard states. All three finished slower than BFS
*and* solved fewer targets. The only strategy that merely reorders won on every
axis.

That is stronger than the theory claims. Proof-covering says discarding costs the
Branch-Covering Theorem; these runs say it also costs time and solve rate. There
was no speed/guarantee trade-off available here — the guarantee was free.

### Why Predator_5 survived where Predator_1 did not

The `µs/exp` column. BFS costs **1083 µs per expansion** here; Predator_1's brute
force cost **21 µs**. Expanding a node on this fragment means trying `D(x,y)` for
every ordered pair with unification and an occurs check, so a 12-feature dot
product is cheap beside it — 1.2× overhead rather than 41×.

The rule, and it is about the domain rather than the policy:

> **A learned policy pays when node expansion is expensive relative to scoring.**

Predator_1's policy may have been fine. Its nodes were too cheap to be worth
avoiding.

Direct consequence for set.mm, now measurable rather than speculative: if
expanding a node there is a cheap index lookup, the ratio moves back toward
Predator_1's regime and the policy stops paying however good it is.

---

## Overall standing

1. **Predator_4** — strongest system in the project. All of set.mm, 3.5% effort
   reduction, recall@10 0.419, flat scaling to 50k. Cannot prove anything: it
   ranks and stops.
2. **Predator_5** — most interesting result, and now the best-evidenced.
   Produces proofs, preserves proof-covering, 2.1× fewer nodes **and 1.76×
   faster in seconds**. Runs on a 287-state toy.
3. **Predator_6 / 6.1** — correct expert iteration, no measurable benefit on
   this fragment. Not wrong; untested where it would matter.
4. **Predator_2 / 3** — superseded by Predator_4 on the same task.
5. **Predator_1** — superseded, and its beam search is now measured as the worst
   strategy available. Its wall-clock warning was the most useful negative
   result in the project, and it is the reason League C exists.

---

## Reproduce

```powershell
python arena.py --depth 5 --edge-cap 12 --budget 400 --seeds 0,1,2,3,4 --out arena.json
python predator6.py versus --depths 4,5,6 --seeds 0,1,2,3,4 -p 0.7 -n 3 --seed-depth 3 --edge-cap 10 --budget 150
python predator6.py sweep --depth 5 --seed-depth 3 --edge-cap 10 --budget 150 --ps 0.5,0.7,0.9 --ns 1,3,5 --seeds 0,1,2,3,4
python predator4_rf.py train --db set.mm -p 0.9
python python_rf.py compare
```

---

## The next number worth having

**Cost per node expansion in set.mm.** League C shows that is what decides
whether a policy pays, and it is currently unknown for the only corpus that
matters.
