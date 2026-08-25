#!/usr/bin/env python3
"""Eight-agent heterogeneous partner architecture smoke test.

Prototype-only typing scaffold:
  P1^(2,3), P2^(0,0)
  R1^(1,3), R2^(2,1)
  I1^(2,2), I2^(0,3)
  C1^(1,2), C2^(2,0)

The goal is not mathematical difficulty.  It is to verify that:
* all eight agents are instantiated in the intended role/coordinate cells;
* deposits go to the correct role BANK compartment;
* partners can consume one another's verified deposits;
* P, R, and C can cooperatively complete short (10-link) derivations;
* I can cooperatively settle a finite-model independence toy by depositing
  opposite verified models;
* no wrong-role settlement is accepted.

This is deliberately a prototype scaffold, not the final untyped agent model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


Coord = Tuple[int, int]


@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    coord: Coord


AGENTS: Tuple[Agent, ...] = (
    Agent("P1", "P", (2, 3)),
    Agent("P2", "P", (0, 0)),
    Agent("R1", "R", (1, 3)),
    Agent("R2", "R", (2, 1)),
    Agent("I1", "I", (2, 2)),
    Agent("I2", "I", (0, 3)),
    Agent("C1", "C", (1, 2)),
    Agent("C2", "C", (2, 0)),
)

EXPECTED = {
    "P1": ("P", (2, 3)), "P2": ("P", (0, 0)),
    "R1": ("R", (1, 3)), "R2": ("R", (2, 1)),
    "I1": ("I", (2, 2)), "I2": ("I", (0, 3)),
    "C1": ("C", (1, 2)), "C2": ("C", (2, 0)),
}


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
    rule: Optional[Rule]
    parent: Optional[str]
    kind: str = "lemma"
    payload: object = None


@dataclass
class Bank:
    compartments: Dict[str, Dict[str, Deposit]] = field(
        default_factory=lambda: {r: {} for r in "PRIC"}
    )
    history: List[Deposit] = field(default_factory=list)

    def deposit(self, d: Deposit) -> bool:
        if d.role not in self.compartments:
            raise AssertionError(f"unknown role {d.role}")
        actual = EXPECT[d.agent][0]
        if actual != d.role:
            raise AssertionError(
                f"misrouted deposit: {d.agent} is {actual}, attempted B_{d.role}")
        if d.fact in self.compartments[d.role]:
            return False
        self.compartments[d.role][d.fact] = d
        self.history.append(d)
        return True

    def facts(self, role: str) -> set[str]:
        return set(self.compartments[role])


@dataclass(frozen=True)
class ChainCase:
    name: str
    role: str
    start: str
    goal: str
    rules: Tuple[Rule, ...]


def make_chain_case(name: str, role: str, prefix: str) -> ChainCase:
    # Ten required links, plus distractors.  The ordering deliberately gives the
    # (0,0)-like brute policy some irrelevant work while controller-rich agents
    # prefer greater progress.
    rules: List[Rule] = []
    for k in range(10):
        rules.append(Rule(f"{prefix}{k}", f"{prefix}_junk{k}", f"junk{k}", -1))
        rules.append(Rule(f"{prefix}{k}", f"{prefix}{k+1}", f"step{k+1}", k + 1))
    return ChainCase(name, role, f"{prefix}0", f"{prefix}10", tuple(rules))


CHAIN_CASES = (
    make_chain_case("P-ten-link-theorem", "P", "p"),
    make_chain_case("R-ten-link-refutation", "R", "r"),
    make_chain_case("C-ten-link-contradiction", "C", "c"),
)


def policy_key(agent: Agent, rule: Rule) -> tuple:
    i, c = agent.coord
    # Prototype cognition mapping.  (0,0) is intentionally source-order/brute.
    # Higher controller rank prefers apparent settlement progress.  Reflection
    # rank is a deterministic secondary novelty preference.
    if (i, c) == (0, 0):
        return (0, rule.label)
    return (-c * rule.progress, -i * len(rule.conclusion), rule.label)


def verify_chain_deposit(case: ChainCase, bank: Bank, d: Deposit) -> bool:
    if d.role != case.role or d.rule is None or d.parent is None:
        return False
    if d.rule.premise != d.parent or d.rule.conclusion != d.fact:
        return False
    if d.parent == case.start:
        return True
    return d.parent in bank.compartments[case.role]


def verify_chain_certificate(case: ChainCase, bank: Bank) -> Tuple[bool, int, List[str]]:
    if case.goal not in bank.compartments[case.role]:
        return False, 0, []
    cur = case.goal
    labels: List[str] = []
    guard = 0
    while cur != case.start:
        guard += 1
        if guard > 100:
            return False, 0, []
        d = bank.compartments[case.role].get(cur)
        if d is None or d.rule is None or d.parent is None:
            return False, 0, []
        if not verify_chain_deposit(case, bank, d):
            return False, 0, []
        labels.append(d.rule.label)
        cur = d.parent
    labels.reverse()
    required = [f"step{k}" for k in range(1, 11)]
    return labels == required, len(labels), labels


def run_chain_case(case: ChainCase, max_turns: int = 80) -> dict:
    bank = Bank()
    team = [a for a in AGENTS if a.role == case.role]
    # Seed axiom/premise is trusted Gamma input, not credited to either partner.
    bank.compartments[case.role][case.start] = Deposit(
        case.start, case.role, "P1" if case.role == "P" else
        "R1" if case.role == "R" else "C1",
        EXPECT["P1" if case.role == "P" else "R1" if case.role == "R" else "C1"][1],
        None, None, kind="axiom")

    turns = 0
    partner_reuse = 0
    contributions = {a.name: 0 for a in team}
    last_writer: Dict[str, Optional[str]] = {case.start: None}

    while turns < max_turns and case.goal not in bank.facts(case.role):
        agent = team[turns % len(team)]
        facts = bank.facts(case.role)
        candidates = [r for r in case.rules if r.premise in facts and r.conclusion not in facts]
        if candidates:
            candidates.sort(key=lambda r: policy_key(agent, r))
            rule = candidates[0]
            parent_writer = last_writer.get(rule.premise)
            d = Deposit(rule.conclusion, case.role, agent.name, agent.coord,
                        rule, rule.premise)
            if not verify_chain_deposit(case, bank, d):
                raise AssertionError(f"verifier rejected legal candidate {d}")
            if bank.deposit(d):
                contributions[agent.name] += 1
                last_writer[rule.conclusion] = agent.name
                if parent_writer is not None and parent_writer != agent.name:
                    partner_reuse += 1
        turns += 1

    ok, proof_steps, labels = verify_chain_certificate(case, bank)
    wrong_role_claims = [
        d for d in bank.history if d.fact == case.goal and d.role != case.role
    ]
    return {
        "case": case.name,
        "expected_role": case.role,
        "settled": ok and not wrong_role_claims,
        "proof_steps": proof_steps,
        "turns": turns,
        "partner_reuse": partner_reuse,
        "contributions": contributions,
        "proof_labels": labels,
        "bank_sizes": {r: len(bank.compartments[r]) for r in "PRIC"},
    }


# Independence toy.  Gamma fixes a 10-link Boolean chain x0=...=x10=True but
# leaves q unconstrained.  Independence requires two verified Gamma-models, one
# with q=True and one with q=False.  The I partners deliberately search opposite
# q polarities first, so the settlement certificate is genuinely additive.

def gamma_ok(model: Dict[str, bool]) -> bool:
    if model.get("x0") is not True:
        return False
    for k in range(10):
        if model.get(f"x{k+1}") != model.get(f"x{k}"):
            return False
    return True


def make_i_model(q: bool) -> Dict[str, bool]:
    m = {f"x{k}": True for k in range(11)}
    m["q"] = q
    return m


def run_independence_case() -> dict:
    bank = Bank()
    team = [a for a in AGENTS if a.role == "I"]
    contributions = {a.name: 0 for a in team}

    for agent in team:
        # Different coordinate-conditioned search orientation.
        q = True if agent.coord[0] >= 2 else False
        model = make_i_model(q)
        if not gamma_ok(model):
            raise AssertionError("bad model generator")
        fact = f"model:q={'T' if q else 'F'}"
        d = Deposit(fact, "I", agent.name, agent.coord, None, None,
                    kind="model", payload=model)
        if bank.deposit(d):
            contributions[agent.name] += 1

    pos = bank.compartments["I"].get("model:q=T")
    neg = bank.compartments["I"].get("model:q=F")
    settled = bool(
        pos and neg
        and gamma_ok(pos.payload) and gamma_ok(neg.payload)
        and pos.payload["q"] is True and neg.payload["q"] is False
    )
    return {
        "case": "I-two-model-independence",
        "expected_role": "I",
        "settled": settled,
        "proof_steps": 10,  # ten Gamma chain equalities checked in each model
        "turns": 2,
        "partner_reuse": 1 if settled else 0,
        "contributions": contributions,
        "bank_sizes": {r: len(bank.compartments[r]) for r in "PRIC"},
    }


def check_typing() -> None:
    assert len(AGENTS) == 8
    assert len({a.name for a in AGENTS}) == 8
    for a in AGENTS:
        assert EXPECT[a.name] == (a.role, a.coord)
    for role in "PRIC":
        assert len([a for a in AGENTS if a.role == role]) == 2


def main() -> int:
    check_typing()
    print("8-AGENT PARTNER ARCHITECTURE SMOKE TEST")
    print("Prototype typing:")
    for a in AGENTS:
        print(f"  {a.name}^({a.coord[0]},{a.coord[1]}) -> B_{a.role}")

    results = [run_chain_case(c) for c in CHAIN_CASES]
    results.append(run_independence_case())

    print("\nRESULTS")
    all_ok = True
    for r in results:
        all_ok &= r["settled"]
        print(
            f"  {r['case']}: settled={r['settled']} role={r['expected_role']} "
            f"steps={r['proof_steps']} turns={r['turns']} "
            f"partner-reuse={r['partner_reuse']} contributions={r['contributions']} "
            f"banks={r['bank_sizes']}"
        )

    # Architecture acceptance criteria: all four settlement kinds succeed,
    # every chain certificate is exactly ten required links, and each chain has
    # at least one cross-partner dependency through the shared role bank.
    chain_ok = all(r["proof_steps"] == 10 and r["partner_reuse"] > 0
                   for r in results[:3])
    i_ok = results[3]["settled"] and all(v > 0 for v in results[3]["contributions"].values())
    passed = all_ok and chain_ok and i_ok
    print("\nARCHITECTURE:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
