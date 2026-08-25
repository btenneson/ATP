#!/usr/bin/env python3
"""Predator 8.009-R3I4-saturation-relay.

Saturation-avoiding population scheduling for the operational (3,4) Halo search.

8.009 keeps the successful mathematical/search machinery of 8.008 unchanged:

* R3 saturation-triggered COMPASS/CERTIFY/DIVERSIFY/LEAN strategy switching;
* I4 DV-coherent FUTUREBANK with full accumulated Metamath DV obligations;
* real-search and terminal-ground DV gates;
* full pre-target assertion index and target-blind policy;
* proof calculus and certificate emission;
* independent Metamath verifier boundary;
* the same declared global expansion budget and eight population profiles.

The only substantive change is the OUTER resource policy.  In 8.008 each profile
received one wall-clock slice even if it had already spent thousands of
expansions in LEAN with no settlement-distance improvement.  8.009 treats that
condition as a resource diagnosis, never as a logical result:

1. Every profile still gets a bounded fair quantum (wall_total / profiles).
2. R3 is allowed to exhaust its own internal strategy ladder first.
3. A profile yields early only after substantial persistent saturation:
     a) >= 6,000 real expansions, strategy=LEAN, stale >= 9,000 and dup >= 35%; or
     b) stale >= 12,000 regardless of duplicate rate (hard stale ceiling).
4. Unused wall time is NOT handed as one ever-growing slice to the last profile.
   After all profiles have had a visit, remaining time starts another relay pass
   with fresh deterministic seeds.  Shared assertion-usage statistics survive
   across all visits, while the saturated private frontier is discarded.
5. Expansion shares remain hard cumulative per-profile caps.  Interrupted wall
   slices are conservatively charged through the next progress quantum so the
   declared global expansion budget cannot be exceeded by accounting error.

The intent is analogous to a relay/striped search: spend the fixed three-hour
clock on more independent useful basins instead of extending a basin after the
Level-3 controller has already diagnosed it as deeply stalled.

A saturation yield or wall-slice expiration is only a resource event.  UNKNOWN
retains its finite-resource meaning.  Only a certificate accepted by the
independent Metamath verifier counts as success.
"""
from __future__ import annotations

import importlib.util
import os
import re
import signal
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.008-R3I4-wallfair-population.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_wallfair", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.008-R3I4-wallfair-population")
BASE8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE8)

P8 = BASE8.P8
P8.VERSION = "8.009-R3I4-saturation-relay"
_PROVE_ONE = BASE8._PROVE_ONE
_ORIG_SELFTEST = P8.cmd_selftest

DEFAULT_POP_WALL_SECONDS = 10720.0
MIN_EXP_BEFORE_YIELD = 6000
SOFT_STALE_YIELD = 9000
SOFT_DUP_PERCENT = 35.0
HARD_STALE_YIELD = 12000
_PROGRESS_RE = re.compile(r"\]\s+([0-9][0-9,]*) expansions\b")
_SAT_RE = re.compile(
    r"strategy=([A-Z]+),\s*stale=([0-9][0-9,]*),\s*dup=([0-9]+(?:\.[0-9]+)?)%")


class _AgentSliceExpired(BaseException):
    """Wall-clock scheduling event, not a proof/search failure."""


class _AgentSaturated(BaseException):
    """Deep-saturation resource event, not a logical result."""


def _wall_seconds_from_env():
    raw = os.environ.get("PREDATOR_POP_WALL_SECONDS", str(DEFAULT_POP_WALL_SECONDS))
    try:
        sec = float(raw)
    except ValueError:
        raise SystemExit("PREDATOR_POP_WALL_SECONDS must be numeric")
    if sec <= 0:
        raise SystemExit("PREDATOR_POP_WALL_SECONDS must be positive")
    return sec


def _should_yield(expansions, strategy, stale, dup_percent):
    """Conservative outer saturation gate after R3 has had room to react."""
    if expansions < MIN_EXP_BEFORE_YIELD:
        return False
    if stale >= HARD_STALE_YIELD:
        return True
    return (strategy == "LEAN"
            and stale >= SOFT_STALE_YIELD
            and dup_percent >= SOFT_DUP_PERCENT)


def _charge_interrupted(last_seen, progress, remaining_cap):
    """Conservative expansion-budget charge for an asynchronously cut slice."""
    if remaining_cap <= 0:
        return 0
    quantum = max(1, int(progress) if progress else 1)
    return min(int(remaining_cap), int(last_seen) + quantum)


def prove_population_saturation_relay(goal_tree, index, budget, max_depth,
                                      agents=4, creativity=0.55, seed=0,
                                      rank=None, say=print, progress=2000,
                                      max_open=6, opener_cap=48):
    """Run bounded fair quanta; relay leftover time away from deep saturation."""
    profiles = P8.make_profiles(agents, creativity, opener_cap)
    shares = P8.schedule_budgets(budget, profiles)
    shared_use = defaultdict(int)
    total_exp_observed = 0

    if not profiles:
        return None, 0, None

    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        if say:
            say("    WARNING: POSIX alarms unavailable; falling back to 8.008 wall-fair scheduler")
        return BASE8.prove_population_wallfair(
            goal_tree, index, budget, max_depth, agents=agents,
            creativity=creativity, seed=seed, rank=rank, say=say,
            progress=progress, max_open=max_open, opener_cap=opener_cap)

    wall_total = _wall_seconds_from_env()
    started = time.perf_counter()
    deadline = started + wall_total
    quantum = wall_total / len(profiles)
    remaining_caps = list(shares)
    saturation_yields = [0] * len(profiles)
    visits = [0] * len(profiles)
    round_no = 0

    if say:
        say("    saturation-relay population: %d agents, internal wall budget %.0fs; fair quantum %.1fs; expansion shares sum %s"
            % (len(profiles), wall_total, quantum, f"{sum(shares):,}"))
        say("    relay gate: after >=%s expansions, yield at LEAN stale>=%s with dup>=%.1f%%, or hard stale>=%s"
            % (f"{MIN_EXP_BEFORE_YIELD:,}", f"{SOFT_STALE_YIELD:,}",
               SOFT_DUP_PERCENT, f"{HARD_STALE_YIELD:,}"))

    while time.perf_counter() < deadline and any(x > 0 for x in remaining_caps):
        round_no += 1
        any_visit = False
        if say:
            say("    relay pass %d starting; %.1fs population wall time remains"
                % (round_no, max(0.0, deadline - time.perf_counter())))

        for pi, profile in enumerate(profiles):
            remaining_wall = deadline - time.perf_counter()
            if remaining_wall <= 0:
                break
            if remaining_caps[pi] <= 0:
                continue

            any_visit = True
            visits[pi] += 1
            slice_seconds = min(quantum, remaining_wall)
            visit_seed = (int(seed)
                          + 1000003 * pi
                          + 10000019 * (round_no - 1))
            last_seen = [0]
            yielded = [False]
            sat_snapshot = [None]
            agent_label = "%s/r%d" % (profile.name, round_no)

            def agent_say(msg):
                text = str(msg)
                m = _PROGRESS_RE.search(text)
                if m:
                    try:
                        last_seen[0] = max(last_seen[0], int(m.group(1).replace(",", "")))
                    except ValueError:
                        pass
                if say:
                    say(text)
                if yielded[0]:
                    return
                sm = _SAT_RE.search(text)
                if m and sm:
                    try:
                        exp_now = int(m.group(1).replace(",", ""))
                        strategy = sm.group(1)
                        stale = int(sm.group(2).replace(",", ""))
                        dup = float(sm.group(3))
                    except ValueError:
                        return
                    if _should_yield(exp_now, strategy, stale, dup):
                        yielded[0] = True
                        sat_snapshot[0] = (exp_now, strategy, stale, dup)
                        raise _AgentSaturated()

            if say:
                say("    visit %s: remaining expansion cap %s; wall quantum %.1fs; seed=%d"
                    % (agent_label, f"{remaining_caps[pi]:,}", slice_seconds, visit_seed))

            previous_handler = signal.getsignal(signal.SIGALRM)

            def _expire(_signum, _frame):
                raise _AgentSliceExpired()

            result = None
            used_exact = None
            interrupted = False
            saturated = False
            visit_started = time.perf_counter()
            try:
                signal.signal(signal.SIGALRM, _expire)
                signal.setitimer(signal.ITIMER_REAL, slice_seconds)
                result, used_exact = _PROVE_ONE(
                    goal_tree, index, remaining_caps[pi], max_depth,
                    rank=rank, say=agent_say, progress=progress,
                    max_open=max_open, profile=profile, seed=visit_seed,
                    shared_use=shared_use, agent_name=agent_label)
            except _AgentSaturated:
                saturated = True
                saturation_yields[pi] += 1
                used_exact = last_seen[0]
                snap = sat_snapshot[0]
                if say and snap is not None:
                    say("    SATURATION YIELD %s after %.1fs at exp=%s strategy=%s stale=%s dup=%.1f%%; relaying unused time"
                        % (agent_label, time.perf_counter() - visit_started,
                           f"{snap[0]:,}", snap[1], f"{snap[2]:,}", snap[3]))
            except _AgentSliceExpired:
                interrupted = True
                if say:
                    say("    wall quantum expired for %s after %.1fs; observed at least %s expansions"
                        % (agent_label, time.perf_counter() - visit_started,
                           f"{last_seen[0]:,}"))
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
                signal.signal(signal.SIGALRM, previous_handler)

            if interrupted:
                charge = _charge_interrupted(last_seen[0], progress,
                                             remaining_caps[pi])
                observed = last_seen[0]
            else:
                # Saturation is raised synchronously from a progress line, so
                # last_seen is exact at that interruption point.  Normal return
                # also supplies the exact expansion count.
                charge = min(remaining_caps[pi], int(used_exact or 0))
                observed = int(used_exact or 0)

            remaining_caps[pi] -= charge
            total_exp_observed += observed

            if result is not None:
                if say:
                    say("    saturation-relay winner: %s after %.1fs total population wall time"
                        % (agent_label, time.perf_counter() - started))
                return result, total_exp_observed, agent_label

            # A non-saturated normal return means this seed exhausted its
            # reachable finite search before the wall quantum; a fresh seed on
            # a later relay pass is allowed to explore a different basin.
            if saturated:
                continue

        if not any_visit:
            break

    if say:
        say("    saturation-relay ended after %d pass(es), %.1fs elapsed; observed expansion lower bound %s"
            % (round_no, time.perf_counter() - started,
               f"{total_exp_observed:,}"))
        say("    relay visits=%s; saturation-yields=%s; conservative remaining expansion budget=%s"
            % (visits, saturation_yields, f"{sum(remaining_caps):,}"))
    return None, total_exp_observed, None


P8.prove_population = prove_population_saturation_relay


def _cmd_selftest_saturation_relay(a):
    rc = _ORIG_SELFTEST(a)
    if rc:
        return rc
    cases = [
        (_should_yield(5999, "LEAN", 20000, 99.0), False),
        (_should_yield(9000, "DIVERSIFY", 10000, 80.0), False),
        (_should_yield(9000, "LEAN", 9000, 35.0), True),
        (_should_yield(9000, "LEAN", 9000, 20.0), False),
        (_should_yield(12000, "LEAN", 12000, 0.0), True),
    ]
    cap_ok = (_charge_interrupted(5000, 1000, 100000) == 6000
              and _charge_interrupted(5000, 1000, 5500) == 5500)
    ok = all(got == want for got, want in cases) and cap_ok
    print("  [8] saturation relay yields only after deep R3/LEAN staleness and conserves interrupted expansion caps")
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _cmd_selftest_saturation_relay


def main():
    return BASE8.BASE7.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
