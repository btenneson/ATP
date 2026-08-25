#!/usr/bin/env python3
"""Semantics-preserving acceleration for setmm_grammar.parse.

The original parser considers every possible endpoint for a grammar variable.
For an infix production such as

    A e. B

that means trying every split even though the next token after A MUST be the
literal constant `e.`.  Very large fully formalized formulas (notably set.mm
stress tests such as quartfull) therefore trigger a combinatorial blow-up.

This parser is intentionally the same span/memo parser with one exact pruning
law:

    if the grammar symbol after a variable is a constant c, only consider
    variable endpoints m for which tokens[m] == c.

Every valid parse already has that property, so no parse is removed.  Candidate
endpoints remain in ascending order, preserving the old parser's first-parse
choice on unambiguous/ambiguous inputs alike.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict

import setmm_grammar as G


def parse(tokens, typecode, by_tc, memo=None, all_parses=False, cap=4):
    tokens = list(tokens)
    n = len(tokens)
    if memo is None:
        memo = {}

    if not G.RULEIDX:
        G.build_index(by_tc)
    vt = G.VARTYPE
    idx = G.RULEIDX

    # Exact token-position index used only to skip split points that could not
    # possibly be followed by the next literal grammar token.
    positions = defaultdict(list)
    for k, tok in enumerate(tokens):
        positions[tok].append(k)

    _rf = {}

    def rules_for(tc, tok):
        key = (tc, tok)
        r = _rf.get(key)
        if r is None:
            a = idx.get(key) or ()
            b = idx.get((tc, None)) or ()
            r = (a + b) if (a and b) else (a or b or ())
            _rf[key] = r
        return r

    def go(i, j, tc):
        key = (i, j, tc)
        if key in memo:
            return memo[key]
        memo[key] = None
        found = []
        span = j - i

        if span == 1 and vt.get(tokens[i]) == tc:
            found.append(G.Tree(None, tc, (), tokens[i]))

        if not (found and not all_parses):
            first_tok = tokens[i] if i < j else None
            for lab, pat, minlen in rules_for(tc, first_tok):
                if span < minlen:
                    continue
                for kids in match(pat, 0, i, j):
                    found.append(G.Tree(lab, tc, kids))
                    if not all_parses:
                        break
                if found and not all_parses:
                    break
                if all_parses and len(found) >= cap:
                    break

        memo[key] = found if all_parses else (found[0] if found else None)
        return memo[key]

    def match(pat, p, i, j):
        np_ = len(pat)
        if p == np_:
            if i == j:
                yield []
            return

        t = pat[p]
        if t not in vt:
            if i < j and tokens[i] == t:
                for rest in match(pat, p + 1, i + 1, j):
                    yield rest
            return

        tc = vt[t]
        tail = np_ - p - 1
        if p == np_ - 1:
            sub = go(i, j, tc)
            if sub:
                for s in (sub if isinstance(sub, list) else [sub]):
                    yield [s]
            return

        lo = i + 1
        hi = j - tail  # inclusive, matching range(i+1, j-tail+1)

        # Exact pruning: when the next grammar symbol is literal, the next
        # unmatched input token must be exactly that literal.
        next_symbol = pat[p + 1]
        if next_symbol not in vt:
            ps = positions.get(next_symbol, ())
            a = bisect_left(ps, lo)
            b = bisect_right(ps, hi)
            endpoints = ps[a:b]
        else:
            endpoints = range(lo, hi + 1)

        for m in endpoints:
            sub = go(i, m, tc)
            if not sub:
                continue
            for s in (sub if isinstance(sub, list) else [sub]):
                for rest in match(pat, p + 1, m, j):
                    yield [s] + rest
                if not isinstance(sub, list):
                    break

    r = go(0, n, typecode)
    if all_parses:
        return r or []
    return r


def install(grammar_module=None):
    """Install the accelerator into the already-loaded grammar module."""
    gm = grammar_module or G
    gm.parse = parse
    return gm
