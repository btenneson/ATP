from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import product
from typing import Any, Callable, Mapping, Sequence

from data_mind_3.control.agents import EscapeAction
from data_mind_3.control.futurebank import (
    FutureProposal,
    FutureTrust,
    TransactionalFutureBank,
)
from data_mind_3_2.epistemic.oracle_dynamics import ALL_ORACLE_FACETS, OracleFacet


@dataclass(frozen=True)
class OracleAccessMask:
    """The four independent Dreamer-to-oracle access gates.

    The bit order is O1 role, O2 resource, O3 strategy, O4 certificate.  The
    mask says which interfaces Dreamer may call; it does not claim oracle
    correctness or omniscience.
    """

    enabled: frozenset[OracleFacet] = frozenset()

    def __post_init__(self) -> None:
        unknown = set(self.enabled) - set(ALL_ORACLE_FACETS)
        if unknown:
            raise ValueError(f"unknown oracle facets: {sorted(x.value for x in unknown)}")

    @classmethod
    def from_bits(cls, bits: Sequence[int | bool]) -> "OracleAccessMask":
        if len(bits) != 4:
            raise ValueError("oracle access mask requires exactly four bits")
        normalized: list[bool] = []
        for bit in bits:
            if bit not in (0, 1, False, True):
                raise ValueError("oracle access bits must be 0 or 1")
            normalized.append(bool(bit))
        return cls(
            frozenset(
                facet
                for facet, enabled in zip(ALL_ORACLE_FACETS, normalized)
                if enabled
            )
        )

    @property
    def bits(self) -> tuple[int, int, int, int]:
        return tuple(1 if facet in self.enabled else 0 for facet in ALL_ORACLE_FACETS)  # type: ignore[return-value]

    def allows(self, facet: OracleFacet) -> bool:
        return facet in self.enabled

    @classmethod
    def nonempty_masks(cls) -> tuple["OracleAccessMask", ...]:
        return tuple(
            cls.from_bits(bits)
            for bits in product((0, 1), repeat=4)
            if any(bits)
        )


@dataclass(frozen=True)
class OracleThrottle:
    """Hard call-site throttle for one oracle interface."""

    max_calls: int | None = None
    min_steps_between_calls: int = 0

    def __post_init__(self) -> None:
        if self.max_calls is not None and self.max_calls < 0:
            raise ValueError("max_calls must be nonnegative or None")
        if self.min_steps_between_calls < 0:
            raise ValueError("min_steps_between_calls must be nonnegative")


@dataclass(frozen=True)
class PromotionThrottle:
    """Hard throttle for FUTUREBANK promotion requests."""

    max_promotions: int | None = None
    min_steps_between_promotions: int = 0

    def __post_init__(self) -> None:
        if self.max_promotions is not None and self.max_promotions < 0:
            raise ValueError("max_promotions must be nonnegative or None")
        if self.min_steps_between_promotions < 0:
            raise ValueError("min_steps_between_promotions must be nonnegative")


@dataclass(frozen=True)
class DreamerContext:
    target_id: str
    step: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("target_id must be nonempty")
        if self.step < 0:
            raise ValueError("step must be nonnegative")


@dataclass(frozen=True)
class OracleResponse:
    facet: OracleFacet
    advice: Any
    confidence: float | None = None
    reported_cost: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must lie in [0, 1]")
        if self.reported_cost < 0:
            raise ValueError("reported_cost must be nonnegative")


@dataclass(frozen=True)
class OracleCallRecord:
    facet: OracleFacet
    step: int
    invoked: bool
    reason: str
    response: OracleResponse | None = None


@dataclass(frozen=True)
class DreamerDraft:
    """One speculative Dreamer synthesis, still outside verifier/BANK authority."""

    action: EscapeAction
    payload: Any = None
    estimated_cost: float | None = None
    predicted_grade: Mapping[str, float | None] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.estimated_cost is not None and self.estimated_cost < 0:
            raise ValueError("estimated_cost must be nonnegative")


class DreamerOutcome(str, Enum):
    REJECTED = "rejected"
    EXPIRED = "expired"
    PROMOTED = "promoted"
    VERIFIED_CONTRIBUTING = "verified_contributing"


@dataclass(frozen=True)
class OracleReflection:
    facet: OracleFacet
    enabled: bool
    calls: int
    remaining_calls: int | None
    last_call_step: int | None
    total_reported_cost: float
    skipped_disabled: int
    skipped_throttled: int
    proposals_supported: int
    verified_contributions: int
    empirical_yield: float | None


@dataclass(frozen=True)
class DreamerReflection:
    """Operational level-2 self-observation for the Logical Dreamer.

    It records Dreamer's own access, usage, resource restrictions and observed
    consequences.  These are search-control facts, never certificate facts.
    """

    access_bits: tuple[int, int, int, int]
    proposals_created: int
    promotions: int
    promotion_rejections: int
    oracle_state: tuple[OracleReflection, ...]


@dataclass
class _MutableOracleState:
    calls: int = 0
    last_call_step: int | None = None
    total_reported_cost: float = 0.0
    skipped_disabled: int = 0
    skipped_throttled: int = 0


@dataclass
class _PromotionState:
    promotions: int = 0
    last_promotion_step: int | None = None
    rejected_by_throttle: int = 0


OracleFunction = Callable[[DreamerContext], OracleResponse]
DreamerSynthesizer = Callable[[DreamerContext, tuple[OracleResponse, ...]], DreamerDraft]


class LogicalDreamer:
    """Throttled, reflective interface to O1/O2/O3/O4.

    Architecture boundary:

        oracle interfaces -> Dreamer -> FUTUREBANK -> external promotion/search

    This class intentionally exposes no verifier acceptance method and no BANK
    write method.  A Dreamer proposal is speculative until ordinary DATA MIND
    computation and the external verifier establish otherwise.
    """

    def __init__(
        self,
        oracle_interfaces: Mapping[OracleFacet, OracleFunction],
        *,
        access: OracleAccessMask,
        throttles: Mapping[OracleFacet, OracleThrottle] | None = None,
        futurebank: TransactionalFutureBank | None = None,
        promotion_throttle: PromotionThrottle | None = None,
        source_agent: str = "DREAMER",
    ) -> None:
        if not source_agent.strip():
            raise ValueError("source_agent must be nonempty")
        self.oracle_interfaces = dict(oracle_interfaces)
        self.access = access
        self.throttles = {
            facet: (throttles or {}).get(facet, OracleThrottle())
            for facet in ALL_ORACLE_FACETS
        }
        self.futurebank = futurebank or TransactionalFutureBank()
        self.promotion_throttle = promotion_throttle or PromotionThrottle()
        self.source_agent = source_agent

        self._oracle_state = {facet: _MutableOracleState() for facet in ALL_ORACLE_FACETS}
        self._promotion_state = _PromotionState()
        self._call_log: list[OracleCallRecord] = []
        self._proposal_facets: dict[str, frozenset[OracleFacet]] = {}
        self._proposal_outcomes: dict[str, DreamerOutcome] = {}
        self._proposals_created = 0

    @property
    def call_log(self) -> tuple[OracleCallRecord, ...]:
        return tuple(self._call_log)

    def _throttle_reason(self, facet: OracleFacet, step: int) -> str | None:
        throttle = self.throttles[facet]
        state = self._oracle_state[facet]
        if throttle.max_calls is not None and state.calls >= throttle.max_calls:
            return "max_calls"
        if (
            state.last_call_step is not None
            and step - state.last_call_step < throttle.min_steps_between_calls
        ):
            return "min_steps_between_calls"
        return None

    def consult(self, facet: OracleFacet, context: DreamerContext) -> OracleCallRecord:
        """Consult one oracle only if the access gate and hard throttle permit it."""

        if context.step < 0:
            raise ValueError("step must be nonnegative")
        state = self._oracle_state[facet]

        if not self.access.allows(facet):
            state.skipped_disabled += 1
            record = OracleCallRecord(facet, context.step, False, "disabled")
            self._call_log.append(record)
            return record

        throttle_reason = self._throttle_reason(facet, context.step)
        if throttle_reason is not None:
            state.skipped_throttled += 1
            record = OracleCallRecord(facet, context.step, False, throttle_reason)
            self._call_log.append(record)
            return record

        try:
            interface = self.oracle_interfaces[facet]
        except KeyError:
            record = OracleCallRecord(facet, context.step, False, "unimplemented")
            self._call_log.append(record)
            return record

        # The expensive/advisory call occurs only after both checks above.  This
        # is deliberate: throttle counters must correspond to real invocations.
        response = interface(context)
        if not isinstance(response, OracleResponse):
            raise TypeError("oracle interface must return OracleResponse")
        if response.facet is not facet:
            raise ValueError("oracle response facet does not match requested facet")

        state.calls += 1
        state.last_call_step = context.step
        state.total_reported_cost += response.reported_cost
        record = OracleCallRecord(facet, context.step, True, "invoked", response)
        self._call_log.append(record)
        return record

    def dream(
        self,
        transaction_id: str,
        context: DreamerContext,
        *,
        facets: Sequence[OracleFacet],
        synthesize: DreamerSynthesizer,
    ) -> FutureProposal:
        """Create exactly one speculative FUTUREBANK proposal."""

        tx = self.futurebank.begin(transaction_id, self.source_agent)
        records = tuple(self.consult(facet, context) for facet in facets)
        responses = tuple(
            record.response
            for record in records
            if record.invoked and record.response is not None
        )
        draft = synthesize(context, responses)
        if not isinstance(draft, DreamerDraft):
            raise TypeError("Dreamer synthesizer must return DreamerDraft")

        proposal_id = f"{transaction_id}:dream:{self._proposals_created + 1}"
        participating = frozenset(response.facet for response in responses)
        reported_oracle_cost = sum(response.reported_cost for response in responses)
        estimated_cost = draft.estimated_cost
        if estimated_cost is None and responses:
            estimated_cost = reported_oracle_cost

        proposal = FutureProposal(
            proposal_id=proposal_id,
            source_agent=self.source_agent,
            action=draft.action,
            trust=FutureTrust.SPEC,
            estimated_cost=estimated_cost,
            predicted_grade=dict(draft.predicted_grade),
            dependencies=draft.dependencies,
            payload={
                "dream": draft.payload,
                "oracle_access_bits": self.access.bits,
                "oracle_facets_consulted": tuple(f.value for f in participating),
                "oracle_reported_cost": reported_oracle_cost,
                "context": {
                    "target_id": context.target_id,
                    "step": context.step,
                },
            },
        )
        tx.add(proposal)
        self._proposal_facets[proposal_id] = participating
        self._proposals_created += 1
        return proposal

    def _promotion_allowed(self, step: int) -> bool:
        throttle = self.promotion_throttle
        state = self._promotion_state
        if throttle.max_promotions is not None and state.promotions >= throttle.max_promotions:
            return False
        if (
            state.last_promotion_step is not None
            and step - state.last_promotion_step < throttle.min_steps_between_promotions
        ):
            return False
        return True

    def close_transaction(
        self,
        transaction_id: str,
        *,
        request_promotion: bool,
        step: int,
    ) -> tuple[FutureProposal, ...]:
        """Close a speculative transaction, applying the hard promotion gate.

        Promotion still means only "send for external computation/checking".
        Nothing here verifies a certificate or writes to BANK.
        """

        if step < 0:
            raise ValueError("step must be nonnegative")
        if not request_promotion:
            proposals = self.futurebank.close_discard(transaction_id)
            for proposal in proposals:
                self._proposal_outcomes[proposal.proposal_id] = DreamerOutcome.REJECTED
            return ()

        if not self._promotion_allowed(step):
            self._promotion_state.rejected_by_throttle += 1
            proposals = self.futurebank.close_discard(transaction_id)
            for proposal in proposals:
                self._proposal_outcomes[proposal.proposal_id] = DreamerOutcome.REJECTED
            return ()

        proposals = self.futurebank.close_for_promotion(transaction_id)
        self._promotion_state.promotions += 1
        self._promotion_state.last_promotion_step = step
        for proposal in proposals:
            self._proposal_outcomes[proposal.proposal_id] = DreamerOutcome.PROMOTED
        return proposals

    def record_outcome(self, proposal_id: str, outcome: DreamerOutcome) -> None:
        """Record an externally observed proposal consequence for reflection."""

        if proposal_id not in self._proposal_facets:
            raise KeyError(proposal_id)
        self._proposal_outcomes[proposal_id] = outcome

    def reflection(self) -> DreamerReflection:
        """Return Dreamer's checked operational self-model."""

        oracle_reflections: list[OracleReflection] = []
        for facet in ALL_ORACLE_FACETS:
            state = self._oracle_state[facet]
            throttle = self.throttles[facet]
            proposal_ids = [
                proposal_id
                for proposal_id, facets in self._proposal_facets.items()
                if facet in facets
            ]
            verified = sum(
                1
                for proposal_id in proposal_ids
                if self._proposal_outcomes.get(proposal_id)
                is DreamerOutcome.VERIFIED_CONTRIBUTING
            )
            proposals_supported = len(proposal_ids)
            empirical_yield = (
                verified / proposals_supported if proposals_supported else None
            )
            remaining_calls = None
            if throttle.max_calls is not None:
                remaining_calls = max(0, throttle.max_calls - state.calls)
            oracle_reflections.append(
                OracleReflection(
                    facet=facet,
                    enabled=self.access.allows(facet),
                    calls=state.calls,
                    remaining_calls=remaining_calls,
                    last_call_step=state.last_call_step,
                    total_reported_cost=state.total_reported_cost,
                    skipped_disabled=state.skipped_disabled,
                    skipped_throttled=state.skipped_throttled,
                    proposals_supported=proposals_supported,
                    verified_contributions=verified,
                    empirical_yield=empirical_yield,
                )
            )

        return DreamerReflection(
            access_bits=self.access.bits,
            proposals_created=self._proposals_created,
            promotions=self._promotion_state.promotions,
            promotion_rejections=self._promotion_state.rejected_by_throttle,
            oracle_state=tuple(oracle_reflections),
        )
