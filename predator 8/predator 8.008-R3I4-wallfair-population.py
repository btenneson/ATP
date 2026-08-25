#!/usr/bin/env python3
"""Predator 8.008-R3I4-wallfair-population.

Wall-clock-fair population scheduling for the operational (3,4) Halo search.

The earlier Predator 8 population scheduler conserved the global expansion
budget, but ran population agents sequentially until each agent exhausted its
assigned expansion share.  On Halo, one agent's multi-million-expansion share
was far larger than the experiment's wall-clock budget, so a three-hour run
never reached agents 2..8.

8.008 changes ONLY population scheduling.  It preserves Predator 8.007's:

* R3 saturation-triggered strategy switching;
* I4 DV-coherent FUTUREBANK;
* real-search and terminal-ground Metamath DV gates;
* full pre-target assertion index and target-blind policy;
* proof calculus and certificate emission;
* independent verifier boundary;
* global expansion budget (the original per-profile expansion shares remain
  hard caps, and their sum remains the declared global budget).

Each population profile now receives a bounded wall-clock slice.  At the start
of each agent, the remaining internal population clock is divided equally among
the agents still to run.  If an agent finishes early, its unused time is thereby
redistributed to the remaining agents.  If its slice expires, a POSIX real-time
alarm interrupts that independent search, its frontier is discarded, and the
scheduler advances to the next profile.  Assertion-usage counts remain shared
across profiles exactly as in the original in-process population scheduler.

For the GitHub Halo workflow the internal population clock is 10,720 seconds
(178m40s), leaving about 80 seconds inside the external 180-minute shell limit
for loading, return, certificate emission, and clean shutdown.  With eight
agents and no early finishes, the initial slice is 1,340 seconds (22m20s) each.

A slice expiration is a resource event, never a logical result.  UNKNOWN retains
its ordinary finite-resource meaning.  The independent Metamath verifier remains
authoritative for any emitted certificate.
"""
from __future__ import annotations

import importlib.util
import os
import re
import signal
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.007-R3I4-dvcoherent-imagination.py")
spec = importlib.util.spec_from_file_location("predator8_r3i4_dvcoherent", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.007-R3I4-dvcoherent-imagination")
BASE7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE7)

P8 = BASE7.P8
P8.VERSION = "8.008-R3I4-wallfair-population"
_PROVE_ONE = P8.prove
_ORIG_SELFTEST = P8.cmd_selftest

DEFAULT_POP_WALL_SECONDS = 10720.0  # 178m40s inside the external 180m clock.
_PROGRESS_RE = re.compile(r"\]\s+([0-9][0-9,]*) expansions\b")


class _AgentSliceExpired(BaseException):
    """Internal scheduling event raised by SIGALRM; not a proof/search failure."""


def _remaining_slice(remaining_wall, remaining_agents):
    if remaining_agents <= 0:
        return 0.0
    return max(0.0, float(remaining_wall) / int(remaining_agents))


def _wall_seconds_from_env():
    raw = os.environ.get("PREDATOR_POP_WALL_SECONDS", str(DEFAULT_POP_WALL_SECONDS))
    try:
        sec = float(raw)
    except ValueError:
        raise SystemExit("PREDATOR_POP_WALL_SECONDS must be numeric")
    if sec <= 0:
        raise SystemExit("PREDATOR_POP_WALL_SECONDS must be positive")
    return sec


def prove_population_wallfair(goal_tree, index, budget, max_depth, agents=4,
                              creativity=0.55, seed=0, rank=None, say=print,
                              progress=2000, max_open=6, opener_cap=48):
    """Run every population profile under one fair internal wall-clock budget.

    Expansion shares are still computed by the original scheduler and remain
    hard per-agent caps, so the declared global expansion budget is never
    multiplied.  Wall time is a second, independent finite resource.
    """
    profiles = P8.make_profiles(agents, creativity, opener_cap)
    shares = P8.schedule_budgets(budget, profiles)
    shared_use = defaultdict(int)
    total_exp_observed = 0

    if not profiles:
        return None, 0, None

    wall_total = _wall_seconds_from_env()
    started = time.perf_counter()
    deadline = started + wall_total

    if say:
        say("    wall-clock-fair population: %d agents, internal wall budget %.0fs; expansion shares still sum to %s"
            % (len(profiles), wall_total, f"{sum(shares):,}"))
        if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
            say("    WARNING: POSIX wall-slice alarms unavailable; falling back to original sequential population scheduler")
            return P8._P8008_ORIG_POPULATION(
                goal_tree, index, budget, max_depth, agents=agents,
                creativity=creativity, seed=seed, rank=rank, say=say,
                progress=progress, max_open=max_open, opener_cap=opener_cap)

    for i, (profile, share) in enumerate(zip(profiles, shares), 1):
        now = time.perf_counter()
        remaining_wall = deadline - now
        remaining_agents = len(profiles) - i + 1
        if remaining_wall <= 0:
            if say:
                say("    population wall budget exhausted before agent %d/%d" % (i, len(profiles)))
            break
        if share <= 0:
            continue

        slice_seconds = _remaining_slice(remaining_wall, remaining_agents)
        last_seen = [0]

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

        if say:
            say("    agent %d/%d: %-46s expansion cap %s; wall slice %.1fs"
                % (i, len(profiles), profile.summary(), f"{share:,}", slice_seconds))

        previous_handler = signal.getsignal(signal.SIGALRM)

        def _expire(_signum, _frame):
            raise _AgentSliceExpired()

        result = None
        used = 0
        agent_started = time.perf_counter()
        try:
            signal.signal(signal.SIGALRM, _expire)
            signal.setitimer(signal.ITIMER_REAL, slice_seconds)
            result, used = _PROVE_ONE(
                goal_tree, index, share, max_depth, rank=rank, say=agent_say,
                progress=progress, max_open=max_open, profile=profile,
                seed=int(seed) + 1000003 * (i - 1), shared_use=shared_use,
                agent_name=profile.name)
        except _AgentSliceExpired:
            # The search routine reports exact expansion counts only on normal
            # return.  Progress lines provide a conservative observed lower
            # bound for an interrupted slice; never pretend it is exact.
            used = last_seen[0]
            if say:
                say("    agent %d/%d wall slice expired after %.1fs; observed at least %s expansions; advancing to next profile"
                    % (i, len(profiles), time.perf_counter() - agent_started,
                       f"{used:,}"))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous_handler)

        total_exp_observed += used
        if result is not None:
            if say:
                say("    wall-fair population winner: agent %d/%d %s after %.1fs total population wall time"
                    % (i, len(profiles), profile.name,
                       time.perf_counter() - started))
            return result, total_exp_observed, profile.name

    if say:
        say("    wall-fair population completed/expired: all reachable profiles were given a slice; observed expansion lower bound %s; %.1fs elapsed"
            % (f"{total_exp_observed:,}", time.perf_counter() - started))
    return None, total_exp_observed, None


# Preserve the original scheduler for non-POSIX fallback, then install 8.008.
P8._P8008_ORIG_POPULATION = P8.prove_population
P8.prove_population = prove_population_wallfair


def _cmd_selftest_wallfair(a):
    rc = _ORIG_SELFTEST(a)
    if rc:
        return rc
    total = 10720.0
    first = _remaining_slice(total, 8)
    # If agent 1 returns 100 s early, its unused time is redistributed rather
    # than lost: seven remaining agents each receive a larger prospective slice.
    after_early = _remaining_slice(total - 100.0, 7)
    profiles = P8.make_profiles(8, 0.65, 96)
    shares = P8.schedule_budgets(50000000, profiles)
    ok = (len(profiles) == 8
          and abs(first - 1340.0) < 1e-9
          and after_early > first
          and sum(shares) == 50000000
          and all(x > 0 for x in shares))
    print("  [7] wall-fair population gives all 8 profiles bounded time while conserving the expansion budget")
    print("      first slice %.0fs; early-finish redistributed slice %.1fs; expansion shares sum %s"
          % (first, after_early, f"{sum(shares):,}"))
    print("      %s\n" % ("passed" if ok else "FAILED"))
    return 0 if ok else 1


P8.cmd_selftest = _cmd_selftest_wallfair


def main():
    return BASE7.main()


if __name__ == "__main__":
    raise SystemExit(main() or 0)
