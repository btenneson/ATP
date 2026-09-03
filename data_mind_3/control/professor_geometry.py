from __future__ import annotations

"""Exact scalar partial-credit formula from the DATA MIND 3.1 snapshot.

This module intentionally does *not* estimate transaction distance.  It accepts
q_c and H_c only after another component has computed them with the frozen
transaction context c=(F,Gamma,phi,R,w).  In particular, it never derives H_c
from q_c and contains no fallback to the historical ``1/q - 1`` surrogate.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PartialCreditConfig:
    alpha: float
    h: float

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.alpha) <= 1.0:
            raise ValueError("alpha must lie in [0,1]")
        if not math.isfinite(float(self.h)) or float(self.h) <= 0.0:
            raise ValueError("h must be a finite positive scale")


@dataclass(frozen=True)
class TransactionContextIdentity:
    """Frozen identity/provenance for c=(F,Gamma,phi,R,w).

    The hashes identify the concrete objects used by an experiment without
    pretending that this class itself computes the transaction geometry.
    """

    formal_system_sha256: str
    hypotheses_sha256: str
    target_statement_sha256: str
    transaction_set_sha256: str
    transaction_costs_sha256: str

    def __post_init__(self) -> None:
        values = (
            self.formal_system_sha256,
            self.hypotheses_sha256,
            self.target_statement_sha256,
            self.transaction_set_sha256,
            self.transaction_costs_sha256,
        )
        for value in values:
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
                raise ValueError("transaction-context identities must be SHA-256 hex strings")


@dataclass(frozen=True)
class PartialCreditEvidence:
    """Values with their intended DATA MIND 3.1 semantics.

    q_c is target-relevant locally verified structure *already present* in A.
    H_c is the directed transaction repair horizon to certified completion.
    Neither value may be silently replaced by an open-goal burden proxy.
    """

    q_c: float
    H_c: float
    context: TransactionContextIdentity | None = None

    def __post_init__(self) -> None:
        q = float(self.q_c)
        H = float(self.H_c)
        if not math.isfinite(q) or not 0.0 <= q <= 1.0:
            raise ValueError("q_c must be finite and lie in [0,1]")
        if math.isnan(H) or H < 0.0:
            raise ValueError("H_c must be nonnegative or +infinity")


def repair_proximity(H_c: float, h: float) -> float:
    """Return exp(-H_c/h), with exp(-infinity)=0."""

    H = float(H_c)
    scale = float(h)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("h must be a finite positive scale")
    if math.isnan(H) or H < 0.0:
        raise ValueError("H_c must be nonnegative or +infinity")
    if math.isinf(H):
        return 0.0
    return math.exp(-H / scale)


def tenneson_partial_credit(
    evidence: PartialCreditEvidence,
    config: PartialCreditConfig,
) -> float:
    """Compute alpha*q_c + (1-alpha)*exp(-H_c/h) exactly."""

    q = float(evidence.q_c)
    proximity = repair_proximity(evidence.H_c, config.h)
    return float(config.alpha) * q + (1.0 - float(config.alpha)) * proximity
