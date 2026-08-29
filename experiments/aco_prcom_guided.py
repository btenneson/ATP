#!/usr/bin/env python3
"""Guided verifier-gated ACO proof search for Metamath `prcom`.

Revision after the preregistered beta=0 pilot timed out. This version still uses:
- no learned model,
- no historical target-proof replay,
- no theorem downstream of the target,
- no revision/inversion controller,
- no target-distance oracle.

Changes:
- structural h_hat participates in move choice (beta > 0),
- epsilon exploration gives every legal successor positive probability,
- elite partial proof states may seed later ants,
- depth/open-goal caps expand through a frozen stage schedule,
- every batch writes a durable checkpoint,
- one root-start ant per batch preserves the probabilistic-completeness argument.
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
    return (
        1.0
        + len(goals)
        + 0.015 * token_count(E, goals, sub)
        + 0.02 * math.tanh(len(metas) / 8.0)
    )


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
        out.append(
            (
                lab,
                E.Node(
                    newgoals + rest,
                    s2,
                    node.trail + ((slot, hix, step),),
                    node.depth + 1,
                ),
            )
        )
    return out, attempts


def guided_weights(E, succ, pheromone, alpha, beta, epsilon):
    hs = [h_hat(E, n.goals, n.sub) for _, n in succ]
    min_h = min(hs)
    scores = []
    for (lab, _), hh in zip(succ, hs):
        pher = max(1e-12, pheromone[lab]) ** alpha
        heur = math.exp(-beta * max(0.0, hh - min_h))
        scores.append(max(1e-300, pher * heur))
    total = sum(scores)
    k = len(scores)
    # Convex mixture with uniform exploration. Every legal successor receives
    # probability at least epsilon / k.
    probs = [(1.0 - epsilon) * (s / total) + epsilon / k for s in scores]
    return probs, hs


def run_ant(
    E,
    start,
    index,
    pheromone,
    rng,
    ant_budget,
    alpha,
    beta,
    epsilon,
    max_open,
    deadline,
):
    node = start
    applications = 0
    transactions = 0
    labels = []
    initial_h = h_hat(E, node.goals, node.sub)
    best_h = initial_h
    best_prefix = []
    best_node = node
    max_branching = 0

    while applications < ant_budget:
        if deadline is not None and time.monotonic() >= deadline:
            return {
                "solved": False,
                "timed_out": True,
                "node": node,
                "best_node": best_node,
                "applications": applications,
                "transactions": transactions,
                "labels": labels,
                "initial_h": initial_h,
                "best_h": best_h,
                "best_prefix": best_prefix,
                "max_branching": max_branching,
            }
        if not node.goals:
            return {
                "solved": True,
                "timed_out": False,
                "node": node,
                "best_node": node,
                "applications": applications,
                "transactions": transactions,
                "labels": labels,
                "initial_h": initial_h,
                "best_h": 0.0,
                "best_prefix": list(labels),
                "max_branching": max_branching,
            }
        if len(node.goals) > max_open:
            break

        succ, attempts = legal_successors(E, index, node)
        transactions += attempts
        if not succ:
            break
        max_branching = max(max_branching, len(succ))

        probs, _ = guided_weights(
            E, succ, pheromone, alpha, beta, epsilon
        )
        lab, node = weighted_pick(succ, probs, rng)
        labels.append(lab)
        applications += 1
        hh = h_hat(E, node.goals, node.sub)
        if hh < best_h - 1e-12:
            best_h = hh
            best_prefix = list(labels)
            best_node = node

    return {
        "solved": False,
        "timed_out": False,
        "node": node,
        "best_node": best_node,
        "applications": applications,
        "transactions": transactions,
        "labels": labels,
        "initial_h": initial_h,
        "best_h": best_h,
        "best_prefix": best_prefix,
        "max_branching": max_branching,
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


def parse_stages(text):
    stages = []
    for raw in text.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if ":" not in raw:
            raise ValueError("stage must be ant_budget:max_open")
        b, w = raw.split(":", 1)
        b, w = int(b), int(w)
        if b <= 0 or w <= 0:
            raise ValueError("stage values must be positive")
        stages.append((b, w))
    if not stages:
        raise ValueError("at least one stage required")
    return stages


def write_checkpoint(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
        fh.flush()


def arm_summary(
    *,
    arm,
    solved,
    verified,
    proof,
    seed,
    alpha,
    beta,
    epsilon,
    rho,
    stages,
    batches_limit,
    ants_per_batch,
    partial_q,
    partial_elite,
    elite_pool_size,
    batches_consumed,
    ants_run,
    root_ants_run,
    total_applications,
    total_transactions,
    global_best_h,
    max_branching_observed,
    wall_seconds,
    stopped_by_deadline,
):
    return {
        "arm": arm,
        "solved": bool(solved and verified),
        "closed_all_goals": bool(solved),
        "verified": bool(verified),
        "proof": proof if verified else None,
        "proof_length": None if proof is None else len(proof),
        "seed": seed,
        "learning": arm == "aco",
        "alpha": alpha,
        "beta": beta,
        "epsilon": epsilon,
        "rho": rho,
        "stages": [{"ant_budget": b, "max_open": w} for b, w in stages],
        "batches_limit": batches_limit,
        "ants_per_batch": ants_per_batch,
        "partial_q": partial_q,
        "partial_elite": partial_elite,
        "elite_pool_size": elite_pool_size,
        "batches_consumed": batches_consumed,
        "ants_run": ants_run,
        "root_ants_run": root_ants_run,
        "total_applications": total_applications,
        "total_transactions": total_transactions,
        "best_h": global_best_h,
        "max_branching_observed": max_branching_observed,
        "wall_seconds": wall_seconds,
        "stopped_by_deadline": stopped_by_deadline,
    }


def run_colony(
    E,
    mm,
    target_label,
    cutoff,
    goal,
    index,
    *,
    arm,
    seed,
    batches,
    ants_per_batch,
    stages,
    alpha,
    beta,
    epsilon,
    rho,
    partial_q,
    partial_elite,
    elite_pool_size,
    checkpoint,
    wall_seconds,
):
    learning = arm == "aco"
    rng = random.Random(seed)
    root = E.Node([(goal, None, 0)], {}, (), 0)
    pheromone = defaultdict(lambda: 1.0)
    elite_nodes = []
    total_applications = 0
    total_transactions = 0
    ants_run = 0
    root_ants_run = 0
    global_best_h = h_hat(E, root.goals, root.sub)
    max_branching_observed = 0
    t0 = time.monotonic()
    deadline = None if wall_seconds <= 0 else t0 + wall_seconds
    batches_consumed = 0

    # Spread batches approximately evenly across stages, with later stages
    # receiving any remainder.
    nstages = len(stages)
    for batch in range(1, batches + 1):
        if deadline is not None and time.monotonic() >= deadline:
            break
        stage_ix = min(nstages - 1, ((batch - 1) * nstages) // batches)
        ant_budget, max_open = stages[stage_ix]
        rows = []

        for ant_index in range(1, ants_per_batch + 1):
            if deadline is not None and time.monotonic() >= deadline:
                break

            # One mandatory root-start ant per batch is part of the completeness
            # argument. Other ants may continue elite partial states.
            if ant_index == 1 or not elite_nodes:
                start = E.Node([(goal, None, 0)], {}, (), 0)
                root_start = True
                root_ants_run += 1
            else:
                # Elite-state retention is a search optimization only.
                start = rng.choice(elite_nodes)
                root_start = False

            r = run_ant(
                E,
                start,
                index,
                pheromone,
                rng,
                ant_budget,
                alpha,
                beta if learning else 0.0,
                epsilon,
                max_open,
                deadline,
            )
            r["root_start"] = root_start
            ants_run += 1
            total_applications += r["applications"]
            total_transactions += r["transactions"]
            max_branching_observed = max(
                max_branching_observed, r["max_branching"]
            )
            global_best_h = min(global_best_h, r["best_h"])

            if r["solved"]:
                verified, proof = verify_candidate(
                    E, mm, target_label, cutoff, r["node"]
                )
                wall = time.monotonic() - t0
                result = arm_summary(
                    arm=arm,
                    solved=True,
                    verified=verified,
                    proof=proof,
                    seed=seed,
                    alpha=alpha,
                    beta=beta if learning else 0.0,
                    epsilon=epsilon,
                    rho=rho,
                    stages=stages,
                    batches_limit=batches,
                    ants_per_batch=ants_per_batch,
                    partial_q=partial_q,
                    partial_elite=partial_elite,
                    elite_pool_size=elite_pool_size,
                    batches_consumed=batch,
                    ants_run=ants_run,
                    root_ants_run=root_ants_run,
                    total_applications=total_applications,
                    total_transactions=total_transactions,
                    global_best_h=0.0,
                    max_branching_observed=max_branching_observed,
                    wall_seconds=wall,
                    stopped_by_deadline=False,
                )
                write_checkpoint(
                    checkpoint,
                    {
                        "event": "settlement",
                        "batch": batch,
                        "stage": stage_ix + 1,
                        "verified": verified,
                        "proof_length": result["proof_length"],
                        "wall_seconds": wall,
                    },
                )
                return result

            rows.append(r)
            if r["timed_out"]:
                break

        if not rows:
            break
        batches_consumed = batch

        reinforced = []
        if learning:
            keep = 1.0 - rho
            for lab in list(pheromone.keys()):
                pheromone[lab] = max(1e-12, pheromone[lab] * keep)

            ranked = sorted(
                rows, key=lambda x: (x["best_h"], x["applications"])
            )
            for r in ranked[:partial_elite]:
                improvement = max(0.0, r["initial_h"] - r["best_h"])
                prefix = r["best_prefix"]
                if improvement <= 0.0 or not prefix:
                    continue
                dep = partial_q * improvement / len(prefix)
                for lab in prefix:
                    pheromone[lab] += dep
                reinforced.append(
                    {
                        "best_h": r["best_h"],
                        "improvement": improvement,
                        "prefix_length": len(prefix),
                    }
                )

            # Retain the best actual partial states, not merely their labels.
            elite_nodes = [
                r["best_node"]
                for r in ranked[:elite_pool_size]
                if r["best_h"] < r["initial_h"] - 1e-12
            ]
        else:
            elite_nodes = []

        elapsed = time.monotonic() - t0
        checkpoint_row = {
            "event": "batch",
            "arm": arm,
            "batch": batch,
            "stage": stage_ix + 1,
            "ant_budget": ant_budget,
            "max_open": max_open,
            "ants_run": ants_run,
            "root_ants_run": root_ants_run,
            "batch_best_h": min(r["best_h"] for r in rows),
            "global_best_h": global_best_h,
            "total_applications": total_applications,
            "total_transactions": total_transactions,
            "max_branching_observed": max_branching_observed,
            "elite_states_retained": len(elite_nodes),
            "reinforced": reinforced,
            "elapsed_seconds": elapsed,
        }
        write_checkpoint(checkpoint, checkpoint_row)
        print(json.dumps(checkpoint_row, sort_keys=True), flush=True)

        if any(r["timed_out"] for r in rows):
            break

    wall = time.monotonic() - t0
    stopped_by_deadline = deadline is not None and time.monotonic() >= deadline
    return arm_summary(
        arm=arm,
        solved=False,
        verified=False,
        proof=None,
        seed=seed,
        alpha=alpha,
        beta=beta if learning else 0.0,
        epsilon=epsilon,
        rho=rho,
        stages=stages,
        batches_limit=batches,
        ants_per_batch=ants_per_batch,
        partial_q=partial_q,
        partial_elite=partial_elite,
        elite_pool_size=elite_pool_size,
        batches_consumed=batches_consumed,
        ants_run=ants_run,
        root_ants_run=root_ants_run,
        total_applications=total_applications,
        total_transactions=total_transactions,
        global_best_h=global_best_h,
        max_branching_observed=max_branching_observed,
        wall_seconds=wall,
        stopped_by_deadline=stopped_by_deadline,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment", type=Path)
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--target", default="prcom")
    ap.add_argument("--arm", choices=("aco", "control"), required=True)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--batches", type=int, default=120)
    ap.add_argument("--ants", type=int, default=8)
    ap.add_argument(
        "--stages",
        default="64:16,128:32,256:64,512:128",
        help="comma-separated ant_budget:max_open stages",
    )
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=1.25)
    ap.add_argument("--epsilon", type=float, default=0.10)
    ap.add_argument("--rho", type=float, default=0.15)
    ap.add_argument("--partial-q", type=float, default=5.0)
    ap.add_argument("--partial-elite", type=int, default=4)
    ap.add_argument("--elite-pool-size", type=int, default=4)
    ap.add_argument("--wall-seconds", type=float, default=2700.0)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not (0.0 < args.epsilon <= 1.0):
        raise SystemExit("epsilon must satisfy 0 < epsilon <= 1")
    if args.ants < 1:
        raise SystemExit("ants must be positive")
    stages = parse_stages(args.stages)

    E = load_engine(args.engine.resolve())
    mm = E.load(str(args.environment.resolve()), say=lambda *a, **k: None)
    if args.target not in mm.order:
        raise SystemExit("target not found: " + args.target)
    cutoff = mm.order.index(args.target)
    by_tc = strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=lambda *a, **k: None)
    statement = mm.labels[args.target][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    # From this point onward, historical target-proof access is fatal.
    mm.proofs = GuardedProofs(mm.proofs, args.target)

    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    args.checkpoint.write_text("", encoding="utf-8")

    result = run_colony(
        E,
        mm,
        args.target,
        cutoff,
        goal,
        index,
        arm=args.arm,
        seed=args.seed,
        batches=args.batches,
        ants_per_batch=args.ants,
        stages=stages,
        alpha=args.alpha,
        beta=args.beta,
        epsilon=args.epsilon,
        rho=args.rho,
        partial_q=args.partial_q,
        partial_elite=args.partial_elite,
        elite_pool_size=args.elite_pool_size,
        checkpoint=args.checkpoint,
        wall_seconds=args.wall_seconds,
    )

    payload = {
        "experiment": "guided verifier-gated ACO on prcom",
        "revision": 2,
        "target": args.target,
        "cutoff_index": cutoff,
        "target_proof_used": False,
        "downstream_used": False,
        "trained_prior_used": False,
        "revision_controller_used": False,
        "target_distance_oracle_used": False,
        "arm_result": result,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)

    # Bounded UNKNOWN is valid. Closing all goals with verifier rejection is not.
    if result["closed_all_goals"] and not result["verified"]:
        raise SystemExit("closed goals but verifier rejected certificate")


if __name__ == "__main__":
    main()
