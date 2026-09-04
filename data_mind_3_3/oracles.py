from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from data_mind_3.control.agents import EscapeAction, SettlementRole
from data_mind_3_2.epistemic.oracle_dynamics import OracleFacet

from .dreamer import DreamerContext, DreamerDraft, OracleResponse


@dataclass(frozen=True)
class DreamerSearchSnapshot:
    """Non-privileged finite search facts exposed to the 3.3 Dreamer.

    The snapshot contains operational state only.  It carries no hidden proof,
    verifier acceptance, BANK admission, or ground-truth settlement label.
    """

    target_id: str
    expansion: int
    generated_total: int
    frontier: int
    max_frontier: int
    elapsed: float
    timeout: float
    partial_credit: float
    relevance: float
    control_error: Mapping[str, float] = field(default_factory=dict)
    effective: Mapping[str, int | float] = field(default_factory=dict)
    creativity: Mapping[str, float] = field(default_factory=dict)
    candidate_certificate_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("target_id must be nonempty")
        if self.expansion < 0 or self.generated_total < 0 or self.frontier < 0:
            raise ValueError("search counters must be nonnegative")
        if self.max_frontier <= 0 or self.timeout <= 0:
            raise ValueError("max_frontier and timeout must be positive")
        if not 0.0 <= self.partial_credit <= 1.0:
            raise ValueError("partial_credit must lie in [0, 1]")
        if not 0.0 <= self.relevance <= 1.0:
            raise ValueError("relevance must lie in [0, 1]")

    @property
    def resource_fraction(self) -> float:
        return max(0.0, min(1.0, self.elapsed / self.timeout))

    @property
    def frontier_fraction(self) -> float:
        return max(0.0, min(1.0, self.frontier / self.max_frontier))

    @property
    def generated_per_expansion(self) -> float:
        return self.generated_total / max(1, self.expansion)


@dataclass(frozen=True)
class RoleAdvice:
    """O1 task-role advice; not an assertion of hidden theorem truth."""

    role: SettlementRole | None
    confidence: float
    basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResourceAdvice:
    """O2 finite resource posture."""

    mode: str
    breadth_factor: float
    depth_factor: float
    conserve: bool
    basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategyAdvice:
    """O3 finite next-action class."""

    action: EscapeAction
    confidence: float
    basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class CertificateAdvice:
    """O4 candidate-only certificate information."""

    candidate_reference: str | None
    readiness: float
    basis: tuple[str, ...] = ()


def _snapshot(context: DreamerContext) -> DreamerSearchSnapshot:
    value = context.metadata.get("search_snapshot")
    if not isinstance(value, DreamerSearchSnapshot):
        raise ValueError("DreamerContext requires a DreamerSearchSnapshot")
    if value.target_id != context.target_id or value.expansion != context.step:
        raise ValueError("Dreamer context and search snapshot must describe the same state")
    return value


def finite_role_oracle(context: DreamerContext) -> OracleResponse:
    """O1 for the Metamath proof-search lane.

    The adapter identifies the configured task lane as PROVE.  It does not use
    hidden theoremhood, a hidden proof, or verifier outcome as evidence.
    """

    _snapshot(context)
    advice = RoleAdvice(
        role=SettlementRole.PROVE,
        confidence=1.0,
        basis=("configured_metamath_proof_lane", "no_hidden_truth_access"),
    )
    return OracleResponse(
        OracleFacet.O1_ROLE,
        advice=advice,
        confidence=advice.confidence,
        reported_cost=1.0,
        provenance={"adapter": "finite_role", "cost_units": "adapter_call"},
    )


def finite_resource_oracle(context: DreamerContext) -> OracleResponse:
    snap = _snapshot(context)
    err = snap.control_error
    resource = max(snap.resource_fraction, float(err.get("resource", 0.0)))
    frontier = max(snap.frontier_fraction, float(err.get("frontier", 0.0)))
    branch = float(err.get("branch", 0.0))
    stagnation = float(err.get("stagnation", 0.0))

    if max(resource, frontier, branch) >= 0.80:
        advice = ResourceAdvice(
            mode="conserve",
            breadth_factor=0.75,
            depth_factor=1.05,
            conserve=True,
            basis=("high_resource_or_frontier_pressure",),
        )
    elif stagnation >= 0.75 and max(resource, frontier) < 0.60:
        advice = ResourceAdvice(
            mode="explore",
            breadth_factor=1.15,
            depth_factor=1.05,
            conserve=False,
            basis=("controlled_stagnation",),
        )
    else:
        advice = ResourceAdvice(
            mode="balanced",
            breadth_factor=1.0,
            depth_factor=1.0,
            conserve=False,
            basis=("no_extreme_resource_signal",),
        )

    return OracleResponse(
        OracleFacet.O2_RESOURCE,
        advice=advice,
        confidence=0.65,
        reported_cost=1.0,
        provenance={"adapter": "finite_resource", "cost_units": "adapter_call"},
    )


def finite_strategy_oracle(context: DreamerContext) -> OracleResponse:
    snap = _snapshot(context)
    err = snap.control_error
    resource = max(snap.resource_fraction, float(err.get("resource", 0.0)))
    stagnation = float(err.get("stagnation", 0.0))
    drift = float(err.get("drift", 0.0))
    branch = float(err.get("branch", 0.0))
    frontier = max(snap.frontier_fraction, float(err.get("frontier", 0.0)))

    if resource >= 0.85:
        advice = StrategyAdvice(EscapeAction.FALLBACK, 0.80, ("resource_near_limit",))
    elif stagnation >= 0.80 and drift >= 0.50:
        advice = StrategyAdvice(EscapeAction.SWITCH_BASIN, 0.72, ("stagnation_plus_drift",))
    elif stagnation >= 0.80:
        advice = StrategyAdvice(EscapeAction.BACKFILL_LEMMA, 0.68, ("sustained_stagnation",))
    elif max(branch, frontier) >= 0.75:
        advice = StrategyAdvice(EscapeAction.FINE_TUNE, 0.70, ("search_pressure",))
    else:
        advice = StrategyAdvice(EscapeAction.REPAIR, 0.55, ("default_local_repair",))

    return OracleResponse(
        OracleFacet.O3_STRATEGY,
        advice=advice,
        confidence=advice.confidence,
        reported_cost=1.0,
        provenance={"adapter": "finite_strategy", "cost_units": "adapter_call"},
    )


def finite_certificate_oracle(context: DreamerContext) -> OracleResponse:
    snap = _snapshot(context)
    # O4 never invents or verifies a certificate.  It may only surface a
    # candidate reference already present in non-authoritative search state.
    ref = snap.candidate_certificate_ref
    advice = CertificateAdvice(
        candidate_reference=ref,
        readiness=snap.partial_credit,
        basis=("existing_candidate_reference",) if ref else ("no_candidate_available",),
    )
    return OracleResponse(
        OracleFacet.O4_CERTIFICATE,
        advice=advice,
        confidence=snap.partial_credit if ref else 0.0,
        reported_cost=1.0,
        provenance={
            "adapter": "finite_certificate",
            "cost_units": "adapter_call",
            "candidate_only": True,
            "verifier_authority": False,
        },
    )


def default_oracle_interfaces():
    """Return the first finite O1/O2/O3/O4 interface installation."""

    return {
        OracleFacet.O1_ROLE: finite_role_oracle,
        OracleFacet.O2_RESOURCE: finite_resource_oracle,
        OracleFacet.O3_STRATEGY: finite_strategy_oracle,
        OracleFacet.O4_CERTIFICATE: finite_certificate_oracle,
    }


def synthesize_typed_dream(
    context: DreamerContext,
    responses: tuple[OracleResponse, ...],
) -> DreamerDraft:
    """Conservative synthesis for shadow mode.

    Strategy advice owns the proposed action when available.  Otherwise a
    conserve recommendation asks for fine tuning; otherwise Dreamer proposes
    local repair.  No response can directly alter the search or certify proof.
    """

    action = EscapeAction.REPAIR
    typed: dict[str, Any] = {}
    for response in responses:
        typed[response.facet.value] = response.advice
        if response.facet is OracleFacet.O3_STRATEGY and isinstance(response.advice, StrategyAdvice):
            action = response.advice.action

    if action is EscapeAction.REPAIR:
        for response in responses:
            if response.facet is OracleFacet.O2_RESOURCE and isinstance(response.advice, ResourceAdvice):
                if response.advice.conserve:
                    action = EscapeAction.FINE_TUNE
                    break

    return DreamerDraft(
        action=action,
        payload={
            "typed_oracle_advice": typed,
            "shadow_only": True,
            "target_id": context.target_id,
            "step": context.step,
        },
    )
