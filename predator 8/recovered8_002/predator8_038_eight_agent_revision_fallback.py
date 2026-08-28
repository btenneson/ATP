#!/usr/bin/env python3
"""Predator 8.038: universal thresholded revision fallback for eight AMLD agents.

For every agent a in {P1,P2,R1,R2,I1,I2,C1,C2}:

    next(c_a) = Phi_a(T_a, c_a)   if D_a(T_a) <= tau_a
                c_a^{-1}          if D_a(T_a) >  tau_a

Every knob must be declared as an element of a group and revision applies the
coordinatewise group inverse. The verifier is a protected invariant:
V(z)=1 for every trajectory state z admitted to the controller. Revision can
change search control, never verification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

AGENTS: Tuple[str, ...] = (
    "P1", "P2", "R1", "R2", "I1", "I2", "C1", "C2",
)
V_REQUIRED = 1

KnobValue = Any
Vector = Mapping[str, KnobValue]
MutableVector = Dict[str, KnobValue]
Trajectory = Sequence[object]
Optimizer = Callable[[Trajectory, Vector], MutableVector]
Diagnostic = Callable[[Trajectory], float]
Inverse = Callable[[KnobValue], KnobValue]
Validator = Callable[[KnobValue], bool]
Compose = Callable[[KnobValue, KnobValue], KnobValue]
Equivalent = Callable[[KnobValue, KnobValue], bool]
Verifier = Callable[[object], int]


def _stable_logistic(x: float) -> float:
    if x >= 0.0:
        e = math.exp(-x)
        return 1.0 / (1.0 + e)
    e = math.exp(x)
    return e / (1.0 + e)


def logit_group_compose(a: KnobValue, b: KnobValue) -> float:
    x, y = float(a), float(b)
    if not (0.0 < x < 1.0 and 0.0 < y < 1.0):
        raise ValueError("logit-group coordinates must lie in (0,1)")
    lx = math.log(x / (1.0 - x))
    ly = math.log(y / (1.0 - y))
    return _stable_logistic(lx + ly)


def logit_group_inverse(c: KnobValue) -> float:
    x = float(c)
    if not 0.0 < x < 1.0:
        raise ValueError("logit-group coordinate must lie in (0,1)")
    return 1.0 - x


@dataclass(frozen=True)
class GroupCoordinate:
    """One knob plus enough structure to check its declared group inverse."""

    name: str
    inverse: Inverse
    compose: Compose
    identity: KnobValue
    validator: Validator
    equivalent: Equivalent = lambda a, b: a == b

    def validate_member(self, value: KnobValue) -> None:
        if not bool(self.validator(value)):
            raise ValueError(f"{self.name}: {value!r} is outside its declared group")

    def invert(self, value: KnobValue) -> KnobValue:
        self.validate_member(value)
        inv = self.inverse(value)
        self.validate_member(inv)
        left = self.compose(value, inv)
        right = self.compose(inv, value)
        if not self.equivalent(left, self.identity):
            raise ValueError(f"{self.name}: x*x^-1 != e")
        if not self.equivalent(right, self.identity):
            raise ValueError(f"{self.name}: x^-1*x != e")
        return inv

    @classmethod
    def logit(cls, name: str) -> "GroupCoordinate":
        return cls(
            name=name,
            inverse=logit_group_inverse,
            compose=logit_group_compose,
            identity=0.5,
            validator=lambda x: 0.0 < float(x) < 1.0,
            equivalent=lambda a, b: math.isclose(
                float(a), float(b), rel_tol=0.0, abs_tol=1e-12
            ),
        )


@dataclass
class AgentRevisionPolicy:
    agent: str
    threshold: float
    diagnostic: Diagnostic
    optimizer: Optimizer
    groups: Mapping[str, GroupCoordinate]
    verifier: Verifier
    min_post_revision_steps: int = 1
    _steps_since_revision: int = field(default=10**9, init=False)

    def __post_init__(self) -> None:
        if self.agent not in AGENTS:
            raise ValueError(f"unknown eight-agent role: {self.agent}")
        if not math.isfinite(float(self.threshold)):
            raise ValueError(f"{self.agent}: threshold must be finite")
        if not self.groups:
            raise ValueError(f"{self.agent}: every knob must have a group")

    def validate_vector(self, vector: Vector) -> None:
        if set(vector) != set(self.groups):
            missing = sorted(set(self.groups) - set(vector))
            extra = sorted(set(vector) - set(self.groups))
            raise ValueError(
                f"{self.agent}: knob/group mismatch; missing={missing}, extra={extra}"
            )
        for key, value in vector.items():
            self.groups[key].validate_member(value)

    def validate_trajectory(self, trajectory: Trajectory) -> None:
        for i, z in enumerate(trajectory):
            v = int(self.verifier(z))
            if v != V_REQUIRED:
                raise ValueError(
                    f"{self.agent}: verifier invariant violated at T[{i}]: V(z)={v}"
                )

    def inverse_vector(self, vector: Vector) -> MutableVector:
        self.validate_vector(vector)
        return {key: self.groups[key].invert(vector[key]) for key in vector}

    def step(self, trajectory: Trajectory, vector: Vector) -> tuple[MutableVector, dict]:
        self.validate_vector(vector)
        self.validate_trajectory(trajectory)
        d = float(self.diagnostic(trajectory))
        if not math.isfinite(d):
            raise ValueError(f"{self.agent}: diagnostic D(T) must be finite")

        can_revise = self._steps_since_revision >= self.min_post_revision_steps
        if d > float(self.threshold) and can_revise:
            nxt = self.inverse_vector(vector)
            mode = "revision"
            self._steps_since_revision = 0
        else:
            nxt = dict(self.optimizer(trajectory, vector))
            self.validate_vector(nxt)
            mode = "optimization"
            self._steps_since_revision += 1

        return nxt, {
            "agent": self.agent,
            "D(T)": d,
            "threshold": float(self.threshold),
            "mode": mode,
            "V": V_REQUIRED,
            "can_revise": can_revise,
        }


@dataclass
class EightAgentRevisionFallback:
    policies: Mapping[str, AgentRevisionPolicy]

    def __post_init__(self) -> None:
        supplied, required = set(self.policies), set(AGENTS)
        if supplied != required:
            raise ValueError(
                "revision fallback must be installed on all eight agents; "
                f"missing={sorted(required-supplied)}, extra={sorted(supplied-required)}"
            )
        for name, policy in self.policies.items():
            if name != policy.agent:
                raise ValueError(
                    f"policy key {name!r} does not match agent {policy.agent!r}"
                )

    def step_agent(self, agent: str, trajectory: Trajectory, vector: Vector):
        if agent not in self.policies:
            raise KeyError(f"unknown agent {agent!r}")
        return self.policies[agent].step(trajectory, vector)

    def step_all(
        self,
        trajectories: Mapping[str, Trajectory],
        vectors: Mapping[str, Vector],
    ) -> tuple[Dict[str, MutableVector], Dict[str, dict]]:
        required = set(AGENTS)
        if set(trajectories) != required or set(vectors) != required:
            raise ValueError(
                "step_all requires trajectories and vectors for all eight agents"
            )
        next_vectors: Dict[str, MutableVector] = {}
        decisions: Dict[str, dict] = {}
        for agent in AGENTS:
            next_vectors[agent], decisions[agent] = self.step_agent(
                agent, trajectories[agent], vectors[agent]
            )
        return next_vectors, decisions
