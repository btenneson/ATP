"""DATA MIND 3.2 research interfaces.

3.2 is additive over the frozen DATA MIND 3.1 architecture.  The executable
oracle is a finite-horizon proxy for the nonstandard hyperfinite specification;
it does not claim that Python instantiates an unlimited hypernatural.
"""

from .epistemic import (
    FiniteHorizonOracle,
    FiniteHorizonReport,
    OracleRecord,
    OracleUseMode,
    OracleAwarenessBridge,
    finite_horizon_report,
)

__all__ = [
    "FiniteHorizonOracle",
    "FiniteHorizonReport",
    "OracleRecord",
    "OracleUseMode",
    "OracleAwarenessBridge",
    "finite_horizon_report",
]
