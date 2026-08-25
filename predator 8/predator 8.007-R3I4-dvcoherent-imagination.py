#!/usr/bin/env python3
"""Predator 8.007-R3I4-dvcoherent-imagination.

Engineering/research continuation of Predator 8.006.

8.006 showed that saturation-triggered Level-3 strategy switching can move the
search into materially different regions and increase real expansion throughput.
One mismatch remained: real search carries the FULL accumulated Metamath
disjoint-variable ($d) obligations, but the four-ply FUTUREBANK imagination
only checked the $d obligations introduced by each imagined assertion itself.
It could therefore award a "solved within 4" reachability bonus to an imagined
future that was already incompatible with an earlier real-search DV obligation,
or that would fail only when unresolved metavariables were grounded at an
imagined terminal.

8.007 makes reasoned imagination certificate-coherent with the real search:

* the exact accumulated real-search DV obligations are captured at the point
  where 8.006 has already checked them for the successor substitution;
* every imagined state carries those obligations forward and adds new ones;
* impossible forced DV states are rejected inside FUTUREBANK;
* a zero-goal imagined state counts as solved only if the SAME deterministic
  emission-time grounding rule used by the real certificate path leaves all
  accumulated DV obligations legal;
* imagined-state cycle detection includes the DV constraint state, so two
  syntactically identical goals reached under different certificate conditions
  are not conflated;
* if the DV context cannot be matched exactly to the successor substitution,
  imagination fails closed: it supplies no progress or solved bonus.

No target proof is read.  No proof rule is added or relaxed.  The real search,
terminal DV fallback, Level-3 strategy switching, full pre-target index, outer
resource controls, and independent Metamath verifier remain those of 8.006.
"""
from __future__ import annotations

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.006-R3I4-strategy-switch.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_strategy_switch", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.006-R3I4-strategy-switch")
BASE6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE6)

BASE5 = BASE6.BASE5
R3I4 = BASE6.R3I4
P8 = BASE6.P8
COMP = BASE6.COMP
P8.VERSION = "8.007-R3I4-dvcoherent-imagination"

_ORIG_DV_OK = R3I4._dv_ok
_LAST_DV_CONTEXT = [None, ()]

_STATS = {
    "calls": 0,
    "context_miss": 0,
    "legal_imagined": 0,
    "dv_rejected": 0,
    "terminal_dv_rejected": 0,
}


def _dv_ok_capture(obligations, sub):
    ok = _ORIG_DV_OK(obligations, sub)
    _LAST_DV_CONTEXT[0] = sub
    _LAST_DV_CONTEXT[1] = tuple(obligations)
    return ok


def _terminal_dv_ok_no_capture(obligations, sub):
    """8.005's terminal-ground check without disturbing capture context."""
    fallback = BASE5._emission_fallback_from_grammar()
    grounded = []
    try:
        for tx, ty, x, y in obligations:
            gx = P8.ground(tx, sub, fallback)
            gy = P8.ground(ty, sub, fallback)
            grounded.append((gx, gy, x, y))
    except KeyError:
        return False
    return _ORIG_DV_OK(tuple(grounded), {})


def _dv_signature(obligations, sub):
    """Constraint fingerprint for imagination cycle detection."""
    out = []
    for tx, ty, _x, _y in obligations:
        a = " ".join(P8.apply_sub(tx, sub).tokens())
        b = " ".join(P8.apply_sub(ty, sub).tokens())
        out.append((a, b) if a <= b else (b, a))
    return tuple(sorted(out))


def _imagined_state_signature(goals, sub, obligations):
    return (R3I4._state_signature(goals, sub), _dv_signature(obligations, sub))


def _imagined_successors_dv(goals, sub, obligations, index, max_open,
                             branch_cap):
    """Legal imagined successors carrying the complete accumulated DV state."""
    if not goals:
        return []
    gi = P8.pick_goal(goals, sub)
    gt, _slot, _hix = goals[gi]
    rest = goals[:gi] + goals[gi + 1:]
    gt = P8.apply_sub(gt, sub)
    closers, openers = index.candidates(gt)

    ordered_openers = sorted(
        openers,
        key=lambda item: (COMP._pre_distance(len(rest), item), item[0]))
    pick = list(closers) + ordered_openers[:max(1, int(branch_cap))]

    out = []
    for lab, ct, data in pick:
        m = {}
        c2 = P8.rename_apart(ct, m)
        s2 = P8.unify(c2, gt, sub)
        if s2 is None:
            continue

        _dv, f_hyps, e_hyps, _concl = data
        fmap = {var: m.get(var, P8.fresh(tc)) for _fh, tc, var in f_hyps}
        for _fh, tc, var in f_hyps:
            m.setdefault(var, fmap[var])

        next_dv = tuple(obligations) + R3I4._dv_obligations(data, m)
        if not _ORIG_DV_OK(next_dv, s2):
            _STATS["dv_rejected"] += 1
            continue

        newgoals = []
        ok = True
        for hj, (_ename, stat) in enumerate(e_hyps):
            try:
                ht = P8.G.parse(stat[1:], "wff", index.by_tc)
            except (RecursionError, P8.MMError):
                ht = None
            if ht is None:
                ok = False
                break
            newgoals.append((P8.rename_apart(ht, m), None, hj))
        if not ok:
            continue

        successor_goals = newgoals + rest
        if len(successor_goals) > max_open:
            continue

        if not successor_goals and not _terminal_dv_ok_no_capture(next_dv, s2):
            _STATS["terminal_dv_rejected"] += 1
            continue

        _STATS["legal_imagined"] += 1
        out.append((successor_goals, s2, next_dv, lab))
    return out


def reasoned_imagination4_dv(goals, sub, index, max_open, beam_width=3,
                              branch_cap=4):
    """Four-ply certificate-coherent FUTUREBANK."""
    _STATS["calls"] += 1
    r0 = COMP.settlement_distance_hat(goals, sub)
    if not goals:
        return 0.0, True, 0, 0

    ctx_sub, ctx_obligations = _LAST_DV_CONTEXT
    if ctx_sub is not sub:
        _STATS["context_miss"] += 1
        return r0, False, 0, 0
    obligations0 = tuple(ctx_obligations)

    best_r = r0
    best_depth = 0
    imagined = 0
    layer = [(r0, goals, sub, obligations0)]
    seen = {_imagined_state_signature(goals, sub, obligations0)}

    for depth in range(1, R3I4.IMAGINATION_DEPTH + 1):
        nxt = []
        for _score, gs, ss, dvs in layer:
            successors = _imagined_successors_dv(
                gs, ss, dvs, index, max_open, branch_cap)
            for ng, ns, ndv, _lab in successors:
                imagined += 1
                if not ng:
                    return 0.0, True, depth, imagined
                sig = _imagined_state_signature(ng, ns, ndv)
                if sig in seen:
                    continue
                seen.add(sig)
                rh = COMP.settlement_distance_hat(ng, ns)
                if rh < best_r:
                    best_r, best_depth = rh, depth
                nxt.append((rh, ng, ns, ndv))
        if not nxt:
            break
        nxt.sort(key=lambda z: (
            z[0], len(z[1]),
            R3I4._state_signature(z[1], z[2]),
            _dv_signature(z[3], z[2])))
        layer = nxt[:max(1, int(beam_width))]

    return best_r, False, best_depth, imagined


R3I4._dv_ok = _dv_ok_capture
R3I4.reasoned_imagination4 = reasoned_imagination4_dv


def prove_r3i4_dvcoherent(*args, **kwargs):
    for k in _STATS:
        _STATS[k] = 0
    _LAST_DV_CONTEXT[0] = None
    _LAST_DV_CONTEXT[1] = ()
    say = kwargs.get("say", print)
    try:
        return BASE6.prove_r3i4_switch(*args, **kwargs)
    finally:
        if say:
            say("      DV-coherent FUTUREBANK stats: calls=%s, legal-imagined=%s, dv-rejected=%s, terminal-dv-rejected=%s, context-miss=%s"
                % (f"{_STATS['calls']:,}", f"{_STATS['legal_imagined']:,}",
                   f"{_STATS['dv_rejected']:,}",
                   f"{_STATS['terminal_dv_rejected']:,}",
                   f"{_STATS['context_miss']:,}"))


P8.prove = prove_r3i4_dvcoherent

_ORIG_SELFTEST = P8.cmd_selftest


def _cmd_selftest_dvcoherent(a):
    rc = _ORIG_SELFTEST(a)
    if rc:
        return rc

    m1 = P8.fresh("wff")
    m2 = P8.fresh("wff")
    obligation = ((m1, m2, "left", "right"),)
    sub = {}
    partial_ok = _dv_ok_capture(obligation, sub)
    capture_ok = (_LAST_DV_CONTEXT[0] is sub
                  and _LAST_DV_CONTEXT[1] == obligation)
    signature_ok = (_imagined_state_signature([], sub, ())
                    != _imagined_state_signature([], sub, obligation))

    _LAST_DV_CONTEXT[0] = None
    _LAST_DV_CONTEXT[1] = ()
    goal = P8.G.Tree(None, "wff", (), "ph")
    r0 = COMP.settlement_distance_hat([(goal, None, 0)], {})
    got = reasoned_imagination4_dv([(goal, None, 0)], {}, None, 6)
    fail_closed_ok = (got == (r0, False, 0, 0))

    ok = partial_ok and capture_ok and signature_ok and fail_closed_ok
    print("  [6] DV-coherent FUTUREBANK carries exact certificate context and fails closed")
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _cmd_selftest_dvcoherent


def main():
    return BASE6.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
