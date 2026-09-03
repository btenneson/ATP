from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .agents import EscapeAction


class FutureTrust(str, Enum):
    SPEC = "SPEC"
    LOCAL = "LOCAL"


@dataclass(frozen=True)
class FutureProposal:
    """A represented possible future, never an accepted theorem."""

    proposal_id: str
    source_agent: str
    action: EscapeAction
    trust: FutureTrust = FutureTrust.SPEC
    estimated_cost: float | None = None
    predicted_grade: dict[str, float | None] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    payload: Any = None


@dataclass
class FutureTransaction:
    transaction_id: str
    source_agent: str
    proposals: list[FutureProposal] = field(default_factory=list)
    closed: bool = False
    disposition: str | None = None

    def add(self, proposal: FutureProposal) -> None:
        if self.closed:
            raise RuntimeError("cannot add to a closed FUTUREBANK transaction")
        if proposal.source_agent != self.source_agent:
            raise ValueError("proposal source must match transaction source agent")
        self.proposals.append(proposal)

    def discard(self) -> tuple[FutureProposal, ...]:
        """Discard the whole speculative transaction.

        This is the search-state counterpart of a real rollback: speculative
        descendants are removed together rather than merely resetting a knob.
        """

        if self.closed:
            raise RuntimeError("FUTUREBANK transaction already closed")
        self.closed = True
        self.disposition = "discard"
        removed = tuple(self.proposals)
        self.proposals.clear()
        return removed

    def propose_promotion(self) -> tuple[FutureProposal, ...]:
        """Close as promising and return proposals for external checking.

        This method does NOT deposit anything into BANK and does not invoke or
        bypass the verifier. Promotion is only a request to real computation.
        """

        if self.closed:
            raise RuntimeError("FUTUREBANK transaction already closed")
        self.closed = True
        self.disposition = "propose_promotion"
        return tuple(self.proposals)


class TransactionalFutureBank:
    """Small transactional shell for reasoned imagination."""

    def __init__(self) -> None:
        self._open: dict[str, FutureTransaction] = {}
        self.history: list[dict[str, object]] = []

    def begin(self, transaction_id: str, source_agent: str) -> FutureTransaction:
        if transaction_id in self._open:
            raise KeyError(transaction_id)
        tx = FutureTransaction(transaction_id=transaction_id, source_agent=source_agent)
        self._open[transaction_id] = tx
        self.history.append({
            "actor": "FUTUREBANK",
            "action": "begin",
            "transaction_id": transaction_id,
            "source_agent": source_agent,
        })
        return tx

    def close_discard(self, transaction_id: str) -> tuple[FutureProposal, ...]:
        tx = self._open.pop(transaction_id)
        removed = tx.discard()
        self.history.append({
            "actor": "FUTUREBANK",
            "action": "discard",
            "transaction_id": transaction_id,
            "discarded_proposals": len(removed),
        })
        return removed

    def close_for_promotion(self, transaction_id: str) -> tuple[FutureProposal, ...]:
        tx = self._open.pop(transaction_id)
        proposals = tx.propose_promotion()
        self.history.append({
            "actor": "FUTUREBANK",
            "action": "propose_promotion",
            "transaction_id": transaction_id,
            "proposal_count": len(proposals),
        })
        return proposals

    @property
    def open_transactions(self) -> tuple[str, ...]:
        return tuple(sorted(self._open))
