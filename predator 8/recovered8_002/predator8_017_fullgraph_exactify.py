#!/usr/bin/env python3
"""Predator 8.017 full-goal exactification wrapper.

Search/navigation remains Predator 8.016.  Only the certification probe changes:
for a proof state with multiple open goals, the probe enumerates legal assertion
applications to every open goal, not only the goal selected by `pick_goal`.

Therefore probe bounds refer to the unrestricted open-goal-choice graph induced
by the same frozen Predator inference engine and strict pre-target assertion
prefix.  Heuristic search may still use `pick_goal`; certification does not.
"""
from __future__ import annotations

import predator8_016_prcom_exactify as P
from bounded_exactifier import bounded_bfs_exactify

VERSION = "8.017-ML-attention-fullgraph-exactify"


class FullGraphProbeContext(P.ProbeContext):
    """Probe context that branches over every currently open goal."""

    def all_successors(self, state: P.ProbeState):
        if state.accepted:
            return ()
        node = state.node
        if node is None:
            return ()
        E = self.E
        if not node.goals:
            if self.closed_verifies(node):
                return (P.ProbeState(None, True, node),)
            return ()

        out = []
        for gi in range(len(node.goals)):
            gt, slot, hix = node.goals[gi]
            rest = node.goals[:gi] + node.goals[gi + 1:]
            gt = E.apply_sub(gt, node.sub)
            closers, openers = self.index.candidates(gt)

            # Every assertion candidate compatible with the rigid conclusion
            # head is actually subjected to unification.  No ML/opener cap or
            # stochastic pruning is permitted inside certification.
            for lab, ct, data in closers + openers:
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
                        ht = E.G.parse(stat[1:], "wff", self.index.by_tc)
                    except (RecursionError, E.MMError):
                        ht = None
                    if ht is None:
                        ok = False
                        break
                    newgoals.append((E.rename_apart(ht, m), step, hj))
                if not ok:
                    continue
                out.append(P.ProbeState(
                    E.Node(newgoals + rest, s2,
                           node.trail + ((slot, hix, step),), node.depth + 1),
                    False, None))
        return out


def make_full_probe_context(E, index, mm, target_data, cutoff):
    fvar, fallback = P.B.formal_variables(E, mm, cutoff)
    return FullGraphProbeContext(E, index, mm, target_data, fvar, fallback)


def run_full_probe(ctx, node, max_depth: int, max_expansions: int,
                   max_next_layer: int = 30000):
    return bounded_bfs_exactify(
        P.ProbeState(node=node),
        all_successors=ctx.all_successors,
        is_settled=lambda s: bool(s.accepted),
        key=lambda s: s,  # identity: no proof-state quotient in certification
        max_depth=max_depth,
        max_expansions=max_expansions,
        max_next_layer=max_next_layer,
        completeness_evidence=(
            "every open-goal choice enumerated; all assertion-head-compatible "
            "candidates enumerated for each chosen goal and subjected to actual "
            "unification; no opener cap/ranker/policy pruning; proof histories "
            "not quotiented; terminal edge requires Metamath CV"
        ),
    )


def main():
    # Monkey-patch only the probe construction/exactification used by 8.016.
    # Guided search, model, budgets, verifier and controller remain unchanged.
    P.VERSION = VERSION
    P.make_probe_context = make_full_probe_context
    P.run_probe = run_full_probe
    return P.main()


if __name__ == "__main__":
    raise SystemExit(main())
