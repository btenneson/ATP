from __future__ import annotations

from dataclasses import dataclass

from data_mind_3.control.agents import DEFAULT_AGENT_PROFILES, SettlementRole

from .oracle import FiniteHorizonOracle, OracleUseMode


@dataclass(frozen=True)
class AwarenessCue:
    """Uncertified salience/routing information derived from an oracle hint."""

    target_id: str
    role: SettlementRole
    recipients: tuple[str, ...]
    source_mode: OracleUseMode
    via_professor: bool
    asserted_truth: bool = False
    certified: bool = False


class OracleAwarenessBridge:
    """Connect oracle counterfactuals to AMLD awareness without certification.

    Hidden mode leaks nothing. Professor mode addresses only the Professor-facing
    member of the matching P/R/I/C couple. Direct mode is a stronger explicit
    counterfactual and may address both members of the matching couple.
    """

    def __init__(self, oracle: FiniteHorizonOracle) -> None:
        self.oracle = oracle

    @staticmethod
    def _profiles_for_role(role: SettlementRole):
        return tuple(p for p in DEFAULT_AGENT_PROFILES if p.role is role)

    def cue(self, target_id: str, *, mode: OracleUseMode) -> AwarenessCue | None:
        hint = self.oracle.runtime_hint(target_id, mode=mode)
        if hint is None:
            return None

        profiles = self._profiles_for_role(hint.role)
        if mode is OracleUseMode.PROFESSOR_ROLE_HINT:
            recipients = tuple(p.name for p in profiles if p.professor_facing)
            via_professor = True
        elif mode is OracleUseMode.DIRECT_ROLE_HINT:
            recipients = tuple(p.name for p in profiles)
            via_professor = False
        else:  # defensive: hidden mode already returned None above
            return None

        return AwarenessCue(
            target_id=hint.target_id,
            role=hint.role,
            recipients=recipients,
            source_mode=mode,
            via_professor=via_professor,
        )
