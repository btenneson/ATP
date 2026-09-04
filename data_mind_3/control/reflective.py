from __future__ import annotations

from typing import Iterable

from .agents import SelfObservation, profile_by_name
from .controller import AdaptiveCreativityController
from .knobs import CreativityVector
from .professor import Professor, ProfessorEvidence, ProfessorGrade


PROFESSOR_SCALARIZATION: dict[str, float] = {
    "verified_structure": 0.50,
    "repair_proximity": 0.50,
}


class ReflectiveP1Controller(AdaptiveCreativityController):
    """Professor-facing, operationally self-aware P1 controller.

    DATA MIND 3.3 preserves the existing Professor semantics while adding an
    explicit *actual-call* cadence.  `Professor.deliver(...)` is never invoked
    merely because `observe_expansion(...)` was called.  Between permitted
    Professor calls P1 reuses the last advisory grade; the verifier remains the
    only source of proof acceptance.
    """

    def __init__(
        self,
        initial: CreativityVector | None = None,
        *,
        interval: int = 16,
        professor_interval: int | None = None,
        experience: Iterable[dict[str, object]] = (),
        child_play: bool = True,
    ) -> None:
        super().__init__(
            initial=initial,
            interval=interval,
            experience=experience,
            child_play=child_play,
        )
        self.profile = profile_by_name("P1")
        if not (self.profile.professor_facing and self.profile.self_aware):
            raise RuntimeError("ReflectiveP1Controller requires Professor-facing self-aware P1")
        self.professor = Professor()
        self.professor_interval = max(4, int(professor_interval or interval))
        self._last_professor_call_expansion: int | None = None
        self._repair_half_distance: float | None = None
        self._previous_raw_partial_credit: float | None = None
        self._previous_observation_expansion: int | None = None
        self._last_professor_grade: ProfessorGrade | None = None
        self._last_professor_credit: float | None = None
        self.professor_updates = 0
        self.self_awareness_updates = 0
        self.actual_professor_calls = 0

    @staticmethod
    def repair_burden_proxy(raw_partial_credit: float) -> float:
        q = max(1e-12, min(1.0, float(raw_partial_credit)))
        return max(0.0, 1.0 / q - 1.0)

    @property
    def repair_half_distance(self) -> float | None:
        return self._repair_half_distance

    @property
    def last_professor_grade(self) -> ProfessorGrade | None:
        return self._last_professor_grade

    @property
    def last_professor_credit(self) -> float | None:
        return self._last_professor_credit

    def _professor_due(self, expansion: int) -> bool:
        if self._last_professor_call_expansion is None:
            return expansion >= self.professor_interval
        return expansion - self._last_professor_call_expansion >= self.professor_interval

    def _grade(
        self,
        *,
        expansion: int,
        raw_partial_credit: float,
        relevance: float,
    ) -> tuple[ProfessorGrade, float, SelfObservation, float]:
        h_hat = self.repair_burden_proxy(raw_partial_credit)
        if self._repair_half_distance is None and h_hat > 0.0:
            self._repair_half_distance = h_hat
        h_p = self._repair_half_distance or 1.0

        resource_delta: float | None = None
        if self._previous_observation_expansion is not None:
            resource_delta = float(max(1, expansion - self._previous_observation_expansion))

        evidence = ProfessorEvidence(
            verified_structure=raw_partial_credit,
            target_relevance=relevance,
            repair_horizon=h_hat,
            repair_half_distance=h_p,
            current_partial_credit=raw_partial_credit,
            previous_partial_credit=self._previous_raw_partial_credit,
            resource_delta=resource_delta,
        )
        grade = self.professor.deliver(self.profile, evidence)
        self.actual_professor_calls += 1
        self._last_professor_call_expansion = expansion
        professor_credit = grade.scalarize(PROFESSOR_SCALARIZATION)
        observation = SelfObservation(
            resource_spent=float(expansion),
            partial_credit=professor_credit,
            previous_partial_credit=self._last_professor_credit,
            resource_delta=resource_delta,
        )

        self._previous_raw_partial_credit = raw_partial_credit
        self._previous_observation_expansion = expansion
        self._last_professor_grade = grade
        self._last_professor_credit = professor_credit
        return grade, professor_credit, observation, h_hat

    def observe_expansion(
        self,
        *,
        expansion: int,
        generated_total: int,
        frontier: int,
        max_frontier: int,
        elapsed: float,
        timeout: float,
        partial_credit: float,
        relevance: float,
        base_config: object,
    ) -> dict[str, object] | None:
        raw_partial_credit = float(partial_credit)
        professor_called = self._professor_due(expansion)
        grade: ProfessorGrade | None = None
        self_observation: SelfObservation | None = None
        h_hat = self.repair_burden_proxy(raw_partial_credit)

        if professor_called:
            grade, professor_credit, self_observation, h_hat = self._grade(
                expansion=expansion,
                raw_partial_credit=raw_partial_credit,
                relevance=relevance,
            )
        else:
            # Reuse the last advisory value between actual Professor calls.  On
            # startup, before the first permitted call, fall back to the locally
            # checked raw partial-credit signal rather than fabricating a grade.
            professor_credit = (
                self._last_professor_credit
                if self._last_professor_credit is not None
                else raw_partial_credit
            )

        event = super().observe_expansion(
            expansion=expansion,
            generated_total=generated_total,
            frontier=frontier,
            max_frontier=max_frontier,
            elapsed=elapsed,
            timeout=timeout,
            partial_credit=professor_credit,
            relevance=relevance,
            base_config=base_config,
        )
        if event is None:
            return None

        professor_event: dict[str, object] = {
            "actor": "Professor",
            "action": "grade_P1" if professor_called else "reuse_cached_grade",
            "expansion": expansion,
            "recipient": "P1",
            "actual_professor_call": professor_called,
            "professor_interval": self.professor_interval,
            "actual_professor_calls_total": self.actual_professor_calls,
            "raw_structural_partial_credit": raw_partial_credit,
            "repair_horizon_proxy": h_hat,
            "repair_half_distance": self._repair_half_distance,
            "grade": grade.to_dict() if grade is not None else (
                self._last_professor_grade.to_dict() if self._last_professor_grade is not None else None
            ),
            "professor_credit": professor_credit,
            "scalarization": dict(PROFESSOR_SCALARIZATION),
            "repair_horizon_semantics": "H_hat=max(0,1/q_raw-1); burden proxy, not exact repair distance",
            "partial_credit_semantics": "locally checked structural proxy; not terminal verifier acceptance",
        }

        if self_observation is None:
            self_observation = SelfObservation(
                resource_spent=float(expansion),
                partial_credit=professor_credit,
                previous_partial_credit=self._last_professor_credit,
                resource_delta=None,
            )
        self_event: dict[str, object] = {
            "actor": "P1",
            "action": "self_observe",
            "expansion": expansion,
            "self_aware": True,
            "resource_spent": self_observation.resource_spent,
            "professor_credit": self_observation.partial_credit,
            "previous_professor_credit": self_observation.previous_partial_credit,
            "resource_delta": self_observation.resource_delta,
            "marginal_credit_per_resource": self_observation.marginal_credit_per_resource,
            "actual_professor_call": professor_called,
        }

        event.update({
            "agent": "P1",
            "professor_credit": professor_credit,
            "professor_grade": professor_event["grade"],
            "actual_professor_call": professor_called,
            "actual_professor_calls_total": self.actual_professor_calls,
            "repair_horizon_proxy": h_hat,
            "repair_half_distance": self._repair_half_distance,
            "self_awareness": self_event,
        })
        self.history.append(professor_event)
        self.history.append(self_event)
        if professor_called:
            self.professor_updates += 1
        self.self_awareness_updates += 1
        return event
