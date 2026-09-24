#!/usr/bin/env python3
"""Launch the fixed five-ATP PRCOM portfolio/federation shell.

Roles are intentionally frozen at five:
  1. BFTS
  2. Structural Hilbert-BFTS
  3. Backward obligation search (Predator 8.019 target-generic, no ML)
  4. Learned Hilbert-BFTS
  5. Stochastic depth-charge explorer

This first PRCOM experiment is a heterogeneous shared-target portfolio with a
common verifier contract and common output archive. It does NOT yet claim full
HHDF lemma donation between live searches.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROLES = (
    "bfts",
    "structural-hbf",
    "backward-obligation",
    "learned-hbf",
    "depth-charge",
)


def cmd_for(role, root: Path, env: Path, engine: Path, model: Path,
            budget: int, seed: int, outdir: Path):
    custom = root / "hhdf_prcom_bfts.py"
    common = [str(env), "--engine", str(engine), "--model", str(model),
              "--label", "prcom"]
    if role == "bfts":
        return [sys.executable, str(custom), *common,
                "--mode", "bfs", "--candidate-cap", "8",
                "--max-depth", "4", "--max-open", "8",
                "--max-expanded", str(budget), "--seed", str(seed),
                "--out", str(outdir / "bfts.mm"),
                "--summary", str(outdir / "bfts.summary.json")]
    if role == "structural-hbf":
        return [sys.executable, str(custom), *common,
                "--mode", "hilbert", "--candidate-cap", "8",
                "--max-depth", "4", "--max-open", "8",
                "--max-expanded", str(budget), "--seed", str(seed + 1),
                "--out", str(outdir / "structural_hbf.mm"),
                "--summary", str(outdir / "structural_hbf.summary.json")]
    if role == "learned-hbf":
        return [sys.executable, str(custom), *common,
                "--mode", "learned-hilbert", "--candidate-cap", "8",
                "--max-depth", "4", "--max-open", "8",
                "--max-expanded", str(budget), "--seed", str(seed + 2),
                "--out", str(outdir / "learned_hbf.mm"),
                "--summary", str(outdir / "learned_hbf.summary.json")]
    if role == "depth-charge":
        return [sys.executable, str(custom), *common,
                "--mode", "depth-charge", "--candidate-cap", "16",
                "--max-depth", "6", "--max-open", "8",
                "--max-expanded", str(budget), "--restarts", "96",
                "--seed", str(seed + 3),
                "--out", str(outdir / "depth_charge.mm"),
                "--summary", str(outdir / "depth_charge.summary.json")]
    if role == "backward-obligation":
        runner = root / "predator8_019_target.py"
        return [sys.executable, str(runner), str(env),
                "--engine", str(engine), "--no-ml", "--label", "prcom",
                "--budget", str(budget),
                "--brute-reserve", str(max(1, budget // 3)),
                "--max-depth", "12", "--max-open", "8",
                "--seed", str(seed + 4),
                "--out", str(outdir / "backward_obligation.mm")]
    raise ValueError(role)


def read_summary(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--root", default=".", help="recovered8_002 directory")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", default="prcom_quick_policy.joblib")
    ap.add_argument("--budget", type=int, default=30000,
                    help="per-agent expansion budget")
    ap.add_argument("--seed", type=int, default=260923)
    ap.add_argument("--outdir", default="prcom_five_atp_run")
    ap.add_argument("--race", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    env = Path(args.environment).resolve()
    engine = (root / args.engine).resolve() if not Path(args.engine).is_absolute() else Path(args.engine)
    model = (root / args.model).resolve() if not Path(args.model).is_absolute() else Path(args.model)
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    procs = {}
    logs = {}
    starts = {}
    results = {}
    for role in ROLES:
        log_path = outdir / (role.replace("-", "_") + ".log")
        log = log_path.open("w", encoding="utf-8")
        cmd = cmd_for(role, root, env, engine, model, args.budget, args.seed, outdir)
        log.write("COMMAND: " + " ".join(cmd) + "\n\n")
        log.flush()
        starts[role] = time.perf_counter()
        procs[role] = subprocess.Popen(cmd, cwd=str(root), stdout=log,
                                       stderr=subprocess.STDOUT, text=True)
        logs[role] = log

    winner = None
    while procs:
        time.sleep(0.25)
        for role, proc in list(procs.items()):
            rc = proc.poll()
            if rc is None:
                continue
            elapsed = time.perf_counter() - starts[role]
            results[role] = {"returncode": rc, "elapsed_seconds": elapsed}
            logs[role].flush(); logs[role].close()
            del procs[role]
            if rc == 0 and winner is None:
                winner = role
                if args.race:
                    for other, p in procs.items():
                        p.terminate()
                    for other, p in list(procs.items()):
                        try:
                            p.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            p.kill(); p.wait()
                        elapsed2 = time.perf_counter() - starts[other]
                        results[other] = {"returncode": p.returncode,
                                          "elapsed_seconds": elapsed2,
                                          "terminated_after_winner": role}
                        logs[other].flush(); logs[other].close()
                        del procs[other]
                    break

    paths = {
        "bfts": outdir / "bfts.summary.json",
        "structural-hbf": outdir / "structural_hbf.summary.json",
        "learned-hbf": outdir / "learned_hbf.summary.json",
        "depth-charge": outdir / "depth_charge.summary.json",
    }
    for role, p in paths.items():
        s = read_summary(p)
        if s is not None:
            results.setdefault(role, {}).update(s)
    if "backward-obligation" in results:
        results["backward-obligation"]["solved"] = (
            results["backward-obligation"].get("returncode") == 0)
        results["backward-obligation"]["certificate"] = str(
            outdir / "backward_obligation.mm")

    report = {
        "experiment": "PRCOM five-ATP federation shell 001",
        "target": "prcom",
        "roles": list(ROLES),
        "budget_per_agent": args.budget,
        "race_mode": args.race,
        "first_verified_winner": winner,
        "results": results,
        "scientific_caveat": (
            "This version is a heterogeneous shared-target portfolio. Full live HHDF "
            "donation of newly proved intermediate lemmas is not yet enabled."
        ),
    }
    (outdir / "federation.summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if winner is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
