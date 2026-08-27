# PRCOM Structure Notes

*Two-Coordinate Compression of a Finite `prcom` Proof Bank*

**August 27, 2026**

## Abstract

A complete bounded search for the Metamath theorem `prcom`, asserting $\{A,B\}=\{B,A\}$, produced exactly four distinct externally verified certificates in the declared cap-8, depth-4, open-goal-8 search space. Direct inspection shows that the four proofs are governed by only two high-level binary decisions: a *route* coordinate describing where commutativity is introduced and an *orientation* coordinate describing the direction of the construction. These two bits recover the four proof skeletons, while the route bit alone recovers proof-step length. This note records the finite result and isolates the larger hypothesis it suggests: long formal proofs may sometimes be projections of a much smaller structural coordinate space.

# Experimental setting

Predator 8.027 exhaustively enumerated a declared finite proof-search
space for `prcom` with the following restrictions:
$$\text{candidate cap}=8,\qquad
\text{search depth}\le 4,\qquad
\text{open goals}\le 8.$$ All legal open-goal choices were considered.
Proof histories were not quotiented, frontier states were not pruned,
and search continued after every proof. The frontier exhausted
naturally, so completeness is valid *within this declared finite space*.

The run expanded $2{,}577$ nonterminal nodes and generated $48{,}224$
children. It encountered $10$ terminal candidates, which reduced to
exactly four distinct externally verified certificates after duplicate
certificate hashes were removed. Their basic measurements were:

| Certificate | First expansion $E$ | Steps | Raw bits | zlib-9 bits |
|:-----------:|:-------------------:|:-----:|:--------:|:-----------:|
| $C_1$ | 362 | 26 | 1368 | 544 |
| $C_2$ | 466 | 26 | 1368 | 536 |
| $C_3$ | 894 | 28 | 1416 | 512 |
| $C_4$ | 1782 | 28 | 1424 | 520 |

Thus the earliest certificate, the shortest-by-steps certificate class,
and the most compressible certificate need not coincide.

# The structural quotient

Inspection of the four proof strings reveals two proof families.

1. Commutativity is introduced through `equncomi`, after a use of the pair definition `df-pr`. The proof then closes with the two-equality transitivity rule `eqtr4i`. These certificates have $26$ proof steps.
2. Commutativity is introduced explicitly by `uncom` between the two singleton unions. Two copies of `df-pr` identify those unions with unordered pairs, and the proof closes by a three-equality transitivity rule, `3eqtr4i` or `3eqtr4ri`. These certificates have $28$ proof steps.

Inside either family there are two orientations corresponding to the two ways of interchanging $A$ and $B$. This motivates two binary coordinates:
$$R\in\{0,1\},\qquad O\in\{0,1\},$$
where $R$ records the route by which commutativity enters the proof and $O$ records orientation.

Concretely, let
$$R(C)=
\begin{cases}
0,&\text{if commutativity is introduced through `equncomi`,}\\
1,&\text{if commutativity is introduced through `uncom`,}
\end{cases}$$
and let $O(C)$ distinguish the two $A/B$ orientations within the chosen route. The four observed certificate skeletons are then represented by
$$(0,0),\ (0,1),\ (1,0),\ (1,1).$$

**Lemma 1 (Two-coordinate finite-bank lemma).** *Let $\mathcal B_8$ be the four distinct verified certificates produced by the complete cap-$8$, depth-$4$, open-goal-$8$ experiment for `prcom`. After quotienting away low-level syntactic construction tokens while retaining the high-level inference skeleton, the map*
$$C\longmapsto (R(C),O(C))$$
*is a bijection from the four observed proof skeletons to $\{0,1\}^2$. Moreover, the proof-step length satisfies*
$$\boxed{L_{\rm steps}(C)=26+2R(C).}$$
*Hence one binary coordinate determines proof-step length, and two binary coordinates determine the observed high-level proof skeleton.*

*Proof.* The four certificates were inspected directly. Exactly two contain the `equncomi` route and close with `eqtr4i`; both have $26$ steps. Exactly two contain the `uncom` route together with two uses of `df-pr` and close with `3eqtr4i` or `3eqtr4ri`; both have $28$ steps. Within each route the two certificates differ by the $A/B$ orientation. Therefore the four skeletons form the Cartesian product of two route values and two orientation values, proving the bijection and the length formula. $\square$

If coordinates are restricted to binary values, two bits are also information-theoretically minimal for lossless identification of four distinct skeletons, since
$$\log_2 4=2.$$
Thus, for this finite bank, the apparent $26$-$28$-step proof complexity reduces at the structural level to two binary decisions.

# Interpretation

The immediate lesson is not that ZFC itself has been reduced to two coordinates. The result is local and concerns one theorem in one explicitly bounded Metamath search space. What it does show is that a large syntactic proof tree can conceal a much smaller decision structure:
$$\boxed{
\text{large proof-search tree}
\longrightarrow
(R,O)
\longrightarrow
\text{verified certificate skeleton}.
}$$

This suggests a different program for automated theorem proving. Instead of searching proof histories directly, seek a coordinate map
$$\Phi(\varphi)=(q_1,\dots,q_d)$$
whose values determine, or strongly constrain, proof architecture. An exact analogue of the present finite result would be a family of theorems for which shortest proof length factors through a low-dimensional map,
$$L_{\min}(\varphi)=F\bigl(\Phi(\varphi)\bigr),$$
or for which the next inference is determined by a recurrence on those coordinates rather than by enumeration of the full proof tree.

# What remains open

Three claims must be kept separate.

1. **Established here:** the four certificates in the complete bounded `prcom` bank admit a two-binary-coordinate description of their high-level skeletons, and the route coordinate exactly determines their step length.
2. **Not established:** these coordinates reconstruct the exact chronological scheduler history. Six of the ten terminal histories were duplicate certificates, so certificate hashing intentionally discarded some history-level information.
3. **Research hypothesis:** similar low-dimensional coordinates recur across neighboring Metamath theorems and eventually across substantial regions of formalized set theory.

A decisive next experiment is therefore not merely a wider brute-force search on `prcom`. It is to repeat this structural quotient analysis across a family of nearby theorems and ask whether route, orientation, transitivity depth, definitional expansion, and related coordinates recur. Repetition would begin to distinguish a one-theorem compression from a genuine local geometry of formal proof space.

# Experimental provenance

The data summarized here come from GitHub Actions run `33071432510`, workflow `Predator8 prcom finite exhaustive proof bank legalcap`, using Predator 8.027. The four certificate SHA-256 prefixes are `40145cceadc4`, `5d7712c87a23`, `77359fc638da`, and `e3e0c2b1e0e2`.
