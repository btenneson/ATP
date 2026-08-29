#!/usr/bin/env python3
"""Predator 8.040: operational R3/I4 supervisory half-turn treatment.

Research question
-----------------
On the same blind ``prcom`` target, does the intended causal self-awareness
architecture behave differently when R3 control remains sovereign over search
strategy and, after the ordinary strategy family is exhausted without progress,
uses one geometric escape operation: rotate every strategy knob by a half-turn
in a continuous circle embedding, then continue ordinary proof search?

Architecture
------------
* I4 is the certificate-coherent four-ply FUTUREBANK from Predator 8.007.
  Imagined states never count as proof.
* R3 is the operational metacontroller from Predator 8.006. It observes live
  settlement-distance/stagnation signals and controls how search resources are
  deployed.
* There is no blind transition to a separate brute-force controller in this
  treatment. The declared expansion budget remains under R3/I4 supervision.
* Creativity is NOT a rotated coordinate. It is treated as a population-level
  derived/initialization quantity. The rotated coordinates are the actual
  strategy controls used by R3/I4.

Half-turn
---------
For each bounded strategy-control coordinate x_i in [a_i,b_i], normalize

    u_i = (x_i-a_i)/(b_i-a_i) in [0,1].

Embed that interval as the cosine coordinate of a circle,

    u_i = (1-cos(theta_i))/2,   theta_i in [0,pi].

Then apply the genuine circle half-turn

    theta_i -> theta_i + pi (mod 2pi).

Decoding the antipode gives

    u_i -> 1-u_i,

so the induced legal-knob map is x_i -> a_i+b_i-x_i. This is an involution even
at the interval endpoints; unlike a naive u -> u+1/2 mod 1 normalization, it
does not incorrectly identify the distinct legal settings u=0 and u=1.
Integer controls are rounded only at the execution boundary.

The first half-turn is triggered only after LEAN itself has had a refractory
window with no settlement-distance improvement. If progress occurs, the
existing controller's stagnation clock resets and local strategy refinement
resumes. If no progress occurs, ROTATED remains active rather than immediately
rotating back, preventing a two-cycle.

Verifier invariant
------------------
Nothing here adds or relaxes a Metamath rule. A theorem claim still requires an
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

# R3 already enters LEAN at stale >= 5000. Give that lowest-overhead regime a
# bounded refinement/refractory window before a global half-turn is permitted.
ROTATE_STALE = max(5200, int(os.environ.get("PREDATOR_840_ROTATE_STALE", "6000")))

# These are the actual R3/I4 strategy controls consumed by 8.006. Creativity is
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
        return 0.5
    return (float(value) - lo) / (hi - lo)


def _angle_from_u(u):
    """Canonical semicircle embedding u=(1-cos(theta))/2."""
    u = min(1.0, max(0.0, float(u)))
    return math.acos(1.0 - 2.0 * u)


def _u_from_angle(theta):
    return 0.5 * (1.0 - math.cos(float(theta)))


def _half_turn_u(u):
    theta = _angle_from_u(u)
    return _u_from_angle((theta + math.pi) % (2.0 * math.pi))


def _decode(key, u):
    lo, hi = _bounds(key)
    if math.isclose(lo, hi):
        x = lo
    else:
        x = lo + min(1.0, max(0.0, float(u))) * (hi - lo)
    if key in INTEGER_KNOBS:
        return max(1, int(round(x)))
    return float(x)


def _rotate_value(key, value):
    return _decode(key, _half_turn_u(_relax(key, value)))


def half_turn_strategy(source="LEAN"):
    """Rotate every actual strategy knob by pi in its circle embedding."""
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
    # The inherited 8.006 test deliberately asserts its frozen four-state
    # thresholds, including stale=6000 -> LEAN. Run that regression test against
    # the frozen controller first, then restore 8.040's supervisory override and
    # test the new ROTATED boundary separately. This keeps both claims honest.
    active_strategy_for = BASE6._strategy_for
    BASE6._strategy_for = _ORIGINAL_STRATEGY_FOR
    try:
        rc = _ORIGINAL_SELFTEST(a)
    finally:
        BASE6._strategy_for = active_strategy_for
    if rc:
        return rc

    different = any(
        not math.isclose(float(ROTATED[k]), float(BASE_FAMILY["LEAN"][k]), rel_tol=0, abs_tol=1e-12)
        for k in KNOBS
    )
    bounded = True
    geometric_involution_ok = True
    decoded_involution_ok = True
    endpoint_ok = True
    for key in KNOBS:
        lo, hi = _bounds(key)
        x = float(ROTATED[key])
        bounded = bounded and (lo - 1e-12 <= x <= hi + 1e-12)
        u = ROTATED_FROM_U[key]
        geometric_involution_ok = geometric_involution_ok and math.isclose(
            _half_turn_u(_half_turn_u(u)), u, rel_tol=0, abs_tol=1e-12)
        original = BASE_FAMILY["LEAN"][key]
        twice = _rotate_value(key, _rotate_value(key, original))
        decoded_involution_ok = decoded_involution_ok and math.isclose(
            float(twice), float(original), rel_tol=0, abs_tol=1e-12)
        if not math.isclose(lo, hi):
            endpoint_ok = endpoint_ok and math.isclose(_half_turn_u(0.0), 1.0, abs_tol=1e-12)
            endpoint_ok = endpoint_ok and math.isclose(_half_turn_u(1.0), 0.0, abs_tol=1e-12)
    no_creativity_knob = "creativity" not in KNOBS
    boundary_ok = (
        supervisory_strategy_for(ROTATE_STALE - 1, 0) == "LEAN"
        and supervisory_strategy_for(ROTATE_STALE, 0) == "ROTATED"
        and supervisory_strategy_for(ROTATE_STALE + 5000, 0) == "ROTATED"
    )
    ok = (
        different and bounded and geometric_involution_ok and decoded_involution_ok
        and endpoint_ok and no_creativity_knob and boundary_ok
    )
    print("  [8.040] supervisory half-turn invariants")
    print("      inherited four-state R3 regression: passed")
    print("      antipodal circle R(R(u))=u: %s" % geometric_involution_ok)
    print("      decoded knob R(R(x))=x: %s" % decoded_involution_ok)
    print("      distinct interval endpoints swap correctly: %s" % endpoint_ok)
    print("      decoded knobs legal and changed: %s" % (bounded and different))
    print("      creativity excluded from knob vector: %s" % no_creativity_knob)
    print("      R3 LEAN->ROTATED boundary/persistence: %s" % boundary_ok)
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
