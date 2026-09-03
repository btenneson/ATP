from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass(frozen=True)
class CreativityVector:
    """The 11-dimensional DATA MIND creativity vector.

    Coordinates are normalized to [0, 1].  They are conceptual controls; the
    adaptive controller maps them to implementation parameters.  Keeping this
    layer separate makes experiments interpretable even if low-level parameters
    change in future DATA MIND versions.
    """

    lemma_direction: float = 0.50
    search_breadth: float = 0.50
    search_depth: float = 0.50
    heuristic_weighting: float = 0.50
    term_ordering: float = 0.50
    goal_selection: float = 0.50
    node_selection: float = 0.50
    divergence: float = 0.50
    abstraction_level: float = 0.50
    risk_tolerance: float = 0.50
    resource_bias: float = 0.50

    def clipped(self) -> "CreativityVector":
        return CreativityVector(**{f.name: _clamp01(getattr(self, f.name)) for f in fields(self)})

    def moved(self, **deltas: float) -> "CreativityVector":
        values = asdict(self)
        for name, delta in deltas.items():
            if name not in values:
                raise KeyError(name)
            values[name] = _clamp01(values[name] + float(delta))
        return CreativityVector(**values)

    def to_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CreativityVector":
        allowed = {f.name for f in fields(cls)}
        values = {k: _clamp01(float(v)) for k, v in data.items() if k in allowed}
        return replace(cls(), **values)
