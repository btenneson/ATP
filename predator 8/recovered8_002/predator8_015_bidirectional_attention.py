#!/usr/bin/env python3
"""Predator 8.015: recovered ML search + attention/surge/torpor/brute fallback.

The formal proof rules, parser, unifier, certificate emitter, and verifier are
those of the recovered frozen Predator 8.001 engine.  The learned policy only
ranks legal moves.  Control states alter search ordering, never admissibility or
verification.

Native mode is deliberately the recovered 8.002 explorer profile.  In native
mode, H telemetry is observation-only: it does not modify candidate or frontier
priority.  Consecutive best-H descent therefore triggers ATTENTION by holding
course rather than perturbing a productive recovered policy.  Persistent
stagnation can trigger SURGE (more control/creativity), then TORPOR (less
control, more coverage), then a bounded deterministic brute-force fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import importlib.util
import math
import random
import subprocess
import sys
import time
from collections import UserDict, defaultdict
from pathlib import Path

from predator8_ml_ranker import RuntimePolicy

ROOT = Path(__file__).resolve().parent
VERSION = "8.015-ML-attention-surge-torpor-bruteforce"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_engine(path):
    spec = importlib.util.spec_from_file_location("p8_015_core", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen engine")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


class GuardedProofs(UserDict):
    def __init__(self, source, blocked):
        super().__init__(source)
        self.blocked = blocked

    def __getitem__(self, key):
        if key == self.blocked:
            raise AssertionError("target proof access attempted: " + key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == self.blocked:
            raise AssertionError("target proof access attempted: " + key)
        return super().get(key, default)


def strict_prefix_grammar(E, mm, cutoff):
    p = type("PrefixMM", (), {})()
    p.order = mm.order[:cutoff]
    p.labels = mm.labels
    return E.G.build_grammar(p)


def formal_variables(E, mm, cutoff):
    fvar, fallback = {}, {}
    for label in mm.order[:cutoff]:
        typ, data = mm.labels[label]
        if typ == "$f":
            fvar.setdefault(data[1], label)
            fallback.setdefault(data[0], E.G.Tree(None, data[0], (), data[1]))
    return fvar, fallback


def token_count(E, goals, sub):
    total = 0
    for g, _, _ in goals:
        try:
            total += len(E.apply_sub(g, sub).tokens())
        except Exception:
            total += 10
    return total


def h_hat(E, goals, sub):
    if not goals:
        return 0.0
    metas = set()
    for g, _, _ in goals:
        E.n_metas(E.apply_sub(g, sub), sub, metas)
    return (1.0 + len(goals)
            + 0.015 * token_count(E, goals, sub)
            + 0.02 * math.tanh(len(metas) / 8.0))


def reconstruct(node):
    root = None
    for parent, ix, st in node.trail:
        if parent is None:
            root = st
        else:
            parent.subs[ix] = st
    return root, node.sub


def make_mode_profile(E, mode, creativity=0.55, opener_cap=48):
    if mode == "native":
        # Exact recovered 8.002 explorer profile (third population agent).
        return E.make_profiles(4, creativity, opener_cap)[2]
    if mode == "high":
        return E.Profile("surge-(3,4)", 1.35, 0.75, 0.55, 0.12, 0.68, 80, 1.0)
    if mode == "low":
        return E.Profile("torpor-(1,2)", 0.05, 0.05, 0.03, 0.25, 0.10, 96, 1.0)
    raise ValueError(mode)


COORD = {"native": (2, 3), "high": (3, 4), "low": (1, 2), "brute": (0, 0)}
ML_WEIGHT = {"native": 1.0, "high": 1.10, "low": 0.30}
H_WEIGHT = {"native": 0.0, "high": 0.25, "low": 0.10}


def adaptive_guided(E, goal, index, policy, budget, max_depth, max_open,
                    seed, creativity=0.55, opener_cap=48, progress=250,
                    frontier_limit=120000, say=print):
    # Historical 8.002 explorer random stream.
    rng = random.Random(int(seed) + 2 * 1000003)
    local_use = defaultdict(int)
    shared_use = defaultdict(int)
    start = E.Node([(goal, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    tie = exp = 0
    seen = set()
    t0 = time.perf_counter()

    mode = "native"
    profile = make_mode_profile(E, mode, creativity, opener_cap)
    best_h = h_hat(E, start.goals, start.sub)
    last_improve = 0
    transitions = []

    # Consecutive descent attention.  Observation only in native mode.
    descent_streak = 0
    prev_improve_exp = None
    attention_until = 0
    attention_window = 400
    attention_hold = 900

    stale_native = 1200
    stale_high = 1200
    stale_low = 2400

    say("    controller start: native recovered-8.002 explorer coord=%s h_hat=%.3f"
        % (COORD[mode], best_h))

    while frontier and exp < budget:
        priority, _, node = heapq.heappop(frontier)
        exp += 1
        nh = h_hat(E, node.goals, node.sub)

        if nh < best_h - 0.05:
            old = best_h
            best_h = nh
            if prev_improve_exp is not None and exp - prev_improve_exp <= attention_window:
                descent_streak += 1
            else:
                descent_streak = 1
            prev_improve_exp = exp
            last_improve = exp
            say("      [H-IMPROVE] exp=%s %.3f->%.3f streak=%d mode=%s coord=%s"
                % (f"{exp:,}", old, best_h, descent_streak, mode, COORD[mode]))
            if descent_streak >= 2:
                attention_until = exp + attention_hold
                transitions.append((exp, mode, mode,
                                    "ATTENTION: consecutive H descent; hold course"))
                say("      [ATTENTION] consecutive descent: hold %s through exp=%s"
                    % (mode, f"{attention_until:,}"))
            if mode == "low":
                oldm = mode
                mode = "native"
                profile = make_mode_profile(E, mode, creativity, opener_cap)
                transitions.append((exp, oldm, mode, "torpor progress -> native"))
                say("      [CONTROL] TORPOR EXIT %s -> %s: progress restored"
                    % (COORD[oldm], COORD[mode]))

        attention_active = exp <= attention_until
        stale = exp - last_improve
        if not attention_active:
            if mode == "native" and stale >= stale_native:
                oldm = mode
                mode = "high"
                profile = make_mode_profile(E, mode, creativity, opener_cap)
                last_improve = exp
                transitions.append((exp, oldm, mode, "stagnation -> SURGE"))
                say("      [CONTROL] SURGE %s -> %s" % (COORD[oldm], COORD[mode]))
            elif mode == "high" and stale >= stale_high:
                oldm = mode
                mode = "low"
                profile = make_mode_profile(E, mode, creativity, opener_cap)
                last_improve = exp
                transitions.append((exp, oldm, mode, "failed surge -> TORPOR"))
                say("      [CONTROL] TORPOR %s -> %s" % (COORD[oldm], COORD[mode]))
            elif mode == "low" and stale >= stale_low:
                transitions.append((exp, mode, "brute", "failed torpor -> brute"))
                say("      [CONTROL] TORPOR %s -> brute %s at exp=%s"
                    % (COORD[mode], COORD["brute"], f"{exp:,}"))
                return None, exp, best_h, transitions, "brute-requested"

        if progress and exp % progress == 0:
            say("      [GUIDED] exp=%s open=%d best_h=%.3f mode=%s attention=%s frontier=%s elapsed=%.1fs"
                % (f"{exp:,}", len(node.goals), best_h, mode,
                   "ON" if attention_active else "off", f"{len(frontier):,}",
                   time.perf_counter() - t0))

        if not node.goals:
            return reconstruct(node), exp, best_h, transitions, "settled"
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
        mlw = ML_WEIGHT[mode]
        sc_c = [mlw * x for x in policy.rank(gt, closers)] if closers else []
        sc_o = [mlw * x for x in policy.rank(gt, openers)] if openers else []
        ranked_c = E._candidate_scores(gt, closers, sc_c, profile, rng,
                                       local_use, shared_use)
        ranked_o = E._candidate_scores(gt, openers, sc_o, profile, rng,
                                       local_use, shared_use)
        chosen = ranked_c + E._counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng)
        curh = h_hat(E, node.goals, node.sub)

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
            # Native mode: exactly recovered 8.002 priority formula.
            edge = (0.25 if not e_hyps else 1.0) - 0.20 * guide
            if H_WEIGHT[mode] > 0.0:
                delta = curh - h_hat(E, successor_goals, s2)
                edge -= H_WEIGHT[mode] * math.tanh(delta)
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

    return None, exp, best_h, transitions, "guided-budget"


def brute_iddfs(E, goal, index, budget, max_depth, max_open,
                progress=250, say=print):
    used = 0
    t0 = time.perf_counter()
    for limit in range(1, max_depth + 1):
        say("      [BRUTE] iterative depth limit=%d used=%s/%s"
            % (limit, f"{used:,}", f"{budget:,}"))
        stack = [E.Node([(goal, None, 0)], {}, (), 0)]
        seen = set()
        while stack and used < budget:
            node = stack.pop()
            used += 1
            if progress and used % progress == 0:
                say("      [BRUTE] exp=%s limit=%d stack=%s elapsed=%.1fs"
                    % (f"{used:,}", limit, f"{len(stack):,}",
                       time.perf_counter() - t0))
            if not node.goals:
                return reconstruct(node), used, limit
            if node.depth >= limit or len(node.goals) > max_open:
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
            # Deterministic lexical enumeration; no learned or stochastic ranking.
            items = sorted(closers + openers, key=lambda x: x[0], reverse=True)
            children = []
            for lab, ct, data in items:
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
                if ok:
                    children.append(E.Node(
                        newgoals + rest, s2,
                        node.trail + ((slot, hix, step),), node.depth + 1))
            stack.extend(children)
        if used >= budget:
            break
    return None, used, None


def verify_emit(E, mm, cutoff, label, result, environment, output, model):
    root, sub = result
    fvar, fallback = formal_variables(E, mm, cutoff)
    proof = root.emit(sub, fvar, fallback)
    statement = mm.labels[label][1][3]
    output = Path(output)
    output.write_text(
        "$( Predator %s candidate for %s; model %s $)\n" %
        (VERSION, label, sha256(model))
        + "$[ %s $]\n" % Path(environment).name
        + "chk $p %s $= %s $.\n" %
        (" ".join(statement), " ".join(proof)), encoding="utf-8")

    check = E.MM()
    check.labels = dict(mm.labels)
    check.order = list(mm.order)
    check.proofs = dict(mm.proofs)
    check.constants, check.variables = mm.constants, mm.variables
    check.scope_dvs = dict(mm.scope_dvs)
    data = mm.labels[label][1]
    check.labels["__p8_015_check__"] = ("$p", data)
    check.proofs["__p8_015_check__"] = proof
    check.scope_dvs["__p8_015_check__"] = mm.scope_dvs.get(label, data[0])
    verdict = check.verify("__p8_015_check__")
    return verdict, proof, output


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
    ap.add_argument("--out", default="prcom_p8_015.mm")
    a = ap.parse_args()
    if a.brute_reserve < 0 or a.brute_reserve > a.budget:
        ap.error("brute reserve must lie in [0,budget]")

    environment = Path(a.environment).resolve()
    model = Path(a.model).resolve()
    engine_path = Path(a.engine).resolve()
    E = load_engine(engine_path)

    print("=" * 78)
    print("Predator %s -- %s -- global budget %s" %
          (VERSION, a.label, f"{a.budget:,}"))
    print("=" * 78)
    mm = E.load(str(environment), say=print)
    cutoff = mm.order.index(a.label)
    by_tc = strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=print)
    statement = mm.labels[a.label][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    policy = RuntimePolicy.load(model, E, by_tc)
    md = policy.artifact["metadata"]
    if md.get("environment_sha256") != sha256(environment):
        raise SystemExit("model/environment hash mismatch")
    if md.get("cutoff_before") != a.label:
        raise SystemExit("model cutoff mismatch")
    if md.get("target_proof_used") is not False:
        raise SystemExit("target proof exclusion not attested")
    if md.get("downstream_used") is not False:
        raise SystemExit("downstream exclusion not attested")
    print("  policy: clean pre-%s; theorems=%s; target proof used=NO; downstream used=NO"
          % (a.label, md.get("theorems")))
    print("  environment sha256: %s" % sha256(environment))
    print("  model sha256: %s" % sha256(model))

    original = mm.proofs
    mm.proofs = GuardedProofs(original, a.label)
    started = time.perf_counter()
    try:
        guided_cap = a.budget - a.brute_reserve
        result, gused, besth, transitions, reason = adaptive_guided(
            E, goal, index, policy, guided_cap, a.max_depth, a.max_open,
            a.seed, creativity=a.creativity, opener_cap=a.opener_cap,
            progress=a.progress, frontier_limit=a.frontier_limit)
        bused = 0
        brute_depth = None
        if result is None:
            remaining = a.budget - gused
            print("    meta-controller: guided stop reason=%s; remaining=%s; entering brute %s"
                  % (reason, f"{remaining:,}", COORD["brute"]))
            result, bused, brute_depth = brute_iddfs(
                E, goal, index, remaining, a.max_depth, a.max_open,
                progress=a.progress)
    finally:
        mm.proofs = original

    total = gused + bused
    elapsed = time.perf_counter() - started
    print("  CONTROL SUMMARY: guided=%s brute=%s total=%s/%s best_h=%.3f transitions=%s"
          % (f"{gused:,}", f"{bused:,}", f"{total:,}", f"{a.budget:,}",
             besth, transitions))
    if brute_depth is not None:
        print("  brute solution depth limit: %d" % brute_depth)

    if result is None:
        print("  OUTCOME: UNKNOWN UNDER DECLARED RESOURCE BOUNDS (%s expansions, %.1fs)"
              % (f"{total:,}", elapsed))
        return 1

    verdict, proof, output = verify_emit(
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