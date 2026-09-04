from __future__ import annotations

from dataclasses import dataclass

from data_mind_3.metamath.search import SearchResult
from data_mind_3_3.dreamer import LogicalDreamer
from data_mind_3_3.promotion import PromotionExecutor


@dataclass(frozen=True)
class RunCostAccounting:
    """Transparent accounting, not a claim that unlike operations have equal CPU cost.

    Wall time and search expansions remain primary physical/search measures.
    `accounted_units` is an explicitly declared normalized bookkeeping sum used
    to ensure advisory work is not silently treated as free.
    """

    search_expansions: int
    wall_time_s: float
    oracle_calls: int
    oracle_reported_cost: float
    dreamer_proposals: int
    dreamer_synthesis_cost: float
    promotions_granted: int
    promotion_executions: int
    promotion_reported_cost: float
    professor_actual_calls: int
    professor_reported_cost: float
    accounted_units: float

    def to_dict(self) -> dict[str, int | float]:
        return {
            "search_expansions": self.search_expansions,
            "wall_time_s": self.wall_time_s,
            "oracle_calls": self.oracle_calls,
            "oracle_reported_cost": self.oracle_reported_cost,
            "dreamer_proposals": self.dreamer_proposals,
            "dreamer_synthesis_cost": self.dreamer_synthesis_cost,
            "promotions_granted": self.promotions_granted,
            "promotion_executions": self.promotion_executions,
            "promotion_reported_cost": self.promotion_reported_cost,
            "professor_actual_calls": self.professor_actual_calls,
            "professor_reported_cost": self.professor_reported_cost,
            "accounted_units": self.accounted_units,
        }


def account_run_cost(
    result: SearchResult,
    dreamer: LogicalDreamer,
    executor: PromotionExecutor,
    *,
    controller: object | None = None,
    dreamer_synthesis_unit_cost: float = 1.0,
    professor_unit_cost: float = 1.0,
) -> RunCostAccounting:
    call_log = dreamer.call_log
    invoked = [row for row in call_log if row.invoked and row.response is not None]
    oracle_cost = sum(float(row.response.reported_cost) for row in invoked if row.response is not None)
    reflection = dreamer.reflection()
    proposal_cost = reflection.proposals_created * float(dreamer_synthesis_unit_cost)
    applied = [row for row in executor.history if row.applied]
    promotion_cost = sum(float(row.reported_cost) for row in applied)
    professor_calls = int(getattr(controller, "actual_professor_calls", 0)) if controller is not None else 0
    professor_cost = professor_calls * float(professor_unit_cost)

    accounted = (
        float(result.expansions)
        + oracle_cost
        + proposal_cost
        + promotion_cost
        + professor_cost
    )
    return RunCostAccounting(
        search_expansions=int(result.expansions),
        wall_time_s=float(result.elapsed_s),
        oracle_calls=len(invoked),
        oracle_reported_cost=oracle_cost,
        dreamer_proposals=reflection.proposals_created,
        dreamer_synthesis_cost=proposal_cost,
        promotions_granted=reflection.promotions,
        promotion_executions=len(applied),
        promotion_reported_cost=promotion_cost,
        professor_actual_calls=professor_calls,
        professor_reported_cost=professor_cost,
        accounted_units=accounted,
    )
