from __future__ import annotations

import unittest

from data_mind_3.control.agents import SettlementRole
from data_mind_3.control.couples import (
    FourCoupleCommunication,
    MessageKind,
)


class CoupleCommunicationTests(unittest.TestCase):
    def test_exact_four_couples_exist(self) -> None:
        net = FourCoupleCommunication()
        self.assertEqual(set(net.channels), set(SettlementRole))
        for role in SettlementRole:
            names = tuple(p.name for p in net.channel(role).members)
            self.assertEqual(names, (f"{role.value}1", f"{role.value}2"))

    def test_subscript1_can_issue_self_aware_strategy_assessment(self) -> None:
        channel = FourCoupleCommunication().channel("P")
        msg = channel.self_aware_strategy_assessment(
            "P1", "we are not on the right strategy"
        )
        self.assertEqual(msg.sender, "P1")
        self.assertEqual(msg.recipient, "P2")
        self.assertTrue(msg.self_aware_basis)
        self.assertEqual(msg.kind, MessageKind.STRATEGY_ASSESSMENT)
        self.assertEqual(channel.inbox("P2"), (msg,))

    def test_subscript2_cannot_claim_ci_basis(self) -> None:
        channel = FourCoupleCommunication().channel("R")
        with self.assertRaises(PermissionError):
            channel.self_aware_strategy_assessment("R2", "we are on strategy")
        with self.assertRaises(PermissionError):
            channel.send(
                sender="R2",
                recipient="R1",
                kind=MessageKind.ADVICE,
                content="self-aware claim",
                self_aware_basis=True,
            )

    def test_cross_role_message_is_rejected(self) -> None:
        channel = FourCoupleCommunication().channel("I")
        with self.assertRaises(ValueError):
            channel.send(
                sender="I1",
                recipient="P2",
                kind=MessageKind.REQUEST,
                content="cross-role implicit communication is not part of this channel",
            )

    def test_math_message_requires_separate_verification_export(self) -> None:
        channel = FourCoupleCommunication().channel("C")
        msg = channel.tell_partner(
            "C1",
            MessageKind.CANDIDATE_LEMMA,
            {"statement": "candidate only"},
            mathematical_candidate=True,
        )
        candidate = channel.verification_candidate(msg)
        self.assertEqual(candidate.proposer, "C1")
        self.assertEqual(candidate.payload, {"statement": "candidate only"})
        # The communication object deliberately has no BANK/deposit method.
        self.assertFalse(hasattr(channel, "bank"))
        self.assertFalse(hasattr(channel, "deposit"))
        self.assertFalse(hasattr(channel, "promote"))

    def test_unmarked_message_cannot_be_exported_as_math_candidate(self) -> None:
        channel = FourCoupleCommunication().channel("P")
        msg = channel.tell_partner("P2", MessageKind.SEARCH_STATE, {"frontier": 9})
        with self.assertRaises(ValueError):
            channel.verification_candidate(msg)


if __name__ == "__main__":
    unittest.main()
