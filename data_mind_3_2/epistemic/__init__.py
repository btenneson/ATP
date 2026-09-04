"""Epistemic horizon, oracle, and factorized ATP interfaces for DATA MIND 3.2."""

from .horizon import FiniteHorizonReport, finite_horizon_report
from .oracle import FiniteHorizonOracle, OracleHint, OracleRecord, OracleUseMode
from .integration import AwarenessCue, OracleAwarenessBridge
from .oracle_dynamics import (
    ALL_ORACLE_FACETS,
    AbelObservation,
    FactorizedOracleATP,
    OracleATPState,
    OracleFacet,
    OraclePartition,
    OracleTransformation,
    TransitionRecord,
    all_oracle_partitions,
    mean_abel_increment,
    mean_abel_residual,
)

__all__ = [
    "ALL_ORACLE_FACETS",
    "AbelObservation",
    "AwarenessCue",
    "FactorizedOracleATP",
    "FiniteHorizonOracle",
    "FiniteHorizonReport",
    "OracleATPState",
    "OracleAwarenessBridge",
    "OracleFacet",
    "OracleHint",
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
