from pathlib import Path

from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig
from data_mind_3_3.costs import account_run_cost
from data_mind_3_3.dreamer import OracleAccessMask, OracleThrottle, PromotionThrottle
from data_mind_3_3.metamath.causal_bridge import (
    build_causal_dreamer,
    search_target_with_causal_dreamer,
)
from data_mind_3_2.epistemic.oracle_dynamics import OracleFacet


HERE = Path(__file__).parent
EXPECTED = ("a0", "r1", "r2", "r3", "r4", "r5")


def _smoke_verifier(proof):
    # Deliberately independent of Dreamer/oracle output.  This is a tiny fixture
    # verifier only; it is not claimed as the production Metamath verifier.
    accepted = tuple(proof) == EXPECTED
    return accepted, {
        "accepted": accepted,
        "verifier": "fixed-chain-smoke-verifier",
        "expected_length": len(EXPECTED),
    }


def test_causal_dreamer_smoke_reaches_verifier_after_real_promotion():
    db = parse_database(HERE / "dreamer_chain.mm")
    controller = AdaptiveCreativityController(interval=4)
    dreamer = build_causal_dreamer(
        access=OracleAccessMask.from_bits((1, 1, 1, 1)),
        throttles={
            OracleFacet.O1_ROLE: OracleThrottle(min_steps_between_calls=4),
            OracleFacet.O2_RESOURCE: OracleThrottle(min_steps_between_calls=4),
            OracleFacet.O3_STRATEGY: OracleThrottle(min_steps_between_calls=4),
            OracleFacet.O4_CERTIFICATE: OracleThrottle(min_steps_between_calls=4),
        },
        promotion_throttle=PromotionThrottle(max_promotions=2, min_steps_between_promotions=4),
    )
    result, bridge = search_target_with_causal_dreamer(
        db,
        "th",
        SearchConfig(max_expansions=50, candidate_cap=8, timeout_s=5),
        verify_candidate=_smoke_verifier,
        controller=controller,
        dreamer=dreamer,
    )

    assert result.status == "PROVED"
    assert result.verification["accepted"] is True
    assert result.proof_labels == EXPECTED
    assert bridge.history
    assert any(row.promotion_granted for row in bridge.history)
    assert any(row.applied for row in bridge.executor.history)
    assert dreamer.reflection().promotions >= 1

    costs = account_run_cost(
        result,
        dreamer,
        bridge.executor,
        controller=controller,
    )
    assert costs.oracle_calls >= 1
    assert costs.dreamer_proposals >= 1
    assert costs.promotion_executions >= 1
    assert costs.accounted_units >= result.expansions
