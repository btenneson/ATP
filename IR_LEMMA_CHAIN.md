# |I| = |ℝ| — a complete lemma chain

The infinitesimals of a nonprincipal ultrapower of ℝ are equinumerous with ℝ.

Seventeen lemmas with proofs. Small enough that every quantity below — closure
depth, proof length, the breadth ratio — can be checked by hand, which is the
point: it is a test of the framework, not of a corpus.

---

## Notation and standing hypotheses

`ℕ₀` is the nonnegative integers. `F` is a nonprincipal ultrafilter on `ℕ₀`,
where **nonprincipal** means `F` contains no finite set.

`ℝ^ℕ₀` is the set of all functions `ℕ₀ → ℝ`. For `z, w ∈ ℝ^ℕ₀`,

```
z ~F w    iff    { m ∈ ℕ₀ : z(m) = w(m) } ∈ F
```

`*ℝ = ℝ^ℕ₀ / ~F`, and `[z]` is the class of `z`. Then

```
I  =  { [z] ∈ *ℝ  :  ∀ r ∈ ℝ⁺,  { m ∈ ℕ₀ : |z(m)| < r } ∈ F }
```

**The condition quantifies over positive real constants `r`, not over
sequences.** Quantifying over sequences `x` with `{m : |z(m)| < |x(m)|} ∈ F`
makes `I` empty: take `x = z` and the set is `∅`, which lies in no filter.
Infinitesimal means *smaller than every standard positive real*.

`Γ` — the background assumed without proof — is ZF, the axiom of choice, the
archimedean property of ℝ, `|ℝ| = 2^ℵ⁰`, and Schröder–Bernstein.

---

## The simplification worth seeing before you start

**This proof never uses field structure on `*ℝ`.** No addition, no
multiplication, no order on the quotient. Only the quotient *set* and cardinal
arithmetic.

The textbook route sets `j(r) = r* · ε` and so needs `*ℝ` to be an ordered
field: well-definedness of `+`, `·` and `<` on classes, absence of zero
divisors, the diagonal embedding. Defining `j(r) = [⟨r/(m+1)⟩]` directly reaches
the same injection with none of it — perhaps two hundred fewer statements in any
formalization.

---

## Part 0 — the construction

### L1. A nonprincipal ultrafilter on ℕ₀ exists.

*Uses:* Γ (AC).

Let `Fr = { A ⊆ ℕ₀ : ℕ₀ ∖ A is finite }`, the Fréchet filter. It is a filter:
`ℕ₀ ∈ Fr`; `∅ ∉ Fr` because `ℕ₀` is infinite; it is closed upward, and closed
under finite intersection because a finite union of finite sets is finite.

Order the filters containing `Fr` by inclusion. Every chain has an upper bound —
its union, which is a filter because any two members of the union lie in a
common element of the chain. By Zorn's lemma there is a maximal such filter `F`,
and a maximal filter is an ultrafilter.

`F` is nonprincipal: if a finite `A ∈ F`, then `ℕ₀ ∖ A` is cofinite, so
`ℕ₀ ∖ A ∈ Fr ⊆ F`, so `∅ = A ∩ (ℕ₀ ∖ A) ∈ F`, contradiction. ∎

### L2. Every cofinite subset of ℕ₀ belongs to F.

*Uses:* L1.

Let `A` be cofinite and suppose `A ∉ F`. Since `F` is an ultrafilter,
`ℕ₀ ∖ A ∈ F`. But `ℕ₀ ∖ A` is finite, contradicting nonprincipality. ∎

> **This is the only consequence of nonprincipality the argument uses.** It
> feeds L7 and L8 and nothing else. Over a *principal* ultrafilter the
> ultrapower collapses to ℝ and `I = {0}`, so the theorem is false — if your
> written proof never appeals to L2, the proof is wrong.

### L3. ~F is an equivalence relation on ℝ^ℕ₀.

*Uses:* L1.

*Reflexive:* `{m : z(m) = z(m)} = ℕ₀ ∈ F`.
*Symmetric:* the defining set is unchanged under swapping `z, w`.
*Transitive:* `{m : z(m)=w(m)} ∩ {m : w(m)=v(m)} ⊆ {m : z(m)=v(m)}`. The left
side is in `F` by closure under intersection, so the right side is by upward
closure. ∎

### L4. \*ℝ is a set.

*Uses:* L3.

`ℝ^ℕ₀` is a set. Each class `[z] ⊆ ℝ^ℕ₀`, so `*ℝ ⊆ 𝒫(ℝ^ℕ₀)`, and `*ℝ` is a set
by power set and separation. ∎

### L5. The condition defining I is ~F-invariant, so I is well defined.

*Uses:* L3.

Suppose `z ~F w` and `z` satisfies the condition. Fix `r ∈ ℝ⁺`. Put
`E = {m : z(m)=w(m)} ∈ F` and `Z = {m : |z(m)| < r} ∈ F`. Then `E ∩ Z ∈ F`, and
`E ∩ Z ⊆ {m : |w(m)| < r}`, so that set is in `F` by upward closure. ∎

---

## Part 1 — ℝ ≼ I

### L6. For every r ∈ ℝ⁺, `{ m ∈ ℕ₀ : 1/(m+1) < r }` is cofinite.

*Uses:* Γ (archimedean).

`1/(m+1) < r ⟺ m + 1 > 1/r ⟺ m > 1/r − 1`. By the archimedean property choose
`N ∈ ℕ₀` with `N > 1/r − 1`. The set contains every `m ≥ N`, so its complement
is contained in `{0, …, N−1}` and is finite. ∎

### L7. ε := [⟨1/(m+1) : m ∈ ℕ₀⟩] ∈ I, and ε ≠ 0.

*Uses:* L2, L6.

For `r ∈ ℝ⁺`, `|1/(m+1)| = 1/(m+1)`, so by L6 the set `{m : |1/(m+1)| < r}` is
cofinite and by L2 lies in `F`. Hence `ε ∈ I`. It is nonzero because
`{m : 1/(m+1) = 0} = ∅ ∉ F`. ∎

> **L7 is expository, not load-bearing.** L8 proves what is needed directly, and
> the dependency graph below confirms L7 is not an ancestor of L17. It is kept
> because it names the witness that makes the theorem plausible.

### L8. For r ∈ ℝ define j(r) := [⟨ r/(m+1) : m ∈ ℕ₀ ⟩]. Then j(r) ∈ I.

*Uses:* L2, L6.

If `r = 0` the sequence is constantly `0`, and for any `s ∈ ℝ⁺`,
`{m : |0| < s} = ℕ₀ ∈ F`.

If `r ≠ 0`, fix `s ∈ ℝ⁺`. Then `|r/(m+1)| < s ⟺ 1/(m+1) < s/|r|`, and
`s/|r| ∈ ℝ⁺`, so by L6 the set is cofinite and by L2 lies in `F`. ∎

### L9. j is injective.

*Uses:* L1.

Let `r ≠ s`. For every `m`, `m+1 ≠ 0`, so `r/(m+1) ≠ s/(m+1)`. Hence
`{m : r/(m+1) = s/(m+1)} = ∅`, and `∅ ∉ F` since `F` is a filter. So the two
sequences are not `~F`-equivalent and `j(r) ≠ j(s)`. ∎

### L10. ℝ ≼ I.

*Uses:* L8, L9. `j : ℝ → I` is injective. ∎

---

## Part 2 — I ≼ ℝ

### L11. I ≼ \*ℝ.

*Uses:* L4, L5. `I ⊆ *ℝ` by definition, and inclusion is injective. ∎

### L12. The quotient map q : ℝ^ℕ₀ → \*ℝ, q(z) = [z], is surjective.

*Uses:* L4. Every element of `*ℝ` is by definition `[z]` for some `z`. ∎

### L13. \*ℝ ≼ ℝ^ℕ₀.

*Uses:* L12, Γ (AC).

The classes form a family of nonempty sets. By AC choose
`s : *ℝ → ℝ^ℕ₀` with `s(x) ∈ x`, so `q(s(x)) = x`. Then `s` is injective, since
`s(x) = s(y)` gives `x = q(s(x)) = q(s(y)) = y`. ∎

> **The tempting shortcut fails.** Each class is a *subset* of `ℝ^ℕ₀`, so
> `*ℝ ⊆ 𝒫(ℝ^ℕ₀)` and `|*ℝ| ≤ 2^(2^ℵ⁰)` — far too weak. The bound must come from
> inverting the surjection, which is where choice enters.

### L14. |ℝ| = 2^ℵ⁰.

*Uses:* Γ. ∎

### L15. |ℝ^ℕ₀| = |ℝ|.

*Uses:* L14.

`|ℝ^ℕ₀| = |ℝ|^ℵ⁰ = (2^ℵ⁰)^ℵ⁰ = 2^(ℵ⁰·ℵ⁰) = 2^ℵ⁰ = |ℝ|`, using `ℵ⁰·ℵ⁰ = ℵ⁰`,
i.e. `ℕ × ℕ ≈ ℕ`. ∎

### L16. I ≼ ℝ.

*Uses:* L11, L13, L15. Compose: `I ≼ *ℝ ≼ ℝ^ℕ₀ ≈ ℝ`, and `≼` is transitive. ∎

---

## Part 3 — conclusion

### L17. I ≈ ℝ.

*Uses:* L10, L16, Γ (Schröder–Bernstein).

`ℝ ≼ I` by L10 and `I ≼ ℝ` by L16, so `I ≈ ℝ`. ∎

---

## The dependency graph

```
L1  ←                      L2  ← L1               L3  ← L1
L4  ← L3                   L5  ← L3               L6  ←
L7  ← L2, L6               L8  ← L2, L6           L9  ← L1
L10 ← L8, L9               L11 ← L4, L5           L12 ← L4
L13 ← L12                  L14 ←                  L15 ← L14
L16 ← L11, L13, L15        L17 ← L10, L16
```

### Closure depth, computed by hand

`δ(φ) = 0` for a lemma with no premises in the graph; otherwise
`δ(φ) = 1 + max{ δ(ψ) : ψ a premise of φ }`.

| | | | | | |
|---|---|---|---|---|---|
| δ(L1)=0 | δ(L6)=0 | δ(L14)=0 | δ(L2)=1 | δ(L3)=1 | δ(L9)=1 |
| δ(L15)=1 | δ(L4)=2 | δ(L5)=2 | δ(L7)=2 | δ(L8)=2 | δ(L10)=3 |
| δ(L11)=3 | δ(L12)=3 | δ(L13)=4 | δ(L16)=5 | **δ(L17)=6** | |

### Proof length

The ancestors of L17 are L1–L6 and L8–L16 — **fifteen** lemmas. L7 is *not*
among them. So

```
‖L17‖ = |ancestors| + 1 = 16
```

### The proposition, checked

```
δ_F(Γ, L17) + 1  =  6 + 1  =  7   ≤   16  =  ‖L17‖_F(Γ)        ✓
```

A slack of 9. The bound holds with room, which is what one expects when the
graph is wide rather than a chain: closure depth counts *rounds*, and L1–L6
fire in parallel while a linear proof must list all sixteen.

---

## Where the hypotheses are used

**Choice** — L1 and L13 only. Nowhere else. Worth tracking; it is exactly the
sort of thing that gets used silently and then misreported.

**Nonprincipality** — L2 only, feeding L7 and L8.

**Archimedean** — L6 only.

**Schröder–Bernstein** — L17 only.

Four hypotheses, each entering at one place. That concentration is itself
evidence the decomposition is right.

---

## What to do with it

The chain is a **labeled theorem graph** — the structure `ml_sic_atp.py` already
consumes. Encode the seventeen nodes with the dependencies above and run it. It
should reproduce δ(L17) = 6 and ‖L17‖ = 16; if it does not, either the encoding
or the tool is wrong, and at seventeen nodes you can find out which by
inspection.

That is the value of a small example: **every number has a known answer.**

Then the breadth ratio `|p_m| / |D_F^(m−1)(Γ)|` measures how much of the closure
an ancestor-only search touches — on this graph, 16 of 17, since only L7 is
unused. A wide, shallow graph is the case where focusing buys least, and saying
so honestly is stronger than reporting a favourable number from a generated
corpus.

---

## Formalization targets, once the chain is written

**Lean / mathlib** — verify yourself whether `Filter.Germ`, `hyperfilter`,
`Hyperreal` and `Infinitesimal` exist. If they do, L1–L5 are already done and
only Parts 1–3 remain. Days.

**set.mm** — L1–L5 must be built from `df-fil`, `df-ufil`, `df-qs`, `ax-ac`,
with four new definitions through eliminability and non-creativity review.
Months.

Either way, this chain is what you formalize *from*.
