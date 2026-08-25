#!/usr/bin/env python3
"""Predator 8.005-R3I4-terminaldv.

Engineering-only continuation of the operational (3,4) Halo controller.

The previous DV-aware search rejected disjoint-variable violations as soon as
they became forced by ordinary Metamath variables, but deliberately left
unresolved metavariables alone.  Certificate emission later grounds every
remaining metavariable with the same per-type fallback variable.  Therefore a
logically complete branch could still become DV-illegal only at emission time
(e.g. two distinct class metavariables both ground to A).

8.005 closes exactly that engineering gap without changing the proof calculus,
R3 metacontrol, I4 imagination depth, search budgets, target access policy, or
verification boundary:

* while goals remain open, keep the existing sound partial DV pruning;
* when a branch reaches zero open goals, ground every remaining metavariable
  using the exact same P8.ground() rule and grammar-derived fallback ordering
  used by certificate emission;
* recheck every accumulated DV obligation after grounding;
* if terminal grounding makes a DV condition illegal, count the rejection and
  CONTINUE the existing frontier instead of returning a doomed candidate;
* only a terminal branch passing this final-ground DV gate may be returned to
  the ordinary certificate emitter and independent Metamath verifier.

The verifier remains authoritative.  This fallback only prevents the search
from stopping on a certificate that its own deterministic grounding step will
necessarily make invalid.
"""
from __future__ import annotations

import heapq
import importlib.util
import os
import random
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.004-R3I4-indexed.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_indexed", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.004-R3I4-indexed")
BASE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE)

R3I4 = BASE.R3I4
P8 = BASE.P8
COMP = R3I4.COMP
P8.VERSION = "8.005-R3I4-terminal-ground-dv"


def _emission_fallback_from_grammar():
    """Reconstruct cmd_prove's exact per-type fallback-variable choice.

    P8.cmd_prove scans $f declarations in Metamath declaration order and keeps
    the first variable for each typecode.  G.build_grammar scanned the same
    declarations in the same order into VARTYPE, whose insertion order is
    preserved by Python.  Thus this produces the same fallback trees without
    reading the target proof or changing certificate semantics.
    """
    fallback = {}
    for var, tc in P8.G.VARTYPE.items():
        fallback.setdefault(tc, P8.G.Tree(None, tc, (), var))
    return fallback


def _terminal_dv_ok(obligations, sub):
    """Check accumulated DVs after the exact emission-time grounding rule."""
    fallback = _emission_fallback_from_grammar()
    grounded = []
    try:
        for tx, ty, x, y in obligations:
            gx = P8.ground(tx, sub, fallback)
            gy = P8.ground(ty, sub, fallback)
            grounded.append((gx, gy, x, y))
    except KeyError:
        # Certificate emission would have no fallback for this surviving type.
        # Treat the terminal branch as non-emittable and keep searching.
        return False
    return R3I4._dv_ok(tuple(grounded), {})


def _notable_count(n):
    """Log the first few terminal rejections and then sparse milestones."""
    return n <= 5 or n in {10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000}


def prove_r3i4_terminaldv(goal_tree, index, budget, max_depth, rank=None,
                          say=print, progress=2000, max_open=6, profile=None,
                          seed=0, shared_use=None, agent_name=None):
    """Same R3/I4 best-first search, with terminal-ground DV rejection."""
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

    while frontier and exp < budget:
        _fhat, _reachhat, _rhat, _neglegacy, _, g_cost, node = heapq.heappop(frontier)
        node_dv = dv_by_node.pop(node, ())
        exp += 1
        if not R3I4._dv_ok(node_dv, node.sub):
            dv_rejects += 1
            continue
        live_rhat = COMP.settlement_distance_hat(node.goals, node.sub)
        mode, stale, dup_rate = meta.observe(exp, live_rhat, False)
        policy = meta.policy()

        if not announced and say:
            say("      [%s] operational (3,4) active: R3 metacontrol + 4-ply reasoned FUTUREBANK + DV gate + terminal-ground fallback"
                % agent_name)
            announced = True
        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open, r_hat=%.3f, R3=%s, stale=%d, dup=%.1f%%, imagined=%s, dvrej=%s, dvfinal=%s, %.0fs"
                % (agent_name, f"{exp:,}", len(node.goals), live_rhat,
                   mode, stale, 100.0 * dup_rate, f"{total_imagined:,}",
                   f"{dv_rejects:,}", f"{dv_final_rejects:,}",
                   time.perf_counter() - t0))

        if not node.goals:
            # Crucial 8.005 fallback: use the SAME deterministic grounding rule
            # the ordinary Step.emit/P8.ground path will use.  If that grounding
            # makes an accumulated $d condition illegal, this is not an
            # emittable certificate.  Reject only this terminal branch and
            # continue the already-built frontier.
            if not _terminal_dv_ok(node_dv, node.sub):
                dv_final_rejects += 1
                if say and _notable_count(dv_final_rejects):
                    say("      [%s] terminal DV rejection #%s after grounding; continuing frontier"
                        % (agent_name, f"{dv_final_rejects:,}"))
                continue

            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            if say and dv_final_rejects:
                say("      [%s] terminal branch passed final-ground DV gate after %s rejected terminal shortcut(s)"
                    % (agent_name, f"{dv_final_rejects:,}"))
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
        chosen_openers = R3I4._select_openers_r3(
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

    if say and dv_final_rejects:
        say("      [%s] search ended after rejecting %s terminal branch(es) that failed emission-time DV grounding"
            % (agent_name, f"{dv_final_rejects:,}"))
    return None, exp


# Install the engineering fallback without altering prove_population or the
# command-line/verifier machinery.  prove_population resolves P8.prove at run
# time, so every population agent now keeps searching past illegal terminals.
P8.prove = prove_r3i4_terminaldv


# Extend the existing selftest with the exact bug class observed on Halo:
# two distinct unresolved metavariables are harmless to the partial DV gate,
# but emission grounds both to the same fallback variable and must reject.
_ORIG_SELFTEST = P8.cmd_selftest


def _cmd_selftest_terminal_dv(a):
    rc = _ORIG_SELFTEST(a)
    if rc:
        return rc
    m1 = P8.fresh("wff")
    m2 = P8.fresh("wff")
    obligation = ((m1, m2, "left", "right"),)
    partial_ok = R3I4._dv_ok(obligation, {})
    terminal_ok = _terminal_dv_ok(obligation, {})
    ok = partial_ok and not terminal_ok
    print("  [4] terminal-ground DV fallback catches fallback-variable collision")
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _cmd_selftest_terminal_dv


def main():
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
