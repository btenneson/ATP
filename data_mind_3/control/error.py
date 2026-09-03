from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ErrorVector:
    branch: float
    frontier: float
    drift: float
    stagnation: float
    resource: float
    progress: float

    def clipped(self) -> "ErrorVector":
        def c(x: float) -> float:
            return max(0.0, min(1.0, float(x)))
        return ErrorVector(*(c(v) for v in asdict(self).values()))

    def to_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


def objective(e: ErrorVector) -> float:
    """Dense search-control objective; proof validity remains external.

    Lower is better.  This objective only guides search behavior and never
    certifies a theorem.  The independent verifier remains the sole proof
    authority.
    """

    e = e.clipped()
    return (
        0.28 * e.branch
        + 0.24 * e.frontier
        + 0.20 * e.drift
        + 0.12 * e.stagnation
        + 0.06 * e.resource
        + 0.10 * e.progress
    )
