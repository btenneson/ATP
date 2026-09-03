from __future__ import annotations

import math
import unittest

from data_mind_3.control.professor_geometry import (
    PartialCreditConfig,
    PartialCreditEvidence,
    repair_proximity,
    tenneson_partial_credit,
)


class ProfessorGeometryTests(unittest.TestCase):
    def test_exact_formula(self) -> None:
        cfg = PartialCreditConfig(alpha=0.3, h=2.0)
        ev = PartialCreditEvidence(q_c=0.8, H_c=4.0)
        want = 0.3 * 0.8 + 0.7 * math.exp(-2.0)
        self.assertAlmostEqual(tenneson_partial_credit(ev, cfg), want)

    def test_zero_horizon_has_unit_repair_proximity(self) -> None:
        self.assertAlmostEqual(repair_proximity(0.0, 3.0), 1.0)

    def test_infinite_horizon_has_zero_repair_proximity(self) -> None:
        cfg = PartialCreditConfig(alpha=0.25, h=3.0)
        ev = PartialCreditEvidence(q_c=0.4, H_c=math.inf)
        self.assertAlmostEqual(tenneson_partial_credit(ev, cfg), 0.25 * 0.4)

    def test_alpha_endpoints_keep_semantics_separate(self) -> None:
        ev = PartialCreditEvidence(q_c=0.2, H_c=5.0)
        self.assertAlmostEqual(
            tenneson_partial_credit(ev, PartialCreditConfig(alpha=1.0, h=2.0)),
            0.2,
        )
        self.assertAlmostEqual(
            tenneson_partial_credit(ev, PartialCreditConfig(alpha=0.0, h=2.0)),
            math.exp(-2.5),
        )

    def test_q_does_not_determine_h(self) -> None:
        cfg = PartialCreditConfig(alpha=0.5, h=1.0)
        a = tenneson_partial_credit(PartialCreditEvidence(q_c=0.5, H_c=1.0), cfg)
        b = tenneson_partial_credit(PartialCreditEvidence(q_c=0.5, H_c=10.0), cfg)
        self.assertNotEqual(a, b)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            PartialCreditConfig(alpha=-0.1, h=1.0)
        with self.assertRaises(ValueError):
            PartialCreditConfig(alpha=0.5, h=0.0)
        with self.assertRaises(ValueError):
            PartialCreditEvidence(q_c=1.1, H_c=1.0)
        with self.assertRaises(ValueError):
            PartialCreditEvidence(q_c=0.5, H_c=-1.0)


if __name__ == "__main__":
    unittest.main()
