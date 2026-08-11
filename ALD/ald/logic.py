from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Mapping


@dataclass(frozen=True, order=True)
class Formula:
    op: str
    name: str = ""
    args: tuple["Formula", ...] = ()

    @staticmethod
    def atom(name: str) -> "Formula":
        if not name:
            raise ValueError("atom name must be non-empty")
        return Formula("atom", name=name)

    @staticmethod
    def neg(phi: "Formula") -> "Formula":
        return Formula("not", args=(phi,))

    @staticmethod
    def disj(left: "Formula", right: "Formula") -> "Formula":
        return Formula("or", args=(left, right))

    def __str__(self) -> str:
        if self.op == "atom":
            return self.name
        if self.op == "not":
            inner = self.args[0]
            return f"¬{inner}" if inner.op == "atom" else f"¬({inner})"
        if self.op == "or":
            return f"({self.args[0]} ∨ {self.args[1]})"
        raise ValueError(f"unknown formula op: {self.op}")

    def atoms(self) -> frozenset[str]:
        if self.op == "atom":
            return frozenset({self.name})
        out: set[str] = set()
        for arg in self.args:
            out.update(arg.atoms())
        return frozenset(out)

    def evaluate(self, valuation: Mapping[str, bool]) -> bool:
        if self.op == "atom":
            return bool(valuation[self.name])
        if self.op == "not":
            return not self.args[0].evaluate(valuation)
        if self.op == "or":
            return self.args[0].evaluate(valuation) or self.args[1].evaluate(valuation)
        raise ValueError(f"unknown formula op: {self.op}")


@dataclass(frozen=True)
class Sequent:
    antecedent: frozenset[Formula]
    succedent: frozenset[Formula]

    @staticmethod
    def make(
        antecedent: Iterable[Formula] = (), succedent: Iterable[Formula] = ()
    ) -> "Sequent":
        return Sequent(frozenset(antecedent), frozenset(succedent))

    def __str__(self) -> str:
        left = ", ".join(sorted(map(str, self.antecedent))) or "·"
        right = ", ".join(sorted(map(str, self.succedent))) or "·"
        return f"{left} ⇒ {right}"


def all_valuations(formulas: Iterable[Formula]) -> list[dict[str, bool]]:
    names: set[str] = set()
    for formula in formulas:
        names.update(formula.atoms())
    ordered = sorted(names)
    return [dict(zip(ordered, values)) for values in product((False, True), repeat=len(ordered))]
