from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from data_mind_3.control.agents import EscapeAction
from data_mind_3.control.futurebank import FutureProposal
from data_mind_3.control.knobs import CreativityVector


# Milestone-3 whitelist.  Every action is translated only into bounded changes
# to the already-existing 11D creativity controller.  No entry touches proof
# state, verifier acceptance, Sentinel, or BANK.
PROMOTION_DELTAS: Mapping[EscapeAction, Mapping[str, float]] = {
    EscapeAction.REPAIR: {
        "heuristic_weighting": 0.04,
        "goal_selection": 0.03,
        "term_ordering": 0.02,
    },
    EscapeAction.FINE_TUNE: {
        "search_breadth": -0.03,
        "divergence": -0.02,
        "resource_bias": 0.03,
    },
    EscapeAction.BACKFILL_LEMMA: {
        "lemma_direction": 0.05,
        "abstraction_level": 0.03,
        "search_depth": 0.02,
    },
    EscapeAction.SWITCH_BASIN: {
        "divergence": 0.05,
        "search_breadth": 0.03,
        "risk_tolerance": 0.02,
    },
    EscapeAction.FALLBACK: {
        "resource_bias": 0.05,
        "search_breadth": -0.05,
        "divergence": -0.04,
        "risk_tolerance": -0.03,
    },
}


@dataclass(frozen=True)
class PromotionExecution:
    proposal_id: str
    action: EscapeAction
    applied: bool
    reason: str
    creativity_before: dict[str, float]
    creativity_after: dict[str, float]
    deltas: dict[str, float]
    reported_cost: float = 1.0


class PromotionExecutor:
    """Translate whitelisted Dreamer proposals into legal controller moves.

    This is deliberately a control-plane executor.  It has no verifier method,
    no BANK method, no proof-state mutation method, and no authority over
    Sentinel.  `undo` restores the exact pre-promotion CreativityVector.
    """

    def __init__(self, *, max_abs_delta: float = 0.05) -> None:
        if max_abs_delta <= 0:
            raise ValueError("max_abs_delta must be positive")
        self.max_abs_delta = float(max_abs_delta)
        self.history: list[PromotionExecution] = []

    def execute(self, proposal: FutureProposal, controller: object) -> PromotionExecution:
        creativity = getattr(controller, "creativity", None)
        if not isinstance(creativity, CreativityVector):
            record = PromotionExecution(
                proposal_id=proposal.proposal_id,
                action=proposal.action,
                applied=False,
                reason="controller_has_no_creativity_vector",
                creativity_before={},
                creativity_after={},
                deltas={},
            )
            self.history.append(record)
            return record

        raw = PROMOTION_DELTAS.get(proposal.action)
        if raw is None:
            record = PromotionExecution(
                proposal_id=proposal.proposal_id,
                action=proposal.action,
                applied=False,
                reason="action_not_whitelisted",
                creativity_before=creativity.to_dict(),
                creativity_after=creativity.to_dict(),
                deltas={},
            )
            self.history.append(record)
            return record

        deltas = {
            name: max(-self.max_abs_delta, min(self.max_abs_delta, float(delta)))
            for name, delta in raw.items()
        }
        before = creativity
        after = before.moved(**deltas)
        setattr(controller, "creativity", after)
        record = PromotionExecution(
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            applied=True,
            reason="whitelisted_bounded_control_move",
            creativity_before=before.to_dict(),
            creativity_after=after.to_dict(),
            deltas=deltas,
        )
        self.history.append(record)
        return record

    def undo(self, record: PromotionExecution, controller: object) -> None:
        if not record.applied:
            return
        setattr(controller, "creativity", CreativityVector.from_dict(record.creativity_before))
