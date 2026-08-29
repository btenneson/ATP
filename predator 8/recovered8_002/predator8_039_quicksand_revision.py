#!/usr/bin/env python3
"""Predator 8.039: joint H/compression quicksand revision for prcom.

Research question
-----------------
Can a verifier-gated controller avoid spending essentially an entire 30,000-
expansion budget in an unproductive search basin by watching two independent
progress signals and revising the search controls before the basin consumes the
run?

Primary progress signal
-----------------------
    H_hat(q)
The same non-authoritative structural settlement heuristic used by the recovered
Predator 8.002 lineage.  It is not exact H and never establishes theoremhood.

Certificate-complexity signal
-----------------------------
The raw compressed length l(q) of a forward partial certificate is naturally
nondecreasing when new proof labels are appended, so minimizing l(q) directly
would favor empty/shallow partial proofs.  Instead this experiment uses the
log compressed-bit density

    z_l(q) = log((l(q)+1)/(depth(q)+1)).

l(q) is measured with the frozen, lossless FirstOccurrenceGammaV1 codec from
8.033, applied only to labels already present in the current partial proof
trail.  z_l is a diagnostic/secondary search coordinate, not a certificate of
remaining proof complexity.

Group-valued revision
---------------------
The pressure beta_l applied to z_l lives in the additive group (R,+).  Normal
search uses beta_l > 0, preferring lower z_l.  When both H_hat and z_l fail to
improve for the basin's patience tranche, revision applies the group inverse

    beta_l -> -beta_l,

and also applies the existing logit-group inverse to creativity

    c -> 1-c.

The inverse phase is deliberately bounded.  It may temporarily prefer the
opposite compression behavior in order to leave a local basin.  If the basin
still yields no H_hat or z_l improvement during the revision window, the basin
prefix is blacklisted and the controller moves elsewhere.

Verifier invariant
------------------
All of the above changes search order only.  The target proof remains unavailable
as a rule, exactification remains diagnostic, and final settlement is accepted
only by the existing candidate/verifier gate.  V(P)=1 remains the hard boundary.

This is an experiment, not a theorem that settlement will occur before 30,000
expansions.  What the controller does enforce is that one unchanged first-prefix
basin cannot consume the whole budget without either (a) measured benefit,
(b) a bounded inverse-revision attempt, or (c) bailout.
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
import predator8_033_bit_coupled_adaptive as CB

VERSION = "8.039-joint-H-compression-quicksand-revision"

BASE_PATIENCE_FRACTION = 0.02
MIN_PATIENCE_FRACTION = 0.01
MAX_PATIENCE_FRACTION = 0.05
MIN_PATIENCE_ABS = 200
H_IMPROVEMENT_EPS = 0.05
Z_IMPROVEMENT_EPS = 0.01
SATURATE_HOLD_CAP = 400
REVISION_HOLD_CAP = 1500
REVISION_HOLD_MIN = 250
INFO_WEIGHT = 0.15
Z_UTILITY_WEIGHT = 0.20
NORMAL_BIT_BETA = 0.12
Z_EDGE_SCALE = 0.20


def _trail_labels(node):
    trail = tuple(getattr(node, "trail", ()) or ())
    return tuple(Q._step_signature(item[2]) for item in trail)


def partial_certificate_bits(node, cache=None):
    """Lossless compressed bits of the labels already present in node.trail."""
    labels = _trail_labels(node)
    if cache is not None and labels in cache:
        return cache[labels]
    bits = int(CB.cert_bits(list(labels)))
    if cache is not None:
        cache[labels] = bits
    return bits


def z_length(node, cache=None):
    """Log compressed-bit density; unlike raw l(q), it can rise or fall."""
    depth = len(tuple(getattr(node, "trail", ()) or ()))
    bits = partial_certificate_bits(node, cache)
    return math.log((bits + 1.0) / (depth + 1.0))


def inverse_bit_pressure(beta):
    """Group inverse in (R,+)."""
    return -float(beta)


def inverse_creativity(c):
    """Group inverse in the logit-addition coordinate used by 8.037/8.038."""
    x = float(c)
    if not 0.0 < x < 1.0:
        raise ValueError("creativity must lie in (0,1)")
    return 1.0 - x


def _new_stats(initial_patience):
    return {
        "spent_total": 0,
        "spent_since_benefit": 0,
        "h_gain": 0.0,
        "h_improvements": 0,
        "z_gain": 0.0,
        "z_improvements": 0,
        "best_z": math.inf,
        "info_events": 0,
        "best_lb": 0,
        "patience": initial_patience,
        "revisions": 0,
        "bailouts": 0,
    }


def _utility(st):
    if st is None:
        return 0.0
    numerator = (
        st["h_gain"]
        + Z_UTILITY_WEIGHT * st["z_gain"]
        + INFO_WEIGHT * st["info_events"]
    )
    return numerator / max(1, st["spent_total"])


def adaptive_guided_quicksand_revision(
    E, goal, index, policy, budget, max_depth, max_open,
    seed, probe_ctx: P.ProbeContext,
    creativity=0.55, opener_cap=48, progress=250,
    frontier_limit=120000, probe_depth=3,
    probe_cap=2000, probe_total_cap=4000,
    probe_next_layer=30000, say=print,
    candidate_gate=None,
):
    B = P.B
    rng = random.Random(int(seed) + 2 * 1000003)
    local_use = defaultdict(int)
    shared_use = defaultdict(int)
    bit_cache = {}

    start = E.Node([(goal, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    tie = exp = 0
    probe_used_total = 0
    probes = 0
    false_zeros = 0
    seen = set()
    t0 = time.perf_counter()

    base_creativity = float(creativity)
    active_creativity = base_creativity
    bit_beta = float(NORMAL_BIT_BETA)

    mode = "native"
    profile = B.make_mode_profile(E, mode, active_creativity, opener_cap)
    best_h = B.h_hat(E, start.goals, start.sub)
    last_global_improve = 0
    transitions = []

    descent_streak = 0
    prev_improve_exp = None
    attention_window = 400
    saturate_until = 0
    last_probe_exp = -10**9
    stale_native, stale_high, stale_low = 1200, 1200, 2400

    min_patience = max(
        MIN_PATIENCE_ABS,
        int(math.ceil(MIN_PATIENCE_FRACTION * budget)),
    )
    base_patience = max(
        min_patience,
        int(math.ceil(BASE_PATIENCE_FRACTION * budget)),
    )
    max_patience = max(
        base_patience,
        int(math.ceil(MAX_PATIENCE_FRACTION * budget)),
    )

    basin_stats = defaultdict(lambda: _new_stats(base_patience))
    blocked_prefixes = set()
    active_basin = ()
    bailouts = 0
    revisions = 0

    revision_basin = None
    revision_until = 0

    say(
        "    controller start: recovered-8.002 explorer + fullgraph exactifier "
        "coord=%s h_hat=%.3f patience=[%s,%s] base=%s beta_l=%+.3f "
        "creativity=%.3f codec=%s"
        % (
            B.COORD[mode], best_h, f"{min_patience:,}", f"{max_patience:,}",
            f"{base_patience:,}", bit_beta, active_creativity, CB.CODEC,
        )
    )
    say(
        "    [QUICKSAND-RULE] joint stall = no H_hat improvement and no z_l "
        "improvement for one patience tranche; then beta_l->-beta_l and "
        "creativity->1-creativity for a bounded revision window"
    )
    if candidate_gate is not None:
        say(
            "    [ZERO-GATE] H=0 is necessary but not sufficient; only a "
            "certified candidate may halt search"
        )

    def set_controls(new_mode=None, new_creativity=None):
        nonlocal mode, active_creativity, profile
        if new_mode is not None:
            mode = new_mode
        if new_creativity is not None:
            active_creativity = float(new_creativity)
        profile = B.make_mode_profile(E, mode, active_creativity, opener_cap)

    def end_revision(reason, total_used):
        nonlocal revision_basin, revision_until, bit_beta, active_creativity
        if revision_basin is None:
            return
        old_basin = revision_basin
        revision_basin = None
        revision_until = 0
        bit_beta = abs(float(NORMAL_BIT_BETA))
        active_creativity = base_creativity
        set_controls(new_creativity=base_creativity)
        transitions.append((total_used, mode, mode, "REVISION-END " + reason))
        say(
            "      [REVISION-END] basin=%s reason=%s beta_l=%+.3f creativity=%.3f"
            % (old_basin, reason, bit_beta, active_creativity)
        )

    def blacklist_basin(basin, reason, total_used):
        nonlocal frontier, bailouts, active_basin, saturate_until
        if not basin or basin in blocked_prefixes:
            return
        st = basin_stats[basin]
        bailouts += 1
        st["bailouts"] += 1
        blocked_prefixes.add(basin)
        before = len(frontier)
        frontier = Q._prune_frontier(frontier, blocked_prefixes)
        removed = before - len(frontier)
        transitions.append((total_used, mode, "BAILOUT", reason))
        say(
            "      [JOINT-BAILOUT] basin=%s reason=%s spent_total=%s "
            "utility=%.6f pruned=%s"
            % (
                basin, reason, f"{st['spent_total']:,}", _utility(st),
                f"{removed:,}",
            )
        )
        if active_basin == basin:
            active_basin = ()
            saturate_until = 0

    def accept_zero(result, source, total_used, basin):
        nonlocal false_zeros
        if candidate_gate is None:
            return True
        say(
            "      [CANDIDATE-ZERO] source=%s total=%s basin=%s; verifying certificate"
            % (source, f"{total_used:,}", basin or "<root>")
        )
        try:
            accepted, detail = candidate_gate(result)
        except Exception as exc:
            accepted, detail = False, "%s: %s" % (type(exc).__name__, exc)
        if accepted:
            say("      [CERTIFIED-ZERO] certificate accepted; settlement gate OPEN")
            transitions.append((total_used, mode, "CERTIFIED-ZERO", str(detail)))
            return True
        false_zeros += 1
        say(
            "      [FALSE-ZERO] #%d rejected: %s; search continues"
            % (false_zeros, detail)
        )
        transitions.append((total_used, mode, "FALSE-ZERO", str(detail)))
        return False

    while frontier and (exp + probe_used_total) < budget:
        # A revision that has consumed its globally bounded exploration window
        # without benefit is not allowed to stretch to the full run budget.
        if revision_basin is not None and exp >= revision_until:
            doomed = revision_basin
            blacklist_basin(
                doomed,
                "inverse revision window expired without H_hat/z_l benefit",
                exp + probe_used_total,
            )
            end_revision("window-expired", exp + probe_used_total)
            set_controls(new_mode="high")

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
        l_bits = partial_certificate_bits(node, bit_cache)
        zl = z_length(node, bit_cache)

        h_improved = nh < best_h - H_IMPROVEMENT_EPS
        z_improved = False
        if st is not None:
            if math.isinf(st["best_z"]):
                st["best_z"] = zl
            elif zl < st["best_z"] - Z_IMPROVEMENT_EPS:
                old_z = st["best_z"]
                st["best_z"] = zl
                gain_z = old_z - zl
                st["z_gain"] += gain_z
                st["z_improvements"] += 1
                st["spent_since_benefit"] = 0
                z_improved = True
                say(
                    "      [L-IMPROVE] guided=%s total=%s basin=%s "
                    "z_l=%.4f->%.4f gain=%.4f raw_bits=%d depth=%d"
                    % (
                        f"{exp:,}", f"{total_used:,}", basin,
                        old_z, zl, gain_z, l_bits, len(node.trail),
                    )
                )

        if h_improved:
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
                st["h_improvements"] += 1
                st["spent_since_benefit"] = 0
                st["patience"] = min(
                    max_patience,
                    max(
                        st["patience"] + min_patience // 3,
                        int(math.ceil(st["patience"] * 1.25)),
                    ),
                )

            say(
                "      [H-IMPROVE] guided=%s total=%s %.3f->%.3f gain=%.3f "
                "streak=%d basin=%s z_l=%.4f raw_bits=%d utility=%.6f"
                % (
                    f"{exp:,}", f"{total_used:,}", old, best_h, gain,
                    descent_streak, basin or "<root>", zl, l_bits,
                    _utility(st),
                )
            )

            if descent_streak >= 2 and basin and basin not in blocked_prefixes:
                active_basin = basin
                local_patience = basin_stats[basin]["patience"]
                saturate_hold = min(
                    SATURATE_HOLD_CAP,
                    max(100, local_patience // 2),
                )
                saturate_until = exp + saturate_hold
                transitions.append(
                    (total_used, mode, "SATURATE", "repeated H descent in basin %s" % (basin,))
                )
                say(
                    "      [SATURATE] earned by repeated H descent; basin=%s "
                    "hold<=%s patience=%s"
                    % (basin, f"{saturate_hold:,}", f"{local_patience:,}")
                )

                remaining_probe = min(
                    probe_cap,
                    max(100, local_patience // 2),
                    probe_total_cap - probe_used_total,
                    budget - (exp + probe_used_total),
                )
                if remaining_probe > 0 and exp - last_probe_exp >= 250:
                    probes += 1
                    last_probe_exp = exp
                    say(
                        "      [PROXIMITY-ALARM] bounded diagnostic probe #%d "
                        "depth<=%d cap=%s basin=%s"
                        % (probes, probe_depth, f"{remaining_probe:,}", basin)
                    )
                    pr = P.run_probe(
                        probe_ctx, node, probe_depth, remaining_probe,
                        max_next_layer=probe_next_layer,
                    )
                    probe_used_total += pr.expanded
                    total_used = exp + probe_used_total
                    st["spent_total"] += pr.expanded
                    st["spent_since_benefit"] += pr.expanded

                    if pr.exact_h is not None:
                        say(
                            "      [EXACTIFY] CERTIFIED exact H=%d at snapshot; "
                            "probe_exp=%s total=%s"
                            % (pr.exact_h, f"{pr.expanded:,}", f"{total_used:,}")
                        )
                        transitions.append(
                            (total_used, mode, "SATURATE", "CERTIFIED exact shell")
                        )
                        witness = pr.witness
                        if witness is not None and witness.closed_witness is not None:
                            candidate = B.reconstruct(witness.closed_witness)
                            if accept_zero(candidate, "exactifier", total_used, basin):
                                return (
                                    candidate, total_used, best_h,
                                    transitions, "exactifier-settled",
                                )
                    else:
                        old_lb = st["best_lb"]
                        if pr.lower_bound > old_lb:
                            st["best_lb"] = pr.lower_bound
                            st["info_events"] += 1
                            st["spent_since_benefit"] = 0
                            say(
                                "      [INFO-GAIN] basin=%s certified lower bound "
                                "H>=%d (was %d)"
                                % (basin, pr.lower_bound, old_lb)
                            )

                        false_proximity = pr.lower_bound - nh > 0.5
                        say(
                            "      [EXACTIFY] no settlement in certified shells; "
                            "H>=%d checked_through=%d complete=%s probe_exp=%s"
                            % (
                                pr.lower_bound, pr.checked_through_depth,
                                pr.complete_to_requested_depth,
                                f"{pr.expanded:,}",
                            )
                        )
                        if false_proximity:
                            st["patience"] = max(
                                min_patience,
                                int(math.floor(st["patience"] * 0.60)),
                            )
                            saturate_until = 0
                            descent_streak = 0
                            transitions.append(
                                (total_used, mode, mode, "FALSE-PROXIMITY shortens patience")
                            )
                            say(
                                "      [FALSE-PROXIMITY] H_hat=%.3f versus "
                                "certified H>=%d; patience->%s"
                                % (nh, pr.lower_bound, f"{st['patience']:,}")
                            )

            if mode == "low" and revision_basin is None:
                oldm = mode
                set_controls(new_mode="native")
                transitions.append(
                    (total_used, oldm, mode, "torpor progress -> native")
                )
                say(
                    "      [CONTROL] TORPOR EXIT %s -> %s: progress restored"
                    % (B.COORD[oldm], B.COORD[mode])
                )

        # If the triggering basin makes progress during inverse revision, return
        # immediately to ordinary minimization.  The revision has done its job.
        if revision_basin is not None and basin == revision_basin and (h_improved or z_improved):
            st["patience"] = min(
                max_patience,
                max(st["patience"], int(math.ceil(st["patience"] * 1.20))),
            )
            end_revision("benefit-restored", total_used)

        # Joint-stall trigger.  The first tranche earns a bounded group-inverse
        # excursion; failure of that excursion leads to basin suppression.
        if st is not None and basin and basin not in blocked_prefixes:
            if st["spent_since_benefit"] >= st["patience"]:
                if revision_basin is None:
                    revisions += 1
                    st["revisions"] += 1
                    revision_basin = basin
                    hold = min(
                        REVISION_HOLD_CAP,
                        max(REVISION_HOLD_MIN, st["patience"]),
                    )
                    revision_until = exp + hold
                    bit_beta = inverse_bit_pressure(abs(NORMAL_BIT_BETA))
                    active_creativity = inverse_creativity(base_creativity)
                    oldm = mode
                    set_controls(new_mode="high", new_creativity=active_creativity)
                    st["spent_since_benefit"] = 0
                    saturate_until = 0
                    descent_streak = 0
                    transitions.append(
                        (
                            total_used, oldm, mode,
                            "REVISION joint H_hat/z_l stall basin %s" % (basin,),
                        )
                    )
                    say(
                        "      [REVISION] #%d joint stall basin=%s; "
                        "beta_l=%+.3f creativity %.3f->%.3f hold=%s; %s->%s"
                        % (
                            revisions, basin, bit_beta, base_creativity,
                            active_creativity, f"{hold:,}",
                            B.COORD[oldm], B.COORD[mode],
                        )
                    )
                    continue
                elif revision_basin == basin:
                    # This usually fires only if the basin consumes its full
                    # revised patience faster than the global revision timer.
                    doomed = revision_basin
                    blacklist_basin(
                        doomed,
                        "joint stall persisted through inverse revision",
                        total_used,
                    )
                    end_revision("persistent-joint-stall", total_used)
                    set_controls(new_mode="high")
                    continue

        revising = revision_basin is not None and exp < revision_until
        saturating = bool(active_basin) and exp <= saturate_until and not revising
        stale = exp - last_global_improve
        if not saturating and not revising:
            if mode == "native" and stale >= stale_native:
                oldm = mode
                set_controls(new_mode="high")
                last_global_improve = exp
                transitions.append(
                    (exp + probe_used_total, oldm, mode, "global stagnation -> SURGE")
                )
                say("      [CONTROL] SURGE %s -> %s" % (B.COORD[oldm], B.COORD[mode]))
            elif mode == "high" and stale >= stale_high:
                oldm = mode
                set_controls(new_mode="low")
                last_global_improve = exp
                transitions.append(
                    (exp + probe_used_total, oldm, mode, "failed surge -> TORPOR")
                )
                say("      [CONTROL] TORPOR %s -> %s" % (B.COORD[oldm], B.COORD[mode]))
            elif mode == "low" and stale >= stale_low:
                transitions.append(
                    (exp + probe_used_total, mode, "brute", "failed torpor -> brute")
                )
                say(
                    "      [CONTROL] TORPOR %s -> brute %s"
                    % (B.COORD[mode], B.COORD["brute"])
                )
                return None, exp + probe_used_total, best_h, transitions, "brute-requested"

        if progress and exp % progress == 0:
            ast = basin_stats[active_basin] if active_basin else st
            say(
                "      [GUIDED] guided=%s probe=%s total=%s open=%d "
                "best_h=%.3f node_h=%.3f raw_l_bits=%d z_l=%.4f "
                "beta_l=%+.3f creativity=%.3f mode=%s revise=%s "
                "saturate=%s frontier=%s revisions=%d bailouts=%d blocked=%d "
                "false_zeros=%d utility=%.6f elapsed=%.1fs"
                % (
                    f"{exp:,}", f"{probe_used_total:,}",
                    f"{exp + probe_used_total:,}", len(node.goals), best_h, nh,
                    l_bits, zl, bit_beta, active_creativity, mode,
                    revision_basin or "off",
                    "ON" if saturating else "off", f"{len(frontier):,}",
                    revisions, bailouts, len(blocked_prefixes), false_zeros,
                    _utility(ast), time.perf_counter() - t0,
                )
            )

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
        key = (
            node.depth,
            " ".join(gt.tokens()),
            tuple(
                sorted(
                    " ".join(E.apply_sub(g, node.sub).tokens())
                    for g, _, _ in rest
                )
            ),
        )
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        mlw = B.ML_WEIGHT[mode]
        sc_c = [mlw * x for x in policy.rank(gt, closers)] if closers else []
        sc_o = [mlw * x for x in policy.rank(gt, openers)] if openers else []
        ranked_c = E._candidate_scores(
            gt, closers, sc_c, profile, rng, local_use, shared_use
        )
        ranked_o = E._candidate_scores(
            gt, openers, sc_o, profile, rng, local_use, shared_use
        )
        chosen = ranked_c + E._counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng
        )
        curh = B.h_hat(E, node.goals, node.sub)
        parent_z = zl

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
                delta_h = curh - B.h_hat(E, successor_goals, s2)
                edge -= B.H_WEIGHT[mode] * math.tanh(delta_h)

            child = E.Node(
                successor_goals,
                s2,
                node.trail + ((slot, hix, step),),
                node.depth + 1,
            )
            child_z = z_length(child, bit_cache)
            delta_z = child_z - parent_z
            # Positive beta minimizes z_l.  During revision beta is its group
            # inverse, so the same term deliberately prefers the opposite local
            # compression behavior for a bounded time.
            edge += bit_beta * math.tanh(delta_z / Z_EDGE_SCALE)
            edge = max(0.05, edge)
            state_cost = 0.02 * len(successor_goals)

            if Q._blocked(child, blocked_prefixes):
                continue
            heapq.heappush(frontier, (priority + edge + state_cost, tie, child))

        if frontier_limit and len(frontier) > frontier_limit:
            keep = max(1000, frontier_limit // 2)
            frontier = heapq.nsmallest(keep, frontier)
            heapq.heapify(frontier)
            say(
                "      [MEMORY-GUARD] frontier pruned to %s best states"
                % f"{len(frontier):,}"
            )

    say(
        "    [QUICKSAND-SUMMARY] expansions=%s revisions=%d bailouts=%d "
        "blocked=%d best_h=%.3f"
        % (f"{exp + probe_used_total:,}", revisions, bailouts, len(blocked_prefixes), best_h)
    )
    return None, exp + probe_used_total, best_h, transitions, "guided-budget"


def main():
    P.adaptive_guided_exactify = adaptive_guided_quicksand_revision
    F.VERSION = VERSION
    return F.main()


if __name__ == "__main__":
    raise SystemExit(main())
