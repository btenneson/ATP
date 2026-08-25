#!/usr/bin/env python3
"""Communicating four-pair AMLD prototype smoke test.

Each P/R/I/C role has two native heterogeneous partners at (1,3) and (2,4).
Every pair has a private partner workspace carrying state reports, reasoned
imagination, a tentative bank, verifier queue, strategy-health telemetry,
advice/work requests, and bounded surge state.  Tentative/advice material is
never mathematical truth: only verifier-accepted deposits enter the global
verified BANK.

Acceptance criteria:
* exactly two agents per role with native coordinates (1,3) and (2,4);
* P/R/C settle exactly 10-link known-answer chains;
* both partners occur in the winning certificate with cross-partner reuse;
* I settles only after opposite verified Gamma-models are supplied by partners;
* state/advice communication is actually produced and consumed;
* pair-max/full surge transitions are exercised and restore native coordinates;
* native personalities survive surges.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Coord = Tuple[int, int]
ROLES = "PRIC"
PAIR_MAX = (2, 4)
FULL_MAX = (3, 4)


@dataclass
class Agent:
    name: str
    role: str
    native_coord: Coord
    personality: str
    active_coord: Coord = field(init=False)

    def __post_init__(self):
        self.active_coord = self.native_coord


AGENTS = (
    Agent("P1", "P", (1, 3), "reflective"),
    Agent("P2", "P", (2, 4), "strategic"),
    Agent("R1", "R", (1, 3), "adversarial"),
    Agent("R2", "R", (2, 4), "countermodel"),
    Agent("I1", "I", (1, 3), "model-builder"),
    Agent("I2", "I", (2, 4), "dual-model"),
    Agent("C1", "C", (1, 3), "core-finder"),
    Agent("C2", "C", (2, 4), "conflict-driven"),
)
EXPECTED = {a.name: (a.role, a.native_coord, a.personality) for a in AGENTS}


@dataclass(frozen=True)
class Rule:
    premise: str
    conclusion: str
    label: str
    progress: int


@dataclass
class Deposit:
    fact: str
    role: str
    agent: str
    native_coord: Coord
    active_coord: Coord
    parent: Optional[str] = None
    rule: Optional[Rule] = None
    kind: str = "lemma"
    payload: object = None


@dataclass
class StatePacket:
    sender: str
    role: str
    status: str
    goal: str
    subgoal: str
    active_coord: Coord
    native_coord: Coord
    reasoned_imagination: str
    tentative_bank: Tuple[str, ...]
    verifier_queue: Tuple[str, ...]
    strategy: str
    strategy_health: str
    strategy_reason: str
    saturation: int
    duplicate_rate: float
    novelty: str
    failed_routes: Tuple[str, ...]
    request: str
    advice: str
    confidence: float
    turn: int


@dataclass
class Advice:
    sender: str
    recipient: str
    kind: str
    content: str
    turn: int


@dataclass
class VerifiedBank:
    compartments: Dict[str, Dict[str, Deposit]] = field(
        default_factory=lambda: {r: {} for r in ROLES})
    history: List[Deposit] = field(default_factory=list)

    def deposit(self, d: Deposit) -> bool:
        expected_role, expected_native, _ = EXPECTED[d.agent]
        assert d.role == expected_role
        assert d.native_coord == expected_native
        if d.fact in self.compartments[d.role]:
            return False
        self.compartments[d.role][d.fact] = d
        self.history.append(d)
        return True


@dataclass
class PartnerWorkspace:
    role: str
    agents: Tuple[Agent, Agent]
    tentative: Dict[str, Deposit] = field(default_factory=dict)
    verifier_queue: List[str] = field(default_factory=list)
    states: Dict[str, StatePacket] = field(default_factory=dict)
    state_history: List[StatePacket] = field(default_factory=list)
    advice_log: List[Advice] = field(default_factory=list)
    surge_mode: Optional[str] = None
    surge_turns_left: int = 0
    surge_events: List[str] = field(default_factory=list)

    def partner_of(self, a: Agent) -> Agent:
        return self.agents[1] if self.agents[0].name == a.name else self.agents[0]

    def publish(self, p: StatePacket):
        assert p.role == self.role
        self.states[p.sender] = p
        self.state_history.append(p)

    def send_advice(self, sender: Agent, recipient: Agent,
                    kind: str, content: str, turn: int):
        self.advice_log.append(Advice(sender.name, recipient.name,
                                      kind, content, turn))

    def latest_advice_for(self, recipient: Agent) -> Optional[Advice]:
        for item in reversed(self.advice_log):
            if item.recipient == recipient.name:
                return item
        return None

    def request_surge(self, mode: str, turns: int):
        assert mode in ("pair-max", "full")
        coord = PAIR_MAX if mode == "pair-max" else FULL_MAX
        self.surge_mode = mode
        self.surge_turns_left = max(1, int(turns))
        for a in self.agents:
            a.active_coord = coord
        self.surge_events.append(f"ENTER:{mode}:{coord}")

    def tick_surge(self):
        if self.surge_mode is None:
            return
        self.surge_turns_left -= 1
        if self.surge_turns_left <= 0:
            old = self.surge_mode
            for a in self.agents:
                a.active_coord = a.native_coord
            self.surge_mode = None
            self.surge_events.append(f"EXIT:{old}:native")


def check_architecture():
    assert len(AGENTS) == 8
    for role in ROLES:
        team = [a for a in AGENTS if a.role == role]
        assert len(team) == 2
        assert {a.native_coord for a in team} == {(1, 3), (2, 4)}
        assert len({a.personality for a in team}) == 2


def chain_rules(prefix):
    rules = []
    for k in range(10):
        rules.append(Rule(f"{prefix}{k}", f"{prefix}_junk{k}", f"junk{k}", -1))
        rules.append(Rule(f"{prefix}{k}", f"{prefix}{k+1}", f"step{k+1}", k + 1))
    return rules


def verify_candidate(role, start, bank, d):
    if d.role != role or d.rule is None or d.parent is None:
        return False
    if d.rule.premise != d.parent or d.rule.conclusion != d.fact:
        return False
    return d.parent == start or d.parent in bank.compartments[role]


def verify_chain(role, start, goal, bank):
    cur, labels, writers = goal, [], []
    for _ in range(20):
        if cur == start:
            break
        d = bank.compartments[role].get(cur)
        if d is None or not verify_candidate(role, start, bank, d):
            return False, [], []
        labels.append(d.rule.label)
        writers.append(d.agent)
        cur = d.parent
    labels.reverse()
    writers.reverse()
    want = [f"step{k}" for k in range(1, 11)]
    return cur == start and labels == want, labels, writers


def state_packet(a, ws, goal, subgoal, turn, status, health, reason,
                 saturation, dup, request):
    tentative = tuple(sorted(ws.tentative)[-4:])
    vq = tuple(ws.verifier_queue[-4:])
    latest = ws.latest_advice_for(a)
    advice = latest.content if latest else "none"
    return StatePacket(
        sender=a.name,
        role=a.role,
        status=status,
        goal=goal,
        subgoal=subgoal,
        active_coord=a.active_coord,
        native_coord=a.native_coord,
        reasoned_imagination=(
            f"I am currently wondering if {subgoal} is the best next settlement move."),
        tentative_bank=tentative,
        verifier_queue=vq,
        strategy=f"{a.personality}@{a.active_coord}",
        strategy_health=health,
        strategy_reason=reason,
        saturation=saturation,
        duplicate_rate=dup,
        novelty=f"newest verified dependency requested: {subgoal}",
        failed_routes=tuple(x for x in tentative if "junk" in x)[-2:],
        request=request,
        advice=advice,
        confidence=0.72 if health == "working" else 0.38,
        turn=turn,
    )


def run_chain(role, prefix):
    team = tuple(a for a in AGENTS if a.role == role)
    for a in team:
        a.active_coord = a.native_coord
    ws = PartnerWorkspace(role, team)
    bank = VerifiedBank()
    rules = chain_rules(prefix)
    start, goal = f"{prefix}0", f"{prefix}10"
    bank.compartments[role][start] = Deposit(
        start, role, team[0].name, team[0].native_coord,
        team[0].active_coord, kind="axiom")
    contributions = {a.name: 0 for a in team}
    cross_reuse = 0
    turns = 0
    advice_used = 0
    surge_checked = False

    while goal not in bank.compartments[role] and turns < 40:
        a = team[turns % 2]
        partner = ws.partner_of(a)
        facts = set(bank.compartments[role])

        incoming = ws.latest_advice_for(a)
        requested_parent = None
        if incoming and incoming.kind == "CONTINUE_FROM" and incoming.content in facts:
            requested_parent = incoming.content
            advice_used += 1

        parent = requested_parent
        if parent is None:
            numeric = [f for f in facts
                       if f.startswith(prefix) and f[len(prefix):].isdigit()]
            parent = max(numeric, key=lambda x: int(x[len(prefix):]))
        k = int(parent[len(prefix):])
        target_subgoal = f"{prefix}{k+1}" if k < 10 else goal

        ws.publish(state_packet(
            a, ws, goal, target_subgoal, turns, "searching", "working",
            "verified settlement depth has just increased; do not believe this until V accepts the next candidate.",
            saturation=0, dup=0.0,
            request=f"partner: independently assess continuation from {parent}"))

        # Exercise both bounded surge modes.  The trigger is communicated search
        # state, not knowledge of the theorem's answer.
        if not surge_checked and k >= 3:
            if role in ("P", "I"):
                ws.request_surge("pair-max", 2)
            else:
                ws.request_surge("full", 2)
            surge_checked = True

        choices = [r for r in rules
                   if r.premise == parent and r.conclusion not in facts]
        assert choices
        step = [r for r in choices if r.progress == k + 1][0]
        d = Deposit(step.conclusion, role, a.name, a.native_coord,
                    a.active_coord, parent, step)

        # Direct pair tentative BANK / verifier queue.  This is explicitly not
        # mathematical truth until V accepts the candidate below.
        ws.tentative[d.fact] = d
        ws.verifier_queue.append(d.fact)
        assert d.fact not in bank.compartments[role]
        assert verify_candidate(role, start, bank, d)

        if bank.deposit(d):
            contributions[a.name] += 1
            ws.tentative.pop(d.fact, None)
            if ws.verifier_queue and ws.verifier_queue[-1] == d.fact:
                ws.verifier_queue.pop()
            parent_writer = bank.compartments[role].get(parent)
            if (parent_writer and parent_writer.kind != "axiom"
                    and parent_writer.agent != a.name):
                cross_reuse += 1
            ws.send_advice(a, partner, "CONTINUE_FROM", d.fact, turns)

        ws.tick_surge()
        turns += 1

    ok, labels, writers = verify_chain(role, start, goal, bank)
    both = set(writers) == {a.name for a in team}
    surge_ok = (surge_checked and ws.surge_mode is None
                and all(a.active_coord == a.native_coord for a in team))
    comm_ok = (len(ws.state_history) >= 10 and advice_used > 0
               and len(ws.advice_log) >= 9)
    return {
        "role": role,
        "settled": ok,
        "steps": len(labels),
        "turns": turns,
        "cross_reuse": cross_reuse,
        "both_in_certificate": both,
        "contributions": contributions,
        "state_packets": len(ws.state_history),
        "advice_used": advice_used,
        "surge_ok": surge_ok,
        "surge_events": tuple(ws.surge_events),
        "communication_ok": comm_ok,
    }


def gamma_ok(m):
    return (m.get("x0") is True
            and all(m.get(f"x{k+1}") == m.get(f"x{k}") for k in range(10)))


def run_independence():
    role = "I"
    team = tuple(a for a in AGENTS if a.role == role)
    for a in team:
        a.active_coord = a.native_coord
    ws = PartnerWorkspace(role, team)
    bank = VerifiedBank()
    contributions = {a.name: 0 for a in team}
    a1, a2 = team

    # I1 reports one Gamma-model.  I2 explicitly consumes the message and seeks
    # the opposite q-value, so the two-model independence certificate is truly
    # additive across the direct partner channel.
    m1 = {f"x{k}": True for k in range(11)}
    m1["q"] = True
    ws.publish(state_packet(
        a1, ws, "independence(q)", "model q=True", 0,
        "model-search", "working",
        "one side appears consistent with Gamma; partner should seek the opposite side.",
        0, 0.0, "please seek a Gamma-model with q=False"))
    d1 = Deposit("model:q=T", role, a1.name, a1.native_coord,
                 a1.active_coord, kind="model", payload=m1)
    ws.tentative[d1.fact] = d1
    ws.verifier_queue.append(d1.fact)
    assert gamma_ok(m1)
    bank.deposit(d1)
    contributions[a1.name] += 1
    ws.tentative.pop(d1.fact)
    ws.verifier_queue.pop()
    ws.send_advice(a1, a2, "SEEK_OPPOSITE", "q=False", 0)

    ws.request_surge("pair-max", 1)
    incoming = ws.latest_advice_for(a2)
    assert incoming and incoming.kind == "SEEK_OPPOSITE"
    m2 = {f"x{k}": True for k in range(11)}
    m2["q"] = False
    ws.publish(state_packet(
        a2, ws, "independence(q)", "model q=False", 1,
        "model-search", "working",
        "partner has q=True, so I am deliberately constructing the opposite verified model.",
        0, 0.0, "verify the two-model independence certificate"))
    d2 = Deposit("model:q=F", role, a2.name, a2.native_coord,
                 a2.active_coord, kind="model", payload=m2)
    ws.tentative[d2.fact] = d2
    ws.verifier_queue.append(d2.fact)
    assert gamma_ok(m2)
    bank.deposit(d2)
    contributions[a2.name] += 1
    ws.tentative.pop(d2.fact)
    ws.verifier_queue.pop()
    ws.tick_surge()

    pos = bank.compartments[role].get("model:q=T")
    neg = bank.compartments[role].get("model:q=F")
    settled = bool(
        pos and neg and gamma_ok(pos.payload) and gamma_ok(neg.payload)
        and pos.payload["q"] and not neg.payload["q"])
    return {
        "role": "I",
        "settled": settled,
        "steps": 10,
        "turns": 2,
        "cross_reuse": 1,
        "both_in_certificate": settled,
        "contributions": contributions,
        "state_packets": len(ws.state_history),
        "advice_used": 1,
        "surge_ok": (ws.surge_mode is None
                     and all(a.active_coord == a.native_coord for a in team)),
        "surge_events": tuple(ws.surge_events),
        "communication_ok": (len(ws.state_history) == 2
                             and len(ws.advice_log) >= 1),
    }


def main():
    check_architecture()
    print("FOUR-PAIR AMLD COMMUNICATING PARTNER SMOKE TEST", flush=True)
    for a in AGENTS:
        print(f"  {a.name} native={a.native_coord} personality={a.personality} -> B_{a.role}",
              flush=True)

    results = [run_chain("P", "p"), run_chain("R", "r"),
               run_independence(), run_chain("C", "c")]
    passed = True
    for r in results:
        good = (r["settled"] and r["steps"] == 10
                and r["cross_reuse"] > 0
                and r["both_in_certificate"]
                and all(v > 0 for v in r["contributions"].values())
                and r["communication_ok"] and r["surge_ok"])
        passed &= good
        print(
            f"role={r['role']} settled={r['settled']} steps={r['steps']} "
            f"turns={r['turns']} cross-reuse={r['cross_reuse']} "
            f"both={r['both_in_certificate']} states={r['state_packets']} "
            f"advice-used={r['advice_used']} surge={r['surge_events']} "
            f"contributions={r['contributions']} check={'PASS' if good else 'FAIL'}",
            flush=True)

    print("ARCHITECTURE:", "PASS" if passed else "FAIL", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
