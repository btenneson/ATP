from __future__ import annotations

import math
import pytest

from data_mind_3.control.professor_geometry import (
    PartialCreditConfig,
    PartialCreditEvidence,
    repair_proximity,
    tenneson_partial_credit,
)


def test_exact_formula() -> None:
    cfg = PartialCreditConfig(alpha=0.3, h=2.0)
    ev = PartialCreditEvidence(q_c=0.8, H_c=4.0)
    want = 0.3 * 0.8 + 0.7 * math.exp(-2.0)
    assert tenneson_partial_credit(ev, cfg) == pytest.approx(want)


def test_zero_horizon_has_unit_repair_proximity() -> None:
    assert repair_proximity(0.0, 3.0) == pytest.approx(1.0)


def test_infinite_horizon_has_zero_repair_proximity() -> None:
    cfg = PartialCreditConfig(alpha=0.25, h=3.0)
    ev = PartialCreditEvidence(q_c=0.4, H_c=math.inf)
    assert tenneson_partial_credit(ev, cfg) == pytest.approx(0.25 * 0.4)


def test_alpha_endpoints_keep_semantics_separate() -> None:
    ev = PartialCreditEvidence(q_c=0.2, H_c=5.0)
    assert tenneson_partial_credit(ev, PartialCreditConfig(alpha=1.0, h=2.0)) == pytest.approx(0.2)
    assert tenneson_partial_credit(ev, PartialCreditConfig(alpha=0.0, h=2.0)) == pytest.approx(math.exp(-2.5))


def test_q_does_not_determine_h() -> None:
    cfg = PartialCreditConfig(alpha=0.5, h=1.0)
    a = tenneson_partial_credit(PartialCreditEvidence(q_c=0.5, H_c=1.0), cfg)
    b = tenneson_partial_credit(PartialCreditEvidence(q_c=0.5, H_c=10.0), cfg)
    assert a != b


def test_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        PartialCreditConfig(alpha=-0.1, h=1.0)
    with pytest.raises(ValueError):
        PartialCreditConfig(alpha=0.5, h=0.0)
    with pytest.raises(ValueError):
        PartialCreditEvidence(q_c=1.1, H_c=1.0)
    with pytest.raises(ValueError):
        PartialCreditEvidence(q_c=0.5, H_c=-1.0)
