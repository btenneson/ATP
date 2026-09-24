#!/usr/bin/env python3
"""PRCOM five-ATP experiment: BFTS / Hilbert-BFTS / learned-HBF / depth-charge.

Designed to live in `predator 8/recovered8_002/` of btenneson/ATP and reuse the
frozen Predator 8.002 runtime.  The target proof is guarded and every claimed
solution is checked both in-process and by predator8_external_cv.py.

The controlled BFTS/HBF comparison uses the *same* declared candidate subspace.
With --candidate-cap 8, the frozen target-clean policy is used only to define
which eight head-compatible assertions belong to that finite subspace at each
open goal.  BFTS then orders those candidates by label; HBF changes only the
within-breadth-layer state order.  Thus proof depth remains a hard primary key.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import heapq
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

import predator8_016_prcom_exactify as P
from predator8_ml_ranker import RuntimePolicy

B = P.B
ROOT = Path(__file__).resolve().parent
VERSION = "hhdf-prcom-search-001"


def _clip(v: int, n: int) -> int:
    return max(0, min(n - 1, int(v)))


def hilbert_xy_to_d(n: int, x: int, y: int) -> int:
    """Standard 2-D Hilbert index on an n x n grid, n a power of two."""
    d = 0
    s = n // 2
    while s:
        rx = 1 if (x & s) else 0
        ry = 1 if (y & s) else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x = n - 1 - x
                y = n - 1 - y
            x, y = y, x
        s //= 2
    return d


def structural_xy(E, node, grid: int) -> tuple[int, int]:
    """Small structural chart for proof states; no target-proof information."""
    token_total = 0
    distinct_total = 0
    punctuation = 0
    for g, _slot, _hix in node.goals:
        gg = E.apply_sub(g, node.sub)
        toks = list(gg.tokens())
        token_total += len(toks)
        distinct_total += len(set(toks))
        punctuation += sum(t in {"(", ")", "{", "}", "=", "e.", "u."} for t in toks)
    # Coordinates are intentionally structural and deterministic.  They are
    # search/navigation coordinates, never proof-validity conditions.
    x = _clip(token_total + 3 * punctuation, grid)
    y = _clip(16 * len(node.goals) + 4 * node.depth + distinct_total, grid)
    return x, y


def node_hilbert_key(E, node, grid: int) -> int:
    x, y = structural_xy(E, node, grid)
    return hilbert_xy_to_d(grid, x, y)


def canonical_proof_bytes(proof) -> bytes:
    return (" ".join(proof)).encode("utf-8")


def write_progress(path, expansions: int, verified: bool = False, proof_steps=None):
    if not path:
        return
    p = Path(path)
    payload = {
        "expansions": int(expansions),
        "verified": bool(verified),
        "proof_steps": proof_steps,
    }
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def ranked_items(policy, gt, closers, openers):
    """Rank every head-compatible candidate; cap only after legal unification.

    The previous experiment capped the ranked head-compatible list before
    actual unification.  On prcom that can select eight candidates that all
    fail unification and falsely make the root look childless.
    """
    items = list(closers) + list(openers)
    if not items:
        return []
    scores = [0.0] * len(items) if policy is None else list(policy.rank(gt, items))
    scored = [(float(s), item) for s, item in zip(scores, items)]
    scored.sort(key=lambda p: (-p[0], p[1][0]))
    return scored


def children(E, index, policy, node, max_open: int, candidate_cap: int):
    """Enumerate legal children for every open-goal choice."""
    out = []
    for gi in range(len(node.goals)):
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = E.apply_sub(gt, node.sub)
        closers, openers = index.candidates(gt)
        accepted = 0
        for model_score, (lab, ct, data) in ranked_items(
                policy, gt, closers, openers):
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
                    ok = False
                    break
                newgoals.append((E.rename_apart(ht, m), step, hj))
            if not ok:
                continue
            successor_goals = newgoals + rest
            if len(successor_goals) > max_open:
                continue
            child = E.Node(
                successor_goals,
                s2,
                node.trail + ((slot, hix, step),),
                node.depth + 1,
            )
            out.append((lab, model_score, child))
            accepted += 1
            if candidate_cap > 0 and accepted >= candidate_cap:
                break
    return out


def emit_and_verify(E, mm, label, node, fvar, fallback, environment: Path,
                    out_path: Path):
    if node.goals:
        return False, None, "nonterminal"
    result = B.reconstruct(node)
    root, sub = result
    if root is None:
        return False, None, "reconstruction failed"
    proof = root.emit(sub, fvar, fallback)

    # In-process Metamath verification.
    check = E.MM()
    check.labels = dict(mm.labels)
    check.order = list(mm.order)
    check.proofs = dict(mm.proofs)
    check.constants, check.variables = mm.constants, mm.variables
    check.scope_dvs = dict(mm.scope_dvs)
    data = mm.labels[label][1]
    check.labels["__hhdf_check__"] = ("$p", data)
    check.proofs["__hhdf_check__"] = proof
    check.scope_dvs["__hhdf_check__"] = mm.scope_dvs.get(label, data[0])
    verdict = check.verify("__hhdf_check__")
    if verdict != "ok":
        return False, proof, "in-process verdict=%s" % verdict

    statement = mm.labels[label][1][3]
    out_path.write_text(
        "$( %s candidate for %s $)\n" % (VERSION, label)
        + "$[ %s $]\n" % environment.name
        + "chk $p %s $= %s $.\n" % (" ".join(statement), " ".join(proof)),
        encoding="utf-8",
    )
    ext = subprocess.run(
        [sys.executable, str(ROOT / "predator8_external_cv.py"),
         str(environment), "--target", label, "--certificate", str(out_path)],
        cwd=str(ROOT), text=True, capture_output=True, check=False,
    )
    detail = (ext.stdout + ext.stderr).strip()
    return ext.returncode == 0, proof, detail


def state_fingerprint(E, node):
    goals = []
    for g, _slot, _hix in node.goals:
        gg = E.apply_sub(g, node.sub)
        goals.append(" ".join(gg.tokens()))
    return (node.depth, tuple(sorted(goals)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", required=True,
                    help="target-clean pre-prcom policy; defines cap and learned mode")
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--mode", choices=["bfs", "hilbert", "learned-hilbert", "depth-charge"],
                    required=True)
    ap.add_argument("--candidate-cap", type=int, default=8)
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--max-open", type=int, default=8)
    ap.add_argument("--max-expanded", type=int, default=50000)
    ap.add_argument("--frontier-limit", type=int, default=500000)
    ap.add_argument("--hilbert-grid", type=int, default=256)
    ap.add_argument("--seed", type=int, default=260923)
    ap.add_argument("--restarts", type=int, default=64)
    ap.add_argument("--progress-every", type=int, default=0,
                    help="emit machine-readable expansion counter every N expansions")
    ap.add_argument("--progress-file", default=None,
                    help="atomically updated JSON expansion counter")
    ap.add_argument("--out", default=None)
    ap.add_argument("--summary", default=None)
    args = ap.parse_args()

    if args.label != "prcom":
        ap.error("this first federation experiment is intentionally frozen to prcom")
    if args.hilbert_grid <= 0 or args.hilbert_grid & (args.hilbert_grid - 1):
        ap.error("--hilbert-grid must be a positive power of two")
    if args.out is None:
        args.out = "prcom_%s.mm" % args.mode.replace("-", "_")
    if args.summary is None:
        args.summary = "prcom_%s.summary.json" % args.mode.replace("-", "_")

    environment = Path(args.environment).resolve()
    engine_path = Path(args.engine).resolve()
    model_path = Path(args.model).resolve()
    out_path = Path(args.out).resolve()
    summary_path = Path(args.summary).resolve()

    E = B.load_engine(engine_path)
    mm = E.load(str(environment), say=print)
    cutoff = mm.order.index(args.label)
    by_tc = B.strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=print)
    statement = mm.labels[args.label][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    policy = RuntimePolicy.load(model_path, E, by_tc)
    md = policy.artifact["metadata"]
    if md.get("environment_sha256") != B.sha256(environment):
        raise SystemExit("model/environment hash mismatch")
    if md.get("cutoff_before") != args.label or md.get("target_proof_used") is not False \
            or md.get("downstream_used") is not False:
        raise SystemExit("target-clean model attestation failed")

    fvar, fallback = B.formal_variables(E, mm, cutoff)
    original_proofs = mm.proofs
    mm.proofs = B.GuardedProofs(original_proofs, args.label)
    rng = random.Random(args.seed)
    started = time.perf_counter()
    expanded = generated = 0
    best_open = 10**9
    solution = None
    solution_detail = ""
    solution_proof = None
    solution_hkey = None

    try:
        start = E.Node([(goal, None, 0)], {}, (), 0)
        tie = 0
        seen = set()

        if args.mode == "depth-charge":
            # Randomized bounded DFS with restarts.  Candidate scores define only
            # the legal cap; within the cap the walk is stochastic.
            for _r in range(args.restarts):
                if expanded >= args.max_expanded or solution is not None:
                    break
                stack = [start]
                local_seen = set()
                while stack and expanded < args.max_expanded:
                    node = stack.pop()
                    expanded += 1
                    write_progress(args.progress_file, expanded)
                    if args.progress_every and expanded % args.progress_every == 0:
                        print(f"@@EXPANSION {expanded}", flush=True)
                    best_open = min(best_open, len(node.goals))
                    if not node.goals:
                        ok, proof, detail = emit_and_verify(
                            E, mm, args.label, node, fvar, fallback, environment, out_path)
                        if ok:
                            solution, solution_proof, solution_detail = node, proof, detail
                            break
                        continue
                    if node.depth >= args.max_depth:
                        continue
                    fp = state_fingerprint(E, node)
                    if fp in local_seen:
                        continue
                    local_seen.add(fp)
                    ch = children(E, index, policy, node, args.max_open, args.candidate_cap)
                    generated += len(ch)
                    rng.shuffle(ch)
                    # random depth charge: push a small stochastic beam
                    width = min(len(ch), 1 + int(math.sqrt(max(1, len(ch)))))
                    for _lab, _score, child in ch[:width]:
                        stack.append(child)
        else:
            frontier = []
            # All three modes are breadth-first: depth is always the first key.
            heapq.heappush(frontier, (0, 0, 0.0, tie, start))
            while frontier and expanded < args.max_expanded:
                if args.frontier_limit and len(frontier) > args.frontier_limit:
                    solution_detail = "frontier limit reached"
                    break
                _depth, _h, _learn, _tie, node = heapq.heappop(frontier)
                expanded += 1
                write_progress(args.progress_file, expanded)
                if args.progress_every and expanded % args.progress_every == 0:
                    print(f"@@EXPANSION {expanded}", flush=True)
                best_open = min(best_open, len(node.goals))

                if not node.goals:
                    ok, proof, detail = emit_and_verify(
                        E, mm, args.label, node, fvar, fallback, environment, out_path)
                    if ok:
                        solution, solution_proof, solution_detail = node, proof, detail
                        solution_hkey = node_hilbert_key(E, node, args.hilbert_grid)
                        break
                    continue
                if node.depth >= args.max_depth:
                    continue

                fp = state_fingerprint(E, node)
                if fp in seen:
                    continue
                seen.add(fp)
                ch = children(E, index, policy, node, args.max_open, args.candidate_cap)
                generated += len(ch)
                if args.mode == "bfs":
                    # Same candidate set, but remove learned ordering after cap selection.
                    ch.sort(key=lambda q: q[0])
                for lab, score, child in ch:
                    tie += 1
                    if args.mode == "bfs":
                        hkey = 0
                        learned = 0.0
                    elif args.mode == "hilbert":
                        hkey = node_hilbert_key(E, child, args.hilbert_grid)
                        learned = 0.0
                    else:  # learned-hilbert
                        hkey = node_hilbert_key(E, child, args.hilbert_grid)
                        learned = -float(score)  # higher score is earlier after same Hilbert cell
                    heapq.heappush(frontier,
                                   (child.depth, hkey, learned, tie, child))
    finally:
        mm.proofs = original_proofs

    elapsed = time.perf_counter() - started
    solved = solution is not None
    proof_sha = None
    proof_steps = None
    if solution_proof is not None:
        raw = canonical_proof_bytes(solution_proof)
        proof_sha = hashlib.sha256(raw).hexdigest()
        proof_steps = len(solution_proof)

    summary = {
        "version": VERSION,
        "target": args.label,
        "mode": args.mode,
        "solved": solved,
        "externally_verified": solved,
        "expansions": expanded,
        "generated_children": generated,
        "best_open_goals": best_open if best_open < 10**9 else None,
        "solution_search_depth": solution.depth if solution is not None else None,
        "solution_proof_steps": proof_steps,
        "solution_proof_sha256": proof_sha,
        "solution_hilbert_key": solution_hkey,
        "candidate_cap": args.candidate_cap,
        "max_depth": args.max_depth,
        "max_open": args.max_open,
        "hilbert_grid": args.hilbert_grid,
        "seed": args.seed,
        "elapsed_seconds": elapsed,
        "detail": solution_detail,
        "target_proof_guarded": True,
        "downstream_assertions_visible": False,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    if solved:
        write_progress(args.progress_file, expanded, True, proof_steps)
        print(f"@@VERIFIED expansions={expanded} proof_steps={proof_steps}", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
