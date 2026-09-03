from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.control.experience import load_experience, save_experience
from data_mind_3.control.reflective import (
    PROFESSOR_SCALARIZATION,
    ReflectiveP1Controller,
)
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
    ap.add_argument("--adaptive-control", action="store_true",
                    help="enable DATA MIND 3.1 error-driven 11D creativity control")
    ap.add_argument("--child-knob-play", action="store_true",
                    help="let the child run reversible fine-tune and rare group-inverse trials over creativity knobs")
    ap.add_argument("--reflective-p1", action="store_true",
                    help="run Professor-facing operationally self-aware P1; implies adaptive control and child play")
    ap.add_argument("--control-interval", type=int, default=16)
    ap.add_argument("--experience-in", type=Path, default=None,
                    help="optional prior DATA MIND 3.1 control JSONL used to warm-start creativity")
    ap.add_argument("--experience-out", type=Path, default=None,
                    help="write DATA MIND 3.1 control updates as portable experience JSONL")
    args = ap.parse_args()

    if args.reflective_p1:
        args.adaptive_control = True
        args.child_knob_play = True
    elif args.child_knob_play:
        args.adaptive_control = True

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

    experience_rows = load_experience(args.experience_in) if args.adaptive_control else []
    controller: AdaptiveCreativityController | None
    if args.reflective_p1:
        controller = ReflectiveP1Controller(
            interval=args.control_interval,
            experience=experience_rows,
            child_play=True,
        )
    elif args.adaptive_control:
        controller = AdaptiveCreativityController(
            interval=args.control_interval,
            experience=experience_rows,
            child_play=args.child_knob_play,
        )
    else:
        controller = None

    result = search_target(db, args.label, config, verifier_callback, controller=controller)
    if controller is not None:
        save_experience(args.experience_out, controller.history)

    child_rows = []
    if controller is not None:
        child_rows = [
            row for row in controller.history
            if isinstance(row, dict) and row.get("actor") == "Child"
        ]
    inverse_trials = sum(
        1 for row in child_rows
        if row.get("action") == "knob_trial_start" and row.get("mode") == "group_inverse"
    )
    kept_trials = sum(
        1 for row in child_rows
        if row.get("action") == "knob_trial_result" and row.get("decision") == "keep"
    )
    rolled_back_trials = sum(
        1 for row in child_rows
        if row.get("action") == "knob_trial_result" and row.get("decision") == "rollback"
    )

    reflective = controller if isinstance(controller, ReflectiveP1Controller) else None
    payload = {
        "experiment": "DATA MIND 3.1 adaptive Metamath adapter" if controller else "DATA MIND 3 Metamath generalized adapter",
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
        "adaptive_control": {
            "enabled": controller is not None,
            "control_interval": args.control_interval if controller is not None else None,
            "warm_start_rows": len(experience_rows),
            "updates": sum(1 for row in controller.history if row.get("actor") == "CreativityController") if controller is not None else 0,
            "final_creativity": controller.creativity.to_dict() if controller is not None else None,
            "child_knob_play": bool(args.child_knob_play),
            "child_trial_starts": sum(1 for row in child_rows if row.get("action") == "knob_trial_start"),
            "child_inverse_trials": inverse_trials,
            "child_kept_trials": kept_trials,
            "child_rolled_back_trials": rolled_back_trials,
        },
        "reflective_p1": {
            "enabled": reflective is not None,
            "agent": "P1" if reflective is not None else None,
            "professor_facing": True if reflective is not None else None,
            "self_aware": True if reflective is not None else None,
            "professor_updates": reflective.professor_updates if reflective is not None else 0,
            "self_awareness_updates": reflective.self_awareness_updates if reflective is not None else 0,
            "repair_half_distance": reflective.repair_half_distance if reflective is not None else None,
            "last_professor_credit": reflective.last_professor_credit if reflective is not None else None,
            "professor_scalarization": dict(PROFESSOR_SCALARIZATION) if reflective is not None else None,
            "repair_horizon_semantics": "H_hat=max(0,1/q_raw-1); burden proxy, not exact transaction-geometric repair distance" if reflective is not None else None,
            "partial_credit_semantics": "locally checked structural proxy; not terminal verifier acceptance" if reflective is not None else None,
            "child_relationship": "advisory creativity under P1; Child does not own scheduling" if reflective is not None else None,
        },
    }
    args.result.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with args.historian.open("w", encoding="utf-8") as f:
        for row in result.historian:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status == "PROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
