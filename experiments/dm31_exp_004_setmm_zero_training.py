#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def proof_status(name: str, text: str, rc: int, timed_out: bool) -> str:
    if timed_out:
        return "TIMEOUT"
    if re.search(r"SZS status\s+(Theorem|Unsatisfiable)", text, re.I):
        return "PROVED"
    if name == "SPASS" and re.search(r"Proof found", text, re.I):
        return "PROVED"
    if name == "Prover9" and re.search(r"THEOREM PROVED", text, re.I):
        return "PROVED"
    if re.search(r"SZS status\s+(GaveUp|Unknown|Timeout|ResourceOut|MemoryOut)", text, re.I):
        return "BOUNDED_UNKNOWN"
    if rc != 0:
        return "FAULT"
    return "UNKNOWN_OUTPUT"


def executable_available(executable: str) -> bool:
    if "/" in executable:
        return Path(executable).exists()
    return shutil.which(executable) is not None


def run_external(name: str, cmd: list[str], timeout_s: float, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    executable = cmd[0]
    if not executable_available(executable):
        return {
            "solver": name,
            "status": "UNAVAILABLE",
            "wall_s": 0.0,
            "returncode": None,
            "command": " ".join(cmd),
            "time_limit_s": timeout_s,
            "reason": f"executable_not_found:{executable}",
            "training_used": False,
        }

    t0 = time.perf_counter()
    timed_out = False
    try:
        cp = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s + 15,
            stdin=subprocess.DEVNULL,
        )
        rc = cp.returncode
        text = cp.stdout
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        text = exc.stdout if isinstance(exc.stdout, str) else ""
    wall = time.perf_counter() - t0
    (out_dir / f"{name}.out").write_text(text, encoding="utf-8", errors="replace")
    return {
        "solver": name,
        "status": proof_status(name, text, rc, timed_out),
        "wall_s": wall,
        "returncode": rc,
        "command": " ".join(cmd),
        "time_limit_s": timeout_s,
        "native_inference_records": len(re.findall(r"\binference\s*\(", text)),
        "training_used": False,
        "premise_policy": "all FOL-translatable set.mm assertions strictly before target; no learned or human-proof premise selection",
    }


def run_data_mind(label: str, setmm: Path, timeout_s: float, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "DATA-MIND-3.1-result.json"
    historian_path = out_dir / "DATA-MIND-3.1-historian.jsonl"
    cmd = [
        sys.executable,
        "run_dm3_metamath_target.py",
        str(setmm),
        "--label", label,
        "--verifier", "metamath.py",
        "--max-expansions", "100000",
        "--candidate-cap", "128",
        "--max-depth", "150",
        "--max-open", "64",
        "--timeout", str(float(timeout_s)),
        "--reflective-p1",
        "--control-interval", "16",
        "--result", str(result_path),
        "--historian", str(historian_path),
    ]
    # Deliberately no --experience-in and no --experience-out.  Every target
    # therefore begins with a blank cross-target experience state.
    t0 = time.perf_counter()
    timed_out = False
    try:
        cp = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s + 30,
            stdin=subprocess.DEVNULL,
        )
        rc = cp.returncode
        text = cp.stdout
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        text = exc.stdout if isinstance(exc.stdout, str) else ""
    wall = time.perf_counter() - t0
    (out_dir / "DATA-MIND-3.1.out").write_text(text, encoding="utf-8", errors="replace")

    payload: dict[str, Any] | None = None
    if result_path.exists():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
    if timed_out:
        status = "TIMEOUT"
    elif payload and payload.get("status") == "PROVED" and payload.get("verification", {}).get("accepted") is True:
        status = "PROVED"
    elif payload and isinstance(payload.get("status"), str):
        status = str(payload["status"])
    elif rc != 0:
        status = "FAULT"
    else:
        status = "UNKNOWN_OUTPUT"

    adaptive = payload.get("adaptive_control", {}) if payload else {}
    reflective = payload.get("reflective_p1", {}) if payload else {}
    return {
        "solver": "DATA-MIND-3.1-zero-training-reflective-P1",
        "status": status,
        "wall_s": wall,
        "returncode": rc,
        "command": " ".join(cmd),
        "time_limit_s": timeout_s,
        "training_used": False,
        "cross_target_experience_used": False,
        "experience_in": None,
        "experience_out": None,
        "legal_context": "native Metamath assertions strictly before target",
        "max_expansions": 100000,
        "max_depth": 150,
        "candidate_cap": 128,
        "max_open": 64,
        "professor_reflective_p1": bool(reflective.get("enabled")),
        "professor_updates": reflective.get("professor_updates"),
        "self_awareness_updates": reflective.get("self_awareness_updates"),
        "child_knob_play": adaptive.get("child_knob_play"),
        "child_trial_starts": adaptive.get("child_trial_starts"),
        "child_inverse_trials": adaptive.get("child_inverse_trials"),
        "expansions": payload.get("expansions_to_first_verifier_accepted_proof") if payload else None,
        "proof_step_labels": payload.get("proof_step_labels") if payload else None,
        "verification": payload.get("verification") if payload else None,
        "implementation_note": "native DATA MIND 3.1 Metamath adapter with reflective Professor/Child control; this is not the unresolved official eight-principal-agent settlement entrypoint",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Experiment -004: fresh random set.mm zero-training ATP comparison")
    ap.add_argument("--label", required=True)
    ap.add_argument("--setmm", type=Path, required=True)
    ap.add_argument("--problem", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=float, default=1800.0)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    p = args.problem
    timeout_s = args.timeout
    commands: list[tuple[str, list[str]]] = [
        ("Vampire", [os.environ.get("VAMPIRE_BIN", "vampire"), "--mode", "casc", "-t", str(int(timeout_s)), "-p", "tptp", str(p)]),
        ("E", [os.environ.get("EPROVER_BIN", "eprover"), "--auto", f"--cpu-limit={int(timeout_s)}", "--proof-object", str(p)]),
        ("iProver", [os.environ.get("IPROVER_BIN", "iproveropt"), "--time_out_real", str(int(timeout_s)), str(p)]),
        ("SPASS", ["SPASS", "-TPTP=2", f"-TimeLimit={int(timeout_s)}", "-DocProof=1", str(p)]),
        ("Prover9", [os.environ.get("PROVER9_BIN", "prover9"), "-tptp", "-tptp_out", "-t", str(int(timeout_s)), "-f", str(p)]),
    ]

    rows: list[dict[str, Any]] = []
    for name, cmd in commands:
        row = run_external(name, cmd, timeout_s, args.out / "raw")
        row["target"] = args.label
        rows.append(row)
        print(name, row["status"], f"{float(row['wall_s']):.6f}s", flush=True)

    dm = run_data_mind(args.label, args.setmm, timeout_s, args.out / "internal")
    dm["target"] = args.label
    rows.append(dm)
    print(dm["solver"], dm["status"], f"{float(dm['wall_s']):.6f}s", flush=True)

    # Depths-F in Experiment -003 was a hidden-route Ocean calibration floor,
    # not a generic Metamath prover.  Keep the lane visible rather than
    # pretending it can fairly solve arbitrary set.mm theorems.
    rows.append({
        "solver": "Depths-F",
        "target": args.label,
        "status": "NOT_APPLICABLE",
        "wall_s": 0.0,
        "time_limit_s": timeout_s,
        "training_used": False,
        "reason": "Experiment -003 Depths-F used privileged planted-route access and no generic set.mm/Metamath implementation exists in the repository",
        "ranked_competitor": False,
    })

    manifest = {
        "experiment": "-004",
        "target": args.label,
        "setmm_sha256": sha256_file(args.setmm),
        "problem_sha256": sha256_file(p),
        "time_limit_s_per_active_lane": timeout_s,
        "zero_training": True,
        "fresh_process_per_target": True,
        "external_premise_policy": "all translated assertions strictly before target; no learned or human-proof premise selection",
        "data_mind_experience_policy": "blank at target start; no cross-target experience input/output",
        "professional_lanes": ["Vampire", "E", "iProver", "SPASS", "Prover9"],
        "internal_lanes": ["DATA-MIND-3.1-zero-training-reflective-P1"],
        "calibration_lane": "Depths-F NOT_APPLICABLE for set.mm",
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "results.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
