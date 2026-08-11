from __future__ import annotations

from dataclasses import dataclass

from .certificates import ProofCertificate, ProofNode
from .logic import Formula, Sequent


@dataclass(frozen=True)
class ReusableLemma:
    lemma_id: str
    formula: Formula
    certificate: ProofCertificate


@dataclass(frozen=True)
class SearchResult:
    certificate: ProofCertificate | None
    expansions: int
    frontier_exhausted: bool
    used_lemma_ids: tuple[str, ...] = ()


class BackwardLKSearch:
    """Small auditable backward search for the initial propositional benchmark.

    Verified bank lemmas may be reused only through an explicit proof-carrying CUT.
    The historical proof of the lemma is embedded as the first CUT premise.
    """

    def search(
        self,
        target: Sequent,
        max_expansions: int,
        bank_lemmas: tuple[ReusableLemma, ...] = (),
    ) -> SearchResult:
        if max_expansions <= 0:
            return SearchResult(None, 0, False)
        self._limit = max_expansions
        self._expansions = 0
        self._budget_hit = False

        for lemma in bank_lemmas:
            if self._expansions >= self._limit:
                self._budget_hit = True
                break
            expected_lemma_root = Sequent.make(target.antecedent, (lemma.formula,))
            if lemma.certificate.root.sequent != expected_lemma_root:
                continue
            if lemma.formula in target.antecedent:
                continue
            assisted_goal = Sequent.make(
                target.antecedent | {lemma.formula}, target.succedent
            )
            assisted_proof = self._prove(assisted_goal, frozenset())
            if assisted_proof:
                cut_root = ProofNode(
                    target,
                    "CUT",
                    (lemma.certificate.root, assisted_proof),
                    lemma.formula,
                )
                return SearchResult(
                    ProofCertificate(cut_root),
                    self._expansions,
                    False,
                    (lemma.lemma_id,),
                )

        proof = self._prove(target, frozenset()) if self._expansions < self._limit else None
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
                        return ProofNode(goal, "OR_L", (left_proof, right_proof), principal)

        return None
