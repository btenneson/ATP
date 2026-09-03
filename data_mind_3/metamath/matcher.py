from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .parser import Assertion


Substitution = dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Match:
    substitution: tuple[tuple[str, tuple[str, ...]], ...]

    def as_dict(self) -> Substitution:
        return dict(self.substitution)


def apply_substitution(statement: Iterable[str], subst: Mapping[str, tuple[str, ...]], variables: set[str]) -> tuple[str, ...]:
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


def _min_required(pattern: tuple[str, ...], start: int, variables: set[str], subst: Mapping[str, tuple[str, ...]]) -> int:
    total = 0
    for tok in pattern[start:]:
        if tok in variables:
            total += len(subst[tok]) if tok in subst else 1
        else:
            total += 1
    return total


def match_pattern(
    pattern: tuple[str, ...],
    goal: tuple[str, ...],
    candidate_variables: set[str] | frozenset[str],
    type_map: Mapping[str, str] | None = None,
    *,
    initial: Mapping[str, tuple[str, ...]] | None = None,
    max_matches: int = 8,
    max_sequence_len: int = 64,
) -> tuple[Match, ...]:
    """Generic Metamath word-pattern matching.

    Only `candidate_variables` are metavariables. The routine is deliberately
    theorem-label agnostic and can therefore be reused by proof search,
    definition-guided term proposals, and later presentation-trading modules.
    """
    if not pattern or not goal:
        return ()
    results: list[Match] = []
    type_map = dict(type_map or {})
    subst: Substitution = dict(initial or {})

    def rec(pi: int, gi: int) -> None:
        if len(results) >= max_matches:
            return
        if pi == len(pattern):
            if gi == len(goal):
                results.append(Match(tuple(sorted(subst.items()))))
            return
        if gi > len(goal):
            return
        tok = pattern[pi]
        if tok not in candidate_variables:
            if gi < len(goal) and goal[gi] == tok:
                rec(pi + 1, gi + 1)
            return

        if tok in subst:
            seq = subst[tok]
            if goal[gi:gi + len(seq)] == seq:
                rec(pi + 1, gi + len(seq))
            return

        min_after = _min_required(pattern, pi + 1, set(candidate_variables), subst)
        max_len = min(max_sequence_len, len(goal) - gi - min_after)
        if max_len < 1:
            return
        lengths = (1,) if type_map.get(tok) == "setvar" else range(1, max_len + 1)
        for n in lengths:
            seq = goal[gi:gi + n]
            if not seq:
                continue
            subst[tok] = seq
            rec(pi + 1, gi + n)
            subst.pop(tok, None)
            if len(results) >= max_matches:
                return

    rec(0, 0)
    return tuple(results)


def match_statement(
    assertion: Assertion,
    goal: tuple[str, ...],
    all_variables: set[str],
    *,
    max_matches: int = 8,
    max_sequence_len: int = 64,
) -> tuple[Match, ...]:
    """Match an assertion conclusion to a goal by Metamath substitution."""
    pattern = assertion.statement
    if not pattern or not goal or pattern[0] != goal[0]:
        return ()
    return match_pattern(
        pattern,
        goal,
        assertion.mandatory_variables,
        assertion.variable_type_map,
        max_matches=max_matches,
        max_sequence_len=max_sequence_len,
    )
