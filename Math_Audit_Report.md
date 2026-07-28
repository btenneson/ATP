# Mathematical Audit — *Depths of a Simulation* v45 and *Formalized Self-Awareness* v18

Brian Tenneson · audit dated 27 July 2026

Both papers were read in full (2,872 + 1,908 lines). Every definition, theorem statement and proof was checked. This report lists what I found, rated by severity. All fixes are applied in `Depths_and_Self_Awareness_Merged_v1.tex`.

**Headline: the mathematics is in good shape.** The core architecture — consequence closure, the SIC axioms, the four simulation notions, the proof-horizon theorem, the reflection hierarchy, the level function and its monotonicity — is correct. I verified the delay-obstruction proof, the clocked repair, the depth-spectrum refutation (both directions), the Picard machine's transaction count, the strictness construction, cumulativity, the dichotomy, and the reflection-closure machine line by line. They hold.

What follows are eight genuine defects and a handful of smaller blemishes.

---

## Serious — a claim that does not follow as stated

### S1. The Cook–Reckhow theorem cannot be proved inside the paper's own definition of a proof
**Location:** Part I, Definition `def:crsystem`, Theorem `thm:cookreckhow` (§10.1)

Definition `def:crsystem` builds a Cook–Reckhow system out of a formal system $F=(x,y,z)$, so a proof is a sequence of *well-formed formulas*, each a hypothesis or a direct consequence of earlier lines (Definition `def:proof`). The forward direction of the theorem then argues: if NP = coNP then UNSAT ∈ NP, so it has polynomial-size witnesses; "declaring each such witness a one-line proof from Γ" gives the required system.

That step is not available. A witness is an arbitrary string, and there is no line of a proof at which an arbitrary string may be guessed — every line must be in Γ or produced by a rule from earlier lines. Nor can the construction be rescued by a unary rule $r(\gamma) = \bot$ defined exactly when $\gamma$ is unsatisfiable: deciding whether $r(\gamma)=\bot$ is then deciding UNSAT, so that $F$ fails Definition `def:polytimecheckable`.

The paper's proof systems are a proper subclass of Cook–Reckhow proof systems — precisely the ones whose proofs happen to be formula sequences. The classical theorem quantifies over all of them.

**Fix applied.** `def:crsystem` now carries an auxiliary proof alphabet $\Pi$ with a polynomial-time verification relation $\mathrm{Ver}$ — Cook and Reckhow's actual definition — with the formula-sequence systems as the special case. A new Remark `rem:crgenerality` says exactly why the generality is load-bearing and notes that everything else in §10 (size, $s_F$, $p$-simulation, resolution, Frege) lives inside the special case.

---

## Moderate — definitions that do not define what they are used for

### M2. The size function contradicts the resolution system
**Location:** Part I, Definition `def:sizefunction` vs. Definition `def:resolutionsystem`

`def:sizefunction` requires a size function to land in $\mathbf{N}^+$, and the remark following it uses $|\varphi| \ge 1$ to derive $\mathrm{size}(\pi) \ge |\pi|$ — the inequality that lets the Proof-Horizon Theorem relativize to size. But `def:resolutionsystem` gives a clause its number of literal occurrences, so the empty clause $\bot$ has size $0$. Since $\bot$ is the target of every refutation, this is not an edge case.

**Fix applied.** Resolution's size function is now one more than the number of literal occurrences, so $|\bot| = 1$.

### M3. The interpolant definition is incoherent
**Location:** Part I, Definition `def:interpolant`

As written: for unsatisfiable $\alpha(\bar p, \bar q)$ and an assignment $\bar a$ to $\bar p$, "if $I(\bar a)=0$ then $\alpha(\bar a,\bar q)$ is unsatisfiable, and if $I(\bar a)=1$ then $\alpha(\bar p,\bar a)$ is unsatisfiable." The second clause substitutes an assignment to $\bar p$ into the $\bar q$ block. The two clauses are not about the same object and the condition states nothing.

Feasible interpolation needs the split form: $A(\bar p,\bar r) \wedge B(\bar p,\bar s)$ unsatisfiable with $\bar p$ shared, and $I(\bar a)=0 \Rightarrow A(\bar a,\bar r)$ unsat, $I(\bar a)=1 \Rightarrow B(\bar a,\bar s)$ unsat. Without it, Theorem `thm:feasinterp` and the clique-colouring argument in `thm:interplowerbound` have nothing to attach to.

**Fix applied.** Restated in the standard split form, with `def:feasibleinterp` adjusted to match.

### M4. Clause 4 of non-degeneracy is not a condition
**Location:** Part II, Definition `def:nondegen`

Clause 4 reads: "$M$ performs proof search over a formula set whose cardinality is large relative to $\mathrm{Self}(M)$." *Large relative to* is undefined. This is not harmless — the clause is discharged in Corollary `cor:pnondegen`, and non-degeneracy then does real work in Corollary `cor:degnoninvariant` (degeneracy is not an $\sim_{\mathrm{SA}}^{\mathrm{adm}}$-invariant) and Proposition `prop:mechcomesapart` (mechanism vs. self-theory properties), which in turn carry the $\Phi$ placement in §18. A chain of results rests on an undefined predicate.

**Fix applied.** Clause 4 is now: $Y$ infinite and $|\mathrm{Self}(M)| < |Y|$, or $Y$ finite and $|\mathrm{Self}(M)| \le |Y|/2$. Remark `rem:clause4` records that the threshold is conventional and that every use needs only the two ends of the comparison. Corollary `cor:pnondegen`'s verification is rewritten to be honest that clause 4 is *assumed* of Picard, not verified.

### M5. The branch SIC is not a SIC
**Location:** Part I, definition preceding Theorem `thm:branchsoundness` (§5)

$M_b$ is defined by "whose stage-$m$ state on input $\Gamma$ is $p_m$" — but a branch $b$ is generated from one input $\Gamma$, while Definition `def:sic` requires $C$ total on $\mathcal{P}(Y) \times \mathbf{N}^+$. $M_b$ is undefined at every other input, so Theorem `thm:branchsoundness`'s appeal to the rule-driven soundness proposition (which quantifies over SICs) is not licensed.

**Fix applied.** $M_b$ now idles on inputs other than $\Gamma$, which is vacuously rule-driven.

---

## Minor — proofs that are right but argued wrongly

### m6. The transfinite distinctness induction is circular
**Location:** Part II, Proposition `prop:transdistinct`

The induction is on $\max(\alpha,\alpha')$. At the limit case it needs $\theta_\lambda \notin \{\theta_\beta : \beta<\lambda\}$, and cites "the inductive hypothesis applied below $\lambda$" — but distinguishing $\theta_\lambda$ from a *limit* $\theta_\mu$ with $\mu<\lambda$ has $\max = \lambda$, which is the case being proved. The conclusion is true; the induction as organised does not establish it.

**Fix applied.** Restructured as an induction on the initial segment: $S(\delta)$ = "the $\theta_\alpha$ for $\alpha<\delta$ are pairwise distinct," with successor and limit cases separated. A parenthetical notes why the $\max$ induction fails.

### m7. "Derived" where "provable" is meant
**Location:** Part II, Theorem `thm:reflclosure`, provability-soundness paragraph

The proof says every $\Pr$-formula in $Y$ arises as $\nu(\psi)$ "for some *derived* $\psi$," concluding "$\psi$ was derived; hence $R \vdash \varphi$." But $\nu(a) = \Pr(\langle R\rangle,\langle a\rangle)$ lies in $Y$ and is proved by $R$, while its argument $a$ is the hypothesis and is derived by no rule. Provability soundness asks for provability, not derivedness, so the theorem is fine — the word is just wrong, and the wrong word makes the step look false.

**Fix applied.** Restated with the counterexample noted explicitly.

### m8. An unused hypothesis
**Location:** Part I, proposition characterising inference-closure by $D_F(W)=W$ (§1)

Stated for $W \subseteq Y$ with $Y$ inference-closed. $Y$ is never used; the result holds for any $W \subseteq y$.

**Fix applied.** Hypothesis dropped.

### m9. Stale version references
**Location:** Part I, Conclusion and Abstract

The Conclusion of a Version 45 document opens "Version 44 separates four mathematically different comparison notions," and continues to narrate in version-relative terms throughout. The Abstract mixes "Version 44 separates three simulation notions" with the four-way separation actually presented.

**Fix applied.** Rewritten in document-relative terms.

### m10. Uncited bibliography entries
**Location:** Part I, bibliography

`buss1998`, `fitting1996`, `harrison2009` are listed but never cited — the same defect the Version 45 changelog claims to have repaired for `cookreckhow1979` and `haken1985`.

**Fix applied.** Cited at the proof-theory background (§1) and the ATP implementation remark (§6).

---

## Checked and correct

Worth recording, since these are the places an error would most likely hide:

- **One-stage-delay obstruction** (`thm:delayobstruction`) — both directions verified, including the $f(p) = f(p) \cup \{a\} = \{a\}$ step added in v43.
- **Depth-spectrum refutation** (`thm:depthspectrumfailure`) — clocks $\rho,\sigma$ verified admissible; $\tau_M(\{b\},a)=2 \ne 3=\tau_N(\{b\},a)$; the static pair $M_0,M_1$ genuinely has identical spectra and genuinely fails clocked equivalence on halting, and recoding genuinely cannot repair it.
- **Picard machine** (`ex:picard`, `thm:picard`) — $r^t = r$, $F_P^t = F_P$, transaction count 2, truth preservation under the declared interpretation, and the mutual-certification symmetry all check out. The construction order (machine before interpretation) does avoid circularity, as claimed.
- **Two forms agree** (`thm:formaltransport` insight box) — the algebra is right, though the text says "multiplying through by $2^{P/h}/2^{P/h}$" where it divides numerator and denominator.
- **Strictness** (`thm:strictness`) — including the provability-soundness verification, which is the delicate part.
- **Cumulativity, dichotomy, level-$\omega$ attainment, monotonicity of $\mathrm{lev}$, the chain corollary** — all correct.
- **`thm:setequiv` and `cor:degnoninvariant`** — the renaming isomorphism now runs in the right direction (the v17.1 fix is sound), and the corollary is a genuinely nice result: an equivalence class can hold both a non-degenerate and a degenerate machine.
- **Proposition `prop:tegmarkeverylevel`** — the enlarged machine loses internal necessitation, but the proof never uses it, so the level computation stands.

---

## One structural observation, not an error

The self-awareness preorder compares machines via translations on *self-theories*, while the simulation preorder compares them via witnesses on *state spaces*. Proposition `prop:tagsim` bridges them only under hypotheses stated in prose ("simulates in a way that preserves tags and proof of self-descriptive formulas") rather than as a definition. It is the one junction between the two parts where the merged document still relies on an informal notion. Making "tag-preserving simulation" a definition — a clocked simulation $(f,\rho)$ together with an admissible translation $\tau$ satisfying a compatibility square — would let Proposition `prop:tagsim` and Corollary `cor:simlevel` be proved rather than asserted, and would answer question 6 of §16.7 outright instead of "under exactly these hypotheses." I did not attempt it; it is a genuine piece of new mathematics, not a repair.
