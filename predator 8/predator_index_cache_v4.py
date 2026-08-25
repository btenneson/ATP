#!/usr/bin/env python3
"""Full assertion index v4: parallel parse + exact proof-derived fallback.

This module preserves the mathematical corpus used by Predator.  Normal
pre-target logical assertions are parsed in parallel.  If an exceptionally
large *proved theorem* still exceeds the bounded parser guards, its syntax tree
is reconstructed from its existing Metamath proof rather than omitted.

The fallback is exact:
* it replays the theorem's decompressed proof in declaration order;
* $f/syntax steps construct typed syntax trees directly;
* logical steps instantiate the already-indexed conclusion tree of the cited
  assertion with the proof's typed substitutions;
* the reconstructed final tree must serialize byte-for-token to the theorem's
  printed conclusion, or index construction fails.

Thus the fallback changes preprocessing only.  It does not add a theorem,
remove a theorem, inspect the Halo target proof, or change proof acceptance.
"""
from __future__ import annotations

import os
import time

import predator_index_cache as BASE

P8 = None


def configure(p8):
    global P8
    P8 = p8
    BASE.configure(p8)


def _clone_subst_tree(t, fmap):
    """Instantiate a parsed syntax tree with typed proof-substitution trees."""
    if t.var is not None:
        r = fmap.get(t.var)
        if r is None:
            raise RuntimeError("missing tree substitution for %s" % t.var)
        return r
    return P8.G.Tree(
        t.label, t.typecode,
        [_clone_subst_tree(k, fmap) for k in t.kids])


def _syntax_step_tree(label, data, fmap):
    """Construct the output tree of a syntax-production application."""
    stat = data[3]
    tc = stat[0]
    rule = P8.G.RULES.get(label)
    if rule is None:
        raise RuntimeError(
            "proof-tree fallback encountered non-grammar syntax assertion %s"
            % label)
    rtc, pat = rule
    if rtc != tc:
        raise RuntimeError("syntax type mismatch at %s" % label)
    kids = []
    for tok in pat:
        if tok in P8.G.VARTYPE:
            k = fmap.get(tok)
            if k is None:
                raise RuntimeError(
                    "missing syntax substitution %s at %s" % (tok, label))
            kids.append(k)
    return P8.G.Tree(label, tc, kids)


def _derive_theorem_tree(mm, label, parsed):
    """Reconstruct one proved logical theorem's conclusion tree from its proof.

    `parsed` maps previously available logical assertion labels to their exact
    parsed conclusion trees.  No parsing of the theorem's giant conclusion is
    performed here.
    """
    typ, data = mm.labels[label]
    if typ != "$p":
        raise RuntimeError("proof-derived fallback requires a $p theorem: %s" % label)
    conclusion = data[3]
    if not conclusion or conclusion[0] != "|-":
        raise RuntimeError("proof-derived fallback requires a logical theorem: %s" % label)

    proof = mm.decompress(label, mm.proofs[label])
    if "?" in proof:
        raise RuntimeError("cannot derive tree from incomplete proof %s" % label)

    # Each stack entry is (typecode, tree-or-None).  Essential hypotheses need
    # no parse tree: when consumed by a logical step they constrain proof
    # correctness, but the output syntax tree is determined by the typed $f
    # substitutions and the cited assertion's conclusion tree.
    stack = []

    for step in proof:
        if step not in mm.labels:
            raise RuntimeError("%s proof references unknown label %s" % (label, step))
        styp, sdata = mm.labels[step]

        if styp == "$f":
            tc, var = sdata
            stack.append((tc, P8.G.Tree(None, tc, (), var)))
            continue
        if styp == "$e":
            stat = sdata
            stack.append((stat[0] if stat else None, None))
            continue

        _dvs, f_hyps, e_hyps, s_concl = sdata
        npop = len(f_hyps) + len(e_hyps)
        if npop > len(stack):
            raise RuntimeError("proof-tree stack underflow at %s in %s" % (step, label))
        base = len(stack) - npop
        args = stack[base:]

        fmap = {}
        for j, (_fh, tc, var) in enumerate(f_hyps):
            etc, et = args[j]
            if etc != tc or et is None:
                raise RuntimeError(
                    "typed syntax tree missing for %s at proof step %s" % (var, step))
            fmap[var] = et

        del stack[base:]

        if not s_concl:
            raise RuntimeError("empty assertion conclusion at %s" % step)
        out_tc = s_concl[0]
        if out_tc == "|-":
            pat = parsed.get(step)
            if pat is None:
                raise RuntimeError(
                    "proof-tree fallback needs earlier logical tree %s while deriving %s"
                    % (step, label))
            out_tree = _clone_subst_tree(pat, fmap)
            stack.append(("|-", out_tree))
        else:
            out_tree = _syntax_step_tree(step, sdata, fmap)
            stack.append((out_tc, out_tree))

    if len(stack) != 1 or stack[0][0] != "|-" or stack[0][1] is None:
        raise RuntimeError(
            "proof-tree replay for %s ended with malformed stack (%d entries)"
            % (label, len(stack)))

    tree = stack[0][1]
    got = tuple(tree.tokens())
    want = tuple(conclusion[1:])
    if got != want:
        # Fail closed.  The independent token equality makes this mechanism a
        # preprocessing accelerator, not an alternate source of mathematics.
        raise RuntimeError(
            "proof-derived tree token mismatch for %s: got %d tokens, expected %d"
            % (label, len(got), len(want)))
    return tree


class CachedParallelIndexV4(BASE.CachedParallelIndex):
    """CachedParallelIndex with exact theorem-proof fallback for parse outliers."""

    CACHE_VERSION = 4

    def __init__(self, mm, by_tc, upto=None, say=None):
        self._v4_mm = mm
        super().__init__(mm, by_tc, upto=upto, say=say)

    def _build_full(self, jobs, by_tc, say):
        BASE._BY_TC = by_tc
        workers = max(1, min(4, os.cpu_count() or 1))
        if say:
            say("    building FULL pre-target index v4: %s logical assertions"
                % f"{len(jobs):,}")
            say("    parser workers: %d; proved parse outliers use exact proof-tree fallback"
                % workers)

        parsed = {}
        pending = list(jobs)

        # Do not burn ten minutes brute-forcing a deliberate parser stress test.
        # The normal parser gets three bounded passes; any remaining *proved*
        # theorem is reconstructed from its proof and independently token-checked.
        for pass_no, timeout_s in enumerate((2.0, 15.0, 90.0), 1):
            if not pending:
                break
            if say:
                say("    parse pass %d: %s assertions, %.0fs per-formula guard"
                    % (pass_no, f"{len(pending):,}", timeout_s))
            if os.name == "posix" and workers > 1:
                got, slow, errors = BASE._parallel_pass(
                    pending, timeout_s, workers, say)
            else:
                got, slow, errors = BASE._sequential_pass(
                    pending, timeout_s, say)
            parsed.update(got)
            if errors:
                preview = ", ".join("%s (%s)" % x for x in errors[:8])
                raise RuntimeError("index parse errors: %s" % preview)
            slowset = set(slow)
            pending = [(lab, toks) for lab, toks in pending if lab in slowset]
            if say and pending:
                say("    %s unusually slow assertions deferred"
                    % f"{len(pending):,}")

        if pending:
            mm = self._v4_mm
            orderpos = {lab: i for i, lab in enumerate(mm.order)}
            pending.sort(key=lambda x: orderpos[x[0]])
            if say:
                say("    proof-tree fallback for %d proved parse outlier(s): %s"
                    % (len(pending), ", ".join(lab for lab, _ in pending)))
            for lab, _toks in pending:
                typ, _data = mm.labels[lab]
                if typ != "$p":
                    raise RuntimeError(
                        "unparsed logical axiom %s cannot use theorem-proof fallback" % lab)
                t0 = time.perf_counter()
                tree = _derive_theorem_tree(mm, lab, parsed)
                parsed[lab] = tree
                if say:
                    say("    %s reconstructed exactly from its Metamath proof in %.2fs"
                        % (lab, time.perf_counter() - t0))

        missing = [lab for lab, _ in jobs if lab not in parsed]
        if missing:
            raise RuntimeError("full index still missing: %s" % ", ".join(missing[:20]))

        out = [(lab, parsed[lab]) for lab, _ in jobs]
        if say:
            say("    full index v4 complete: %s/%s assertions available"
                % (f"{len(out):,}", f"{len(jobs):,}"))
        return out
