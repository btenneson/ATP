from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.metamath.search import SearchConfig, SearchResult, search_target
from data_mind_3_2.epistemic.oracle_dynamics import ALL_ORACLE_FACETS, OracleFacet

from data_mind_3_3.dreamer import (
    DreamerContext,
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


DEFAULT_SHADOW_THROTTLES = {
    OracleFacet.O1_ROLE: OracleThrottle(min_steps_between_calls=64),
    OracleFacet.O2_RESOURCE: OracleThrottle(min_steps_between_calls=16),
    OracleFacet.O3_STRATEGY: OracleThrottle(min_steps_between_calls=64),
    OracleFacet.O4_CERTIFICATE: OracleThrottle(min_steps_between_calls=256),
}


@dataclass(frozen=True)
class ShadowDreamRecord:
    proposal_id: str
    expansion: int
    action: str
    consulted_facets: tuple[str, ...]
    access_bits: tuple[int, int, int, int]


class ShadowDreamerController:
    """Non-causal Dreamer wrapper around an existing DATA MIND controller.

    All ordinary search decisions delegate to `base_controller`.  Dreamer is
    invoked only after the base controller emits a genuine control-update event.
    Every dream is immediately closed without promotion, so this wrapper cannot
    alter the search trajectory or verifier/BANK behavior.

    With `dreamer_enabled=False`, observe_expansion returns the base controller's
    result *unchanged* and performs no Dreamer/oracle/FUTUREBANK work.  This is
    the explicit DATA MIND 3.3 OFF-control invariant path.
    """

    def __init__(
        self,
        base_controller: object,
        dreamer: LogicalDreamer,
        *,
        target_id: str,
        facets: Sequence[OracleFacet] = ALL_ORACLE_FACETS,
        dreamer_enabled: bool = True,
    ) -> None:
        if not target_id:
            raise ValueError("target_id must be nonempty")
        self.base_controller = base_controller
        self.dreamer = dreamer
        self.target_id = target_id
        self.facets = tuple(facets)
        self.dreamer_enabled = bool(dreamer_enabled)
        self.shadow_history: list[ShadowDreamRecord] = []

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
        if event is None or not self.dreamer_enabled:
            return event

        raw_error = event.get("error", {}) if isinstance(event, dict) else {}
        control_error = {
            str(k): float(v)
            for k, v in raw_error.items()
            if isinstance(v, (int, float))
        } if isinstance(raw_error, dict) else {}

        raw_effective = event.get("effective", {}) if isinstance(event, dict) else {}
        effective = dict(raw_effective) if isinstance(raw_effective, dict) else {}

        raw_creativity = event.get("creativity_after", {}) if isinstance(event, dict) else {}
        creativity = {
            str(k): float(v)
            for k, v in raw_creativity.items()
            if isinstance(v, (int, float))
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
            metadata={"search_snapshot": snapshot, "shadow_mode": True},
        )
        txid = f"dm33-shadow:{self.target_id}:{expansion}:{len(self.shadow_history) + 1}"
        proposal = self.dreamer.dream(
            txid,
            context,
            facets=self.facets,
            synthesize=synthesize_typed_dream,
        )

        self.dreamer.close_transaction(
            txid,
            request_promotion=False,
            step=expansion,
        )

        payload = proposal.payload if isinstance(proposal.payload, dict) else {}
        record = ShadowDreamRecord(
            proposal_id=proposal.proposal_id,
            expansion=expansion,
            action=proposal.action.value,
            consulted_facets=tuple(payload.get("oracle_facets_consulted", ())),
            access_bits=self.dreamer.access.bits,
        )
        self.shadow_history.append(record)

        enriched = dict(event)
        enriched["dreamer_shadow"] = {
            "proposal_id": record.proposal_id,
            "action": record.action,
            "consulted_facets": record.consulted_facets,
            "access_bits": record.access_bits,
            "promotion_requested": False,
            "causal_search_effect": False,
        }
        return enriched


def build_shadow_dreamer(
    *,
    access: OracleAccessMask | None = None,
    throttles: dict[OracleFacet, OracleThrottle] | None = None,
) -> LogicalDreamer:
    return LogicalDreamer(
        default_oracle_interfaces(),
        access=access or OracleAccessMask.from_bits((1, 1, 1, 1)),
        throttles=throttles or DEFAULT_SHADOW_THROTTLES,
        promotion_throttle=PromotionThrottle(max_promotions=0),
        source_agent="DREAMER-3.3-SHADOW",
    )


def search_target_with_shadow_dreamer(
    db: object,
    target_label: str,
    config: SearchConfig,
    *,
    verify_candidate: Callable | None = None,
    controller: object | None = None,
    dreamer: LogicalDreamer | None = None,
    dreamer_enabled: bool = True,
) -> tuple[SearchResult, ShadowDreamerController]:
    base = controller or AdaptiveCreativityController()
    installed = dreamer or build_shadow_dreamer()
    wrapper = ShadowDreamerController(
        base,
        installed,
        target_id=target_label,
        dreamer_enabled=dreamer_enabled,
    )
    result = search_target(
        db,
        target_label,
        config,
        verify_candidate=verify_candidate,
        controller=wrapper,
    )
    return result, wrapper
