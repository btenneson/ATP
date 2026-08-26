#!/usr/bin/env python3
"""Implementation adapter between Predator proof states and settlement authority.

The adapter deliberately provides only bounds that are justified by existing
proof-state facts. It does not treat h_hat as evidence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from settlement_authority import (
    AuthorityDecision,
    HorizonInterval,
    SuccessorAssessment,
    geodesic_lock,
    heuristic_proximity,
    open_goal_lower_bound,
    shell_authority,
    verified_route_upper_bound,
)


@dataclass(frozen=True)
class BoundEvidence:
    open_goals: int
    verified_remaining_edges: Optional[int] = None
    accepted: bool = False
    note: str = ""


def interval_from_evidence(ev: BoundEvidence) -> Optional[HorizonInterval]:
    """Construct the strongest currently justified interval from proof facts."""
    if ev.accepted:
        return HorizonInterval(
            0.0, 0.0, ev.note or "verifier-accepted ACCEPT state"
        )

    lower = float(open_goal_lower_bound(ev.open_goals, accepted=False))
    if ev.verified_remaining_edges is None:
        return HorizonInterval(
            lower,
            math.inf,
            ev.note or f"open-goal theorem: H>={int(lower)}",
        )

    upper = float(verified_route_upper_bound(ev.verified_remaining_edges))
    if upper < lower:
        raise ValueError(
            "inconsistent evidence: verified route upper bound is below open-goal lower bound"
        )
    return HorizonInterval(
        lower,
        upper,
        ev.note
        or (
            f"open-goal lower bound H>={int(lower)} plus explicit verified "
            f"completion route H<={int(upper)}"
        ),
    )


def assess_state(
    h_hat: float, ev: Optional[BoundEvidence] = None
) -> AuthorityDecision:
    """Return Stage 1 or Stage 3 authority for one current state."""
    interval = interval_from_evidence(ev) if ev is not None else None
    return shell_authority(h_hat, interval)


def assess_successors(
    items: Sequence[tuple[str, float, Optional[BoundEvidence]]],
) -> AuthorityDecision:
    """Return Stage 2 only if all competing successors satisfy the theorem gate."""
    ss = []
    for key, h_hat, ev in items:
        interval = interval_from_evidence(ev) if ev is not None else None
        ss.append(SuccessorAssessment(key, h_hat, interval))
    return geodesic_lock(ss)


def stage1_alarm(h_hat: float, threshold: float = 2.0) -> AuthorityDecision:
    return heuristic_proximity(h_hat, threshold=threshold)
