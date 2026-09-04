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
import time

from benchmarks.ocean.generate_ocean_tptp import make_ocean
from data_mind_3.ocean.solver import parse_ocean_tptp, shortest_path_bfs
from data_mind_3.ocean.verifier import verify_ocean_certificate


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def proof_status(name: str, text: str, rc: int, timed_out: bool) -> str:
    if timed_out:
        return 'TIMEOUT'
    if re.search(r'SZS status\s+(Theorem|Unsatisfiable)', text, re.I):
        return 'PROVED'
    if name == 'SPASS' and re.search(r'Proof found', text, re.I):
        return 'PROVED'
    if name == 'Prover9' and re.search(r'THEOREM PROVED', text, re.I):
        return 'PROVED'
    if re.search(r'SZS status\s+(GaveUp|Unknown|Timeout|ResourceOut|MemoryOut)', text, re.I):
        return 'BOUNDED_UNKNOWN'
    if rc != 0:
        return 'FAULT'
    return 'UNKNOWN_OUTPUT'


def run_external(name: str, cmd: list[str], timeout_s: float, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    executable = cmd[0]
    if '/' not in executable and shutil.which(executable) is None:
        return {
            'solver': name,
            'status': 'UNAVAILABLE',
            'wall_s': 0.0,
            'returncode': None,
            'command': ' '.join(cmd),
            'time_limit_s': timeout_s,
            'reason': f'executable_not_found:{executable}',
        }
    if '/' in executable and not Path(executable).exists():
        return {
            'solver': name,
            'status': 'UNAVAILABLE',
            'wall_s': 0.0,
            'returncode': None,
            'command': ' '.join(cmd),
            'time_limit_s': timeout_s,
            'reason': f'executable_not_found:{executable}',
        }

    t0 = time.perf_counter()
    timed_out = False
    try:
        cp = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s + 5,
            stdin=subprocess.DEVNULL,
        )
        rc = cp.returncode
        text = cp.stdout
    except subprocess.TimeoutExpired as e:
        timed_out = True
        rc = 124
        text = e.stdout if isinstance(e.stdout, str) else ''
    wall = time.perf_counter() - t0
    (out_dir / f'{name}.out').write_text(text, encoding='utf-8', errors='replace')
    return {
        'solver': name,
        'status': proof_status(name, text, rc, timed_out),
        'wall_s': wall,
        'returncode': rc,
        'command': ' '.join(cmd),
        'time_limit_s': timeout_s,
        'native_inference_records': len(re.findall(r'\binference\s*\(', text)),
    }


def run_data_mind(problem_path: Path, timeout_s: float, out_dir: Path) -> dict[str, object]:
    t0 = time.perf_counter()
    problem = parse_ocean_tptp(problem_path)
    result = shortest_path_bfs(problem, timeout_s=timeout_s, breadcrumb_depth=25)
    vr = verify_ocean_certificate(problem_path, result.path) if result.path else None
    wall = time.perf_counter() - t0
    record = {
        'solver': 'DATA-MIND-3.1',
        'status': 'PROVED' if vr and vr.accepted else result.status,
        'wall_s': wall,
        'time_limit_s': timeout_s,
        'visited_nodes': result.visited_nodes,
        'frontier_peak': result.frontier_peak,
        'certificate_transitions': result.certificate_transitions,
        'verifier': vr.to_dict() if vr else None,
        'reason': result.reason,
        'implementation': 'data_mind_3.ocean.solver.shortest_path_bfs + independent Ocean verifier',
        'hidden_route_access': False,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'DATA-MIND-3.1.json').write_text(json.dumps({'record': record, 'historian': result.historian, 'path': result.path}, indent=2), encoding='utf-8')
    return record


def run_depths_f(problem_path: Path, seed: int, timeout_s: float, out_dir: Path) -> dict[str, object]:
    t0 = time.perf_counter()
    g = make_ocean(150, seed)
    public = parse_ocean_tptp(problem_path)
    if public.source != g['source'] or public.target != g['target'] or tuple(public.edges) != tuple(g['edges']):
        raise RuntimeError('Depths-F calibration regeneration does not match frozen serialized problem')
    path = tuple(g['planted'])
    vr = verify_ocean_certificate(problem_path, path)
    wall = time.perf_counter() - t0
    record = {
        'solver': 'Depths-F',
        'status': 'PROVED' if vr.accepted else 'VERIFY_REJECTED',
        'wall_s': wall,
        'time_limit_s': timeout_s,
        'certificate_transitions': max(0, len(path) - 1),
        'verifier': vr.to_dict(),
        'implementation': 'known-map calibration floor; frozen generator planted path',
        'hidden_route_access': True,
        'ranked_professional_competitor': False,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'Depths-F.json').write_text(json.dumps({'record': record, 'path': path}, indent=2), encoding='utf-8')
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--problem', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--timeout', type=float, default=1800.0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    p = a.problem
    timeout_s = a.timeout
    commands: list[tuple[str, list[str]]] = [
        ('Vampire', [os.environ.get('VAMPIRE_BIN', 'vampire'), '--mode', 'casc', '-t', str(int(timeout_s)), '-p', 'tptp', str(p)]),
        ('E', [os.environ.get('EPROVER_BIN', 'eprover'), '--auto', f'--cpu-limit={int(timeout_s)}', '--proof-object', str(p)]),
        ('iProver', [os.environ.get('IPROVER_BIN', 'iproveropt'), '--time_out_real', str(int(timeout_s)), str(p)]),
        ('SPASS', ['SPASS', '-TPTP=2', f'-TimeLimit={int(timeout_s)}', '-DocProof=1', str(p)]),
        ('Prover9', [os.environ.get('PROVER9_BIN', 'prover9'), '-tptp', '-tptp_out', '-t', str(int(timeout_s)), '-f', str(p)]),
    ]

    rows: list[dict[str, object]] = []
    for name, cmd in commands:
        r = run_external(name, cmd, timeout_s, a.out / 'raw')
        rows.append(r)
        print(name, r['status'], f"{float(r['wall_s']):.6f}s", flush=True)

    dm = run_data_mind(p, timeout_s, a.out / 'internal')
    rows.append(dm)
    print('DATA-MIND-3.1', dm['status'], f"{float(dm['wall_s']):.6f}s", flush=True)

    df = run_depths_f(p, a.seed, timeout_s, a.out / 'internal')
    rows.append(df)
    print('Depths-F', df['status'], f"{float(df['wall_s']):.6f}s", flush=True)

    problem = parse_ocean_tptp(p)
    manifest = {
        'experiment': '-003',
        'seed': a.seed,
        'Lstar': problem.declared_depth,
        'problem_file': p.name,
        'problem_sha256': sha256_file(p),
        'source': problem.source,
        'target': problem.target,
        'edges': len(problem.edges),
        'time_limit_s_per_lane': timeout_s,
        'professional_lanes': ['Vampire', 'E', 'iProver', 'SPASS', 'Prover9'],
        'internal_lanes': ['DATA-MIND-3.1', 'Depths-F'],
    }
    (a.out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (a.out / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
