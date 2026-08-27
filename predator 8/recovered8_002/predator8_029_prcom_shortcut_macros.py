#!/usr/bin/env python3
"""Predator 8.029: quotient-aware ML-guided shortcut-macro prcom experiment.

This experiment keeps the 8.028 structural transposition quotient and the
8.019 verifier-gated controller, but augments the primitive action set with
bounded *verified macro-transition candidates*.  A macro is formed by taking
an ordinary legal child and greedily extending it by at most two additional
verifier-legal primitive inference steps selected by the same frozen ML policy
and H guidance used by the baseline controller.  The primitive child is still
enqueued, so the ordinary action set remains available; the macro endpoint is
added as an extra shortcut candidate.

Important accounting distinction:
  * proof cost is unchanged: every primitive step remains in Node.trail and the
    emitted certificate is independently checked by the same Metamath verifier;
  * search expansions count outer proof-state expansions, exactly as in 8.028;
  * macro-internal primitive applications are reported separately and are not
    silently treated as free computation;
  * wall-clock time is therefore a co-primary experimental response.

This is an architecture experiment, not yet the widened-corpus training phase.
It asks whether the existing learned policy becomes substantially more useful
when it is allowed to propose short structural proof fragments rather than only
one primitive theorem application at a time.

Awareness grid is unchanged from 8.028:
  C in {0,2,4,5}
  I in {3,5,6}
  five fixed seeds in the workflow.
"""
from __future__ import annotations

import argparse
import inspect
import sys

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S

ALLOWED_C = {0, 2, 4, 5}
ALLOWED_I = {3, 5, 6}

# One ordinary step plus at most two internal steps gives a macro spanning at
# most three primitive inferences.  If the architecture is useful, a roughly
# 28-step certificate could in principle be navigated in ~10 outer decisions.
MACRO_MAX_EXTRA = 2
MACRO_TOPK_PER_KIND = 8
MACRO_DECISION_DISCOUNT = 0.35
MACRO_MIN_H_GAIN = 0.10
MACRO_MIN_GUIDE = 0.20


def install_shortcut_controller():
    """Patch 8.019 with the 8.028 quotient plus bounded macro transitions."""
    src = inspect.getsource(S.adaptive_guided_selective)

    old_init = """    false_zeros = 0\n    seen = set()\n    t0 = time.perf_counter()\n"""
    new_init = """    false_zeros = 0\n    seen = set()\n    quotient_best_depth = {}\n    quotient_prunes = 0\n    quotient_improvements = 0\n    macro_attempts = 0\n    macro_successes = 0\n    macro_internal_steps = 0\n    macro_generated = 0\n    t0 = time.perf_counter()\n"""

    old_key = """        key = (node.depth, \" \".join(gt.tokens()),\n               tuple(sorted(\" \".join(E.apply_sub(g, node.sub).tokens())\n                            for g, _, _ in rest)))\n        if key in seen:\n            continue\n        seen.add(key)\n"""
    new_key = """        # 8.028 structural transposition quotient.\n        structural_key = (\" \".join(gt.tokens()),\n                          tuple(sorted(\" \".join(E.apply_sub(g, node.sub).tokens())\n                                       for g, _, _ in rest)))\n        previous_depth = quotient_best_depth.get(structural_key)\n        if previous_depth is not None and node.depth >= previous_depth:\n            quotient_prunes += 1\n            if quotient_prunes <= 5 or quotient_prunes % 100 == 0:\n                say(\"      [QUOTIENT-PRUNE] count=%d depth=%d best_depth=%d classes=%d\"\n                    % (quotient_prunes, node.depth, previous_depth,\n                       len(quotient_best_depth)))\n            continue\n        if previous_depth is not None:\n            quotient_improvements += 1\n            say(\"      [QUOTIENT-IMPROVE] count=%d depth %d->%d classes=%d\"\n                % (quotient_improvements, previous_depth, node.depth,\n                   len(quotient_best_depth)))\n        quotient_best_depth[structural_key] = node.depth\n"""

    helper_anchor = """    while frontier and (exp + probe_used_total) < budget:\n"""
    helper = r'''    def shortcut_extend(start_node):
        """Greedily extend one child by <= MACRO_MAX_EXTRA legal primitive steps.

        This is not counted as an outer expansion.  The work is accounted in
        macro counters and, crucially, in wall-clock time.  The returned node
        retains every primitive Step in its trail, so certificate semantics are
        unchanged.
        """
        nonlocal tie, macro_attempts, macro_successes, macro_internal_steps
        nonlocal macro_generated

        cur = start_node
        added_cost = 0.0
        labels = []
        h0 = B.h_hat(E, cur.goals, cur.sub) if cur.goals else 0.0

        for _ in range(MACRO_MAX_EXTRA):
            if (not cur.goals or cur.depth >= max_depth or
                    len(cur.goals) > max_open or Q._blocked(cur, blocked_prefixes)):
                break

            macro_attempts += 1
            gi2 = E.pick_goal(cur.goals, cur.sub)
            gt2, slot2, hix2 = cur.goals[gi2]
            rest2 = cur.goals[:gi2] + cur.goals[gi2 + 1:]
            gt2 = E.apply_sub(gt2, cur.sub)

            closers2, openers2 = index.candidates(gt2)
            mlw2 = B.ML_WEIGHT[mode]
            sc_c2 = [mlw2 * x for x in policy.rank(gt2, closers2)] if closers2 else []
            sc_o2 = [mlw2 * x for x in policy.rank(gt2, openers2)] if openers2 else []
            ranked_c2 = E._candidate_scores(gt2, closers2, sc_c2, profile, rng,
                                            local_use, shared_use)
            ranked_o2 = E._candidate_scores(gt2, openers2, sc_o2, profile, rng,
                                            local_use, shared_use)
            pool2 = (ranked_c2[:MACRO_TOPK_PER_KIND] +
                     ranked_o2[:MACRO_TOPK_PER_KIND])
            if not pool2:
                break

            curh2 = B.h_hat(E, cur.goals, cur.sub)
            best = None

            for cand_score2, (lab2, ct2, data2) in pool2:
                m2 = {}
                c22 = E.rename_apart(ct2, m2)
                s22 = E.unify(c22, gt2, cur.sub)
                if s22 is None:
                    continue
                _, f_hyps2, e_hyps2, _ = data2
                fmap2 = {var: m2.get(var, E.fresh(tc)) for _, tc, var in f_hyps2}
                for _, tc, var in f_hyps2:
                    m2.setdefault(var, fmap2[var])
                step2 = E.Step(lab2, fmap2, data2)
                newgoals2 = []
                ok2 = True
                for hj2, (_, stat2) in enumerate(e_hyps2):
                    try:
                        ht2 = E.G.parse(stat2[1:], "wff", index.by_tc)
                    except (RecursionError, E.MMError):
                        ht2 = None
                    if ht2 is None:
                        ok2 = False
                        break
                    newgoals2.append((E.rename_apart(ht2, m2), step2, hj2))
                if not ok2:
                    continue

                succ2 = newgoals2 + rest2
                h_after2 = B.h_hat(E, succ2, s22) if succ2 else 0.0
                delta2 = curh2 - h_after2
                guide2 = math.tanh(cand_score2 / 2.0)
                edge2 = (0.25 if not e_hyps2 else 1.0) - 0.20 * guide2
                if B.H_WEIGHT[mode] > 0.0:
                    edge2 -= B.H_WEIGHT[mode] * math.tanh(delta2)
                edge2 = max(0.05, edge2)
                state_cost2 = 0.02 * len(succ2)
                local_cost2 = edge2 + state_cost2

                # A macro is deliberately high-confidence: accept a possible
                # internal step only if the learned score is positive enough,
                # H decreases enough, or the step closes the selected goal.
                confident2 = (delta2 >= MACRO_MIN_H_GAIN or
                              guide2 >= MACRO_MIN_GUIDE or
                              not e_hyps2)
                if not confident2:
                    continue

                child2 = E.Node(succ2, s22,
                                cur.trail + ((slot2, hix2, step2),),
                                cur.depth + 1)
                if Q._blocked(child2, blocked_prefixes):
                    continue
                rank_key = (local_cost2, -delta2, -guide2)
                if best is None or rank_key < best[0]:
                    best = (rank_key, child2, lab2, local_cost2, delta2)

            if best is None:
                break

            _, cur, chosen_lab, chosen_cost, _ = best
            local_use[chosen_lab] += 1
            shared_use[chosen_lab] += 1
            labels.append(chosen_lab)
            added_cost += chosen_cost
            macro_internal_steps += 1

        if labels:
            macro_successes += 1
            macro_generated += 1
            h1 = B.h_hat(E, cur.goals, cur.sub) if cur.goals else 0.0
            if macro_generated <= 8 or macro_generated % 100 == 0:
                say("      [SHORTCUT-MACRO] count=%d extra_steps=%d H=%.3f->%.3f labels=%s"
                    % (macro_generated, len(labels), h0, h1, "/".join(labels)))
            return cur, added_cost, len(labels)
        return start_node, 0.0, 0

    while frontier and (exp + probe_used_total) < budget:
'''

    old_push = """            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))\n"""
    new_push = """            base_priority = priority + edge + state_cost\n            # Preserve the primitive action exactly as in 8.028.\n            heapq.heappush(frontier, (base_priority, tie, child))\n\n            # Add an ML-guided macro endpoint as an *extra* action.  Its trail\n            # contains all primitive proof steps, but only the endpoint becomes\n            # another frontier state.  Discount applies only to search ordering,\n            # not to certificate/proof cost.\n            macro_child, macro_cost, macro_extra = shortcut_extend(child)\n            if macro_extra > 0 and macro_child is not child:\n                tie += 1\n                shortcut_priority = (base_priority +\n                                     MACRO_DECISION_DISCOUNT * macro_cost)\n                heapq.heappush(frontier,\n                               (shortcut_priority, tie, macro_child))\n"""

    if old_init not in src:
        raise RuntimeError("8.019 source changed: init patch anchor missing")
    if old_key not in src:
        raise RuntimeError("8.019 source changed: quotient patch anchor missing")
    if helper_anchor not in src:
        raise RuntimeError("8.019 source changed: helper insertion anchor missing")
    if old_push not in src:
        raise RuntimeError("8.019 source changed: push patch anchor missing")

    src = src.replace(old_init, new_init, 1)
    src = src.replace(old_key, new_key, 1)
    src = src.replace(helper_anchor, helper, 1)
    src = src.replace(old_push, new_push, 1)

    # Add macro accounting to the periodic progress line without changing the
    # controller's semantics.
    old_progress_tail = """                   _utility(ast) if ast is not None else 0.0,\n                   time.perf_counter() - t0))\n"""
    # Leave the existing progress line intact if the exact formatting changes;
    # dedicated [SHORTCUT-MACRO] records plus wall time remain sufficient.

    ns = {}
    exec(compile(src, "<8.029 shortcut-patched adaptive_guided_selective>", "exec"),
         dict(S.__dict__,
              MACRO_MAX_EXTRA=MACRO_MAX_EXTRA,
              MACRO_TOPK_PER_KIND=MACRO_TOPK_PER_KIND,
              MACRO_DECISION_DISCOUNT=MACRO_DECISION_DISCOUNT,
              MACRO_MIN_H_GAIN=MACRO_MIN_H_GAIN,
              MACRO_MIN_GUIDE=MACRO_MIN_GUIDE),
         ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]


def install_fixed_pair(c: int, i: int):
    B = P.B
    if c not in ALLOWED_C or i not in ALLOWED_I:
        raise ValueError("C must be one of 0,2,4,5 and I one of 3,5,6")

    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    def fixed_profile(E, mode, creativity=0.55, opener_cap=48):
        if i == 3:
            return original_profile(E, "native", creativity, opener_cap)
        if i == 5:
            return E.Profile("imagination-(%d,5)" % c,
                             1.60, 0.95, 0.75, 0.10, 0.85,
                             max(96, opener_cap), 1.0)
        return E.Profile("imagination-(%d,6)" % c,
                         1.85, 1.10, 0.90, 0.08, 1.00,
                         max(128, opener_cap), 1.0)

    B.make_mode_profile = fixed_profile
    for mode in ("native", "high", "low"):
        B.COORD[mode] = (c, i)
        B.H_WEIGHT[mode] = 0.10 * c
        B.ML_WEIGHT[mode] = 1.0
    B.COORD["brute"] = (0, 0)

    def restore():
        B.make_mode_profile = original_profile
        B.COORD.clear(); B.COORD.update(old_coord)
        B.H_WEIGHT.clear(); B.H_WEIGHT.update(old_h)
        B.ML_WEIGHT.clear(); B.ML_WEIGHT.update(old_ml)

    return restore


def main():
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("--control-awareness", type=int, required=True)
    gate.add_argument("--imagination-awareness", type=int, required=True)
    ns, rest = gate.parse_known_args()

    install_shortcut_controller()
    restore = install_fixed_pair(ns.control_awareness, ns.imagination_awareness)
    print("[SHORTCUT] 8.029 quotient + ML-guided verified macro architecture ENABLED")
    print("[SHORTCUT] primitive child retained; macro endpoint added; max span=3 primitive steps")
    print("[SHORTCUT] macro internal work is NOT counted as outer expansions; compare wall time")
    print("[QUOTIENT] 8.028 structural-depth dominance retained")
    print("[AWARENESS-GRID] fixed guided pair (C,I)=(%d,%d)" %
          (ns.control_awareness, ns.imagination_awareness))
    print("[AWARENESS-GRID] guided H_WEIGHT=%.2f; brute fallback=(0,0); verifier unchanged" %
          (0.10 * ns.control_awareness))
    try:
        sys.argv = [sys.argv[0]] + rest
        return S.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
