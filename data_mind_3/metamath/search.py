from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import itertools
import time
from typing import Callable, Iterable

from .matcher import apply_substitution, match_statement
from .parser import Assertion, Database


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
    candidate_cap: int = 32
    match_cap_per_candidate: int = 4
    max_sequence_len: int = 48
    timeout_s: float = 300.0
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


class StructuralLibrarian:
    """Target-generic retrieval of a small working shelf from legal prefix assertions."""

    def __init__(self, assertions: Iterable[Assertion]):
        self.assertions = tuple(assertions)
        self._cache: dict[tuple[tuple[str, ...], int], tuple[Assertion, ...]] = {}
        self.by_type: dict[str, list[Assertion]] = {}
        for a in self.assertions:
            if a.statement:
                self.by_type.setdefault(a.statement[0], []).append(a)

    @staticmethod
    def _score(a: Assertion, goal: tuple[str, ...]) -> float:
        aset = set(a.statement[1:])
        gset = set(goal[1:])
        overlap = len(aset & gset)
        exact_len_bonus = 2.0 / (1.0 + abs(len(a.statement) - len(goal)))
        hyp_penalty = 0.15 * len(a.mandatory_hypotheses)
        theorem_bonus = 0.05 if a.kind == "$p" else 0.0
        return 2.0 * overlap + exact_len_bonus + theorem_bonus - hyp_penalty

    def shelf(self, goal: tuple[str, ...], cap: int) -> tuple[Assertion, ...]:
        key = (goal, cap)
        if key in self._cache:
            return self._cache[key]
        pool = self.by_type.get(goal[0], ()) if goal else ()
        ranked = sorted(pool, key=lambda a: (-self._score(a, goal), a.order, a.label))
        value = tuple(ranked[:cap])
        self._cache[key] = value
        return value


class PartialCredit:
    """Search measurement only; never a settlement authority."""

    @staticmethod
    def value(state: SearchState) -> float:
        if not state.open_goals:
            return 1.0
        mass = sum(len(g.statement) for g in state.open_goals)
        return 1.0 / (1.0 + len(state.open_goals) + 0.02 * mass)


class Scout:
    @staticmethod
    def successor_score(parent: SearchState, child: SearchState) -> float:
        pc = PartialCredit.value(child)
        return 8.0 * pc - 0.025 * child.depth - 0.01 * len(child.open_goals)


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
) -> tuple[tuple[str, ...], ...] | None:
    # Explicit capability boundary of generalized adapter v0.1: mandatory
    # variables must be constrained by the conclusion match.
    if any(v not in subst for v in assertion.mandatory_variables):
        return None
    return tuple(
        apply_substitution(h.statement, subst, all_variables)
        for h in assertion.mandatory_hypotheses
    )


def _dv_ok(
    assertion: Assertion,
    subst: dict[str, tuple[str, ...]],
    target: Assertion,
    all_variables: set[str],
) -> bool:
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
    sentinel = Sentinel(config)

    target_hyp_by_stmt = {h.statement: h.label for h in target.mandatory_hypotheses}
    root = Goal(0, target.statement)
    initial = SearchState((root,), {}, 1, 0, 0.0)
    counter = itertools.count()
    frontier: list[tuple[float, int, SearchState]] = []
    heapq.heappush(frontier, (0.0, next(counter), initial))
    expansions = 0
    generated = 0
    start = time.monotonic()
    historian: list[dict] = []
    best_seen: dict[tuple[tuple[str, ...], ...], int] = {}

    while frontier:
        elapsed = time.monotonic() - start
        allowed, sentinel_state = sentinel.allow(expansions, len(frontier), elapsed)
        if not allowed:
            historian.append({"actor": "Sentinel", "action": "stop", "reason": sentinel_state,
                              "expansions": expansions, "frontier": len(frontier)})
            return SearchResult("UNKNOWN", expansions, generated, elapsed_s=elapsed,
                                reason=sentinel_state, historian=historian)

        _, _, state = heapq.heappop(frontier)
        signature = tuple(g.statement for g in state.open_goals)
        previous_depth = best_seen.get(signature)
        if previous_depth is not None and previous_depth <= state.depth:
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

        # Frozen Experiment-004 metric: exactly one expansion per nonterminal
        # state popped and actually expanded.
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
                          "goal": " ".join(goal.statement), "shelf_size": len(shelf)})

        for cand in shelf:
            matches = match_statement(cand, goal.statement, db.variables,
                                      max_matches=config.match_cap_per_candidate,
                                      max_sequence_len=config.max_sequence_len)
            for match in matches:
                subst = match.as_dict()
                if not _dv_ok(cand, subst, target, db.variables):
                    continue
                child_statements = _instantiate_hypotheses(cand, subst, db.variables)
                if child_statements is None:
                    continue
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
                historian.append({"actor": "Scout", "action": "score_successor",
                                  "expansion": expansions, "candidate": cand.label,
                                  "score": child.score, "child_open_goals": len(child.open_goals)})
                historian.append({"actor": "Professor", "action": "admit_successor",
                                  "expansion": expansions, "candidate": cand.label})

    elapsed = time.monotonic() - start
    return SearchResult("UNKNOWN", expansions, generated, elapsed_s=elapsed,
                        reason="frontier_exhausted", historian=historian)
