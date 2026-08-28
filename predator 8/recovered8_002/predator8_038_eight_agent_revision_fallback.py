#!/usr/bin/env python3
"""Predator 8.038: universal thresholded revision fallback for eight AMLD agents.

Scientific rule
---------------
Each agent a in {P1,P2,R1,R2,I1,I2,C1,C2} has an ordinary
optimality-seeking update Phi_a and a trajectory diagnostic D_a(T_a).

    next(c_a) = Phi_a(T_a, c_a)   if D_a(T_a) <= tau_a
                c_a^{-1}          if D_a(T_a) >  tau_a

Every knob is required to belong to a group.  A revision therefore means the
full coordinatewise group inverse, not an arbitrary perturbation.  For the
current logit-addition creativity coordinates on (0,1), inverse(c)=1-c.

This file is deliberately controller-only: it is safe to prepare before the
8.037 result is known.  The next experiment can bind each agent's existing
optimizer and trajectory diagnostic without changing verifier semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Mapping, MutableMapping, Sequence, Tuple

AGENTS: Tuple[str, ...] = (
    "P1", "P2", "R1", "R2", "I1", "I2", "C1", "C2",
)

Vector = Mapping[str, float]
MutableVector = Dict[str, float]
Trajectory = Sequence[object]
Optimizer = Callable[[Trajectory, Vector], MutableVector]
Diagnostic = Callable[[Trajectory], float]
Inverse = Callable[[float], float]


def logit_group_inverse(c: float) -> float:
    """Inverse in ((0,1), logit-addition): c^{-1}=1-c."""
    c = float(c)
    if not 0.0 < c < 1.0:
        raise ValueError("logit-group coordinate must lie in (0,1)")
    return 1.0 - c


@dataclass(frozen=True)
class GroupCoordinate:
    """One knob together with the inverse operation of its group."""

    name: str
    inverse: Inverse = logit_group_inverse

    def invert(self, value: float) -> float:
        return float(self.inverse(float(value)))


@dataclass
class AgentRevisionPolicy:
    """Thresholded optimization/revision policy for one agent."""

    agent: str
    threshold: float
    diagnostic: Diagnostic
    optimizer: Optimizer
    groups: Mapping[str, GroupCoordinate]
    min_post_revision_observations: int = 1
    _observations_since_revision: int = field(default=10**9, init=False)

    def __post_init__(self) -> None:
        if self.agent not in AGENTS:
            raise ValueError(f"unknown eight-agent role: {self.agent}")
        if not self.groups:
            raise ValueError("every agent must expose at least one grouped knob")

    def validate_vector(self, vector: Vector) -> None:
        if set(vector) != set(self.groups):
            missing = sorted(set(self.groups) - set(vector))
            extra = sorted(set(vector) - set(self.groups))
            raise ValueError(
                f"{self.agent}: knob/group mismatch; missing={missing}, extra={extra}"
            )

    def inverse_vector(self, vector: Vector) -> MutableVector:
        """Full revision: invert every knob in its own group."""
        self.validate_vector(vector)
        return {
            key: self.groups[key].invert(float(vector[key]))
            for key in vector
        }

    def step(self, trajectory: Trajectory, vector: Vector) -> tuple[MutableVector, dict]:
        """Choose ordinary optimization or full inverse revision.

        A one-observation refractory period prevents immediate c <-> c^{-1}
        ping-pong before the revised state has actually been evaluated.
        """
        self.validate_vector(vector)
        d = float(self.diagnostic(trajectory))
        if d != d:  # NaN guard
            raise ValueError(f"{self.agent}: diagnostic D(T) returned NaN")

        can_revise = self._observations_since_revision >= self.min_post_revision_observations
        if d > float(self.threshold) and can_revise:
            nxt = self.inverse_vector(vector)
            mode = "revision"
            self._observations_since_revision = 0
        else:
            nxt = dict(self.optimizer(trajectory, vector))
            self.validate_vector(nxt)
            mode = "optimization"
            self._observations_since_revision += 1

        return nxt, {
            "agent": self.agent,
            "D(T)": d,
            "threshold": float(self.threshold),
            "mode": mode,
            "can_revise": can_revise,
        }


@dataclass
class EightAgentRevisionFallback:
    """Federation wrapper requiring revision fallback on all eight agents."""

    policies: Mapping[str, AgentRevisionPolicy]

    def __post_init__(self) -> None:
        supplied = set(self.policies)
        required = set(AGENTS)
        if supplied != required:
            raise ValueError(
                "revision fallback must be installed on all eight agents; "
                f"missing={sorted(required-supplied)}, extra={sorted(supplied-required)}"
            )
        for name, policy in self.policies.items():
            if name != policy.agent:
                raise ValueError(f"policy key {name!r} does not match agent {policy.agent!r}")

    def step_agent(self, agent: str, trajectory: Trajectory, vector: Vector):
        return self.policies[agent].step(trajectory, vector)

    def step_all(
        self,
        trajectories: Mapping[str, Trajectory],
        vectors: Mapping[str, Vector],
    ) -> tuple[Dict[str, MutableVector], Dict[str, dict]]:
        if set(trajectories) != set(AGENTS) or set(vectors) != set(AGENTS):
            raise ValueError("step_all requires trajectories and vectors for all eight agents")
        next_vectors: Dict[str, MutableVector] = {}
        decisions: Dict[str, dict] = {}
        for agent in AGENTS:
            next_vectors[agent], decisions[agent] = self.step_agent(
                agent, trajectories[agent], vectors[agent]
            )
        return next_vectors, decisions
