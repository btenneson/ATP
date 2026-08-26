#!/usr/bin/env python3
"""Predator 8.012: asymmetric H-guided pair with a genuine (3,4) controller.

This experiment preserves the proof semantics and verifier boundary of
Predator 8.011.  The only intended change is search control:

* P1 remains the stable reflective (1,3) partner.
* P2 is promoted from nominal (2,4) to active/native (3,4).
* P2 observes its own H-hat trend and stagnation and switches among several
  predeclared search strategies instead of remaining on one fixed policy.

The (3,4) coordinate is therefore behavioral rather than cosmetic.  Strategy
switches may reorder legal proof attempts; they never add inference rules,
relax unification, enter the BANK as proof, or certify theoremhood.  Only the
ordinary emitted Metamath certificate plus the unchanged verifier can settle
the target.
"""
from __future__ import annotations

import importlib.util
import os
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.011-H-goal.py")
spec = importlib.util.spec_from_file_location("predator8_hgoal_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.011-H-goal")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
P8 = B.P8
P8.VERSION = "8.012-control-selfaware-34"

SWITCH_STALE = max(2, int(os.environ.get("PREDATOR_34_SWITCH_STALE", "4")))
SWITCH_MIN_EXP = max(100, int(os.environ.get("PREDATOR_34_SWITCH_MIN_EXP", "500")))
IMPROVE_EPS = max(0.0, float(os.environ.get("PREDATOR_34_IMPROVE_EPS", "0.10")))

# Keep an immutable copy of each profile's original policy so strategy changes
# are reproducible and do not compound multiplicatively across calls.
_PROFILE_BASE = {}
_ORIG_SCORE = B.P810._scored_with_partner


def _base_profile(profile):
    key = id(profile)
    if key not in _PROFILE_BASE:
        _PROFILE_BASE[key] = (
            profile.temperature,
            profile.novelty,
            profile.rarity,
            profile.lemma,
            profile.exploration,
            profile.opener_cap,
        )
    return _PROFILE_BASE[key]


def _apply_mode(profile, mode):
    """Apply one predeclared controller strategy to P2's search profile."""
    temp, nov, rare, lemma, explore, cap = _base_profile(profile)
    if mode == "exploit":
        profile.temperature = 0.45 * temp
        profile.novelty = 0.60 * nov
        profile.rarity = 0.60 * rare
        profile.lemma = 1.20 * lemma
        profile.exploration = max(0.03, 0.50 * explore)
        profile.opener_cap = cap
    elif mode == "diversify":
        profile.temperature = 1.60 * temp
        profile.novelty = 1.60 * nov
        profile.rarity = 1.50 * rare
        profile.lemma = 0.70 * lemma
        profile.exploration = min(0.85, explore + 0.30)
        profile.opener_cap = max(cap, int(round(1.25 * cap)))
    elif mode == "lemma":
        profile.temperature = 0.70 * temp
        profile.novelty = 0.90 * nov
        profile.rarity = 1.10 * rare
        profile.lemma = 2.40 * lemma
        profile.exploration = max(0.05, 0.75 * explore)
        profile.opener_cap = cap
    else:
        profile.temperature = temp
        profile.novelty = nov
        profile.rarity = rare
        profile.lemma = lemma
        profile.exploration = explore
        profile.opener_cap = cap


def _controlled_score(goal, items, base_scores, profile, rng,
                      local_use, shared_use, channel, agent_name):
    """Use P2's current strategy before invoking the unchanged 8.010 scorer."""
    mode = getattr(channel, "strategy_mode", {}).get(agent_name, "native")
    if getattr(channel, "controller_name", None) == agent_name:
        _apply_mode(profile, mode)
    return _ORIG_SCORE(
        goal, items, base_scores, profile, rng,
        local_use, shared_use, channel, agent_name)


# 8.011's search loop calls the 8.010 partner scorer directly.  Replacing only
# that scorer lets us reuse the proof-search implementation unchanged while
# making the controller's current strategy operational.
B.P810._scored_with_partner = _controlled_score


class Control34Channel(B.HPartnerChannel):
    """H telemetry plus reflective strategy selection for exactly one partner."""

    def __init__(self, names, say=print):
        super().__init__(names, say=say)
        self.controller_name = names[1]
        self.native[names[0]] = (1, 3)
        self.native[names[1]] = (3, 4)
        self.active[names[0]] = (1, 3)
        self.active[names[1]] = (3, 4)
        self.personality[names[0]] = "reflective-stable"
        self.personality[names[1]] = "control-selfaware"

        self.strategy_mode = {names[0]: "native", names[1]: "exploit"}
        self.strategy_switches = []
        self.last_switch_exp = {names[0]: 0, names[1]: 0}
        self.last_report_h = {names[0]: float("inf"), names[1]: float("inf")}
        self.last_best_at_switch = {names[0]: float("inf"), names[1]: float("inf")}

    def request_surge(self, mode, seconds=0.35):
        """Never let a pair-max surge demote the native (3,4) controller."""
        with self.lock:
            self._maybe_end_surge()
            if self.surge_mode is not None:
                return
            self.surge_mode = mode
            self.surge_until = time.monotonic() + max(0.05, float(seconds))
            if mode == "pair-max":
                self.active[self.names[0]] = (2, 4)
                self.active[self.names[1]] = (3, 4)
            else:
                self.active[self.names[0]] = (3, 4)
                self.active[self.names[1]] = (3, 4)
            self.surge_events.append(
                "ENTER:%s:%s+%s" % (
                    mode, self.active[self.names[0]], self.active[self.names[1]]))
            if self.say:
                self.say(
                    "      [PAIR] surge enter %s -> P1 %s, P2 %s; "
                    "P2 is never demoted below native (3,4)"
                    % (mode, self.active[self.names[0]], self.active[self.names[1]]))

    def _switch(self, name, exp, new_mode, reason, estimate):
        old = self.strategy_mode[name]
        if new_mode == old:
            return
        self.strategy_mode[name] = new_mode
        self.last_switch_exp[name] = int(exp)
        self.last_best_at_switch[name] = self.best_h_hat[name]
        row = {
            "agent": name,
            "expansions": int(exp),
            "from": old,
            "to": new_mode,
            "reason": reason,
            "h_hat": float(estimate),
            "best_h_hat": float(self.best_h_hat[name]),
            "stale": int(self.stale[name]),
        }
        self.strategy_switches.append(row)
        if self.say:
            self.say(
                "      [%s CONTROL (3,4)] %s -> %s at exp=%s; "
                "h_hat=%.3f best=%.3f stale=%d; %s"
                % (name, old, new_mode, f"{exp:,}", estimate,
                   self.best_h_hat[name], self.stale[name], reason))

    def publish_h(self, name, exp, open_goals, goal_text, candidate_labels,
                  estimate, duplicate_hint=0.0):
        previous_best = self.best_h_hat[name]
        previous_h = self.last_report_h[name]
        super().publish_h(
            name, exp, open_goals, goal_text, candidate_labels,
            estimate, duplicate_hint=duplicate_hint)
        self.last_report_h[name] = float(estimate)

        if name != self.controller_name:
            return

        since_switch = int(exp) - self.last_switch_exp[name]
        genuine_improvement = (
            previous_best < float("inf")
            and estimate <= previous_best - IMPROVE_EPS)
        report_improvement = (
            previous_h < float("inf")
            and estimate <= previous_h - IMPROVE_EPS)

        # Improvement is evidence that the present basin is productive, so
        # return to a focused exploit policy.  Stagnation causes a policy
        # change rather than simply spending the remainder of the budget in
        # the same basin.
        if (genuine_improvement or report_improvement) and since_switch >= SWITCH_MIN_EXP:
            self._switch(
                name, exp, "exploit",
                "estimated settlement distance improved; exploit this basin",
                estimate)
            return

        if self.stale[name] < SWITCH_STALE or since_switch < SWITCH_MIN_EXP:
            return

        mode = self.strategy_mode[name]
        if mode == "exploit":
            nxt = "diversify"
            reason = "stagnation under exploit; widen counterfactual search"
        elif mode == "diversify":
            nxt = "lemma"
            reason = "diversification did not improve H-hat; seek lower-hypothesis lemmas"
        else:
            nxt = "diversify"
            reason = "lemma-seeking stagnated; reopen a different basin"
        self._switch(name, exp, nxt, reason, estimate)


def prove_population_control34(goal_tree, index, budget, max_depth, agents=2,
                               creativity=0.55, seed=0, rank=None, say=print,
                               progress=1000, max_open=6, opener_cap=48):
    if agents != 2 and say:
        say(
            "    control-(3,4) engine uses exactly 2 P agents; "
            "--agents=%d ignored" % agents)

    profiles = P8.make_profiles(2, creativity, opener_cap)
    profiles[0].name = "P1-reflective-(1,3)-H"
    profiles[1].name = "P2-control-selfaware-(3,4)-H"
    shares = P8.schedule_budgets(budget, profiles)
    names = [p.name for p in profiles]
    channel = Control34Channel(names, say=say)
    stop = threading.Event()
    shared_use = B.defaultdict(int)
    results = [None, None]
    used = [0, 0]

    if say:
        say(
            "    asymmetric H pair: stable P1 (1,3) + control-self-aware P2 (3,4)")
        say(
            "    P2 strategies: exploit / diversify / lemma; switches require "
            "observed stagnation or H-hat improvement")
        say(
            "    switch controls: stale=%d min-exp=%d improve-eps=%.3f"
            % (SWITCH_STALE, SWITCH_MIN_EXP, IMPROVE_EPS))
        say(
            "    verifier boundary unchanged: strategy control cannot certify proof")

    def worker(i):
        res, n = B.prove_partner_h(
            goal_tree, index, shares[i], max_depth, profiles[i],
            int(seed) + 1000003 * i, channel, stop, shared_use, names[i],
            say=say, progress=progress, max_open=max_open)
        results[i] = res
        used[i] = n
        if res is not None:
            stop.set()

    threads = [
        threading.Thread(
            target=worker, args=(i,), name=names[i], daemon=True)
        for i in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    winner = None
    result = None
    for i, res in enumerate(results):
        if res is not None:
            result = res
            winner = names[i]
            break

    if say:
        say(
            "    CONTROL34 telemetry: switches=%d final-modes=%s"
            % (len(channel.strategy_switches), channel.strategy_mode))
        for row in channel.strategy_switches[-12:]:
            say(
                "      CONTROL34 switch exp=%s %s->%s h_hat=%.3f stale=%d"
                % (f"{row['expansions']:,}", row["from"], row["to"],
                   row["h_hat"], row["stale"]))
        say(
            "    H telemetry: reports=%d alerts=%d best=%s"
            % (
                len(channel.h_history),
                len(channel.h_alerts),
                {n: round(channel.best_h_hat[n], 3) for n in names},
            ))
        say(
            "    H edge predictions: improving=%s predicted_geodesic=%s"
            % (channel.h_improving_edges, channel.predicted_geodesic))
        say(
            "    partner expansion accounting: %s / global cap %s"
            % (f"{sum(used):,}", f"{budget:,}"))

    return result, sum(used), winner


P8.prove_population = prove_population_control34


def main():
    return P8.main()


if __name__ == "__main__":
    main()
