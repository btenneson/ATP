from __future__ import annotations

from dataclasses import dataclass
import math

from .agents import AgentProfile


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class ProfessorEvidence:
    """Evidence from which a Professor grade can be assembled.

    The evidence deliberately keeps the components separate. DATA MIND 3.1
    does not silently freeze a universal scalar grading formula before the next
    preregistered experiment.
    """

    verified_structure: float
    target_relevance: float
    repair_horizon: float | None = None
    repair_half_distance: float | None = None
    local_density: float | None = None
    landscape_quality: float | None = None
    current_partial_credit: float | None = None
    previous_partial_credit: float | None = None
    resource_delta: float | None = None
    uncertainty: float | None = None


@dataclass(frozen=True)
class ProfessorGrade:
    verified_structure: float
    repair_proximity: float | None
    local_density: float | None
    landscape_quality: float | None
    target_relevance: float
    marginal_credit_per_resource: float | None
    uncertainty: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "verified_structure": self.verified_structure,
            "repair_proximity": self.repair_proximity,
            "local_density": self.local_density,
            "landscape_quality": self.landscape_quality,
            "target_relevance": self.target_relevance,
            "marginal_credit_per_resource": self.marginal_credit_per_resource,
            "uncertainty": self.uncertainty,
        }

    def scalarize(self, weights: dict[str, float]) -> float:
        """Explicit opt-in scalarization for a later frozen experiment.

        There are intentionally no default weights. Missing/None components are
        ignored and the supplied nonnegative weights are renormalized.
        """

        values = self.to_dict()
        total = 0.0
        mass = 0.0
        for key, weight in weights.items():
            if weight < 0:
                raise ValueError("Professor scalarization weights must be nonnegative")
            value = values.get(key)
            if value is None or weight == 0:
                continue
            total += weight * float(value)
            mass += weight
        if mass <= 0:
            raise ValueError("no graded component received positive weight")
        return total / mass


class Professor:
    """Advisory grader for Professor-facing DATA MIND agents.

    Professor evaluates search progress; it does not choose the next action and
    cannot certify mathematics.
    """

    @staticmethod
    def grade(evidence: ProfessorEvidence) -> ProfessorGrade:
        proximity: float | None = None
        if evidence.repair_horizon is not None:
            h = evidence.repair_half_distance
            if h is not None and h > 0:
                # Half-distance form: one h of repair distance halves proximity.
                proximity = 2.0 ** (-max(0.0, evidence.repair_horizon) / h)
            elif evidence.repair_horizon == 0:
                proximity = 1.0

        marginal: float | None = None
        if (
            evidence.current_partial_credit is not None
            and evidence.previous_partial_credit is not None
            and evidence.resource_delta is not None
            and evidence.resource_delta > 0
        ):
            marginal = (
                evidence.current_partial_credit - evidence.previous_partial_credit
            ) / evidence.resource_delta

        return ProfessorGrade(
            verified_structure=_clip01(evidence.verified_structure),
            repair_proximity=proximity,
            local_density=(None if evidence.local_density is None else _clip01(evidence.local_density)),
            landscape_quality=(None if evidence.landscape_quality is None else _clip01(evidence.landscape_quality)),
            target_relevance=_clip01(evidence.target_relevance),
            marginal_credit_per_resource=marginal,
            uncertainty=(None if evidence.uncertainty is None else max(0.0, float(evidence.uncertainty))),
        )

    @staticmethod
    def may_address(agent: AgentProfile) -> bool:
        """Initial 3.1 communication contract: only the facing member is coached."""

        return agent.professor_facing

    def deliver(self, agent: AgentProfile, evidence: ProfessorEvidence) -> ProfessorGrade:
        if not self.may_address(agent):
            raise PermissionError(
                f"{agent.name} is the protected independent partner lane; "
                "Professor communication is disabled by the current 3.1 contract"
            )
        return self.grade(evidence)
