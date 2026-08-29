#!/usr/bin/env python3
"""Predator 8.040: operational R3/I4 supervisory half-turn treatment.

Research question
-----------------
On the same blind ``prcom`` target, does the intended causal self-awareness
architecture behave differently when R3 control remains sovereign over search
strategy and, after the ordinary strategy family is exhausted without progress,
uses one geometric escape operation: rotate every strategy knob by a half-turn
in a normalized continuous relaxation, then continue ordinary proof search?

Architecture
------------
* I4 is the certificate-coherent four-ply FUTUREBANK from Predator 8.007.
  Imagined states never count as proof.
* R3 is the operational metacontroller from Predator 8.006.  It observes live
  settlement-distance/stagnation signals and controls how search resources are
  deployed.
* There is no blind transition to a separate brute-force controller in this
  treatment.  The declared expansion budget remains under R3/I4 supervision.
* Creativity is NOT a rotated coordinate.  It is treated as a population-level
  derived/initialization quantity.  The rotated coordinates are the actual
  strategy controls used by R3/I4.

Half-turn
---------
For each strategy-control coordinate x_i, take the min/max values already
present in the frozen COMPASS/CERTIFY/DIVERSIFY/LEAN family, relax to
u_i in [0,1], apply the circle half-turn

    u_i -> (u_i + 1/2) mod 1,

and decode to the legal execution type.  Integer controls are rounded only at
that final decoding boundary; the involution lives in the relaxed coordinate.

The first half-turn is triggered only after LEAN itself has had a refractory
window with no settlement-distance improvement.  If progress occurs, the
existing controller's stagnation clock resets and local strategy refinement
resumes.  If no progress occurs, ROTATED remains active rather than immediately
rotating back, preventing a two-cycle.

Verifier invariant
------------------
Nothing here adds or relaxes a Metamath rule.  A theorem claim still requires an
emitted finite certificate accepted by the ordinary verifier.
"""
from __future__ import annotations

import importlib.util
import math
import os
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
BASE7_PATH = os.path.join(HERE, "predator 8.007-R3I4-dvcoherent-imagination.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_dvcoherent", BASE7_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.007 R3/I4 base")
BASE7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE7)

BASE6 = BASE7.BASE6
P8 = BASE7.P8
P8.VERSION = "8.040-R3I4-supervisory-half-turn"

# R3 already enters LEAN at stale >= 5000.  Give that lowest-overhead regime a
# bounded refinement/refractory window before a global half-turn is permitted.
ROTATE_STALE = max(5200, int(os.environ.get("PREDATOR_840_ROTATE_STALE", "6000")))

# These are the actual R3/I4 strategy controls consumed by 8.006.  Creativity is
# intentionally absent: it is not a knob in this treatment.
KNOBS = (
    "imagine_top",
    "beam",
    "branch_cap",
    "progress_weight",
    "solve_bonus",
    "explore_extra",
    "cap_factor",
    "goal_meta_weight",
    "dv_meta_weight",
    "rhat_weight",
    "diversity_bonus",
)
INTEGER_KNOBS = {"imagine_top", "beam", "branch_cap"}
BASE_FAMILY = {
    name: deepcopy(BASE6.STRATEGY[name])
    for name in ("COMPASS", "CERTIFY", "DIVERSIFY", "LEAN")
}


def _bounds(key):
    vals = [float(BASE_FAMILY[name][key]) for name in BASE_FAMILY]
    return min(vals), max(vals)


def _relax(key, value):
    lo, hi = _bounds(key)
    if math.isclose(lo, hi):
        return 0.0
    return (float(value) - lo) / (hi - lo)


def _half_turn_u(u):
    return (float(u) + 0.5) % 1.0


def _decode(key, u):
    lo, hi = _bounds(key)
    if math.isclose(lo, hi):
        x = lo
    else:
        x = lo + float(u) * (hi - lo)
    if key in INTEGER_KNOBS:
        return max(1, int(round(x)))
    return float(x)


def half_turn_strategy(source="LEAN"):
    """Rotate every actual strategy knob by pi in its relaxed circle."""
    src = BASE_FAMILY[source]
    out = {}
    relaxed_before = {}
    relaxed_after = {}
    for key in KNOBS:
        u = _relax(key, src[key])
        ur = _half_turn_u(u)
        relaxed_before[key] = u
        relaxed_after[key] = ur
        out[key] = _decode(key, ur)
    return out, relaxed_before, relaxed_after


ROTATED, ROTATED_FROM_U, ROTATED_TO_U = half_turn_strategy("LEAN")
BASE6.STRATEGY["ROTATED"] = ROTATED
_ORIGINAL_STRATEGY_FOR = BASE6._strategy_for


def supervisory_strategy_for(stale, terminal_rejects_since_improvement):
    """R3 has final authority: after LEAN stalls, rotate rather than give up."""
    if int(stale) >= ROTATE_STALE:
        return "ROTATED"
    return _ORIGINAL_STRATEGY_FOR(stale, terminal_rejects_since_improvement)


BASE6._strategy_for = supervisory_strategy_for

# Extend notable logging so the first rotation transition is always visible.
_ORIGINAL_NOTABLE_SWITCH = BASE6._notable_switch
BASE6._notable_switch = lambda n: True if n <= 16 else _ORIGINAL_NOTABLE_SWITCH(n)

_ORIGINAL_SELFTEST = P8.cmd_selftest


def _selftest(a):
    rc = _ORIGINAL_SELFTEST(a)
    if rc:
        return rc
    different = any(
        not math.isclose(float(ROTATED[k]), float(BASE_FAMILY["LEAN"][k]), rel_tol=0, abs_tol=1e-12)
        for k in KNOBS
    )
    bounded = True
    half_turn_ok = True
    for key in KNOBS:
        lo, hi = _bounds(key)
        x = float(ROTATED[key])
        bounded = bounded and (lo - 1e-12 <= x <= hi + 1e-12)
        u = ROTATED_FROM_U[key]
        # The geometric state is exactly an involution before integer decoding.
        half_turn_ok = half_turn_ok and math.isclose(
            _half_turn_u(_half_turn_u(u)), u, rel_tol=0, abs_tol=1e-12)
    no_creativity_knob = "creativity" not in KNOBS
    ok = different and bounded and half_turn_ok and no_creativity_knob
    print("  [8.040] supervisory half-turn invariants")
    print("      relaxed R(R(c))=c: %s" % half_turn_ok)
    print("      decoded knobs legal and changed: %s" % (bounded and different))
    print("      creativity excluded from knob vector: %s" % no_creativity_knob)
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _selftest


def _fmt_strategy(d):
    return ", ".join("%s=%s" % (k, d[k]) for k in KNOBS)


def main():
    print("[P8.040 ARCHITECTURE] operational R3 control + certificate-coherent I4 FUTUREBANK")
    print("[P8.040 CONTROL] no blind brute fallback; R3 retains authority over the declared budget")
    print("[P8.040 ROTATION] trigger stale >= %d after LEAN; one half-turn state persists until real progress" % ROTATE_STALE)
    print("[P8.040 KNOBS] creativity is derived/not rotated; actual strategy knobs: %s" % ", ".join(KNOBS))
    print("[P8.040 LEAN] %s" % _fmt_strategy(BASE_FAMILY["LEAN"]))
    print("[P8.040 OPPOSITE] %s" % _fmt_strategy(ROTATED))
    return BASE7.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
