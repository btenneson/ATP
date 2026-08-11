from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any

from .certificates import ModelPairCertificate, ProofCertificate
from .logic import Formula, Sequent, all_valuations
from .search import BackwardLKSearch
from .verifier import ClassicalLKVerifier, VerificationResult


class AgentId(str, Enum):
    PROVER = "P"
    REFUTER = "R"
    INDEPENDENCE = "I"


class SettlementLabel(str, Enum):
    PROVED = "PROVED"
    REFUTED = "REFUTED"
    INDEPENDENT = "INDEPENDENT"


class RunStatus(str, Enum):
    SETTLED = "SETTLED"
    BOUNDED_UNKNOWN = "BOUNDED_UNKNOWN"
    IMPLEMENTATION_FAILURE = "IMPLEMENTATION_FAILURE"


@dataclass(frozen=True)
class FormalEnvironment:
    name: str
    axioms: tuple[Formula, ...] = ()
    parser_version: str = "ald-formula-0.1"
    verifier_version: str = ClassicalLKVerifier.VERSION
    logic: str = "classical-propositional-LK"

    @property
    def environment_hash(self) -> str:
        payload = "|".join(
            [self.name, self.logic, self.parser_version, self.verifier_version]
            + sorted(map(str, self.axioms))
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConjectureSpec:
    conjecture: Formula
    environment: FormalEnvironment

    @property
    def positive_target(self) -> Sequent:
        return Sequent.make(self.environment.axioms, (self.conjecture,))

    @property
    def negative_target(self) -> Sequent:
        return Sequent.make(
            self.environment.axioms, (Formula.neg(self.conjecture),)
        )

    @property
    def target_hash(self) -> str:
        return sha256(str(self.conjecture).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateContribution:
    agent: AgentId
    objective: SettlementLabel
    certificate: ProofCertificate | ModelPairCertificate
    cost: int
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LemmaRecord:
    record_id: str
    agent: AgentId
    objective: SettlementLabel
    statement: str
    certificate_type: str
    cost: int
    verifier_version: str
    verification_reason: str
    reused_by: tuple[AgentId, ...] = ()


class SharedLemmaBank:
    def __init__(self) -> None:
        self._records: list[LemmaRecord] = []
        self._ids: set[str] = set()

    def snapshot(self) -> tuple[LemmaRecord, ...]:
        return tuple(self._records)

    def deposit(self, record: LemmaRecord) -> bool:
        if record.record_id in self._ids:
            return False
        self._records.append(record)
        self._ids.add(record.record_id)
        return True


@dataclass(frozen=True)
class AgentStepResult:
    candidate: CandidateContribution | None
    cost: int
    frontier_exhausted: bool
    note: str


class ProofAgent:
    def __init__(self, agent_id: AgentId, objective: SettlementLabel, target: Sequent):
        self.agent_id = agent_id
        self.objective = objective
        self.target = target
        self.searcher = BackwardLKSearch()

    def step(self, bank_snapshot: tuple[LemmaRecord, ...], budget_slice: int) -> AgentStepResult:
        result = self.searcher.search(self.target, budget_slice)
        candidate = None
        if result.certificate is not None:
            candidate = CandidateContribution(
                self.agent_id,
                self.objective,
                result.certificate,
                result.expansions,
                {"bank_records_visible": len(bank_snapshot)},
            )
        return AgentStepResult(
            candidate,
            result.expansions,
            result.frontier_exhausted,
            "proof found" if candidate else "no proof in this activation",
        )


class IndependenceAgent:
    def __init__(self, spec: ConjectureSpec):
        self.agent_id = AgentId.INDEPENDENCE
        self.objective = SettlementLabel.INDEPENDENT
        self.spec = spec

    def step(self, bank_snapshot: tuple[LemmaRecord, ...], budget_slice: int) -> AgentStepResult:
        formulas = self.spec.environment.axioms + (self.spec.conjecture,)
        valuations = all_valuations(formulas)
        model_c: dict[str, bool] | None = None
        model_not_c: dict[str, bool] | None = None
        cost = 0
        for valuation in valuations:
            if cost >= budget_slice:
                break
            cost += 1
            if not all(ax.evaluate(valuation) for ax in self.spec.environment.axioms):
                continue
            if self.spec.conjecture.evaluate(valuation):
                model_c = model_c or valuation
            if Formula.neg(self.spec.conjecture).evaluate(valuation):
                model_not_c = model_not_c or valuation
            if model_c is not None and model_not_c is not None:
                cert = ModelPairCertificate(model_c, model_not_c)
                return AgentStepResult(
                    CandidateContribution(
                        self.agent_id,
                        self.objective,
                        cert,
                        cost,
                        {"bank_records_visible": len(bank_snapshot)},
                    ),
                    cost,
                    False,
                    "model-pair certificate found",
                )
        frontier_exhausted = cost >= len(valuations)
        return AgentStepResult(
            None,
            cost,
            frontier_exhausted,
            "no model-pair independence certificate in this activation",
        )


class RoundRobinScheduler:
    def __init__(self, order: tuple[AgentId, ...]):
        if set(order) != {AgentId.PROVER, AgentId.REFUTER, AgentId.INDEPENDENCE}:
            raise ValueError("scheduler order must contain P, R, and I exactly once")
        self.order = order
        self.index = 0

    def next_agent(self) -> AgentId:
        agent = self.order[self.index % len(self.order)]
        self.index += 1
        return agent


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    settlement: SettlementLabel | None
    expansions: int
    activations: int
    environment_hash: str
    target_hash: str
    bank: tuple[LemmaRecord, ...]
    log: tuple[str, ...]


class ALDRunner:
    def __init__(self, spec: ConjectureSpec, activation_slice: int = 64):
        self.spec = spec
        self.activation_slice = activation_slice
        self.verifier = ClassicalLKVerifier()
        self.bank = SharedLemmaBank()
        self.agents = {
            AgentId.PROVER: ProofAgent(
                AgentId.PROVER, SettlementLabel.PROVED, spec.positive_target
            ),
            AgentId.REFUTER: ProofAgent(
                AgentId.REFUTER, SettlementLabel.REFUTED, spec.negative_target
            ),
            AgentId.INDEPENDENCE: IndependenceAgent(spec),
        }
        self.scheduler = RoundRobinScheduler(
            (AgentId.INDEPENDENCE, AgentId.REFUTER, AgentId.PROVER)
        )

    def _verify(self, candidate: CandidateContribution) -> VerificationResult:
        if isinstance(candidate.certificate, ProofCertificate):
            result = self.verifier.verify_proof(candidate.certificate)
            if not result.accepted:
                return result
            expected = (
                self.spec.positive_target
                if candidate.objective == SettlementLabel.PROVED
                else self.spec.negative_target
            )
            if candidate.certificate.root.sequent != expected:
                return VerificationResult(False, "proof root is not the declared target")
            return result
        return self.verifier.verify_model_pair(
            candidate.certificate,
            self.spec.environment.axioms,
            self.spec.conjecture,
        )

    def _record(self, candidate: CandidateContribution, verification: VerificationResult) -> LemmaRecord:
        if isinstance(candidate.certificate, ProofCertificate):
            statement = str(candidate.certificate.root.sequent)
            cert_type = "LK_PROOF"
        else:
            statement = f"independent({self.spec.conjecture})"
            cert_type = "MODEL_PAIR"
        payload = f"{candidate.agent}|{candidate.objective}|{statement}|{cert_type}"
        return LemmaRecord(
            sha256(payload.encode("utf-8")).hexdigest(),
            candidate.agent,
            candidate.objective,
            statement,
            cert_type,
            candidate.cost,
            self.verifier.VERSION,
            verification.reason,
        )

    def run(self, global_budget: int) -> RunResult:
        if global_budget <= 0:
            raise ValueError("global_budget must be positive")
        used = 0
        activations = 0
        log: list[str] = [
            f"environment_hash={self.spec.environment.environment_hash}",
            f"target_hash={self.spec.target_hash}",
            f"target={self.spec.conjecture}",
        ]
        try:
            while used < global_budget:
                agent_id = self.scheduler.next_agent()
                remaining = global_budget - used
                slice_budget = min(self.activation_slice, remaining)
                step = self.agents[agent_id].step(self.bank.snapshot(), slice_budget)
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
                self.bank.deposit(record)
                return RunResult(
                    RunStatus.SETTLED,
                    step.candidate.objective,
                    used,
                    activations,
                    self.spec.environment.environment_hash,
                    self.spec.target_hash,
                    self.bank.snapshot(),
                    tuple(log),
                )

            return RunResult(
                RunStatus.BOUNDED_UNKNOWN,
                None,
                used,
                activations,
                self.spec.environment.environment_hash,
                self.spec.target_hash,
                self.bank.snapshot(),
                tuple(log),
            )
        except Exception as exc:
            log.append(f"implementation_failure={type(exc).__name__}: {exc}")
            return RunResult(
                RunStatus.IMPLEMENTATION_FAILURE,
                None,
                used,
                activations,
                self.spec.environment.environment_hash,
                self.spec.target_hash,
                self.bank.snapshot(),
                tuple(log),
            )
