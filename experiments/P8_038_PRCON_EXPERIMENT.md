# Predator 8.038 — `prcon` Revision-Fallback Experiment

## Purpose

Test the eight-agent revision mechanism on a real `set.mm` theorem target (`prcon`) rather than only on the architecture-level synthetic mechanism test.

This experiment asks whether a search agent that appears stuck under its current creativity/search-control setting can benefit from a mathematically defined revision fallback.

## Agents

Eight agents are used:

- `P1`, `P2`
- `R1`, `R2`
- `I1`, `I2`
- `C1`, `C2`

For this prototype all eight agents invoke the same sound theorem-proving engine on the same formal target. The P/R/I/C labels preserve the eight-agent AMLD federation identities; they do **not** change the theorem statement or verifier semantics in this first `prcon` prototype.

## Protected verification invariant

The verifier is not a knob.

\[
V(z)=1
\]

throughout every admitted result. Search-control revision may change search order, creativity, exploration, novelty, rarity, or related control coordinates, but it may never weaken proof verification.

A theorem settlement is counted only if an emitted Metamath certificate is accepted by the verifier. An unverified candidate is not admitted as a successful state and is not treated as mathematical truth.

## Revision rule

Each agent has a search-control vector `c_a` whose coordinates are declared as group-valued knobs. In the current prototype the main active scalar creativity coordinate is modeled with the logit-addition group on `(0,1)`, whose inverse is

\[
c^{-1}=1-c.
\]

The general controller rule is

\[
R_a(T_a,c_a)=
\begin{cases}
\Phi_a(T_a,c_a), & D_a(T_a)\le \tau_a,\\
c_a^{-1}, & D_a(T_a)>\tau_a.
\end{cases}
\]

Here `Phi_a` is the ordinary optimality-seeking continuation and `D_a(T_a)` is a diagnostic of whether the current search trajectory is failing or stuck.

## `prcon` prototype interpretation of `T` and `D(T)`

For this first real-target experiment, `T_a` is defined at the level of completed bounded search attempts rather than internal unverified proof nodes.

A phase is therefore a sound bounded experiment:

1. run agent `a` on `prcon` with a declared creativity value, seed, depth/open-goal controls, and expansion budget;
2. if a verified certificate is produced, record settlement and stop that agent;
3. if the bounded phase returns finite-resource `UNKNOWN`, treat the phase as evidence of search failure/stagnation for the purpose of the fallback diagnostic;
4. if `D(T)>tau`, revise the creativity coordinate by its group inverse and run the second phase;
5. count success only after Metamath verification.

For the initial prototype, a first-phase finite-resource `UNKNOWN` is intentionally mapped above the fallback threshold, while a verified settlement maps below it. This is a coarse diagnostic and is being recorded explicitly as a prototype choice, not asserted as the final definition of `D(T)`.

## Experimental controls

Target: `prcon`

Formal environment: frozen `set.mm` revision already used by the Predator comparison workflows.

Search engine: Predator 8.001 backward-search semantics and certificate emission, with 8.038 supplying the per-agent revision controller.

The run record must preserve, per agent and per phase:

- agent identity;
- seed;
- initial creativity coordinate;
- revised creativity coordinate if fallback fires;
- expansion budget;
- maximum depth;
- maximum open goals;
- opener cap;
- return code;
- verified/unknown/protocol-failure outcome;
- whether revision fired;
- emitted certificate path if any;
- independent verifier result;
- expansions and elapsed time when available.

## Scientific comparison

The immediate question is not merely whether the mechanism executes correctly; that was already established by the 8.038 architecture test. The real-target question is:

> When an agent fails to settle `prcon` under its current search-control coordinate, does group-inverse revision provide a useful second basin of search under the same declared formal verifier?

The result should be reported without overclaiming. A successful second phase is evidence that inverse revision can rescue at least one bounded search configuration; failure is evidence only under the declared finite controls.

## Status

Protocol documented before interpreting the `prcon` result. The real-target run is prepared on branch `predator8-038-eight-agent-revision-fallback`.
