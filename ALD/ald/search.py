from __future__ import annotations

from dataclasses import dataclass
from math import log
from random import Random

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
    counterfactual_admissions: int = 0


@dataclass(frozen=True)
class _Action:
    rule: str
    principal: Formula
    premises: tuple[Sequent, ...]
    base_score: float


def _formula_size(formula: Formula) -> int:
    return 1 + sum(_formula_size(arg) for arg in formula.args)


class BackwardLKSearch:
    """Small auditable backward search for the initial propositional benchmark.

    Search actions are ranked by a transparent structural heuristic. Candidate width
    caps the ordinary active set. A seeded counterfactual mechanism may admit one
    legal action from outside that cap and try it first. Verified bank lemmas may be
    reused only through an explicit proof-carrying CUT.
    """

    def search(
        self,
        target: Sequent,
        max_expansions: int,
        bank_lemmas: tuple[ReusableLemma, ...] = (),
        *,
        candidate_width: int = 8,
        temperature: float = 0.0,
        counterfactual_admission_rate: float = 0.0,
        seed: int = 0,
    ) -> SearchResult:
        if max_expansions <= 0:
            return SearchResult(None, 0, False)
        if candidate_width <= 0:
            raise ValueError("candidate_width must be positive")
        if temperature < 0:
            raise ValueError("temperature must be nonnegative")
        if not 0 <= counterfactual_admission_rate <= 1:
            raise ValueError("counterfactual admission rate must lie in [0,1]")
        self._limit = max_expansions
        self._expansions = 0
        self._budget_hit = False
        self._candidate_width = candidate_width
        self._temperature = temperature
        self._counterfactual_rate = counterfactual_admission_rate
        self._rng = Random(seed)
        self._counterfactual_admissions = 0

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
                    self._counterfactual_admissions,
                )

        proof = self._prove(target, frozenset()) if self._expansions < self._limit else None
        return SearchResult(
            ProofCertificate(proof) if proof else None,
            self._expansions,
            frontier_exhausted=proof is None and not self._budget_hit,
            counterfactual_admissions=self._counterfactual_admissions,
        )

    def _gumbel(self) -> float:
        u = min(max(self._rng.random(), 1e-12), 1 - 1e-12)
        return -log(-log(u))

    def _actions(self, goal: Sequent) -> list[_Action]:
        actions: list[_Action] = []
        for principal in sorted(goal.succedent, key=str):
            if principal.op == "or":
                left, right = principal.args
                premise = Sequent.make(
                    goal.antecedent,
                    (goal.succedent - {principal}) | {left, right},
                )
                actions.append(_Action("OR_R", principal, (premise,), 40 - _formula_size(principal)))
            elif principal.op == "not":
                inner = principal.args[0]
                premise = Sequent.make(
                    goal.antecedent | {inner}, goal.succedent - {principal}
                )
                actions.append(_Action("NOT_R", principal, (premise,), 30 - _formula_size(principal)))

        for principal in sorted(goal.antecedent, key=str):
            if principal.op == "not":
                inner = principal.args[0]
                premise = Sequent.make(
                    goal.antecedent - {principal}, goal.succedent | {inner}
                )
                actions.append(_Action("NOT_L", principal, (premise,), 20 - _formula_size(principal)))
            elif principal.op == "or":
                left, right = principal.args
                base = goal.antecedent - {principal}
                actions.append(
                    _Action(
                        "OR_L",
                        principal,
                        (
                            Sequent.make(base | {left}, goal.succedent),
                            Sequent.make(base | {right}, goal.succedent),
                        ),
                        10 - _formula_size(principal),
                    )
                )
        return actions

    def _ranked_actions(self, goal: Sequent) -> list[_Action]:
        actions = self._actions(goal)
        if not actions:
            return []
        scored: list[tuple[float, str, str, _Action]] = []
        for action in actions:
            score = action.base_score
            if self._temperature > 0:
                score += self._temperature * self._gumbel()
            scored.append((score, action.rule, str(action.principal), action))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        ranked = [item[3] for item in scored]
        ordinary = ranked[: self._candidate_width]
        excluded = ranked[self._candidate_width :]
        if excluded and self._rng.random() < self._counterfactual_rate:
            counterfactual = self._rng.choice(excluded)
            self._counterfactual_admissions += 1
            return [counterfactual] + ordinary
        return ordinary

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

        for action in self._ranked_actions(goal):
            premise_proofs: list[ProofNode] = []
            success = True
            for premise_goal in action.premises:
                premise = self._prove(premise_goal, next_ancestors)
                if premise is None:
                    success = False
                    break
                premise_proofs.append(premise)
            if success:
                return ProofNode(
                    goal,
                    action.rule,
                    tuple(premise_proofs),
                    action.principal,
                )
        return None
