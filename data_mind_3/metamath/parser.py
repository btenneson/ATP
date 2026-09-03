from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Hypothesis:
    label: str
    kind: str  # $f or $e
    statement: tuple[str, ...]
    order: int
    variable: str | None = None
    typecode: str | None = None


@dataclass(frozen=True)
class Assertion:
    label: str
    kind: str  # $a or $p
    statement: tuple[str, ...]
    mandatory_hypotheses: tuple[Hypothesis, ...]
    mandatory_variables: frozenset[str]
    variable_types: tuple[tuple[str, str], ...]
    disjoint_pairs: frozenset[tuple[str, str]]
    order: int

    @property
    def variable_type_map(self) -> dict[str, str]:
        return dict(self.variable_types)


@dataclass
class Database:
    constants: set[str]
    variables: set[str]
    hypotheses: dict[str, Hypothesis]
    assertions: list[Assertion]
    by_label: dict[str, Hypothesis | Assertion]

    def target(self, label: str) -> Assertion:
        obj = self.by_label.get(label)
        if not isinstance(obj, Assertion):
            raise KeyError(f"assertion not found: {label}")
        return obj

    def assertions_before(self, target: Assertion) -> tuple[Assertion, ...]:
        return tuple(a for a in self.assertions if a.order < target.order)


class ParseError(RuntimeError):
    pass


def _tokenize(path: Path) -> Iterator[str]:
    """Streaming-ish tokenizer for a monolithic Metamath database.

    The historical set.mm used by Experiment 004 is monolithic, so includes are
    intentionally rejected instead of silently loading a different source tree.
    """
    in_comment = False
    with path.open("r", encoding="utf-8", errors="strict") as fh:
        for line in fh:
            parts = line.split()
            i = 0
            while i < len(parts):
                tok = parts[i]
                if in_comment:
                    if tok == "$)":
                        in_comment = False
                    i += 1
                    continue
                if tok == "$(":
                    in_comment = True
                    i += 1
                    continue
                yield tok
                i += 1
    if in_comment:
        raise ParseError("unterminated Metamath comment")


def parse_database(path: str | Path) -> Database:
    path = Path(path)
    toks = iter(_tokenize(path))
    constants: set[str] = set()
    variables: set[str] = set()
    hypotheses: dict[str, Hypothesis] = {}
    assertions: list[Assertion] = []
    by_label: dict[str, Hypothesis | Assertion] = {}

    active_f: list[Hypothesis] = []
    active_e: list[Hypothesis] = []
    active_d: list[tuple[str, str]] = []
    scopes: list[tuple[int, int, int]] = []
    order = 0

    def read_until(stop: str) -> list[str]:
        out: list[str] = []
        for t in toks:
            if t == stop:
                return out
            out.append(t)
        raise ParseError(f"unexpected EOF looking for {stop}")

    for tok in toks:
        if tok == "${":
            scopes.append((len(active_f), len(active_e), len(active_d)))
            continue
        if tok == "$}":
            if not scopes:
                raise ParseError("unmatched $}")
            nf, ne, nd = scopes.pop()
            del active_f[nf:]
            del active_e[ne:]
            del active_d[nd:]
            continue
        if tok == "$[":
            raise ParseError(
                "file inclusion encountered; Experiment 004 requires the frozen monolithic set.mm"
            )
        if tok == "$c":
            constants.update(read_until("$."))
            continue
        if tok == "$v":
            variables.update(read_until("$."))
            continue
        if tok == "$d":
            vs = read_until("$.")
            for a, b in combinations(vs, 2):
                active_d.append(tuple(sorted((a, b))))
            continue
        if tok.startswith("$"):
            raise ParseError(f"unexpected token {tok}")

        label = tok
        try:
            kind = next(toks)
        except StopIteration as e:
            raise ParseError(f"EOF after label {label}") from e
        if label in by_label:
            raise ParseError(f"duplicate label {label}")

        order += 1
        if kind in ("$f", "$e"):
            stmt = tuple(read_until("$."))
            if kind == "$f":
                if len(stmt) != 2:
                    raise ParseError(f"malformed $f {label}: {stmt}")
                typecode, var = stmt
                h = Hypothesis(label, kind, stmt, order, var, typecode)
                active_f.append(h)
            else:
                h = Hypothesis(label, kind, stmt, order)
                active_e.append(h)
            hypotheses[label] = h
            by_label[label] = h
            continue

        if kind not in ("$a", "$p"):
            raise ParseError(f"unsupported labelled statement {label} {kind}")

        stmt_parts: list[str] = []
        if kind == "$a":
            stmt_parts = read_until("$.")
        else:
            for t in toks:
                if t == "$=":
                    break
                stmt_parts.append(t)
            else:
                raise ParseError(f"EOF before proof of {label}")
            # Deliberately discard theorem proof: the search layer never sees it.
            read_until("$.")

        stmt = tuple(stmt_parts)
        mandatory_vars = {t for t in stmt if t in variables}
        for eh in active_e:
            mandatory_vars.update(t for t in eh.statement if t in variables)

        mandatory_h: list[Hypothesis] = [
            h for h in active_f if h.variable in mandatory_vars
        ] + list(active_e)
        mandatory_h.sort(key=lambda h: h.order)

        var_types = []
        for h in mandatory_h:
            if h.kind == "$f" and h.variable is not None and h.typecode is not None:
                var_types.append((h.variable, h.typecode))

        dvs = frozenset(
            pair for pair in active_d if pair[0] in mandatory_vars and pair[1] in mandatory_vars
        )
        a = Assertion(
            label=label,
            kind=kind,
            statement=stmt,
            mandatory_hypotheses=tuple(mandatory_h),
            mandatory_variables=frozenset(mandatory_vars),
            variable_types=tuple(var_types),
            disjoint_pairs=dvs,
            order=order,
        )
        assertions.append(a)
        by_label[label] = a

    if scopes:
        raise ParseError("unterminated ${ scope")
    return Database(constants, variables, hypotheses, assertions, by_label)
