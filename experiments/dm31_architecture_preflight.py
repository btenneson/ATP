#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from data_mind_3.control.agents import DEFAULT_AGENT_PROFILES

# An official run is not allowed merely because a class/function exists or a
# unit test passes. Required architecture must have already passed a runtime
# integration test demonstrating that the component is actually wired.
OFFICIAL_READY = {"INTEGRATION-TESTED", "EXERCISED IN RUN", "VERIFIED"}
REQUIRED_OFFICIAL = (
    "eight_agent_profiles",
    "four_couples_live_runtime",
    "couple_direct_communication",
    "subscript1_self_awareness_ci",
    "subscript2_no_ci",
    "professor_addresses_only_subscript1",
    "professor_smooth_partial_credit",
    "transaction_geometry_dc",
    "repair_horizon_Hc",
    "P1_engine", "P2_engine", "R1_engine", "R2_engine",
    "I1_engine", "I2_engine", "C1_engine", "C2_engine",
    "verifier_V", "BANK", "FUTUREBANK", "COMPASS", "controller",
    "settlement_tensor", "Child", "Counselor", "Picard", "Creativity",
    "Dreamer", "Regulation", "Learner", "Horizon", "Compiler",
    "Quotient_Hunter", "Presentation_Manager", "Sentinel", "Quarantine",
    "federated_verified_memory", "persistent_logs_replay",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def null_paths(value: Any, prefix: str = "") -> list[str]:
    """Return every explicit unresolved/null leaf in the runtime config."""

    if value is None:
        return [prefix or "<root>"]
    if isinstance(value, dict):
        out: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.extend(null_paths(child, path))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for i, child in enumerate(value):
            path = f"{prefix}[{i}]"
            out.extend(null_paths(child, path))
        return out
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("report", "official"), default="report")
    ap.add_argument(
        "--snapshot",
        default="data_mind_3/spec/DATA_MIND_3_1_CANONICAL_ARCHITECTURE_SNAPSHOT_001.md",
    )
    ap.add_argument(
        "--status",
        default="data_mind_3/spec/IMPLEMENTATION_STATUS_001.json",
    )
    ap.add_argument(
        "--runtime-config",
        default="data_mind_3/spec/RUNTIME_CONFIG_001.json",
    )
    ap.add_argument(
        "--benchmark-lock",
        default="benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json",
    )
    args = ap.parse_args()

    snapshot = Path(args.snapshot)
    status = json.loads(Path(args.status).read_text(encoding="utf-8"))
    runtime = json.loads(Path(args.runtime_config).read_text(encoding="utf-8"))
    lock = json.loads(Path(args.benchmark_lock).read_text(encoding="utf-8"))
    actual_hash = digest(snapshot)
    expected_hash = status["architecture_snapshot_sha256"]

    blockers: list[str] = []
    checks: list[dict] = []

    checks.append({
        "check": "architecture_snapshot_sha256",
        "expected": expected_hash,
        "actual": actual_hash,
        "ok": actual_hash == expected_hash,
    })
    if actual_hash != expected_hash:
        blockers.append("canonical architecture snapshot hash mismatch")
    if lock.get("architecture_snapshot_sha256") != expected_hash:
        blockers.append("benchmark lock points at a different architecture snapshot")
    if runtime.get("architecture_snapshot_sha256") != expected_hash:
        blockers.append("runtime config points at a different architecture snapshot")

    names = [p.name for p in DEFAULT_AGENT_PROFILES]
    expected_names = ["P1", "P2", "R1", "R2", "I1", "I2", "C1", "C2"]
    checks.append({"check": "eight_agent_profile_names", "actual": names, "ok": names == expected_names})
    if names != expected_names:
        blockers.append(f"agent profile set/order mismatch: {names!r}")

    for p in DEFAULT_AGENT_PROFILES:
        expected_facing = p.member == 1
        if p.professor_facing != expected_facing:
            blockers.append(f"{p.name} professor-facing contract mismatch")
        if p.self_aware != expected_facing:
            blockers.append(f"{p.name} self-awareness presence contract mismatch")

    if len(lock.get("targets", [])) != 20:
        blockers.append("benchmark lock does not contain exactly 20 targets")
    if len({row["label"] for row in lock.get("targets", [])}) != 20:
        blockers.append("benchmark target labels are not unique")
    if int(lock.get("training_count", -1)) != 45410 or int(lock.get("holdout_count", -1)) != 2390:
        blockers.append("frozen 95/5 benchmark counts changed")

    components = status.get("components", {})
    for key in REQUIRED_OFFICIAL:
        row = components.get(key)
        if row is None:
            blockers.append(f"missing implementation-status row: {key}")
            continue
        component_status = row.get("status")
        if component_status not in OFFICIAL_READY:
            detail = row.get("reason") or row.get("evidence") or "not integration-tested in live runtime"
            blockers.append(f"{key}: {component_status} — {detail}")

    unresolved_config = null_paths(runtime)
    for path in unresolved_config:
        blockers.append(f"RUNTIME CONFIG UNRESOLVED: {path}")

    unresolved = list(status.get("unresolved_from_snapshot", ()))
    for item in unresolved:
        blockers.append(f"UNRESOLVED SNAPSHOT DECISION: {item}")

    report = {
        "mode": args.mode,
        "official_ready_statuses": sorted(OFFICIAL_READY),
        "architecture_snapshot_sha256": actual_hash,
        "benchmark_name": lock.get("benchmark_name"),
        "training_count": lock.get("training_count"),
        "holdout_count": lock.get("holdout_count"),
        "target_count": len(lock.get("targets", [])),
        "runtime_config_status": runtime.get("status"),
        "runtime_config_unresolved_paths": unresolved_config,
        "checks": checks,
        "official_run_ready": not blockers,
        "blockers": blockers,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if args.mode == "official" and blockers:
        print("OFFICIAL DATA MIND 3.1 RUN ABORTED: architecture/config is not exact/complete/live-wired.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
