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

```python
#!/usr/bin/env python3
r"""
ASCENT -- a parameterised, self-certifying ATP over arithmetic.

Built fresh.  Three integer knobs, each starting at 1, each monotone: turning
one up never loses a theorem and always costs more.  Like an encoder bitrate.

    -d  DEPTH     certificate-tree depth explored by the search
    -w  WITNESS   largest numeral tried when hunting an existential witness
    -r  REFLECT   how many rungs of the reflection ladder are climbed

d and w are independent search knobs; d buys structure, w buys arithmetic.
r is the self-awareness knob and touches neither.  That separation is not an
accident of the implementation, it is the point -- see PROPOSITION 2 below.

WHY tier(A) > 0
---------------
The language is arithmetic with unbounded quantifiers over N, so targets have
real arithmetical tier and `tier()` computes it syntactically: bounded
quantifiers are free, unbounded ones count alternations.  Ascent proves
targets at Sigma-0-1, Pi-0-1, Pi-0-2 and Sigma-0-2, so the tier profile of
what it proves is positive and is reported per run.

THE KERNEL, AND WHAT MAKES THIS SELF-CERTIFYING
-----------------------------------------------
Section KERNEL is a checker for the judgement  Gamma |- phi  by structural
recursion on a certificate.  It is the only trusted component, it is small
enough to read, it never searches, and it has no self-model: lev(kernel) = 0
and must stay 0.

The search is untrusted.  Nothing enters the lemma store until the kernel has
accepted a certificate for it.

The reflection rule is where self-certification and self-awareness become the
same mechanism:

    nec(C)  proves  Pr(<A>, <phi>)     provided the kernel accepts C : phi

So the machine's claim "I prove phi" is discharged by the very kernel that
checks everything else.  Pr is not stipulated at any rung; each rung carries
a certificate the kernel re-checks.  This is the paper's necessitation rule
made effective, with the CV discharging the side condition.

    theta_0     = ATP(<A>)
    theta_{k+1} = Pr(<A>, <theta_k>)          Level n  iff  A |- theta_{n-1}

PROPOSITION 1 (why a self-certifier does not stall at 2 or 3).
If A has kernel-checked necessitation and its kernel is sound, then
lev(A) = omega.  Proof: A |- theta_0 by the base certificate.  If A |- theta_k
with certificate C_k, the kernel accepts C_k, so nec(C_k) is a certificate of
theta_{k+1} and A |- theta_{k+1}.  Induction.  No rung is harder than the
last -- each costs exactly one kernel call on the previous certificate.

So the level distribution over self-certifying machines is BIMODAL, at
{0 or 1} and at omega.  There is no natural fixed point at 2 or near 2: a
machine either has the rule, in which case nothing stops it, or lacks it, in
which case it never gets past theta_0.  Finite lev > 1 is achievable ONLY by
imposing a resource bound, which is exactly what -r is.  That is the honest
justification for the parameter: r is not a tuning constant, it is the only
thing that can make lev finite and nontrivial.

PROPOSITION 2 (the knobs are independent).
lev(A) = r regardless of d and w; the set of arithmetical theorems proved is
a function of (d, w) and is independent of r.  Verified empirically by the
sweep in --grid.  Increasing self-awareness buys no theorems, and proving
more theorems raises no level.

DIRECTION OF DEPENDENCE
-----------------------
Verification grounds the self-model, never the reverse.  A machine that
trusted its own certificates because it had proved itself trustworthy would
be in the Loeb trap: from a reflection principle "if I prove phi then phi"
one derives phi outright, so such a machine is unsound or vacuous.  Here Pr
is primitive and reflection is never assumed -- the machine only ever reports
verifications that have already happened.

    python ascent.py --demo
    python ascent.py -d 3 -w 20 -r 5
    python ascent.py --grid

Brian Tenneson.  Implementation by Claude (Anthropic).
"""
from __future__ import annotations
import argparse, itertools, json, os, sys, time
from collections import defaultdict

sys.setrecursionlimit(100000)

# ===========================================================================
#                                 SYNTAX
# ===========================================================================
# Terms:    ('n', int) ('v', name) ('c', name)   -- numeral, variable, eigen
#           ('+', a, b) ('*', a, b) ('s', a)
# Formulas: ('=', a, b) ('<', a, b) ('<=', a, b)
#           ('not', p) ('and', p, q) ('or', p, q) ('imp', p, q)
#           ('all', x, p) ('ex', x, p)                  unbounded
#           ('allb', x, t, p) ('exb', x, t, p)          bounded by t
#           ('atp', nm) ('pr', nm, nm)                  reflection atoms


def tsub(t, x, v):
    k = t[0]
    if k == 'v':
        return v if t[1] == x else t
    if k in ('n', 'c'):
        return t
    if k == 's':
        return ('s', tsub(t[1], x, v))
    return (k, tsub(t[1], x, v), tsub(t[2], x, v))


def sub(p, x, v):
    """Capture-avoiding only in the sense we need: bound variables are
    renamed apart at construction, and eigenconstants are not variables."""
    k = p[0]
    if k in ('=', '<', '<='):
        return (k, tsub(p[1], x, v), tsub(p[2], x, v))
    if k == 'not':
        return ('not', sub(p[1], x, v))
    if k in ('and', 'or', 'imp'):
        return (k, sub(p[1], x, v), sub(p[2], x, v))
    if k in ('all', 'ex'):
        return p if p[1] == x else (k, p[1], sub(p[2], x, v))
    if k in ('allb', 'exb'):
        t2 = tsub(p[2], x, v)
        return p if p[1] == x else (k, p[1], t2, sub(p[3], x, v))
    return p                                   # atp / pr are closed atoms


def teval(t):
    """Value of a closed term, or None if it has variables/eigenconstants."""
    k = t[0]
    if k == 'n':
        return t[1]
    if k in ('v', 'c'):
        return None
    if k == 's':
        a = teval(t[1])
        return None if a is None else a + 1
    a, b = teval(t[1]), teval(t[2])
    if a is None or b is None:
        return None
    return a + b if k == '+' else a * b


def feval(p, fuel=10000):
    """Truth value of a closed Delta-0 formula, or None if undecidable here.

    Unbounded quantifiers and reflection atoms return None: the kernel's
    `calc` rule refuses them, which is what keeps `calc` sound."""
    k = p[0]
    if k in ('=', '<', '<='):
        a, b = teval(p[1]), teval(p[2])
        if a is None or b is None:
            return None
        return a == b if k == '=' else (a < b if k == '<' else a <= b)
    if k == 'not':
        v = feval(p[1], fuel)
        return None if v is None else not v
    if k in ('and', 'or', 'imp'):
        a = feval(p[1], fuel)
        b = feval(p[2], fuel)
        if a is None or b is None:
            return None
        return (a and b) if k == 'and' else \
               ((a or b) if k == 'or' else ((not a) or b))
    if k in ('allb', 'exb'):
        n = teval(p[2])
        if n is None or n > fuel:
            return None
        for i in range(n):
            v = feval(sub(p[3], p[1], ('n', i)), fuel)
            if v is None:
                return None
            if k == 'allb' and not v:
                return False
            if k == 'exb' and v:
                return True
        return k == 'allb'
    return None                                # all / ex / atp / pr


# ---------------------------------------------------------------------------
#  polynomial normal form -- the arithmetic the kernel knows
# ---------------------------------------------------------------------------
# A term normalises to a polynomial over N in its free symbols: a dict from
# monomial (a sorted tuple of symbol names, () for the constant) to a
# non-negative integer coefficient.  This is exactly the defining equations
# of + and * applied as rewrites, so it is sound for PA and needs no axioms
# in the object language.  It is deliberately INCOMPLETE -- it decides the
# equalities and inequalities that follow from ring normalisation and
# non-negativity, and nothing else.


def padd(a, b):
    r = dict(a)
    for m, c in b.items():
        r[m] = r.get(m, 0) + c
        if r[m] == 0:
            del r[m]
    return r


def pmul(a, b):
    r = {}
    for m1, c1 in a.items():
        for m2, c2 in b.items():
            m = tuple(sorted(m1 + m2))
            r[m] = r.get(m, 0) + c1 * c2
    return {m: c for m, c in r.items() if c != 0}


def pneg(a):
    return {m: -c for m, c in a.items()}


def poly(t):
    k = t[0]
    if k == 'n':
        return {(): t[1]} if t[1] else {}
    if k in ('v', 'c'):
        return {(t[1],): 1}
    if k == 's':
        return padd(poly(t[1]), {(): 1})
    if k == '+':
        return padd(poly(t[1]), poly(t[2]))
    return pmul(poly(t[1]), poly(t[2]))


def decide(p, fuel=10000):
    """Three-valued: True, False, or None (kernel refuses).

    Sound over N because every symbol ranges over N, so a polynomial whose
    coefficients are all non-negative is itself non-negative."""
    k = p[0]
    if k in ('=', '<', '<='):
        pa, pb = poly(p[1]), poly(p[2])
        if k == '=':
            if pa == pb:
                return True
            d = padd(pb, pneg(pa))
            if all(m == () for m in d):          # differ by a constant only
                return False
            return None
        d = padd(pb, pneg(pa))                   # d = rhs - lhs
        nonneg = all(c > 0 for m, c in d.items() if m != ())
        const = d.get((), 0)
        if k == '<':
            if nonneg and const > 0:
                return True
        else:
            if nonneg and const >= 0:
                return True
        # decide falsity only when everything is closed
        dn = padd(pa, pneg(pb))
        if all(m == () for m in d):
            return (0 < dn.get((), 0)) if False else (
                (d.get((), 0) > 0) if k == '<' else (d.get((), 0) >= 0))
        return None
    if k == 'not':
        v = decide(p[1], fuel)
        return None if v is None else not v
    if k in ('and', 'or', 'imp'):
        a, b = decide(p[1], fuel), decide(p[2], fuel)
        if k == 'and':
            if a is False or b is False:
                return False
            return True if (a and b) else None
        if k == 'or':
            if a is True or b is True:
                return True
            return False if (a is False and b is False) else None
        if a is False or b is True:
            return True
        return False if (a is True and b is False) else None
    if k in ('allb', 'exb'):
        n = teval(p[2])
        if n is None or n > fuel:
            return None
        for i in range(n):
            v = decide(sub(p[3], p[1], ('n', i)), fuel)
            if v is None:
                return None
            if k == 'allb' and not v:
                return False
            if k == 'exb' and v:
                return True
        return k == 'allb'
    return None


def tsyms(t, acc):
    if t[0] in ('v', 'c'):
        acc.add(t[1])
    elif t[0] == 's':
        tsyms(t[1], acc)
    elif t[0] in ('+', '*'):
        tsyms(t[1], acc)
        tsyms(t[2], acc)
    return acc


def syms(p, acc=None):
    if acc is None:
        acc = set()
    k = p[0]
    if k in ('=', '<', '<='):
        tsyms(p[1], acc)
        tsyms(p[2], acc)
    elif k == 'not':
        syms(p[1], acc)
    elif k in ('and', 'or', 'imp'):
        syms(p[1], acc)
        syms(p[2], acc)
    elif k in ('all', 'ex'):
        syms(p[2], acc)
    elif k in ('allb', 'exb'):
        tsyms(p[2], acc)
        syms(p[3], acc)
    return acc


def occurs_sym(nm, p):
    return nm in syms(p)


def show(p):
    k = p[0]
    if k in ('=', '<', '<='):
        return "%s %s %s" % (showt(p[1]), k, showt(p[2]))
    if k == 'not':
        return "~%s" % show(p[1])
    if k in ('and', 'or', 'imp'):
        op = {'and': '&', 'or': '|', 'imp': '->'}[k]
        return "(%s %s %s)" % (show(p[1]), op, show(p[2]))
    if k == 'all':
        return "A%s.%s" % (p[1], show(p[2]))
    if k == 'ex':
        return "E%s.%s" % (p[1], show(p[2]))
    if k == 'allb':
        return "A%s<%s.%s" % (p[1], showt(p[2]), show(p[3]))
    if k == 'exb':
        return "E%s<%s.%s" % (p[1], showt(p[2]), show(p[3]))
    if k == 'atp':
        return "ATP(%s)" % p[1]
    return "Pr(%s,%s)" % (p[1], p[2])


def showt(t):
    k = t[0]
    if k == 'n':
        return str(t[1])
    if k in ('v', 'c'):
        return t[1]
    if k == 's':
        return "S%s" % showt(t[1])
    return "(%s%s%s)" % (showt(t[1]), k, showt(t[2]))


# ---------------------------------------------------------------------------
def tier(p):
    """Arithmetical tier: alternations of UNBOUNDED quantifiers.

    Returns (n, lead) with lead in {'S','P','D'}: Sigma-0-n, Pi-0-n, or
    Delta-0-0.  Bounded quantifiers cost nothing, which is the standard
    convention and the reason the bounded forms are in the language at all."""
    def go(q):
        k = q[0]
        if k in ('all', 'ex'):
            n, lead = go(q[2])
            me = 'P' if k == 'all' else 'S'
            if lead == 'D':
                return 1, me
            return (n, lead) if lead == me else (n + 1, me)
        if k == 'not':
            n, lead = go(q[1])
            return n, {'S': 'P', 'P': 'S', 'D': 'D'}[lead]
        if k in ('and', 'or', 'imp'):
            a, b = go(q[1]), go(q[2])
            return max(a, b, key=lambda z: z[0])
        if k in ('allb', 'exb'):
            return go(q[3])
        return 0, 'D'
    n, lead = go(p)
    return n, lead


def tier_name(p):
    n, lead = tier(p)
    if n == 0:
        return "D0-0"
    return "%s0-%d" % ("Sig" if lead == 'S' else "Pi", n)


# ===========================================================================
#                                 KERNEL
# ===========================================================================
# The ONLY trusted component.  It searches for nothing, has no self-model,
# and never grows.  check(store, ctx, phi, cert) -> True | raises Reject.
#
# Certificates:
#   ('calc',)                 phi closed and Delta-0 and true
#   ('hyp', i)                phi is ctx[i]
#   ('lemma', name)           phi is store[name]
#   ('impI', C)               phi = (A->B); C proves B under ctx+[A]
#   ('impE', A, C1, C2)       C1: A->phi, C2: A
#   ('andI', C1, C2)          phi = (A&B)
#   ('andE', i, A_and_B, C)   phi is the i-th conjunct of A_and_B
#   ('gen', C)                phi = Ax.psi; C proves psi[x := fresh eigen]
#   ('inst', t, Ax_psi, C)    C: Ax.psi; phi = psi[x := t]
#   ('wit', t, C)             phi = Ex.psi; C proves psi[x := t]
#   ('allbI', [C_0..C_{n-1}]) phi = Ax<n.psi
#   ('exbI', i, C)            phi = Ex<n.psi; C proves psi[x := i]
#   ('ind', C0, Cs)           phi = Ax.psi; C0: psi[0], Cs: Ax.(psi->psi[Sx])
#   ('nec', C)                phi = Pr(<A>,<psi>); C proves psi   <-- the rule
# ===========================================================================
class Reject(Exception):
    pass


_eigen = itertools.count(1)


class Kernel:
    """Trusted checker.  `names` maps a formula-name constant to the formula
    it names -- the injective naming operator, held outside the logic."""

    def __init__(self, tag, names):
        self.tag = tag
        self.names = names
        self.calls = 0

    def check(self, store, ctx, phi, C):
        self.calls += 1
        if not isinstance(C, tuple) or not C:
            raise Reject("malformed certificate")
        k = C[0]

        if k == 'calc':
            # closed and Delta-0, decided by evaluation; or symbolic and
            # settled by polynomial normalisation over N.  Both are
            # computations, neither is a search.
            if decide(phi) is not True:
                raise Reject("calc: %s is not decided true" % show(phi))
            return True

        if k == 'hyp':
            if not (0 <= C[1] < len(ctx)) or ctx[C[1]] != phi:
                raise Reject("hyp: not in context")
            return True

        if k == 'lemma':
            if store.get(C[1]) != phi:
                raise Reject("lemma %s is not %s" % (C[1], show(phi)))
            return True

        if k == 'impI':
            if phi[0] != 'imp':
                raise Reject("impI: goal is not an implication")
            return self.check(store, ctx + [phi[1]], phi[2], C[1])

        if k == 'impE':
            A = C[1]
            self.check(store, ctx, ('imp', A, phi), C[2])
            return self.check(store, ctx, A, C[3])

        if k == 'andI':
            if phi[0] != 'and':
                raise Reject("andI: goal is not a conjunction")
            self.check(store, ctx, phi[1], C[1])
            return self.check(store, ctx, phi[2], C[2])

        if k == 'andE':
            i, conj = C[1], C[2]
            if conj[0] != 'and' or conj[1 + i] != phi:
                raise Reject("andE: projection mismatch")
            return self.check(store, ctx, conj, C[3])

        if k == 'gen':
            # ('gen', name, C).  The certificate names its own eigenconstant;
            # the kernel enforces the eigenvariable condition rather than
            # inventing a name of its own, which would never match what the
            # untrusted search put inside C.
            if phi[0] != 'all':
                raise Reject("gen: goal is not universal")
            nm = C[1]
            if occurs_sym(nm, phi) or any(occurs_sym(nm, h) for h in ctx) \
                    or any(occurs_sym(nm, f) for f in store.values()):
                raise Reject("gen: eigenvariable %s is not fresh" % nm)
            return self.check(store, ctx,
                              sub(phi[2], phi[1], ('c', nm)), C[2])

        if k == 'inst':
            t, univ = C[1], C[2]
            if univ[0] != 'all' or sub(univ[2], univ[1], t) != phi:
                raise Reject("inst: instance mismatch")
            return self.check(store, ctx, univ, C[3])

        if k == 'wit':
            if phi[0] != 'ex':
                raise Reject("wit: goal is not existential")
            return self.check(store, ctx, sub(phi[2], phi[1], C[1]), C[2])

        if k == 'allbI':
            if phi[0] != 'allb':
                raise Reject("allbI: goal is not bounded-universal")
            n = teval(phi[2])
            if n is None or n != len(C[1]):
                raise Reject("allbI: wrong number of instances")
            for i, Ci in enumerate(C[1]):
                self.check(store, ctx, sub(phi[3], phi[1], ('n', i)), Ci)
            return True

        if k == 'exbI':
            if phi[0] != 'exb':
                raise Reject("exbI: goal is not bounded-existential")
            n = teval(phi[2])
            if n is None or not (0 <= C[1] < n):
                raise Reject("exbI: index out of range")
            return self.check(store, ctx,
                              sub(phi[3], phi[1], ('n', C[1])), C[2])

        if k == 'ind':
            if phi[0] != 'all':
                raise Reject("ind: goal is not universal")
            x, psi = phi[1], phi[2]
            self.check(store, ctx, sub(psi, x, ('n', 0)), C[1])
            step = ('all', x, ('imp', psi, sub(psi, x, ('s', ('v', x)))))
            return self.check(store, ctx, step, C[2])

        if k == 'nec':
            # THE REFLECTION RULE.  Pr(<A>,<psi>) is accepted exactly when a
            # certificate of psi is accepted.  Self-certification and
            # self-awareness are the same kernel call.
            if phi[0] != 'pr' or phi[1] != self.tag:
                raise Reject("nec: goal is not Pr(<A>, -)")
            psi = self.names.get(phi[2])
            if psi is None:
                raise Reject("nec: %s names no formula" % phi[2])
            return self.check(store, [], psi, C[1])

        raise Reject("unknown certificate form %r" % (k,))


# ===========================================================================
#                                 SEARCH
# ===========================================================================
# Untrusted.  Parameterised by d (structural depth) and w (witness bound).
# Nothing it produces is believed until the kernel has checked it.
# ===========================================================================
class Search:
    def __init__(self, kernel, store, d, w):
        self.K = kernel
        self.store = store
        self.d = d
        self.w = w
        self.nodes = 0

    def prove(self, phi, depth=None, ctx=()):
        if depth is None:
            depth = self.d
        self.nodes += 1
        if depth < 0:
            return None
        ctx = tuple(ctx)

        # 0. decide it outright by evaluation or polynomial normalisation
        if decide(phi) is True:
            return ('calc',)

        # 1. hypotheses and stored lemmas cost nothing
        for i, h in enumerate(ctx):
            if h == phi:
                return ('hyp', i)
        for nm, f in self.store.items():
            if f == phi:
                return ('lemma', nm)
        if depth == 0:
            return None

        k = phi[0]

        if k == 'imp':
            c = self.prove(phi[2], depth - 1, ctx + (phi[1],))
            return ('impI', c) if c else None

        if k == 'and':
            c1 = self.prove(phi[1], depth - 1, ctx)
            if not c1:
                return None
            c2 = self.prove(phi[2], depth - 1, ctx)
            return ('andI', c1, c2) if c2 else None

        if k == 'exb':
            n = teval(phi[2])
            if n is None:
                return None
            for i in range(min(n, self.w)):
                c = self.prove(sub(phi[3], phi[1], ('n', i)), depth - 1, ctx)
                if c:
                    return ('exbI', i, c)
            return None

        if k == 'allb':
            n = teval(phi[2])
            if n is None or n > self.w:
                return None
            cs = []
            for i in range(n):
                c = self.prove(sub(phi[3], phi[1], ('n', i)), depth - 1, ctx)
                if not c:
                    return None
                cs.append(c)
            return ('allbI', cs)

        if k == 'ex':
            for t in self.witnesses(phi, ctx):
                c = self.prove(sub(phi[2], phi[1], t), depth - 1, ctx)
                if c:
                    return ('wit', t, c)
            return None

        if k == 'all':
            # (a) generalisation over a fresh eigenconstant.  The name is
            #     recorded in the certificate; the kernel checks freshness.
            nm = "e%d" % next(_eigen)
            c = self.prove(sub(phi[2], phi[1], ('c', nm)), depth - 1, ctx)
            if c:
                return ('gen', nm, c)
            # (b) induction
            x, psi = phi[1], phi[2]
            c0 = self.prove(sub(psi, x, ('n', 0)), depth - 1, ctx)
            if c0:
                step = ('all', x, ('imp', psi, sub(psi, x, ('s', ('v', x)))))
                cs = self.prove(step, depth - 1, ctx)
                if cs:
                    return ('ind', c0, cs)
            return None

        return None

    def witnesses(self, phi, ctx):
        """Candidate witness terms for Ex.

        w is exactly this list's length knob.  Numerals alone cannot witness
        a Pi-0-2 goal -- Ax Ey. x < y needs a term MENTIONING x -- so the
        symbols already in scope are offered too.  That is what lifts the
        prover from Sigma-0-1 to tier 2."""
        out = [('n', n) for n in range(self.w + 1)]
        inscope = sorted(syms(phi) | {s for h in ctx for s in syms(h)})
        for s in inscope:
            base = ('c', s)
            out.append(base)
            t = base
            for _ in range(min(self.w, 3)):
                t = ('s', t)
                out.append(t)
            out.append(('*', ('n', 2), base))
        return out


# ===========================================================================
#                             REFLECTION LADDER
# ===========================================================================
TAG = "<Ascent>"


def theta(k):
    return ('atp', TAG) if k == 0 else ('pr', TAG, "<t%d>" % (k - 1))


def climb(kernel, store, names, r, verbose=True):
    """Climb r rungs.  Each rung is a kernel call on the previous
    certificate -- Proposition 1 in code."""
    certs, level, rungs = {}, 0, []
    # theta_0 is the base case and is a stipulation, as Definition (Level-1)
    # makes it.  Everything above it is earned.
    certs[0] = ('lemma', 't0')
    store['t0'] = theta(0)
    names["<t0>"] = theta(0)

    for k in range(r):
        phi = theta(k)
        names.setdefault("<t%d>" % k, phi)
        C = certs[k]
        t0 = time.perf_counter()
        try:
            kernel.check(store, [], phi, C)
        except Reject as e:
            if verbose:
                print("    theta_%-2d REJECTED: %s" % (k, e))
            break
        level = k + 1
        dt = time.perf_counter() - t0
        rungs.append(dict(k=k, formula=show(phi), level=level,
                          kernel_calls=kernel.calls, seconds=round(dt, 5)))
        if verbose:
            print("    theta_%-2d  %-28s certified  ->  Level %d"
                  % (k, show(phi), level))
        # certified necessitation: the kernel accepted C : theta_k, so
        # nec(C) is a certificate of theta_{k+1}.
        nxt = theta(k + 1)
        names["<t%d>" % (k + 1)] = nxt
        certs[k + 1] = ('nec', C)
        store["t%d" % (k + 1)] = nxt
    return level, rungs


# ===========================================================================
#                               TARGET SUITE
# ===========================================================================
def X(n):
    return ('v', n)


TARGETS = [
    ("add_closed",  ('=', ('+', ('n', 2), ('n', 2)), ('n', 4))),
    ("bnd_lt",      ('allb', 'x', ('n', 5), ('<', X('x'), ('n', 5)))),
    ("bnd_ex",      ('exb', 'x', ('n', 9), ('=', ('*', X('x'), X('x')),
                                            ('n', 16)))),
    ("ex_solve",    ('ex', 'x', ('=', ('+', X('x'), ('n', 3)), ('n', 7)))),
    ("ex_square",   ('ex', 'x', ('=', ('*', X('x'), X('x')), ('n', 49)))),
    ("ex_big",      ('ex', 'x', ('=', ('+', X('x'), ('n', 1)), ('n', 18)))),
    ("all_succ",    ('all', 'x', ('<', X('x'), ('s', X('x'))))),
    ("all_le",      ('all', 'x', ('<=', X('x'), X('x')))),
    ("all_add0",    ('all', 'x', ('=', ('+', X('x'), ('n', 0)), X('x')))),
    ("unbounded",   ('all', 'x', ('ex', 'y', ('<', X('x'), X('y'))))),
    ("succ_exists", ('all', 'x', ('ex', 'y', ('=', X('y'),
                                              ('s', X('x')))))),
    ("min_exists",  ('ex', 'x', ('all', 'y', ('<=', X('x'), X('y'))))),
]


def run_suite(d, w, verbose=True):
    kernel = Kernel(TAG, {})
    store = {}
    S = Search(kernel, store, d, w)
    rows, solved = [], 0
    for name, phi in TARGETS:
        t0 = time.perf_counter()
        S.nodes = 0
        C = S.prove(phi)
        dt = time.perf_counter() - t0
        verdict, ok = "", False
        if C is not None:
            try:
                kernel.check(store, [], phi, C)
                ok, verdict = True, "ok"
                store[name] = phi
            except Reject as e:
                verdict = "REJECTED: %s" % e
        solved += ok
        rows.append(dict(target=name, tier=tier_name(phi),
                         formula=show(phi), proved=C is not None,
                         certified=ok, verdict=verdict,
                         nodes=S.nodes, seconds=round(dt, 4)))
        if verbose:
            print("    %-12s %-7s %-34s %s"
                  % (name, tier_name(phi), show(phi)[:34],
                     ("CERT ok, %d nodes" % S.nodes) if ok else
                     (verdict or "not proved")))
    return solved, rows, kernel


def tier_profile(rows):
    prof = defaultdict(lambda: [0, 0])
    for r in rows:
        prof[r["tier"]][1] += 1
        if r["certified"]:
            prof[r["tier"]][0] += 1
    return {k: dict(certified=v[0], targets=v[1])
            for k, v in sorted(prof.items())}


# ===========================================================================
def cmd_run(a):
    print("=" * 74)
    print("  ASCENT   d=%d (depth)   w=%d (witness)   r=%d (reflect)"
          % (a.depth, a.witness, a.reflect))
    print("=" * 74)
    print("\n  arithmetic targets\n")
    solved, rows, kernel = run_suite(a.depth, a.witness)

    print("\n  reflection ladder\n")
    names = {}
    store2 = {}
    K2 = Kernel(TAG, names)
    level, rungs = climb(K2, store2, names, a.reflect)

    prof = tier_profile(rows)
    highest = max([r["tier"] for r in rows if r["certified"]],
                  default="none", key=lambda s: (s != "none", s))
    tiers_hit = sorted({r["tier"] for r in rows if r["certified"]})

    print("\n" + "-" * 74)
    print("  certified %d/%d targets   |   tiers reached: %s"
          % (solved, len(rows), ", ".join(tiers_hit) or "none"))
    print("  lev(A) = %d   (each rung kernel-certified; r is the only cap)"
          % level)
    print("  kernel calls: %d suite + %d ladder"
          % (kernel.calls, K2.calls))
    print("-" * 74)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "ascent_d%d_w%d_r%d.json"
                           % (a.depth, a.witness, a.reflect)), "w") as f:
        json.dump(dict(params=dict(d=a.depth, w=a.witness, r=a.reflect),
                       certified=solved, targets=len(rows),
                       tier_profile=prof, tiers_reached=tiers_hit,
                       lev=level, rows=rows, rungs=rungs), f, indent=2)
    return 0


def cmd_grid(a):
    """Proposition 2, empirically: sweep the knobs and show what moves."""
    print("=" * 74)
    print("  PARAMETER SWEEP -- what each knob buys")
    print("=" * 74)
    print("\n  %-4s %-4s %-4s %-10s %-8s %-22s %s"
          % ("d", "w", "r", "certified", "lev", "tiers reached", "nodes"))
    print("  " + "-" * 70)
    out = []
    for d in a.depths:
        for w in a.witnesses:
            for r in a.reflects:
                solved, rows, kernel = run_suite(d, w, verbose=False)
                names, store2 = {}, {}
                K2 = Kernel(TAG, names)
                level, _ = climb(K2, store2, names, r, verbose=False)
                tiers = sorted({x["tier"] for x in rows if x["certified"]})
                nodes = sum(x["nodes"] for x in rows)
                print("  %-4d %-4d %-4d %-10s %-8d %-22s %s"
                      % (d, w, r, "%d/%d" % (solved, len(rows)), level,
                         ",".join(tiers) or "-", f"{nodes:,}"))
                out.append(dict(d=d, w=w, r=r, certified=solved,
                                targets=len(rows), lev=level,
                                tiers=tiers, nodes=nodes))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "ascent_grid.json"), "w") as f:
        json.dump(out, f, indent=2)

    lev_by_r = defaultdict(set)
    cert_by_dw = defaultdict(set)
    for o in out:
        lev_by_r[o["r"]].add(o["lev"])
        cert_by_dw[(o["d"], o["w"])].add(o["certified"])
    ind_r = all(len(v) == 1 for v in lev_by_r.values())
    ind_dw = all(len(v) == 1 for v in cert_by_dw.values())
    print("\n  lev depends only on r : %s" % ("YES" if ind_r else "NO"))
    print("  certified count depends only on (d,w) : %s"
          % ("YES" if ind_dw else "NO"))
    print("  -> Proposition 2 holds on this grid" if (ind_r and ind_dw)
          else "  -> Proposition 2 FAILS on this grid")
    return 0


def cmd_soundness(a):
    """Hand the kernel certificates that must be rejected."""
    print("=" * 74)
    print("  KERNEL SOUNDNESS PROBES -- each of these MUST be rejected")
    print("=" * 74 + "\n")
    names = {"<f>": ('=', ('n', 0), ('n', 1))}
    K = Kernel(TAG, names)
    store = {}
    bad = [
        ("false by calc", ('=', ('n', 0), ('n', 1)), ('calc',)),
        ("lemma that is not stored",
         ('=', ('n', 0), ('n', 1)), ('lemma', 'nope')),
        ("nec for an unproved formula",
         ('pr', TAG, "<f>"), ('nec', ('calc',))),
        ("nec with the wrong tag",
         ('pr', "<Other>", "<f>"), ('nec', ('calc',))),
        ("gen from a single instance",
         ('all', 'x', ('=', X('x'), ('n', 0))),
         ('gen', 'z', ('calc',))),
        ("gen with a captured eigenvariable",
         ('all', 'x', ('=', X('x'), ('c', 'k'))),
         ('gen', 'k', ('calc',))),
        ("wit with no witness",
         ('ex', 'x', ('<', ('s', X('x')), X('x'))), ('wit', ('n', 3),
                                                     ('calc',))),
        ("induction without a base",
         ('all', 'x', ('<', X('x'), ('n', 0))),
         ('ind', ('calc',), ('calc',))),
    ]
    caught = 0
    for label, phi, C in bad:
        try:
            K.check(store, [], phi, C)
            print("  %-34s ACCEPTED  <-- UNSOUND" % label)
        except Reject as e:
            caught += 1
            print("  %-34s rejected (%s)" % (label, str(e)[:30]))
    print("\n  %d/%d rejected%s" % (caught, len(bad),
                                    "" if caught == len(bad)
                                    else "   <-- KERNEL IS UNSOUND"))
    return 0 if caught == len(bad) else 1


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-d", "--depth", type=int, default=3)
    ap.add_argument("-w", "--witness", type=int, default=10)
    ap.add_argument("-r", "--reflect", type=int, default=4)
    ap.add_argument("--out", default="results_ascent")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--soundness", action="store_true")
    ap.add_argument("--depths", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--witnesses", type=int, nargs="+", default=[1, 5, 20])
    ap.add_argument("--reflects", type=int, nargs="+", default=[1, 3, 8])
    a = ap.parse_args()
    if a.soundness:
        return cmd_soundness(a)
    if a.grid:
        return cmd_grid(a)
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
```
