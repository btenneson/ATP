#!/usr/bin/env python3
from __future__ import annotations

"""Strict DATA MIND 3.1 Frozen-20 settlement launcher.

There is intentionally no built-in fallback search engine here.  Before a
scientific run the user-approved runtime config must name one exact entrypoint,
and the architecture preflight must already be fully green.  This prevents an
old/single-agent/surrogate engine from being selected merely because it is
available in the repository.
"""

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

ALL_AGENTS = ("P1", "P2", "R1", "R2", "I1", "I2", "C1", "C2")
SETTLEMENT_STATUSES = {"PROVED", "REFUTED", "INDEPENDENT", "CONTRADICTION", "UNKNOWN"}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require_official_preflight() -> None:
    cmd = [sys.executable, "experiments/dm31_architecture_preflight.py", "--mode", "official"]
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def resolve_entrypoint(spec: str) -> Callable[..., dict[str, Any]]:
    if ":" not in spec:
        raise RuntimeError("official_settlement_entrypoint must be 'module:function'")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, function_name, None)
    if not callable(fn):
        raise RuntimeError(f"settlement entrypoint is not callable: {spec}")
    return fn


def validate_learner(
    learner: dict[str, Any],
    runtime: dict[str, Any],
    lock: dict[str, Any],
    learner_path: Path,
) -> None:
    expected_hash = runtime.get("official_learner_artifact_sha256")
    if not isinstance(expected_hash, str):
        raise RuntimeError("official learner artifact hash is not frozen")
    actual_hash = sha256_file(learner_path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"learner artifact SHA-256 mismatch: {actual_hash} != {expected_hash}"
        )
    expected_backend = runtime.get("official_learner_backend")
    actual_backend = learner.get("model", {}).get("learner_backend")
    if actual_backend != expected_backend:
        raise RuntimeError(
            f"learner backend mismatch: {actual_backend!r} != {expected_backend!r}"
        )
    if learner.get("architecture_snapshot_sha256") != lock["architecture_snapshot_sha256"]:
        raise RuntimeError("learner was produced for a different architecture snapshot")
    if learner.get("benchmark_name") != lock["benchmark_name"]:
        raise RuntimeError("learner was produced for a different benchmark")
    if learner.get("heldout_proofs_used_for_training") is not False:
        raise RuntimeError("learner reports held-out proof use")
    if learner.get("heldout_proofs_emitted") is not False:
        raise RuntimeError("learner artifact contains/emits held-out proofs")
    if learner.get("target_exposed_to_training") is not False:
        raise RuntimeError("learner reports target exposure during training")


def validate_result(result: dict[str, Any], target_label: str) -> None:
    if result.get("target") != target_label:
        raise RuntimeError("settlement engine returned the wrong target label")
    if result.get("status") not in SETTLEMENT_STATUSES:
        raise RuntimeError(f"invalid settlement status: {result.get('status')!r}")

    activity = result.get("agent_activity")
    if not isinstance(activity, dict):
        raise RuntimeError("result must contain agent_activity for all eight principal agents")
    if set(activity) != set(ALL_AGENTS):
        raise RuntimeError(
            "agent_activity must name exactly P1,P2,R1,R2,I1,I2,C1,C2; "
            f"got {sorted(activity)}"
        )
    for name in ALL_AGENTS:
        row = activity[name]
        if not isinstance(row, dict):
            raise RuntimeError(f"agent_activity[{name}] must be an object")
        if "initialized" not in row or row["initialized"] is not True:
            raise RuntimeError(f"{name} was not initialized")
        if "activations" not in row:
            raise RuntimeError(f"{name} is missing activation accounting")

    # The exact rule for minimum activations before early global settlement is
    # intentionally NOT invented here.  RUNTIME_CONFIG_001 must resolve the
    # resource-floor and stop-policy fields before official preflight can open.
    if result.get("silent_component_substitution") not in (False, None):
        raise RuntimeError("settlement engine reports component substitution")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-ordinal", type=int, required=True)
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--learner", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--runtime-config",
        default="data_mind_3/spec/RUNTIME_CONFIG_001.json",
    )
    ap.add_argument(
        "--benchmark-lock",
        default="benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json",
    )
    args = ap.parse_args()

    require_official_preflight()

    runtime = load_json(args.runtime_config)
    lock = load_json(args.benchmark_lock)
    targets = sorted(lock["targets"], key=lambda row: int(row["ordinal"]))
    if not 0 <= args.target_ordinal < len(targets):
        raise RuntimeError("target ordinal out of range")
    target = targets[args.target_ordinal]

    entrypoint_spec = runtime.get("official_settlement_entrypoint")
    if not isinstance(entrypoint_spec, str) or not entrypoint_spec.strip():
        raise RuntimeError("official_settlement_entrypoint is not frozen")

    learner_path = Path(args.learner)
    learner = load_json(learner_path)
    validate_learner(learner, runtime, lock, learner_path)

    settle = resolve_entrypoint(entrypoint_spec)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    result = settle(
        setmm_path=str(Path(args.setmm)),
        learner_artifact=learner,
        benchmark_lock=lock,
        target_ordinal=args.target_ordinal,
        target_record=target,
        runtime_config=runtime,
        output_dir=str(out),
    )
    if not isinstance(result, dict):
        raise RuntimeError("official settlement entrypoint must return a result dict")
    validate_result(result, str(target["label"]))

    result_path = out / "result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
