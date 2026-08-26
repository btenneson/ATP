#!/usr/bin/env python3
"""Blind-safe launcher for Predator 8.016.

This overrides only ProbeContext.closed_verifies so a local exactification probe
never copies or reads the stored target proof.  It verifies only the newly
emitted candidate against the preloaded assertion frames.
"""
from __future__ import annotations

import predator8_016_prcom_exactify as X


def _blind_closed_verifies(self, node) -> bool:
    if node.goals:
        return False
    try:
        root, sub = self._reconstruct(node)
        if root is None:
            return False
        proof = root.emit(sub, self.fvar, self.fallback)
        E = self.E
        check = E.MM()
        check.labels = dict(self.mm.labels)
        check.order = list(self.mm.order)
        check.proofs = {}  # critical blind boundary: never copy target/stored proofs
        check.constants, check.variables = self.mm.constants, self.mm.variables
        check.scope_dvs = dict(self.mm.scope_dvs)
        check.labels["__p8_016_probe__"] = ("$p", self.target_data)
        check.proofs["__p8_016_probe__"] = proof
        check.scope_dvs["__p8_016_probe__"] = self.target_data[0]
        return check.verify("__p8_016_probe__") == "ok"
    except Exception:
        return False


X.ProbeContext.closed_verifies = _blind_closed_verifies

if __name__ == "__main__":
    raise SystemExit(X.main())
