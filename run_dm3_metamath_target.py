from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig, search_target
from data_mind_3.metamath.verifier import verify_with_brian_metamath


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="DATA MIND 3 generic Metamath target adapter")
    ap.add_argument("database", type=Path)
    ap.add_argument("--label", required=True)
    ap.add_argument("--verifier", type=Path, default=Path("metamath.py"))
    ap.add_argument("--max-expansions", type=int, default=20000)
    ap.add_argument("--candidate-cap", type=int, default=32)
    ap.add_argument("--max-depth", type=int, default=24)
    ap.add_argument("--max-open", type=int, default=24)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--result", type=Path, default=Path("dm3_metamath_result.json"))
    ap.add_argument("--historian", type=Path, default=Path("dm3_metamath_historian.jsonl"))
    args = ap.parse_args()

    db = parse_database(args.database)
    target = db.target(args.label)
    config = SearchConfig(
        max_expansions=args.max_expansions,
        candidate_cap=args.candidate_cap,
        max_depth=args.max_depth,
        max_open_goals=args.max_open,
        timeout_s=args.timeout,
    )

    def verifier_callback(proof_labels: tuple[str, ...]):
        vr = verify_with_brian_metamath(
            args.database, args.label, proof_labels, args.verifier, timeout_s=600.0
        )
        meta = {
            "accepted": vr.accepted,
            "returncode": vr.returncode,
            "verifier": vr.verifier,
            "stdout_tail": vr.stdout[-4000:],
            "stderr_tail": vr.stderr[-4000:],
        }
        return vr.accepted, meta

    result = search_target(db, args.label, config, verifier_callback)
    payload = {
        "experiment": "DATA MIND 3 Metamath generalized adapter",
        "target": args.label,
        "target_statement": " ".join(target.statement),
        "source_sha256": sha256(args.database),
        "expansion_definition": "one nonterminal search state popped and its legal successors generated",
        "status": result.status,
        "expansions_to_first_verifier_accepted_proof": result.expansions if result.status == "PROVED" else None,
        "generated_children": result.generated_children,
        "proof_step_labels": len(result.proof_labels),
        "proof_labels": list(result.proof_labels),
        "elapsed_search_s": result.elapsed_s,
        "reason": result.reason,
        "verification": result.verification,
        "config": config.__dict__,
    }
    args.result.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with args.historian.open("w", encoding="utf-8") as f:
        for row in result.historian:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status == "PROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
