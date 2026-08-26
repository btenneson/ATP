#!/usr/bin/env python3
"""Verifier-safe settlement authority gates for Predator.

This module implements the mathematical boundary between:

Stage 1: heuristic proximity signals (may steer search only),
Stage 2: certified geodesic lock (requires sound local <1/2 error bounds),
Stage 3: certified zero candidate (requires a sound shell/error certificate).

The module NEVER manufactures soundness. Interval bounds are accepted only with
an explicit evidence string supplied by the caller. In production that evidence
must come from a separately justified bound/certificate mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence

HALF = 0.5


@dataclass(frozen=True)
class HorizonInterval:
    """A claimed sound interval L <= H <= U for integer-valued H."""

    lower: float
    upper: float
    evidence: str

    def __post_init__(self):
        if not self.evidence or not self.evidence.strip():
            raise ValueError("certified interval requires explicit evidence")
        if math.isnan(self.lower) or math.isnan(self.upper):
            raise ValueError("NaN horizon bound")
        if self.lower < 0:
            raise ValueError("H lower bound must be nonnegative")
        if self.upper < self.lower:
            raise ValueError("upper bound below lower bound")


@dataclass(frozen=True)
class SuccessorAssessment:
    key: str
    h_hat: float
    interval: Optional[HorizonInterval] = None


@dataclass(frozen=True)
class AuthorityDecision:
    stage: int
    flag: str
    reason: str
    selected_keys: tuple[str, ...] = ()
    exact_shell: Optional[int] = None


def open_goal_lower_bound(open_goals: int, *, accepted: bool = False) -> int:
    """Rigorous lower bound for the unit logical-edge + verifier-edge graph.

    For a nonaccepted proof state with k open goals, H >= k+1. ACCEPT itself
    has H=0. A closed candidate (k=0) is therefore at least one edge away
    unless it is already represented as ACCEPT.
    """
    if open_goals < 0:
        raise ValueError("open_goals must be nonnegative")
    return 0 if accepted else open_goals + 1


def verified_route_upper_bound(remaining_verified_edges: int) -> int:
    """Upper bound supplied by an explicit verified completion route."""
    if remaining_verified_edges < 0:
        raise ValueError("remaining_verified_edges must be nonnegative")
    return int(remaining_verified_edges)


def unique_integer_shell(interval: HorizonInterval) -> Optional[int]:
    """Return the unique nonnegative integer in [L,U], else None."""
    lo = max(0, math.ceil(interval.lower - 1e-15))
    if math.isinf(interval.upper):
        return None
    hi = math.floor(interval.upper + 1e-15)
    return int(lo) if lo == hi else None


def certifies_half_error(h_hat: float, interval: HorizonInterval) -> bool:
    """Soundly imply |h_hat-H| < 1/2 for every H in the supplied interval."""
    if not math.isfinite(h_hat) or math.isinf(interval.upper):
        return False
    return max(abs(h_hat - interval.lower), abs(h_hat - interval.upper)) < HALF


def heuristic_proximity(h_hat: float, *, threshold: float = 2.0) -> AuthorityDecision:
    """Stage-1 alarm only. Never certifies optimality or settlement."""
    if math.isfinite(h_hat) and h_hat <= threshold:
        return AuthorityDecision(
            1,
            "HEURISTIC-PROXIMITY",
            f"estimated H={h_hat:.6g} <= heuristic threshold {threshold:.6g}; verification/attention only",
        )
    return AuthorityDecision(
        1, "HEURISTIC-NORMAL", "no certified authority; ordinary heuristic search"
    )


def shell_authority(h_hat: float, interval: Optional[HorizonInterval]) -> AuthorityDecision:
    """Stage 1 or 3 shell decision for one state."""
    if interval is None:
        return heuristic_proximity(h_hat)

    shell = unique_integer_shell(interval)
    if shell == 0:
        return AuthorityDecision(
            3,
            "CERTIFIED-ZERO-CANDIDATE",
            f"sound interval [{interval.lower},{interval.upper}] contains only H=0; evidence={interval.evidence}",
            exact_shell=0,
        )

    if h_hat < HALF and certifies_half_error(h_hat, interval):
        return AuthorityDecision(
            3,
            "CERTIFIED-ZERO-CANDIDATE",
            f"sound <1/2 error certificate plus h_hat={h_hat:.6g}<1/2 forces H=0; evidence={interval.evidence}",
            exact_shell=0,
        )

    if shell is not None:
        return AuthorityDecision(
            1,
            "CERTIFIED-SHELL",
            f"exact shell H={shell} is known, but it is not settlement; evidence={interval.evidence}",
            exact_shell=shell,
        )

    return heuristic_proximity(h_hat)


def geodesic_lock(successors: Sequence[SuccessorAssessment]) -> AuthorityDecision:
    """Authorize Stage-2 greedy lock only under the Half-Gap theorem.

    Every competing immediate successor must carry a sound interval certifying
    |h_hat-H|<1/2. If even one competitor is uncertified, lock is denied.
    Ties in estimated H are retained as multiple equally authorized choices.
    """
    if not successors:
        return AuthorityDecision(1, "NO-SUCCESSORS", "no immediate successors to assess")

    missing = [s.key for s in successors if s.interval is None]
    if missing:
        return AuthorityDecision(
            1,
            "GEODESIC-LOCK-DENIED",
            "uncertified successor estimates: " + ",".join(missing),
        )

    bad = [
        s.key
        for s in successors
        if not certifies_half_error(s.h_hat, s.interval)  # type: ignore[arg-type]
    ]
    if bad:
        return AuthorityDecision(
            1,
            "GEODESIC-LOCK-DENIED",
            "<1/2 error not certified for: " + ",".join(bad),
        )

    best = min(s.h_hat for s in successors)
    eps = 1e-12
    chosen = tuple(s.key for s in successors if abs(s.h_hat - best) <= eps)
    evidence = "; ".join(
        f"{s.key}:{s.interval.evidence}" for s in successors if s.interval
    )
    return AuthorityDecision(
        2,
        "GEODESIC-LOCK",
        "all competing immediate successors satisfy certified |h_hat-H|<1/2; "
        "Half-Gap theorem authorizes minimum-h_hat choice; "
        + evidence,
        selected_keys=chosen,
    )


def partial_credit_from_h(h_value: float, h_p: float = 1.0) -> float:
    if h_p <= 0:
        raise ValueError("h_p must be positive")
    if math.isinf(h_value):
        return 0.0
    if h_value < 0:
        raise ValueError("H must be nonnegative")
    return 2.0 ** (-h_value / h_p)


def pc_ratio_half_error_bound(h_p: float = 1.0) -> float:
    """Multiplicative PC error factor corresponding to |h_hat-H|<1/2."""
    if h_p <= 0:
        raise ValueError("h_p must be positive")
    return 2.0 ** (HALF / h_p)
