#!/usr/bin/env python3
"""Predator 8.011: Partner 8.010 with an H-guided control layer.

The mathematical proof geometry is deliberately kept separate from the
controller:

* one legal logical assertion application is one exact proof edge;
* independent Metamath verifier acceptance is the terminal proof edge;
* partner messages, heap scores, novelty, imagination, and surge are control
  metadata and are not proof edges.

The exact shortest-path horizon h is generally oracle-only.  This experiment
therefore uses an explicitly non-authoritative estimate h_hat to order search
and trigger extra attention near promising states.  h_hat can waste resources;
it can never certify a theorem.  Certificate emission and independent
verification are inherited unchanged from Predator 8.001 through 8.010.
"""
from __future__ import annotations

import heapq
import importlib.util
import math
import os
import random
import threading
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.010-partner-pair.py")
spec = importlib.util.spec_from_file_location("predator8_partner_hbase", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.010")
P810 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P810)
P8 = P810.P8
P8.VERSION = "8.011-h-goal"

H_WEIGHT = max(0.0, float(os.environ.get("PREDATOR_H_WEIGHT", "0.30")))
H_SURGE = max(1.0, float(os.environ.get("PREDATOR_H_SURGE", "4.0")))
H_TOKEN_WEIGHT = max(0.0, float(os.environ.get("PREDATOR_H_TOKEN_WEIGHT", "0.015")))


def _goal_token_count(goals, sub):
    """Cheap proof-state complexity feature; control-only, never a certificate."""
    total = 0
    for g, _slot, _hix in goals:
        try:
            total += min(200, len(P8.apply_sub(g, sub).tokens()))
        except (RecursionError, AttributeError):
            total += 200
    return total


def h_hat(goals, sub):
    """Non-authoritative estimate of remaining unit proof distance.

    The rigorous lower-bound component is 1 + number_of_open_goals for a
    non-accepted node in the unit-edge geometry.  A small formula-size term
    breaks ties.  The result is *not* the exact h and is never used as a proof.
    """
    k = len(goals)
    if k == 0:
        # A closed candidate is one verifier edge from ACCEPT only if V accepts.
        # We do not know that online, so 1 is an optimistic estimate.
        return 1.0
    return 1.0 + float(k) + H_TOKEN_WEIGHT * _goal_token_count(goals, sub)


class HPartnerChannel(P810.PartnerChannel):
    """8.010 partner channel plus non-authoritative H telemetry."""

    def __init__(self, names, say=print):
        super().__init__(names, say=say)
        self.best_h_hat = {n: float("inf") for n in names}
        self.h_history = []
        self.h_alerts = []
        self.predicted_geodesic = {n: 0 for n in names}
        self.h_improving_edges = {n: 0 for n in names}

    def publish_h(self, name, exp, open_goals, goal_text, candidate_labels,
                  estimate, duplicate_hint=0.0):
        """Publish ordinary partner state, then add H-specific control telemetry."""
        super().publish(
            name, exp, open_goals, goal_text, candidate_labels,
            duplicate_hint=duplicate_hint)
        with self.lock:
            estimate = float(estimate)
            improved = estimate < self.best_h_hat[name] - 1e-12
            if improved:
                self.best_h_hat[name] = estimate
            row = {
                "sender": name,
                "expansions": int(exp),
                "h_hat": estimate,
                "best_h_hat": self.best_h_hat[name],
                "open_goals": int(open_goals),
                "improved": bool(improved),
                "authoritative": False,
            }
            self.h_history.append(row)

            if self.say:
                self.say(
                    "      [%s H] h_hat=%.3f best=%.3f open=%d "
                    "(estimate only; verifier remains authoritative)"
                    % (name, estimate, self.best_h_hat[name], open_goals))

            # This is deliberately a search-policy trigger only.  It does not
            # claim h < 1, h = 0, or theoremhood.
            if estimate <= H_SURGE:
                self.h_alerts.append((name, int(exp), estimate))
                if self.say:
                    self.say(
                        "      [%s H-ALERT] h_hat=%.3f <= %.3f; "
                        "requesting near-settlement surge"
                        % (name, estimate, H_SURGE))
                if self.surge_mode is None:
                    self.request_surge("pair-max")

    def record_edge_prediction(self, name, delta_hat):
        with self.lock:
            if delta_hat > 0.0:
                self.h_improving_edges[name] += 1
            # In the exact unit metric a geodesic edge decreases h by exactly 1.
            # delta_hat >= 0.75 is only a prediction of that event.
            if delta_hat >= 0.75:
                self.predicted_geodesic[name] += 1


def prove_partner_h(goal_tree, index, budget, max_depth, profile, seed,
                    channel, stop_event, shared_use, agent_name,
                    say=print, progress=1000, max_open=6):
    rng = random.Random(seed)
    local_use = defaultdict(int)
    start = P8.Node([(goal_tree, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    exp = tie = 0
    seen = set()
    report_every = max(
        100, int(os.environ.get("PREDATOR_PARTNER_REPORT", "250")))

    while frontier and exp < budget and not stop_event.is_set():
        priority, _, node = heapq.heappop(frontier)
        exp += 1

        if not node.goals:
            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            channel.final_candidate(agent_name)
            return (root, node.sub), exp

        if node.depth >= max_depth or len(node.goals) > max_open:
            continue

        current_hat = h_hat(node.goals, node.sub)
        gi = P8.pick_goal(node.goals, node.sub)
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = P8.apply_sub(gt, node.sub)

        key = (
            node.depth,
            " ".join(gt.tokens()),
            tuple(sorted(
                " ".join(P8.apply_sub(g, node.sub).tokens())
                for g, _, _ in rest)),
        )
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        ranked_c = P810._scored_with_partner(
            gt, closers, [0.0] * len(closers), profile, rng,
            local_use, shared_use, channel, agent_name)
        ranked_o = P810._scored_with_partner(
            gt, openers, [0.0] * len(openers), profile, rng,
            local_use, shared_use, channel, agent_name)
        chosen = ranked_c + P8._counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng)
        candidate_labels = tuple(item[1][0] for item in chosen[:8])

        if exp == 1 or exp % report_every == 0:
            channel.publish_h(
                agent_name, exp, len(node.goals), " ".join(gt.tokens()),
                candidate_labels, current_hat,
                duplicate_hint=(len(seen) / max(1.0, float(exp))))

        if progress and say and exp % progress == 0:
            say(
                "      [%s] %s expansions, %d open goals, "
                "h_hat=%.3f active=%s"
                % (agent_name, f"{exp:,}", len(node.goals), current_hat,
                   channel.active[agent_name]))

        for candidate_score, (lab, ct, data) in chosen:
            if stop_event.is_set():
                break

            m = {}
            c2 = P8.rename_apart(ct, m)
            s2 = P8.unify(c2, gt, node.sub)
            if s2 is None:
                continue

            _, f_hyps, e_hyps, _ = data
            fmap = {
                var: m.get(var, P8.fresh(tc))
                for _, tc, var in f_hyps
            }
            for _, tc, var in f_hyps:
                m.setdefault(var, fmap[var])

            step = P8.Step(lab, fmap, data)
            newgoals = []
            ok = True
            for hj, (_, stat) in enumerate(e_hyps):
                try:
                    ht = P8.G.parse(stat[1:], "wff", index.by_tc)
                except (RecursionError, P8.MMError):
                    ht = None
                if ht is None:
                    ok = False
                    break
                newgoals.append((P8.rename_apart(ht, m), step, hj))
            if not ok:
                continue

            next_goals = newgoals + rest
            next_hat = h_hat(next_goals, s2)
            delta_hat = current_hat - next_hat
            channel.record_edge_prediction(agent_name, delta_hat)

            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1

            # Preserve the 8.010 controller and add a bounded H-descent term.
            # This priority is NOT the mathematical unit edge cost.
            guide = math.tanh(candidate_score / 2.0)
            base_edge_cost = (0.25 if not e_hyps else 1.0) - 0.20 * guide
            h_bonus = H_WEIGHT * math.tanh(delta_hat)
            edge_priority_cost = max(0.05, base_edge_cost - h_bonus)
            state_cost = 0.02 * len(next_goals)

            heapq.heappush(
                frontier,
                (
                    priority + edge_priority_cost + state_cost,
                    tie,
                    P8.Node(
                        next_goals,
                        s2,
                        node.trail + ((slot, hix, step),),
                        node.depth + 1,
                    ),
                ),
            )

    return None, exp


def prove_population_h(goal_tree, index, budget, max_depth, agents=2,
                       creativity=0.55, seed=0, rank=None, say=print,
                       progress=1000, max_open=6, opener_cap=48):
    if agents != 2 and say:
        say(
            "    H-partner engine uses exactly 2 P agents; "
            "--agents=%d ignored" % agents)

    profiles = P8.make_profiles(2, creativity, opener_cap)
    profiles[0].name = "P1-reflective-(1,3)-H"
    profiles[1].name = "P2-strategic-(2,4)-H"
    shares = P8.schedule_budgets(budget, profiles)
    names = [p.name for p in profiles]
    channel = HPartnerChannel(names, say=say)
    stop = threading.Event()
    shared_use = defaultdict(int)
    results = [None, None]
    used = [0, 0]

    if say:
        say(
            "    H-guided communicating P pair: exact proof edges are unit "
            "logical transitions; h_hat is control-only")
        say(
            "    H controls: weight=%.3f surge-threshold=%.3f "
            "token-weight=%.4f" % (H_WEIGHT, H_SURGE, H_TOKEN_WEIGHT))
        say(
            "    verifier boundary unchanged: no H estimate can certify proof")

    def worker(i):
        res, n = prove_partner_h(
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
            "    partner telemetry: %d state packets, %d advice messages, "
            "surges=%s"
            % (
                len(channel.history),
                len(channel.messages),
                channel.surge_events or "none",
            ))
        say(
            "    partner expansion accounting: %s / global cap %s"
            % (f"{sum(used):,}", f"{budget:,}"))

    return result, sum(used), winner


P8.prove_population = prove_population_h


def main():
    return P8.main()


if __name__ == "__main__":
    main()
