from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from data_mind_3.control.agents import SettlementRole


class OracleUseMode(str, Enum):
    """Explicit visibility modes for the finite proxy oracle."""

    HIDDEN_GROUND_TRUTH = "hidden_ground_truth"
    PROFESSOR_ROLE_HINT = "professor_role_hint"
    DIRECT_ROLE_HINT = "direct_role_hint"


@dataclass(frozen=True)
class OracleRecord:
    """One frozen gold record inside a finite approximation to F_H.

    `role=None` represents a conceptually undefined/withheld U answer.  The
    provenance field is mandatory because declaring a role to be oracle truth
    is not itself evidence that the role is correct.
    """

    index: int
    target_id: str
    role: SettlementRole | None
    provenance: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("oracle record index must be nonnegative")
        if not self.target_id:
            raise ValueError("oracle target_id must be nonempty")
        if not self.provenance.strip():
            raise ValueError("oracle ground truth requires explicit provenance")


@dataclass(frozen=True)
class OracleHint:
    """An advisory oracle-derived cue, never a certificate."""

    target_id: str
    role: SettlementRole
    source_mode: OracleUseMode
    provenance: str
    asserted_truth: bool = False
    certified: bool = False


class FiniteHorizonOracle:
    """Executable finite proxy for the conceptual hyperfinite oracle O_H.

    The class deliberately has no BANK deposit API and no verifier-accept API.
    Hidden-ground-truth mode returns no runtime hint.  Counterfactual modes may
    expose a role only as an uncertified advisory cue.
    """

    def __init__(self, *, horizon: int, records: Iterable[OracleRecord]) -> None:
        if horizon < 0:
            raise ValueError("horizon must be nonnegative")
        self.horizon = int(horizon)
        self._by_target: dict[str, OracleRecord] = {}
        seen_indexes: set[int] = set()
        for record in records:
            if record.index > self.horizon:
                raise ValueError(
                    f"record index {record.index} exceeds finite horizon {self.horizon}"
                )
            if record.index in seen_indexes:
                raise ValueError(f"duplicate oracle index {record.index}")
            if record.target_id in self._by_target:
                raise ValueError(f"duplicate oracle target {record.target_id}")
            seen_indexes.add(record.index)
            self._by_target[record.target_id] = record

    @property
    def size(self) -> int:
        return len(self._by_target)

    def evaluator_record(self, target_id: str) -> OracleRecord:
        """Return frozen gold data to the evaluator, not to a search agent."""

        try:
            return self._by_target[target_id]
        except KeyError as exc:
            raise KeyError(f"target not in oracle horizon: {target_id}") from exc

    def runtime_hint(
        self, target_id: str, *, mode: OracleUseMode
    ) -> OracleHint | None:
        """Return an optional role cue under an explicitly selected mode."""

        if mode is OracleUseMode.HIDDEN_GROUND_TRUTH:
            return None
        record = self.evaluator_record(target_id)
        if record.role is None:
            return None
        return OracleHint(
            target_id=record.target_id,
            role=record.role,
            source_mode=mode,
            provenance=record.provenance,
        )

    def score_reported_role(
        self, target_id: str, reported_role: SettlementRole | None
    ) -> bool | None:
        """Score a reported role against gold data.

        Returns None when the oracle record is U/undefined, so an undefined gold
        item is never silently scored as a failure or success.
        """

        record = self.evaluator_record(target_id)
        if record.role is None:
            return None
        return reported_role is record.role
