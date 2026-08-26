import unittest

from predator8_authority_adapter import (
    BoundEvidence,
    interval_from_evidence,
    assess_state,
    assess_successors,
)


class AdapterTests(unittest.TestCase):
    def test_lower_bound_only_does_not_certify_zero(self):
        d = assess_state(0.1, BoundEvidence(open_goals=0))
        self.assertEqual(d.stage, 1)

    def test_accept_certifies_zero_candidate(self):
        d = assess_state(0.0, BoundEvidence(open_goals=0, accepted=True))
        self.assertEqual(d.stage, 3)
        self.assertEqual(d.exact_shell, 0)

    def test_exact_shell_from_matching_bounds(self):
        iv = interval_from_evidence(
            BoundEvidence(open_goals=1, verified_remaining_edges=2)
        )
        self.assertEqual(iv.lower, 2)
        self.assertEqual(iv.upper, 2)

    def test_stage2_from_exact_successor_shells(self):
        d = assess_successors([
            ("good", 2.1, BoundEvidence(open_goals=1, verified_remaining_edges=2)),
            ("worse", 3.1, BoundEvidence(open_goals=2, verified_remaining_edges=3)),
        ])
        self.assertEqual(d.stage, 2)
        self.assertEqual(d.selected_keys, ("good",))

    def test_stage2_denied_without_verified_upper_bounds(self):
        d = assess_successors([
            ("a", 2.1, BoundEvidence(open_goals=1)),
            ("b", 3.1, BoundEvidence(open_goals=2)),
        ])
        self.assertEqual(d.stage, 1)


if __name__ == "__main__":
    unittest.main()
