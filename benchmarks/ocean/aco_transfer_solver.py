#!/usr/bin/env python3
"""Stage-2 ACO solver with partial-progress reinforcement before first proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

from aco_solver import parse_problem, verify_path, weighted_order


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ant_search_partial(source, target, adj, pheromone, rng, budget, alpha, beta):
    if source == target:
        return {
            "solved": True,
            "nodes": [source],
            "edges": [],
            "expansions": 0,
            "transactions": 0,
            "best_partial_nodes": [source],
            "best_partial_edges": [],
        }

    stack = [[source, None]]
    path_nodes = [source]
    path_edges = []
    on_path = {source}
    best_nodes = list(path_nodes)
    best_edges = list(path_edges)
    expansions = 0
    transactions = 0

    while stack and expansions < budget:
        node, choices = stack[-1]
        if node == target:
            return {
                "solved": True,
                "nodes": list(path_nodes),
                "edges": list(path_edges),
                "expansions": expansions,
                "transactions": transactions,
                "best_partial_nodes": list(path_nodes),
                "best_partial_edges": list(path_edges),
            }

        if choices is None:
            options = [(lab, v) for lab, v in adj.get(node, ()) if v not in on_path]
            choices = weighted_order(options, pheromone, adj, rng, alpha, beta)
            stack[-1][1] = choices

        if not choices:
            stack.pop()
            old = path_nodes.pop()
            on_path.remove(old)
            if path_edges:
                path_edges.pop()
            continue

        lab, nxt = choices.pop(0)
        expansions += 1
        transactions += 1
        if nxt in on_path:
            continue
        path_nodes.append(nxt)
        path_edges.append(lab)
        on_path.add(nxt)
        stack.append([nxt, None])
        if len(path_edges) > len(best_edges):
            best_nodes = list(path_nodes)
            best_edges = list(path_edges)

    return {
        "solved": False,
        "nodes": None,
        "edges": None,
        "expansions": expansions,
        "transactions": transactions,
        "best_partial_nodes": best_nodes,
        "best_partial_edges": best_edges,
    }


def run_transfer(source, target, edges, adj, *, seed, batches, ants_per_batch,
                 ant_budget, alpha, beta, rho, partial_q, partial_elite):
    rng = random.Random(seed)
    pheromone = {lab: 1.0 for lab, _, _ in edges}
    total_expansions = 0
    total_transactions = 0
    ants_run = 0
    deepest_partial = 0
    history = []
    t0 = time.perf_counter()

    for batch in range(1, batches + 1):
        partials = []
        batch_exp = batch_tx = 0
        batch_deepest = 0
        for ant_index in range(1, ants_per_batch + 1):
            r = ant_search_partial(
                source, target, adj, pheromone, rng, ant_budget, alpha, beta
            )
            ants_run += 1
            total_expansions += r["expansions"]
            total_transactions += r["transactions"]
            batch_exp += r["expansions"]
            batch_tx += r["transactions"]
            d = len(r["best_partial_edges"])
            deepest_partial = max(deepest_partial, d)
            batch_deepest = max(batch_deepest, d)

            if r["solved"]:
                wall = time.perf_counter() - t0
                return {
                    "solved": True,
                    "seed": seed,
                    "batches_limit": batches,
                    "ants_per_batch": ants_per_batch,
                    "ant_budget": ant_budget,
                    "alpha": alpha,
                    "beta": beta,
                    "rho": rho,
                    "partial_q": partial_q,
                    "partial_elite": partial_elite,
                    "batches_consumed": batch,
                    "ants_run": ants_run,
                    "total_expansions": total_expansions,
                    "total_transactions": total_transactions,
                    "deepest_partial_depth": max(deepest_partial, len(r["edges"])),
                    "best_path_length": len(r["edges"]),
                    "best_path_nodes": r["nodes"],
                    "best_path_edges": r["edges"],
                    "wall_seconds": wall,
                    "history": history + [{
                        "batch": batch,
                        "settled_by_ant": ant_index,
                        "batch_expansions_through_settlement": batch_exp,
                        "batch_transactions_through_settlement": batch_tx,
                        "batch_deepest_partial": batch_deepest,
                    }],
                }

            partials.append((d, r["best_partial_nodes"], r["best_partial_edges"]))

        # No complete proof in this batch: now partial progress may alter the
        # next batch.  This is the only pre-settlement reinforcement signal.
        keep = 1.0 - rho
        for lab in pheromone:
            pheromone[lab] = max(1e-12, pheromone[lab] * keep)

        partials.sort(key=lambda x: x[0], reverse=True)
        chosen = [p for p in partials[:partial_elite] if p[0] > 0]
        dmax = max((p[0] for p in chosen), default=0)
        for d, _, labs in chosen:
            strength = partial_q * (d / dmax) if dmax else 0.0
            dep = strength / max(1, len(labs))
            for lab in labs:
                pheromone[lab] += dep

        history.append({
            "batch": batch,
            "settled_by_ant": None,
            "batch_expansions": batch_exp,
            "batch_transactions": batch_tx,
            "batch_deepest_partial": batch_deepest,
            "reinforced_partial_depths": [p[0] for p in chosen],
        })

    return {
        "solved": False,
        "seed": seed,
        "batches_limit": batches,
        "ants_per_batch": ants_per_batch,
        "ant_budget": ant_budget,
        "alpha": alpha,
        "beta": beta,
        "rho": rho,
        "partial_q": partial_q,
        "partial_elite": partial_elite,
        "batches_consumed": batches,
        "ants_run": ants_run,
        "total_expansions": total_expansions,
        "total_transactions": total_transactions,
        "deepest_partial_depth": deepest_partial,
        "best_path_length": None,
        "best_path_nodes": None,
        "best_path_edges": None,
        "wall_seconds": time.perf_counter() - t0,
        "history": history,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("problem", type=Path)
    ap.add_argument("--prior", type=Path)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--batches", type=int, default=40)
    ap.add_argument("--ants", type=int, default=8)
    ap.add_argument("--ant-budget", type=int, default=8000)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=0.0)
    ap.add_argument("--rho", type=float, default=0.15)
    ap.add_argument("--partial-q", type=float, default=5.0)
    ap.add_argument("--partial-elite", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--path-out", type=Path)
    args = ap.parse_args()

    prior_sha = None
    alpha = args.alpha
    rho = args.rho
    if args.prior:
        prior = json.loads(args.prior.read_text(encoding="utf-8"))
        alpha = float(prior["learned"]["alpha"])
        rho = float(prior["learned"]["rho"])
        prior_sha = sha256(args.prior)

    source, target, edges, adj = parse_problem(args.problem)
    r = run_transfer(
        source, target, edges, adj,
        seed=args.seed,
        batches=args.batches,
        ants_per_batch=args.ants,
        ant_budget=args.ant_budget,
        alpha=alpha,
        beta=args.beta,
        rho=rho,
        partial_q=args.partial_q,
        partial_elite=args.partial_elite,
    )
    r.update({
        "problem": str(args.problem),
        "source": source,
        "target": target,
        "edge_count": len(edges),
        "prior_file": None if args.prior is None else str(args.prior),
        "prior_sha256": prior_sha,
        "internal_path_check": False if not r["solved"] else verify_path(
            source, target, edges, r["best_path_nodes"], r["best_path_edges"]
        ),
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
    if args.path_out and r["solved"]:
        args.path_out.parent.mkdir(parents=True, exist_ok=True)
        args.path_out.write_text(json.dumps({
            "problem": str(args.problem),
            "source": source,
            "target": target,
            "nodes": r["best_path_nodes"],
            "edges": r["best_path_edges"],
        }, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: r[k] for k in (
        "solved", "alpha", "rho", "batches_consumed", "ants_run",
        "total_expansions", "total_transactions", "deepest_partial_depth",
        "best_path_length", "wall_seconds", "internal_path_check"
    )}, indent=2))

    if r["solved"] and not r["internal_path_check"]:
        raise SystemExit(2)
    raise SystemExit(0 if r["solved"] else 1)


if __name__ == "__main__":
    main()
