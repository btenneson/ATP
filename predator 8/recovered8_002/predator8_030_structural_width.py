#!/usr/bin/env python3
"""Predator 8.030: explicit structural-future-width control for prcom.

Hypothesis under test
---------------------
For a proof-search state there is a minimum retained structural diversity D*
needed to preserve at least one proof-bearing future.  Below D* the useful
future is pruned; near D* search should be efficient; far above D* settlement
may remain reliable while extra work rises.

This experiment deliberately fixes control-awareness C=0 and replaces the
coarse imagination coordinate with one explicit width parameter D.  D caps the
number of structurally distinct successor classes retained from each expanded
state.  Primitive successors and shortcut-macro endpoints compete together.
Within a class only the best-priority representative is retained.

The structural class key is the same quotient idea used by 8.028/8.029: the
selected/current goal structure plus the multiset of remaining instantiated
goals, independent of proof-history depth.  Certificate semantics are
unchanged: every primitive Step remains in Node.trail and final certificates
are independently checked by Metamath.

Accounting
----------
* outer expansions: popped proof states (same convention as 8.029)
* macro-internal primitive applications: separately counted, not free
* retained structural width: exact per-expansion cap D
* generated and retained class counts: logged for empirical D_eff analysis
* proof steps: unchanged primitive certificate length
* wall-clock time: co-primary response
"""
from __future__ import annotations

import argparse
import inspect
import math
import sys

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S

MACRO_MAX_EXTRA = 2
MACRO_TOPK_PER_KIND = 8
MACRO_DECISION_DISCOUNT = 0.35
MACRO_MIN_H_GAIN = 0.10
MACRO_MIN_GUIDE = 0.20


def install_structural_width_controller(width: int):
    if width < 1:
        raise ValueError("structural width must be >= 1")

    src = inspect.getsource(S.adaptive_guided_selective)

    old_init = """    false_zeros = 0\n    seen = set()\n    t0 = time.perf_counter()\n"""
    new_init = """    false_zeros = 0\n    seen = set()\n    quotient_best_depth = {}\n    quotient_prunes = 0\n    quotient_improvements = 0\n    macro_attempts = 0\n    macro_successes = 0\n    macro_internal_steps = 0\n    macro_generated = 0\n    width_generated_classes = 0\n    width_retained_classes = 0\n    width_pruned_classes = 0\n    width_events = 0\n    t0 = time.perf_counter()\n"""

    old_key = """        key = (node.depth, \" \".join(gt.tokens()),\n               tuple(sorted(\" \".join(E.apply_sub(g, node.sub).tokens())\n                            for g, _, _ in rest)))\n        if key in seen:\n            continue\n        seen.add(key)\n"""
    new_key = """        # 8.028 structural transposition quotient.\n        structural_key = (\" \".join(gt.tokens()),\n                          tuple(sorted(\" \".join(E.apply_sub(g, node.sub).tokens())\n                                       for g, _, _ in rest)))\n        previous_depth = quotient_best_depth.get(structural_key)\n        if previous_depth is not None and node.depth >= previous_depth:\n            quotient_prunes += 1\n            if quotient_prunes <= 5 or quotient_prunes % 100 == 0:\n                say(\"      [QUOTIENT-PRUNE] count=%d depth=%d best_depth=%d classes=%d\"\n                    % (quotient_prunes, node.depth, previous_depth,\n                       len(quotient_best_depth)))\n            continue\n        if previous_depth is not None:\n            quotient_improvements += 1\n            say(\"      [QUOTIENT-IMPROVE] count=%d depth %d->%d classes=%d\"\n                % (quotient_improvements, previous_depth, node.depth,\n                   len(quotient_best_depth)))\n        quotient_best_depth[structural_key] = node.depth\n"""

    helper_anchor = """    while frontier and (exp + probe_used_total) < budget:\n"""
    helper = r'''    def state_structural_key(n):
        if not n.goals:
            return ("<closed>", ())
        gi = E.pick_goal(n.goals, n.sub)
        g0, _, _ = n.goals[gi]
        rem = n.goals[:gi] + n.goals[gi + 1:]
        g0 = E.apply_sub(g0, n.sub)
        return (" ".join(g0.tokens()),
                tuple(sorted(" ".join(E.apply_sub(g, n.sub).tokens())
                             for g, _, _ in rem)))

    def shortcut_extend(start_node):
        """Greedily extend one child by <= MACRO_MAX_EXTRA legal primitive steps."""
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
                # C is fixed at zero: H is observation, never priority pressure.
                edge2 = max(0.05, edge2)
                state_cost2 = 0.02 * len(succ2)
                local_cost2 = edge2 + state_cost2

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

    # Gather primitive and macro successors locally rather than immediately
    # pushing them.  After candidate generation, retain one best representative
    # from each structural class and then cap the number of classes at D.
    old_loop = """        for cand_score, (lab, ct, data) in chosen:\n"""
    new_loop = """        pending_structural = []\n        for cand_score, (lab, ct, data) in chosen:\n"""

    old_push = """            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))\n"""
    new_push = """            base_priority = priority + edge + state_cost\n            pending_structural.append((base_priority, tie, child, 'primitive'))\n\n            macro_child, macro_cost, macro_extra = shortcut_extend(child)\n            if macro_extra > 0 and macro_child is not child:\n                tie += 1\n                shortcut_priority = (base_priority +\n                                     MACRO_DECISION_DISCOUNT * macro_cost)\n                pending_structural.append((shortcut_priority, tie, macro_child, 'macro'))\n"""

    # In 8.019/8.029 the candidate loop is followed by the frontier memory guard.
    # Insert structural-class selection immediately before that guard.
    flush_anchor = """        if frontier_limit and len(frontier) > frontier_limit:\n"""
    flush = r'''        if pending_structural:
            width_events += 1
            by_class = {}
            for pri3, tie3, child3, kind3 in pending_structural:
                k3 = state_structural_key(child3)
                old3 = by_class.get(k3)
                if old3 is None or (pri3, tie3) < (old3[0], old3[1]):
                    by_class[k3] = (pri3, tie3, child3, kind3)
            classes3 = sorted(by_class.values(), key=lambda x: (x[0], x[1]))
            generated3 = len(classes3)
            retained3 = min(STRUCTURAL_WIDTH, generated3)
            width_generated_classes += generated3
            width_retained_classes += retained3
            width_pruned_classes += max(0, generated3 - retained3)
            if width_events <= 8 or width_events % 100 == 0:
                # Shannon effective width of the retained priority mass.  Lower
                # priority is better, so convert relative priority to softmax
                # mass using exp(-(p-p_min)).
                kept3 = classes3[:retained3]
                pmin3 = kept3[0][0]
                ws3 = [math.exp(-(x[0] - pmin3)) for x in kept3]
                z3 = sum(ws3) or 1.0
                ps3 = [w / z3 for w in ws3]
                entropy3 = -sum(p * math.log(p) for p in ps3 if p > 0.0)
                deff3 = math.exp(entropy3)
                say("      [STRUCTURAL-WIDTH] event=%d generated=%d retained=%d cap=%d D_eff=%.3f"
                    % (width_events, generated3, retained3, STRUCTURAL_WIDTH, deff3))
            for pri3, tie3, child3, kind3 in classes3[:retained3]:
                heapq.heappush(frontier, (pri3, tie3, child3))

        if frontier_limit and len(frontier) > frontier_limit:
'''

    for needle, repl, label in (
        (old_init, new_init, "init"),
        (old_key, new_key, "quotient"),
        (helper_anchor, helper, "helper"),
        (old_loop, new_loop, "candidate loop"),
        (old_push, new_push, "push"),
        (flush_anchor, flush, "flush"),
    ):
        if needle not in src:
            raise RuntimeError("8.019 source changed: %s patch anchor missing" % label)
        src = src.replace(needle, repl, 1)

    ns = {}
    exec(compile(src, "<8.030 structural-width adaptive_guided_selective>", "exec"),
         dict(S.__dict__,
              STRUCTURAL_WIDTH=int(width),
              MACRO_MAX_EXTRA=MACRO_MAX_EXTRA,
              MACRO_TOPK_PER_KIND=MACRO_TOPK_PER_KIND,
              MACRO_DECISION_DISCOUNT=MACRO_DECISION_DISCOUNT,
              MACRO_MIN_H_GAIN=MACRO_MIN_H_GAIN,
              MACRO_MIN_GUIDE=MACRO_MIN_GUIDE),
         ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]


def install_c0_profile(opener_cap: int):
    """Fix C=0 and use one constant exploratory profile across controller modes."""
    B = P.B
    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    # Use the successful I=5-style profile as a neutral generator.  D, not the
    # profile, is the experimental width variable.  opener_cap is deliberately
    # generous so it does not become the binding width constraint.
    def fixed_profile(E, mode, creativity=0.55, cap=48):
        return E.Profile("structural-width-C0",
                         1.60, 0.95, 0.75, 0.10, 0.85,
                         max(int(opener_cap), 160), 1.0)

    B.make_mode_profile = fixed_profile
    for mode in ("native", "high", "low"):
        B.COORD[mode] = (0, 0)
        B.H_WEIGHT[mode] = 0.0
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
    gate.add_argument("--structural-width", type=int, required=True)
    ns, rest = gate.parse_known_args()
    if ns.structural_width < 1:
        gate.error("--structural-width must be >= 1")

    # Keep this wider than every tested D so raw opener truncation does not
    # determine the result before structural quotienting does.
    restore = install_c0_profile(160)
    install_structural_width_controller(ns.structural_width)
    try:
        sys.argv = [sys.argv[0]] + rest
        return P.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
