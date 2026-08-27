#!/usr/bin/env python3
"""Predator 8.020: 16-cell prcom awareness grid with Schroeder-flow guidance.

Controlled intervention relative to predator8_019_awareness_grid.py:

* Same theorem (prcom), historical set.mm, trained model, seed, global budget,
  brute reserve, max depth/open limits, creativity, opener cap, probe limits,
  frontier limit, fixed awareness coordinates, exactifier, bailout logic,
  admissible proof moves, candidate-zero gate, certificate emission, and
  independent external Metamath verification.
* Same 16 awareness cells C,I in {0,2,4,5}^2.
* C=0 remains an exact search-order baseline: no H or Schroeder term affects
  frontier ordering.
* For C>0, retain the original local H-descent reward and add a bounded
  Schroeder contraction-margin term.

The scalar fine coordinate is

    Phi(x) = 0                                      if x is closed,
             H_hat(x) - (1 + number_of_open_goals) otherwise.

With the current H_hat this isolates the token/meta-variable complexity above
its discrete open-goal floor, giving the contraction controller finer local
resolution than H_hat alone while leaving H_hat itself unchanged.

The target multiplier is fixed across the whole grid at

    lambda = 2^(-1/2) ~= 0.70710678.

Thus an ideal ten-step contraction has lambda^10 = 1/32.  This is an
engineering target for the ~10-expansion experiment, not a claim that the true
fixed-point multiplier has already been identified.  The experiment asks
whether adding this contraction field to the already-successful local descent
improves search ordering.  A later experiment can estimate/learn Phi and the
fixed-point multiplier from independent trajectories.

For a legal edge x->y, define the normalized contraction margin

    M(x,y) = (lambda*Phi(x) - Phi(y)) / max(Phi(x), eps).

M>0 means the move contracts at least as strongly as the target law;
M=0 matches the target multiplier; M<0 under-contracts.  The edge cost gets a
bounded reward proportional to tanh(M).  Over-contraction, including a closed
successor with Phi=0, is rewarded rather than penalized.  This avoids the bad
behavior of an absolute residual |Phi(y)-lambda Phi(x)| at the settlement
boundary.

CRITICAL ZERO RULE: H_hat=0 is only a candidate event.  The unchanged 8.019
candidate gate must certify the reconstructed proof, and any emitted proof is
independently checked by Metamath.  FALSE-ZERO events continue search.
"""
from __future__ import annotations

import inspect

import predator8_019_awareness_grid as A
import predator8_019_selective_sink as S


OLD_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n    last_global_improve = 0\n'''
NEW_INIT = '''    best_h = B.h_hat(E, start.goals, start.sub)\n\n    # Fine settlement coordinate for the Schroeder controller.  The discrete\n    # open-goal floor remains in H_hat; Phi isolates the continuous-valued\n    # token/meta complexity above that floor.\n    SCHRODER_LAMBDA = 2.0 ** -0.5\n    SCHRODER_WEIGHT_RATIO = 0.50\n    SCHRODER_EPS = 1e-12\n\n    def schroder_phi(goals, sub):\n        if not goals:\n            return 0.0\n        return max(0.0, B.h_hat(E, goals, sub) - (1.0 + len(goals)))\n\n    start_phi = schroder_phi(start.goals, start.sub)\n    say("    [SCHRODER-FLOW] lambda=%.8f phi0=%.6f weight_ratio=%.2f "\n        "(C=0 is untouched baseline)"\n        % (SCHRODER_LAMBDA, start_phi, SCHRODER_WEIGHT_RATIO))\n    last_global_improve = 0\n'''

OLD_CURH = '''        curh = B.h_hat(E, node.goals, node.sub)\n'''
NEW_CURH = '''        curh = B.h_hat(E, node.goals, node.sub)\n        curphi = schroder_phi(node.goals, node.sub)\n'''

OLD_EDGE = '''            if B.H_WEIGHT[mode] > 0.0:\n                delta = curh - B.h_hat(E, successor_goals, s2)\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n'''
NEW_EDGE = '''            if B.H_WEIGHT[mode] > 0.0:\n                # Preserve the original first discrete directional derivative\n                # reward: positive delta means local H descent.\n                successor_h = B.h_hat(E, successor_goals, s2)\n                delta = curh - successor_h\n                edge -= B.H_WEIGHT[mode] * math.tanh(delta)\n\n                # Add a Schroeder contraction field on the finer Phi coordinate.\n                # Use a signed margin rather than absolute residual so a move\n                # that contracts faster than lambda (especially settlement) is\n                # never penalized for overshooting the target contraction rate.\n                successor_phi = schroder_phi(successor_goals, s2)\n                if curphi > SCHRODER_EPS:\n                    contraction_margin = (\n                        SCHRODER_LAMBDA * curphi - successor_phi\n                    ) / max(curphi, SCHRODER_EPS)\n                    sch_weight = SCHRODER_WEIGHT_RATIO * B.H_WEIGHT[mode]\n                    edge -= sch_weight * math.tanh(contraction_margin)\n'''


def install_schroder_policy():
    src = inspect.getsource(S.adaptive_guided_selective)
    replacements = (
        (OLD_INIT, NEW_INIT),
        (OLD_CURH, NEW_CURH),
        (OLD_EDGE, NEW_EDGE),
    )
    for old, new in replacements:
        if src.count(old) != 1:
            raise RuntimeError(
                "8.019 source no longer matches controlled Schroeder-flow patch"
            )
        src = src.replace(old, new, 1)

    ns = {}
    exec(compile(src, __file__ + ":patched", "exec"), S.__dict__, ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]
    print("[SCHRODER-FLOW] installed local-delta-H + contraction-margin guidance")
    print("[SCHRODER-FLOW] lambda=2^(-1/2); verifier zero-gate unchanged")


def main():
    install_schroder_policy()
    return A.main()


if __name__ == "__main__":
    raise SystemExit(main())
