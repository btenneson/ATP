from dataclasses import dataclass
from pathlib import Path

from data_mind_3.control.controller import AdaptiveCreativityController
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
