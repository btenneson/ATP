#!/usr/bin/env python3
"""PRCOM Experiment 001: Professor/A*-style priority with protected Hilbert fairness.

This runner deliberately reuses the exact legal-successor generator, target-clean
candidate subspace, Hilbert chart, proof reconstruction, and dual verification
from hhdf_prcom_bfts.py.  The only experimental addition is a second priority
queue based on the previously frozen Professor proxy.

Professor proxy (matching DATA MIND 3.1 Experiment 007 semantics):
    q_raw = 1 / (1 + 0.9 * open_goals + 0.012 * residual_token_mass)
    H_hat = max(0, 1/q_raw - 1)
    h_P   = H_hat(root)
    repair_proximity = 2 ** (-(H_hat/h_P))
    PC_prof = 0.5*q_raw + 0.5*repair_proximity

The Professor queue uses an A*-style key
    f_hat = depth + H_hat/h_P
but H_hat is NOT asserted to be an admissible heuristic.  Completeness protection
comes from a separate fair Hilbert/BFTS queue receiving a fixed share of expansion
opportunities.  MAPQUEST-style trust separation is preserved: priority never
certifies mathematics; emitted proofs must pass the same in-process and external
Metamath checks as the control.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path
import time

import hhdf_prcom_bfts as H

B = H.B


def professor_metrics(E, node, h_p: float) -> dict[str, float | int]:
    if not node.goals:
        return {
            "open_goals": 0,
            "residual_token_mass": 0,
            "q_raw": 1.0,
            "H_hat": 0.0,
            "h_norm": 0.0,
            "repair_proximity": 1.0,
            "PC_prof": 1.0,
            "f_hat": float(node.depth),
        }
    mass = 0
    for g, _slot, _hix in node.goals:
        gg = E.apply_sub(g, node.sub)
        mass += len(list(gg.tokens()))
    q_raw = 1.0 / (1.0 + 0.9 * len(node.goals) + 0.012 * mass)
    h_hat = max(0.0, 1.0 / q_raw - 1.0)
    h_norm = h_hat / h_p if h_p > 0 else h_hat
    repair = 2.0 ** (-h_norm)
    pc = 0.5 * q_raw + 0.5 * repair
    return {
        "open_goals": len(node.goals),
        "residual_token_mass": mass,
        "q_raw": q_raw,
        "H_hat": h_hat,
        "h_norm": h_norm,
        "repair_proximity": repair,
        "PC_prof": pc,
        "f_hat": float(node.depth) + h_norm,
    }


def pop_live(heap, expanded_serials: set[int]):
    while heap:
        item = heapq.heappop(heap)
        serial = item[-2]
        node = item[-1]
        if serial not in expanded_serials:
            return serial, node
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", default="prcom_quick_policy.joblib")
    ap.add_argument("--label", default="prcom")
    ap.add_argument("--candidate-cap", type=int, default=8)
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--max-open", type=int, default=8)
    ap.add_argument("--max-expanded", type=int, default=10000)
    ap.add_argument("--frontier-limit", type=int, default=500000)
    ap.add_argument("--hilbert-grid", type=int, default=256)
    ap.add_argument("--seed", type=int, default=260923)
    ap.add_argument("--professor-share", type=float, default=0.5)
    ap.add_argument("--out", default="prcom_professor_hybrid.mm")
    ap.add_argument("--summary", default="prcom_professor_hybrid.summary.json")
    ap.add_argument("--trace", default="prcom_professor_hybrid.trace.jsonl")
    args = ap.parse_args()

    if args.label != "prcom":
        ap.error("PRCOM Experiment 001 is frozen to prcom")
    if not (0.0 < args.professor_share < 1.0):
        ap.error("--professor-share must lie strictly between 0 and 1")
    if args.hilbert_grid <= 0 or args.hilbert_grid & (args.hilbert_grid - 1):
        ap.error("--hilbert-grid must be a positive power of two")

    environment = Path(args.environment).resolve()
    engine_path = Path(args.engine).resolve()
    model_path = Path(args.model).resolve()
    out_path = Path(args.out).resolve()
    summary_path = Path(args.summary).resolve()
    trace_path = Path(args.trace).resolve()

    E = B.load_engine(engine_path)
    mm = E.load(str(environment), say=print)
    cutoff = mm.order.index(args.label)
    by_tc = B.strict_prefix_grammar(E, mm, cutoff)
    index = E.Index(mm, by_tc, upto=cutoff, say=print)
    statement = mm.labels[args.label][1][3]
    goal = E.G.parse(statement[1:], "wff", by_tc)

    policy = H.RuntimePolicy.load(model_path, E, by_tc)
    md = policy.artifact["metadata"]
    if md.get("environment_sha256") != B.sha256(environment):
        raise SystemExit("model/environment hash mismatch")
    if md.get("cutoff_before") != args.label or md.get("target_proof_used") is not False \
            or md.get("downstream_used") is not False:
        raise SystemExit("target-clean model attestation failed")

    fvar, fallback = B.formal_variables(E, mm, cutoff)
    original_proofs = mm.proofs
    mm.proofs = B.GuardedProofs(original_proofs, args.label)

    start_node = E.Node([(goal, None, 0)], {}, (), 0)
    # Freeze h_P from the first positive burden proxy, here the root.
    root_mass = len(list(goal.tokens()))
    root_q = 1.0 / (1.0 + 0.9 + 0.012 * root_mass)
    h_p = max(0.0, 1.0 / root_q - 1.0)
    if h_p <= 0:
        h_p = 1.0

    # Every generated state is inserted into both queues.  Expanding it from one
    # invalidates the duplicate queue entry by serial number, so dual queue
    # bookkeeping itself never double-counts an expansion.
    hilbert_q = []
    professor_q = []
    serial_next = 0

    def push(node):
        nonlocal serial_next
        serial = serial_next
        serial_next += 1
        hkey = H.node_hilbert_key(E, node, args.hilbert_grid)
        pm = professor_metrics(E, node, h_p)
        heapq.heappush(hilbert_q, (node.depth, hkey, serial, node))
        heapq.heappush(
            professor_q,
            (pm["f_hat"], -pm["PC_prof"], node.depth, hkey, serial, node),
        )
        return serial

    push(start_node)
    expanded_serials: set[int] = set()
    seen = set()
    expanded = 0
    generated = 0
    best_open = 10**9
    source_expansions = {"hilbert": 0, "professor": 0}
    solution = None
    solution_proof = None
    solution_detail = ""
    solution_hkey = None
    started = time.perf_counter()

    # For 0.5 this is exact alternation.  The accumulator generalizes without
    # changing the preregistered default.
    professor_credit = 0.0

    trace_f = trace_path.open("w", encoding="utf-8")
    try:
        while expanded < args.max_expanded:
            live_h = any(item[-2] not in expanded_serials for item in hilbert_q)
            live_p = any(item[-2] not in expanded_serials for item in professor_q)
            if not live_h and not live_p:
                break
            if args.frontier_limit and (len(hilbert_q) + len(professor_q)) > 2 * args.frontier_limit:
                solution_detail = "frontier limit reached"
                break

            professor_credit += args.professor_share
            use_professor = professor_credit >= 1.0
            if use_professor:
                professor_credit -= 1.0

            if use_professor:
                serial, node = pop_live(professor_q, expanded_serials)
                source = "professor"
                if node is None:
                    serial, node = pop_live(hilbert_q, expanded_serials)
                    source = "hilbert"
            else:
                serial, node = pop_live(hilbert_q, expanded_serials)
                source = "hilbert"
                if node is None:
                    serial, node = pop_live(professor_q, expanded_serials)
                    source = "professor"
            if node is None:
                break

            expanded_serials.add(serial)
            expanded += 1
            source_expansions[source] += 1
            best_open = min(best_open, len(node.goals))

            pm = professor_metrics(E, node, h_p)
            hkey = H.node_hilbert_key(E, node, args.hilbert_grid)
            trace_f.write(json.dumps({
                "expansion": expanded,
                "source": source,
                "serial": serial,
                "depth": node.depth,
                "hilbert_key": hkey,
                **pm,
            }, sort_keys=True) + "\n")

            if not node.goals:
                ok, proof, detail = H.emit_and_verify(
                    E, mm, args.label, node, fvar, fallback, environment, out_path
                )
                if ok:
                    solution = node
                    solution_proof = proof
                    solution_detail = detail
                    solution_hkey = hkey
                    break
                continue
            if node.depth >= args.max_depth:
                continue

            fp = H.state_fingerprint(E, node)
            if fp in seen:
                continue
            seen.add(fp)

            ch = H.children(
                E, index, policy, node, args.max_open, args.candidate_cap
            )
            generated += len(ch)
            # Legal candidate set/generator is identical to the control.  State
            # priority is the sole experimental change, so child iteration order
            # does not itself encode the Professor.
            ch.sort(key=lambda q: q[0])
            for _lab, _score, child in ch:
                push(child)
    finally:
        trace_f.close()
        mm.proofs = original_proofs

    elapsed = time.perf_counter() - started
    solved = solution is not None
    proof_sha = None
    proof_steps = None
    if solution_proof is not None:
        raw = H.canonical_proof_bytes(solution_proof)
        proof_sha = hashlib.sha256(raw).hexdigest()
        proof_steps = len(solution_proof)

    summary = {
        "experiment": "PRCOM Experiment 001 Professor hybrid",
        "target": args.label,
        "mode": "professor-a-star-style-plus-protected-hilbert",
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
        "professor_share": args.professor_share,
        "source_expansions": source_expansions,
        "professor_formula": {
            "q_raw": "1/(1+0.9*open_goals+0.012*residual_token_mass)",
            "H_hat": "max(0,1/q_raw-1)",
            "h_P": h_p,
            "repair_proximity": "2^(-(H_hat/h_P))",
            "PC_prof": "0.50*q_raw+0.50*repair_proximity",
            "priority": "f_hat=depth+H_hat/h_P",
            "admissibility_claim": False,
        },
        "trust_separation": (
            "Professor affects queue priority only; theoremhood requires the same "
            "in-process and external Metamath verification as the control."
        ),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if solved:
        print(f"@@VERIFIED expansions={expanded} proof_steps={proof_steps}", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
