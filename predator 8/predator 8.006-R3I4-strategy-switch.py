#!/usr/bin/env python3
"""Predator 8.006-R3I4-strategy-switch.

Operational Level-3 strategy switching for the (3,4) Halo experiment.

8.005 established a useful failure mode: after terminal-ground DV shortcuts were
rejected, the search could remain in R3 ESCAPE for thousands of expansions while
four-ply imagination consumed most of the wall clock without improving the best
settlement-distance estimate.  Increasing imagination inside the same policy is
not a strategy switch.

8.006 therefore keeps the SAME proof calculus, I4 maximum lookahead depth,
DV/terminal-ground safeguards, frozen corpus, target-blind policy, resource
budget, and independent verifier, but adds an operational Level-3 controller
that changes HOW those resources are used when the current strategy saturates.

The controller cycles through four target-generic strategies:

  COMPASS    normal settlement-compass + selective I4 lookahead;
  CERTIFY    penalize unresolved metavariables in DV obligations and reduce
             imagination breadth after repeated illegal terminal shortcuts;
  DIVERSIFY  widen counterfactual opener sampling while making I4 sparse;
  LEAN       spend most resources on real proof expansions, using only a thin
             four-ply probe instead of repeatedly simulating the same region.

A real improvement in r_hat resets the saturation clock, so the controller can
return to COMPASS.  When a strategy changes, the EXISTING frontier is re-keyed
under the new policy; no state is silently discarded.  Thus the experiment
implements the Level-3 idea "try a strategy; if it is cheaply diagnosed as
stalled, change strategy" rather than merely turning the same knob upward.

I=4 still means the imagination operator can simulate up to four legal backward
Metamath applications.  Some strategies deliberately call it less often to
avoid imagination saturation.  No imagined path is accepted as mathematics.
"""
from __future__ import annotations

import heapq
import importlib.util
import os
import random
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.005-R3I4-terminaldv.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_terminaldv", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.005-R3I4-terminaldv")
BASE5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE5)

BASE = BASE5.BASE
R3I4 = BASE5.R3I4
P8 = BASE5.P8
COMP = BASE5.COMP
P8.VERSION = "8.006-R3I4-strategy-switch"


# ---------------------------------------------------------------------------
# Level-3 strategy controller
# ---------------------------------------------------------------------------

def _strategy_for(stale, terminal_rejects_since_improvement):
    """Choose a distinct search policy from checked live saturation signals.

    Four terminal-ground failures before a fresh r_hat improvement are treated
    as direct evidence that the current route family is producing attractive
    but non-emittable certificates, so CERTIFY can activate early.
    """
    if stale >= 5000:
        return "LEAN"
    if stale >= 2500:
        return "DIVERSIFY"
    if stale >= 900 or terminal_rejects_since_improvement >= 4:
        return "CERTIFY"
    return "COMPASS"


STRATEGY = {
    # imagine_top/beam/branch_cap retain maximum imagination depth = 4; they
    # control only how often/how broadly the four-ply operator is invoked.
    "COMPASS": dict(imagine_top=6, beam=2, branch_cap=3,
                    progress_weight=0.50, solve_bonus=1.00,
                    explore_extra=0.04, cap_factor=1.00,
                    goal_meta_weight=0.01, dv_meta_weight=0.03,
                    rhat_weight=1.00, diversity_bonus=0.00),
    "CERTIFY": dict(imagine_top=4, beam=2, branch_cap=2,
                    progress_weight=0.45, solve_bonus=0.75,
                    explore_extra=0.02, cap_factor=0.80,
                    goal_meta_weight=0.06, dv_meta_weight=0.35,
                    rhat_weight=1.00, diversity_bonus=0.00),
    "DIVERSIFY": dict(imagine_top=2, beam=1, branch_cap=2,
                      progress_weight=0.30, solve_bonus=0.45,
                      explore_extra=0.38, cap_factor=1.35,
                      goal_meta_weight=0.03, dv_meta_weight=0.10,
                      rhat_weight=0.90, diversity_bonus=0.18),
    "LEAN": dict(imagine_top=1, beam=1, branch_cap=1,
                 progress_weight=0.18, solve_bonus=0.25,
                 explore_extra=0.30, cap_factor=1.50,
                 goal_meta_weight=0.02, dv_meta_weight=0.08,
                 rhat_weight=0.75, diversity_bonus=0.10),
}


def _tree_metas(t, sub, acc=None):
    if acc is None:
        acc = set()
    t = P8.walk(t, sub)
    if t.var is not None:
        if P8.is_meta(t):
            acc.add(t.var)
        return acc
    for k in t.kids:
        _tree_metas(k, sub, acc)
    return acc


def _goal_meta_count(goals, sub):
    acc = set()
    for g, _slot, _hix in goals:
        _tree_metas(g, sub, acc)
    return len(acc)


def _dv_meta_count(obligations, sub):
    acc = set()
    for tx, ty, _x, _y in obligations:
        _tree_metas(tx, sub, acc)
        _tree_metas(ty, sub, acc)
    return len(acc)


def _diversity_fraction(node):
    """Stable target-generic state jitter in [0,1), independent of hash seed."""
    sig = R3I4._state_signature(node.goals, node.sub)
    raw = "\x1f".join(sig).encode("utf-8", "replace")
    return (zlib.crc32(raw) & 0xffffffff) / 4294967296.0


def _strategy_priority(node, g_cost, obligations, strategy):
    p = STRATEGY[strategy]
    rhat = COMP.settlement_distance_hat(node.goals, node.sub)
    gm = _goal_meta_count(node.goals, node.sub)
    dm = _dv_meta_count(obligations, node.sub)
    return (g_cost + p["rhat_weight"] * rhat
            + p["goal_meta_weight"] * gm
            + p["dv_meta_weight"] * dm
            - p["diversity_bonus"] * _diversity_fraction(node))


def _rekey_frontier(frontier, dv_by_node, strategy):
    """Apply a true strategy change to every surviving state, dropping none."""
    out = []
    for _f, reachhat, rhat, neglegacy, tie, g_cost, node in frontier:
        obligations = dv_by_node.get(node, ())
        fnew = _strategy_priority(node, g_cost, obligations, strategy)
        out.append((fnew, reachhat, rhat, neglegacy, tie, g_cost, node))
    heapq.heapify(out)
    return out


def _select_openers_switch(openers, rest_count, legacy, profile, rng, strategy):
    """Exploit/explore split that changes materially with the Level-3 strategy."""
    p = STRATEGY[strategy]
    cap = max(1, int(round(profile.opener_cap * p["cap_factor"])))
    if len(openers) <= cap:
        return list(openers)

    ordered = sorted(
        openers,
        key=lambda item: (COMP._pre_distance(rest_count, item),
                          -legacy.get(item[0], 0.0), item[0]))
    explore_frac = min(0.85, profile.exploration + p["explore_extra"])
    explore_n = min(cap - 1, int(round(cap * explore_frac)))
    exploit_n = cap - explore_n
    chosen = list(ordered[:exploit_n])
    tail = ordered[exploit_n:]
    if explore_n and tail:
        chosen.extend(rng.sample(tail, min(explore_n, len(tail))))
    return chosen


def _notable_switch(n):
    return n <= 12 or n in {20, 30, 50}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def prove_r3i4_switch(goal_tree, index, budget, max_depth, rank=None,
                      say=print, progress=2000, max_open=6, profile=None,
                      seed=0, shared_use=None, agent_name=None):
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
    dv_by_node = {start: ()}
    exp = tie = 0
    seen = set()
    t0 = time.perf_counter()
    announced = False
    meta = R3I4.R3Controller()
    total_imagined = 0
    dv_rejects = 0
    dv_final_rejects = 0
    dv_final_since_improvement = 0
    improvement_marker = 0
    strategy = "COMPASS"
    strategy_switches = 0

    while frontier and exp < budget:
        _fhat, _reachhat, _rhat, _neglegacy, _, g_cost, node = heapq.heappop(frontier)
        node_dv = dv_by_node.pop(node, ())
        exp += 1
        if not R3I4._dv_ok(node_dv, node.sub):
            dv_rejects += 1
            continue

        live_rhat = COMP.settlement_distance_hat(node.goals, node.sub)
        mode, stale, dup_rate = meta.observe(exp, live_rhat, False)

        # A genuine settlement-distance improvement starts a fresh strategy
        # trial.  Terminal failures from an older local basin no longer count
        # against the new one.
        if meta.last_improvement != improvement_marker:
            improvement_marker = meta.last_improvement
            dv_final_since_improvement = 0

        desired = _strategy_for(stale, dv_final_since_improvement)
        if desired != strategy:
            old = strategy
            strategy = desired
            strategy_switches += 1
            frontier = _rekey_frontier(frontier, dv_by_node, strategy)
            if say and _notable_switch(strategy_switches):
                say("      [%s] LEVEL-3 STRATEGY SWITCH #%d: %s -> %s; stale=%d, terminal-rejects-since-improvement=%d; re-keyed %s frontier states"
                    % (agent_name, strategy_switches, old, strategy, stale,
                       dv_final_since_improvement, f"{len(frontier):,}"))

        sp = STRATEGY[strategy]

        if not announced and say:
            say("      [%s] operational (3,4) active: R3 metacontrol + I4 FUTUREBANK + DV gates + saturation-triggered strategy switching"
                % agent_name)
            announced = True
        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open, r_hat=%.3f, R3=%s, strategy=%s, stale=%d, dup=%.1f%%, imagined=%s, dvrej=%s, dvfinal=%s, switches=%d, %.0fs"
                % (agent_name, f"{exp:,}", len(node.goals), live_rhat,
                   mode, strategy, stale, 100.0 * dup_rate,
                   f"{total_imagined:,}", f"{dv_rejects:,}",
                   f"{dv_final_rejects:,}", strategy_switches,
                   time.perf_counter() - t0))

        if not node.goals:
            if not BASE5._terminal_dv_ok(node_dv, node.sub):
                dv_final_rejects += 1
                dv_final_since_improvement += 1
                if say and BASE5._notable_count(dv_final_rejects):
                    say("      [%s] terminal DV rejection #%s after grounding; continuing frontier"
                        % (agent_name, f"{dv_final_rejects:,}"))
                # Let the direct certificate failure signal trigger CERTIFY
                # immediately rather than waiting for another popped node.
                desired = _strategy_for(stale, dv_final_since_improvement)
                if desired != strategy:
                    old = strategy
                    strategy = desired
                    strategy_switches += 1
                    frontier = _rekey_frontier(frontier, dv_by_node, strategy)
                    if say and _notable_switch(strategy_switches):
                        say("      [%s] LEVEL-3 STRATEGY SWITCH #%d: %s -> %s after terminal-ground rejection; re-keyed %s frontier states"
                            % (agent_name, strategy_switches, old, strategy,
                               f"{len(frontier):,}"))
                continue

            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            if say:
                say("      [%s] terminal branch passed final-ground DV gate after %s rejected shortcut(s), %d strategy switch(es)"
                    % (agent_name, f"{dv_final_rejects:,}", strategy_switches))
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
        chosen_openers = _select_openers_switch(
            openers, len(rest), legacy_o, profile, rng, strategy)
        pick = [(legacy_c.get(item[0], 0.0), item) for item in closers]
        pick += [(legacy_o.get(item[0], 0.0), item) for item in chosen_openers]
        pick.sort(key=lambda pair: (
            COMP._pre_distance(len(rest), pair[1]), -pair[0], pair[1][0]))

        ranked_opener_labels = [item[0] for _score, item in pick if item[2][2]]
        imagine_labels = set(ranked_opener_labels[:sp["imagine_top"]])

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

            successor_dv = node_dv + R3I4._dv_obligations(data, m)
            if not R3I4._dv_ok(successor_dv, s2):
                dv_rejects += 1
                continue

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
            dv_by_node[successor] = successor_dv
            new_g = g_cost + 1.0
            rhat = COMP.settlement_distance_hat(successor_goals, s2)
            reachhat = rhat

            if lab in imagine_labels and successor_goals:
                best_future, solved4, best_d, nim = R3I4.reasoned_imagination4(
                    successor_goals, s2, index, max_open,
                    beam_width=sp["beam"], branch_cap=sp["branch_cap"])
                total_imagined += nim
                progress4 = max(0.0, rhat - best_future)
                reachhat = (rhat
                            - sp["progress_weight"] * progress4
                            - (sp["solve_bonus"] if solved4 else 0.0)
                            + 0.03 * best_d)

            goal_metas = _goal_meta_count(successor_goals, s2)
            dv_metas = _dv_meta_count(successor_dv, s2)
            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1

            fhat = (new_g + sp["rhat_weight"] * reachhat
                    + sp["goal_meta_weight"] * goal_metas
                    + sp["dv_meta_weight"] * dv_metas
                    - sp["diversity_bonus"] * _diversity_fraction(successor))
            heapq.heappush(frontier,
                           (fhat, reachhat, rhat, -legacy_score,
                            tie, new_g, successor))

    if say:
        say("      [%s] search ended: strategy switches=%d, terminal-ground DV rejections=%s, imagined states=%s"
            % (agent_name, strategy_switches, f"{dv_final_rejects:,}",
               f"{total_imagined:,}"))
    return None, exp


P8.prove = prove_r3i4_switch


# Extend the inherited selftest with the controller's activation boundaries.
_ORIG_SELFTEST = P8.cmd_selftest


def _cmd_selftest_strategy_switch(a):
    rc = _ORIG_SELFTEST(a)
    if rc:
        return rc
    cases = [
        (_strategy_for(0, 0), "COMPASS"),
        (_strategy_for(1000, 0), "CERTIFY"),
        (_strategy_for(100, 4), "CERTIFY"),
        (_strategy_for(3000, 0), "DIVERSIFY"),
        (_strategy_for(6000, 0), "LEAN"),
    ]
    ok = all(got == want for got, want in cases)
    print("  [5] saturation signals activate distinct Level-3 strategies")
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _cmd_selftest_strategy_switch


def main():
    return BASE5.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
