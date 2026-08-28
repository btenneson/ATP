#!/usr/bin/env python3
"""Predator 8.030: adaptive shortcut-aware prcom controller.

Revision of 8.029 driven by the five-seed shortcut experiment.

Adaptive awareness state machine:
  REST      : (C,I) = (0,5)   default
  SURGE     : (C,I) = (2,5)   temporary control surge on stagnation
  TORPOR-1  : (C,I) = (0,4)   first reduced-imagination recovery state
  TORPOR-2  : (C,I) = (0,3)   deeper torpor before brute fallback
  BRUTE     : (C,I) = (0,0)

I=6 is intentionally not an admissible adaptive state.

The I=4 profile is a genuine intermediate search profile.  It is not merely a
coordinate label.  It sits between the established I=5 shortcut profile and the
recovered I=3/native 8.002 explorer profile.

The controller preserves 8.029's verified shortcut macros, 8.028 quotienting,
8.019 verifier gate, and independent external certificate check.  Awareness
changes affect search ordering only; proof admissibility and verification are
unchanged.
"""
from __future__ import annotations

import inspect
import linecache
import sys

import predator8_016_prcom_exactify as P
import predator8_019_selective_sink as S
import predator8_029_prcom_shortcut_macros as M


VERSION = "8.030-adaptive-shortcut"
DEFAULT_COORD = (0, 5)
SURGE_COORD = (2, 5)
TORPOR1_COORD = (0, 4)
TORPOR2_COORD = (0, 3)
BRUTE_COORD = (0, 0)


def _replace_once(src: str, old: str, new: str, label: str) -> str:
    if old not in src:
        raise RuntimeError("8.019 source changed: %s patch anchor missing" % label)
    return src.replace(old, new, 1)


def install_adaptive_state_machine():
    """Patch 8.019's control transitions before 8.029 adds shortcut macros."""
    src = inspect.getsource(S.adaptive_guided_selective)

    old_stale = """    stale_native, stale_high, stale_low = 1200, 1200, 2400
"""
    new_stale = """    # 8.030 data-calibrated control clock.  Four of the successful I=5
    # treatments settled within 134 outer expansions, so 1,200-expansion
    # stagnation is far too slow for macro-search wall time.
    stale_native, stale_high, stale_low = 160, 100, 140
    deep_torpor = False
"""
    src = _replace_once(src, old_stale, new_stale, "deep-torpor init")

    old_progress_exit = """            if mode == "low":
                oldm = mode
                mode = "native"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                transitions.append((total_used, oldm, mode,
                                    "torpor progress -> native"))
                say("      [CONTROL] TORPOR EXIT %s -> %s: progress restored"
                    % (B.COORD[oldm], B.COORD[mode]))
"""
    new_progress_exit = """            if mode in ("high", "low"):
                oldm = mode
                old_coord = B.COORD[oldm]
                if oldm == "low":
                    deep_torpor = False
                    B.COORD["low"] = (0, 4)
                mode = "native"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                transitions.append((total_used, oldm, mode,
                                    "%s progress -> default" % oldm))
                say("      [CONTROL] RECOVER %s -> %s: progress restored; default resumed"
                    % (old_coord, B.COORD[mode]))
"""
    src = _replace_once(src, old_progress_exit, new_progress_exit,
                        "progress returns to default")

    old_high_to_low = """            elif mode == "high" and stale >= stale_high:
                oldm = mode
                mode = "low"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                last_global_improve = exp
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "failed surge -> TORPOR"))
                say("      [CONTROL] TORPOR %s -> %s"
                    % (B.COORD[oldm], B.COORD[mode]))
"""
    new_high_to_low = """            elif mode == "high" and stale >= stale_high:
                oldm = mode
                deep_torpor = False
                B.COORD["low"] = (0, 4)
                mode = "low"
                profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                last_global_improve = exp
                transitions.append((exp + probe_used_total, oldm, mode,
                                    "failed surge -> TORPOR-1 (0,4)"))
                say("      [CONTROL] TORPOR-1 %s -> %s"
                    % (B.COORD[oldm], B.COORD[mode]))
"""
    src = _replace_once(src, old_high_to_low, new_high_to_low,
                        "SURGE to TORPOR-1")

    old_low_to_brute = """            elif mode == "low" and stale >= stale_low:
                transitions.append((exp + probe_used_total, mode, "brute",
                                    "failed torpor -> brute"))
                say("      [CONTROL] TORPOR %s -> brute %s"
                    % (B.COORD[mode], B.COORD["brute"]))
                return None, exp + probe_used_total, best_h, transitions, "brute-requested"
"""
    new_low_to_brute = """            elif mode == "low" and stale >= stale_low:
                if not deep_torpor:
                    old_coord = B.COORD["low"]
                    deep_torpor = True
                    B.COORD["low"] = (0, 3)
                    profile = B.make_mode_profile(E, mode, creativity, opener_cap)
                    last_global_improve = exp
                    transitions.append((exp + probe_used_total, mode, mode,
                                        "failed TORPOR-1 -> TORPOR-2 (0,3)"))
                    say("      [CONTROL] TORPOR-2 %s -> %s"
                        % (old_coord, B.COORD["low"]))
                else:
                    transitions.append((exp + probe_used_total, mode, "brute",
                                        "failed TORPOR-2 -> brute"))
                    say("      [CONTROL] TORPOR-2 %s -> brute %s"
                        % (B.COORD[mode], B.COORD["brute"]))
                    return None, exp + probe_used_total, best_h, transitions, "brute-requested"
"""
    src = _replace_once(src, old_low_to_brute, new_low_to_brute,
                        "TORPOR-1/TORPOR-2")

    filename = "<8.030 adaptive-state-machine>"
    # Register the transformed source so 8.029's inspect.getsource() can safely
    # apply the quotient/macro patch to this already-adaptive controller.
    linecache.cache[filename] = (
        len(src),
        None,
        [line + "\n" for line in src.splitlines()],
        filename,
    )
    ns = {}
    exec(compile(src, filename, "exec"), dict(S.__dict__), ns)
    S.adaptive_guided_selective = ns["adaptive_guided_selective"]


def install_adaptive_profiles():
    """Install distinct profiles/weights for REST, SURGE, and two torpor levels."""
    B = P.B
    original_profile = B.make_mode_profile
    old_coord = dict(B.COORD)
    old_h = dict(B.H_WEIGHT)
    old_ml = dict(B.ML_WEIGHT)

    def adaptive_profile(E, mode, creativity=0.55, opener_cap=48):
        coord = B.COORD[mode]
        i = coord[1]

        if i == 5:
            # Established 8.029 I=5 shortcut profile.
            return E.Profile("imagination-(%d,5)" % coord[0],
                             1.60, 0.95, 0.75, 0.10, 0.85,
                             max(96, opener_cap), 1.0)

        if i == 4:
            # Untested intermediate torpor profile.  Numerically between the
            # I=5 shortcut profile and the recovered I=3 explorer regime.
            return E.Profile("imagination-(0,4)-torpor1",
                             1.35, 0.75, 0.55, 0.12, 0.68,
                             max(80, opener_cap), 1.0)

        if i == 3:
            # Recovered 8.002 explorer profile, previously tested as I=3.
            return original_profile(E, "native", creativity, opener_cap)

        raise ValueError("adaptive 8.030 forbids imagination coordinate I=%s" % i)

    B.make_mode_profile = adaptive_profile
    B.COORD["native"] = DEFAULT_COORD
    B.COORD["high"] = SURGE_COORD
    B.COORD["low"] = TORPOR1_COORD
    B.COORD["brute"] = BRUTE_COORD

    # C is quiescent except during SURGE.
    B.H_WEIGHT["native"] = 0.0
    B.H_WEIGHT["high"] = 0.20
    B.H_WEIGHT["low"] = 0.0

    # Hold the learned-policy multiplier fixed so this experiment isolates the
    # adaptive coordinate/profile change rather than simultaneously ablating ML.
    B.ML_WEIGHT["native"] = 1.0
    B.ML_WEIGHT["high"] = 1.0
    B.ML_WEIGHT["low"] = 1.0

    def restore():
        B.make_mode_profile = original_profile
        B.COORD.clear(); B.COORD.update(old_coord)
        B.H_WEIGHT.clear(); B.H_WEIGHT.update(old_h)
        B.ML_WEIGHT.clear(); B.ML_WEIGHT.update(old_ml)

    return restore


def main():
    # First make the 8.019 state machine adaptive, then let 8.029 add its
    # structural quotient and verified macro transitions to that function.
    install_adaptive_state_machine()
    M.install_shortcut_controller()
    restore = install_adaptive_profiles()
    S.VERSION = VERSION

    print("[ADAPTIVE] Predator 8.030 adaptive shortcut controller ENABLED")
    print("[ADAPTIVE] default=(0,5) surge=(2,5) torpor-1=(0,4) torpor-2=(0,3)")
    print("[ADAPTIVE] I=6 REMOVED from admissible adaptive states")
    print("[ADAPTIVE] SURGE is temporary; H progress returns to default (0,5)")
    print("[ADAPTIVE] I=4 is an actual intermediate profile, not a label-only state")
    print("[SHORTCUT] 8.029 verified macro transitions retained; max span=3 primitive steps")
    print("[QUOTIENT] 8.028 structural-depth dominance retained")
    print("[VERIFY] verifier gate and independent certificate checking unchanged")
    try:
        return S.main()
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
