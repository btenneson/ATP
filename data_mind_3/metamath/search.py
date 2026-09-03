from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import itertools
import time
from typing import Callable, Iterable

from .matcher import apply_substitution, match_statement
from .parser import Assertion, Database, Hypothesis


@dataclass(frozen=True)
class Goal:
    gid: int
    statement: tuple[str, ...]


@dataclass(frozen=True)
class Derivation:
    label: str
    children: tuple[int, ...]


@dataclass
class SearchState:
    open_goals: tuple[Goal, ...]
    derivations: dict[int, Derivation]
    next_gid: int
    depth: int = 0
    score: float = 0.0
    last_action: str = "root"


@dataclass(frozen=True)
class SearchConfig:
    max_expansions: int = 20_000
    max_depth: int = 24
    max_open_goals: int = 24
    candidate_cap: int = 64
    match_cap_per_candidate: int = 8
    max_sequence_len: int = 64
    timeout_s: float = 1800.0
    max_frontier: int = 200_000


@dataclass
class SearchResult:
    status: str
    expansions: int
    generated_children: int
    proof_labels: tuple[str, ...] = ()
    elapsed_s: float = 0.0
    reason: str = ""
    historian: list[dict] = field(default_factory=list)
    verification: dict | None = None


def _fixed_skeleton(a: Assertion) -> tuple[str, ...]:
    return tuple(t for t in a.statement if t not in a.mandatory_variables)


def _is_subsequence(needle: tuple[str, ...], haystack: tuple[str, ...]) -> bool:
    if not needle:
        return True
    it = iter(haystack)
    return all(any(x == n for x in it) for n in needle)


class StructuralLibrarian:
    """Retrieve only structurally possible prefix assertions, then rank them."""

    def __init__(self, assertions: Iterable[Assertion]):
        self.assertions = tuple(assertions)
        self._cache: dict[tuple[tuple[str, ...], int], tuple[Assertion, ...]] = {}
        self.by_type: dict[str, list[Assertion]] = {}
        for a in self.assertions:
            if a.statement:
                self.by_type.setdefault(a.statement[0], []).append(a)

    @staticmethod
    def _score(a: Assertion, goal: tuple[str, ...]) -> float:
        fixed = set(_fixed_skeleton(a)[1:])
        gset = set(goal[1:])
        overlap = len(fixed & gset)
        len_bonus = 3.0 / (1.0 + abs(len(a.statement) - len(goal)))
        hyp_penalty = 0.10 * len(a.mandatory_hypotheses)
        return 2.5 * overlap + len_bonus - hyp_penalty

    def shelf(self, goal: tuple[str, ...], cap: int) -> tuple[Assertion, ...]:
        key = (goal, cap)
        if key in self._cache:
            return self._cache[key]
        pool = self.by_type.get(goal[0], ()) if goal else ()
        filtered = [a for a in pool if _is_subsequence(_fixed_skeleton(a), goal)]
        ranked = sorted(filtered, key=lambda a: (-self._score(a, goal), a.order, a.label))
        value = tuple(ranked[:cap])
        self._cache[key] = value
        return value


class SyntaxOracle:
    """Prefix-derived well-formedness filter; not a mathematical verifier."""

    def __init__(self, db: Database, target: Assertion, legal_assertions: tuple[Assertion, ...]):
        self.db = db
        self.assumptions = {h.statement for h in target.mandatory_hypotheses if h.kind == "$f"}
        syntax = [a for a in legal_assertions if a.statement and a.statement[0] != "|-"]
        self.librarian = StructuralLibrarian(syntax)
        self.memo: dict[tuple[str, ...], bool] = {}
        self.visiting: set[tuple[str, ...]] = set()

    def valid(self, statement: tuple[str, ...], depth: int = 0) -> bool:
        if statement in self.assumptions:
            return True
        if statement in self.memo:
            return self.memo[statement]
        if not statement or statement[0] == "|-" or depth > 16 or statement in self.visiting:
            return False
        self.visiting.add(statement)
        try:
            for cand in self.librarian.shelf(statement, 256):
                for match in match_statement(
                    cand, statement, self.db.variables, max_matches=8, max_sequence_len=64
                ):
                    subst = match.as_dict()
                    if any(v not in subst for v in cand.mandatory_variables):
                        continue
                    children = [
                        apply_substitution(h.statement, subst, self.db.variables)
                        for h in cand.mandatory_hypotheses
                    ]
                    if all(self.valid(c, depth + 1) for c in children):
                        self.memo[statement] = True
                        return True
            self.memo[statement] = False
            return False
        finally:
            self.visiting.discard(statement)


class PartialCredit:
    @staticmethod
    def value(state: SearchState) -> float:
        if not state.open_goals:
            return 1.0
        mass = sum(len(g.statement) for g in state.open_goals)
        logic_goals = sum(1 for g in state.open_goals if g.statement and g.statement[0] == "|-")
        return 1.0 / (1.0 + 1.25 * logic_goals + 0.6 * len(state.open_goals) + 0.015 * mass)


class Scout:
    @staticmethod
    def successor_score(parent: SearchState, child: SearchState) -> float:
        pc = PartialCredit.value(child)
        return 10.0 * pc - 0.02 * child.depth - 0.006 * len(child.open_goals)


class Sentinel:
    def __init__(self, config: SearchConfig):
        self.config = config

    def allow(self, expansions: int, frontier: int, elapsed: float) -> tuple[bool, str]:
        if expansions >= self.config.max_expansions:
            return False, "expansion_budget"
        if frontier > self.config.max_frontier:
            return False, "frontier_budget"
        if elapsed >= self.config.timeout_s:
            return False, "timeout"
        return True, "GREEN"


def _instantiate_hypotheses(
    assertion: Assertion,
    subst: dict[str, tuple[str, ...]],
    all_variables: set[str],
) -> tuple[tuple[Hypothesis, tuple[str, ...]], ...] | None:
    if any(v not in subst for v in assertion.mandatory_variables):
        return None
    return tuple(
        (h, apply_substitution(h.statement, subst, all_variables))
        for h in assertion.mandatory_hypotheses
    )


def _dv_ok(assertion: Assertion, subst: dict[str, tuple[str, ...]], target: Assertion, all_variables: set[str]) -> bool:
    target_dv = target.disjoint_pairs
    for x, y in assertion.disjoint_pairs:
        sx = {t for t in subst.get(x, ()) if t in all_variables}
        sy = {t for t in subst.get(y, ()) if t in all_variables}
        if sx & sy:
            return False
        for a in sx:
            for b in sy:
                if a == b or tuple(sorted((a, b))) not in target_dv:
                    return False
    return True


def _linearize(root_gid: int, derivations: dict[int, Derivation]) -> tuple[str, ...]:
    out: list[str] = []
    visiting: set[int] = set()

    def walk(gid: int) -> None:
        if gid in visiting:
            raise RuntimeError("cycle in derivation")
        d = derivations[gid]
        visiting.add(gid)
        for c in d.children:
            walk(c)
        out.append(d.label)
        visiting.remove(gid)

    walk(root_gid)
    return tuple(out)


def search_target(
    db: Database,
    target_label: str,
    config: SearchConfig,
    verify_candidate: Callable[[tuple[str, ...]], tuple[bool, dict]] | None = None,
) -> SearchResult:
    target = db.target(target_label)
    legal_assertions = db.assertions_before(target)
    librarian = StructuralLibrarian(legal_assertions)
    syntax_oracle = SyntaxOracle(db, target, legal_assertions)
    sentinel = Sentinel(config)
    target_hyp_by_stmt = {h.statement: h.label for h in target.mandatory_hypotheses}

    initial = SearchState((Goal(0, target.statement),), {}, 1)
    counter = itertools.count()
    frontier: list[tuple[float, int, SearchState]] = [(0.0, next(counter), initial)]
    expansions = generated = 0
    start = time.monotonic()
    historian: list[dict] = []
    best_seen: dict[tuple[tuple[str, ...], ...], int] = {}

    while frontier:
        elapsed = time.monotonic() - start
        allowed, sstate = sentinel.allow(expansions, len(frontier), elapsed)
        if not allowed:
            historian.append({"actor": "Sentinel", "action": "stop", "reason": sstate,
                              "expansions": expansions, "frontier": len(frontier)})
            return SearchResult("UNKNOWN", expansions, generated, elapsed_s=elapsed,
                                reason=sstate, historian=historian)

        _, _, state = heapq.heappop(frontier)
        signature = tuple(g.statement for g in state.open_goals)
        prev = best_seen.get(signature)
        if prev is not None and prev <= state.depth:
            historian.append({"actor": "Quicksand", "action": "duplicate_state_discard",
                              "depth": state.depth, "open_goals": len(state.open_goals)})
            continue
        best_seen[signature] = state.depth

        if not state.open_goals:
            proof = _linearize(0, state.derivations)
            if verify_candidate is None:
                return SearchResult("CANDIDATE", expansions, generated, proof, elapsed,
                                    "terminal_candidate", historian)
            accepted, verification = verify_candidate(proof)
            historian.append({"actor": "Verifier", "action": "candidate_check",
                              "accepted": accepted, "expansions": expansions,
                              "proof_labels": len(proof)})
            if accepted:
                return SearchResult("PROVED", expansions, generated, proof, elapsed,
                                    "verifier_accepted", historian, verification)
            continue

        expansions += 1
        goal = state.open_goals[0]
        rest = state.open_goals[1:]
        historian.append({"actor": "Search", "action": "expand", "expansion": expansions,
                          "goal": " ".join(goal.statement), "open_goals": len(state.open_goals),
                          "pc": PartialCredit.value(state)})

        hyp_label = target_hyp_by_stmt.get(goal.statement)
        if hyp_label is not None:
            deriv = dict(state.derivations)
            deriv[goal.gid] = Derivation(hyp_label, ())
            child = SearchState(rest, deriv, state.next_gid, state.depth, last_action=hyp_label)
            child.score = Scout.successor_score(state, child)
            heapq.heappush(frontier, (-child.score, next(counter), child))
            generated += 1

        shelf = librarian.shelf(goal.statement, config.candidate_cap)
        historian.append({"actor": "Librarian", "action": "retrieve", "expansion": expansions,
                          "goal": " ".join(goal.statement), "shelf_size": len(shelf),
                          "shelf_labels": [a.label for a in shelf]})
        admitted_here = 0
        for cand in shelf:
            for match in match_statement(
                cand, goal.statement, db.variables,
                max_matches=config.match_cap_per_candidate,
                max_sequence_len=config.max_sequence_len,
            ):
                subst = match.as_dict()
                if not _dv_ok(cand, subst, target, db.variables):
                    continue
                instantiated = _instantiate_hypotheses(cand, subst, db.variables)
                if instantiated is None:
                    continue
                if any(h.kind == "$f" and not syntax_oracle.valid(stmt) for h, stmt in instantiated):
                    continue
                child_statements = tuple(stmt for _, stmt in instantiated)
                if state.depth + 1 > config.max_depth:
                    continue
                if len(rest) + len(child_statements) > config.max_open_goals:
                    continue

                deriv = dict(state.derivations)
                child_ids: list[int] = []
                new_goals: list[Goal] = []
                ngid = state.next_gid
                for stmt in child_statements:
                    child_ids.append(ngid)
                    new_goals.append(Goal(ngid, stmt))
                    ngid += 1
                deriv[goal.gid] = Derivation(cand.label, tuple(child_ids))
                child = SearchState(tuple(new_goals) + rest, deriv, ngid,
                                    state.depth + 1, last_action=cand.label)
                child.score = Scout.successor_score(state, child)
                heapq.heappush(frontier, (-child.score, next(counter), child))
                generated += 1
                admitted_here += 1
                historian.append({"actor": "Scout", "action": "score_successor",
                                  "expansion": expansions, "candidate": cand.label,
                                  "score": child.score, "child_open_goals": len(child.open_goals)})
                historian.append({"actor": "Professor", "action": "admit_successor",
                                  "expansion": expansions, "candidate": cand.label})
        if admitted_here == 0 and hyp_label is None:
            historian.append({"actor": "Quicksand", "action": "no_legal_successor",
                              "expansion": expansions, "goal": " ".join(goal.statement)})

    elapsed = time.monotonic() - start
    return SearchResult("UNKNOWN", expansions, generated, elapsed_s=elapsed,
                        reason="frontier_exhausted", historian=historian)
