#!/usr/bin/env python3
"""Independent certificate checker for Predator 8 qualification.

This process imports the Metamath checker, but no Predator search code.  It
loads the formal environment, extracts the proof-token sequence from a
Predator certificate, attaches that sequence to a fresh theorem label with the
target's statement and mandatory frame, and asks the Metamath stack machine to
verify it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metamath import MM, MMError, load


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_proof_tokens(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="strict") as f:
        source = f.read()
    matches = re.findall(r"\$=\s*(.*?)\s*\$\.", source, flags=re.S)
    if len(matches) != 1:
        raise ValueError(
            "%s must contain exactly one `$= ... $.` proof, found %d"
            % (path, len(matches))
        )
    proof = matches[0].split()
    if not proof:
        raise ValueError("%s contains an empty proof" % path)
    return proof


def verify_external(environment: str, target: str, certificate: str) -> str:
    mm = load(environment, say=lambda _s: None)
    if target not in mm.labels or mm.labels[target][0] != "$p":
        raise ValueError("target %s is not a theorem in %s" % (target, environment))

    proof = read_proof_tokens(certificate)
    # Loading the whole database lets us reconstruct the target's mandatory
    # frame, but the synthetic check label would otherwise be able to cite
    # downstream theorems.  Restore normal Metamath declaration-order rules
    # explicitly: every certificate token must precede the target.
    cut = mm.order.index(target)
    allowed = set(mm.order[:cut])
    downstream = sorted({step for step in proof if step not in allowed})
    if downstream:
        raise ValueError(
            "certificate uses labels not declared before %s: %s"
            % (target, ", ".join(downstream[:12]))
        )

    check_label = "__predator8_external_check__"
    target_data = mm.labels[target][1]
    mm.labels[check_label] = ("$p", target_data)
    mm.proofs[check_label] = proof
    mm.scope_dvs[check_label] = mm.scope_dvs.get(target, target_data[0])
    return mm.verify(check_label)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Check a Predator certificate without importing Predator"
    )
    ap.add_argument("environment", help="frozen Metamath database, e.g. set.mm")
    ap.add_argument("--target", required=True, help="target theorem label")
    ap.add_argument("--certificate", required=True, help="candidate .mm file")
    a = ap.parse_args()

    try:
        verdict = verify_external(a.environment, a.target, a.certificate)
    except (MMError, OSError, ValueError) as e:
        print("EXTERNAL CV: FAILED -- %s" % e)
        return 2

    print("EXTERNAL CV: %s" % verdict.upper())
    print("environment sha256: %s" % sha256(a.environment))
    print("certificate sha256: %s" % sha256(a.certificate))
    return 0 if verdict == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
