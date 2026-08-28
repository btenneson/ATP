# Predator 8.038 — Threshold Sensitivity Amendment

Date: 2026-08-28

This amendment is written before inspecting any run performed with the changed threshold.

## Change

The threshold for entering the group-inverse revision fallback is narrowed by half:

\[
\tau: 0.50 \longrightarrow 0.25.
\]

The revision rule remains

\[
R_a(T_a,c_a)=
\begin{cases}
\Phi_a(T_a,c_a), & D_a(T_a)\le \tau,\\
c_a^{-1}, & D_a(T_a)>\tau.
\end{cases}
\]

All other declared controls are to remain unchanged: target `prcon`; agents P1, P2, R1, R2, I1, I2, C1, C2; seeds 2301–2308; initial creativity coordinates 0.15 through 0.85 as previously assigned; 12,000 expansions per bounded phase; maximum depth 12; maximum open goals 8; opener cap 64; the same frozen `set.mm`; the same independent verifier requirement; and the same cooperative federation-wide halt after independently verified settlement.

## Important prediction under the current coarse diagnostic

The present real-target prototype maps a verified Phase-1 settlement to `D=0` and finite-resource `UNKNOWN` to `D=1`. Therefore the threshold change from 0.50 to 0.25 is not expected to alter any branch decision in this particular prototype:

- verified settlement: `D=0 <= 0.25`, so ordinary continuation / no revision;
- bounded UNKNOWN: `D=1 > 0.25`, so group-inverse revision fires.

Thus this run is a threshold-sensitivity control, not yet a test of a genuinely finer trigger boundary. If its revision decisions differ from the tau=0.50 run while all other controls are fixed, that would indicate an implementation or reproducibility issue rather than the intended mathematical effect of the narrower threshold.

A later experiment with a continuous or multi-level diagnostic `D(T)` would be required for values between 0.25 and 0.50 to become scientifically discriminating.
