import math
from types import SimpleNamespace

import pytest

from data_mind_3.control.agents import (
    DEFAULT_AGENT_PROFILES,
    EscapeAction,
    profile_by_name,
)
from data_mind_3.control.futurebank import (
    FutureProposal,
    TransactionalFutureBank,
)
from data_mind_3.control.professor import Professor, ProfessorEvidence
from data_mind_3.control.reflective import ReflectiveP1Controller


def test_eight_agents_one_professor_facing_self_aware_member_per_couple():
    assert [p.name for p in DEFAULT_AGENT_PROFILES] == [
        "P1", "P2", "R1", "R2", "I1", "I2", "C1", "C2"
    ]
    for prefix in "PRIC":
        first = profile_by_name(prefix + "1")
        second = profile_by_name(prefix + "2")
        assert first.professor_facing and first.self_aware
        assert not second.professor_facing and not second.self_aware


def test_professor_cannot_coach_protected_partner_lane_by_default():
    professor = Professor()
    evidence = ProfessorEvidence(verified_structure=0.4, target_relevance=0.5)
    professor.deliver(profile_by_name("P1"), evidence)
    with pytest.raises(PermissionError):
        professor.deliver(profile_by_name("P2"), evidence)


def test_half_distance_repair_proximity():
    grade = Professor.grade(
        ProfessorEvidence(
            verified_structure=0.25,
            target_relevance=0.5,
            repair_horizon=12.0,
            repair_half_distance=6.0,
        )
    )
    assert math.isclose(grade.repair_proximity, 0.25)


def test_professor_has_no_silent_default_scalarization():
    grade = Professor.grade(
        ProfessorEvidence(verified_structure=0.5, target_relevance=0.75)
    )
    with pytest.raises(ValueError):
        grade.scalarize({})


def test_futurebank_discard_removes_entire_speculative_transaction():
    bank = TransactionalFutureBank()
    tx = bank.begin("trial-1", "P1")
    tx.add(FutureProposal("p1", "P1", EscapeAction.BACKFILL_LEMMA))
    tx.add(FutureProposal("p2", "P1", EscapeAction.TRADE_PRESENTATION))
    removed = bank.close_discard("trial-1")
    assert [p.proposal_id for p in removed] == ["p1", "p2"]
    assert bank.open_transactions == ()


def test_escape_menu_exposes_budget_and_stagnation_responses():
    expected = {
        EscapeAction.REPAIR,
        EscapeAction.BACKFILL_LEMMA,
        EscapeAction.ASK_PARTNER,
        EscapeAction.SWITCH_BASIN,
        EscapeAction.FINE_TUNE,
        EscapeAction.GROUP_INVERSE,
        EscapeAction.TRADE_PRESENTATION,
        EscapeAction.QUOTIENT,
        EscapeAction.COMPILE_MACRO,
        EscapeAction.RESTART,
        EscapeAction.FALLBACK,
    }
    assert set(EscapeAction) == expected


def test_reflective_controller_throttles_actual_professor_deliver_calls():
    controller = ReflectiveP1Controller(
        interval=16,
        professor_interval=16,
        child_play=False,
    )
    base = SimpleNamespace(
        candidate_cap=64,
        match_cap_per_candidate=8,
        free_var_completion_cap=64,
        max_depth=24,
    )

    events = []
    for expansion in range(1, 33):
        event = controller.observe_expansion(
            expansion=expansion,
            generated_total=expansion * 4,
            frontier=10,
            max_frontier=1000,
            elapsed=float(expansion),
            timeout=1000.0,
            partial_credit=0.25,
            relevance=0.5,
            base_config=base,
        )
        if event is not None:
            events.append(event)

    assert controller.actual_professor_calls == 2
    assert controller.professor_updates == 2
    assert [e["expansion"] for e in events] == [16, 32]
    assert all(e["actual_professor_call"] is True for e in events)
