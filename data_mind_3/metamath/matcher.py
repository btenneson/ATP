from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .parser import Assertion


Substitution = dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Match:
    substitution: tuple[tuple[str, tuple[str, ...]], ...]

    def as_dict(self) -> Substitution:
        return dict(self.substitution)


def apply_substitution(statement: Iterable[str], subst: Substitution, variables: set[str]) -> tuple[str, ...]:
    out: list[str] = []
    for tok in statement:
        if tok in variables:
            seq = subst.get(tok)
            if seq is None:
                out.append(tok)
            else:
                out.extend(seq)
        else:
            out.append(tok)
    return tuple(out)


def _min_required(pattern: tuple[str, ...], start: int, variables: set[str], subst: Substitution) -> int:
    total = 0
    for tok in pattern[start:]:
        if tok in variables:
            total += len(subst[tok]) if tok in subst else 1
        else:
            total += 1
    return total


def match_statement(
    assertion: Assertion,
    goal: tuple[str, ...],
    all_variables: set[str],
    *,
    max_matches: int = 8,
    max_sequence_len: int = 48,
) -> tuple[Match, ...]:
    """Match an assertion conclusion to a concrete goal by Metamath substitution.

    This is sequence matching, not theorem-specific parsing. Candidate variables
    are metavariables; symbols in the goal are data. The later verifier remains
    the mathematical authority.
    """
    pattern = assertion.statement
    if not pattern or not goal or pattern[0] != goal[0]:
        return ()
    candidate_vars = assertion.mandatory_variables
    type_map = assertion.variable_type_map
    results: list[Match] = []

    def rec(pi: int, gi: int, subst: Substitution) -> None:
        if len(results) >= max_matches:
            return
        if pi == len(pattern):
            if gi == len(goal):
                results.append(Match(tuple(sorted(subst.items()))))
            return
        if gi > len(goal):
            return
        tok = pattern[pi]
        if tok not in candidate_vars:
            if gi < len(goal) and goal[gi] == tok:
                rec(pi + 1, gi + 1, subst)
            return

        if tok in subst:
            seq = subst[tok]
            if goal[gi:gi + len(seq)] == seq:
                rec(pi + 1, gi + len(seq), subst)
            return

        min_after = _min_required(pattern, pi + 1, candidate_vars, subst)
        max_len = min(max_sequence_len, len(goal) - gi - min_after)
        if max_len < 1:
            return
        # setvar variables can only be replaced by one symbol. Other sorts are
        # constrained later by their instantiated floating hypotheses.
        lengths = (1,) if type_map.get(tok) == "setvar" else range(1, max_len + 1)
        for n in lengths:
            seq = goal[gi:gi + n]
            if not seq:
                continue
            subst[tok] = seq
            rec(pi + 1, gi + n, subst)
            subst.pop(tok, None)
            if len(results) >= max_matches:
                return

    rec(0, 0, {})
    return tuple(results)
