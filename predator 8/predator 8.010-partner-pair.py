#!/usr/bin/env python3
"""Predator 8.010: communicating heterogeneous P-partner pair.

This front-end preserves Predator 8.001 proof semantics, parsing, target-blind
indexing, certificate emission, and independent Metamath verification.  It
changes only search control.

Two prover partners have native awareness coordinates (1,3) and (2,4).  They
run concurrently under one conserved global expansion budget and communicate
through a direct PartnerChannel containing non-authoritative state packets,
reasoned-imagination text, tentative assertion candidates, verifier-queue
status, strategy-health telemetry, advice, and bounded surge state.

State/advice/tentative material can change search ordering but can never enter
a proof.  Only the ordinary Predator derivation followed by the unchanged
Metamath verifier can establish the theorem.
"""
from __future__ import annotations

import heapq
import importlib.util
import math
import os
import random
import threading
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "predator 8.001.py")
spec = importlib.util.spec_from_file_location("predator8_partner_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load Predator 8.001")
P8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P8)
P8.VERSION = "8.010-partner-pair"

NATIVE = ((1, 3), (2, 4))
PAIR_MAX = (2, 4)
FULL_MAX = (3, 4)


class PartnerChannel:
    """Direct pair workspace.  Nothing here is a proof object."""

    def __init__(self, names, say=print):
        self.names = tuple(names)
        self.say = say
        self.lock = threading.RLock()
        self.states = {}
        self.history = []
        self.messages = []
        self.active = {names[0]: NATIVE[0], names[1]: NATIVE[1]}
        self.native = dict(self.active)
        self.personality = {names[0]: "reflective", names[1]: "strategic"}
        self.best_open = {n: 10**9 for n in names}
        self.stale = {n: 0 for n in names}
        self.surge_mode = None
        self.surge_until = 0.0
        self.surge_events = []
        self.final_queue = []

    def partner(self, name):
        return self.names[1] if name == self.names[0] else self.names[0]

    def _maybe_end_surge(self):
        if self.surge_mode and time.monotonic() >= self.surge_until:
            old = self.surge_mode
            self.active = dict(self.native)
            self.surge_mode = None
            self.surge_events.append("EXIT:%s:native" % old)
            if self.say:
                self.say("      [PAIR] surge exit: native coordinates restored")

    def request_surge(self, mode, seconds=0.35):
        with self.lock:
            self._maybe_end_surge()
            if self.surge_mode is not None:
                return
            coord = PAIR_MAX if mode == "pair-max" else FULL_MAX
            self.surge_mode = mode
            self.surge_until = time.monotonic() + max(0.05, float(seconds))
            for n in self.names:
                self.active[n] = coord
            self.surge_events.append("ENTER:%s:%s" % (mode, coord))
            if self.say:
                self.say("      [PAIR] surge enter %s -> both %s; native personalities retained"
                         % (mode, coord))

    def publish(self, name, exp, open_goals, goal_text, candidate_labels,
                duplicate_hint=0.0):
        """Publish a state packet and derive cautious partner advice."""
        with self.lock:
            self._maybe_end_surge()
            if open_goals < self.best_open[name]:
                self.best_open[name] = open_goals
                self.stale[name] = 0
                health = "working"
                reason = "open-goal count reached a new personal best"
            else:
                self.stale[name] += 1
                health = "working" if self.stale[name] < 5 else "uncertain"
                reason = "no new open-goal best in %d reports" % self.stale[name]

            packet = {
                "sender": name,
                "native_coord": self.native[name],
                "active_coord": self.active[name],
                "personality": self.personality[name],
                "status": "searching",
                "expansions": exp,
                "open_goals": open_goals,
                "goal": goal_text,
                "reasoned_imagination":
                    "I am currently wondering if one of %s is the best next move."
                    % (", ".join(candidate_labels[:3]) or "the available assertions"),
                "tentative_bank": tuple(candidate_labels[:8]),
                "verifier_queue": tuple(self.final_queue[-2:]),
                "strategy": "%s@%s" % (self.personality[name], self.active[name]),
                "strategy_health": health,
                "why": reason + "; but do not believe this report as proof",
                "saturation": self.stale[name],
                "duplicate_hint": float(duplicate_hint),
                "request": "partner: compare these candidates with your current basin",
                "confidence": 0.72 if health == "working" else 0.45,
            }
            self.states[name] = packet
            self.history.append(packet)

            other = self.partner(name)
            op = self.states.get(other)
            if op:
                overlap = set(packet["tentative_bank"]) & set(op["tentative_bank"])
                if packet["strategy_health"] == "uncertain" and overlap:
                    msg = (name, other, "DIVERSIFY",
                           "avoid duplicated tentative labels: %s"
                           % ",".join(sorted(overlap)[:5]))
                else:
                    msg = (name, other, "COMPARE",
                           "consider my current candidates: %s"
                           % ",".join(packet["tentative_bank"][:4]))
                self.messages.append(msg)

                if (open_goals <= 2 and op["open_goals"] <= 2
                        and self.surge_mode is None):
                    self.request_surge("pair-max")

                if (self.stale[name] >= 8 and self.stale[other] >= 8
                        and overlap and self.surge_mode is None):
                    self.request_surge("full")

            if self.say:
                self.say("      [%s STATE] exp=%s open=%d native=%s active=%s "
                         "health=%s tentative=%s"
                         % (name, f"{exp:,}", open_goals, self.native[name],
                            self.active[name], health,
                            ",".join(candidate_labels[:4]) or "-"))

    def advice_bonus(self, recipient, label):
        """Advice may reorder search, never certify mathematics."""
        with self.lock:
            self._maybe_end_surge()
            other = self.partner(recipient)
            op = self.states.get(other)
            if not op:
                return 0.0
            c = self.active[recipient][1]
            if label not in op["tentative_bank"]:
                return 0.0
            if op["strategy_health"] == "working":
                return 0.025 * c
            return -0.025 * c

    def final_candidate(self, name):
        with self.lock:
            self.final_queue.append("%s -> Verifier V" % name)
            self.messages.append((name, "V", "VERIFY",
                                  "complete proof candidate submitted"))


def _scored_with_partner(goal, items, base_scores, profile, rng,
                         local_use, shared_use, channel, agent_name):
    ranked = P8._candidate_scores(
        goal, items, base_scores, profile, rng, local_use, shared_use)
    out = []
    for score, item in ranked:
        label = item[0]
        i, _c = channel.active[agent_name]
        novelty_capacity = 0.008 * i / math.sqrt(1.0 + local_use[label])
        advice = channel.advice_bonus(agent_name, label)
        out.append((score + novelty_capacity + advice, item))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def prove_partner(goal_tree, index, budget, max_depth, profile, seed,
                  channel, stop_event, shared_use, agent_name,
                  say=print, progress=1000, max_open=6):
    rng = random.Random(seed)
    local_use = defaultdict(int)
    start = P8.Node([(goal_tree, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    exp = tie = 0
    seen = set()
    report_every = max(100, int(os.environ.get("PREDATOR_PARTNER_REPORT", "250")))

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

        gi = P8.pick_goal(node.goals, node.sub)
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = P8.apply_sub(gt, node.sub)

        key = (node.depth, " ".join(gt.tokens()),
               tuple(sorted(" ".join(P8.apply_sub(g, node.sub).tokens())
                            for g, _, _ in rest)))
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        ranked_c = _scored_with_partner(
            gt, closers, [0.0] * len(closers), profile, rng,
            local_use, shared_use, channel, agent_name)
        ranked_o = _scored_with_partner(
            gt, openers, [0.0] * len(openers), profile, rng,
            local_use, shared_use, channel, agent_name)
        chosen = ranked_c + P8._counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng)
        candidate_labels = tuple(item[1][0] for item in chosen[:8])

        if exp == 1 or exp % report_every == 0:
            channel.publish(
                agent_name, exp, len(node.goals), " ".join(gt.tokens()),
                candidate_labels,
                duplicate_hint=(len(seen) / max(1.0, float(exp))))
        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open goals, active=%s"
                % (agent_name, f"{exp:,}", len(node.goals),
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
            fmap = {var: m.get(var, P8.fresh(tc)) for _, tc, var in f_hyps}
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

            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1
            guide = math.tanh(candidate_score / 2.0)
            edge_cost = (0.25 if not e_hyps else 1.0) - 0.20 * guide
            state_cost = 0.02 * len(newgoals + rest)
            heapq.heappush(
                frontier,
                (priority + edge_cost + state_cost, tie,
                 P8.Node(newgoals + rest, s2,
                         node.trail + ((slot, hix, step),),
                         node.depth + 1)))

    return None, exp


def prove_population_partner(goal_tree, index, budget, max_depth, agents=2,
                             creativity=0.55, seed=0, rank=None, say=print,
                             progress=1000, max_open=6, opener_cap=48):
    if agents != 2 and say:
        say("    partner engine uses exactly 2 P agents; --agents=%d ignored" % agents)

    profiles = P8.make_profiles(2, creativity, opener_cap)
    profiles[0].name = "P1-reflective-(1,3)"
    profiles[1].name = "P2-strategic-(2,4)"
    shares = P8.schedule_budgets(budget, profiles)
    names = [p.name for p in profiles]
    channel = PartnerChannel(names, say=say)
    stop = threading.Event()
    shared_use = defaultdict(int)
    results = [None, None]
    used = [0, 0]

    if say:
        say("    communicating P pair: native (1,3) + (2,4); "
            "pair-max (2,4)+(2,4); full surge (3,4)+(3,4)")
        say("    direct workspace: state + imagination + tentative bank + "
            "advice + verifier queue; none of these are proof")

    def worker(i):
        res, n = prove_partner(
            goal_tree, index, shares[i], max_depth, profiles[i],
            int(seed) + 1000003 * i, channel, stop, shared_use, names[i],
            say=say, progress=progress, max_open=max_open)
        results[i] = res
        used[i] = n
        if res is not None:
            stop.set()

    threads = [threading.Thread(target=worker, args=(i,),
                                name=names[i], daemon=True)
               for i in range(2)]
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
        say("    partner telemetry: %d state packets, %d advice messages, surges=%s"
            % (len(channel.history), len(channel.messages),
               channel.surge_events or "none"))
        say("    partner expansion accounting: %s / global cap %s"
            % (f"{sum(used):,}", f"{budget:,}"))
    return result, sum(used), winner


P8.prove_population = prove_population_partner


def main():
    return P8.main()


if __name__ == "__main__":
    main()
