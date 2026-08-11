from __future__ import annotations

from typing import Mapping

from .core import (
    ALDRunner,
    AgentId,
    AgentStepResult,
    CandidateContribution,
    ConjectureSpec,
    CreativityProfile,
    LemmaRecord,
    ProofAgent,
    SettlementLabel,
)
from .logic import Formula, Sequent


class ControlledProofAgent(ProofAgent):
    """Proof agent that wires reproducible creativity-profile controls into LK search."""

    def __init__(
        self,
        agent_id: AgentId,
        objective: SettlementLabel,
        target: Sequent,
        profile: CreativityProfile,
        forbidden_lemma_formulas: frozenset[Formula],
    ) -> None:
        super().__init__(agent_id, objective, target, profile, forbidden_lemma_formulas)
        self._activation_count = 0

    def _search(self, target: Sequent, budget: int, reusable, seed_offset: int):
        return self.searcher.search(
            target,
            budget,
            reusable,
            candidate_width=self.profile.candidate_width,
            temperature=self.profile.temperature,
            counterfactual_admission_rate=self.profile.counterfactual_admission_rate,
            seed=self.profile.seed + 1009 * self._activation_count + seed_offset,
        )

    def step(self, bank_snapshot: tuple[LemmaRecord, ...], budget_slice: int) -> AgentStepResult:
        self._activation_count += 1
        if budget_slice <= 0:
            return AgentStepResult(None, 0, False, "no budget")
        reusable = self._reusable(bank_snapshot)
        used = 0

        lemma = self._next_lemma_candidate(bank_snapshot)
        fraction = self.profile.lemma_construction_budget_fraction
        if lemma is not None and fraction > 0:
            lemma_budget = max(1, min(budget_slice, int(round(budget_slice * fraction))))
            lemma_target = Sequent.make(self.target.antecedent, (lemma,))
            lemma_result = self._search(lemma_target, lemma_budget, reusable, 1)
            used += lemma_result.expansions
            self._attempted_lemmas.add(lemma)
            if lemma_result.certificate is not None:
                return AgentStepResult(
                    CandidateContribution(
                        self.agent_id,
                        self.objective,
                        lemma_result.certificate,
                        lemma_result.expansions,
                        settlement_label=None,
                        lemma_formula=lemma,
                        details={
                            "kind": "lemma",
                            "used_lemma_ids": lemma_result.used_lemma_ids,
                            "bank_records_visible": len(bank_snapshot),
                            "profile": self.profile.name,
                            "counterfactual_admissions": lemma_result.counterfactual_admissions,
                        },
                    ),
                    used,
                    False,
                    f"verified-lemma candidate found: {lemma}; "
                    f"counterfactual_admissions={lemma_result.counterfactual_admissions}",
                )

        remaining = budget_slice - used
        if remaining <= 0:
            return AgentStepResult(None, used, False, "lemma construction consumed activation")

        result = self._search(self.target, remaining, reusable, 2)
        used += result.expansions
        candidate = None
        if result.certificate is not None:
            candidate = CandidateContribution(
                self.agent_id,
                self.objective,
                result.certificate,
                used,
                settlement_label=self.objective,
                details={
                    "kind": "settlement",
                    "used_lemma_ids": result.used_lemma_ids,
                    "bank_records_visible": len(bank_snapshot),
                    "profile": self.profile.name,
                    "counterfactual_admissions": result.counterfactual_admissions,
                },
            )
        note = "proof found" if candidate else "no proof in this activation"
        note += f"; counterfactual_admissions={result.counterfactual_admissions}"
        return AgentStepResult(candidate, used, result.frontier_exhausted, note)


class CreativityALDRunner(ALDRunner):
    """ALD runner that activates the proof-search controls stored in creativity profiles."""

    def __init__(
        self,
        spec: ConjectureSpec,
        activation_slice: int = 64,
        profiles: Mapping[AgentId, CreativityProfile] | None = None,
    ) -> None:
        super().__init__(spec, activation_slice=activation_slice, profiles=profiles)
        forbidden = frozenset({spec.conjecture, Formula.neg(spec.conjecture)})
        self.agents[AgentId.PROVER] = ControlledProofAgent(
            AgentId.PROVER,
            SettlementLabel.PROVED,
            spec.positive_target,
            self.profiles[AgentId.PROVER],
            forbidden,
        )
        self.agents[AgentId.REFUTER] = ControlledProofAgent(
            AgentId.REFUTER,
            SettlementLabel.REFUTED,
            spec.negative_target,
            self.profiles[AgentId.REFUTER],
            forbidden,
        )
