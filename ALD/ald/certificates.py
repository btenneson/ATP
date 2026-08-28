from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .logic import Formula, Sequent


@dataclass(frozen=True)
class ProofNode:
    sequent: Sequent
    rule: str
    premises: tuple["ProofNode", ...] = ()
    principal: Formula | None = None


@dataclass(frozen=True)
class ProofCertificate:
    root: ProofNode


@dataclass(frozen=True)
class ModelPairCertificate:
    model_for_c: Mapping[str, bool]
    model_for_not_c: Mapping[str, bool]
