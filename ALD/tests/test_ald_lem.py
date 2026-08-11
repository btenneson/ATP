import unittest

from ald.benchmark_lem import classical_lem_spec, excluded_middle, run_classical_lem
from ald.core import ALDRunner, ConjectureSpec, FormalEnvironment, RunStatus, SettlementLabel
from ald.logic import Formula


class ALDLEMTests(unittest.TestCase):
    def test_classical_excluded_middle_is_proved(self):
        result = run_classical_lem(global_budget=256)
        self.assertEqual(result.status, RunStatus.SETTLED)
        self.assertEqual(result.settlement, SettlementLabel.PROVED)
        self.assertTrue(result.bank)
        self.assertEqual(result.bank[-1].certificate_type, "LK_PROOF")

    def test_tiny_budget_is_bounded_unknown_not_independent(self):
        result = ALDRunner(classical_lem_spec(), activation_slice=1).run(global_budget=1)
        self.assertEqual(result.status, RunStatus.BOUNDED_UNKNOWN)
        self.assertIsNone(result.settlement)

    def test_atom_is_independent_from_empty_classical_theory(self):
        p = Formula.atom("p")
        spec = ConjectureSpec(p, FormalEnvironment(name="empty classical theory"))
        result = ALDRunner(spec, activation_slice=16).run(global_budget=64)
        self.assertEqual(result.status, RunStatus.SETTLED)
        self.assertEqual(result.settlement, SettlementLabel.INDEPENDENT)
        self.assertEqual(result.bank[-1].certificate_type, "MODEL_PAIR")

    def test_negation_of_lem_is_refuted(self):
        spec = ConjectureSpec(
            Formula.neg(excluded_middle()),
            FormalEnvironment(name="classical refutation check"),
        )
        result = ALDRunner(spec, activation_slice=64).run(global_budget=256)
        self.assertEqual(result.status, RunStatus.SETTLED)
        self.assertEqual(result.settlement, SettlementLabel.REFUTED)


if __name__ == "__main__":
    unittest.main()
