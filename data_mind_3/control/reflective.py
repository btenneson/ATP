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
    """Professor-facing, operationally self-aware P1 controller for DATA MIND 3.1.

    This controller deliberately distinguishes a measurable repair-*burden proxy*
    from the true transaction-geometric repair horizon.  If q_raw is the current
    locally checked structural partial-credit proxy, define

        H_hat = max(0, 1/q_raw - 1).

    H_hat is exactly the residual weighted obligation burden induced by the
    current DATA MIND Metamath partial-credit formula; it is *not* asserted to be
    the shortest repair distance to a verified proof.

    The first positive H_hat in a run becomes the proof half-distance scale h_P,
    so the initial repair-proximity component is normalized to one half.  The
    preregisterable Professor credit used by P1 is

        PC_prof = 0.5*q_raw + 0.5*2^(-H_hat/h_P).

    Target relevance remains a separate search signal in the inherited successor
    score and is therefore not counted a second time in this scalarization.

    The Professor grades.  P1 owns the control response.  The optional Child is
    still advisory creativity under P1 and receives P1's Professor-mediated
    progress signal through the inherited controller.  Nothing in this class can
    certify a proof or alter verifier acceptance semantics.
    """

    def __init__(
        self,
        initial: CreativityVector | None = None,
        *,
        interval: int = 16,
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
        self._repair_half_distance: float | None = None
        self._previous_raw_partial_credit: float | None = None
        self._previous_observation_expansion: int | None = None
        self._last_professor_grade: ProfessorGrade | None = None
        self._last_professor_credit: float | None = None
        self.professor_updates = 0
        self.self_awareness_updates = 0

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
        grade, professor_credit, self_observation, h_hat = self._grade(
            expansion=expansion,
            raw_partial_credit=raw_partial_credit,
            relevance=relevance,
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
            "action": "grade_P1",
            "expansion": expansion,
            "recipient": "P1",
            "raw_structural_partial_credit": raw_partial_credit,
            "repair_horizon_proxy": h_hat,
            "repair_half_distance": self._repair_half_distance,
            "grade": grade.to_dict(),
            "professor_credit": professor_credit,
            "scalarization": dict(PROFESSOR_SCALARIZATION),
            "repair_horizon_semantics": "H_hat=max(0,1/q_raw-1); burden proxy, not exact repair distance",
            "partial_credit_semantics": "locally checked structural proxy; not terminal verifier acceptance",
        }
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
        }

        # The inherited control snapshot is already in history.  Mutating this
        # dictionary enriches that same recorded snapshot with the advisory
        # grade P1 actually used, while separate Professor/P1 events preserve
        # the role boundary in the Historian.
        event.update({
            "agent": "P1",
            "professor_credit": professor_credit,
            "professor_grade": grade.to_dict(),
            "repair_horizon_proxy": h_hat,
            "repair_half_distance": self._repair_half_distance,
            "self_awareness": self_event,
        })
        self.history.append(professor_event)
        self.history.append(self_event)
        self.professor_updates += 1
        self.self_awareness_updates += 1
        return event
