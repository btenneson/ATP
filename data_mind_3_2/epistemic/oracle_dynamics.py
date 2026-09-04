from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

from data_mind_3.control.agents import SettlementRole


class OracleFacet(str, Enum):
    """The four functional oracle coordinates of the factorized ATP view."""

    O1_ROLE = "O1_role"
    O2_RESOURCE = "O2_resource"
    O3_STRATEGY = "O3_strategy"
    O4_CERTIFICATE = "O4_certificate"


ALL_ORACLE_FACETS = (
    OracleFacet.O1_ROLE,
    OracleFacet.O2_RESOURCE,
    OracleFacet.O3_STRATEGY,
    OracleFacet.O4_CERTIFICATE,
)


@dataclass(frozen=True)
class OraclePartition:
    """A partition of O1/O2/O3/O4 into ATP components.

    For four oracle facets there are Bell(4)=15 possible set partitions.  A
    partition describes *where functions are colocated*, not communication
    topology or implementation quality.
    """

    blocks: tuple[frozenset[OracleFacet], ...]

    def __post_init__(self) -> None:
        if not self.blocks:
            raise ValueError("oracle partition must contain at least one block")
        seen: set[OracleFacet] = set()
        for block in self.blocks:
            if not block:
                raise ValueError("oracle partition blocks must be nonempty")
            overlap = seen.intersection(block)
            if overlap:
                raise ValueError(f"oracle facet repeated across blocks: {sorted(x.value for x in overlap)}")
            seen.update(block)
        if seen != set(ALL_ORACLE_FACETS):
            missing = set(ALL_ORACLE_FACETS) - seen
            extra = seen - set(ALL_ORACLE_FACETS)
            raise ValueError(
                "oracle partition must contain O1/O2/O3/O4 exactly once; "
                f"missing={sorted(x.value for x in missing)}, "
                f"extra={sorted(x.value for x in extra)}"
            )

    @property
    def component_count(self) -> int:
        return len(self.blocks)

    def canonical_label(self) -> str:
        def facet_number(f: OracleFacet) -> str:
            return f.value[1]

        normalized = []
        for block in self.blocks:
            normalized.append("".join(sorted(facet_number(f) for f in block)))
        # Order blocks by their least oracle index, matching the mathematical
        # notation used in the architecture: {123}{4}, not {4}{123}.
        normalized.sort(key=lambda x: tuple(int(c) for c in x))
        return "{" + "}{".join(normalized) + "}"


def _set_partitions(items: Sequence[OracleFacet]) -> Iterable[list[list[OracleFacet]]]:
    if not items:
        yield []
        return
    first = items[0]
    for rest in _set_partitions(items[1:]):
        yield [[first], *[list(block) for block in rest]]
        for i in range(len(rest)):
            grown = [list(block) for block in rest]
            grown[i] = [first, *grown[i]]
            yield grown


def all_oracle_partitions() -> tuple[OraclePartition, ...]:
    """Return the 15 canonical set partitions of the four oracle faculties."""

    unique: dict[tuple[tuple[str, ...], ...], OraclePartition] = {}
    for raw in _set_partitions(list(ALL_ORACLE_FACETS)):
        blocks = tuple(frozenset(block) for block in raw)
        partition = OraclePartition(blocks=blocks)
        key = tuple(
            sorted(tuple(sorted(f.value for f in block)) for block in partition.blocks)
        )
        unique[key] = partition
    return tuple(sorted(unique.values(), key=lambda p: (p.component_count, p.canonical_label())))


@dataclass(frozen=True)
class OracleATPState:
    """Finite executable state for the factorized-oracle ATP diagnostic.

    This state intentionally contains no verifier-accept or BANK-deposit flag.
    O4 may produce a *candidate* certificate reference only.  Certification and
    BANK admission remain outside this transition system.
    """

    target_id: str
    step: int = 0
    role: SettlementRole | None = None
    resource_allocation: tuple[tuple[str, float], ...] = ()
    strategy: str | None = None
    candidate_certificate_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("target_id must be nonempty")
        if self.step < 0:
            raise ValueError("step must be nonnegative")
        for name, amount in self.resource_allocation:
            if not name:
                raise ValueError("resource recipient name must be nonempty")
            if amount < 0:
                raise ValueError("resource allocations must be nonnegative")

    def advanced(self, **changes: Any) -> "OracleATPState":
        """Return a next state with the step incremented exactly once."""

        if "step" in changes:
            raise ValueError("step is managed by OracleATPState.advanced")
        return replace(self, step=self.step + 1, **changes)


@dataclass(frozen=True)
class OracleTransformation:
    """One finite state transformation associated with one oracle faculty."""

    facet: OracleFacet
    name: str
    transform: Callable[[OracleATPState], OracleATPState]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("transformation name must be nonempty")

    def apply(self, state: OracleATPState) -> OracleATPState:
        nxt = self.transform(state)
        if not isinstance(nxt, OracleATPState):
            raise TypeError("oracle transformation must return OracleATPState")
        if nxt.target_id != state.target_id:
            raise ValueError("oracle transformation may not silently change target_id")
        if nxt.step != state.step + 1:
            raise ValueError("oracle transformation must advance state.step by exactly one")
        return nxt


@dataclass(frozen=True)
class AbelObservation:
    """Observed Abel-style displacement across one executable transition.

    `coordinate` is a finite diagnostic supplied by the experiment.  The code
    does not claim an exact Abel conjugacy exists.  Residual zero means only that
    this observed transition matched the declared target increment.
    """

    step: int
    facet: OracleFacet
    transformation: str
    coordinate_before: float
    coordinate_after: float
    increment: float
    target_increment: float
    residual: float


@dataclass(frozen=True)
class TransitionRecord:
    step: int
    facet: OracleFacet
    transformation: str
    before: OracleATPState
    after: OracleATPState
    abel: AbelObservation | None = None


class FactorizedOracleATP:
    """Controlled IFS/semigroup view of O1/O2/O3/O4.

    A schedule chooses one registered transformation at a time:

        x_(n+1) = T_(sigma_n)(x_n).

    The class is diagnostic orchestration only.  It has no verifier method and
    no BANK write surface.  Its purpose is to make normally entangled ATP
    faculties explicit and measurable.
    """

    def __init__(
        self,
        transformations: Iterable[OracleTransformation],
        *,
        partition: OraclePartition | None = None,
        abel_coordinate: Callable[[OracleATPState], float] | None = None,
        target_increment: float = 1.0,
    ) -> None:
        self.partition = partition or OraclePartition(
            blocks=(frozenset(ALL_ORACLE_FACETS),)
        )
        self.abel_coordinate = abel_coordinate
        self.target_increment = float(target_increment)
        self._transformations: dict[str, OracleTransformation] = {}
        for transformation in transformations:
            if transformation.name in self._transformations:
                raise ValueError(f"duplicate transformation name: {transformation.name}")
            self._transformations[transformation.name] = transformation

    @property
    def transformation_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._transformations))

    def step(self, state: OracleATPState, transformation_name: str) -> TransitionRecord:
        try:
            transformation = self._transformations[transformation_name]
        except KeyError as exc:
            raise KeyError(f"unknown oracle transformation: {transformation_name}") from exc

        before_value = None
        if self.abel_coordinate is not None:
            before_value = float(self.abel_coordinate(state))

        nxt = transformation.apply(state)

        abel = None
        if self.abel_coordinate is not None:
            after_value = float(self.abel_coordinate(nxt))
            increment = after_value - float(before_value)
            abel = AbelObservation(
                step=nxt.step,
                facet=transformation.facet,
                transformation=transformation.name,
                coordinate_before=float(before_value),
                coordinate_after=after_value,
                increment=increment,
                target_increment=self.target_increment,
                residual=abs(increment - self.target_increment),
            )

        return TransitionRecord(
            step=nxt.step,
            facet=transformation.facet,
            transformation=transformation.name,
            before=state,
            after=nxt,
            abel=abel,
        )

    def run(
        self, state: OracleATPState, schedule: Sequence[str]
    ) -> tuple[OracleATPState, tuple[TransitionRecord, ...]]:
        records: list[TransitionRecord] = []
        cur = state
        for name in schedule:
            record = self.step(cur, name)
            records.append(record)
            cur = record.after
        return cur, tuple(records)


def mean_abel_increment(records: Iterable[TransitionRecord]) -> float | None:
    values = [record.abel.increment for record in records if record.abel is not None]
    if not values:
        return None
    return sum(values) / len(values)


def mean_abel_residual(records: Iterable[TransitionRecord]) -> float | None:
    values = [record.abel.residual for record in records if record.abel is not None]
    if not values:
        return None
    return sum(values) / len(values)
