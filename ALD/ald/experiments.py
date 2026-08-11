from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .core import AgentId, ConjectureSpec, CreativityProfile, RunResult
from .experimental import CreativityALDRunner


@dataclass(frozen=True)
class SharingComparison:
    shared: RunResult
    isolated: RunResult

    @property
    def expansion_savings(self) -> int:
        return self.isolated.expansions - self.shared.expansions

    @property
    def relative_expansion_reduction(self) -> float:
        if self.isolated.expansions == 0:
            return 0.0
        return self.expansion_savings / self.isolated.expansions

    @property
    def same_settlement(self) -> bool:
        return (
            self.shared.status == self.isolated.status
            and self.shared.settlement == self.isolated.settlement
        )


def matched_sharing_trial(
    spec: ConjectureSpec,
    *,
    global_budget: int,
    activation_slice: int,
    profiles: Mapping[AgentId, CreativityProfile],
) -> SharingComparison:
    """Run shared and isolated ALDs under identical declared conditions.

    The two runs are fresh instances with the same formal target, profiles, seeds,
    scheduler design, verifier, activation slice, and global budget. Only cross-agent
    visibility of verifier-certified bank records changes.
    """

    shared = CreativityALDRunner(
        spec,
        activation_slice=activation_slice,
        profiles=profiles,
        sharing_mode="shared",
    ).run(global_budget)
    isolated = CreativityALDRunner(
        spec,
        activation_slice=activation_slice,
        profiles=profiles,
        sharing_mode="isolated",
    ).run(global_budget)
    return SharingComparison(shared=shared, isolated=isolated)
