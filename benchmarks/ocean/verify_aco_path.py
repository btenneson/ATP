#!/usr/bin/env python3
"""Independent checker for an ACO Ocean proof chain.

This checker does not import the ACO solver.  It re-parses the benchmark file
and verifies the emitted chain directly against the declared start, goal, and
implication axioms.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

START_RE = re.compile(r"^fof\(start,axiom,p\(n(\d+)\)\)\.$")
EDGE_RE = re.compile(r"^fof\((e\d+),axiom,\(p\(n(\d+)\) => p\(n(\d+)\)\)\)\.$")
GOAL_RE = re.compile(r"^fof\(goal,conjecture,p\(n(\d+)\)\)\.$")


def parse_problem(path: Path):
    source = target = None
    edges = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = START_RE.match(line)
        if m:
            source = int(m.group(1))
            continue
        m = EDGE_RE.match(line)
        if m:
            lab, u, v = m.group(1), int(m.group(2)), int(m.group(3))
            if lab in edges:
                raise ValueError(f"duplicate edge label {lab}")
            edges[lab] = (u, v)
            continue
        m = GOAL_RE.match(line)
        if m:
            target = int(m.group(1))
    if source is None or target is None:
        raise ValueError("missing start or goal")
    return source, target, edges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("problem", type=Path)
    ap.add_argument("path_json", type=Path)
    ap.add_argument("--expected-length", type=int)
    args = ap.parse_args()

    source, target, edges = parse_problem(args.problem)
    rec = json.loads(args.path_json.read_text(encoding="utf-8"))
    nodes = rec.get("nodes")
    labels = rec.get("edges")

    if not isinstance(nodes, list) or not isinstance(labels, list):
        raise SystemExit("FAIL: malformed path record")
    if not nodes or nodes[0] != source:
        raise SystemExit("FAIL: chain does not begin at declared source")
    if nodes[-1] != target:
        raise SystemExit("FAIL: chain does not end at declared goal")
    if len(labels) != len(nodes) - 1:
        raise SystemExit("FAIL: edge/node count mismatch")

    for i, lab in enumerate(labels):
        if lab not in edges:
            raise SystemExit(f"FAIL: undeclared implication axiom {lab}")
        if edges[lab] != (nodes[i], nodes[i + 1]):
            raise SystemExit(
                f"FAIL: {lab} is {edges[lab]}, not {(nodes[i], nodes[i + 1])}"
            )

    if args.expected_length is not None and len(labels) != args.expected_length:
        raise SystemExit(
            f"FAIL: verified chain length {len(labels)} != expected {args.expected_length}"
        )

    print(f"VERIFIED chain source=n{source} target=n{target} steps={len(labels)}")


if __name__ == "__main__":
    main()
