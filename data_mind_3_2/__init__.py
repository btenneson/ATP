"""DATA MIND 3.2 research interfaces.

3.2 is additive over the frozen DATA MIND 3.1 architecture.  The executable
oracle is a finite-horizon proxy for the nonstandard hyperfinite specification;
it does not claim that Python instantiates an unlimited hypernatural.

The factorized-oracle ATP layer is likewise an executable finite diagnostic:
O1/O2/O3/O4 are exposed as state transformations, optionally grouped by any of
the 15 set partitions of four faculties, with Abel-style progress telemetry.
It does not move verifier or BANK authority into the oracle network.
"""

from .epistemic import (
    ALL_ORACLE_FACETS,
    AbelObservation,
    FactorizedOracleATP,
    FiniteHorizonOracle,
    FiniteHorizonReport,
    OracleATPState,
    OracleAwarenessBridge,
    OracleFacet,
    OraclePartition,
    OracleRecord,
    OracleTransformation,
    OracleUseMode,
    TransitionRecord,
    all_oracle_partitions,
    finite_horizon_report,
    mean_abel_increment,
    mean_abel_residual,
)

__all__ = [
    "ALL_ORACLE_FACETS",
    "AbelObservation",
    "FactorizedOracleATP",
    "FiniteHorizonOracle",
    "FiniteHorizonReport",
    "OracleATPState",
    "OracleAwarenessBridge",
    "OracleFacet",
    "OraclePartition",
    "OracleRecord",
    "OracleTransformation",
    "OracleUseMode",
    "TransitionRecord",
    "all_oracle_partitions",
    "finite_horizon_report",
    "mean_abel_increment",
    "mean_abel_residual",
]
