from data_mind_3.control.agents import SettlementRole
from data_mind_3_2.epistemic.horizon import finite_horizon_report
from data_mind_3_2.epistemic.integration import OracleAwarenessBridge
from data_mind_3_2.epistemic.oracle import (
    FiniteHorizonOracle,
    OracleRecord,
    OracleUseMode,
)


def _oracle() -> FiniteHorizonOracle:
    return FiniteHorizonOracle(
        horizon=4,
        records=(
            OracleRecord(0, "p-case", SettlementRole.PROVE, "fixture: verified P"),
            OracleRecord(1, "r-case", SettlementRole.REFUTE, "fixture: verified R"),
            OracleRecord(2, "i-case", SettlementRole.INDEPENDENCE, "fixture: certified I"),
            OracleRecord(3, "c-case", SettlementRole.CONTRADICTION, "fixture: certified C"),
            OracleRecord(4, "u-case", None, "fixture: deliberately undefined U"),
        ),
    )


def test_hidden_ground_truth_leaks_no_runtime_role():
    oracle = _oracle()
    assert oracle.runtime_hint("i-case", mode=OracleUseMode.HIDDEN_GROUND_TRUTH) is None
    assert oracle.score_reported_role("i-case", SettlementRole.INDEPENDENCE) is True
    assert oracle.score_reported_role("i-case", SettlementRole.PROVE) is False


def test_professor_hint_preserves_protected_partner_lane():
    bridge = OracleAwarenessBridge(_oracle())
    cue = bridge.cue("i-case", mode=OracleUseMode.PROFESSOR_ROLE_HINT)
    assert cue is not None
    assert cue.role is SettlementRole.INDEPENDENCE
    assert cue.recipients == ("I1",)
    assert cue.via_professor is True
    assert cue.asserted_truth is False
    assert cue.certified is False


def test_direct_hint_is_explicit_stronger_counterfactual():
    bridge = OracleAwarenessBridge(_oracle())
    cue = bridge.cue("r-case", mode=OracleUseMode.DIRECT_ROLE_HINT)
    assert cue is not None
    assert cue.recipients == ("R1", "R2")
    assert cue.via_professor is False
    assert cue.certified is False


def test_undefined_u_record_produces_no_hint_and_no_binary_score():
    oracle = _oracle()
    assert oracle.runtime_hint("u-case", mode=OracleUseMode.PROFESSOR_ROLE_HINT) is None
    assert oracle.score_reported_role("u-case", None) is None


def test_oracle_requires_ground_truth_provenance():
    try:
        OracleRecord(0, "bad", SettlementRole.PROVE, "")
    except ValueError as exc:
        assert "provenance" in str(exc)
    else:
        raise AssertionError("oracle record without provenance must be rejected")


def test_finite_horizon_cost_and_coverage_proxy():
    report = finite_horizon_report(
        horizon=4,
        required=("a", "b", "c"),
        acquired=("a", "b", "c"),
        least_cost={"a": 1, "b": 3, "c": 4},
    )
    assert report.coverage == 1.0
    assert report.closure_cost == 4
    assert report.normalized_closure_cost == 1.0
    assert report.horizon_omniscient is True
    assert report.missing == ()


def test_missing_cost_does_not_fake_infinity_or_omniscience():
    report = finite_horizon_report(
        horizon=5,
        required=("a", "b"),
        acquired=("a",),
        least_cost={"a": 2},
    )
    assert report.coverage == 0.5
    assert report.closure_cost is None
    assert report.normalized_closure_cost is None
    assert report.horizon_omniscient is False
    assert report.missing == ("b",)


def test_oracle_has_no_bank_or_verifier_bypass_surface():
    oracle = _oracle()
    forbidden = {
        "deposit",
        "deposit_to_bank",
        "write_bank",
        "verify",
        "accept_certificate",
        "certify",
    }
    for name in forbidden:
        assert not hasattr(oracle, name)
