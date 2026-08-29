#!/usr/bin/env python3
"""Predator 8.041: closed-loop reference-tracking knob control.

Research question
-----------------
On the same blind ``prcom`` mechanism benchmark used by Predator 8.040, can
feedback control of the actual R3/I4 strategy knobs expose a verified proof
more efficiently than the previous one-shot antipodal half-turn?

This is deliberately a mechanism experiment, not a generalization claim.  The
reference operating point is the knob vector that was empirically successful
in the independently verified 8.040 run.  Crucially, 8.041 does NOT compute an
inverse, antipode, or half-turn at runtime.  It treats that earlier successful
configuration as an empirical reference r and regulates the current knob vector
toward r by a stable discrete-time proportional controller.

Control law
-----------
After the inherited R3 controller has reached LEAN and LEAN has itself had a
short refractory window, let x_i(k) be actual knob i after control update k and
r_i the empirical reference.  Each coordinate obeys

    x_i(k+1) = x_i(k) + K_i (r_i - x_i(k)),   0 < K_i < 1.

Equivalently,

    x_i(k) = r_i + (x_i(0)-r_i) (1-K_i)^k.

Different knobs have independent gains K_i.  Integer-valued knobs are rounded
only at the execution boundary.  The feedback trigger is observed stagnation:
a new control update occurs every CONTROL_TICK stale expansions after
CONTROL_START_STALE.  A genuine settlement-distance improvement resets the
stagnation clock, so control automatically returns to the inherited productive
regime rather than continuing to force the reference.

No proof rule, admissibility condition, target proof, or verifier is changed.
Creativity is not one of the controlled coordinates.  There is no blind brute
fallback.  The existing frontier is re-keyed after every control update so the
effect is a real change in search ordering, not just a label.
"""
from __future__ import annotations

import importlib.util
import math
import os
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
BASE7_PATH = os.path.join(HERE, "predator 8.007-R3I4-dvcoherent-imagination.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_dvcoherent_control", BASE7_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.007 R3/I4 base")
BASE7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE7)

BASE6 = BASE7.BASE6
P8 = BASE7.P8
P8.VERSION = "8.041-R3I4-reference-tracking-control"

CONTROL_START_STALE = max(
    5000, int(os.environ.get("PREDATOR_841_CONTROL_START_STALE", "5200"))
)
CONTROL_TICK = max(
    50, int(os.environ.get("PREDATOR_841_CONTROL_TICK", "100"))
)
MAX_CONTROL_STEPS = max(
    1, int(os.environ.get("PREDATOR_841_MAX_CONTROL_STEPS", "24"))
)

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

LEAN = deepcopy(BASE6.STRATEGY["LEAN"])

# Empirical reference operating point from the previously verified 8.040 run.
# It is recorded as data.  No inverse/antipode/half-turn is computed in 8.041.
REFERENCE = {
    "imagine_top": 6,
    "beam": 2,
    "branch_cap": 3,
    "progress_weight": 0.50,
    "solve_bonus": 1.00,
    "explore_extra": 0.10,
    "cap_factor": 0.80,
    "goal_meta_weight": 0.05,
    "dv_meta_weight": 0.30,
    "rhat_weight": 1.00,
    "diversity_bonus": 0.08,
}

# Per-coordinate proportional gains.  Structural/breadth controls are allowed
# to respond a little faster than continuous ranking weights.
GAIN = {
    "imagine_top": 0.30,
    "beam": 0.30,
    "branch_cap": 0.30,
    "progress_weight": 0.25,
    "solve_bonus": 0.25,
    "explore_extra": 0.25,
    "cap_factor": 0.25,
    "goal_meta_weight": 0.25,
    "dv_meta_weight": 0.25,
    "rhat_weight": 0.25,
    "diversity_bonus": 0.25,
}


def _bounds(key):
    vals = [float(BASE6.STRATEGY[name][key])
            for name in ("COMPASS", "CERTIFY", "DIVERSIFY", "LEAN")]
    vals.append(float(REFERENCE[key]))
    return min(vals), max(vals)


def _decode(key, value):
    lo, hi = _bounds(key)
    x = min(hi, max(lo, float(value)))
    if key in INTEGER_KNOBS:
        return max(1, int(round(x)))
    return x


def controlled_value(key, step):
    """Closed-form proportional reference tracking for one knob."""
    k = min(MAX_CONTROL_STEPS, max(0, int(step)))
    gain = GAIN[key]
    x0 = float(LEAN[key])
    ref = float(REFERENCE[key])
    value = ref + (x0 - ref) * ((1.0 - gain) ** k)
    return _decode(key, value)


def control_profile(step):
    return {key: controlled_value(key, step) for key in KNOBS}


# Pre-register a finite bank of controller states.  The state changes only at
# fixed stale-expansion ticks, so frontier re-keying is explicit and auditable.
for _step in range(1, MAX_CONTROL_STEPS + 1):
    BASE6.STRATEGY[f"CTRL_{_step:02d}"] = control_profile(_step)

_ORIGINAL_STRATEGY_FOR = BASE6._strategy_for


def feedback_strategy_for(stale, terminal_rejects_since_improvement):
    """R3 feedback controller: inherited policy until LEAN stalls, then regulate."""
    stale = int(stale)
    if stale < CONTROL_START_STALE:
        return _ORIGINAL_STRATEGY_FOR(stale, terminal_rejects_since_improvement)
    step = 1 + (stale - CONTROL_START_STALE) // CONTROL_TICK
    step = min(MAX_CONTROL_STEPS, max(1, int(step)))
    return f"CTRL_{step:02d}"


BASE6._strategy_for = feedback_strategy_for

# Log the early control updates densely enough to reconstruct the trajectory.
_ORIGINAL_NOTABLE_SWITCH = BASE6._notable_switch
BASE6._notable_switch = lambda n: True if n <= 20 else _ORIGINAL_NOTABLE_SWITCH(n)

_ORIGINAL_SELFTEST = P8.cmd_selftest


def _distance_to_reference(profile):
    total = 0.0
    for key in KNOBS:
        lo, hi = _bounds(key)
        span = max(1e-12, hi - lo)
        total += ((float(profile[key]) - float(REFERENCE[key])) / span) ** 2
    return math.sqrt(total)


def _selftest(a):
    # Preserve the inherited frozen 8.006 controller regression first.
    active_strategy_for = BASE6._strategy_for
    BASE6._strategy_for = _ORIGINAL_STRATEGY_FOR
    try:
        rc = _ORIGINAL_SELFTEST(a)
    finally:
        BASE6._strategy_for = active_strategy_for
    if rc:
        return rc

    profiles = [control_profile(i) for i in range(1, MAX_CONTROL_STEPS + 1)]
    bounded = True
    for p in profiles:
        for key in KNOBS:
            lo, hi = _bounds(key)
            bounded = bounded and (lo - 1e-12 <= float(p[key]) <= hi + 1e-12)

    # Because integer execution knobs can plateau after rounding, require
    # non-increasing rather than strictly decreasing reference distance.
    distances = [_distance_to_reference(LEAN)] + [
        _distance_to_reference(p) for p in profiles
    ]
    stable = all(b <= a + 1e-12 for a, b in zip(distances, distances[1:]))
    moved = any(
        not math.isclose(float(profiles[0][k]), float(LEAN[k]),
                         rel_tol=0, abs_tol=1e-12)
        for k in KNOBS
    )
    near_reference = distances[-1] < 0.02
    no_creativity_knob = "creativity" not in KNOBS
    boundary_ok = (
        feedback_strategy_for(CONTROL_START_STALE - 1, 0)
        == _ORIGINAL_STRATEGY_FOR(CONTROL_START_STALE - 1, 0)
        and feedback_strategy_for(CONTROL_START_STALE, 0) == "CTRL_01"
        and feedback_strategy_for(
            CONTROL_START_STALE + CONTROL_TICK * 3, 0
        ) == "CTRL_04"
    )
    ok = (
        bounded and stable and moved and near_reference
        and no_creativity_knob and boundary_ok
    )

    print("  [8.041] closed-loop proportional-control invariants")
    print("      inherited four-state R3 regression: passed")
    print("      all controlled knob states legal: %s" % bounded)
    print("      normalized distance to reference never increases: %s" % stable)
    print("      first control update actually changes knobs: %s" % moved)
    print("      final registered state approaches reference: %s" % near_reference)
    print("      creativity excluded from knob vector: %s" % no_creativity_knob)
    print("      feedback-control activation/tick boundary: %s" % boundary_ok)
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _selftest


def _fmt_strategy(d):
    return ", ".join("%s=%s" % (k, d[k]) for k in KNOBS)


def main():
    print("[P8.041 ARCHITECTURE] operational R3 control + certificate-coherent I4 FUTUREBANK")
    print("[P8.041 CONTROL] closed-loop proportional reference tracking; no inverse/antipode/half-turn at runtime")
    print("[P8.041 CONTROL] start stale >= %d; update every %d stale expansions; max steps=%d"
          % (CONTROL_START_STALE, CONTROL_TICK, MAX_CONTROL_STEPS))
    print("[P8.041 KNOBS] creativity is derived/not controlled; actual strategy knobs: %s"
          % ", ".join(KNOBS))
    print("[P8.041 LEAN] %s" % _fmt_strategy(LEAN))
    print("[P8.041 EMPIRICAL REFERENCE] %s" % _fmt_strategy(REFERENCE))
    print("[P8.041 CTRL_01] %s" % _fmt_strategy(control_profile(1)))
    print("[P8.041 CTRL_04] %s" % _fmt_strategy(control_profile(4)))
    print("[P8.041 CTRL_08] %s" % _fmt_strategy(control_profile(8)))
    return BASE7.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
