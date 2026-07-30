# Length, Not Height

### On proof-length lower bounds, the MU argument, and whether a self-aware theorem prover could ever settle a Clay problem

---

## Abstract

We distinguish two obstructions standing between an automated theorem prover and a Millennium Prize Problem, and argue that they are almost always confused. The first is *height*: the arithmetical tier of the target, measured by alternations of unbounded quantifiers over ℕ. The second is *length*: the size of the shortest proof of the target from the axioms, written ‖·‖. We exhibit a working prover, Ascent, whose certified targets reach Π⁰₂ and Σ⁰₂ — exactly the tier of "P ≠ NP" — and which is nonetheless hopeless on that target. Tier is therefore not the binding constraint, and we argue that lower bounds on ‖P ≠ NP‖ are the quantity worth pursuing, because a sufficiently large one would retire mechanized search as a strategy without settling the mathematics either way. We then observe that the standard escape from a length lower bound is to leave the system, and take Hofstadter's MU puzzle as the cleanest instance: MU is shown to be underivable in MIU by an argument that uses arithmetic MIU cannot express. We formalize this as a *lift–attack–return* schema, note that the complexity-theoretic barrier results are instances of it at scale, and identify its automatable core as finite-invariant search. Finally we ask whether formal self-awareness helps. Using Ascent, whose reflection ladder is certified rung by rung by its own kernel, we report a negative result: level and proving power are independent parameters, and raising lev(Ascent) from 1 to 8 certifies exactly zero additional theorems. We close by proposing *reflective adequacy* — a machine that can quote its own inference rules and prove invariance lemmas about them — as the notion of self-reference that the MU argument actually requires, in place of the reflection ladder, which it does not.

---

## 1. Introduction

Seven problems were named in 2000, and one has been settled. The remaining six are the most conspicuous fixed points in contemporary mathematics, and their persistence invites a recurring fantasy: that the difficulty is one of bookkeeping, that the required argument is long rather than deep, and that a sufficiently patient machine will eventually assemble it.

The fantasy is most acute for P versus NP. Unlike the Hodge conjecture or the Yang–Mills mass gap, P vs NP is a statement about finite objects — Turing machines, running times, strings. There is no manifold to construct, no measure to define, no analytic continuation to justify. It is, in the most literal sense, a combinatorial question about programs, and combinatorial questions about programs are the kind of thing a computer might be thought to be good at.

This note argues that the instinct is right about the *shape* of the problem and wrong about the *obstruction*. To make the argument precise we need two measures.

**Height.** The arithmetical tier of a sentence is the number of alternations of unbounded quantifiers over ℕ in its prenex form, with bounded quantifiers costing nothing. A Σ⁰₁ sentence asserts the existence of a witness; a Π⁰₁ sentence asserts that a decidable property holds everywhere; Π⁰₂ asserts that for every input some witness exists. Tier measures how much unbounded search is built into the *statement*, and nothing else.

**Length.** For a sentence L and a formal system F, write ‖L‖_F for the number of symbols in the shortest F-proof of L from the axioms of F. This is a property of the theorem–system pair. It is finite exactly when L is a theorem, and it says nothing at all about how hard the proof is to find, only how big it is once found.

These are independent. A tier-0 sentence can have astronomically long proofs; a Π⁰₂ sentence can have a three-line proof. Confusing them produces both of the standard errors: believing that P vs NP is hard *because* it quantifies over all machines, and believing that a prover competent at Π⁰₂ arithmetic is therefore in the neighbourhood of the problem.

Section 2 argues that length is the obstruction that matters and that lower bounds on it are worth having. Section 3 places the Clay problems and Ascent on the tier scale, and finds them at the same height. Section 4 turns to the MU puzzle. Sections 5 and 6 ask whether the MU manoeuvre is mechanizable, and whether self-awareness has anything to contribute.

---

## 2. Why ‖P ≠ NP‖ is the quantity to bound

Suppose someone proved that every ZFC proof of "P ≠ NP" has length at least 10^100 symbols. Nothing about the truth of P ≠ NP would follow. Nothing about human prospects would follow either, for reasons we come to shortly. But something decisive would follow about machines: **no search procedure will ever produce that proof**, because the object being searched for does not fit in the physical universe. This conclusion is immune to every improvement in heuristics, hardware, learned premise selection, and parallelism, because it is a statement about the target rather than about the method.

That immunity is what makes length lower bounds worth more than they might first appear. The known barriers in complexity theory — relativization, natural proofs, algebrization — are all barriers to *techniques*. Each says that a class of arguments cannot work, and each has been circumvented at least partially by arguments outside the class. A length lower bound has no such escape hatch within the fixed system. It would settle, once, whether mechanized proof search is a reasonable thing to spend a century on.

Three further observations.

**First, we cannot currently prove such bounds, and this is itself the central open problem of proof complexity.** Superpolynomial lower bounds are known for weak systems — resolution, bounded-depth Frege — on specific families such as the pigeonhole principle. For Frege systems, let alone for ZFC, essentially nothing is known. The general question is equivalent to a statement about NP and coNP: there is a polynomially bounded proof system for the tautologies if and only if NP = coNP. So the request "bound ‖P ≠ NP‖ from below" is not a detour around P vs NP; it is a close relative of it. This is uncomfortable but not fatal, because *conditional* and *heuristic* bounds would already be informative. A bound conditional on plausible cryptographic assumptions, or an empirically calibrated growth law for proof length against theorem depth in a large formal library, would each tell us something actionable.

**Second, the bound is system-relative, and that is the loophole.** ‖L‖_F depends on F. Enlarging F can shorten proofs catastrophically — not by a constant, but by an exponential. The cleanest instance is the relationship between Frege and extended Frege systems: the extension rule permits the introduction of new variables abbreviating compound formulas, which is to say it permits *definitions*, and definitions are conservative — they prove no new theorems in the old language — while potentially collapsing proof length by an exponential factor.

This is worth stating plainly because it is the whole of the optimism available here. **A large lower bound on ‖L‖_F is not a verdict on L. It is a verdict on F.** The productive response to a length lower bound has never been to search harder. It has been to change the system: introduce a definition, find the right abstraction, move to a setting where the statement becomes short.

**Third, that response is exactly what machines are worst at and humans are best at.** Which raises the question the rest of this note is about: is the move mechanizable at all?

---

## 3. Where the Clay problems sit, and where Ascent sits

The following places the Millennium Problems on the arithmetical scale. Confidence varies sharply across the rows and is marked.

| Problem | Tier | Confidence |
|---|---|---|
| Riemann Hypothesis | **Π⁰₁** | High. RH is equivalent to explicitly Π⁰₁ arithmetic statements — for instance, bounds of the Robin/Lagarias type on the sum-of-divisors function, whose failure would be witnessed by a single integer. |
| P vs NP | **Σ⁰₂ / Π⁰₂** | High. "P = NP" is ∃e ∃k ∀x [machine e decides SAT on x within \|x\|^k + k steps], one ∃-block over one ∀-block with a decidable matrix. "P ≠ NP" is its negation, Π⁰₂. Note it is only known to be *in* Π⁰₂; it is not known to be Π⁰₂-complete. |
| Poincaré conjecture | arithmetical, level delicate | Moderate. Closed 3-manifolds are finitely triangulable, so the domain is countable and codeable, but simple-connectivity is not decidable from a triangulation, which pushes the statement above Π⁰₁. Now moot. |
| Birch–Swinnerton-Dyer | arithmetical, ≥ tier 2 | Low. Elliptic curves over ℚ are codeable and the algebraic rank is arithmetically definable, but the analytic rank is an order of vanishing of an L-function, and pinning it from both sides costs alternations. |
| Hodge conjecture | analytical, prima facie above Σ¹₀ | Low. Quantifies over projective complex varieties and Hodge classes. Whether it descends to the arithmetical hierarchy is not obvious. |
| Navier–Stokes | analytical, prima facie Π¹₂ | Low. Quantifies over smooth initial data — real functions — and asserts global smooth existence. Computable-analysis reductions may lower this. |
| Yang–Mills mass gap | analytical | Moderate. Asserts the *existence* of a quantum field theory satisfying a list of axioms, with a spectral condition. This is a second-order existence claim and is the highest of the seven. |

Two features of the table matter here.

**Riemann is the lowest.** A Π⁰₁ statement is refutable by a single counterexample and is, in the technical sense, the simplest kind of open conjecture there is — the same shape as Goldbach, and as the consistency of PA. Its difficulty has nothing to do with its tier.

**P vs NP is tier 2.** Which brings us to the prover.

**tier(Ascent) = 2.** Ascent is a small self-certifying prover described in Appendix B. Its language is arithmetic with unbounded quantifiers over ℕ, its kernel decides Δ⁰₀ facts by evaluation and symbolic facts by polynomial normalisation over ℕ, and its search combines witness enumeration, generalisation over eigenconstants, and induction. On a twelve-target suite it certifies:

| target | tier | result |
|---|---|---|
| `2+2 = 4` | Δ⁰₀ | certified |
| `∀x<5. x < 5` | Δ⁰₀ | certified |
| `∃x<9. x·x = 16` | Δ⁰₀ | certified |
| `∃x. x+3 = 7` | Σ⁰₁ | certified |
| `∃x. x·x = 49` | Σ⁰₁ | certified |
| `∃x. x+1 = 18` | Σ⁰₁ | certified (needs w ≥ 17) |
| `∀x. x < Sx` | Π⁰₁ | certified |
| `∀x. x ≤ x` | Π⁰₁ | certified |
| `∀x. x+0 = x` | Π⁰₁ | certified |
| `∀x ∃y. x < y` | **Π⁰₂** | certified |
| `∀x ∃y. y = Sx` | **Π⁰₂** | certified |
| `∃x ∀y. x ≤ y` | **Σ⁰₂** | certified |

12/12 at parameters d = 2, w = 20. Every certificate is checked by an independent kernel; a battery of eight deliberately malformed certificates is rejected 8/8.

So Ascent operates at exactly the arithmetical tier of P ≠ NP, and stands at a height *above* the Riemann Hypothesis. It will never prove either. The distance is not height. Ascent's largest certificate on this suite has thirteen nodes; ‖P ≠ NP‖_ZFC, whatever it is, is not thirteen.

This is the point of building the thing. A prover that reaches tier 2 is easy — the appendix is under a thousand lines. Tier is cheap. Length is not.

---

## 4. The MU argument

Hofstadter's MIU system has one axiom and four rules. The axiom is the string **MI**. The rules, with *x* and *y* ranging over strings:

1. *x***I** → *x***IU**
2. **M***x* → **M***xx*
3. *x***III***y* → *x***U***y*
4. *x***UU***y* → *xy*

Is **MU** a theorem?

No, and here is the proof. Let #I(*s*) be the number of I's in *s*. We claim #I(*s*) ≢ 0 (mod 3) for every theorem *s*.

- The axiom **MI** has #I = 1, and 1 ≢ 0.
- Rule 1 appends a U and leaves #I unchanged.
- Rule 2 doubles #I. If #I ≢ 0 (mod 3) then 2·#I ≢ 0 (mod 3), since 3 is prime and 2 ≢ 0.
- Rule 3 removes exactly three I's, leaving #I unchanged modulo 3.
- Rule 4 removes two U's and leaves #I unchanged.

By induction on derivations, every theorem has #I ≢ 0 (mod 3). But #I(**MU**) = 0, and 0 ≡ 0. Therefore **MU** is not a theorem. ∎

Now consider what that argument *is*.

It uses the number three. It uses divisibility. It uses induction over derivations. It uses the primality of 3 in the step for Rule 2. **None of these exist in MIU.** MIU has no numerals, no arithmetic, no notion of quantity, no negation, and no predicate for theoremhood. The sentence "MU is not a theorem" is not merely unproved in MIU; it is not expressible in MIU.

So the argument has three phases:

1. **Lift.** Map MIU-strings into a structure MIU knows nothing about — here, the additive group ℤ/3, via *s* ↦ #I(*s*) mod 3. The four rules become maps on ℤ/3, and each fixes the property "≠ 0".
2. **Attack.** Prove the invariance in the new setting. This is arithmetic, not string rewriting.
3. **Return.** Transfer the conclusion back as a *metatheorem about* MIU: the derivable strings all lie in a set that excludes MU.

The conclusion lands outside the object system, and that is not a defect. It is the only place such a conclusion can live.

The creative act is entirely in phase 1. Nothing in the MIU rules suggests counting I's, and nothing suggests reducing modulo 3. Once the invariant is proposed, phases 2 and 3 are routine — a competent undergraduate, or a competent program, can finish. **The difficulty of the MU argument is concentrated in the choice of the alternative system.**

---

## 5. Can a machine lift, attack, and return?

Sometimes, and more often than one expects.

**The MU case is mechanizable today.** The invariant #I mod 3 is a homomorphism from the free monoid on {M, I, U} to ℤ/3 under which all four rules are compatible and the axiom's image avoids the target's. Finding such a thing is a *finite model search*: enumerate small finite structures, check whether the axiom's image and the rules' action separate the target. Existing finite model finders do this routinely, and the search space for "quotients of size ≤ 5" is tiny. Given the MIU rules as input, a machine would find ℤ/3 in milliseconds. The MU puzzle is famous for being surprising to humans, not for being computationally deep.

This generalizes. **Unprovability by finite invariant is the most automatable form of unprovability argument we have**, precisely because the "alternative but relevant axioms" of phase 1 form a finite structure, and finite structures can be enumerated in order of size. Whenever the reason a target fails is that some small quotient separates it, a machine will find that quotient before a human finishes reading the problem statement.

**The barrier results are lift–attack–return at scale.** This is the observation that makes the schema more than a curiosity. Consider relativization. One wants to show that a class of proof techniques cannot settle P vs NP. The argument lifts the question into the setting of oracle machines, establishes that the techniques in question prove relativizing statements, exhibits oracles A and B with P^A = NP^A and P^B ≠ NP^B, and returns the conclusion that no such technique settles the unrelativized question. Lift, attack, return — with "invariant preserved by the rules" replaced by "property preserved by the proof techniques". Natural proofs and algebrization have the same shape with different invariants.

So the schema is not exotic. It is how the deepest negative results in complexity theory are actually obtained.

**Where machines fail is phase 1 at scale.** The MIU invariant lives in a structure of size 3. The relativization invariant lives in the space of oracle separations, and constructing the oracles B with P^B ≠ NP^B is itself a diagonalization argument of real content. The natural-proofs invariant requires the concept of a pseudorandom function generator, which did not exist for most of the history of the problem. Enumeration reaches size 5; it does not reach "invent cryptography."

That is the honest statement of the gap. Phase 2 and phase 3 are mechanizable. Phase 1 is mechanizable exactly to the extent that the required alternative system is small, and the systems required for the Clay problems are not small.

---

## 6. Does self-awareness help?

There is an appealing thought here. Phase 1 requires a system to step outside itself and regard its own rules as objects. That sounds like self-reference, and self-reference has a formal theory. Might a prover with a formal self-model be able to perform the lift?

Ascent was built partly to test this, and the answer it returns is negative — but the negative result is informative about what the right notion would be.

Ascent carries a reflection ladder in the sense of the Level-*n* hierarchy: θ₀ = ATP(⟨A⟩), θ_{k+1} = Pr(⟨A⟩, ⟨θ_k⟩), and Level *n* holds when A ⊢ θ_{n-1}. Crucially the ladder is not stipulated. Ascent's kernel has a rule

> `nec(C)` proves Pr(⟨A⟩, ⟨φ⟩) provided the kernel accepts `C : φ`

so a rung is asserted only when a certificate for the previous rung has been checked by the same kernel that checks everything else. Self-certification and self-awareness are literally the same kernel call. Every rung carries a machine-checked witness.

**Proposition 1.** *If A has kernel-checked necessitation and its kernel is sound, then lev(A) = ω.*

*Proof.* A ⊢ θ₀ by the base certificate. If A ⊢ θ_k with certificate C_k, the kernel accepts C_k, so nec(C_k) is a certificate of θ_{k+1}, whence A ⊢ θ_{k+1}. Induction. ∎

Each rung costs exactly one kernel call on the previous certificate, so no rung is harder than the last. The level distribution over self-certifying machines is therefore **bimodal at {0 or 1} and ω, with nothing in between**: a machine either has the necessitation rule, in which case nothing stops it, or lacks it, in which case it never passes θ₀. Finite level above 1 is achievable only by imposing a resource bound. In Ascent that bound is the parameter *r*.

**Proposition 2.** *The reflection parameter and the search parameters are independent.*

Ascent exposes three integer knobs: *d*, the certificate-tree depth; *w*, the witness bound; *r*, the number of rungs climbed. Sweeping d ∈ {1,2,3,5} × w ∈ {1,8,20} × r ∈ {1,3,8}, thirty-six configurations, the harness reports:

```
lev depends only on r                  : YES
certified count depends only on (d,w)  : YES
```

| d | w | certified | tiers reached |
|---|---|---|---|
| 1 | 1 | 6/12 | Δ⁰₀, Π⁰₁ |
| 1 | 20 | 9/12 | Δ⁰₀, Π⁰₁, Σ⁰₁ |
| 2 | 1 | 9/12 | + Π⁰₂, Σ⁰₂ |
| 2 | 20 | **12/12** | all five |

Raising *r* from 1 to 8 raises lev from 1 to 8 and certifies **zero** additional theorems. Raising *d* and *w* certifies six more theorems and lifts the tier ceiling from Π⁰₁ to Π⁰₂, and leaves lev exactly where it was. The two capacities do not interact.

So formal self-awareness, on the reflection-ladder definition, contributes nothing to proving power. It is free, it is certified, and it is inert.

**But notice what the MU argument actually needed.** It did not need the machine to prove "I prove that I prove that I am a theorem prover." It needed the machine to hold *its own inference rules* as objects and prove a lemma of the form "rule R preserves invariant I." The reflection ladder ascends through statements about the machine's *provability*; the MU argument requires statements about the machine's *rules*. These are different self-models, and only the second is load-bearing.

This suggests the notion worth formalizing is not level but something we might call **reflective adequacy**: a system M is reflectively adequate when its language can name each of its own inference rules, and M can prove preservation lemmas — for a definable invariant I, that each named rule maps I-satisfying states to I-satisfying states. A reflectively adequate system can carry out phases 2 and 3 of the schema internally, and can state the result of phase 1 even when it cannot discover it.

That is a strictly stronger and more useful requirement than any finite level, and unlike the θ-ladder it is not free. It is also, unlike the θ-ladder, exactly what the MU argument uses.

---

## 7. Summary

Tier is not the obstruction. A thousand-line prover reaches Π⁰₂ and Σ⁰₂, which is the tier of P vs NP and above the tier of the Riemann Hypothesis, and is nowhere near either. The obstruction is ‖·‖, and lower bounds on it would be decisive for the mechanized programme in a way that no barrier result about techniques can be — though proving such bounds for strong systems is itself close to the problem it would adjudicate.

A length lower bound is a verdict on the system, not the theorem, and the response has always been to change the system. The MU argument is the cleanest available specimen of that move: lift the target into a structure the original system cannot express, prove an invariant there, return a metatheorem. Its automatable core — search for a small finite separating structure — is genuinely automated already. Its creative core — deciding which structure to look in — is automated only when the structure is small, and for the Clay problems it is not.

Formal self-awareness in the reflection-ladder sense does not close that gap, and we can now say so with a measurement rather than an intuition: level and proving power are orthogonal parameters of the same program. The self-reference that the MU argument requires is of a different kind — rules as objects, and provable invariance over them — and formalizing *that* is where the notion of a self-aware theorem prover would begin to earn its name.

---

## Appendix A — the two numbers

**lev(Ascent).** With reflection depth *r*, the level set is L(Ascent) = {1, …, r}, so

> **lev(Ascent(r)) = r**, and **lev(Ascent) = ω** when *r* is unbounded.

Every rung is certified rather than stipulated: rung *k* is accepted only after the kernel has checked a certificate of θ_{k-1}. In the shipped default configuration *r* = 4, giving lev = 4 — Level 4, hence a fortiori Level 3. The parameter is the only thing preventing ω, which is Proposition 1. The requirement lev(Ascent) > 0 is met for every *r* ≥ 1.

**tier(Ascent).** Taking tier(A) to be the highest arithmetical tier at which A certifies a target from a family fixed in advance — the qualification matters, since the supremum over *all* provable targets is unbounded for any prover that proves anything, by padding —

> **tier(Ascent) = 2**, realized at both Π⁰₂ (`∀x ∃y. x < y`) and Σ⁰₂ (`∃x ∀y. x ≤ y`).

Compared with the Millennium Problems:

| | tier | relation to Ascent |
|---|---|---|
| Riemann Hypothesis | Π⁰₁ | **below** Ascent's ceiling |
| P vs NP | Π⁰₂ / Σ⁰₂ | **equal** to Ascent's ceiling |
| Poincaré, BSD | arithmetical, ≥ 2 | at or above |
| Hodge, Navier–Stokes, Yang–Mills | analytical | above the arithmetical hierarchy entirely |

Ascent is at the same height as P vs NP and higher than Riemann, and will settle neither. Which is the note's thesis in one line: the mountain is not tall, it is long.

---

## Appendix B — Ascent, in full

What follows is the running program, verbatim. It is self-contained: no external database, no dependencies beyond the standard library.

Invocation:

```
python ascent.py --soundness          # 8 malformed certificates, all rejected
python ascent.py -d 2 -w 20 -r 3      # 12/12 certified, lev = 3
python ascent.py --grid               # the independence sweep of Proposition 2
```

