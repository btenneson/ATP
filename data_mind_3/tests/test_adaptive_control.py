from dataclasses import dataclass
from pathlib import Path

from data_mind_3.control.child import ChildKnobPlayer
from data_mind_3.control.controller import AdaptiveCreativityController
from data_mind_3.control.error import ErrorVector
from data_mind_3.control.knobs import CreativityVector
from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig, search_target

HERE = Path(__file__).parent


@dataclass(frozen=True)
class DummyConfig:
    candidate_cap: int = 64
    match_cap_per_candidate: int = 8
    free_var_completion_cap: int = 64
    max_depth: int = 24
    definition_rounds: int = 2


def test_creativity_vector_is_bounded():
    c = CreativityVector().moved(search_breadth=3.0, divergence=-3.0)
    assert c.search_breadth == 1.0
    assert c.divergence == 0.0
    assert len(c.to_dict()) == 11


def test_centered_group_inverse_is_one_minus_c():
    c = CreativityVector(search_breadth=0.17, divergence=0.82)
    d = c.inverted("search_breadth")
    assert abs(d.search_breadth - 0.83) < 1e-12
    assert d.divergence == c.divergence
    e = d.inverted("search_breadth")
    assert abs(e.search_breadth - c.search_breadth) < 1e-12
    assert e.divergence == c.divergence


def test_frontier_explosion_tightens_breadth_and_raises_guidance():
    ctl = AdaptiveCreativityController(interval=16)
    event = ctl.observe_expansion(
        expansion=16,
        generated_total=16000,
        frontier=15000,
        max_frontier=200000,
        elapsed=2.0,
        timeout=1800.0,
        partial_credit=0.48,
        relevance=0.20,
        base_config=DummyConfig(),
    )
    assert event is not None
    assert ctl.creativity.search_breadth < 0.5
    assert ctl.creativity.divergence < 0.5
    assert ctl.creativity.heuristic_weighting > 0.5
    assert ctl.creativity.search_depth > 0.5
    assert int(event["effective"]["candidate_cap"]) < 64


def test_experience_warm_starts_creativity():
    prior = [{"creativity_after": {"search_breadth": 0.23, "search_depth": 0.71}}]
    ctl = AdaptiveCreativityController(experience=prior)
    assert ctl.creativity.search_breadth == 0.23
    assert ctl.creativity.search_depth == 0.71


def test_child_fine_trial_rolls_back_when_loss_does_not_improve():
    child = ChildKnobPlayer(interval=4, trial_updates=2)
    e = ErrorVector(branch=0.0, frontier=0.6, drift=0.0, stagnation=1.0, resource=0.1, progress=0.5)
    c0 = CreativityVector()
    c1, start = child.maybe_start(expansion=16, creativity=c0, loss=0.7, error=e)
    assert start is not None
    assert start["mode"] == "fine_tune"
    assert c1 != c0
    c2, finish = child.maybe_finish(expansion=24, creativity=c1, loss=0.7)
    assert finish is not None
    assert finish["decision"] == "rollback"
    assert c2 == c0


def test_child_rare_inverse_requires_repeated_failed_fine_trials():
    child = ChildKnobPlayer(interval=4, trial_updates=2, inverse_after_rejections=4)
    e = ErrorVector(branch=0.0, frontier=0.6, drift=0.0, stagnation=1.0, resource=0.1, progress=0.5)
    c = CreativityVector(search_breadth=0.2)
    expansion = 16
    for _ in range(4):
        trial_c, start = child.maybe_start(expansion=expansion, creativity=c, loss=0.7, error=e)
        assert start is not None and start["mode"] == "fine_tune"
        expansion += 8
        c, finish = child.maybe_finish(expansion=expansion, creativity=trial_c, loss=0.7)
        assert finish is not None and finish["decision"] == "rollback"
    trial_c, start = child.maybe_start(expansion=expansion, creativity=c, loss=0.7, error=e)
    assert start is not None
    assert start["mode"] == "group_inverse"
    knob = str(start["knob"])
    assert abs(getattr(trial_c, knob) - (1.0 - getattr(c, knob))) < 1e-12


def test_child_mode_ignores_old_frontier_backlog_for_play_when_branching_is_controlled():
    ctl = AdaptiveCreativityController(interval=4, child_play=True)
    for expansion in (4, 8, 12, 16):
        event = ctl.observe_expansion(
            expansion=expansion,
            generated_total=expansion,
            frontier=120000,
            max_frontier=200000,
            elapsed=1.0,
            timeout=1800.0,
            partial_credit=0.48,
            relevance=0.99,
            base_config=DummyConfig(),
        )
    assert event is not None
    child_events = event.get("child_events", [])
    assert any(x.get("action") == "knob_trial_start" for x in child_events)


def test_adaptive_control_preserves_tiny_candidate_search():
    db = parse_database(HERE / "mini.mm")
    ctl = AdaptiveCreativityController(interval=4)
    result = search_target(
        db,
        "th",
        SearchConfig(max_expansions=20, candidate_cap=8, timeout_s=5),
        controller=ctl,
    )
    assert result.status == "CANDIDATE"
    assert result.proof_labels == ("wph", "ax")
