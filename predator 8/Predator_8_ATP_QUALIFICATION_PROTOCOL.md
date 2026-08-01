# Predator 8 ATP qualification protocol

## Purpose

Qualify the frozen, untrained Predator 8.001 search core as a bounded automated
theorem prover before adding learned guidance. The question is not whether it
proves every benchmark. The question is whether its successes are produced by
target-blind proof search and independently checkable certificates, and whether
finite failures are reported honestly.

## ATP acceptance criteria

1. **Formal input only.** Search receives the target statement and assertions
   declared before it in the frozen Metamath environment.
2. **Target-proof denial.** Any attempt to read the target's stored reference
   proof raises an exception during qualification.
3. **Declaration-order isolation.** The external checker rejects every proof
   token not declared strictly before the target, including the target itself
   and all downstream theorems. The search grammar is independently rebuilt
   from that same strict pre-target prefix.
4. **Legal search.** Creativity may reorder or sample unification-compatible
   applications, but may not create inference rules or relax unification.
5. **Certificate output.** A successful search emits an explicit Metamath proof
   token sequence.
6. **Independent authority.** A fresh process importing the Metamath checker,
   but no Predator code, must accept the certificate.
7. **Honest bounded failure.** Exhaustion returns `unknown_under_bounds`; it is
   not a counterexample and produces no certificate.
8. **Metered resources.** The declared budget counts frontier-state expansion
   transactions globally across the population.
9. **Reproducibility.** The engine, environment, search limits, and random seed
   are recorded with cryptographic hashes.

## Order of development

1. Freeze the no-ML engine and formal environment.
2. Pass toy soundness, scheduler, and reproducibility checks.
3. Pass blind real-theorem controls with external certificate checking.
4. Compare 8.001 and 7.1 on identical frozen targets and resource limits.
5. Freeze a leakage-controlled training corpus.
6. Train policy/value guidance.
7. Compare guided and unguided conditions without changing the verifier or ATP
   acceptance criteria.

## Interpretation

An ATP may be heuristic and incomplete. Failure on `prcom`, HaloProof, or any
other target under finite limits does not make it a non-ATP. Conversely,
printing a plausible derivation does not make it an ATP success: only an
accepted certificate does.

The ML model will eventually rank legal transitions and estimate remaining
search cost. It will neither define theoremhood nor authorize a proof.
