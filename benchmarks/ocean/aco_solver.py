#!/usr/bin/env python3
"""Ant-colony proof search for the repository Ocean implication benchmark.

The solver intentionally does not use the planted route or BFS distance.  It
parses only the public TPTP-like start fact, implication axioms, and goal.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path

START_RE = re.compile(r"^fof\(start,axiom,p\(n(\d+)\)\)\.$")
EDGE_RE = re.compile(r"^fof\((e\d+),axiom,\(p\(n(\d+)\) => p\(n(\d+)\)\)\)\.$")
GOAL_RE = re.compile(r"^fof\(goal,conjecture,p\(n(\d+)\)\)\.$")


def parse_problem(path: Path):
    source = target = None
    edges = []
    adj = defaultdict(list)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = START_RE.match(line)
        if m:
            source = int(m.group(1))
            continue
        m = EDGE_RE.match(line)
        if m:
            lab, u, v = m.group(1), int(m.group(2)), int(m.group(3))
            edges.append((lab, u, v))
            adj[u].append((lab, v))
            continue
        m = GOAL_RE.match(line)
        if m:
            target = int(m.group(1))
    if source is None or target is None or not edges:
        raise ValueError(f"could not parse Ocean problem: {path}")
    return source, target, edges, dict(adj)


def weighted_order(options, pheromone, adj, rng, alpha, beta):
    """Sample a weighted permutation without replacement.

    The only heuristic is local destination branching.  No target-distance or
    reachability oracle is consulted.
    """
    pool = list(options)
    out = []
    while pool:
        weights = []
        for lab, v in pool:
            tau = max(1e-12, pheromone.get(lab, 1.0)) ** alpha
            eta = (1.0 / (1.0 + len(adj.get(v, ())))) ** beta
            weights.append(max(1e-15, tau * eta))
        total = sum(weights)
        r = rng.random() * total
        acc = 0.0
        pick = len(pool) - 1
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                pick = i
                break
        out.append(pool.pop(pick))
    return out


def ant_search(source, target, adj, pheromone, rng, budget, alpha, beta):
    """Bounded stochastic DFS with pheromone-weighted local edge ordering."""
    if source == target:
        return [source], [], 0, 0

    # frame = [node, remaining_choices_or_None]
    stack = [[source, None]]
    path_nodes = [source]
    path_edges = []
    on_path = {source}
    expansions = 0
    transactions = 0

    while stack and expansions < budget:
        node, choices = stack[-1]
        if node == target:
            return list(path_nodes), list(path_edges), expansions, transactions

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
        transactions += 1
        expansions += 1
        if nxt in on_path:
            continue
        path_nodes.append(nxt)
        path_edges.append(lab)
        on_path.add(nxt)
        stack.append([nxt, None])

    return None, None, expansions, transactions


def verify_path(source, target, edges, nodes, labels):
    if not nodes or nodes[0] != source or nodes[-1] != target:
        return False
    if len(labels) != len(nodes) - 1:
        return False
    by_label = {lab: (u, v) for lab, u, v in edges}
    for i, lab in enumerate(labels):
        if lab not in by_label:
            return False
        if by_label[lab] != (nodes[i], nodes[i + 1]):
            return False
    return True


def run_colony(source, target, edges, adj, *, seed, iterations, ants,
               ant_budget, alpha, beta, rho, q, elite, learning):
    rng = random.Random(seed)
    pheromone = {lab: 1.0 for lab, _, _ in edges}
    best = None
    first_success_iteration = None
    total_expansions = 0
    total_transactions = 0
    successes = 0
    iteration_rows = []
    t0 = time.perf_counter()

    for it in range(1, iterations + 1):
        successful = []
        exp_this = tx_this = 0
        for _ in range(ants):
            nodes, labels, exp, tx = ant_search(
                source, target, adj, pheromone, rng, ant_budget, alpha, beta
            )
            exp_this += exp
            tx_this += tx
            total_expansions += exp
            total_transactions += tx
            if nodes is not None:
                successes += 1
                if first_success_iteration is None:
                    first_success_iteration = it
                successful.append((nodes, labels, exp, tx))
                cand = (len(labels), exp, tx, nodes, labels)
                if best is None or cand[:3] < best[:3]:
                    best = cand

        if learning:
            keep = 1.0 - rho
            for lab in pheromone:
                pheromone[lab] = max(1e-12, pheromone[lab] * keep)
            for _, labels, _, _ in successful:
                dep = q / max(1, len(labels))
                for lab in labels:
                    pheromone[lab] += dep
            if best is not None and elite > 0:
                dep = elite * q / max(1, best[0])
                for lab in best[4]:
                    pheromone[lab] += dep

        iteration_rows.append({
            "iteration": it,
            "successful_ants": len(successful),
            "expansions": exp_this,
            "transactions": tx_this,
            "best_length_so_far": None if best is None else best[0],
        })

    wall = time.perf_counter() - t0
    all_vals = list(pheromone.values())
    global_mean = statistics.fmean(all_vals) if all_vals else 0.0
    if best is None:
        best_path_mean = None
        reinforcement_ratio = None
    else:
        best_path_mean = statistics.fmean(pheromone[x] for x in best[4])
        reinforcement_ratio = best_path_mean / global_mean if global_mean else math.inf

    return {
        "solved": best is not None,
        "learning": learning,
        "seed": seed,
        "iterations": iterations,
        "ants_per_iteration": ants,
        "ant_budget": ant_budget,
        "alpha": alpha,
        "beta": beta,
        "rho": rho,
        "q": q,
        "elite": elite,
        "successful_ants_total": successes,
        "first_success_iteration": first_success_iteration,
        "total_expansions": total_expansions,
        "total_transactions": total_transactions,
        "wall_seconds": wall,
        "best_path_length": None if best is None else best[0],
        "best_path_expansions": None if best is None else best[1],
        "best_path_transactions": None if best is None else best[2],
        "best_path_nodes": None if best is None else best[3],
        "best_path_edges": None if best is None else best[4],
        "global_mean_pheromone": global_mean,
        "best_path_mean_pheromone": best_path_mean,
        "best_path_reinforcement_ratio": reinforcement_ratio,
        "iteration_rows": iteration_rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("problem", type=Path)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--iterations", type=int, default=12)
    ap.add_argument("--ants", type=int, default=16)
    ap.add_argument("--ant-budget", type=int, default=2000)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--rho", type=float, default=0.15)
    ap.add_argument("--q", type=float, default=10.0)
    ap.add_argument("--elite", type=float, default=2.0)
    ap.add_argument("--no-learning", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--path-out", type=Path)
    args = ap.parse_args()

    source, target, edges, adj = parse_problem(args.problem)
    result = run_colony(
        source, target, edges, adj,
        seed=args.seed,
        iterations=args.iterations,
        ants=args.ants,
        ant_budget=args.ant_budget,
        alpha=args.alpha,
        beta=args.beta,
        rho=args.rho,
        q=args.q,
        elite=args.elite,
        learning=not args.no_learning,
    )
    result.update({
        "problem": str(args.problem),
        "source": source,
        "target": target,
        "edge_count": len(edges),
        "internal_path_check": False if not result["solved"] else verify_path(
            source, target, edges, result["best_path_nodes"], result["best_path_edges"]
        ),
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.path_out and result["solved"]:
        args.path_out.parent.mkdir(parents=True, exist_ok=True)
        args.path_out.write_text(json.dumps({
            "problem": str(args.problem),
            "source": source,
            "target": target,
            "nodes": result["best_path_nodes"],
            "edges": result["best_path_edges"],
        }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "solved", "learning", "successful_ants_total", "first_success_iteration",
        "total_expansions", "total_transactions", "best_path_length",
        "best_path_reinforcement_ratio", "wall_seconds", "internal_path_check"
    )}, indent=2))
    raise SystemExit(0 if result["solved"] and result["internal_path_check"] else 1)


if __name__ == "__main__":
    main()
