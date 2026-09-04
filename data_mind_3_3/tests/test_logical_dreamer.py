from data_mind_3.control.agents import EscapeAction
from data_mind_3_2.epistemic.oracle_dynamics import OracleFacet
from data_mind_3_3.dreamer import (
    DreamerContext,
    DreamerDraft,
    DreamerOutcome,
    LogicalDreamer,
    OracleAccessMask,
    OracleResponse,
    OracleThrottle,
    PromotionThrottle,
)


def test_four_binary_access_switches_have_15_nonempty_configurations():
    masks = OracleAccessMask.nonempty_masks()
    bits = {mask.bits for mask in masks}
    assert len(masks) == 15
    assert len(bits) == 15
    assert (0, 0, 0, 0) not in bits
    assert (1, 1, 1, 1) in bits
    assert (0, 0, 1, 1) in bits


def test_disabled_gate_prevents_actual_oracle_invocation():
    called = {"count": 0}

    def strategy(context):
        called["count"] += 1
        return OracleResponse(OracleFacet.O3_STRATEGY, advice="try quotient")

    dreamer = LogicalDreamer(
        {OracleFacet.O3_STRATEGY: strategy},
        access=OracleAccessMask.from_bits((0, 0, 0, 0)),
    )
    record = dreamer.consult(
        OracleFacet.O3_STRATEGY,
        DreamerContext(target_id="t", step=0),
    )

    assert not record.invoked
    assert record.reason == "disabled"
    assert called["count"] == 0


def test_throttle_wraps_actual_oracle_call_site():
    called = {"count": 0}

    def strategy(context):
        called["count"] += 1
        return OracleResponse(
            OracleFacet.O3_STRATEGY,
            advice=f"strategy-at-{context.step}",
            reported_cost=2.0,
        )

    dreamer = LogicalDreamer(
        {OracleFacet.O3_STRATEGY: strategy},
        access=OracleAccessMask.from_bits((0, 0, 1, 0)),
        throttles={
            OracleFacet.O3_STRATEGY: OracleThrottle(
                max_calls=2,
                min_steps_between_calls=3,
            )
        },
    )

    r0 = dreamer.consult(OracleFacet.O3_STRATEGY, DreamerContext("t", 0))
    r1 = dreamer.consult(OracleFacet.O3_STRATEGY, DreamerContext("t", 1))
    r3 = dreamer.consult(OracleFacet.O3_STRATEGY, DreamerContext("t", 3))
    r9 = dreamer.consult(OracleFacet.O3_STRATEGY, DreamerContext("t", 9))

    assert r0.invoked
    assert not r1.invoked and r1.reason == "min_steps_between_calls"
    assert r3.invoked
    assert not r9.invoked and r9.reason == "max_calls"
    assert called["count"] == 2

    reflection = dreamer.reflection()
    o3 = next(x for x in reflection.oracle_state if x.facet is OracleFacet.O3_STRATEGY)
    assert o3.calls == 2
    assert o3.skipped_throttled == 2
    assert o3.total_reported_cost == 4.0
    assert o3.remaining_calls == 0


def test_dreamer_synthesizes_only_a_speculative_futurebank_proposal():
    def strategy(context):
        return OracleResponse(
            OracleFacet.O3_STRATEGY,
            advice="quotient-first",
            confidence=0.8,
            reported_cost=1.0,
        )

    def certificate(context):
        return OracleResponse(
            OracleFacet.O4_CERTIFICATE,
            advice={"candidate_skeleton": "c1"},
            confidence=0.4,
            reported_cost=3.0,
        )

    dreamer = LogicalDreamer(
        {
            OracleFacet.O3_STRATEGY: strategy,
            OracleFacet.O4_CERTIFICATE: certificate,
        },
        access=OracleAccessMask.from_bits((0, 0, 1, 1)),
        promotion_throttle=PromotionThrottle(max_promotions=1),
    )

    proposal = dreamer.dream(
        "tx1",
        DreamerContext(target_id="prcom", step=10),
        facets=(OracleFacet.O3_STRATEGY, OracleFacet.O4_CERTIFICATE),
        synthesize=lambda context, responses: DreamerDraft(
            action=EscapeAction.QUOTIENT,
            payload={"response_count": len(responses)},
        ),
    )

    assert proposal.trust.value == "SPEC"
    assert proposal.payload["oracle_access_bits"] == (0, 0, 1, 1)
    assert proposal.payload["oracle_reported_cost"] == 4.0
    assert proposal.estimated_cost == 4.0
    assert dreamer.futurebank.open_transactions == ("tx1",)

    forbidden = {
        "verify",
        "certify",
        "deposit",
        "deposit_to_bank",
        "bank_admit",
        "verifier_accept",
    }
    for name in forbidden:
        assert not hasattr(dreamer, name)

    promoted = dreamer.close_transaction("tx1", request_promotion=True, step=10)
    assert promoted == (proposal,)
    assert dreamer.futurebank.open_transactions == ()


def test_promotion_gate_is_hard_and_reflection_tracks_verified_yield():
    def strategy(context):
        return OracleResponse(OracleFacet.O3_STRATEGY, advice="switch basin")

    dreamer = LogicalDreamer(
        {OracleFacet.O3_STRATEGY: strategy},
        access=OracleAccessMask.from_bits((0, 0, 1, 0)),
        promotion_throttle=PromotionThrottle(max_promotions=1),
    )

    first = dreamer.dream(
        "first",
        DreamerContext("target", 1),
        facets=(OracleFacet.O3_STRATEGY,),
        synthesize=lambda context, responses: DreamerDraft(EscapeAction.SWITCH_BASIN),
    )
    promoted = dreamer.close_transaction("first", request_promotion=True, step=1)
    assert promoted == (first,)
    dreamer.record_outcome(first.proposal_id, DreamerOutcome.VERIFIED_CONTRIBUTING)

    second = dreamer.dream(
        "second",
        DreamerContext("target", 2),
        facets=(OracleFacet.O3_STRATEGY,),
        synthesize=lambda context, responses: DreamerDraft(EscapeAction.FINE_TUNE),
    )
    blocked = dreamer.close_transaction("second", request_promotion=True, step=2)
    assert blocked == ()

    reflection = dreamer.reflection()
    assert reflection.access_bits == (0, 0, 1, 0)
    assert reflection.proposals_created == 2
    assert reflection.promotions == 1
    assert reflection.promotion_rejections == 1

    o3 = next(x for x in reflection.oracle_state if x.facet is OracleFacet.O3_STRATEGY)
    assert o3.proposals_supported == 2
    assert o3.verified_contributions == 1
    assert o3.empirical_yield == 0.5


def test_oracle_response_cannot_impersonate_another_facet():
    def bad_role(context):
        return OracleResponse(OracleFacet.O4_CERTIFICATE, advice="wrong facet")

    dreamer = LogicalDreamer(
        {OracleFacet.O1_ROLE: bad_role},
        access=OracleAccessMask.from_bits((1, 0, 0, 0)),
    )

    try:
        dreamer.consult(OracleFacet.O1_ROLE, DreamerContext("target", 0))
    except ValueError as exc:
        assert "facet" in str(exc)
    else:
        raise AssertionError("oracle response facet mismatch must be rejected")
