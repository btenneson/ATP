from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class FiniteHorizonReport:
    """Executable finite analogue of the conceptual hyperfinite horizon.

    This object is intentionally ordinary and finite.  It must not be reported
    as an actual nonstandard standard-part/shadow computation.
    """

    horizon: int
    required_count: int
    acquired_count: int
    coverage: float
    closure_cost: int | None
    normalized_closure_cost: float | None
    horizon_omniscient: bool
    missing: tuple[str, ...]


def finite_horizon_report(
    *,
    horizon: int,
    required: Iterable[str],
    acquired: Iterable[str],
    least_cost: Mapping[str, int],
) -> FiniteHorizonReport:
    """Compute the finite-N proxy for hyperfinite epistemic closure quantities.

    `required` is the frozen set of items whose complete coverage defines the
    finite horizon test. `least_cost[x]` is an observed/certified least resource
    cost only when the caller has defensibly established such a cost.

    The finite analogue O_i(N) is returned only when every required item has a
    supplied least cost. Otherwise `closure_cost` is None rather than silently
    treating an unsolved item as infinity.
    """

    if horizon < 0:
        raise ValueError("horizon must be nonnegative")

    required_tuple = tuple(dict.fromkeys(required))
    if len(required_tuple) > horizon + 1:
        raise ValueError(
            "a finite 0..N horizon can contain at most N+1 indexed required items"
        )

    acquired_set = set(acquired)
    required_set = set(required_tuple)
    covered = required_set & acquired_set
    missing = tuple(x for x in required_tuple if x not in acquired_set)

    coverage = 1.0 if not required_tuple else len(covered) / len(required_tuple)

    costs: list[int] = []
    all_costs_known = True
    for item in required_tuple:
        if item not in least_cost:
            all_costs_known = False
            break
        cost = int(least_cost[item])
        if cost < 0:
            raise ValueError("least resource costs must be nonnegative")
        costs.append(cost)

    closure_cost: int | None
    if all_costs_known:
        closure_cost = max(costs, default=0)
    else:
        closure_cost = None

    normalized: float | None = None
    if closure_cost is not None and horizon > 0:
        normalized = closure_cost / horizon

    horizon_omniscient = (
        coverage == 1.0
        and closure_cost is not None
        and closure_cost <= horizon
    )

    return FiniteHorizonReport(
        horizon=horizon,
        required_count=len(required_tuple),
        acquired_count=len(covered),
        coverage=coverage,
        closure_cost=closure_cost,
        normalized_closure_cost=normalized,
        horizon_omniscient=horizon_omniscient,
        missing=missing,
    )
