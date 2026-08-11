from __future__ import annotations

from .core import ALDRunner, ConjectureSpec, FormalEnvironment, RunResult
from .logic import Formula


def excluded_middle() -> Formula:
    phi = Formula.atom("φ")
    return Formula.disj(phi, Formula.neg(phi))


def classical_lem_spec() -> ConjectureSpec:
    environment = FormalEnvironment(name="ALD-LEM-01 classical propositional sanity environment")
    return ConjectureSpec(excluded_middle(), environment)


def run_classical_lem(global_budget: int = 256) -> RunResult:
    return ALDRunner(classical_lem_spec(), activation_slice=64).run(global_budget)
