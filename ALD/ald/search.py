from __future__ import annotations

from dataclasses import dataclass

from .certificates import ProofCertificate, ProofNode
from .logic import Sequent


@dataclass(frozen=True)
class SearchResult:
    certificate: ProofCertificate | None
    expansions: int
    frontier_exhausted: bool


class BackwardLKSearch:
    """Small auditable backward search for the initial propositional benchmark."""

    def search(self, target: Sequent, max_expansions: int) -> SearchResult:
        if max_expansions <= 0:
            return SearchResult(None, 0, False)
        self._limit = max_expansions
        self._expansions = 0
        self._budget_hit = False
        proof = self._prove(target, frozenset())
        return SearchResult(
            ProofCertificate(proof) if proof else None,
            self._expansions,
            frontier_exhausted=proof is None and not self._budget_hit,
        )

    def _prove(self, goal: Sequent, ancestors: frozenset[Sequent]) -> ProofNode | None:
        if self._expansions >= self._limit:
            self._budget_hit = True
            return None
        self._expansions += 1

        if goal.antecedent & goal.succedent:
            return ProofNode(goal, "ID")
        if goal in ancestors:
            return None
        next_ancestors = ancestors | {goal}

        for principal in sorted(goal.succedent, key=str):
            if principal.op == "or":
                left, right = principal.args
                premise_goal = Sequent.make(
                    goal.antecedent,
                    (goal.succedent - {principal}) | {left, right},
                )
                premise = self._prove(premise_goal, next_ancestors)
                if premise:
                    return ProofNode(goal, "OR_R", (premise,), principal)
            if principal.op == "not":
                inner = principal.args[0]
                premise_goal = Sequent.make(
                    goal.antecedent | {inner},
                    goal.succedent - {principal},
                )
                premise = self._prove(premise_goal, next_ancestors)
                if premise:
                    return ProofNode(goal, "NOT_R", (premise,), principal)

        for principal in sorted(goal.antecedent, key=str):
            if principal.op == "not":
                inner = principal.args[0]
                premise_goal = Sequent.make(
                    goal.antecedent - {principal},
                    goal.succedent | {inner},
                )
                premise = self._prove(premise_goal, next_ancestors)
                if premise:
                    return ProofNode(goal, "NOT_L", (premise,), principal)
            if principal.op == "or":
                left, right = principal.args
                base = goal.antecedent - {principal}
                left_goal = Sequent.make(base | {left}, goal.succedent)
                right_goal = Sequent.make(base | {right}, goal.succedent)
                left_proof = self._prove(left_goal, next_ancestors)
                if left_proof:
                    right_proof = self._prove(right_goal, next_ancestors)
                    if right_proof:
                        return ProofNode(
                            goal, "OR_L", (left_proof, right_proof), principal
                        )

        return None
