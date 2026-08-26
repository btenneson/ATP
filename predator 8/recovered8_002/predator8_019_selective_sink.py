#!/usr/bin/env python3
"""Predator 8.019: selective-kitchen-sink self-aware controller for prcom.

This version keeps the 8.017 unrestricted full-goal certification graph and the
recovered 8.002 ML search distribution. It adds only control mechanisms with a
clear expected search benefit:

* per-basin resource accounting rather than a single global stagnation clock;
* adaptive bailout patience (1%-5% of guided budget, initially 2%);
* H-progress-per-cost utility;
* persistent basin memory and subtree suppression after bailout;
* an earned SATURATE state for basins showing repeated H descent;
* bounded exactification as a diagnostic, never as a second brute-force solver;
* false-proximity evidence shortens patience instead of attracting more search.

The target theorem/proof remains guarded exactly as in 8.015-8.018.

Candidate-gate rule (added after the sgrpcl C5 false-zero experiment): H=0 is a
necessary condition for settlement, but an apparent zero never halts search when
a candidate_gate is supplied unless that gate certifies the reconstructed proof.
Rejected zeros are logged as FALSE-ZERO and search continues within the same
resource budget.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
import math
import random
import time

import predator8_016_prcom_exactify as P
import predator8_017_fullgraph_exactify as F
import predator8_018_bailout as Q

VERSION = "8.019-selective-kitchen-sink"

BASE_PATIENCE_FRACTION = 0.02
MIN_PATIENCE_FRACTION = 0.01
MAX_PATIENCE_FRACTION = 0.05
MIN_PATIENCE_ABS = 200
H_IMPROVEMENT_EPS = 0.05
SATURATE_HOLD_CAP = 400
INFO_WEIGHT = 0.15


def _new_stats(initial_patience):
    return {
        "spent_total": 0,
        "spent_since_benefit": 0,
        "h_gain": 0.0,
        "improvements": 0,
        "info_events": 0,
        "best_lb": 0,
        "patience": initial_patience,
        "bailouts": 0,
    }


def _utility(st):
    return (st["h_gain"] + INFO_WEIGHT * st["info_events"]) / max(1, st["spent_total"])


def adaptive_guided_selective(E, goal, index, policy, budget, max_depth, max_open,
                              seed, probe_ctx: P.ProbeContext,
                              creativity=0.55, opener_cap=48, progress=250,
                              frontier_limit=120000, probe_depth=3,
                              probe_cap=2000, probe_total_cap=4000,
                              probe_next_layer=30000, say=print,
                              candidate_gate=None):
    B = P.B
    rng = random.Random(int(seed) + 2 * 1000003)
    local_use = defaultdict(int)
    shared_use = defaultdict(int)
    start = E.Node([(goal, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    tie = exp = 0
    probe_used_total = 0
    probes = 0
    false_zeros = 0
    seen = set()
    t0 = time.perf_counter()

    mode = "native"
    profile = B.make_mode_profile(E, mode, creativity, opener_cap)
    best_h = B.h_hat(E, start.goals, start.sub)
    last_global_improve = 0
    transitions = []

    descent_streak = 0
    prev_improve_exp = None
    attention_window = 400
    saturate_until = 0
    last_probe_exp = -10**9
    stale_native, stale_high, stale_low = 1200, 1200, 2400

    min_patience = max(MIN_PATIENCE_ABS,
                       int(math.ceil(MIN_PATIENCE_FRACTION * budget)))
    base_patience = max(min_patience,
                        int(math.ceil(BASE_PATIENCE_FRACTION * budget)))
    max_patience = max(base_patience,
                       int(math.ceil(MAX_PATIENCE_FRACTION * budget)))

    basin_stats = defaultdict(lambda: _new_stats(base_patience))
    blocked_prefixes = set()
    active_basin = ()
    bailouts = 0

    say("    controller start: recovered-8.002 explorer + fullgraph exactifier "
        "coord=%s h_hat=%.3f patience=[%s,%s] base=%s"
        % (B.COORD[mode], best_h, f"{min_patience:,}",
           f"{max_patience:,}", f"{base_patience:,}"))
    if candidate_gate is not None:
        say("    [ZERO-GATE] H=0 is necessary but not sufficient; only a certified "
            "candidate may halt search")

    def accept_zero(result, source, total_used, basin):
        nonlocal false_zeros
        if candidate_gate is None:
            return True
        say("      [CANDIDATE-ZERO] source=%s total=%s basin=%s; verifying certificate"
            % (source, f"{total_used:,}", basin or "<root>"))
        try:
            accepted, detail = candidate_gate(result)
        except Exception as exc:
            accepted, detail = False, "%s: %s" % (type(exc).__name__, exc)
        if accepted:
            say("      [CERTIFIED-ZERO] certificate accepted; settlement gate OPEN")
            transitions.append((total_used, mode, "CERTIFIED-ZERO", str(detail)))
            return True
        false_zeros += 1
        say("      [FALSE-ZERO] #%d rejected: %s; search continues"
            % (false_zeros, detail))
        transitions.append((total_used, mode, "FALSE-ZERO", str(detail)))
        return False

    while frontier and (exp + probe_used_total) < budget:
        priority, _, node = heapq.heappop(frontier)
        if Q._blocked(node, blocked_prefixes):
            continue

        exp += 1
        total_used = exp + probe_used_total
        basin = Q._basin_prefix(node)
        st = basin_stats[basin] if basin else None
        if st is not None:
            st["spent_total"] += 1
            st["spent_since_benefit"] += 1

        nh = B.h_hat(E, node.goals, node.sub)
        improved = nh < best_h - H_IMPROVEMENT_EPS

        if improved:
            old = best_h
            gain = old - nh
            best_h = nh
            last_global_improve = exp

            if prev_improve_exp is not None and exp - prev_improve_exp <= attention_window:
                descent_streak += 1
            else:
                descent_streak = 1
            prev_improve_exp = exp

            if st is not None:
                st["h_gain"] += gain
                st["improvements"] += 1
                st["spent_since_benefit"] = 0
                st["patience"] = min(
                    max_patience,
                    max(st["patience"] + min_patience // 3,
                        int(math.ceil(st["patience"] * 1.25))),
                )

            say("      [H-IMPROVE] guided=%s total=%s %.3f->%.3f gain=%.3f "
                "streak=%d basin=%s utility=%.6f"
                % (f"{exp:,}", f"{total_used:,}", old, best_h, gain,
                   descent_streak, basin or "<root>",
                   _utility(st) if st is not None else 0.0))

            if descent_streak >= 2 and basin and basin not in blocked_prefixes:
                active_basin = basin
                local_patience = basin_stats[basin]["patience"]
                saturate_hold = min(SATURATE_HOLD_CAP,
                                    max(100, local_patience // 2))
                saturate_until = exp + saturate_hold
                transitions.append((total_used, mode, "SATURATE",
                                    "repeated H descent in basin %s" % (basin,)))
                say("      [SATURATE] earned by repeated H descent; basin=%s "
                    "hold<=%s patience=%s"
                    % (basin, f"{saturate_hold:,}", f"{local_patience:,}"))

                remaining_probe = min(
                    probe_cap,
                    max(100, local_patience // 2),
                    probe_total_cap - probe_used_total,
                    budget - (exp + probe_used_total),
                )
                if remaining_probe > 0 and exp - last_probe_exp >= 250:
                    probes += 1
                    last_probe_exp = exp
                    say("      [PROXIMITY-ALARM] bounded diagnostic probe #%d "
                        "depth<=%d cap=%s basin=%s"
                        % (probes, probe_depth, f"{remaining_probe:,}", basin))
                    pr = P.run_probe(probe_ctx, node, probe_depth, remaining_probe,
                                     max_next_layer=probe_next_layer)
                    probe_used_total += pr.expanded
                    total_used = exp + probe_used_total
                    st["spent_total"] += pr.expanded
                    st["spent_since_benefit"] += pr.expanded

                    if pr.exact_h is not None:
                        say("      [EXACTIFY] CERTIFIED exact H=%d at snapshot; "
                            "probe_exp=%s total=%s"
                            % (pr.exact_h, f"{pr.expanded:,}", f"{total_used:,}"))
                        transitions.append((total_used, mode, "SATURATE",
                                            "CERTIFIED exact shell"))
                        witness = pr.witness
                        if witness is not None and witness.closed_witness is not None:
                            candidate = B.reconstruct(witness.closed_witness)
                            if accept_zero(candidate, "exactifier", total_used, basin):
                                return (candidate, total_used, best_h,
                                        transitions, "exactifier-settled")
                    else:
                        old_lb = st["best_lb"]
                        if pr.lower_bound > old_lb:
                            st["best_lb"] = pr.lower_bound
                            st["info_events"] += 1
                            say("      [INFO-GAIN] basin=%s certified lower bound "
                                "H>=%d (was %d)"
                                % (basin, pr.lower_bound, old_lb))

                        false_proximity = pr.lower_bound - nh > 0.5
                        say("      [EXACTIFY] no settlement in certified shells; "
                            "H>=%d checked_through=%d complete=%s probe_exp=%s"
                            % (pr.lower_bound, pr.checked_through_depth,
                               pr.complete_to_requested_depth,
                               f"{pr.expanded:,}"))
                        if false_proximity:
                            st["patience"] = max(
                                min_patience,
                                int(math.floor(st["patience"] * 0.60)),
                            )
                            saturate_until = 0
                            descent_streak = 0
                            transitions.append((total_used, mode, mode,
                                                "FALSE-PROXIMITY shortens patience"))
                            say("      [FALSE-PROXIMITY] H_hat=%.3f versus "
                                "certified H>=%d; patience->%s"
                                % (nh, pr.lower_bound, f"{st['patience']:,}"))

            if mode == "low":
                oldm = mode
                mode = "native"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                transitions.append((total_used, oldm, mode,
                                    "torpor progress -> native"))
                say("      [CONTROL] TORPOR EXIT %s -> %s: progress restored"
                    % (B.COORD[oldm], B.COORD[mode]))

        if st is not None and basin and basin not in blocked_prefixes:
            if st["spent_since_benefit"] >= st["patience"]:
                bailouts += 1
                st["bailouts"] += 1
                blocked_prefixes.add(basin)
                before = len(frontier)
                frontier = Q._prune_frontier(frontier, blocked_prefixes)
                removed = before - len(frontier)
                oldm = mode
                mode = "high"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "BAILOUT basin %s utility=%.6f"
                                    % (basin, _utility(st))))
                say("      [BAILOUT] basin=%s spent_without_benefit=%s "
                    "patience=%s utility=%.6f; pruned=%s; %s -> %s"
                    % (basin, f"{st['spent_since_benefit']:,}",
                       f"{st['patience']:,}", _utility(st), f"{removed:,}",
                       B.COORD[oldm], B.COORD[mode]))
                if active_basin == basin:
                    active_basin = ()
                    saturate_until = 0
                    descent_streak = 0
                continue

        saturating = bool(active_basin) and exp <= saturate_until
        stale = exp - last_global_improve
        if not saturating:
            if mode == "native" and stale >= stale_native:
                oldm = mode
                mode = "high"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                last_global_improve = exp
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "global stagnation -> SURGE"))
                say("      [CONTROL] SURGE %s -> %s"
                    % (B.COORD[oldm], B.COORD[mode]))
            elif mode == "high" and stale >= stale_high:
                oldm = mode
                mode = "low"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                last_global_improve = exp
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "failed surge -> TORPOR"))
                say("      [CONTROL] TORPOR %s -> %s"
                    % (B.COORD[oldm], B.COORD[mode]))
            elif mode == "low" and stale >= stale_low:
                transitions.append((exp + probe_used_total, mode, "brute",
                                    "failed torpor -> brute"))
                say("      [CONTROL] TORPOR %s -> brute %s"
                    % (B.COORD[mode], B.COORD["brute"]))
                return None, exp + probe_used_total, best_h, transitions, "brute-requested"

        if progress and exp % progress == 0:
            ast = basin_stats[active_basin] if active_basin else None
            say("      [GUIDED] guided=%s probe=%s total=%s open=%d "
                "best_h=%.3f mode=%s saturate=%s frontier=%s "
                "bailouts=%d blocked=%d false_zeros=%d active_utility=%.6f elapsed=%.1fs"
                % (f"{exp:,}", f"{probe_used_total:,}",
                   f"{exp + probe_used_total:,}", len(node.goals), best_h, mode,
                   "ON" if saturating else "off", f"{len(frontier):,}",
                   bailouts, len(blocked_prefixes), false_zeros,
                   _utility(ast) if ast is not None else 0.0,
                   time.perf_counter() - t0))

        if not node.goals:
            candidate = B.reconstruct(node)
            if accept_zero(candidate, "guided", exp + probe_used_total, basin):
                return candidate, exp + probe_used_total, best_h, transitions, "settled"
            continue
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
            if Q._blocked(child, blocked_prefixes):
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
    P.adaptive_guided_exactify = adaptive_guided_selective
    F.VERSION = VERSION
    return F.main()


if __name__ == "__main__":
    raise SystemExit(main())
