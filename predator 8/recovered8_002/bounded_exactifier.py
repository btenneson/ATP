#!/usr/bin/env python3
"""Bounded exhaustive shell exactification for unit-cost settlement graphs.

A Predator integration must pass an `all_successors` callback that enumerates
EVERY legal proof successor in the exact graph used by the theorem. Pruned,
opener-capped, or policy-restricted successors are not enough unless the claimed
horizon is explicitly the corresponding restricted horizon.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Generic, Hashable, Iterable, Optional, Sequence, TypeVar

from settlement_authority import AuthorityDecision, HorizonInterval

T = TypeVar("T")


@dataclass(frozen=True)
class ProbeResult(Generic[T]):
    exact_h: Optional[int]
    lower_bound: int
    checked_through_depth: int
    expanded: int
    complete_to_requested_depth: bool
    witness: Optional[T]
    evidence: str

    def interval(self) -> HorizonInterval:
        if self.exact_h is not None:
            return HorizonInterval(
                float(self.exact_h), float(self.exact_h), self.evidence
            )
        return HorizonInterval(float(self.lower_bound), math.inf, self.evidence)


def bounded_bfs_exactify(
    start: T,
    *,
    all_successors: Callable[[T], Iterable[T]],
    is_settled: Callable[[T], bool],
    key: Callable[[T], Hashable],
    max_depth: int,
    completeness_evidence: str,
    max_expansions: Optional[int] = None,
) -> ProbeResult[T]:
    """Exhaustively inspect settlement shells through `max_depth`.

    If settlement first appears in BFS layer r, exact H=r.
    If every layer through m=max_depth is exhausted with no settlement, H>=m+1.
    If an expansion cap interrupts the probe after fully checking layer d, only
    H>=d+1 is certified.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be nonnegative")
    if max_expansions is not None and max_expansions < 0:
        raise ValueError("max_expansions must be nonnegative")
    if not completeness_evidence or not completeness_evidence.strip():
        raise ValueError(
            "exactification requires explicit successor-completeness evidence"
        )

    seen = {key(start)}
    layer = [start]
    expanded = 0

    for depth in range(max_depth + 1):
        for node in layer:
            if is_settled(node):
                return ProbeResult(
                    exact_h=depth,
                    lower_bound=depth,
                    checked_through_depth=depth,
                    expanded=expanded,
                    complete_to_requested_depth=True,
                    witness=node,
                    evidence=(
                        f"complete BFS first settlement at depth {depth}; "
                        + completeness_evidence
                    ),
                )

        if depth == max_depth:
            return ProbeResult(
                exact_h=None,
                lower_bound=depth + 1,
                checked_through_depth=depth,
                expanded=expanded,
                complete_to_requested_depth=True,
                witness=None,
                evidence=(
                    f"complete BFS exhausted settlement-free shells 0..{depth}; "
                    + completeness_evidence
                ),
            )

        if max_expansions is not None and expanded + len(layer) > max_expansions:
            return ProbeResult(
                exact_h=None,
                lower_bound=depth + 1,
                checked_through_depth=depth,
                expanded=expanded,
                complete_to_requested_depth=False,
                witness=None,
                evidence=(
                    f"BFS interrupted after fully checking shell {depth}; "
                    f"therefore H>={depth + 1}; " + completeness_evidence
                ),
            )

        nxt = []
        for node in layer:
            expanded += 1
            for child in all_successors(node):
                k = key(child)
                if k in seen:
                    continue
                seen.add(k)
                nxt.append(child)
        layer = nxt

        if not layer:
            return ProbeResult(
                exact_h=None,
                lower_bound=depth + 1,
                checked_through_depth=depth,
                expanded=expanded,
                complete_to_requested_depth=True,
                witness=None,
                evidence=(
                    "complete BFS exhausted reachable component with no settlement "
                    f"after shell {depth}; H is unreachable/infinite in this graph; "
                    + completeness_evidence
                ),
            )

    raise AssertionError("unreachable")


@dataclass(frozen=True)
class IntervalSuccessor:
    key: str
    interval: HorizonInterval


def interval_optimal_lock(successors: Sequence[IntervalSuccessor]) -> AuthorityDecision:
    """Certify an optimal successor using interval dominance.

    If U_i <= L_j for every competing j, successor i is guaranteed to minimize
    true H (ties are allowed when equality occurs). In a reachable unit-cost
    proof graph, any such minimizing successor is geodesic.
    """
    if not successors:
        return AuthorityDecision(1, "INTERVAL-LOCK-DENIED", "no successors")

    chosen = []
    for i, s in enumerate(successors):
        if math.isinf(s.interval.upper):
            continue
        others = [
            t.interval.lower for j, t in enumerate(successors) if j != i
        ]
        if not others or s.interval.upper <= min(others):
            chosen.append(s.key)

    if not chosen:
        return AuthorityDecision(
            1,
            "INTERVAL-LOCK-DENIED",
            "sound successor intervals overlap too much to certify an H-minimizer",
        )

    return AuthorityDecision(
        2,
        "INTERVAL-OPTIMAL-LOCK",
        "interval dominance U_i <= every competing L_j certifies an H-minimizing successor",
        selected_keys=tuple(chosen),
    )
