#!/usr/bin/env python3
"""Untrained ACO proof search for Metamath `prcom`.

No learned model, revision controller, target-proof replay, downstream theorem,
or target-distance oracle is used.  Candidate move probability is pheromone-only
(beta=0 in the preregistered pilot).  A simple structural h_hat is used only as
a pre-settlement partial-progress reinforcement signal.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import time
from collections import UserDict, defaultdict
from pathlib import Path


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


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("aco_prcom_core", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen engine")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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


def weighted_pick(items, weights, rng):
    total = sum(weights)
    if total <= 0:
        return items[rng.randrange(len(items))]
    r = rng.random() * total
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if r <= acc:
            return item
    return items[-1]


def legal_successors(E, index, node):
    gi = E.pick_goal(node.goals, node.sub)
    gt, slot, hix = node.goals[gi]
    rest = node.goals[:gi] + node.goals[gi + 1:]
    gt = E.apply_sub(gt, node.sub)
    closers, openers = index.candidates(gt)
    out = []
    attempts = 0
    for lab, ct, data in closers + openers:
        attempts += 1
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
        out.append((lab, E.Node(newgoals + rest, s2,
                                node.trail + ((slot, hix, step),),
                                node.depth + 1)))
    return out, attempts


def run_ant(E, start, index, pheromone, rng, ant_budget, alpha, max_open):
    node = start
    applications = 0
    transactions = 0
    labels = []
    initial_h = h_hat(E, node.goals, node.sub)
    best_h = initial_h
    best_prefix = []

    while applications < ant_budget:
        if not node.goals:
            return {
                "solved": True,
                "node": node,
                "applications": applications,
                "transactions": transactions,
                "labels": labels,
                "initial_h": initial_h,
                "best_h": 0.0,
                "best_prefix": list(labels),
            }
        if len(node.goals) > max_open:
            break

        succ, attempts = legal_successors(E, index, node)
        transactions += attempts
        if not succ:
            break

        weights = [max(1e-12, pheromone[lab]) ** alpha for lab, _ in succ]
        lab, node = weighted_pick(succ, weights, rng)
        labels.append(lab)
        applications += 1
        hh = h_hat(E, node.goals, node.sub)
        if hh < best_h - 1e-12:
            best_h = hh
            best_prefix = list(labels)

    return {
        "solved": False,
        "node": node,
        "applications": applications,
        "transactions": transactions,
        "labels": labels,
        "initial_h": initial_h,
        "best_h": best_h,
        "best_prefix": best_prefix,
    }


def verify_candidate(E, mm, target_label, cutoff, solved_node):
    root, sub = reconstruct(solved_node)
    if root is None:
        return False, None
    fvar, fallback = formal_variables(E, mm, cutoff)
    proof = root.emit(sub, fvar, fallback)
    target_data = mm.labels[target_label][1]
    check = E.MM()
    check.labels = dict(mm.labels)
    check.order = list(mm.order)
    check.proofs = {}
    check.constants, check.variables = mm.constants, mm.variables
    check.scope_dvs = dict(mm.scope_dvs)
    synthetic = "__aco_prcom_candidate__"
    check.labels[synthetic] = ("$p", target_data)
    check.proofs[synthetic] = proof
    check.scope_dvs[synthetic] = target_data[0]
    ok = check.verify(synthetic) == "ok"
    return ok, proof


def run_colony(E, mm, target_label, cutoff, goal, index, *, seed, batches,
               ants_per_batch, ant_budget, alpha, rho, partial_q,
               partial_elite, max_open, learning):
    rng = random.Random(seed)
    start = E.Node([(goal, None, 0)], {}, (), 0)
    # Pheromone is created lazily for legal assertion labels only.
    pheromone = defaultdict(lambda: 1.0)
    total_applications = 0
    total_transactions = 0
    ants_run = 0
    global_best_h = h_hat(E, start.goals, start.sub)
    history = []
    t0 = time.perf_counter()

    for batch in range(1, batches + 1):
        rows = []
        for ant_index in range(1, ants_per_batch + 1):
            # Each ant must get a fresh proof-state object; nodes/steps are mutable.
            fresh = E.Node([(goal, None, 0)], {}, (), 0)
            r = run_ant(E, fresh, index, pheromone, rng, ant_budget, alpha, max_open)
            ants_run += 1
            total_applications += r["applications"]
            total_transactions += r["transactions"]
            global_best_h = min(global_best_h, r["best_h"])
            if r["solved"]:
                verified, proof = verify_candidate(E, mm, target_label, cutoff, r["node"])
                wall = time.perf_counter() - t0
                return {
                    "solved": bool(verified),
                    "closed_all_goals": True,
                    "verified": bool(verified),
                    "proof": proof if verified else None,
                    "proof_length": None if proof is None else len(proof),
                    "seed": seed,
                    "learning": learning,
                    "alpha": alpha,
                    "rho": rho,
                    "batches_limit": batches,
                    "ants_per_batch": ants_per_batch,
                    "ant_budget": ant_budget,
                    "partial_q": partial_q,
                    "partial_elite": partial_elite,
                    "max_open": max_open,
                    "batches_consumed": batch,
                    "settled_by_ant_in_batch": ant_index,
                    "ants_run": ants_run,
                    "total_applications": total_applications,
                    "total_transactions": total_transactions,
                    "best_h": 0.0,
                    "wall_seconds": wall,
                    "history": history,
                }
            rows.append(r)

        reinforced = []
        if learning:
            keep = 1.0 - rho
            for lab in list(pheromone.keys()):
                pheromone[lab] = max(1e-12, pheromone[lab] * keep)

            ranked = sorted(rows, key=lambda x: (x["best_h"], x["applications"]))
            for r in ranked[:partial_elite]:
                improvement = max(0.0, r["initial_h"] - r["best_h"])
                prefix = r["best_prefix"]
                if improvement <= 0.0 or not prefix:
                    continue
                dep = partial_q * improvement / len(prefix)
                for lab in prefix:
                    pheromone[lab] += dep
                reinforced.append({
                    "best_h": r["best_h"],
                    "improvement": improvement,
                    "prefix_length": len(prefix),
                })

        history.append({
            "batch": batch,
            "batch_best_h": min(r["best_h"] for r in rows),
            "global_best_h": global_best_h,
            "reinforced": reinforced,
        })

    return {
        "solved": False,
        "closed_all_goals": False,
        "verified": False,
        "proof": None,
        "proof_length": None,
        "seed": seed,
        "learning": learning,
        "alpha": alpha,
        "rho": rho,
        "batches_limit": batches,
        "ants_per_batch": ants_per_batch,
        "ant_budget": ant_budget,
        "partial_q": partial_q,
        "partial_elite": partial_elite,
        "max_open": max_open,
        "batches_consumed": batches,
        "settled_by_ant_in_batch": None,
        "ants_run": ants_run,
        "total_applications": total_applications,
        "total_transactions": total_transactions,
        "best_h": global_best_h,
        "wall_seconds": time.perf_counter() - t0,
        "history": history,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment", type=Path)
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--target", default="prcom")
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--batches", type=int, default=200)
    ap.add_argument("--ants", type=int, default=8)
    ap.add_argument("--ant-budget", type=int, default=64)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--rho", type=float, default=0.15)
    ap.add_argument("--partial-q", type=float, default=5.0)
    ap.add_argument("--partial-elite", type=int, default=4)
    ap.add_argument("--max-open", type=int, default=16)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    E = load_engine(args.engine.resolve())
    mm = E.load(str(args.environment.resolve()), say=lambda *a, **k: None)
    if args.target not in mm.order:
        raise SystemExit("target not found: " + args.target)
    cutoff = mm.order.index(args.target)
    by_tc = strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=lambda *a, **k: None)
    statement = mm.labels[args.target][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    # From this point onward, any attempt to read the historical target proof aborts.
    original_proofs = mm.proofs
    mm.proofs = GuardedProofs(original_proofs, args.target)

    aco = run_colony(
        E, mm, args.target, cutoff, goal, index,
        seed=args.seed,
        batches=args.batches,
        ants_per_batch=args.ants,
        ant_budget=args.ant_budget,
        alpha=args.alpha,
        rho=args.rho,
        partial_q=args.partial_q,
        partial_elite=args.partial_elite,
        max_open=args.max_open,
        learning=True,
    )
    control = run_colony(
        E, mm, args.target, cutoff, goal, index,
        seed=args.seed,
        batches=args.batches,
        ants_per_batch=args.ants,
        ant_budget=args.ant_budget,
        alpha=args.alpha,
        rho=args.rho,
        partial_q=args.partial_q,
        partial_elite=args.partial_elite,
        max_open=args.max_open,
        learning=False,
    )

    result = {
        "experiment": "untrained ACO on prcom",
        "target": args.target,
        "cutoff_index": cutoff,
        "target_proof_used": False,
        "downstream_used": False,
        "trained_prior_used": False,
        "revision_controller_used": False,
        "move_heuristic_beta": 0.0,
        "aco": aco,
        "no_learning_control": control,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    def summary(name, r):
        print(json.dumps({
            "arm": name,
            "verified": r["verified"],
            "batches_consumed": r["batches_consumed"],
            "ants_run": r["ants_run"],
            "total_applications": r["total_applications"],
            "total_transactions": r["total_transactions"],
            "proof_length": r["proof_length"],
            "best_h": r["best_h"],
            "wall_seconds": r["wall_seconds"],
        }, indent=2))

    summary("ACO", aco)
    summary("NO_LEARNING", control)

    # Bounded UNKNOWN is a valid scientific outcome; only verifier inconsistency is fatal.
    if aco["closed_all_goals"] and not aco["verified"]:
        raise SystemExit("ACO closed goals but verifier rejected certificate")
    if control["closed_all_goals"] and not control["verified"]:
        raise SystemExit("control closed goals but verifier rejected certificate")


if __name__ == "__main__":
    main()
