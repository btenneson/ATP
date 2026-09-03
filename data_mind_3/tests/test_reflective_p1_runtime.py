from types import SimpleNamespace

import math

from data_mind_3.control.reflective import (
    PROFESSOR_SCALARIZATION,
    ReflectiveP1Controller,
)


def base_config():
    return SimpleNamespace(
        candidate_cap=64,
        match_cap_per_candidate=8,
        free_var_completion_cap=64,
        max_depth=24,
    )


def test_repair_burden_proxy_is_explicit_not_exact_horizon():
    assert math.isclose(ReflectiveP1Controller.repair_burden_proxy(0.2), 4.0)
    assert math.isclose(ReflectiveP1Controller.repair_burden_proxy(1.0), 0.0)


def test_reflective_controller_is_professor_facing_self_aware_p1():
    c = ReflectiveP1Controller(interval=4, child_play=True)
    assert c.profile.name == "P1"
    assert c.profile.professor_facing
    assert c.profile.self_aware
    assert c.child_play_enabled


def test_professor_credit_drives_p1_update_and_is_historian_visible():
    c = ReflectiveP1Controller(interval=4, child_play=True)
    event = None
    for expansion in range(1, 5):
        event = c.observe_expansion(
            expansion=expansion,
            generated_total=expansion * 10,
            frontier=20,
            max_frontier=200000,
            elapsed=float(expansion),
            timeout=1800.0,
            partial_credit=0.2,
            relevance=0.75,
            base_config=base_config(),
        )

    assert event is not None
    assert math.isclose(c.repair_half_distance, 4.0)
    grade = c.last_professor_grade
    assert grade is not None
    assert math.isclose(grade.verified_structure, 0.2)
    assert math.isclose(grade.repair_proximity, 0.5)
    assert PROFESSOR_SCALARIZATION == {
        "verified_structure": 0.50,
        "repair_proximity": 0.50,
    }
    assert math.isclose(c.last_professor_credit, 0.35)
    assert event["agent"] == "P1"
    assert math.isclose(event["professor_credit"], 0.35)
    assert "professor_grade" in event
    assert event["self_awareness"]["self_aware"] is True
    assert c.professor_updates == 1
    assert c.self_awareness_updates == 1

    professor_rows = [r for r in c.history if r.get("actor") == "Professor"]
    p1_rows = [r for r in c.history if r.get("actor") == "P1"]
    assert len(professor_rows) == 1
    assert len(p1_rows) == 1
    assert "not exact repair distance" in professor_rows[0]["repair_horizon_semantics"]


def test_professor_credit_not_target_relevance_double_counted():
    c1 = ReflectiveP1Controller(interval=4, child_play=False)
    c2 = ReflectiveP1Controller(interval=4, child_play=False)
    for expansion in range(1, 5):
        c1.observe_expansion(
            expansion=expansion,
            generated_total=0,
            frontier=0,
            max_frontier=200000,
            elapsed=0.0,
            timeout=1800.0,
            partial_credit=0.25,
            relevance=0.1,
            base_config=base_config(),
        )
        c2.observe_expansion(
            expansion=expansion,
            generated_total=0,
            frontier=0,
            max_frontier=200000,
            elapsed=0.0,
            timeout=1800.0,
            partial_credit=0.25,
            relevance=0.9,
            base_config=base_config(),
        )
    assert math.isclose(c1.last_professor_credit, c2.last_professor_credit)
