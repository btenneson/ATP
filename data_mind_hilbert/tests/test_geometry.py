from itertools import product
from pathlib import Path

from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig, search_target
from data_mind_hilbert.geometry import address_premise, hilbert_distance
from data_mind_hilbert.search import search_target_geometric


ROOT = Path(__file__).resolve().parents[2]
MINI = ROOT / "data_mind_3" / "tests" / "mini.mm"


def test_hilbert_grid_is_bijection_small_cases():
    for dimension in (1, 2, 3):
        for bits in (1, 2, 3):
            side = 1 << bits
            vals = [
                hilbert_distance(tuple(point), bits)
                for point in product(range(side), repeat=dimension)
            ]
            assert sorted(vals) == list(range(side ** dimension))


def test_addresses_are_frozen_and_in_range():
    stmt = ("|-", "(", "ph", "->", "ps", ")")
    variables = {"ph", "ps"}
    for mode in ("naive", "structural"):
        a = address_premise(stmt, variables, mode=mode, bits=6)
        b = address_premise(stmt, variables, mode=mode, bits=6)
        assert a == b
        assert 0 <= a < 64


def test_off_mode_matches_production_baseline_on_mini():
    db = parse_database(MINI)
    cfg = SearchConfig(max_expansions=20, candidate_cap=8, timeout_s=5)
    baseline = search_target(db, "th", cfg)
    off = search_target_geometric(db, "th", cfg, mode="off")
    assert off.status == baseline.status == "CANDIDATE"
    assert off.proof_labels == baseline.proof_labels == ("wph", "ax")
    assert off.expansions == baseline.expansions
    assert off.generated_children == baseline.generated_children


def test_hilbert_modes_still_find_mini_candidate():
    db = parse_database(MINI)
    cfg = SearchConfig(max_expansions=20, candidate_cap=8, timeout_s=5)
    for mode in ("naive", "structural"):
        result = search_target_geometric(db, "th", cfg, mode=mode)
        assert result.status == "CANDIDATE"
        assert result.proof_labels == ("wph", "ax")
