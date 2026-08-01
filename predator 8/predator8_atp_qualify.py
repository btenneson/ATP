#!/usr/bin/env python3
"""Executable ATP qualification gate for frozen Predator 8.001.

The suite deliberately denies the search access to each target's stored proof.
For every positive control it searches using only earlier assertions, emits a
Metamath certificate, and starts ``predator8_external_cv.py`` in a fresh
process.  The external checker imports no Predator module.

This is a qualification suite, not a performance benchmark.  Passing means
the tested program behaves as a certificate-producing bounded ATP on the
tested controls.  It does not establish completeness or prove every target.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections import UserDict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class GuardedProofs(UserDict):
    """Dictionary that raises if search code touches a held-out proof."""

    def __init__(self, source, blocked):
        super().__init__(source)
        self.blocked = blocked

    def _guard(self, key):
        if key == self.blocked:
            raise AssertionError(
                "ATP qualification violation: target proof %s was accessed" % key
            )

    def __getitem__(self, key):
        self._guard(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._guard(key)
        return super().get(key, default)


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("predator8_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def formal_variables(mm, grammar, upto):
    fvar, fallback = {}, {}
    for lab in mm.order[:upto]:
        typ, data = mm.labels[lab]
        if typ == "$f":
            fvar.setdefault(data[1], lab)
            fallback.setdefault(
                data[0], grammar.Tree(None, data[0], (), data[1])
            )
    return fvar, fallback


def write_certificate(path: Path, environment: Path, target: str,
                      statement, proof, winner: str, seed: int):
    text = (
        "$( Predator 8 ATP qualification certificate for %s; "
        "agent %s, seed %d $)\n" % (target, winner, seed)
        + "$[ %s $]\n" % environment.name
        + "chk $p %s $= %s $.\n"
        % (" ".join(statement), " ".join(proof))
    )
    path.write_text(text, encoding="utf-8")


def qualify_target(engine, mm, environment: Path, target: str,
                   output_dir: Path, budget: int, max_depth: int,
                   agents: int, creativity: float, seed: int,
                   opener_cap: int, max_open: int, progress: int):
    if target not in mm.labels or mm.labels[target][0] != "$p":
        return {"target": target, "passed": False, "error": "not a theorem"}

    cut = mm.order.index(target)
    statement = mm.labels[target][1][3]
    # setmm_grammar stores its active rules in module globals.  Build those
    # rules from the strict pre-target prefix so search cannot even inspect a
    # syntax production declared downstream.
    prefix = type("PrefixMM", (), {})()
    prefix.order = mm.order[:cut]
    prefix.labels = mm.labels
    by_tc = engine.G.build_grammar(prefix)
    original_proofs = mm.proofs
    mm.proofs = GuardedProofs(original_proofs, target)
    started = time.perf_counter()
    try:
        index = engine.Index(mm, by_tc, upto=cut, say=None)
        goal = engine.G.parse(statement[1:], "wff", by_tc)
        result, expansions, winner = engine.prove_population(
            goal,
            index,
            budget,
            max_depth,
            agents=agents,
            creativity=creativity,
            seed=seed,
            progress=progress,
            max_open=max_open,
            opener_cap=opener_cap,
        )
    finally:
        mm.proofs = original_proofs

    elapsed = time.perf_counter() - started
    row = {
        "target": target,
        "budget": budget,
        "expansions": expansions,
        "elapsed_seconds": round(elapsed, 6),
        "winner": winner,
        "target_proof_access": False,
    }
    if result is None:
        row.update(passed=False, outcome="unknown_under_bounds")
        return row

    root, substitution = result
    fvar, fallback = formal_variables(mm, engine.G, cut)
    proof = root.emit(substitution, fvar, fallback)
    cert = output_dir / ("qualification_%s.mm" % target)
    write_certificate(
        cert, environment, target, statement, proof, winner, seed
    )
    row["certificate"] = str(cert)
    row["proof_steps"] = len(proof)

    cv = subprocess.run(
        [
            sys.executable,
            str(ROOT / "predator8_external_cv.py"),
            str(environment),
            "--target",
            target,
            "--certificate",
            str(cert),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    row["external_cv_exit"] = cv.returncode
    row["external_cv_output"] = (cv.stdout + cv.stderr).strip()
    row["passed"] = cv.returncode == 0 and "EXTERNAL CV: OK" in cv.stdout
    row["outcome"] = "verified_proof" if row["passed"] else "protocol_failure"
    return row


def negative_control(engine):
    """No legal logical assertion can prove conjunction in the toy system."""
    mm = engine.MM()
    mm.read(engine.Toks(engine.SELFTEST))
    by_tc = engine.G.build_grammar(mm)
    index = engine.Index(mm, by_tc)
    goal = engine.G.parse("( ph /\\ ph )".split(), "wff", by_tc)
    result, expansions = engine.prove(
        goal, index, budget=250, max_depth=6, progress=0
    )
    return {
        "name": "toy_unproved_conjunction",
        "passed": result is None,
        "expansions": expansions,
        "outcome": "unknown_under_bounds" if result is None else "unexpected_candidate",
    }


def write_reports(output_dir: Path, metadata, positive, negative):
    payload = {"metadata": metadata, "positive": positive, "negative": negative}
    json_path = output_dir / "Predator_8_ATP_QUALIFICATION.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    all_pass = all(r["passed"] for r in positive) and negative["passed"]
    lines = [
        "# Predator 8 ATP qualification",
        "",
        "Overall result: **%s**" % ("PASS" if all_pass else "NOT YET PASSED"),
        "",
        "The positive controls denied search access to each target's stored proof. "
        "Every claimed success was checked in a fresh process that imported the "
        "Metamath verifier but no Predator search code.",
        "",
        "| Target | Outcome | Expansions | Proof steps | External CV |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in positive:
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (
                row["target"],
                row.get("outcome", "error"),
                row.get("expansions", "-"),
                row.get("proof_steps", "-"),
                "PASS" if row.get("passed") else "FAIL/NOT FOUND",
            )
        )
    lines.extend(
        [
            "",
            "Negative control: **%s** after %s expansions; the engine returned `%s` "
            "and emitted no certificate."
            % (
                "PASS" if negative["passed"] else "FAIL",
                negative["expansions"],
                negative["outcome"],
            ),
            "",
            "Passing this suite establishes certificate-producing ATP behavior on "
            "the tested controls. It does not establish completeness, optimality, "
            "or success on every theorem.",
            "",
        ]
    )
    md_path = output_dir / "Predator_8_ATP_QUALIFICATION.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path, all_pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("environment", nargs="?", default="set.mm")
    ap.add_argument(
        "--engine", default="Predator_8.001_FROZEN.py", help="frozen engine"
    )
    ap.add_argument("--targets", nargs="+", default=["axin1", "idd"])
    ap.add_argument("--budget", type=int, default=5000, help="per-target budget")
    ap.add_argument("--max-depth", type=int, default=10)
    ap.add_argument("--agents", type=int, default=4)
    ap.add_argument("--creativity", type=float, default=0.55)
    ap.add_argument("--seed", type=int, default=881)
    ap.add_argument("--opener-cap", type=int, default=48)
    ap.add_argument("--max-open", type=int, default=6)
    ap.add_argument("--progress", type=int, default=0)
    ap.add_argument("--output-dir", default="qualification_artifacts")
    a = ap.parse_args()

    environment = Path(a.environment).resolve()
    engine_path = Path(a.engine).resolve()
    output_dir = Path(a.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = load_engine(engine_path)
    mm = engine.load(str(environment), say=lambda s: print(s))
    metadata = {
        "engine": str(engine_path),
        "engine_sha256": sha256(engine_path),
        "engine_version": engine.VERSION,
        "environment": str(environment),
        "environment_sha256": sha256(environment),
        "budget_per_target": a.budget,
        "creativity": a.creativity,
        "seed": a.seed,
    }

    positive = []
    for target in a.targets:
        print("\nqualifying %s..." % target)
        row = qualify_target(
            engine,
            mm,
            environment,
            target,
            output_dir,
            a.budget,
            a.max_depth,
            a.agents,
            a.creativity,
            a.seed,
            a.opener_cap,
            a.max_open,
            a.progress,
        )
        positive.append(row)
        print("  %s" % row.get("outcome", row.get("error", "error")))

    negative = negative_control(engine)
    json_path, md_path, all_pass = write_reports(
        output_dir, metadata, positive, negative
    )
    print("\nreport: %s" % md_path)
    print("data:   %s" % json_path)
    print("overall: %s" % ("PASS" if all_pass else "NOT YET PASSED"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
