#!/usr/bin/env python3
"""Predator 8.002C: settlement-distance compass front-end for Predator 8.001.

This variant changes search control, not proof semantics.  The target proof is
never read.  Every successful result is still emitted as a Metamath
certificate and checked by the same verifier.

The control objective is the unit-cost settlement value r*(x): the minimum
number of further verified search actions needed to reach a terminal proof
state.  Exact r* is unavailable on a hard target, so 8.002C uses an explicit
blind surrogate r_hat on successor proof-search states and makes that quantity
the primary best-first control signal.  Creativity/novelty survives only as a
secondary tie-break/exploration mechanism.

This is an experimental implementation of the settlement-compass control law,
not a claim that r_hat already satisfies the < 1/2 theorem hypothesis.
"""
from __future__ import annotations

import heapq
import importlib.util
import math
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.001.py")
spec = importlib.util.spec_from_file_location("predator8_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.001 base module")
P8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P8)
P8.VERSION = "8.002C-settlement-compass"


def settlement_distance_hat(goals, sub):
    """Blind surrogate for optimal remaining unit-cost settlement distance.

    The dominant term is the number of currently open logical goals: every
    such goal must be discharged before the proof can settle.  Two bounded
    structural terms break ties using only the present formal state.

    No target proof, theorem-specific hint, or downstream proof data is read.
    """
    if not goals:
        return 0.0
    structural = 0.0
    metas = set()
    for g, _slot, _hix in goals:
        gg = P8.apply_sub(g, sub)
        # Each contribution is bounded, so open-goal count remains dominant.
        structural += math.tanh(gg.size() / 40.0)
        P8.n_metas(gg, sub, metas)
    return (float(len(goals))
            + 0.08 * structural
            + 0.02 * math.tanh(len(metas) / 8.0))


def _legacy_scores(goal, items, profile, rng, local_use, shared_use):
    """Keep 8.001 diversity as a secondary signal only."""
    ranked = P8._candidate_scores(
        goal, items, [0.0] * len(items), profile, rng, local_use, shared_use)
    return {item[0]: score for score, item in ranked}


def _pre_distance(rest_count, item):
    """Cheap successor-distance proxy used before expensive unification."""
    _lab, _ct, data = item
    e_hyps = data[2]
    token_burden = sum(max(0, len(stat) - 1) for _name, stat in e_hyps)
    return (rest_count + len(e_hyps)
            + 0.002 * min(250, token_burden))


def _select_openers(openers, rest_count, legacy, profile, rng):
    """Compass-first opener cap with a protected exploration tail."""
    if len(openers) <= profile.opener_cap:
        return list(openers)
    ordered = sorted(
        openers,
        key=lambda item: (_pre_distance(rest_count, item),
                          -legacy.get(item[0], 0.0), item[0]))
    cap = profile.opener_cap
    explore_n = min(cap - 1, int(round(cap * profile.exploration)))
    exploit_n = cap - explore_n
    chosen = list(ordered[:exploit_n])
    tail = ordered[exploit_n:]
    if explore_n and tail:
        chosen.extend(rng.sample(tail, min(explore_n, len(tail))))
    return chosen


def prove_compass(goal_tree, index, budget, max_depth, rank=None, say=print,
                  progress=2000, max_open=6, profile=None, seed=0,
                  shared_use=None, agent_name=None):
    """Best-first backward search controlled primarily by settlement distance.

    Frontier key is lexicographic with

        f_hat = g + r_hat(successor),

    followed by r_hat itself and then the old creativity score.  Thus the
    settlement-distance estimate is primary; creativity cannot overrule a
    better compass value, but it can diversify equal/near-equal states.
    """
    if profile is None:
        profile = P8.Profile("deterministic", 0.0, 0.0, 0.0, 0.0,
                             0.0, 48, 1.0)
    rng = random.Random(seed)
    local_use = defaultdict(int)
    if shared_use is None:
        shared_use = defaultdict(int)
    agent_name = agent_name or profile.name

    start = P8.Node([(goal_tree, None, 0)], {}, (), 0)
    start_h = settlement_distance_hat(start.goals, start.sub)
    # (f_hat, r_hat, -legacy, tie, g, node)
    frontier = [(start_h, start_h, 0.0, 0, 0.0, start)]
    exp = tie = 0
    seen = set()
    import time
    t0 = time.perf_counter()
    announced = False

    while frontier and exp < budget:
        _fhat, _rhat, _neglegacy, _, g_cost, node = heapq.heappop(frontier)
        exp += 1
        if not announced and say:
            say("      [%s] settlement compass active: primary key g + r_hat"
                % agent_name)
            announced = True
        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open goals, r_hat=%.3f, %.0fs"
                % (agent_name, f"{exp:,}", len(node.goals),
                   settlement_distance_hat(node.goals, node.sub),
                   time.perf_counter() - t0))

        if not node.goals:
            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            return (root, node.sub), exp
        if node.depth >= max_depth:
            continue
        if len(node.goals) > max_open:
            continue

        gi = P8.pick_goal(node.goals, node.sub)
        (gt, slot, hix) = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = P8.apply_sub(gt, node.sub)

        key = (node.depth, " ".join(gt.tokens()),
               tuple(sorted(" ".join(P8.apply_sub(g, node.sub).tokens())
                            for g, _, _ in rest)))
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        legacy_c = _legacy_scores(gt, closers, profile, rng,
                                  local_use, shared_use)
        legacy_o = _legacy_scores(gt, openers, profile, rng,
                                  local_use, shared_use)

        # Never cap closers: a unifying closer can settle the selected goal now.
        # Cap openers by estimated successor distance, with an exploration tail.
        chosen_openers = _select_openers(openers, len(rest), legacy_o,
                                         profile, rng)
        pick = [(legacy_c.get(item[0], 0.0), item) for item in closers]
        pick += [(legacy_o.get(item[0], 0.0), item)
                 for item in chosen_openers]
        pick.sort(key=lambda pair: (
            _pre_distance(len(rest), pair[1]), -pair[0], pair[1][0]))

        for legacy_score, (lab, ct, data) in pick:
            m = {}
            c2 = P8.rename_apart(ct, m)
            s2 = P8.unify(c2, gt, node.sub)
            if s2 is None:
                continue
            _, f_hyps, e_hyps, _ = data
            fmap = {var: m.get(var, P8.fresh(tc)) for _, tc, var in f_hyps}
            for _, tc, var in f_hyps:
                m.setdefault(var, fmap[var])
            step = P8.Step(lab, fmap, data)
            newgoals = []
            ok = True
            for hj, (_, stat) in enumerate(e_hyps):
                try:
                    ht = P8.G.parse(stat[1:], "wff", index.by_tc)
                except (RecursionError, P8.MMError):
                    ht = None
                if ht is None:
                    ok = False
                    break
                newgoals.append((P8.rename_apart(ht, m), step, hj))
            if not ok:
                continue

            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1
            successor_goals = newgoals + rest
            successor = P8.Node(
                successor_goals, s2,
                node.trail + ((slot, hix, step),),
                node.depth + 1)
            new_g = g_cost + 1.0
            rhat = settlement_distance_hat(successor_goals, s2)
            fhat = new_g + rhat
            # Legacy creativity is strictly secondary in the heap key.
            heapq.heappush(frontier,
                           (fhat, rhat, -legacy_score, tie, new_g, successor))
    return None, exp


# Replace only the search controller.  Parsing, proof emission, benchmark
# withholding, population budget accounting, and Metamath verification remain
# those of the audited 8.001 base.
P8.prove = prove_compass


def main():
    # The base CLI calls global prove/prove_population at runtime, so patching
    # P8.prove above switches both selftest and prove commands to the compass.
    return P8.main()


if __name__ == "__main__":
    main()
