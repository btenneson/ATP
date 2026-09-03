from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .error import ErrorVector, objective
from .knobs import CreativityVector


@dataclass(frozen=True)
class ControlSnapshot:
    expansion: int
    creativity_before: dict[str, float]
    creativity_after: dict[str, float]
    error: dict[str, float]
    objective: float
    previous_objective: float | None
    generated_per_expansion: float
    effective: dict[str, int | float]

    def to_dict(self) -> dict[str, object]:
        return {
            "actor": "CreativityController",
            "action": "control_update",
            "expansion": self.expansion,
            "creativity_before": self.creativity_before,
            "creativity_after": self.creativity_after,
            "error": self.error,
            "objective": self.objective,
            "previous_objective": self.previous_objective,
            "generated_per_expansion": self.generated_per_expansion,
            "effective": self.effective,
        }


class AdaptiveCreativityController:
    """Transparent bounded feedback for DATA MIND 3.1.

    This is deliberately not a black-box optimizer.  It changes the 11D
    creativity vector in small deterministic steps in response to observable
    search error.  The resulting vector maps to low-level search controls.
    Nothing here can certify a proof.
    """

    def __init__(
        self,
        initial: CreativityVector | None = None,
        *,
        interval: int = 16,
        experience: Iterable[dict[str, object]] = (),
    ) -> None:
        self.interval = max(4, int(interval))
        self.creativity = initial or CreativityVector()
        for row in experience:
            after = row.get("creativity_after") if isinstance(row, dict) else None
            if isinstance(after, dict):
                self.creativity = CreativityVector.from_dict(after)
        self._last_update_expansion = 0
        self._last_generated = 0
        self._previous_objective: float | None = None
        self._best_pc = 0.0
        self._last_improvement_expansion = 0
        self._recent_relevance_sum = 0.0
        self._recent_relevance_n = 0
        self.history: list[dict[str, object]] = []

    @staticmethod
    def relevance(statement: tuple[str, ...], target: tuple[str, ...]) -> float:
        """Generic structural overlap, independent of any target proof."""
        s = set(statement[1:] if statement and statement[0] == "|-" else statement)
        t = set(target[1:] if target and target[0] == "|-" else target)
        if not t:
            return 1.0
        union = s | t
        return len(s & t) / len(union) if union else 1.0

    def choose_goal_index(
        self,
        statements: tuple[tuple[str, ...], ...],
        target: tuple[str, ...],
    ) -> int:
        if not statements or self.creativity.goal_selection <= 0.52:
            return 0
        return max(range(len(statements)), key=lambda i: self.relevance(statements[i], target))

    def effective(self, base: object) -> dict[str, int | float]:
        c = self.creativity

        def scaled(value: int, factor: float, floor: int = 1) -> int:
            return max(floor, int(round(value * max(0.1, factor))))

        breadth_factor = (
            1.0
            + 0.90 * (c.search_breadth - 0.5)
            + 0.30 * (c.divergence - 0.5)
            + 0.20 * (c.risk_tolerance - 0.5)
            - 0.35 * (c.resource_bias - 0.5)
        )
        match_factor = (
            1.0
            + 0.55 * (c.search_breadth - 0.5)
            + 0.55 * (c.risk_tolerance - 0.5)
            - 0.20 * (c.resource_bias - 0.5)
        )
        completion_factor = (
            1.0
            + 0.65 * (c.search_breadth - 0.5)
            + 0.65 * (c.risk_tolerance - 0.5)
            + 0.25 * (c.abstraction_level - 0.5)
            - 0.30 * (c.resource_bias - 0.5)
        )
        depth_factor = 1.0 + 0.75 * (c.search_depth - 0.5)
        term_factor = (
            1.0
            + 0.40 * (c.term_ordering - 0.5)
            + 0.45 * (c.abstraction_level - 0.5)
            + 0.20 * (c.risk_tolerance - 0.5)
        )
        definition_factor = 1.0 + 0.80 * (c.abstraction_level - 0.5)

        return {
            "candidate_cap": scaled(int(getattr(base, "candidate_cap")), breadth_factor, 4),
            "match_cap_per_candidate": scaled(int(getattr(base, "match_cap_per_candidate")), match_factor, 1),
            "free_var_completion_cap": scaled(int(getattr(base, "free_var_completion_cap")), completion_factor, 2),
            "max_depth": scaled(int(getattr(base, "max_depth")), depth_factor, 4),
            "term_limit": scaled(16, term_factor, 4),
            "definition_rounds": max(0, scaled(int(getattr(base, "definition_rounds")), definition_factor, 0)),
            "lemma_direction": c.lemma_direction,
            "heuristic_weighting": c.heuristic_weighting,
            "term_ordering": c.term_ordering,
            "node_selection": c.node_selection,
            "divergence": c.divergence,
        }

    def successor_score(
        self,
        *,
        partial_credit: float,
        relevance: float,
        depth: int,
        open_goals: int,
    ) -> float:
        c = self.creativity
        base = 12.0 * partial_credit - 0.02 * depth - 0.005 * open_goals
        target_bonus = (3.0 + 7.0 * c.heuristic_weighting) * relevance
        drift_penalty = 6.0 * (1.0 - c.divergence) * (1.0 - relevance)
        depth_penalty = 0.025 * depth * (1.0 - c.search_depth)
        guided = base + target_bonus - drift_penalty - depth_penalty
        # node_selection=0 preserves the old score; 1 fully uses guided ranking.
        return (1.0 - c.node_selection) * base + c.node_selection * guided

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
        if partial_credit > self._best_pc + 1e-12:
            self._best_pc = partial_credit
            self._last_improvement_expansion = expansion
        self._recent_relevance_sum += relevance
        self._recent_relevance_n += 1

        if expansion - self._last_update_expansion < self.interval:
            return None

        delta_exp = max(1, expansion - self._last_update_expansion)
        delta_gen = max(0, generated_total - self._last_generated)
        branch_rate = delta_gen / delta_exp
        avg_relevance = self._recent_relevance_sum / max(1, self._recent_relevance_n)

        e = ErrorVector(
            branch=max(0.0, min(1.0, (branch_rate - 96.0) / 512.0)),
            frontier=max(0.0, min(1.0, frontier / max(1, max_frontier))),
            drift=max(0.0, min(1.0, 1.0 - avg_relevance)),
            stagnation=max(
                0.0,
                min(1.0, (expansion - self._last_improvement_expansion) / (4.0 * self.interval)),
            ),
            resource=max(0.0, min(1.0, elapsed / max(1e-9, timeout))),
            progress=max(0.0, min(1.0, 1.0 - self._best_pc)),
        ).clipped()
        j = objective(e)
        before = self.creativity
        deltas: dict[str, float] = {}

        pressure = max(e.branch, e.frontier)
        if pressure > 0.20:
            deltas.update({
                "search_breadth": deltas.get("search_breadth", 0.0) - 0.12 * pressure,
                "risk_tolerance": deltas.get("risk_tolerance", 0.0) - 0.08 * pressure,
                "divergence": deltas.get("divergence", 0.0) - 0.06 * pressure,
                "resource_bias": deltas.get("resource_bias", 0.0) + 0.08 * pressure,
                "search_depth": deltas.get("search_depth", 0.0) + 0.04 * pressure,
                "heuristic_weighting": deltas.get("heuristic_weighting", 0.0) + 0.06 * pressure,
                "node_selection": deltas.get("node_selection", 0.0) + 0.04 * pressure,
            })

        if e.drift > 0.35:
            deltas.update({
                "divergence": deltas.get("divergence", 0.0) - 0.08 * e.drift,
                "lemma_direction": deltas.get("lemma_direction", 0.0) + 0.07 * e.drift,
                "heuristic_weighting": deltas.get("heuristic_weighting", 0.0) + 0.06 * e.drift,
                "term_ordering": deltas.get("term_ordering", 0.0) + 0.03 * e.drift,
                "goal_selection": deltas.get("goal_selection", 0.0) + 0.06 * e.drift,
                "node_selection": deltas.get("node_selection", 0.0) + 0.04 * e.drift,
            })

        # If the search is not under branching pressure but has stopped improving,
        # deliberately loosen creativity rather than collapsing into a narrow beam.
        if e.stagnation > 0.60 and pressure < 0.40:
            deltas.update({
                "search_breadth": deltas.get("search_breadth", 0.0) + 0.06 * e.stagnation,
                "divergence": deltas.get("divergence", 0.0) + 0.07 * e.stagnation,
                "risk_tolerance": deltas.get("risk_tolerance", 0.0) + 0.05 * e.stagnation,
                "abstraction_level": deltas.get("abstraction_level", 0.0) + 0.04 * e.stagnation,
                "lemma_direction": deltas.get("lemma_direction", 0.0) - 0.03 * e.stagnation,
            })

        # Bound every individual move even if several error terms vote together.
        bounded = {k: max(-0.12, min(0.12, v)) for k, v in deltas.items()}
        self.creativity = self.creativity.moved(**bounded)
        effective = self.effective(base_config)
        snap = ControlSnapshot(
            expansion=expansion,
            creativity_before=before.to_dict(),
            creativity_after=self.creativity.to_dict(),
            error=e.to_dict(),
            objective=j,
            previous_objective=self._previous_objective,
            generated_per_expansion=branch_rate,
            effective=effective,
        ).to_dict()
        self.history.append(snap)

        self._previous_objective = j
        self._last_update_expansion = expansion
        self._last_generated = generated_total
        self._recent_relevance_sum = 0.0
        self._recent_relevance_n = 0
        return snap
