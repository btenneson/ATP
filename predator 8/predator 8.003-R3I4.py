#!/usr/bin/env python3
"""Predator 8.003-R3I4: operational (3,4) reasoned-imagination controller.

This front-end preserves Predator 8.001 proof semantics and the 8.002C
settlement-compass baseline.  It changes search control only.

Operational coordinate used in this experiment
----------------------------------------------
R=3 (checked metacontrol, operational): the controller computes only observable
self-state facts from its own current search (best r_hat reached, expansions
since improvement, and duplicate-state rate), checks those facts by
recomputation from the live search state, and uses them to change how the
lower-level compass is deployed.  This is NOT claimed to be a fully arithmetized
Prf_M/Prov_M reflection hierarchy.

I=4 (reasoned FUTUREBANK imagination): before ranking the strongest successor
candidates, the controller simulates up to four further legal backward
Metamath assertion applications.  Imagined steps must parse, unify with occurs
check, stay within the open-goal bound, and avoid repeated imagined states.
The imagined path is never deposited as a proof.  It only supplies a bounded
certificate-reachability signal to the search controller.

The target proof is never read.  No Halo-specific lemma list or route is coded.
A success is still a Metamath certificate emitted by Predator and accepted by
the independent verifier.
"""
from __future__ import annotations

import heapq
import importlib.util
import math
import os
import random
import time
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
COMPASS_PATH = os.path.join(HERE, "predator 8.002-compass.py")
spec = importlib.util.spec_from_file_location("predator8_compass", COMPASS_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.002C compass module")
COMP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(COMP)
P8 = COMP.P8
P8.VERSION = "8.003-R3I4-operational"

IMAGINATION_DEPTH = 4


def _state_signature(goals, sub):
    """Canonical-enough live/imagination signature for cycle rejection."""
    return tuple(sorted(
        " ".join(P8.apply_sub(g, sub).tokens()) for g, _slot, _hix in goals
    ))


def _imagined_successors(goals, sub, index, max_open, branch_cap):
    """Generate a small target-generic set of legal imagined successors.

    This is a FUTUREBANK operation: it does not attach Step objects to the real
    proof trail and it does not change BANK/verification state.
    """
    if not goals:
        return []
    gi = P8.pick_goal(goals, sub)
    gt, _slot, _hix = goals[gi]
    rest = goals[:gi] + goals[gi + 1:]
    gt = P8.apply_sub(gt, sub)
    closers, openers = index.candidates(gt)

    ordered_openers = sorted(
        openers,
        key=lambda item: (COMP._pre_distance(len(rest), item), item[0]))
    pick = list(closers) + ordered_openers[:max(1, int(branch_cap))]

    out = []
    for lab, ct, data in pick:
        m = {}
        c2 = P8.rename_apart(ct, m)
        s2 = P8.unify(c2, gt, sub)
        if s2 is None:
            continue
        _dv, f_hyps, e_hyps, _concl = data
        fmap = {var: m.get(var, P8.fresh(tc)) for _fh, tc, var in f_hyps}
        for _fh, tc, var in f_hyps:
            m.setdefault(var, fmap[var])

        newgoals = []
        ok = True
        for hj, (_ename, stat) in enumerate(e_hyps):
            try:
                ht = P8.G.parse(stat[1:], "wff", index.by_tc)
            except (RecursionError, P8.MMError):
                ht = None
            if ht is None:
                ok = False
                break
            newgoals.append((P8.rename_apart(ht, m), None, hj))
        if not ok:
            continue
        successor_goals = newgoals + rest
        if len(successor_goals) > max_open:
            continue
        out.append((successor_goals, s2, lab))
    return out


def reasoned_imagination4(goals, sub, index, max_open, beam_width=3,
                          branch_cap=4):
    """Four-ply reasoned imagination with a bounded beam.

    Returns (best_future_rhat, solved_within_4, depth_of_best, imagined_states).
    Failure to find a 4-ply route means UNKNOWN, never impossibility.
    """
    r0 = COMP.settlement_distance_hat(goals, sub)
    if not goals:
        return 0.0, True, 0, 0

    best_r = r0
    best_depth = 0
    imagined = 0
    layer = [(r0, goals, sub)]
    seen = {_state_signature(goals, sub)}

    for depth in range(1, IMAGINATION_DEPTH + 1):
        nxt = []
        for _score, gs, ss in layer:
            for ng, ns, _lab in _imagined_successors(
                    gs, ss, index, max_open, branch_cap):
                imagined += 1
                if not ng:
                    return 0.0, True, depth, imagined
                sig = _state_signature(ng, ns)
                if sig in seen:
                    continue
                seen.add(sig)
                rh = COMP.settlement_distance_hat(ng, ns)
                if rh < best_r:
                    best_r, best_depth = rh, depth
                nxt.append((rh, ng, ns))
        if not nxt:
            break
        nxt.sort(key=lambda z: (z[0], len(z[1]), _state_signature(z[1], z[2])))
        layer = nxt[:max(1, int(beam_width))]

    return best_r, False, best_depth, imagined


class R3Controller:
    """Operational level-3 metacontrol over the lower-level compass."""
    def __init__(self):
        self.best_rhat = math.inf
        self.last_improvement = 0
        self.recent_dup = deque(maxlen=512)
        self.mode = "FOCUS"
        self.mode_changes = 0

    def observe(self, exp, rhat, duplicate=False):
        self.recent_dup.append(1 if duplicate else 0)
        if rhat + 1e-12 < self.best_rhat:
            self.best_rhat = rhat
            self.last_improvement = exp
        stale = exp - self.last_improvement
        dup_rate = (sum(self.recent_dup) / len(self.recent_dup)
                    if self.recent_dup else 0.0)
        old = self.mode
        if stale >= 2500 or dup_rate >= 0.45:
            self.mode = "ESCAPE"
        elif stale >= 700 or dup_rate >= 0.25:
            self.mode = "BALANCED"
        else:
            self.mode = "FOCUS"
        if self.mode != old:
            self.mode_changes += 1
        return self.mode, stale, dup_rate

    def policy(self):
        if self.mode == "ESCAPE":
            return dict(imagine_top=12, beam=4, branch_cap=5,
                        progress_weight=0.90, solve_bonus=2.0,
                        extra_explore=0.20)
        if self.mode == "BALANCED":
            return dict(imagine_top=9, beam=3, branch_cap=4,
                        progress_weight=0.70, solve_bonus=1.5,
                        extra_explore=0.10)
        return dict(imagine_top=6, beam=2, branch_cap=3,
                    progress_weight=0.50, solve_bonus=1.0,
                    extra_explore=0.04)


def _select_openers_r3(openers, rest_count, legacy, profile, rng, policy):
    """Compass cap plus R3's stagnation-sensitive exploration reserve."""
    if len(openers) <= profile.opener_cap:
        return list(openers)
    ordered = sorted(
        openers,
        key=lambda item: (COMP._pre_distance(rest_count, item),
                          -legacy.get(item[0], 0.0), item[0]))
    cap = profile.opener_cap
    explore_frac = min(0.75, profile.exploration + policy["extra_explore"])
    explore_n = min(cap - 1, int(round(cap * explore_frac)))
    exploit_n = cap - explore_n
    chosen = list(ordered[:exploit_n])
    tail = ordered[exploit_n:]
    if explore_n and tail:
        chosen.extend(rng.sample(tail, min(explore_n, len(tail))))
    return chosen


def prove_r3i4(goal_tree, index, budget, max_depth, rank=None, say=print,
               progress=2000, max_open=6, profile=None, seed=0,
               shared_use=None, agent_name=None):
    """Best-first backward search with operational R3 + I4 control."""
    if profile is None:
        profile = P8.Profile("deterministic", 0.0, 0.0, 0.0, 0.0,
                             0.0, 48, 1.0)
    rng = random.Random(seed)
    local_use = defaultdict(int)
    if shared_use is None:
        shared_use = defaultdict(int)
    agent_name = agent_name or profile.name

    start = P8.Node([(goal_tree, None, 0)], {}, (), 0)
    start_h = COMP.settlement_distance_hat(start.goals, start.sub)
    frontier = [(start_h, start_h, start_h, 0.0, 0, 0.0, start)]
    exp = tie = 0
    seen = set()
    t0 = time.perf_counter()
    announced = False
    meta = R3Controller()
    total_imagined = 0

    while frontier and exp < budget:
        _fhat, _reachhat, _rhat, _neglegacy, _, g_cost, node = heapq.heappop(frontier)
        exp += 1
        live_rhat = COMP.settlement_distance_hat(node.goals, node.sub)
        mode, stale, dup_rate = meta.observe(exp, live_rhat, False)
        policy = meta.policy()

        if not announced and say:
            say("      [%s] operational (3,4) active: R3 metacontrol + 4-ply reasoned FUTUREBANK"
                % agent_name)
            announced = True
        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open, r_hat=%.3f, R3=%s, stale=%d, dup=%.1f%%, imagined=%s, %.0fs"
                % (agent_name, f"{exp:,}", len(node.goals), live_rhat,
                   mode, stale, 100.0 * dup_rate, f"{total_imagined:,}",
                   time.perf_counter() - t0))

        if not node.goals:
            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            return (root, node.sub), exp
        if node.depth >= max_depth or len(node.goals) > max_open:
            continue

        gi = P8.pick_goal(node.goals, node.sub)
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = P8.apply_sub(gt, node.sub)

        key = (node.depth, " ".join(gt.tokens()),
               tuple(sorted(" ".join(P8.apply_sub(g, node.sub).tokens())
                            for g, _, _ in rest)))
        if key in seen:
            meta.observe(exp, live_rhat, True)
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        legacy_c = COMP._legacy_scores(gt, closers, profile, rng,
                                       local_use, shared_use)
        legacy_o = COMP._legacy_scores(gt, openers, profile, rng,
                                       local_use, shared_use)
        chosen_openers = _select_openers_r3(
            openers, len(rest), legacy_o, profile, rng, policy)
        pick = [(legacy_c.get(item[0], 0.0), item) for item in closers]
        pick += [(legacy_o.get(item[0], 0.0), item) for item in chosen_openers]
        pick.sort(key=lambda pair: (
            COMP._pre_distance(len(rest), pair[1]), -pair[0], pair[1][0]))

        ranked_opener_labels = [item[0] for _score, item in pick if item[2][2]]
        imagine_labels = set(ranked_opener_labels[:policy["imagine_top"]])

        for legacy_score, (lab, ct, data) in pick:
            m = {}
            c2 = P8.rename_apart(ct, m)
            s2 = P8.unify(c2, gt, node.sub)
            if s2 is None:
                continue
            _dv, f_hyps, e_hyps, _concl = data
            fmap = {var: m.get(var, P8.fresh(tc)) for _fh, tc, var in f_hyps}
            for _fh, tc, var in f_hyps:
                m.setdefault(var, fmap[var])
            step = P8.Step(lab, fmap, data)
            newgoals = []
            ok = True
            for hj, (_ename, stat) in enumerate(e_hyps):
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

            successor_goals = newgoals + rest
            if len(successor_goals) > max_open:
                continue
            successor = P8.Node(
                successor_goals, s2,
                node.trail + ((slot, hix, step),),
                node.depth + 1)
            new_g = g_cost + 1.0
            rhat = COMP.settlement_distance_hat(successor_goals, s2)
            reachhat = rhat

            if lab in imagine_labels and successor_goals:
                best_future, solved4, best_d, nim = reasoned_imagination4(
                    successor_goals, s2, index, max_open,
                    beam_width=policy["beam"],
                    branch_cap=policy["branch_cap"])
                total_imagined += nim
                progress4 = max(0.0, rhat - best_future)
                reachhat = (rhat
                            - policy["progress_weight"] * progress4
                            - (policy["solve_bonus"] if solved4 else 0.0)
                            + 0.03 * best_d)

            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1
            fhat = new_g + reachhat
            heapq.heappush(frontier,
                           (fhat, reachhat, rhat, -legacy_score,
                            tie, new_g, successor))

    return None, exp


P8.prove = prove_r3i4


def main():
    return P8.main()


if __name__ == "__main__":
    main()
