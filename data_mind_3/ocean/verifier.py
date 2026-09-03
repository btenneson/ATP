from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_START = re.compile(r"fof\(start,axiom,p\(n(\d+)\)\)\.")
_EDGE = re.compile(r"fof\(e\d+,axiom,\(p\(n(\d+)\)\s*=>\s*p\(n(\d+)\)\)\)\.")
_GOAL = re.compile(r"fof\(goal,conjecture,p\(n(\d+)\)\)\.")
_DEPTH = re.compile(r"Ocean benchmark L\*=(\d+)")


@dataclass(frozen=True)
class OceanVerification:
    accepted: bool
    reason: str
    transitions: int
    declared_depth: int | None
    source: int | None
    target: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "transitions": self.transitions,
            "declared_depth": self.declared_depth,
            "source": self.source,
            "target": self.target,
        }


def verify_ocean_certificate(problem_path: Path, path: tuple[int, ...]) -> OceanVerification:
    """Independently check an Ocean path against the serialized TPTP input.

    This verifier deliberately reparses the problem instead of trusting the
    solver's graph object.  It checks only certificate facts: endpoints, every
    edge, and (when present) the declared benchmark depth.
    """

    source: int | None = None
    target: int | None = None
    declared_depth: int | None = None
    edges: set[tuple[int, int]] = set()

    for raw in problem_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = _DEPTH.search(line)
        if m:
            declared_depth = int(m.group(1))
        m = _START.fullmatch(line)
        if m:
            source = int(m.group(1))
            continue
        m = _EDGE.fullmatch(line)
        if m:
            edges.add((int(m.group(1)), int(m.group(2))))
            continue
        m = _GOAL.fullmatch(line)
        if m:
            target = int(m.group(1))

    transitions = max(0, len(path) - 1)
    if source is None or target is None:
        return OceanVerification(False, "malformed_problem", transitions, declared_depth, source, target)
    if not path:
        return OceanVerification(False, "empty_certificate", 0, declared_depth, source, target)
    if path[0] != source:
        return OceanVerification(False, "wrong_source", transitions, declared_depth, source, target)
    if path[-1] != target:
        return OceanVerification(False, "wrong_target", transitions, declared_depth, source, target)
    for u, v in zip(path, path[1:]):
        if (u, v) not in edges:
            return OceanVerification(False, f"missing_edge:{u}->{v}", transitions, declared_depth, source, target)
    if declared_depth is not None and transitions != declared_depth:
        return OceanVerification(False, "certificate_depth_mismatch", transitions, declared_depth, source, target)
    return OceanVerification(True, "verified_path", transitions, declared_depth, source, target)
