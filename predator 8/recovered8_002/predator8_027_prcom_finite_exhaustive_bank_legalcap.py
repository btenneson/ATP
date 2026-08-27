#!/usr/bin/env python3
"""Predator 8.027: prcom finite exhaustive proof bank with LEGAL-successor caps.

8.026 ranked/capped raw assertion candidates before unification.  The first
experiment therefore admitted an accidentally empty root space for prcom.
8.027 preserves 8.026 for auditability and changes exactly that definition:

    candidate_cap = top K *legal, successfully unified successors* per open goal.

K=0 means all legal successors in the strict pre-prcom prefix.  Everything else
about 8.026's finite exhaustive banking contract is retained: distinct proof
histories are not quotiented, verified terminal certificates are banked and
search continues, and completeness is claimed only after natural frontier
exhaustion inside the declared bounded space.
"""
from __future__ import annotations

import predator8_026_prcom_finite_exhaustive_bank as Base

VERSION = "8.027-prcom-finite-exhaustive-bank-legalcap"


def enumerate_children_legalcap(E, index, policy, node, max_open: int, candidate_cap: int):
    """Enumerate top-K LEGAL successors for every legal open-goal choice.

    The expensive legality test (rename-apart + unification + hypothesis parsing
    + max-open check) happens before the policy cap is applied.  Thus K no longer
    creates a vacuous space merely because highly ranked raw candidates fail to
    unify with the current goal.
    """
    out = []
    for gi in range(len(node.goals)):
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = E.apply_sub(gt, node.sub)
        closers, openers = index.candidates(gt)
        raw_items = list(closers) + list(openers)

        legal = []  # (raw assertion item, constructed child)
        for lab, ct, data in raw_items:
            m = {}
            c2 = E.rename_apart(ct, m)
            s2 = E.unify(c2, gt, node.sub)
            if s2 is None:
                continue

            _, f_hyps, e_hyps, _ = data
            fmap = {var: m.get(var, E.fresh(tc)) for _, tc, var in f_hyps}
            for _, tc, var in f_hyps:
                m.setdefault(var, fmap[var])
            step = E.Step(lab, fmap, data)

            newgoals = []
            ok = True
            for hj, (_, stat) in enumerate(e_hyps):
                try:
                    ht = E.G.parse(stat[1:], "wff", index.by_tc)
                except (RecursionError, E.MMError):
                    ht = None
                if ht is None:
                    ok = False
                    break
                newgoals.append((E.rename_apart(ht, m), step, hj))
            if not ok:
                continue

            successor_goals = newgoals + rest
            if len(successor_goals) > max_open:
                continue

            child = E.Node(
                successor_goals,
                s2,
                node.trail + ((slot, hix, step),),
                node.depth + 1,
            )
            legal.append(((lab, ct, data), child))

        if candidate_cap > 0 and len(legal) > candidate_cap:
            items = [item for item, _ in legal]
            scores = policy.rank(gt, items)
            scored = list(zip(scores, legal))
            # Larger frozen-policy score is better.  The theorem label is a
            # deterministic secondary key, matching the original experiment.
            scored.sort(key=lambda p: (-float(p[0]), p[1][0][0]))
            legal = [pair for _, pair in scored[:candidate_cap]]

        out.extend(child for _, child in legal)
    return out


def main():
    # Monkey-patch only the candidate-space definition while reusing the audited
    # 8.026 banking/verifier/completeness machinery.
    Base.VERSION = VERSION
    Base.enumerate_children = enumerate_children_legalcap
    return Base.main()


if __name__ == "__main__":
    raise SystemExit(main())
