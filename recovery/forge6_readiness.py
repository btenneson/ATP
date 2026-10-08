#!/usr/bin/env python3
"""Read-only recovery diagnostic for FORGE-6 Eureka Prompt Experiment 1.

This does NOT implement FORGE-6, start agents, or authorize scientific runs.
It checks the archived Metamath verifier separately from the six-board/SAT
integration obligations and reports missing requirements without substitutes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REQUIRED_BOARDS = ("B0", "B1", "B2", "B3", "B4", "B5")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def metamath_selftest(root: Path) -> dict:
    script = root / "metamath.py"
    if not script.is_file():
        return {"status": "MISSING", "scope": "Metamath only"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "selftest"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "ERROR", "error": str(exc), "scope": "Metamath only"}
    return {
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-1000:],
        "scope": "Metamath verifier selftest only; does not verify F_k SAT/cost results",
    }


def diagnose(root: Path, manifest_path: Path) -> dict:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    roles = data.get("six_board_roles", {})
    roles_exact = isinstance(roles, dict) and tuple(roles) == REQUIRED_BOARDS
    expected_fields = data.get("required_local_artifacts", {})
    expected_sha = data.get("expected_sha256", {})
    checks = []
    for key, declared in expected_fields.items():
        path = safe_file(root, declared)
        if path is None:
            checks.append({
                "key": key, "status": "UNRESOLVED",
                "declared_path": declared,
                "reason": "No verified, local, regular file; missing or invalid path",
            })
            continue
        h = sha256_file(path)
        frozen_hash = expected_sha.get(key)
        if key in expected_sha and not (
            isinstance(frozen_hash, str) and len(frozen_hash) == 64
        ):
            checks.append({
                "key": key, "status": "UNPINNED", "declared_path": declared,
                "sha256_observed": h,
                "reason": "Reference SHA-256 has not been frozen",
            })
        elif frozen_hash is not None and h != frozen_hash:
            checks.append({
                "key": key, "status": "HASH_MISMATCH", "declared_path": declared,
                "sha256_observed": h, "sha256_expected": frozen_hash,
            })
        else:
            checks.append({
                "key": key, "status": "FILE_FOUND_NOT_INTEGRATION_TESTED",
                "declared_path": declared, "sha256_observed": h,
            })
    selftest = metamath_selftest(root)
    missing = [entry["key"] for entry in checks
               if entry["status"] != "FILE_FOUND_NOT_INTEGRATION_TESTED"]
    if not roles_exact:
        missing.append("six_board_role_contract")
    if selftest["status"] != "PASS":
        missing.append("metamath_selftest")
    return {
        "experiment_id": data.get("experiment_id"),
        "purpose": "Read-only recovery diagnostic, not an experimental arm",
        "manifest_sha256": sha256_file(manifest_path),
        "six_board_roles_exact": roles_exact,
        "metamath_selftest": selftest,
        "artifact_checks": checks,
        "unresolved_requirements": missing,
        "static_status": "BLOCKED" if missing else "STATIC_FILES_PRESENT_UNVALIDATED",
        "official_experiment_authorized": False,
        "scientific_trials_executed": 0,
        "next_action": (
            "Recover/pin exact six-board launcher, trained creativity module "
            "and checkpoint, SAT evaluator/recognizer/verifier, certified BANK, "
            "input bundle, cost ledger and a genuine live integration receipt. "
            "Independently exercise the whole integration before experiment."
        ),
        "disclaimer": (
            "Passing a Metamath selftest or finding files is not a proof of "
            "FORGE-6 readiness. No eight-agent surrogate is permitted."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="recovery/forge6_exp1_manifest.json")
    ap.add_argument("--out", default="recovery/forge6_readiness_report.json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = root / args.manifest
    output = root / args.out
    report = diagnose(root, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "static_status": report["static_status"],
        "metamath_selftest": report["metamath_selftest"]["status"],
        "missing_count": len(report["unresolved_requirements"]),
        "official_experiment_authorized": False,
        "report": str(output.relative_to(root)),
    }, indent=2))
    # Diagnostic completion is distinct from experiment readiness.
    # An intentionally blocked preflight is an expected diagnostic result.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
