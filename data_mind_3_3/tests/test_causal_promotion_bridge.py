from data_mind_3.control.agents import EscapeAction
from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.control.futurebank import FutureProposal
from data_mind_3_2.epistemic.oracle_dynamics import OracleFacet
from data_mind_3_3.dreamer import OracleAccessMask, OracleThrottle, PromotionThrottle
from data_mind_3_3.metamath.causal_bridge import CausalDreamerController, build_causal_dreamer
from data_mind_3_3.promotion import PromotionExecutor


class _Config:
    candidate_cap = 64
    match_cap_per_candidate = 8
    free_var_completion_cap = 64
    max_depth = 24


def test_promotion_executor_applies_only_bounded_whitelisted_control_and_can_undo():
    controller = AdaptiveCreativityController(interval=4)
    before = controller.creativity.to_dict()
    proposal = FutureProposal(
        "p1",
        "DREAMER",
        EscapeAction.SWITCH_BASIN,
    )
    executor = PromotionExecutor(max_abs_delta=0.05)
    record = executor.execute(proposal, controller)

    assert record.applied
    assert record.reason == "whitelisted_bounded_control_move"
    assert max(abs(v) for v in record.deltas.values()) <= 0.05
    assert controller.creativity.to_dict() != before

    executor.undo(record, controller)
    assert controller.creativity.to_dict() == before

    forbidden = {"verify", "certify", "deposit", "deposit_to_bank", "bank_admit"}
    for name in forbidden:
        assert not hasattr(executor, name)


def test_unwhitelisted_promotion_cannot_change_controller():
    controller = AdaptiveCreativityController(interval=4)
    before = controller.creativity.to_dict()
    proposal = FutureProposal("p2", "DREAMER", EscapeAction.QUOTIENT)
    executor = PromotionExecutor()
    record = executor.execute(proposal, controller)
    assert not record.applied
    assert record.reason == "action_not_whitelisted"
    assert controller.creativity.to_dict() == before


def test_causal_bridge_promotes_through_futurebank_gate_then_applies_legal_move():
    base = AdaptiveCreativityController(interval=4)
    dreamer = build_causal_dreamer(
        access=OracleAccessMask.from_bits((0, 0, 1, 0)),
        throttles={
            OracleFacet.O3_STRATEGY: OracleThrottle(min_steps_between_calls=0),
        },
        promotion_throttle=PromotionThrottle(max_promotions=1),
    )
    bridge = CausalDreamerController(base, dreamer, target_id="demo")

    event = bridge.observe_expansion(
        expansion=4,
        generated_total=8,
        frontier=1,
        max_frontier=1000,
        elapsed=1.0,
        timeout=100.0,
        partial_credit=0.2,
        relevance=0.5,
        base_config=_Config(),
    )
    assert event is not None
    assert event["dreamer_causal"]["promotion_granted"] is True
    assert event["dreamer_causal"]["execution_applied"] is True
    assert dreamer.reflection().promotions == 1
    assert len(bridge.executor.history) == 1

    event2 = bridge.observe_expansion(
        expansion=8,
        generated_total=16,
        frontier=1,
        max_frontier=1000,
        elapsed=2.0,
        timeout=100.0,
        partial_credit=0.2,
        relevance=0.5,
        base_config=_Config(),
    )
    assert event2 is not None
    assert event2["dreamer_causal"]["promotion_granted"] is False
    assert dreamer.reflection().promotion_rejections == 1


def test_causal_bridge_off_returns_base_event_unchanged():
    direct = AdaptiveCreativityController(interval=4)
    wrapped_base = AdaptiveCreativityController(interval=4)
    bridge = CausalDreamerController(
        wrapped_base,
        build_causal_dreamer(),
        target_id="demo",
        enabled=False,
    )
    kwargs = dict(
        expansion=4,
        generated_total=8,
        frontier=1,
        max_frontier=1000,
        elapsed=1.0,
        timeout=100.0,
        partial_credit=0.2,
        relevance=0.5,
        base_config=_Config(),
    )
    assert bridge.observe_expansion(**kwargs) == direct.observe_expansion(**kwargs)
    assert bridge.history == []
    assert bridge.dreamer.call_log == ()
