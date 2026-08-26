#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import random
import subprocess
import sys
import time
from collections import defaultdict
from typing import Optional

import predator8_015_bidirectional_attention as B
from predator8_ml_ranker import RuntimePolicy
from bounded_exactifier import bounded_bfs_exactify

VERSION = "8.016-ML-attention-exactify-surge-torpor"
ROOT = Path(__file__).resolve().parent

@dataclass(eq=False)
class ProbeState:
    node: object | None = None
    accepted: bool = False
    closed_witness: object | None = None

@dataclass
class ProbeContext:
    E: object
    index: object
    mm: object
    target_data: tuple
    fvar: dict
    fallback: dict

    def _reconstruct(self, node):
        return B.reconstruct(node)

    def closed_verifies(self, node) -> bool:
        if node.goals:
            return False
        try:
            root, sub = self._reconstruct(node)
            if root is None:
                return False
            proof = root.emit(sub, self.fvar, self.fallback)
            E = self.E
            check = E.MM()
            check.labels = dict(self.mm.labels)
            check.order = list(self.mm.order)
            check.proofs = dict(self.mm.proofs)
            check.constants, check.variables = self.mm.constants, self.mm.variables
            check.scope_dvs = dict(self.mm.scope_dvs)
            check.labels["__p8_016_probe__"] = ("$p", self.target_data)
            check.proofs["__p8_016_probe__"] = proof
            check.scope_dvs["__p8_016_probe__"] = self.target_data[0]
            return check.verify("__p8_016_probe__") == "ok"
        except Exception:
            return False

    def all_successors(self, state: ProbeState):
        if state.accepted:
            return ()
        node = state.node
        if node is None:
            return ()
        E = self.E
        if not node.goals:
            if self.closed_verifies(node):
                return (ProbeState(None, True, node),)
            return ()

        gi = E.pick_goal(node.goals, node.sub)
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = E.apply_sub(gt, node.sub)
        closers, openers = self.index.candidates(gt)
        out = []
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
            out.append(ProbeState(
                E.Node(newgoals + rest, s2,
                       node.trail + ((slot, hix, step),), node.depth + 1),
                False, None))
        return out

def make_probe_context(E, index, mm, target_data, cutoff):
    fvar, fallback = B.formal_variables(E, mm, cutoff)
    return ProbeContext(E, index, mm, target_data, fvar, fallback)

def run_probe(ctx: ProbeContext, node, max_depth: int, max_expansions: int):
    return bounded_bfs_exactify(
        ProbeState(node=node),
        all_successors=ctx.all_successors,
        is_settled=lambda s: bool(s.accepted),
        key=lambda s: s,
        max_depth=max_depth,
        max_expansions=max_expansions,
        completeness_evidence=(
            "all assertion-head-compatible candidates enumerated; each candidate "
            "subjected to actual unification; no opener cap/ranker/policy pruning; "
            "proof histories not quotiented; terminal edge requires Metamath CV"
        ),
    )

def adaptive_guided_exactify(E, goal, index, policy, budget, max_depth, max_open,
                             seed, probe_ctx: ProbeContext,
                             creativity=0.55, opener_cap=48, progress=250,
                             frontier_limit=120000, probe_depth=3,
                             probe_cap=2000, probe_total_cap=4000, say=print):
    rng = random.Random(int(seed) + 2 * 1000003)
    local_use = defaultdict(int)
    shared_use = defaultdict(int)
    start = E.Node([(goal, None, 0)], {}, (), 0)
    import heapq
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

    say("    controller start: recovered-8.002 explorer + exactifier coord=%s h_hat=%.3f"
        % (B.COORD[mode], best_h))

    while frontier and (exp + probe_used_total) < budget:
        priority, _, node = heapq.heappop(frontier)
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
            say("      [H-IMPROVE] guided=%s total=%s %.3f->%.3f streak=%d mode=%s"
                % (f"{exp:,}", f"{total_used:,}", old, best_h,
                   descent_streak, mode))

            if descent_streak >= 2:
                attention_until = exp + attention_hold
                transitions.append((total_used, mode, mode,
                                    "ATTENTION: consecutive H descent"))
                say("      [ATTENTION] consecutive descent; snapshot eligible for exactification")

                remaining_probe = min(
                    probe_cap,
                    probe_total_cap - probe_used_total,
                    budget - (exp + probe_used_total),
                )
                if remaining_probe > 0 and exp - last_probe_exp >= 250:
                    probes += 1
                    last_probe_exp = exp
                    say("      [PROXIMITY-ALARM] launching complete local BFS probe #%d "
                        "depth<=%d cap=%s" %
                        (probes, probe_depth, f"{remaining_probe:,}"))
                    pr = run_probe(probe_ctx, node, probe_depth, remaining_probe)
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
                "mode=%s attention=%s frontier=%s elapsed=%.1fs"
                % (f"{exp:,}", f"{probe_used_total:,}",
                   f"{exp + probe_used_total:,}", len(node.goals), best_h, mode,
                   "ON" if attention_active else "off", f"{len(frontier):,}",
                   time.perf_counter() - t0))

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
                    ok = False; break
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
            heapq.heappush(
                frontier,
                (priority + edge + state_cost, tie,
                 E.Node(successor_goals, s2,
                        node.trail + ((slot, hix, step),), node.depth + 1)))

        if frontier_limit and len(frontier) > frontier_limit:
            keep = max(1000, frontier_limit // 2)
            frontier = heapq.nsmallest(keep, frontier)
            heapq.heapify(frontier)
            say("      [MEMORY-GUARD] frontier pruned to %s best states"
                % f"{len(frontier):,}")

    return None, exp + probe_used_total, best_h, transitions, "guided-budget"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--budget", type=int, default=30000)
    ap.add_argument("--brute-reserve", type=int, default=6000)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--max-open", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--creativity", type=float, default=0.55)
    ap.add_argument("--opener-cap", type=int, default=48)
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--frontier-limit", type=int, default=120000)
    ap.add_argument("--probe-depth", type=int, default=3)
    ap.add_argument("--probe-cap", type=int, default=2000)
    ap.add_argument("--probe-total-cap", type=int, default=4000)
    ap.add_argument("--out", default="prcom_p8_016.mm")
    a = ap.parse_args()
    if a.label != "prcom":
        ap.error("8.016 experiment is intentionally scoped to prcom")
    if not (0 <= a.brute_reserve <= a.budget):
        ap.error("brute reserve must lie in [0,budget]")

    environment = Path(a.environment).resolve()
    model = Path(a.model).resolve()
    E = B.load_engine(Path(a.engine).resolve())
    print("=" * 78)
    print("Predator %s -- prcom -- global budget %s" % (VERSION, f"{a.budget:,}"))
    print("=" * 78)
    mm = E.load(str(environment), say=print)
    cutoff = mm.order.index(a.label)
    by_tc = B.strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=print)
    statement = mm.labels[a.label][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)
    policy = RuntimePolicy.load(model, E, by_tc)
    md = policy.artifact["metadata"]
    if md.get("environment_sha256") != B.sha256(environment):
        raise SystemExit("model/environment hash mismatch")
    if md.get("cutoff_before") != a.label or md.get("target_proof_used") is not False \
            or md.get("downstream_used") is not False:
        raise SystemExit("model leakage/cutoff attestation failed")

    target_data = mm.labels[a.label][1]
    probe_ctx = make_probe_context(E, index, mm, target_data, cutoff)
    original = mm.proofs
    mm.proofs = B.GuardedProofs(original, a.label)
    probe_ctx.mm = mm

    started = time.perf_counter()
    try:
        guided_cap = a.budget - a.brute_reserve
        result, gused, besth, transitions, reason = adaptive_guided_exactify(
            E, goal, index, policy, guided_cap, a.max_depth, a.max_open, a.seed,
            probe_ctx=probe_ctx, creativity=a.creativity,
            opener_cap=a.opener_cap, progress=a.progress,
            frontier_limit=a.frontier_limit, probe_depth=a.probe_depth,
            probe_cap=a.probe_cap, probe_total_cap=a.probe_total_cap)
        bused = 0
        brute_depth = None
        if result is None:
            remaining = a.budget - gused
            print("    meta-controller: guided stop reason=%s; remaining=%s; entering brute %s"
                  % (reason, f"{remaining:,}", B.COORD["brute"]))
            result, bused, brute_depth = B.brute_iddfs(
                E, goal, index, remaining, a.max_depth, a.max_open,
                progress=a.progress)
    finally:
        mm.proofs = original

    total = gused + bused
    elapsed = time.perf_counter() - started
    print("  CONTROL SUMMARY: guided+probe=%s brute=%s total=%s/%s best_h=%.3f transitions=%s"
          % (f"{gused:,}", f"{bused:,}", f"{total:,}", f"{a.budget:,}",
             besth, transitions))
    if result is None:
        print("  OUTCOME: UNKNOWN UNDER DECLARED RESOURCE BOUNDS (%s expansions, %.1fs)"
              % (f"{total:,}", elapsed))
        return 1

    verdict, proof, output = B.verify_emit(
        E, mm, cutoff, a.label, result, environment, a.out, model)
    print("  candidate found after total %s expansions, %.1fs; proof steps=%s; in-process CV=%s"
          % (f"{total:,}", elapsed, f"{len(proof):,}", verdict.upper()))
    if verdict != "ok":
        print("  OUTCOME: PROTOCOL FAILURE")
        return 2
    external = subprocess.run(
        [sys.executable, str(ROOT / "predator8_external_cv.py"),
         str(environment), "--target", a.label, "--certificate", str(output)],
        cwd=str(ROOT), text=True, capture_output=True, check=False)
    print((external.stdout + external.stderr).strip())
    if external.returncode:
        print("  OUTCOME: PROTOCOL FAILURE")
        return 2
    print("  OUTCOME: VERIFIED PROOF")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
