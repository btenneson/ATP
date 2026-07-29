# Formalizing "the infinitesimals are equipollent to the reals"

A specification, not a formalization. The mathematics below is complete and
checked. The Metamath is a **proposal** whose syntax must be validated against
set.mm's conventions before anything is written for real.

Read the caveat in §7 before trusting any label name here.

---

## 1. The statement

Let `F` be a nonprincipal ultrafilter on ℕ. Let `*R = R^N / ~F` be the
ultrapower. Let

```
Inf  =  { x ∈ *R  :  ∀ r ∈ R⁺,  |x| <* r* }
```

be the infinitesimals, where `r*` is the image of the real `r` under the
diagonal embedding. Then

```
Inf ≈ R
```

**This is a theorem of ZFC, not a conjecture.** It is provable, no continuum
hypothesis is needed, and it holds for every nonprincipal ultrafilter on ℕ. Any
plan that "dovetails `s` and `¬s` until one settles" is spending half its budget
searching for a proof of a falsehood.

The result is also not sensitive to which ultrafilter is chosen, because the
argument only uses cardinality, never the specific structure of `F`.

---

## 2. The mathematics

### 2.1 Direction one: `R ≼ Inf`

Let `ε = [ n ↦ 1/(n+1) ]`.

**`ε > 0`.** `{ n : 1/(n+1) > 0 } = N ∈ F`, since a filter contains the whole
set.

**`ε` is infinitesimal.** Fix real `r > 0`. Then
`{ n : 1/(n+1) < r } ⊇ { n : n > 1/r − 1 }`, which is cofinite. A nonprincipal
ultrafilter contains every cofinite set — that is exactly what nonprincipality
buys — so the set is in `F`, so `ε <* r*`.

This is the only place nonprincipality is used, and it is essential: over a
principal ultrafilter the ultrapower collapses to `R` and `Inf = {0}`, making
the theorem false.

**The injection.** Define `j : R → Inf` by `j(r) = r* ·* ε`.

- *Lands in `Inf`*: for real `δ > 0`, `|r·ε| <* δ*` because `ε <* (δ/|r|)*`
  when `r ≠ 0`, and `j(0) = 0 ∈ Inf`.
- *Injective*: if `r ≠ s` then `{ n : r = s } = ∅ ∉ F`, so `r* ≠ s*`. `*R` is an
  ordered field (this needs the ultrafilter property, not just filter), so it
  has no zero divisors, and `ε ≠ 0` cancels.

Hence `R ≼ Inf`.

### 2.2 Direction two: `Inf ≼ R`

```
Inf  ⊆  *R                        (by definition)
|*R| ≤ |R^N|                      (quotient map is onto; invert it using AC)
|R^N| = (2^ℵ₀)^ℵ₀ = 2^(ℵ₀·ℵ₀) = 2^ℵ₀ = |R|
```

Hence `Inf ≼ R`.

**A trap worth naming.** One is tempted to say `*R ⊆ P(R^N)` because its
elements are equivalence classes, i.e. sets of functions. That gives
`|*R| ≤ 2^(2^ℵ₀)`, which is far too weak. The bound must come from the
surjection `R^N ↠ *R`, and inverting a surjection needs choice. AC is already in
play — the ultrafilter itself requires it — so this costs nothing new, but it
must be cited rather than glossed.

### 2.3 Conclusion

`R ≼ Inf` and `Inf ≼ R`, so by Schröder–Bernstein, `Inf ≈ R`. ∎

---

## 3. What has to be defined

None of `*R`, `Inf`, or "nonprincipal ultrafilter on ℕ" exists in set.mm today.
Note that `RR*` in set.mm is the **extended reals** `R ∪ {±∞}` — a different
object, and a name collision to avoid.

Each new symbol needs **two** `$a` statements: a syntax constructor and a
definition. Definitions must satisfy set.mm's soundness conditions —
**eliminability** (the new symbol can always be paraphrased away) and
**non-creativity** (it proves no new theorem in the old language).

### 3.1 Nonprincipal ultrafilters on ℕ

set.mm has `UFil` as a class-valued function, so `( UFil \` NN )` should be the
set of ultrafilters on ℕ. Nonprincipal = contains no finite set.

```
  cnpuf     $a class NPUFil $.
  df-npuf   $a |- NPUFil = { f e. ( UFil ` NN ) | ( f i^i Fin ) = (/) } $.
```

Then a nonemptiness lemma is required, and it is where choice enters:

```
  npufn0    |- NPUFil =/= (/)
```

Standard route: the Fréchet filter (cofinite subsets of ℕ) is a filter; every
filter on a set extends to an ultrafilter; the extension of the Fréchet filter
contains no finite set. Search for the extension lemma before assuming its name.

### 3.2 The ultrapower

```
  cur       $a class UPow $.
  df-ur     $a |- ( UPow ` f ) = ( ( RR ^m NN ) /. ( ~UF ` f ) ) $.
```

with the equivalence relation

```
  cufeq     $a class ~UF $.
  df-ufeq   $a |- ( ~UF ` f ) =
                  { <. g , h >. | ( g e. ( RR ^m NN ) /\ h e. ( RR ^m NN ) /\
                                    { n e. NN | ( g ` n ) = ( h ` n ) } e. f ) } $.
```

Obligations: `~UF f` is an equivalence relation on `R^N` (reflexive needs
`NN ∈ f`; symmetric is trivial; transitive needs closure under intersection).

### 3.3 Order, arithmetic, embedding, infinitesimals

```
  ltur      [ g ] <* [ h ]  iff  { n | g(n) < h(n) } ∈ f
  plusur    [ g ] +* [ h ]  =    [ n ↦ g(n) + h(n) ]
  timesur   [ g ] ·* [ h ]  =    [ n ↦ g(n) · h(n) ]
  starr     r*              =    [ n ↦ r ]
```

Every one needs a well-definedness lemma: independent of representatives. Those
proofs are short and numerous, and they are the bulk of the work.

```
  cinf      $a class Infml $.
  df-inf    $a |- ( Infml ` f ) =
                  { x e. ( UPow ` f ) | A. r e. RR+ ( abs* ` x ) <* ( starr ` r ) } $.
```

---

## 4. Proof skeleton, with what each step needs

| # | step | needs |
|---|---|---|
| 1 | `NPUFil ≠ ∅` | Fréchet filter is a filter; filter extends to ultrafilter; AC |
| 2 | `~UF f` is an equivalence relation on `R^N` | filter closure properties |
| 3 | `UPow f` is a set | quotient of a set is a set |
| 4 | `<*` is well defined and totally orders `UPow f` | **ultrafilter** property, not merely filter |
| 5 | `UPow f` is an ordered field | well-definedness of `+*`, `·*`; no zero divisors |
| 6 | `starr` is an injective field embedding `R → UPow f` | `{n : r = s} = ∅ ∉ f` |
| 7 | `ε = [n ↦ 1/(n+1)]` is a positive infinitesimal | nonprincipal ⟹ cofinite sets ∈ f |
| 8 | `j(r) = starr(r) ·* ε` maps `R` into `Infml f` | step 7 + field arithmetic |
| 9 | `j` is injective | step 5 (no zero divisors) + step 6 |
| 10 | **`R ≼ Infml f`** | steps 8, 9 + definition of `≼` |
| 11 | `Infml f ⊆ UPow f`, so `Infml f ≼ UPow f` | subset dominance |
| 12 | `UPow f ≼ R^N` | surjection `R^N ↠ UPow f`, inverted with AC |
| 13 | `R^N ≈ R` | `rpnnen` + map cardinality + `N × N ≈ N` |
| 14 | **`Infml f ≼ R`** | 11, 12, 13, transitivity of `≼` |
| 15 | **`Infml f ≈ R`** | 10, 14, `sbth` |

Steps 10, 14 and 15 are three statements. Steps 1–9 are the formalization
project.

---

## 5. Inventory what already exists — run these

`metamath.py` now has a `search` command. **Do this before writing any
Metamath**, because I have twice in this project asserted label names that were
wrong.

```powershell
python metamath.py search --prefix sbth
python metamath.py search "~<_" "~~" --logical-only --limit 20
python metamath.py search --prefix rpnnen
python metamath.py search --prefix df-ufil
python metamath.py search --prefix df-fil
python metamath.py search "UFil" --logical-only --limit 40
python metamath.py search --prefix ax-ac
python metamath.py search "^m" "~~" --logical-only --limit 40
python metamath.py search --prefix df-qs
python metamath.py search --prefix df-ec
python metamath.py search "Fin" "(/)" --logical-only --limit 30
```

The one confirmed so far, from your own run:

```
sbth   |- ( ( A ~<_ B /\ B ~<_ A ) -> A ~~ B )     638 steps, verifies OK
```

For each hit, confirm it says what you expect:

```powershell
python metamath.py show set.mm <label>
```

Three questions the inventory has to answer:

1. **Does set.mm have "every filter extends to an ultrafilter"?** Step 1 depends
   on it. If absent, that is a sub-project of its own.
2. **What is the cleanest route to `R^N ≈ R`?** Step 13. Some combination of
   `rpnnen` and the map-cardinality lemmas; find the exact chain rather than
   reconstructing it.
3. **What are the quotient-structure conventions?** `/.` and `df-qs` are the
   likely spellings, but confirm the argument order.

---

## 6. Scope

Steps 1–9 are a genuine formalization project: an ordered-field structure built
from scratch, with a well-definedness lemma for every operation. Comparable
efforts elsewhere run to hundreds of lemmas.

My estimate is **500–1500 set.mm statements**, and I want to be clear that it is
an estimate from the shape of the work, not from having done it. The
well-definedness obligations in steps 4–6 dominate; each is individually easy
and there are many.

Steps 10–15, once 1–9 exist, are short.

---

## 7. Caveat, and why it is here

Everything in §3 is a **sketch**. The set.mm syntax for class abstraction,
quotient structures, and function-valued definitions has conventions I have not
verified, and definitional soundness review is a real gate in set.mm, not a
formality.

I am flagging this loudly because of what already happened twice in this
project. `setmm_parser.py` produced 43,000 theorems all named `|-` and looked
entirely plausible. The disjoint-variable check in `metamath.py` rejected five
correct proofs on its first contact with real data. Both were caught only by
running against ground truth.

A 300-line block of confident-looking Metamath that does not typecheck is the
same failure at larger scale. The mathematics in §2 is solid and you can build
on it. The Metamath in §3 is a starting point to be checked against the corpus,
one definition at a time, with `metamath.py verify` run after each.

---

## 8. Next action

Run the searches in §5 and paste the output. That inventory decides whether step
1 is one lemma or a sub-project, and it is the difference between a plan and a
guess.
