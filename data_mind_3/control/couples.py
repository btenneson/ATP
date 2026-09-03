from __future__ import annotations

"""Direct communication inside each DATA MIND 3.1 settlement couple.

Messages are deliberately non-authoritative.  This module has no BANK write
method and no verifier bypass.  Mathematical content can be packaged as a
candidate for a separate verifier path, but communication itself never promotes
anything to trusted mathematical memory.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .agents import AgentProfile, SettlementRole, profile_by_name


class MessageKind(str, Enum):
    MATHEMATICAL_IDEA = "mathematical_idea"
    CANDIDATE_LEMMA = "candidate_lemma"
    PARTIAL_ROUTE = "partial_route"
    REQUEST = "request"
    WARNING = "warning"
    SEARCH_STATE = "search_state"
    STRATEGY_ASSESSMENT = "strategy_assessment"
    ADVICE = "advice"


@dataclass(frozen=True)
class VerificationCandidate:
    """Untrusted mathematical content explicitly leaving the chat channel."""

    proposer: str
    role: SettlementRole
    payload: Any
    provenance_message_seq: int


@dataclass(frozen=True)
class CoupleMessage:
    seq: int
    role: SettlementRole
    sender: str
    recipient: str
    kind: MessageKind
    content: Any
    self_aware_basis: bool = False
    mathematical_candidate: bool = False


@dataclass
class CoupleChannel:
    role: SettlementRole
    history: list[CoupleMessage] = field(default_factory=list)
    _inbox: dict[str, list[CoupleMessage]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.members = (
            profile_by_name(f"{self.role.value}1"),
            profile_by_name(f"{self.role.value}2"),
        )
        self._inbox = {p.name: [] for p in self.members}

    def _profile(self, name: str) -> AgentProfile:
        p = profile_by_name(name)
        if p.role != self.role:
            raise ValueError(f"{name} is not a member of the {self.role.value} couple")
        return p

    def partner_of(self, name: str) -> AgentProfile:
        sender = self._profile(name)
        return self.members[1] if sender.member == 1 else self.members[0]

    def send(
        self,
        *,
        sender: str,
        recipient: str,
        kind: MessageKind,
        content: Any,
        mathematical_candidate: bool = False,
        self_aware_basis: bool = False,
    ) -> CoupleMessage:
        s = self._profile(sender)
        self._profile(recipient)
        if sender == recipient:
            raise ValueError("couple communication must have a distinct recipient")
        if self_aware_basis and not s.self_aware:
            raise PermissionError(
                f"{sender} has no (c,i) self-awareness in Snapshot 001"
            )
        message = CoupleMessage(
            seq=len(self.history),
            role=self.role,
            sender=sender,
            recipient=recipient,
            kind=kind,
            content=content,
            self_aware_basis=bool(self_aware_basis),
            mathematical_candidate=bool(mathematical_candidate),
        )
        self.history.append(message)
        self._inbox[recipient].append(message)
        return message

    def tell_partner(
        self,
        sender: str,
        kind: MessageKind,
        content: Any,
        *,
        mathematical_candidate: bool = False,
    ) -> CoupleMessage:
        partner = self.partner_of(sender)
        return self.send(
            sender=sender,
            recipient=partner.name,
            kind=kind,
            content=content,
            mathematical_candidate=mathematical_candidate,
        )

    def self_aware_strategy_assessment(self, sender: str, content: Any) -> CoupleMessage:
        """X1 may tell X2 that the current strategy appears right/wrong/etc."""

        profile = self._profile(sender)
        if profile.member != 1 or not profile.self_aware:
            raise PermissionError(
                "Snapshot 001 grants (c,i)-based strategy assessment to subscript 1"
            )
        return self.send(
            sender=sender,
            recipient=self.partner_of(sender).name,
            kind=MessageKind.STRATEGY_ASSESSMENT,
            content=content,
            self_aware_basis=True,
        )

    def inbox(self, recipient: str) -> tuple[CoupleMessage, ...]:
        self._profile(recipient)
        return tuple(self._inbox[recipient])

    def verification_candidate(self, message: CoupleMessage) -> VerificationCandidate:
        """Export a marked mathematical message to a separate verifier pipeline.

        This does not verify, accept, deposit, or mutate BANK.
        """

        if message.role != self.role or message.seq >= len(self.history):
            raise ValueError("message is not from this couple channel")
        if self.history[message.seq] != message:
            raise ValueError("message provenance mismatch")
        if not message.mathematical_candidate:
            raise ValueError("message was not marked as a mathematical candidate")
        return VerificationCandidate(
            proposer=message.sender,
            role=message.role,
            payload=message.content,
            provenance_message_seq=message.seq,
        )


class FourCoupleCommunication:
    """The four direct pair channels, with no cross-role implicit broadcast."""

    def __init__(self) -> None:
        self.channels = {role: CoupleChannel(role) for role in SettlementRole}

    def channel(self, role: SettlementRole | str) -> CoupleChannel:
        if isinstance(role, str):
            role = SettlementRole(role)
        return self.channels[role]
