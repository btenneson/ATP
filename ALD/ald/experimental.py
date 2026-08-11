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
    RunStatus,
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
    """ALD runner that activates proof-search controls and bank-visibility conditions."""

    def __init__(
        self,
        spec: ConjectureSpec,
        activation_slice: int = 64,
        profiles: Mapping[AgentId, CreativityProfile] | None = None,
        sharing_mode: str = "shared",
    ) -> None:
        if sharing_mode not in {"shared", "isolated"}:
            raise ValueError("sharing_mode must be 'shared' or 'isolated'")
        self.sharing_mode = sharing_mode
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

    def _visible_bank(self, agent_id: AgentId):
        snapshot = self.bank.snapshot()
        if self.sharing_mode == "shared":
            return snapshot
        return tuple(record for record in snapshot if record.agent == agent_id)

    def run(self, global_budget: int):
        if global_budget <= 0:
            raise ValueError("global_budget must be positive")
        used = 0
        activations = 0
        log: list[str] = [
            f"environment_hash={self.spec.environment.environment_hash}",
            f"target_hash={self.spec.target_hash}",
            f"target={self.spec.conjecture}",
            f"sharing_mode={self.sharing_mode}",
        ]
        for agent_id in (AgentId.PROVER, AgentId.REFUTER, AgentId.INDEPENDENCE):
            profile = self.profiles[agent_id]
            log.append(
                f"profile agent={agent_id.value} name={profile.name} hash={profile.profile_hash}"
            )
        try:
            while used < global_budget:
                agent_id = self.scheduler.next_agent()
                remaining = global_budget - used
                slice_budget = min(self.activation_slice, remaining)
                step = self.agents[agent_id].step(self._visible_bank(agent_id), slice_budget)
                activations += 1
                used += step.cost
                log.append(
                    f"activation={activations} agent={agent_id.value} cost={step.cost} "
                    f"used={used}/{global_budget} note={step.note}"
                )
                if step.candidate is None:
                    if step.cost == 0:
                        used += 1
                    continue

                verification = self._verify(step.candidate)
                log.append(
                    f"verify agent={agent_id.value} accepted={verification.accepted} "
                    f"reason={verification.reason}"
                )
                if not verification.accepted:
                    continue

                record = self._record(step.candidate, verification)
                deposited = self.bank.deposit(record)
                log.append(
                    f"deposit agent={agent_id.value} type={record.certificate_type} "
                    f"id={record.record_id[:12]} deposited={deposited}"
                )
                if not deposited:
                    continue

                for lemma_id in record.parent_lemma_ids:
                    self.bank.record_reuse(
                        lemma_id,
                        step.candidate.agent,
                        step.candidate.objective,
                        activations,
                        productive=True,
                    )
                    producer = next(r for r in self.bank.snapshot() if r.record_id == lemma_id)
                    log.append(
                        f"reuse lemma={lemma_id[:12]} producer={producer.agent.value} "
                        f"consumer={step.candidate.agent.value} productive=true"
                    )

                if step.candidate.settlement_label is not None:
                    return self._result(
                        RunStatus.SETTLED,
                        step.candidate.settlement_label,
                        used,
                        activations,
                        log,
                    )

            return self._result(RunStatus.BOUNDED_UNKNOWN, None, used, activations, log)
        except Exception as exc:
            log.append(f"implementation_failure={type(exc).__name__}: {exc}")
            return self._result(RunStatus.IMPLEMENTATION_FAILURE, None, used, activations, log)
