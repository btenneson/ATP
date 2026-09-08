from __future__ import annotations

"""Theoremhood-independent premise-slot addresses for Experiment 001.

A WFF/premise remains a zero-dimensional syntactic object.  The integer
returned here is metadata for one premise slot on a finite grid.  For a rule
with k logical ($e) premises, the k grid coordinates are traversed in a finite
k-dimensional Hilbert order.

Two frozen address modes are used:

``naive``
    A cryptographic hash scatters premise strings over the grid.  This retains
    exact determinism but intentionally carries no locality hypothesis.

``structural``
    A coarse theoremhood-independent syntactic signature chooses a basin and a
    short hash microcode distinguishes premises inside that basin.  This is a
    first structural-address prototype; it is not a learned geometry.
"""

from hashlib import sha256
from typing import Iterable


DEFAULT_BITS = 6
STRUCTURAL_COARSE_BITS = 4


def _digest_int(tokens: Iterable[str]) -> int:
    payload = "\x1f".join(tokens).encode("utf-8")
    return int.from_bytes(sha256(payload).digest()[:8], "big")


def _max_parenthesis_depth(tokens: tuple[str, ...]) -> int:
    depth = 0
    best = 0
    for tok in tokens:
        if tok == "(":
            depth += 1
            best = max(best, depth)
        elif tok == ")" and depth:
            depth -= 1
    return best


def _structural_basin(statement: tuple[str, ...], variables: set[str]) -> int:
    body = statement[1:] if statement and statement[0] in {"|-", "wff", "class", "setvar"} else statement
    n = len(body)
    variable_count = sum(tok in variables for tok in body)
    quantifier_count = sum(tok in {"A.", "E."} for tok in body)
    negation_count = body.count("-.")
    connective_count = sum(tok in {"->", "/\\", "\\/", "<->"} for tok in body)
    relation_count = sum(tok in {"=", "e.", "C_", "C.", "=/="} for tok in body)
    repeated = max(0, n - len(set(body)))
    depth = _max_parenthesis_depth(body)

    # The weights and clipping are frozen before the sealed run.  They use
    # syntax only and deliberately avoid theorem labels, proof text, target
    # outcome, or future search information.
    score = (
        min(n, 63)
        + 2 * min(depth, 15)
        + min(variable_count, 31)
        + 3 * min(quantifier_count, 7)
        + 2 * min(negation_count, 7)
        + 2 * min(connective_count, 15)
        + min(relation_count, 15)
        + min(repeated, 31)
    )
    return score & ((1 << STRUCTURAL_COARSE_BITS) - 1)


def address_premise(
    statement: tuple[str, ...],
    variables: set[str],
    *,
    mode: str,
    bits: int = DEFAULT_BITS,
) -> int:
    """Return a deterministic finite-grid premise-slot coordinate."""
    if bits <= 0:
        raise ValueError("bits must be positive")
    size = 1 << bits
    digest = _digest_int(statement)
    if mode == "naive":
        return digest % size
    if mode != "structural":
        raise ValueError(f"unknown address mode: {mode}")

    coarse_bits = min(STRUCTURAL_COARSE_BITS, bits)
    micro_bits = bits - coarse_bits
    basin = _structural_basin(statement, variables) & ((1 << coarse_bits) - 1)
    if micro_bits == 0:
        return basin
    micro = digest & ((1 << micro_bits) - 1)
    return (basin << micro_bits) | micro


def hilbert_distance(point: tuple[int, ...], bits: int = DEFAULT_BITS) -> int:
    """Map a finite integer grid point to its Hilbert traversal index.

    This is the compact transpose-based Hilbert integer transform.  Every
    coordinate must lie in [0, 2**bits).  Dimension zero has the single index
    zero; dimension one reduces to the coordinate itself.
    """
    if bits <= 0:
        raise ValueError("bits must be positive")
    n = len(point)
    if n == 0:
        return 0
    limit = 1 << bits
    if any(x < 0 or x >= limit for x in point):
        raise ValueError("point lies outside finite Hilbert grid")
    if n == 1:
        return point[0]

    x = list(point)
    q = 1 << (bits - 1)
    while q > 1:
        p = q - 1
        for i in range(n - 1, -1, -1):
            if x[i] & q:
                x[0] ^= p
            else:
                t = (x[0] ^ x[i]) & p
                x[0] ^= t
                x[i] ^= t
        q >>= 1

    for i in range(1, n):
        x[i] ^= x[i - 1]

    t = 0
    q = 1 << (bits - 1)
    while q > 1:
        if x[n - 1] & q:
            t ^= q - 1
        q >>= 1
    for i in range(n - 1, -1, -1):
        x[i] ^= t

    h = 0
    for bit in range(bits - 1, -1, -1):
        for i in range(n):
            h = (h << 1) | ((x[i] >> bit) & 1)
    return h


def hilbert_action_key(
    premise_statements: tuple[tuple[str, ...], ...],
    variables: set[str],
    *,
    mode: str,
    bits: int = DEFAULT_BITS,
) -> tuple[int, tuple[int, ...]]:
    """Return (Hilbert index, exact grid point) for one legal rule action."""
    point = tuple(
        address_premise(stmt, variables, mode=mode, bits=bits)
        for stmt in premise_statements
    )
    return hilbert_distance(point, bits), point
