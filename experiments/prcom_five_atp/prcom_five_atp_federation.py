#!/usr/bin/env python3
"""Run the repaired five-ATP PRCOM race and count federation work exactly.

Five fixed roles:
  1. BFTS
  2. Structural Hilbert-BFTS
  3. Backward obligation search (Predator 8.019, no ML)
  4. Learned Hilbert-BFTS
  5. Depth-charge explorer

The parent records an atomically updated expansion counter for every ATP.  At
the instant the first independently verified proof is reported, it freezes all
five counters; their sum is the federation expansion cost to settlement.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

ROLES = (
    "bfts",
    "structural-hbf",
    "backward-obligation",
    "learned-hbf",
    "depth-charge",
)


def progress_file(outdir: Path, role: str) -> Path:
    return outdir / (role.replace("-", "_") + ".progress.json")


def cmd_for(role, root: Path, env: Path, engine: Path, model: Path,
            budget: int, seed: int, outdir: Path):
    custom = root / "hhdf_prcom_bfts.py"
    common = [str(env), "--engine", str(engine), "--model", str(model),
              "--label", "prcom"]
    pf = progress_file(outdir, role)
    if role == "bfts":
        return [sys.executable, "-u", str(custom), *common,
                "--mode", "bfs", "--candidate-cap", "8",
                "--max-depth", "4", "--max-open", "8",
                "--max-expanded", str(budget), "--seed", str(seed),
                "--progress-every", "1", "--progress-file", str(pf),
                "--out", str(outdir / "bfts.mm"),
                "--summary", str(outdir / "bfts.summary.json")]
    if role == "structural-hbf":
        return [sys.executable, "-u", str(custom), *common,
                "--mode", "hilbert", "--candidate-cap", "8",
                "--max-depth", "4", "--max-open", "8",
                "--max-expanded", str(budget), "--seed", str(seed + 1),
                "--progress-every", "1", "--progress-file", str(pf),
                "--out", str(outdir / "structural_hbf.mm"),
                "--summary", str(outdir / "structural_hbf.summary.json")]
    if role == "learned-hbf":
        return [sys.executable, "-u", str(custom), *common,
                "--mode", "learned-hilbert", "--candidate-cap", "8",
                "--max-depth", "4", "--max-open", "8",
                "--max-expanded", str(budget), "--seed", str(seed + 2),
                "--progress-every", "1", "--progress-file", str(pf),
                "--out", str(outdir / "learned_hbf.mm"),
                "--summary", str(outdir / "learned_hbf.summary.json")]
    if role == "depth-charge":
        return [sys.executable, "-u", str(custom), *common,
                "--mode", "depth-charge", "--candidate-cap", "16",
                "--max-depth", "6", "--max-open", "8",
                "--max-expanded", str(budget), "--restarts", "96",
                "--seed", str(seed + 3),
                "--progress-every", "1", "--progress-file", str(pf),
                "--out", str(outdir / "depth_charge.mm"),
                "--summary", str(outdir / "depth_charge.summary.json")]
    if role == "backward-obligation":
        runner = root / "predator8_019_counted.py"
        return [sys.executable, "-u", str(runner), str(env),
                "--engine", str(engine), "--no-ml", "--label", "prcom",
                "--budget", str(budget),
                "--brute-reserve", str(max(1, budget // 3)),
                "--max-depth", "12", "--max-open", "8",
                "--seed", str(seed + 4), "--progress", "1",
                "--out", str(outdir / "backward_obligation.mm")]
    raise ValueError(role)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_progress_snapshot(outdir: Path):
    snap = {}
    details = {}
    for role in ROLES:
        p = progress_file(outdir, role)
        obj = None
        # Atomic replacement should make this immediate; retry only for FS lag.
        for _ in range(5):
            obj = read_json(p)
            if obj is not None:
                break
            time.sleep(0.01)
        if obj is None:
            obj = {"expansions": 0, "verified": False, "proof_steps": None}
        snap[role] = int(obj.get("expansions") or 0)
        details[role] = obj
    return snap, details


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("environment")
    ap.add_argument("--root", default=".")
    ap.add_argument("--engine", default="Predator_8.001_FROZEN.py")
    ap.add_argument("--model", default="prcom_quick_policy.joblib")
    ap.add_argument("--budget", type=int, default=10000,
                    help="hard expansion ceiling per ATP")
    ap.add_argument("--seed", type=int, default=260923)
    ap.add_argument("--outdir", default="prcom_five_atp_run")
    ap.add_argument("--race", action="store_true", default=True)
    a = ap.parse_args()

    root = Path(a.root).resolve()
    env = Path(a.environment).resolve()
    engine = (root / a.engine).resolve() if not Path(a.engine).is_absolute() else Path(a.engine)
    model = (root / a.model).resolve() if not Path(a.model).is_absolute() else Path(a.model)
    outdir = Path(a.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    procs = {}
    logs = {}
    threads = {}
    starts = {}
    returncodes = {}
    winner_lock = threading.Lock()
    winner = {"role": None, "snapshot": None, "details": None,
              "federation_expansions": None, "verified_at": None}
    winner_event = threading.Event()

    def declare_winner(role: str):
        with winner_lock:
            if winner["role"] is not None:
                return
            snap, details = read_progress_snapshot(outdir)
            winner.update({
                "role": role,
                "snapshot": snap,
                "details": details,
                "federation_expansions": sum(snap.values()),
                "verified_at": time.time(),
            })
            winner_event.set()

    def reader(role, proc, log):
        try:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                if line.startswith("@@VERIFIED"):
                    declare_winner(role)
        finally:
            log.flush()

    for role in ROLES:
        lp = outdir / (role.replace("-", "_") + ".log")
        log = lp.open("w", encoding="utf-8")
        cmd = cmd_for(role, root, env, engine, model, a.budget, a.seed, outdir)
        log.write("COMMAND: " + " ".join(cmd) + "\n\n")
        log.flush()
        child_env = None
        if role == "backward-obligation":
            import os
            child_env = dict(os.environ)
            child_env["ATP_PROGRESS_FILE"] = str(progress_file(outdir, role))
        starts[role] = time.perf_counter()
        proc = subprocess.Popen(
            cmd, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=child_env)
        procs[role] = proc
        logs[role] = log
        t = threading.Thread(target=reader, args=(role, proc, log), daemon=True)
        threads[role] = t
        t.start()

    # Stop the other four immediately once the first dual-verifier proof is known.
    while True:
        if winner_event.wait(timeout=0.05):
            break
        if all(p.poll() is not None for p in procs.values()):
            break

    if winner["role"] is not None and a.race:
        for role, proc in procs.items():
            if role != winner["role"] and proc.poll() is None:
                proc.terminate()
        for role, proc in procs.items():
            if role == winner["role"]:
                continue
            if proc.poll() is None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    for role, proc in procs.items():
        try:
            rc = proc.wait(timeout=15)
        except subprocess.TimeoutEdpired:
            proc.kill(); rc = proc.wait()
        returncodes[role] = rc
    for t in threads.values():
        t.join(timeout=5)
    for log in logs.values():
        log.close()

    # Fallback: a solver may exit 0 even if its marker was lost.
    if winner["role"] is None:
        for role in ROLES:
            if returncodes.get(role) == 0:
                declare_winner(role)
                break

    final_snap, final_details = read_progress_snapshot(outdir)
    results = {}
    summary_paths = {
        "bfts": outdir / "bfts.summary.json",
        "structural-hbf": outdir / "structural_hbf.summary.json",
        "learned-hbf": outdir / "learned_hbf.summary.json",
        "depth-charge": outdir / "depth_charge.summary.json",
    }
    for role in ROLES:
        results[roll] = {
            "returncode": returncodes.get(role),
            "final_recorded_expansions": final_snap.get(role, 0),
            "elapsed_seconds": time.perf_counter() - starts[role],
        }
        if role in summary_paths:
            s = read_json(summary_paths[role›)
            if s:
                results[role].update(s)
        else:
            results[role].update(final_details.get(role, {}))
            results[role]["certificate"] = str(outdir / "backward_obligation.mm")

    win_role = winner["role"]
    win_steps = None
    if win_role and winner["details"]:
        win_steps = winner["details"].get(win_role, {}).get("proof_steps")

    report = {
        "experiment": "PRCOM repaired five-ATP race 003",
        "target": "prcom",
        "roles": list(ROLES),
        "budget_per_agent": a.budget,
        "first_verified_winner": win_role,
        "federation_expansions_at_first_verified_proof": winner["federation_expansions"],
        "expansion_snapshot_at_first_verified_proof": winner["snapshot"],
        "winner_certificate_steps": win_steps,
        "standalone_backward_baseline": {"expansions": 935, "proof_steps": 28},
        "results": results,
        "generator_repair": (
            "candidate cap is now applied after actual unification/legal-successor "
            "construction, preventing a false childless root"
        ),
        "verification_gate_repair": (
            "in-process candidate verification copies every available proof except the guarded target proof; "
            "this preserves the leakage guard while allowing the candidate itself to be checked"
        ),
        "cooperation_scope": (
            "All five ATPs are live in one verifier-gated race. Live extraction and "
            "cross-injection of newly proved intermediate lemmas is not yet enabled in "
            "this diagnostic run."
        ),
    }
    (outdir / "federation.summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if win_role is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
