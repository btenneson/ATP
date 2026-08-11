from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping

from .certificates import ModelPairCertificate, ProofCertificate
from .logic import Formula, Sequent, all_valuations
from .search import BackwardLKSearch, ReusableLemma
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
class CreativityProfile:
    """Reproducible search-control profile.

    candidate_width, lemma_construction_budget_fraction, and bank_reuse_limit are
    operational in this bootstrap. Temperature, breadth/depth balance, novelty
    pressure, restart rate, and counterfactual admission are recorded now so the
    next ranked-search layer can activate them without changing the experiment schema.
    """

    name: str
    temperature: float
    candidate_width: int
    breadth_depth_balance: float
    novelty_pressure: float
    restart_rate: float
    lemma_construction_budget_fraction: float
    bank_reuse_limit: int
    counterfactual_admission_rate: float
    seed: int

    def __post_init__(self) -> None:
        if self.temperature < 0:
            raise ValueError("temperature must be nonnegative")
        if self.candidate_width <= 0:
            raise ValueError("candidate_width must be positive")
        if not 0 <= self.breadth_depth_balance <= 1:
            raise ValueError("breadth_depth_balance must lie in [0,1]")
        if not 0 <= self.novelty_pressure <= 1:
            raise ValueError("novelty_pressure must lie in [0,1]")
        if not 0 <= self.restart_rate <= 1:
            raise ValueError("restart_rate must lie in [0,1]")
        if not 0 <= self.lemma_construction_budget_fraction <= 1:
            raise ValueError("lemma construction fraction must lie in [0,1]")
        if self.bank_reuse_limit < 0:
            raise ValueError("bank_reuse_limit must be nonnegative")
        if not 0 <= self.counterfactual_admission_rate <= 1:
            raise ValueError("counterfactual admission rate must lie in [0,1]")

    @property
    def profile_hash(self) -> str:
        return sha256(repr(self).encode("utf-8")).hexdigest()


DEFAULT_PROFILES: Mapping[AgentId, CreativityProfile] = {
    AgentId.PROVER: CreativityProfile(
        name="focused-prover",
        temperature=0.20,
        candidate_width=8,
        breadth_depth_balance=0.35,
        novelty_pressure=0.30,
        restart_rate=0.05,
        lemma_construction_budget_fraction=0.15,
        bank_reuse_limit=8,
        counterfactual_admission_rate=0.05,
        seed=101,
    ),
    AgentId.REFUTER: CreativityProfile(
        name="exploratory-refuter",
        temperature=0.60,
        candidate_width=12,
        breadth_depth_balance=0.65,
        novelty_pressure=0.65,
        restart_rate=0.15,
        lemma_construction_budget_fraction=0.30,
        bank_reuse_limit=12,
        counterfactual_admission_rate=0.15,
        seed=202,
    ),
    AgentId.INDEPENDENCE: CreativityProfile(
        name="model-diversity-independence",
        temperature=0.85,
        candidate_width=16,
        breadth_depth_balance=0.80,
        novelty_pressure=0.80,
        restart_rate=0.20,
        lemma_construction_budget_fraction=0.00,
        bank_reuse_limit=16,
        counterfactual_admission_rate=0.20,
        seed=303,
    ),
}


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
        return Sequent.make(self.environment.axioms, (Formula.neg(self.conjecture),))

    @property
    def target_hash(self) -> str:
        return sha256(str(self.conjecture).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateContribution:
    agent: AgentId
    objective: SettlementLabel
    certificate: ProofCertificate | ModelPairCertificate
    cost: int
    settlement_label: SettlementLabel | None = None
    lemma_formula: Formula | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LemmaRecord:
    record_id: str
    agent: AgentId
    objective: SettlementLabel
    statement: str
    formula: Formula | None
    certificate_type: str
    certificate: ProofCertificate | ModelPairCertificate
    cost: int
    verifier_version: str
    verification_reason: str
    parent_lemma_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LemmaUseEvent:
    lemma_id: str
    producing_agent: AgentId
    producing_objective: SettlementLabel
    consuming_agent: AgentId
    consuming_objective: SettlementLabel
    activation: int
    productive: bool

    @property
    def cross_objective(self) -> bool:
        return self.producing_objective != self.consuming_objective


class SharedLemmaBank:
    def __init__(self) -> None:
        self._records: list[LemmaRecord] = []
        self._ids: set[str] = set()
        self._by_id: dict[str, LemmaRecord] = {}
        self._reuse_events: list[LemmaUseEvent] = []

    def snapshot(self) -> tuple[LemmaRecord, ...]:
        return tuple(self._records)

    def reuse_events(self) -> tuple[LemmaUseEvent, ...]:
        return tuple(self._reuse_events)

    def deposit(self, record: LemmaRecord) -> bool:
        if record.record_id in self._ids:
            return False
        self._records.append(record)
        self._ids.add(record.record_id)
        self._by_id[record.record_id] = record
        return True

    def record_reuse(
        self,
        lemma_id: str,
        consuming_agent: AgentId,
        consuming_objective: SettlementLabel,
        activation: int,
        productive: bool,
    ) -> None:
        record = self._by_id.get(lemma_id)
        if record is None:
            raise KeyError(f"unknown lemma id {lemma_id}")
        self._reuse_events.append(
            LemmaUseEvent(
                lemma_id,
                record.agent,
                record.objective,
                consuming_agent,
                consuming_objective,
                activation,
                productive,
            )
        )


@dataclass(frozen=True)
class AgentStepResult:
    candidate: CandidateContribution | None
    cost: int
    frontier_exhausted: bool
    note: str


def _tautology_candidates(target: Sequent) -> tuple[Formula, ...]:
    names: set[str] = set()
    for formula in target.antecedent | target.succedent:
        names.update(formula.atoms())
    return tuple(
        Formula.disj(Formula.atom(name), Formula.neg(Formula.atom(name)))
        for name in sorted(names)
    )


class ProofAgent:
    def __init__(
        self,
        agent_id: AgentId,
        objective: SettlementLabel,
        target: Sequent,
        profile: CreativityProfile,
        forbidden_lemma_formulas: frozenset[Formula],
    ):
        self.agent_id = agent_id
        self.objective = objective
        self.target = target
        self.profile = profile
        self.searcher = BackwardLKSearch()
        self._lemma_candidates = tuple(
            formula
            for formula in _tautology_candidates(target)
            if formula not in forbidden_lemma_formulas
        )
        self._attempted_lemmas: set[Formula] = set()

    def _reusable(self, bank_snapshot: tuple[LemmaRecord, ...]) -> tuple[ReusableLemma, ...]:
        reusable: list[ReusableLemma] = []
        for record in bank_snapshot:
            if record.formula is None or not isinstance(record.certificate, ProofCertificate):
                continue
            reusable.append(ReusableLemma(record.record_id, record.formula, record.certificate))
            if len(reusable) >= self.profile.bank_reuse_limit:
                break
        return tuple(reusable)

    def _next_lemma_candidate(self, bank_snapshot: tuple[LemmaRecord, ...]) -> Formula | None:
        bank_formulas = {r.formula for r in bank_snapshot if r.formula is not None}
        for formula in self._lemma_candidates[: self.profile.candidate_width]:
            if formula in self._attempted_lemmas or formula in bank_formulas:
                continue
            return formula
        return None

    def step(self, bank_snapshot: tuple[LemmaRecord, ...], budget_slice: int) -> AgentStepResult:
        if budget_slice <= 0:
            return AgentStepResult(None, 0, False, "no budget")
        reusable = self._reusable(bank_snapshot)
        used = 0

        lemma = self._next_lemma_candidate(bank_snapshot)
        fraction = self.profile.lemma_construction_budget_fraction
        if lemma is not None and fraction > 0:
            lemma_budget = max(1, min(budget_slice, int(round(budget_slice * fraction))))
            lemma_target = Sequent.make(self.target.antecedent, (lemma,))
            lemma_result = self.searcher.search(lemma_target, lemma_budget, reusable)
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
                        },
                    ),
                    used,
                    False,
                    f"verified-lemma candidate found: {lemma}",
                )

        remaining = budget_slice - used
        if remaining <= 0:
            return AgentStepResult(None, used, False, "lemma construction consumed activation")

        result = self.searcher.search(self.target, remaining, reusable)
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
                },
            )
        return AgentStepResult(
            candidate,
            used,
            result.frontier_exhausted,
            "proof found" if candidate else "no proof in this activation",
        )


class IndependenceAgent:
    def __init__(self, spec: ConjectureSpec, profile: CreativityProfile):
        self.agent_id = AgentId.INDEPENDENCE
        self.objective = SettlementLabel.INDEPENDENT
        self.spec = spec
        self.profile = profile

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
                        settlement_label=SettlementLabel.INDEPENDENT,
                        details={
                            "kind": "settlement",
                            "bank_records_visible": len(bank_snapshot),
                            "profile": self.profile.name,
                        },
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
    reuse_events: tuple[LemmaUseEvent, ...]
    log: tuple[str, ...]

    @property
    def cross_objective_reuse_count(self) -> int:
        return sum(event.cross_objective and event.productive for event in self.reuse_events)

    @property
    def verified_lemma_cost(self) -> int:
        return sum(record.cost for record in self.bank if record.certificate_type == "LK_LEMMA")

    @property
    def cross_objective_reuse_efficiency(self) -> float:
        cost = self.verified_lemma_cost
        return self.cross_objective_reuse_count / cost if cost else 0.0


class ALDRunner:
    def __init__(
        self,
        spec: ConjectureSpec,
        activation_slice: int = 64,
        profiles: Mapping[AgentId, CreativityProfile] | None = None,
    ):
        self.spec = spec
        self.activation_slice = activation_slice
        self.verifier = ClassicalLKVerifier()
        self.bank = SharedLemmaBank()
        profiles = dict(DEFAULT_PROFILES if profiles is None else profiles)
        if set(profiles) != {AgentId.PROVER, AgentId.REFUTER, AgentId.INDEPENDENCE}:
            raise ValueError("profiles must contain P, R, and I exactly once")
        self.profiles = profiles
        forbidden = frozenset({spec.conjecture, Formula.neg(spec.conjecture)})
        self.agents = {
            AgentId.PROVER: ProofAgent(
                AgentId.PROVER,
                SettlementLabel.PROVED,
                spec.positive_target,
                profiles[AgentId.PROVER],
                forbidden,
            ),
            AgentId.REFUTER: ProofAgent(
                AgentId.REFUTER,
                SettlementLabel.REFUTED,
                spec.negative_target,
                profiles[AgentId.REFUTER],
                forbidden,
            ),
            AgentId.INDEPENDENCE: IndependenceAgent(spec, profiles[AgentId.INDEPENDENCE]),
        }
        self.scheduler = RoundRobinScheduler(
            (AgentId.INDEPENDENCE, AgentId.REFUTER, AgentId.PROVER)
        )

    def _verify(self, candidate: CandidateContribution) -> VerificationResult:
        if isinstance(candidate.certificate, ProofCertificate):
            result = self.verifier.verify_proof(candidate.certificate)
            if not result.accepted:
                return result
            if candidate.settlement_label == SettlementLabel.PROVED:
                expected = self.spec.positive_target
            elif candidate.settlement_label == SettlementLabel.REFUTED:
                expected = self.spec.negative_target
            elif candidate.settlement_label is None and candidate.lemma_formula is not None:
                expected = Sequent.make(self.spec.environment.axioms, (candidate.lemma_formula,))
            else:
                return VerificationResult(False, "invalid proof contribution classification")
            if candidate.certificate.root.sequent != expected:
                return VerificationResult(False, "proof root is not the declared contribution target")
            return result
        if candidate.settlement_label != SettlementLabel.INDEPENDENT:
            return VerificationResult(False, "model pair may only certify independence")
        return self.verifier.verify_model_pair(
            candidate.certificate,
            self.spec.environment.axioms,
            self.spec.conjecture,
        )

    def _record(self, candidate: CandidateContribution, verification: VerificationResult) -> LemmaRecord:
        if isinstance(candidate.certificate, ProofCertificate):
            if candidate.lemma_formula is not None:
                statement = str(candidate.lemma_formula)
                cert_type = "LK_LEMMA"
                formula = candidate.lemma_formula
            else:
                statement = str(candidate.certificate.root.sequent)
                cert_type = "LK_PROOF"
                formula = None
        else:
            statement = f"independent({self.spec.conjecture})"
            cert_type = "MODEL_PAIR"
            formula = None
        parents = tuple(candidate.details.get("used_lemma_ids", ()))
        payload = (
            f"{candidate.agent}|{candidate.objective}|{statement}|{cert_type}|"
            f"{','.join(parents)}"
        )
        return LemmaRecord(
            sha256(payload.encode("utf-8")).hexdigest(),
            candidate.agent,
            candidate.objective,
            statement,
            formula,
            cert_type,
            candidate.certificate,
            candidate.cost,
            self.verifier.VERSION,
            verification.reason,
            parents,
        )

    def _result(
        self,
        status: RunStatus,
        settlement: SettlementLabel | None,
        used: int,
        activations: int,
        log: list[str],
    ) -> RunResult:
        return RunResult(
            status,
            settlement,
            used,
            activations,
            self.spec.environment.environment_hash,
            self.spec.target_hash,
            self.bank.snapshot(),
            self.bank.reuse_events(),
            tuple(log),
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
