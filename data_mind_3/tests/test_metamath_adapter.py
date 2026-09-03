from pathlib import Path

from data_mind_3.metamath.parser import parse_database
from data_mind_3.metamath.search import SearchConfig, search_target

HERE = Path(__file__).parent


def test_parse_and_search_generic_mini():
    db = parse_database(HERE / "mini.mm")
    target = db.target("th")
    assert target.statement == ("|-", "ph")
    result = search_target(
        db,
        "th",
        SearchConfig(max_expansions=20, candidate_cap=8, timeout_s=5),
    )
    assert result.status == "CANDIDATE"
    assert result.expansions <= 3
    assert result.proof_labels == ("wph", "ax")
