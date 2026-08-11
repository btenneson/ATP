import unittest

from ald.benchmark_lem import classical_lem_spec, excluded_middle, run_classical_lem
from ald.core import (
    ALDRunner,
    AgentId,
    ConjectureSpec,
    CreativityProfile,
    FormalEnvironment,
    RunStatus,
    SettlementLabel,
)
from ald.logic import Formula


def profile(name: str, lemma_fraction: float, bank_reuse_limit: int = 8) -> CreativityProfile:
    return CreativityProfile(
        name=name,
        temperature=0.5,
        candidate_width=8,
        breadth_depth_balance=0.5,
        novelty_pressure=0.5,
        restart_rate=0.0,
        lemma_construction_budget_fraction=lemma_fraction,
        bank_reuse_limit=bank_reuse_limit,
        counterfactual_admission_rate=0.0,
        seed=1,
    )


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

    def test_verified_bank_lemma_can_be_reused_across_objectives_by_cut(self):
        p = Formula.atom("p")
        lem = Formula.disj(p, Formula.neg(p))
        target = Formula.disj(lem, p)
        spec = ConjectureSpec(target, FormalEnvironment(name="shared lemma reuse test"))
        profiles = {
            AgentId.PROVER: profile("consumer-prover", 0.0),
            AgentId.REFUTER: profile("lemma-refuter", 0.5),
            AgentId.INDEPENDENCE: profile("independence", 0.0),
        }
        result = ALDRunner(spec, activation_slice=16, profiles=profiles).run(global_budget=128)
        self.assertEqual(result.status, RunStatus.SETTLED)
        self.assertEqual(result.settlement, SettlementLabel.PROVED)
        lemma_records = [r for r in result.bank if r.certificate_type == "LK_LEMMA"]
        self.assertTrue(lemma_records)
        self.assertEqual(lemma_records[0].agent, AgentId.REFUTER)
        self.assertGreaterEqual(result.cross_objective_reuse_count, 1)
        self.assertTrue(any(e.consuming_agent == AgentId.PROVER for e in result.reuse_events))
        final_record = result.bank[-1]
        self.assertTrue(final_record.parent_lemma_ids)

    def test_profiles_are_logged_and_distinct(self):
        result = run_classical_lem(global_budget=256)
        profile_lines = [line for line in result.log if line.startswith("profile agent=")]
        self.assertEqual(len(profile_lines), 3)
        self.assertEqual(len(set(profile_lines)), 3)


if __name__ == "__main__":
    unittest.main()
