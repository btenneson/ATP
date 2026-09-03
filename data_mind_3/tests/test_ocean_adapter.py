from pathlib import Path

from data_mind_3.ocean.solver import parse_ocean_tptp, shortest_path_bfs
from data_mind_3.ocean.verifier import verify_ocean_certificate


PROBLEM = """% Ocean benchmark L*=2 seed=1
% Frozen implication encoding. One graph edge = one benchmark resolution inference.
fof(start,axiom,p(n0)).
fof(e0,axiom,(p(n0) => p(n1))).
fof(e1,axiom,(p(n1) => p(n2))).
fof(e2,axiom,(p(n0) => p(n9))).
fof(goal,conjecture,p(n2)).
"""


def test_ocean_adapter_finds_and_independently_verifies_exact_depth(tmp_path: Path):
    p = tmp_path / "ocean_L2_seed1.p"
    p.write_text(PROBLEM, encoding="utf-8")
    problem = parse_ocean_tptp(p)
    assert problem.declared_depth == 2
    result = shortest_path_bfs(problem, timeout_s=5.0, breadcrumb_depth=1)
    assert result.status == "CANDIDATE"
    assert result.path == (0, 1, 2)
    assert result.certificate_transitions == 2
    vr = verify_ocean_certificate(p, result.path)
    assert vr.accepted
    assert vr.transitions == 2
    assert vr.declared_depth == 2


def test_ocean_verifier_rejects_non_edge_even_with_right_endpoints(tmp_path: Path):
    p = tmp_path / "ocean_L2_seed1.p"
    p.write_text(PROBLEM, encoding="utf-8")
    vr = verify_ocean_certificate(p, (0, 9, 2))
    assert not vr.accepted
    assert vr.reason.startswith("missing_edge")
