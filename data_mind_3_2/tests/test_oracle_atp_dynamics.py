from data_mind_3.control.agents import SettlementRole
from data_mind_3_2.epistemic.oracle_dynamics import (
    ALL_ORACLE_FACETS,
    FactorizedOracleATP,
    OracleATPState,
    OracleFacet,
    OraclePartition,
    OracleTransformation,
    all_oracle_partitions,
    mean_abel_increment,
    mean_abel_residual,
)


def test_four_oracle_faculties_have_exactly_15_set_partitions():
    partitions = all_oracle_partitions()
    assert len(partitions) == 15
    labels = {p.canonical_label() for p in partitions}
    assert "{1234}" in labels
    assert "{1}{2}{3}{4}" in labels
    assert "{12}{34}" in labels
    assert "{123}{4}" in labels


def test_partition_must_cover_each_oracle_exactly_once():
    try:
        OraclePartition(
            blocks=(
                frozenset({OracleFacet.O1_ROLE, OracleFacet.O2_RESOURCE}),
                frozenset({OracleFacet.O2_RESOURCE, OracleFacet.O3_STRATEGY}),
                frozenset({OracleFacet.O4_CERTIFICATE}),
            )
        )
    except ValueError as exc:
        assert "repeated" in str(exc)
    else:
        raise AssertionError("overlapping oracle partition must be rejected")


def test_factorized_oracle_atp_runs_as_controlled_ifs_with_abel_telemetry():
    state = OracleATPState(target_id="demo")

    role = OracleTransformation(
        OracleFacet.O1_ROLE,
        "classify-role",
        lambda s: s.advanced(role=SettlementRole.PROVE),
    )
    resource = OracleTransformation(
        OracleFacet.O2_RESOURCE,
        "allocate-proof",
        lambda s: s.advanced(resource_allocation=(("P1", 0.75), ("P2", 0.25))),
    )
    strategy = OracleTransformation(
        OracleFacet.O3_STRATEGY,
        "choose-strategy",
        lambda s: s.advanced(strategy="metamath_backward_search"),
    )
    certificate = OracleTransformation(
        OracleFacet.O4_CERTIFICATE,
        "propose-certificate",
        lambda s: s.advanced(candidate_certificate_ref="candidate:demo:1"),
    )

    system = FactorizedOracleATP(
        (role, resource, strategy, certificate),
        partition=OraclePartition(
            blocks=(
                frozenset({OracleFacet.O1_ROLE, OracleFacet.O2_RESOURCE, OracleFacet.O3_STRATEGY}),
                frozenset({OracleFacet.O4_CERTIFICATE}),
            )
        ),
        abel_coordinate=lambda s: float(s.step),
    )

    final_state, records = system.run(
        state,
        ("classify-role", "allocate-proof", "choose-strategy", "propose-certificate"),
    )

    assert final_state.step == 4
    assert final_state.role is SettlementRole.PROVE
    assert final_state.strategy == "metamath_backward_search"
    assert final_state.candidate_certificate_ref == "candidate:demo:1"
    assert tuple(r.facet for r in records) == ALL_ORACLE_FACETS
    assert all(r.abel is not None for r in records)
    assert all(r.abel.increment == 1.0 for r in records if r.abel is not None)
    assert all(r.abel.residual == 0.0 for r in records if r.abel is not None)
    assert mean_abel_increment(records) == 1.0
    assert mean_abel_residual(records) == 0.0


def test_abel_probe_records_nonunit_progress_without_claiming_exact_conjugacy():
    move = OracleTransformation(
        OracleFacet.O3_STRATEGY,
        "jump",
        lambda s: s.advanced(metadata={"progress": 2.5}),
    )
    system = FactorizedOracleATP(
        (move,),
        abel_coordinate=lambda s: float(s.metadata.get("progress", 0.0)),
        target_increment=1.0,
    )
    _, records = system.run(OracleATPState(target_id="x"), ("jump",))
    obs = records[0].abel
    assert obs is not None
    assert obs.increment == 2.5
    assert obs.residual == 1.5


def test_o4_state_has_candidate_only_and_no_verifier_or_bank_surface():
    state = OracleATPState(target_id="x", candidate_certificate_ref="candidate:x")
    forbidden = {
        "verified",
        "verifier_accepted",
        "bank_admitted",
        "deposit",
        "deposit_to_bank",
        "verify",
        "certify",
    }
    for name in forbidden:
        assert not hasattr(state, name)

    system = FactorizedOracleATP(())
    for name in forbidden:
        assert not hasattr(system, name)


def test_transformation_cannot_silently_change_target_or_skip_step_counter():
    change_target = OracleTransformation(
        OracleFacet.O1_ROLE,
        "bad-target",
        lambda s: OracleATPState(target_id="other", step=s.step + 1),
    )
    try:
        change_target.apply(OracleATPState(target_id="original"))
    except ValueError as exc:
        assert "target_id" in str(exc)
    else:
        raise AssertionError("target change must be rejected")

    skip_step = OracleTransformation(
        OracleFacet.O2_RESOURCE,
        "bad-step",
        lambda s: OracleATPState(target_id=s.target_id, step=s.step + 2),
    )
    try:
        skip_step.apply(OracleATPState(target_id="original"))
    except ValueError as exc:
        assert "step" in str(exc)
    else:
        raise AssertionError("non-unit transition step must be rejected")
