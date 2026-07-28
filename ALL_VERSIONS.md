# Every Predator, head to head

All numbers are from runs on this machine, 2026-07-27/28. Nothing is estimated.

---

## The thing to get straight first

**Most of these versions cannot be compared to each other.** They rank different
objects, on different corpora, measured in different units.

| version | ranks | corpus | metric |
|---|---|---|---|
| Predator_1 | proof-graph nodes | synthetic, 789 stmts | node expansions, wall clock |
| Predator_2 | **lemmas** | set.mm, 8k | recall@k, effort |
| Predator_3 | **lemmas** | set.mm, 2k–32k | recall@k, effort |
| Predator_4 | **lemmas** | set.mm, 50k | recall@k, effort |
| python_rf | **lemmas** | set.mm, 16k | recall@k, effort |
| Predator_5 | **edges** | CD fragment | node expansions vs BFS |
| Predator_6 | **edges** | CD fragment | node expansions vs BFS |
| Predator_6.1 | **edges** | CD fragment | node expansions vs BFS |

Predator_4's "3.5×" is *fraction of the library you must read*. Predator_5's
"1.8×" is *nodes expanded before the target appears*. Putting them in one column
under a heading like "speedup" would be the single most misleading thing this
project could publish.

So: two leagues, judged separately, plus one orphan.

---

## League A — premise selection over set.mm

Same task, same corpus, same metrics. These genuinely race each other.

| version | corpus | recall@10 | recall@50 | MRR | effort | vs brute |
|---|---|---|---|---|---|---|
| Predator_2 (early features) | 8k | 0.160 | 0.333 | 0.436 | 0.3513 | 2.6× |
| Predator_2 (later features) | 8k | 0.232 | 0.491 | 0.479 | 0.3871 | 2.4× |
| Predator_2 (bad feature set) | 8k | 0.059 | 0.147 | 0.159 | 0.7470 | 1.2× |
| Predator_3 | 32k | 0.275 | 0.600 | 0.668 | 0.6417 | 1.5× |
| **Predator_4** | **50k** | **0.419** | **0.730** | **0.885** | **0.2866** | **3.5×** |
| python_rf (forest) | 16k | 0.163 | 0.497 | 0.567 | 0.7007 | 1.4× |

**Predator_4 wins League A, decisively and on every metric.**

Two further findings inside the league:

**Feature choice dominates model choice.** The same Predator_2 code scored
recall@10 of 0.059 and 0.232 depending only on which features were active — a
4× swing, larger than any gap between versions. The bad run's top weights were
`local co-citation −0.94`, `length ratio −0.64`, `log recency −0.41`; the good
run's were `local co-citation +0.586`, `goal covers cand +0.336`. A sign flip on
co-citation cost more than three versions of progress.

**Predator_3's scaling curve was noise; Predator_4's is real.**

```
Predator_3   r@10 at 2k/4k/8k/16k/32k:  0.326  0.253  0.143  0.228  0.275
Predator_4   r@10 at 2k/4k/8k/16k/32k:  0.336  0.412  0.413  0.431  0.414
```

Predator_3's curve is non-monotonic and swings by a factor of 2.3 with no
mechanism to explain it. Predator_4's is flat to ±0.02 from 4k onward. A flat
curve is a real result — performance holds as the library grows — whereas
Predator_3's was measuring variance.

**Linear beats forest, twice.** `python_rf` swapped in a real random forest and
lost on everything: recall@10 0.319 → 0.163, effort 0.2898 → 0.7007, fit time
54.7 s → 350.4 s. Predator_3's forest variant lost the same way (r@10 0.185,
0.063, 0.077). Consistent with Predator_5, where logistic beat forest 34.9 vs
47.0 expansions. Three independent settings agree: **the signal is close to
linear in these features.** That is a fact about the features, not a defect in
the forest.

---

## League B — search policy over the condensed-detachment fragment

Same fragment, same metric, paired over seeds.

| version | what it does | depth 4 | depth 5 |
|---|---|---|---|
| BFS (λ=0) | no policy | 25.6 exp | 75.5 exp |
| **Predator_5** | one pass, certified labels | **15.5 ± 2.6** (1.60×) | **42.3 ± 8.6** (1.78×) |
| Predator_6 | + expert iteration, p=0.7 | indistinguishable | indistinguishable |
| Predator_6.1 | + expert iteration, p=0.9 | indistinguishable | — |

**Predator_5 wins League B on cost, because nothing beats it on quality.**

The p × n sweep, paired over 3 seeds at depth 4, on a held-out set that no
longer moves with p:

```
p     n    d(expansions)      d(solved) verdict
0.50  3            +0.6           +0.0  within noise
0.70  1            +0.0           +0.0  within noise
0.70  3            +0.2           +0.0  within noise
0.90  1            +0.0           +0.0  within noise
0.90  3            -0.5           +0.0  within noise
```

**No setting of p or n beats n=1.** Predator_6.1 (p=0.9, n=3) came in 0.5
expansions faster — against a seed-to-seed standard deviation of 2.6. That is
not a result.

Predator_6 also costs 30–139% more node expansions to reach the same place.

### Why raising p cannot help here

`p` sets how much of the frontier is used for bootstrapping. Enlarging it does
not create anything past the breadth-first horizon, and on this fragment BFS can
price *every* target. The certified labels are already geodesics — optimal by
theorem — so bootstrapped labels can only add upper bounds to a training set
that did not need them. Certified share fell to 22% at depth 5 and 10% at
depth 6.

`p` is not the variable that matters. Having unreachable targets is.

### A retraction

I claimed earlier that expert iteration pays when pass 1 leaves a frontier
unsolved, based on a depth-5 vs depth-6 comparison. Your controlled sweep
refuted it: depth 6 had 35% of its frontier surviving — the most favourable case
the theory allows — and Predator_6 lost there, 22 solved against 24. Depth 4 had
0% surviving and Predator_6 nominally won.

The correlation runs backwards from my claim, and all three differences were
inside the seed noise anyway. The hypothesis is unsupported.

---

## The orphan, and the warning it carries

Predator_1 ran on a synthetic 789-statement corpus and reported:

```
EXPANSIONS   ratio 0.0613  ->  18.1x fewer
WALL CLOCK   brute 0.32s  Predator 0.81s  ->  0.40x   SLOWER
per expansion  brute 21us   Predator 883us   (41x overhead)
break-even     never at this scale
```

**18× fewer expansions and 2.5× slower in wall clock.** The policy cost 41× more
per node than it saved in nodes.

**League B has never measured wall clock.** Predator_5 and Predator_6 report
node expansions only. Predator_5's 1.6–1.8× advantage is smaller than
Predator_1's 18×, and its per-node cost is a feature extraction plus a dot
product on every edge at every state. It is entirely possible that Predator_5 is
slower in seconds than the BFS it beats on nodes, and nobody has checked.

This is a real hole in the headline result and it should be closed before the
number is quoted anywhere. Predator_1 already found the trap once.

---

## Overall standing

1. **Predator_4** — the strongest system in the project. Runs on all of set.mm,
   3.5× effort reduction, recall@10 0.419, scaling curve flat to 50k. Cannot
   prove anything: it ranks and stops.
2. **Predator_5** — the most interesting result. Produces actual proofs,
   preserves proof-covering, 1.6–1.8× fewer expansions than BFS with the gap
   widening as depth grows. Runs on a 287-state toy. Wall clock unmeasured.
3. **Predator_6 / 6.1** — correct implementations of expert iteration with no
   measurable benefit on this fragment. Not wrong; untested where they would
   matter. The case for them is set.mm, where BFS reaches nothing.
4. **Predator_2 / 3** — superseded by Predator_4 on the same task.
5. **Predator_1** — superseded, but its wall-clock finding is the most useful
   negative result in the project and still applies to League B.

---

## Reproduce

```powershell
# League B, paired over seeds, fixed held-out set
python predator6.py versus --depths 4,5,6 --seeds 0,1,2,3,4 -p 0.7 -n 3 --seed-depth 3 --edge-cap 10 --budget 150

# p x n grid, including Predator_6.1 as the p=0.9 cell
python predator6.py sweep --depth 5 --seed-depth 3 --edge-cap 10 --budget 150 --ps 0.5,0.7,0.9 --ns 1,3,5 --seeds 0,1,2,3,4

# League A
python predator4_rf.py train --db set.mm -p 0.9
python python_rf.py compare
```

---

## The next number worth having

Wall clock for League B. Everything else in this document is measured;
Predator_5's headline is measured in the one unit Predator_1 proved can lie.
