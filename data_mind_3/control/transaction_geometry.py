from __future__ import annotations

"""Directed transaction geometry for DATA MIND 3.1.

This module implements the definitions once a scientific experiment supplies a
frozen primitive transaction set R and positive cost function w.  It does not
choose R or w and has no fallback based on open-goal counts or old partial
credit.
"""

from dataclasses import dataclass
import heapq
import math
from typing import Hashable, Iterable, Mapping

StateKey = Hashable


@dataclass(frozen=True)
class TransactionEdge:
    source: StateKey
    target: StateKey
    transaction: str
    cost: float

    def __post_init__(self) -> None:
        c = float(self.cost)
        if not math.isfinite(c) or c <= 0.0:
            raise ValueError("primitive transaction costs must be finite and positive")
        if not self.transaction:
            raise ValueError("transaction label must be nonempty")


@dataclass(frozen=True)
class ShortestTransactionPath:
    cost: float
    transactions: tuple[str, ...]
    states: tuple[StateKey, ...]


class DirectedTransactionGraph:
    """Finite explored realization of c=(F,Gamma,phi,R,w)."""

    def __init__(self, edges: Iterable[TransactionEdge] = ()) -> None:
        self._adj: dict[StateKey, list[TransactionEdge]] = {}
        self._states: set[StateKey] = set()
        for edge in edges:
            self.add(edge)

    def add(self, edge: TransactionEdge) -> None:
        self._adj.setdefault(edge.source, []).append(edge)
        self._states.add(edge.source)
        self._states.add(edge.target)

    @property
    def states(self) -> frozenset[StateKey]:
        return frozenset(self._states)

    def outgoing(self, source: StateKey) -> tuple[TransactionEdge, ...]:
        return tuple(self._adj.get(source, ()))

    def shortest_path(self, source: StateKey, target: StateKey) -> ShortestTransactionPath | None:
        """Compute d_c(source,target) and a witnessing transaction sequence."""

        if source == target:
            return ShortestTransactionPath(0.0, (), (source,))

        counter = 0
        heap: list[tuple[float, int, StateKey]] = [(0.0, counter, source)]
        best: dict[StateKey, float] = {source: 0.0}
        parent: dict[StateKey, tuple[StateKey, TransactionEdge]] = {}

        while heap:
            cost, _tie, state = heapq.heappop(heap)
            if cost != best.get(state):
                continue
            if state == target:
                break
            for edge in self._adj.get(state, ()):
                new_cost = cost + float(edge.cost)
                if new_cost < best.get(edge.target, math.inf):
                    best[edge.target] = new_cost
                    parent[edge.target] = (state, edge)
                    counter += 1
                    heapq.heappush(heap, (new_cost, counter, edge.target))

        if target not in best:
            return None

        states_rev: list[StateKey] = [target]
        tx_rev: list[str] = []
        cur = target
        while cur != source:
            prev, edge = parent[cur]
            tx_rev.append(edge.transaction)
            states_rev.append(prev)
            cur = prev
        states_rev.reverse()
        tx_rev.reverse()
        return ShortestTransactionPath(
            cost=best[target],
            transactions=tuple(tx_rev),
            states=tuple(states_rev),
        )

    def distance(self, source: StateKey, target: StateKey) -> float:
        """Directed transaction distance d_c(A,B), infinity if unreachable."""

        path = self.shortest_path(source, target)
        return math.inf if path is None else path.cost

    def repair_horizon(
        self,
        source: StateKey,
        certified_completions: Iterable[StateKey],
    ) -> tuple[float, StateKey | None, ShortestTransactionPath | None]:
        """Compute H_c(A)=inf_{P in P_c} d_c(A,P) on this finite graph."""

        best_cost = math.inf
        best_target: StateKey | None = None
        best_path: ShortestTransactionPath | None = None
        for target in certified_completions:
            path = self.shortest_path(source, target)
            if path is not None and path.cost < best_cost:
                best_cost = path.cost
                best_target = target
                best_path = path
        return best_cost, best_target, best_path


def transaction_set_cost_digest_material(edges: Iterable[TransactionEdge]) -> str:
    """Stable text suitable for hashing a frozen finite R,w realization."""

    rows = sorted(
        (repr(e.source), repr(e.target), e.transaction, format(float(e.cost), ".17g"))
        for e in edges
    )
    return "".join("\t".join(row) + "\n" for row in rows)
