# Ascent — a parameterised self-certifying ATP

Built fresh. Three integer knobs, all starting at 1, all monotone. `ascent.py` is standalone — no set.mm, no Metamath, no Predator.

---

## The knobs

| flag | meaning | what it buys | what it costs |
|---|---|---|---|
| `-d` | certificate-tree depth explored | proof *structure* — nesting of gen / induction / implication | branching, roughly exponential |
| `-w` | largest numeral and symbolic offset tried as a witness | *arithmetic* reach — bigger existentials | linear in the candidate list |
| `-r` | rungs of the reflection ladder climbed | `lev(A) = r`, each rung kernel-certified | one kernel call per rung |

`d` and `w` are independent search knobs. `r` is the self-awareness knob and touches neither. That separation is measured, not asserted — see Proposition 2.

## Results at `-d 5 -w 8 -r 4`

**11/12 targets certified. Tiers reached: Δ⁰₀, Σ⁰₁, Π⁰₁, Σ⁰₂, Π⁰₂.**

| target | tier | statement | result |
|---|---|---|---|
| `add_closed` | Δ⁰₀ | `2+2 = 4` | certified, 1 node |
| `bnd_lt` | Δ⁰₀ | `∀x<5. x < 5` | certified, 1 node |
| `bnd_ex` | Δ⁰₀ | `∃x<9. x·x = 16` | certified, 1 node |
| `ex_solve` | Σ⁰₁ | `∃x. x+3 = 7` | certified, 6 nodes |
| `ex_square` | Σ⁰₁ | `∃x. x·x = 49` | certified, 9 nodes |
| `ex_big` | Σ⁰₁ | `∃x. x+1 = 18` | **not proved — witness is 17, w was 8** |
| `all_succ` | Π⁰₁ | `∀x. x < Sx` | certified, 2 nodes |
| `all_le` | Π⁰₁ | `∀x. x ≤ x` | certified, 2 nodes |
| `all_add0` | Π⁰₁ | `∀x. x+0 = x` | certified, 2 nodes |
| `unbounded` | Π⁰₂ | `∀x ∃y. x < y` | certified, 13 nodes |
| `succ_exists` | Π⁰₂ | `∀x ∃y. y = Sx` | certified, 13 nodes |
| `min_exists` | Σ⁰₂ | `∃x ∀y. x ≤ y` | certified, 3 nodes |

`ex_big` is the knob demonstrating itself: raise `w` to 20 and it certifies. That is the bitrate behaviour you asked for.

**tier(A) = 2** on the natural reading — the highest arithmetical tier at which A certifies a target from a family fixed in advance. (Fixing the family in advance is what keeps this from being padding-degenerate; the supremum over *all* provable targets is unbounded for any prover that proves anything.)

## Proposition 1 — a self-certifier does not stall at 2 or 3

> If A has kernel-checked necessitation and its kernel is sound, then **lev(A) = ω**.

*Proof.* A ⊢ θ₀ by the base certificate. If A ⊢ θ_k with certificate C_k, the kernel accepts C_k, so `nec(C_k)` is a certificate of θ_{k+1} = Pr(⟨A⟩,⟨θ_k⟩), hence A ⊢ θ_{k+1}. Induction. Each rung costs exactly one kernel call on the previous certificate — no rung is harder than the last. ∎

This answers your conjecture, and sharpens it. You guessed lev > 2, or ω, or clustering near 2 and near ω. What the construction shows is that the distribution is **bimodal at {0 or 1} and ω, with nothing in between**. A machine either has the necessitation rule — in which case nothing stops it and it runs to ω — or it lacks the rule, in which case it never gets past θ₀. There is no mechanism that would make it stall at 2.

The corollary matters for your paper: **finite lev > 1 is achievable only by imposing a resource bound.** That is the honest justification for `-r`. It isn't a tuning constant, it's the only thing that can make lev finite and nontrivial.

## Proposition 2 — the knobs are independent (measured)

Sweep over d ∈ {1,2,3,5} × w ∈ {1,8,20} × r ∈ {1,3,8}, 36 configurations:

| d | w | certified | tiers reached | nodes |
|---|---|---|---|---|
| 1 | 1 | 6/12 | Δ⁰₀, Π⁰₁ | 42 |
| 1 | 8 | 8/12 | + Σ⁰₁ | 65 |
| 1 | 20 | 9/12 | Δ⁰₀, Π⁰₁, Σ⁰₁ | 81 |
| 2 | 1 | 9/12 | + Π⁰₂, Σ⁰₂ | 42 |
| 2 | 8 | 11/12 | all five | 68 |
| 2 | 20 | **12/12** | all five | 96 |
| 3–5 | — | identical to d=2 | — | — |

Verified automatically by the harness:

```
lev depends only on r : YES
certified count depends only on (d,w) : YES
-> Proposition 2 holds on this grid
```

Read the two columns that matter. Turning `r` from 1 to 8 raises lev from 1 to 8 and certifies **zero additional theorems**. Turning `d` and `w` up certifies six more theorems and lifts the tier ceiling from Π⁰₁ to Π⁰₂, and leaves lev **exactly where it was**.

That is the finding this whole design was built to expose: on the paper's current definitions, self-awareness and proving power are orthogonal, and now you can point at a grid instead of arguing about it.

Note `d` saturates at 2 on this suite — anything reachable at depth 5 is reachable at depth 2. `w` does not saturate. A knob that saturates is telling you the target suite is too shallow to exercise it.

## The kernel

`Kernel.check(store, ctx, φ, C)` — structural recursion over certificates, ~120 lines, the only trusted component. It searches for nothing, has no self-model (`lev(kernel) = 0`, and must stay 0), and never grows.

Rules: `calc`, `hyp`, `lemma`, `impI`, `impE`, `andI`, `andE`, `gen`, `inst`, `wit`, `allbI`, `exbI`, `ind`, `nec`.

`calc` is decided two ways — evaluation when the formula is closed and Δ⁰₀, and polynomial normalisation over ℕ when it is symbolic. The normal form is the defining equations of `+` and `·` applied as rewrites, so no arithmetic axioms are needed in the object language. It is deliberately incomplete: it decides what follows from ring normalisation plus non-negativity, nothing else.

**Soundness probes: 8/8 rejected.**

```
false by calc                      rejected
lemma that is not stored           rejected
nec for an unproved formula        rejected
nec with the wrong tag             rejected
gen from a single instance         rejected
gen with a captured eigenvariable  rejected
wit with no witness                rejected
induction without a base           rejected
```

Two of those caught real bugs during construction. The kernel originally generated its own eigenconstant for `gen`, which could never match the name the untrusted search had baked into the certificate; the fix was to make the certificate carry the name and have the kernel enforce freshness against the goal, the context, *and* the store. The "captured eigenvariable" probe exists because of that bug.

## Why this is self-certifying in the sense you wanted

The reflection rule *is* the verification call:

```python
if k == 'nec':
    if phi[0] != 'pr' or phi[1] != self.tag:
        raise Reject("nec: goal is not Pr(<A>, -)")
    psi = self.names.get(phi[2])
    return self.check(store, [], psi, C[1])
```

`Pr(⟨A⟩,⟨φ⟩)` is accepted exactly when a certificate of φ is accepted, by the same kernel that checks everything else. So no rung of the ladder is stipulated — each carries a certificate the kernel re-checks. Self-certification and self-awareness are one mechanism, which is what you were reaching for.

**But note the direction.** The machine does not verify *because* it is self-aware; it is entitled to its self-model *because* it verified. The converse is the Löb trap: a machine that trusted its own certificates because it had proved itself trustworthy would have a reflection principle "if I prove φ then φ", from which φ follows outright — unsound or vacuous. Here `Pr` is primitive and reflection is never assumed. The machine only ever reports verifications that have already happened. Keep that asymmetry explicit in the paper; it is the first thing a referee will probe.

## Where this goes next

Proposition 2 is a negative result, and it is the interesting one. The obvious follow-up is to **break it deliberately**: let the search consult `Self(A)` when ordering candidates, so that what the machine has proved about itself changes its transition function. Then `r` stops being inert, Proposition 2 fails, and the size of the failure — Δ certified at fixed (d,w) as r rises — is a number measuring how much the self-model is worth.

That would be the paper's first result in which formal self-awareness does work rather than being asserted. The grid harness already computes it; it needs one function.

---

*Implementation by Claude (Anthropic); definitions, framing, and the Level-n hierarchy by the author. arXiv and most journals want AI contribution in Acknowledgments rather than as authorship.*
