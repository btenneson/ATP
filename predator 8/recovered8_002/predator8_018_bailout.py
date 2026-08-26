#!/usr/bin/env python3
"""Predator 8.018: self-aware basin bailout for prcom.

This keeps the 8.017 unrestricted full-goal exactification graph, but adds a
resource/benefit feedback rule to the guided controller.  A low-H basin earns
only a bounded tranche of continued search.  If that tranche is spent without
meaningful H descent or settlement, the controller blacklists the basin's first
proof-choice prefix, prunes that subtree from the frontier, and deliberately
moves to competing branches.

The bailout fraction is an experimental hyperparameter, not a theorem constant.
The initial value is 3% of the guided budget.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
import math
import random
import time

import predator8_016_prcom_exactify as P
import predator8_017_fullgraph_exactify as F

VERSION = "8.018-ML-fullgraph-self-aware-bailout"
BAILOUT_FRACTION = 0.03
BAILOUT_MIN_EXPANSIONS = 250
BASIN_PREFIX_LEN = 1


def _step_signature(step):
    for name in ("lab", "label", "name"):
        value = getattr(step, name, None)
        if value is not None:
            return str(value)
    return repr(step)


def _basin_prefix(node):
    trail = tuple(getattr(node, "trail", ()) or ())
    if not trail:
        return ()
    n = min(BASIN_PREFIX_LEN, len(trail))
    return tuple(_step_signature(trail[i][2]) for i in range(n))


def _blocked(node, blocked_prefixes):
    trail = tuple(getattr(node, "trail", ()) or ())
    if not trail:
        return False
    sig = tuple(_step_signature(item[2]) for item in trail)
    return any(len(sig) >= len(bp) and sig[:len(bp)] == bp for bp in blocked_prefixes)


def _prune_frontier(frontier, blocked_prefixes):
    kept = [item for item in frontier if not _blocked(item[2], blocked_prefixes)]
    heapq.heapify(kept)
    return kept


def adaptive_guided_bailout(E, goal, index, policy, budget, max_depth, max_open,
                            seed, probe_ctx: P.ProbeContext,
                            creativity=0.55, opener_cap=48, progress=250,
                            frontier_limit=120000, probe_depth=3,
                            probe_cap=2000, probe_total_cap=4000,
                            probe_next_layer=30000, say=print):
    B = P.B
    rng = random.Random(int(seed) + 2 * 1000003)
    local_use = defaultdict(int)
    shared_use = defaultdict(int)
    start = E.Node([(goal, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    tie = exp = 0
    probe_used_total = 0
    probes = 0
    seen = set()
    t0 = time.perf_counter()

    mode = "native"
    profile = B.make_mode_profile(E, mode, creativity, opener_cap)
    best_h = B.h_hat(E, start.goals, start.sub)
    last_improve = 0
    transitions = []
    descent_streak = 0
    prev_improve_exp = None
    attention_until = 0
    attention_window = 400
    attention_hold = 900
    last_probe_exp = -10**9
    stale_native, stale_high, stale_low = 1200, 1200, 2400

    # Self-awareness state: which promising basin are we currently paying for,
    # and how much no-benefit work has it consumed?
    basin_budget = max(BAILOUT_MIN_EXPANSIONS,
                       int(math.ceil(BAILOUT_FRACTION * budget)))
    active_basin = ()
    basin_anchor_exp = 0
    blocked_prefixes = set()
    bailouts = 0

    # Exactification is diagnostic, not a second brute-force solver.  Bound each
    # probe by the same tranche scale even if a larger probe cap is supplied.
    probe_bailout_cap = basin_budget

    say("    controller start: recovered-8.002 explorer + fullgraph exactifier "
        "coord=%s h_hat=%.3f bailout_fraction=%.3f basin_budget=%s"
        % (B.COORD[mode], best_h, BAILOUT_FRACTION, f"{basin_budget:,}"))

    while frontier and (exp + probe_used_total) < budget:
        priority, _, node = heapq.heappop(frontier)
        if _blocked(node, blocked_prefixes):
            continue

        exp += 1
        total_used = exp + probe_used_total
        nh = B.h_hat(E, node.goals, node.sub)
        improved = nh < best_h - 0.05

        if improved:
            old = best_h
            best_h = nh
            if prev_improve_exp is not None and exp - prev_improve_exp <= attention_window:
                descent_streak += 1
            else:
                descent_streak = 1
            prev_improve_exp = exp
            last_improve = exp
            # Any genuine descent earns the currently active basin a fresh tranche.
            if active_basin:
                basin_anchor_exp = exp
            say("      [H-IMPROVE] guided=%s total=%s %.3f->%.3f streak=%d mode=%s"
                % (f"{exp:,}", f"{total_used:,}", old, best_h,
                   descent_streak, mode))

            if descent_streak >= 2:
                attention_until = exp + attention_hold
                candidate_basin = _basin_prefix(node)
                if candidate_basin and candidate_basin not in blocked_prefixes:
                    active_basin = candidate_basin
                    basin_anchor_exp = exp
                transitions.append((total_used, mode, mode,
                                    "ATTENTION: consecutive H descent"))
                say("      [ATTENTION] consecutive descent; snapshot eligible for exactification; "
                    "basin=%s" % (active_basin or "<root>"))

                remaining_probe = min(
                    probe_cap,
                    probe_bailout_cap,
                    probe_total_cap - probe_used_total,
                    budget - (exp + probe_used_total),
                )
                if remaining_probe > 0 and exp - last_probe_exp >= 250:
                    probes += 1
                    last_probe_exp = exp
                    say("      [PROXIMITY-ALARM] launching bounded diagnostic BFS probe #%d "
                        "depth<=%d cap=%s" %
                        (probes, probe_depth, f"{remaining_probe:,}"))
                    pr = P.run_probe(probe_ctx, node, probe_depth, remaining_probe,
                                     max_next_layer=probe_next_layer)
                    probe_used_total += pr.expanded
                    total_used = exp + probe_used_total
                    if pr.exact_h is not None:
                        say("      [EXACTIFY] CERTIFIED exact H=%d at snapshot; "
                            "probe expansions=%s total=%s"
                            % (pr.exact_h, f"{pr.expanded:,}", f"{total_used:,}"))
                        transitions.append((total_used, mode, mode,
                                            "CERTIFIED exact shell by complete BFS"))
                        witness = pr.witness
                        if witness is not None and witness.closed_witness is not None:
                            return (B.reconstruct(witness.closed_witness), total_used,
                                    best_h, transitions, "exactifier-settled")
                    else:
                        if pr.lower_bound - nh > 0.5:
                            say("      [HALF-GAP-DENIED] certified H>=%d versus H_hat=%.3f; "
                                "local estimator error is already >1/2"
                                % (pr.lower_bound, nh))
                            transitions.append((total_used, mode, mode,
                                                "HALF-GAP-DENIED by certified lower bound"))
                        say("      [EXACTIFY] no settlement in certified shells; H>=%d "
                            "for snapshot; checked_through=%d complete=%s probe_exp=%s"
                            % (pr.lower_bound, pr.checked_through_depth,
                               pr.complete_to_requested_depth,
                               f"{pr.expanded:,}"))
                        transitions.append((total_used, mode, mode,
                                            "EXACTIFY lower bound H>=%d" % pr.lower_bound))
                        if pr.lower_bound >= 3 and best_h < 2.5:
                            attention_until = 0
                            descent_streak = 0
                            say("      [FALSE-PROXIMITY] certified lower bound cancels ATTENTION")

            if mode == "low":
                oldm = mode
                mode = "native"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                transitions.append((total_used, oldm, mode, "torpor progress -> native"))
                say("      [CONTROL] TORPOR EXIT %s -> %s: progress restored"
                    % (B.COORD[oldm], B.COORD[mode]))

        # Level-3-style self-awareness: if a basin keeps consuming cost without
        # H benefit, infer that the current strategy/basin is failing and leave.
        if (active_basin and
                exp - basin_anchor_exp >= basin_budget and
                exp - last_improve >= basin_budget):
            bailouts += 1
            blocked_prefixes.add(active_basin)
            before = len(frontier)
            frontier = _prune_frontier(frontier, blocked_prefixes)
            removed = before - len(frontier)
            oldm = mode
            mode = "high"  # deliberately diversify after abandoning the basin
            profile = B.make_mode_profile(E, mode, creativity, opener_cap)
            transitions.append((exp + probe_used_total, oldm, mode,
                                "BAILOUT no-benefit basin %s" % (active_basin,)))
            say("      [BAILOUT] cost without benefit: basin=%s spent=%s/%s; "
                "blacklisting subtree, pruned=%s frontier states; %s -> %s"
                % (active_basin, f"{exp - basin_anchor_exp:,}",
                   f"{basin_budget:,}", f"{removed:,}",
                   B.COORD[oldm], B.COORD[mode]))
            active_basin = ()
            basin_anchor_exp = exp
            attention_until = 0
            descent_streak = 0
            last_improve = exp
            continue

        attention_active = exp <= attention_until
        stale = exp - last_improve
        if not attention_active:
            if mode == "native" and stale >= stale_native:
                oldm = mode; mode = "high"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                last_improve = exp
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "stagnation -> SURGE"))
                say("      [CONTROL] SURGE %s -> %s" % (B.COORD[oldm], B.COORD[mode]))
            elif mode == "high" and stale >= stale_high:
                oldm = mode; mode = "low"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                last_improve = exp
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "failed surge -> TORPOR"))
                say("      [CONTROL] TORPOR %s -> %s" % (B.COORD[oldm], B.COORD[mode]))
            elif mode == "low" and stale >= stale_low:
                transitions.append((exp + probe_used_total, mode, "brute",
                                    "failed torpor -> brute"))
                say("      [CONTROL] TORPOR %s -> brute %s"
                    % (B.COORD[mode], B.COORD["brute"]))
                return None, exp + probe_used_total, best_h, transitions, "brute-requested"

        if progress and exp % progress == 0:
            say("      [GUIDED] guided=%s probe=%s total=%s open=%d best_h=%.3f "
                "mode=%s attention=%s frontier=%s bailouts=%d blocked=%d elapsed=%.1fs"
                % (f"{exp:,}", f"{probe_used_total:,}",
                   f"{exp + probe_used_total:,}", len(node.goals), best_h, mode,
                   "ON" if attention_active else "off", f"{len(frontier):,}",
                   bailouts, len(blocked_prefixes), time.perf_counter() - t0))

        if not node.goals:
            return B.reconstruct(node), exp + probe_used_total, best_h, transitions, "settled"
        if node.depth >= max_depth or len(node.goals) > max_open:
            continue

        gi = E.pick_goal(node.goals, node.sub)
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = E.apply_sub(gt, node.sub)
        key = (node.depth, " ".join(gt.tokens()),
               tuple(sorted(" ".join(E.apply_sub(g, node.sub).tokens())
                            for g, _, _ in rest)))
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        mlw = B.ML_WEIGHT[mode]
        sc_c = [mlw * x for x in policy.rank(gt, closers)] if closers else []
        sc_o = [mlw * x for x in policy.rank(gt, openers)] if openers else []
        ranked_c = E._candidate_scores(gt, closers, sc_c, profile, rng,
                                       local_use, shared_use)
        ranked_o = E._candidate_scores(gt, openers, sc_o, profile, rng,
                                       local_use, shared_use)
        chosen = ranked_c + E._counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng)
        curh = B.h_hat(E, node.goals, node.sub)

        for cand_score, (lab, ct, data) in chosen:
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
            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1
            successor_goals = newgoals + rest
            guide = math.tanh(cand_score / 2.0)
            edge = (0.25 if not e_hyps else 1.0) - 0.20 * guide
            if B.H_WEIGHT[mode] > 0.0:
                delta = curh - B.h_hat(E, successor_goals, s2)
                edge -= B.H_WEIGHT[mode] * math.tanh(delta)
            edge = max(0.05, edge)
            state_cost = 0.02 * len(successor_goals)
            child = E.Node(successor_goals, s2,
                           node.trail + ((slot, hix, step),), node.depth + 1)
            if _blocked(child, blocked_prefixes):
                continue
            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))

        if frontier_limit and len(frontier) > frontier_limit:
            keep = max(1000, frontier_limit // 2)
            frontier = heapq.nsmallest(keep, frontier)
            heapq.heapify(frontier)
            say("      [MEMORY-GUARD] frontier pruned to %s best states"
                % f"{len(frontier):,}")

    return None, exp + probe_used_total, best_h, transitions, "guided-budget"


def main():
    # Retain 8.017's unrestricted certification graph and substitute only the
    # guided controller.  P.main still enforces the no-target-proof leakage
    # guards and the same global resource accounting as 8.016/8.017.
    P.adaptive_guided_exactify = adaptive_guided_bailout
    F.VERSION = VERSION
    return F.main()


if __name__ == "__main__":
    raise SystemExit(main())
