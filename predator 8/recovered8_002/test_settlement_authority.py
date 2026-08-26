import unittest
import math

from settlement_authority import (
    HorizonInterval,
    SuccessorAssessment,
    open_goal_lower_bound,
    unique_integer_shell,
    certifies_half_error,
    shell_authority,
    geodesic_lock,
    partial_credit_from_h,
    pc_ratio_half_error_bound,
)


class SettlementAuthorityTests(unittest.TestCase):
    def test_open_goal_lower_bound(self):
        self.assertEqual(open_goal_lower_bound(0), 1)
        self.assertEqual(open_goal_lower_bound(3), 4)
        self.assertEqual(open_goal_lower_bound(0, accepted=True), 0)

    def test_unique_shell(self):
        self.assertEqual(unique_integer_shell(HorizonInterval(1.8, 2.2, "proof")), 2)
        self.assertIsNone(unique_integer_shell(HorizonInterval(1.0, 2.1, "proof")))
        self.assertIsNone(unique_integer_shell(HorizonInterval(3, math.inf, "lower-bound-only")))

    def test_half_error(self):
        iv = HorizonInterval(1.9, 2.1, "sound interval")
        self.assertTrue(certifies_half_error(2.0, iv))
        self.assertFalse(certifies_half_error(2.5, iv))

    def test_zero_authority(self):
        d = shell_authority(
            0.2,
            HorizonInterval(0.0, 0.0, "verifier-accepted ACCEPT state"),
        )
        self.assertEqual(d.stage, 3)
        self.assertEqual(d.exact_shell, 0)

    def test_uncertified_low_estimate_is_not_stage3(self):
        d = shell_authority(0.1, None)
        self.assertEqual(d.stage, 1)
        self.assertNotEqual(d.flag, "CERTIFIED-ZERO-CANDIDATE")

    def test_geodesic_lock(self):
        ss = [
            SuccessorAssessment("a", 2.05, HorizonInterval(2, 2, "exact shell 2")),
            SuccessorAssessment("b", 3.05, HorizonInterval(3, 3, "exact shell 3")),
        ]
        d = geodesic_lock(ss)
        self.assertEqual(d.stage, 2)
        self.assertEqual(d.selected_keys, ("a",))

    def test_geodesic_lock_denied_if_one_competitor_uncertified(self):
        ss = [
            SuccessorAssessment("a", 2.05, HorizonInterval(2, 2, "exact shell 2")),
            SuccessorAssessment("b", 3.05, None),
        ]
        d = geodesic_lock(ss)
        self.assertEqual(d.stage, 1)
        self.assertEqual(d.flag, "GEODESIC-LOCK-DENIED")

    def test_pc_shells(self):
        self.assertEqual(partial_credit_from_h(0), 1.0)
        self.assertEqual(partial_credit_from_h(1), 0.5)
        self.assertEqual(partial_credit_from_h(2), 0.25)
        self.assertAlmostEqual(pc_ratio_half_error_bound(), math.sqrt(2))

    def test_interval_requires_evidence(self):
        with self.assertRaises(ValueError):
            HorizonInterval(1, 1, "")


if __name__ == "__main__":
    unittest.main()
