from data_mind_3.control.agents import EscapeAction, SettlementRole
from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3_2.epistemic.oracle_dynamics import OracleFacet
from data_mind_3_3.dreamer import DreamerContext
from data_mind_3_3.metamath.dreamer_bridge import (
    ShadowDreamerController,
    build_shadow_dreamer,
)
from data_mind_3_3.oracles import (
    CertificateAdvice,
    DreamerSearchSnapshot,
    ResourceAdvice,
    RoleAdvice,
    StrategyAdvice,
    finite_certificate_oracle,
    finite_resource_oracle,
    finite_role_oracle,
    finite_strategy_oracle,
)


class _Config:
    candidate_cap = 64
    match_cap_per_candidate = 8
    free_var_completion_cap = 64
    max_depth = 24


def _context(*, step=16, error=None, candidate=None):
    snapshot = DreamerSearchSnapshot(
        target_id="prcom",
        expansion=step,
        generated_total=100,
        frontier=20,
        max_frontier=1000,
        elapsed=10.0,
        timeout=100.0,
        partial_credit=0.4,
        relevance=0.5,
        control_error=error or {},
        candidate_certificate_ref=candidate,
    )
    return DreamerContext(
        target_id="prcom",
        step=step,
        metadata={"search_snapshot": snapshot},
    )


def test_four_finite_oracle_adapters_return_typed_non_authoritative_advice():
    context = _context(error={"stagnation": 0.9, "drift": 0.6, "resource": 0.1})
    o1 = finite_role_oracle(context)
    o2 = finite_resource_oracle(context)
    o3 = finite_strategy_oracle(context)
    o4 = finite_certificate_oracle(context)
    assert isinstance(o1.advice, RoleAdvice)
    assert o1.advice.role is SettlementRole.PROVE
    assert "no_hidden_truth_access" in o1.advice.basis
    assert isinstance(o2.advice, ResourceAdvice)
    assert o2.advice.mode == "explore"
    assert isinstance(o3.advice, StrategyAdvice)
    assert o3.advice.action is EscapeAction.SWITCH_BASIN
    assert isinstance(o4.advice, CertificateAdvice)
    assert o4.advice.candidate_reference is None
    assert o4.provenance["verifier_authority"] is False


def test_certificate_oracle_only_surfaces_existing_candidate_reference():
    context = _context(candidate="candidate:prcom:7")
    response = finite_certificate_oracle(context)
    assert response.advice.candidate_reference == "candidate:prcom:7"
    assert response.advice.basis == ("existing_candidate_reference",)


def test_shadow_bridge_runs_only_on_control_updates_and_never_promotes():
    base = AdaptiveCreativityController(interval=16)
    dreamer = build_shadow_dreamer()
    bridge = ShadowDreamerController(base, dreamer, target_id="prcom")

    no_event = bridge.observe_expansion(
        expansion=8,
        generated_total=16,
        frontier=5,
        max_frontier=1000,
        elapsed=1.0,
        timeout=100.0,
        partial_credit=0.2,
        relevance=0.4,
        base_config=_Config(),
    )
    assert no_event is None
    assert bridge.shadow_history == []
    assert len(dreamer.call_log) == 0

    event = bridge.observe_expansion(
        expansion=16,
        generated_total=32,
        frontier=10,
        max_frontier=1000,
        elapsed=2.0,
        timeout=100.0,
        partial_credit=0.2,
        relevance=0.4,
        base_config=_Config(),
    )
    assert event is not None
    assert event["dreamer_shadow"]["causal_search_effect"] is False
    assert event["dreamer_shadow"]["promotion_requested"] is False
    assert len(bridge.shadow_history) == 1
    assert dreamer.futurebank.open_transactions == ()
    reflection = dreamer.reflection()
    assert reflection.proposals_created == 1
    assert reflection.promotions == 0
    assert reflection.access_bits == (1, 1, 1, 1)
    assert all(x.calls == 1 for x in reflection.oracle_state)


def test_default_shadow_throttles_apply_to_real_oracle_invocations():
    base = AdaptiveCreativityController(interval=16)
    dreamer = build_shadow_dreamer()
    bridge = ShadowDreamerController(base, dreamer, target_id="prcom")
    for expansion in (16, 32):
        event = bridge.observe_expansion(
            expansion=expansion,
            generated_total=expansion * 2,
            frontier=10,
            max_frontier=1000,
            elapsed=float(expansion) / 10.0,
            timeout=100.0,
            partial_credit=0.2,
            relevance=0.4,
            base_config=_Config(),
        )
        assert event is not None
    reflection = dreamer.reflection()
    by_facet = {row.facet: row for row in reflection.oracle_state}
    assert by_facet[OracleFacet.O1_ROLE].calls == 1
    assert by_facet[OracleFacet.O2_RESOURCE].calls == 2
    assert by_facet[OracleFacet.O3_STRATEGY].calls == 1
    assert by_facet[OracleFacet.O4_CERTIFICATE].calls == 1
    assert by_facet[OracleFacet.O1_ROLE].skipped_throttled == 1
    assert by_facet[OracleFacet.O3_STRATEGY].skipped_throttled == 1
    assert by_facet[OracleFacet.O4_CERTIFICATE].skipped_throttled == 1


def test_dreamer_off_returns_base_controller_event_unchanged_and_calls_nothing():
    direct = AdaptiveCreativityController(interval=16)
    wrapped_base = AdaptiveCreativityController(interval=16)
    dreamer = build_shadow_dreamer()
    bridge = ShadowDreamerController(
        wrapped_base,
        dreamer,
        target_id="prcom",
        dreamer_enabled=False,
    )

    kwargs = dict(
        expansion=16,
        generated_total=64,
        frontier=10,
        max_frontier=1000,
        elapsed=2.0,
        timeout=100.0,
        partial_credit=0.2,
        relevance=0.4,
        base_config=_Config(),
    )
    direct_event = direct.observe_expansion(**kwargs)
    wrapped_event = bridge.observe_expansion(**kwargs)

    assert wrapped_event == direct_event
    assert bridge.shadow_history == []
    assert dreamer.call_log == ()
    assert dreamer.reflection().proposals_created == 0
