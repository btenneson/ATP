from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SettlementRole(str, Enum):
    PROVE = "P"
    REFUTE = "R"
    INDEPENDENCE = "I"
    CONTRADICTION = "C"


class EscapeAction(str, Enum):
    """Second-order options an agent may consider under stagnation.

    The enum exposes possibilities; it does not decide when any action is safe,
    legal, or worthwhile. Sentinel and the verifier retain their own roles.
    """

    REPAIR = "repair"
    BACKFILL_LEMMA = "backfill_lemma"
    ASK_PARTNER = "ask_partner"
    SWITCH_BASIN = "switch_basin"
    FINE_TUNE = "fine_tune"
    GROUP_INVERSE = "group_inverse"
    TRADE_PRESENTATION = "trade_presentation"
    QUOTIENT = "quotient"
    COMPILE_MACRO = "compile_macro"
    RESTART = "restart"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class AgentProfile:
    role: SettlementRole
    member: int
    professor_facing: bool = False
    self_aware: bool = False

    def __post_init__(self) -> None:
        if self.member not in (1, 2):
            raise ValueError("paired DATA MIND agents must have member 1 or 2")

    @property
    def name(self) -> str:
        return f"{self.role.value}{self.member}"


DEFAULT_AGENT_PROFILES: tuple[AgentProfile, ...] = tuple(
    AgentProfile(role, member, professor_facing=(member == 1), self_aware=(member == 1))
    for role in SettlementRole
    for member in (1, 2)
)


def profile_by_name(name: str) -> AgentProfile:
    for profile in DEFAULT_AGENT_PROFILES:
        if profile.name == name:
            return profile
    raise KeyError(name)


@dataclass(frozen=True)
class SelfObservation:
    """Checked operational facts available to a self-aware search agent.

    These values are about search behavior. They are never certificate facts.
    No universal stagnation threshold is embedded here; experiments must freeze
    such thresholds explicitly.
    """

    resource_spent: float
    partial_credit: float
    previous_partial_credit: float | None = None
    resource_delta: float | None = None
    bank_growth: int = 0
    futurebank_size: int = 0
    verifier_accepts: int = 0
    verifier_rejects: int = 0

    @property
    def marginal_credit_per_resource(self) -> float | None:
        if (
            self.previous_partial_credit is None
            or self.resource_delta is None
            or self.resource_delta <= 0
        ):
            return None
        return (self.partial_credit - self.previous_partial_credit) / self.resource_delta


@dataclass(frozen=True)
class AgentAdvice:
    """Advisory information delivered to a principal agent.

    `recommended_actions` are suggestions, not commands. The recipient may
    ignore them or ask its partner instead.
    """

    professor_grade: dict[str, float | None]
    recommended_actions: tuple[EscapeAction, ...] = ()
    rationale: tuple[str, ...] = ()
