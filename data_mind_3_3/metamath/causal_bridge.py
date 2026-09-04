from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.metamath.search import SearchConfig, SearchResult, search_target
from data_mind_3_2.epistemic.oracle_dynamics import ALL_ORACLE_FACETS, OracleFacet

from data_mind_3_3.dreamer import (
    DreamerContext,
    DreamerDraft,
    LogicalDreamer,
    OracleAccessMask,
    OracleThrottle,
    PromotionThrottle,
)
from data_mind_3_3.oracles import (
    DreamerSearchSnapshot,
    default_oracle_interfaces,
    synthesize_typed_dream,
)
from data_mind_3_3.promotion import PROMOTION_DELTAS, PromotionExecution, PromotionExecutor


ENGINEERING_CAUSAL_THROTTLES = {
    OracleFacet.O1_ROLE: OracleThrottle(min_steps_between_calls=64),
    OracleFacet.O2_RESOURCE: OracleThrottle(min_steps_between_calls=16),
    OracleFacet.O3_STRATEGY: OracleThrottle(min_steps_between_calls=64),
    OracleFacet.O4_CERTIFICATE: OracleThrottle(min_steps_between_calls=256),
}


@dataclass(frozen=True)
class CausalDreamRecord:
    proposal_id: str
    expansion: int
    action: str
    promotion_requested: bool
    promotion_granted: bool
    execution_applied: bool
    execution_reason: str


def synthesize_promotable_typed_dream(context, responses) -> DreamerDraft:
    base = synthesize_typed_dream(context, responses)
    payload = dict(base.payload) if isinstance(base.payload, dict) else {"value": base.payload}
    payload["shadow_only"] = False
    payload["promotion_eligible"] = base.action in PROMOTION_DELTAS
    return DreamerDraft(
        action=base.action,
        payload=payload,
        estimated_cost=base.estimated_cost,
        predicted_grade=base.predicted_grade,
        dependencies=base.dependencies,
    )


class CausalDreamerController:
    """Milestone-3 bridge: Dreamer may cause bounded legal control moves.

    The base controller still owns ordinary search decisions.  Dreamer is
    consulted only on real control-update events.  A proposal must pass both the
    FUTUREBANK promotion throttle and the explicit PromotionExecutor whitelist.
    The only causal effect is a bounded mutation of the existing creativity
    vector.  Verifier, Sentinel and BANK remain outside this class.
    """

    def __init__(
        self,
        base_controller: object,
        dreamer: LogicalDreamer,
        *,
        target_id: str,
        executor: PromotionExecutor | None = None,
        facets: Sequence[OracleFacet] = ALL_ORACLE_FACETS,
        enabled: bool = True,
    ) -> None:
        self.base_controller = base_controller
        self.dreamer = dreamer
        self.target_id = target_id
        self.executor = executor or PromotionExecutor()
        self.facets = tuple(facets)
        self.enabled = bool(enabled)
        self.history: list[CausalDreamRecord] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_controller, name)

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
        event = self.base_controller.observe_expansion(
            expansion=expansion,
            generated_total=generated_total,
            frontier=frontier,
            max_frontier=max_frontier,
            elapsed=elapsed,
            timeout=timeout,
            partial_credit=partial_credit,
            relevance=relevance,
            base_config=base_config,
        )
        if event is None or not self.enabled:
            return event

        raw_error = event.get("error", {}) if isinstance(event, dict) else {}
        control_error = {
            str(k): float(v) for k, v in raw_error.items() if isinstance(v, (int, float))
        } if isinstance(raw_error, dict) else {}
        raw_effective = event.get("effective", {}) if isinstance(event, dict) else {}
        effective = dict(raw_effective) if isinstance(raw_effective, dict) else {}
        raw_creativity = event.get("creativity_after", {}) if isinstance(event, dict) else {}
        creativity = {
            str(k): float(v) for k, v in raw_creativity.items() if isinstance(v, (int, float))
        } if isinstance(raw_creativity, dict) else {}

        snapshot = DreamerSearchSnapshot(
            target_id=self.target_id,
            expansion=expansion,
            generated_total=generated_total,
            frontier=frontier,
            max_frontier=max_frontier,
            elapsed=elapsed,
            timeout=timeout,
            partial_credit=max(0.0, min(1.0, float(partial_credit))),
            relevance=max(0.0, min(1.0, float(relevance))),
            control_error=control_error,
            effective=effective,
            creativity=creativity,
        )
        context = DreamerContext(
            target_id=self.target_id,
            step=expansion,
            metadata={"search_snapshot": snapshot, "causal_mode": True},
        )
        txid = f"dm33-causal:{self.target_id}:{expansion}:{len(self.history) + 1}"
        proposal = self.dreamer.dream(
            txid,
            context,
            facets=self.facets,
            synthesize=synthesize_promotable_typed_dream,
        )

        request = proposal.action in PROMOTION_DELTAS
        promoted = self.dreamer.close_transaction(
            txid,
            request_promotion=request,
            step=expansion,
        )

        execution: PromotionExecution | None = None
        if promoted:
            # Current Dreamer creates exactly one proposal per transaction.
            execution = self.executor.execute(promoted[0], self.base_controller)

        record = CausalDreamRecord(
            proposal_id=proposal.proposal_id,
            expansion=expansion,
            action=proposal.action.value,
            promotion_requested=request,
            promotion_granted=bool(promoted),
            execution_applied=bool(execution and execution.applied),
            execution_reason=execution.reason if execution else (
                "promotion_not_granted" if request else "action_not_whitelisted"
            ),
        )
        self.history.append(record)

        enriched = dict(event)
        enriched["dreamer_causal"] = {
            "proposal_id": record.proposal_id,
            "action": record.action,
            "promotion_requested": record.promotion_requested,
            "promotion_granted": record.promotion_granted,
            "execution_applied": record.execution_applied,
            "execution_reason": record.execution_reason,
            "authority": "bounded_control_only",
        }
        return enriched


def build_causal_dreamer(
    *,
    access: OracleAccessMask | None = None,
    throttles: dict[OracleFacet, OracleThrottle] | None = None,
    promotion_throttle: PromotionThrottle | None = None,
) -> LogicalDreamer:
    return LogicalDreamer(
        default_oracle_interfaces(),
        access=access or OracleAccessMask.from_bits((1, 1, 1, 1)),
        throttles=throttles or ENGINEERING_CAUSAL_THROTTLES,
        promotion_throttle=promotion_throttle or PromotionThrottle(
            max_promotions=16,
            min_steps_between_promotions=64,
        ),
        source_agent="DREAMER-3.3-CAUSAL",
    )


def search_target_with_causal_dreamer(
    db: object,
    target_label: str,
    config: SearchConfig,
    *,
    verify_candidate: Callable | None = None,
    controller: object | None = None,
    dreamer: LogicalDreamer | None = None,
    executor: PromotionExecutor | None = None,
    enabled: bool = True,
) -> tuple[SearchResult, CausalDreamerController]:
    base = controller or AdaptiveCreativityController()
    wrapper = CausalDreamerController(
        base,
        dreamer or build_causal_dreamer(),
        target_id=target_label,
        executor=executor,
        enabled=enabled,
    )
    result = search_target(
        db,
        target_label,
        config,
        verify_candidate=verify_candidate,
        controller=wrapper,
    )
    return result, wrapper
