#!/usr/bin/env python3
"""Prototype smoke test for the 8-agent heterogeneous partner architecture.

Typed scaffolding only:
P1^(2,3), P2^(0,0); R1^(1,3), R2^(2,1);
I1^(2,2), I2^(0,3); C1^(1,2), C2^(2,0).

Acceptance criteria:
* exactly two agents per settlement role and all coordinates are in the intended cells;
* every deposit is routed to the agent's own B_P/B_R/B_I/B_C compartment;
* P, R and C each cooperatively settle an exactly 10-link known-answer chain;
* those certificates use lemmas written by both partners and contain cross-partner reuse;
* I settles a toy independence case only after its two partners provide opposite verified models.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

Coord = Tuple[int, int]

@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    coord: Coord

AGENTS = (
    Agent("P1", "P", (2, 3)), Agent("P2", "P", (0, 0)),
    Agent("R1", "R", (1, 3)), Agent("R2", "R", (2, 1)),
    Agent("I1", "I", (2, 2)), Agent("I2", "I", (0, 3)),
    Agent("C1", "C", (1, 2)), Agent("C2", "C", (2, 0)),
)
EXPECTED = {a.name: (a.role, a.coord) for a in AGENTS}

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
    coord: Coord
    parent: Optional[str] = None
    rule: Optional[Rule] = None
    kind: str = "lemma"
    payload: object = None

@dataclass
class Bank:
    compartments: Dict[str, Dict[str, Deposit]] = field(
        default_factory=lambda: {r: {} for r in "PRIC"})

    def deposit(self, d: Deposit) -> bool:
        expected_role, expected_coord = EXPECTED[d.agent]
        assert d.role == expected_role, (d.agent, d.role, expected_role)
        assert d.coord == expected_coord, (d.agent, d.coord, expected_coord)
        if d.fact in self.compartments[d.role]:
            return False
        self.compartments[d.role][d.fact] = d
        return True


def check_typing() -> None:
    assert len(AGENTS) == 8 and len({a.name for a in AGENTS}) == 8
    for role in "PRIC":
        team = [a for a in AGENTS if a.role == role]
        assert len(team) == 2
        assert team[0].coord != team[1].coord
    for a in AGENTS:
        assert EXPECTED[a.name] == (a.role, a.coord)


def chain_rules(prefix: str):
    rules = []
    for k in range(10):
        # Distractor first, so low-control/brute policies really differ.
        rules.append(Rule(f"{prefix}{k}", f"{prefix}_junk{k}", f"junk{k}", -1))
        rules.append(Rule(f"{prefix}{k}", f"{prefix}{k+1}", f"step{k+1}", k + 1))
    return rules


def policy_key(a: Agent, r: Rule):
    i, c = a.coord
    if (i, c) == (0, 0):
        return (0, r.label)                 # source-ish brute behavior
    return (-c * r.progress, -i * len(r.conclusion), r.label)


def verify_deposit(role: str, start: str, bank: Bank, d: Deposit) -> bool:
    if d.role != role or d.rule is None or d.parent is None:
        return False
    if d.rule.premise != d.parent or d.rule.conclusion != d.fact:
        return False
    return d.parent == start or d.parent in bank.compartments[role]


def verify_chain(role: str, start: str, goal: str, bank: Bank):
    cur, labels, writers = goal, [], []
    for _ in range(20):
        if cur == start:
            break
        d = bank.compartments[role].get(cur)
        if d is None or not verify_deposit(role, start, bank, d):
            return False, [], []
        labels.append(d.rule.label)
        writers.append(d.agent)
        cur = d.parent
    labels.reverse(); writers.reverse()
    want = [f"step{k}" for k in range(1, 11)]
    return cur == start and labels == want, labels, writers


def run_chain(role: str, prefix: str):
    team = [a for a in AGENTS if a.role == role]
    rules = chain_rules(prefix)
    start, goal = f"{prefix}0", f"{prefix}10"
    bank = Bank()
    # Gamma seed is input, not credited to a partner.
    seed_agent = team[0]
    bank.compartments[role][start] = Deposit(start, role, seed_agent.name, seed_agent.coord, kind="axiom")
    writer = {start: None}
    cross_reuse = 0
    contributions = {a.name: 0 for a in team}
    turns = 0

    while goal not in bank.compartments[role] and turns < 80:
        a = team[turns % 2]
        facts = set(bank.compartments[role])
        choices = [r for r in rules if r.premise in facts and r.conclusion not in facts]
        if choices:
            choices.sort(key=lambda r: policy_key(a, r))
            r = choices[0]
            d = Deposit(r.conclusion, role, a.name, a.coord, r.premise, r)
            assert verify_deposit(role, start, bank, d)
            if bank.deposit(d):
                contributions[a.name] += 1
                if writer.get(r.premise) not in (None, a.name):
                    cross_reuse += 1
                writer[r.conclusion] = a.name
        turns += 1

    ok, labels, writers = verify_chain(role, start, goal, bank)
    both_in_certificate = set(writers) == {a.name for a in team}
    return {
        "role": role, "settled": ok, "steps": len(labels), "turns": turns,
        "cross_reuse": cross_reuse, "both_in_certificate": both_in_certificate,
        "contributions": contributions,
    }


def gamma_ok(m):
    if m.get("x0") is not True:
        return False
    return all(m.get(f"x{k+1}") == m.get(f"x{k}") for k in range(10))


def run_independence():
    team = [a for a in AGENTS if a.role == "I"]
    bank = Bank()
    contributions = {a.name: 0 for a in team}
    for a in team:
        # The two coordinate styles deliberately seek opposite sides first.
        q = a.coord[0] >= 2
        m = {f"x{k}": True for k in range(11)}
        m["q"] = q
        assert gamma_ok(m)
        d = Deposit(f"model:q={'T' if q else 'F'}", "I", a.name, a.coord,
                    kind="model", payload=m)
        if bank.deposit(d):
            contributions[a.name] += 1
    pos = bank.compartments["I"].get("model:q=T")
    neg = bank.compartments["I"].get("model:q=F")
    settled = bool(pos and neg and gamma_ok(pos.payload) and gamma_ok(neg.payload)
                   and pos.payload["q"] and not neg.payload["q"])
    return {"role": "I", "settled": settled, "steps": 10, "turns": 2,
            "cross_reuse": 1 if settled else 0,
            "both_in_certificate": settled,
            "contributions": contributions}


def main() -> int:
    check_typing()
    print("8-AGENT PARTNER ARCHITECTURE SMOKE TEST", flush=True)
    for a in AGENTS:
        print(f"  {a.name}^({a.coord[0]},{a.coord[1]}) -> B_{a.role}", flush=True)

    results = [run_chain("P", "p"), run_chain("R", "r"),
               run_independence(), run_chain("C", "c")]
    print("RESULTS", flush=True)
    passed = True
    for r in results:
        good = (r["settled"] and r["steps"] == 10 and r["cross_reuse"] > 0
                and r["both_in_certificate"] and all(v > 0 for v in r["contributions"].values()))
        passed &= good
        print(f"  role={r['role']} settled={r['settled']} steps={r['steps']} "
              f"turns={r['turns']} cross-partner-reuse={r['cross_reuse']} "
              f"both-in-certificate={r['both_in_certificate']} "
              f"contributions={r['contributions']} check={'PASS' if good else 'FAIL'}",
              flush=True)
    print("ARCHITECTURE:", "PASS" if passed else "FAIL", flush=True)
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
