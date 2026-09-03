from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from data_mind_3.ocean.solver import parse_ocean_tptp, shortest_path_bfs
from data_mind_3.ocean.verifier import verify_ocean_certificate


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="DATA MIND 3.1 Ocean F(n) fallback adapter")
    ap.add_argument("problem", type=Path)
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--breadcrumb-depth", type=int, default=1000)
    ap.add_argument("--result", type=Path, default=Path("dm31_ocean_result.json"))
    ap.add_argument("--certificate", type=Path, default=Path("dm31_ocean_certificate.json"))
    ap.add_argument("--historian", type=Path, default=Path("dm31_ocean_historian.jsonl"))
    args = ap.parse_args()

    problem = parse_ocean_tptp(args.problem)
    search = shortest_path_bfs(
        problem,
        timeout_s=args.timeout,
        breadcrumb_depth=args.breadcrumb_depth,
    )

    verification = None
    status = search.status
    reason = search.reason
    if search.path:
        args.certificate.write_text(json.dumps(list(search.path)), encoding="utf-8")
        vr = verify_ocean_certificate(args.problem, search.path)
        verification = vr.to_dict()
        if vr.accepted:
            status = "PROVED"
            reason = "independent_ocean_verifier_accepted"
        else:
            status = "UNKNOWN"
            reason = "candidate_rejected_by_independent_ocean_verifier"

    payload = {
        "experiment": "DATA MIND 3.1 Ocean F(n) calibration fallback",
        "problem_sha256": sha256(args.problem),
        "declared_depth": problem.declared_depth,
        "declared_seed": problem.declared_seed,
        "source": problem.source,
        "target": problem.target,
        "edge_count": len(problem.edges),
        "hidden_route_access": False,
        "search_policy": "plain breadth-first search over serialized implication graph",
        "historical_depths_f_claim": False,
        "status": status,
        "reason": reason,
        "certificate_transitions": search.certificate_transitions,
        "certificate_nodes": len(search.path),
        "visited_nodes": search.visited_nodes,
        "frontier_peak": search.frontier_peak,
        "elapsed_search_s": search.elapsed_s,
        "verification": verification,
    }
    args.result.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with args.historian.open("w", encoding="utf-8") as f:
        for row in search.historian:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        if verification is not None:
            f.write(json.dumps({"actor": "OceanVerifier", "action": "certificate_check", **verification}, sort_keys=True) + "\n")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "PROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
