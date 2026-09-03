from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import itertools
import time
from typing import Callable, Iterable

from .matcher import apply_substitution, match_pattern, match_statement
from .parser import Assertion, Database, Hypothesis


@dataclass(frozen=True)
class Goal:
    gid: int
    statement: tuple[str, ...]


@dataclass(frozen=True)
class Derivation:
    label: str
    # An int is a logical child goal. A tuple[str,...] is a complete syntax
    # proof emitted by SyntaxOracle for one floating hypothesis.
    premises: tuple[object, ...]


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
    free_var_completion_cap: int = 64
    term_pool_cap_per_type: int = 256
    definition_rounds: int = 2
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
    """Retrieve structurally possible legal-prefix assertions, then rank them."""

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
        essential = sum(1 for h in a.mandatory_hypotheses if h.kind == "$e")
        # A small preference for low-premise rules, not a proof-specific prior.
        return 2.5 * overlap + len_bonus - 0.08 * essential

    def shelf(self, goal: tuple[str, ...], cap: int) -> tuple[Assertion, ...]:
        key = (goal, cap)
        if key in self._cache:
            return self._cache[key]
        pool = self.by_type.get(goal[0], ()) if goal else ()
        filtered = [a for a in pool if _is_subsequence(_fixed_skeleton(a), goal)]
        ranked = sorted(filtered, key=lambda a: (-self._score(a, goal), a.order, a.label))
        value = tuple(ranked[:cap] if cap > 0 else ranked)
        self._cache[key] = value
        return value


class SyntaxOracle:
    """Prefix-derived syntax recognizer/proof emitter; it cannot certify `|-` truth."""

    def __init__(self, db: Database, target: Assertion, legal_assertions: tuple[Assertion, ...]):
        self.db = db
        self.assumption_proofs = {
            h.statement: (h.label,) for h in target.mandatory_hypotheses if h.kind == "$f"
        }
        syntax = [a for a in legal_assertions if a.statement and a.statement[0] != "|-"]
        self.librarian = StructuralLibrarian(syntax)
        self.memo: dict[tuple[str, ...], tuple[str, ...] | None] = {}
        self.visiting: set[tuple[str, ...]] = set()

    def prove(self, statement: tuple[str, ...], depth: int = 0) -> tuple[str, ...] | None:
        assumed = self.assumption_proofs.get(statement)
        if assumed is not None:
            return assumed
        if statement in self.memo:
            return self.memo[statement]
        if not statement or statement[0] == "|-" or depth > 18 or statement in self.visiting:
            return None
        self.visiting.add(statement)
        try:
            for cand in self.librarian.shelf(statement, 512):
                for match in match_statement(cand, statement, self.db.variables, max_matches=12):
                    subst = match.as_dict()
                    if any(v not in subst for v in cand.mandatory_variables):
                        continue
                    chunks: list[str] = []
                    ok = True
                    for h in cand.mandatory_hypotheses:
                        inst = apply_substitution(h.statement, subst, self.db.variables)
                        if h.kind == "$e":
                            ok = False
                            break
                        child = self.prove(inst, depth + 1)
                        if child is None:
                            ok = False
                            break
                        chunks.extend(child)
                    if ok:
                        result = tuple(chunks + [cand.label])
                        self.memo[statement] = result
                        return result
            self.memo[statement] = None
            return None
        finally:
            self.visiting.discard(statement)

    def valid(self, statement: tuple[str, ...]) -> bool:
        return self.prove(statement) is not None


class TermScout:
    """Generate typed term proposals without consulting the target proof.

    Sources are visible target syntax plus legal-prefix `df-*` equalities. This
    is a generic presentation-exploration mechanism: definitions suggest useful
    alternate terms, but only the final Metamath verifier can establish a proof.
    """

    def __init__(
        self,
        db: Database,
        target: Assertion,
        legal_assertions: tuple[Assertion, ...],
        syntax: SyntaxOracle,
        config: SearchConfig,
    ):
        self.db = db
        self.target = target
        self.syntax = syntax
        self.config = config
        self.types = sorted({tc for _, tc in target.variable_types} | {"class", "wff", "setvar"})
        self.pool: dict[str, set[tuple[str, ...]]] = {tc: set() for tc in self.types}
        self.definitions = tuple(
            a for a in legal_assertions
            if a.label.startswith("df-")
            and a.statement and a.statement[0] == "|-"
            and not any(h.kind == "$e" for h in a.mandatory_hypotheses)
            and "=" in a.statement[1:]
        )
        for h in target.mandatory_hypotheses:
            if h.kind == "$f" and h.typecode and h.variable:
                self.pool.setdefault(h.typecode, set()).add((h.variable,))
        self.observe(target.statement)
        self._definition_expand(config.definition_rounds)

    def _add_spans(self, tokens: tuple[str, ...]) -> bool:
        changed = False
        # Formula typecode is not part of the term itself.
        body = tokens[1:] if tokens and tokens[0] in ("|-", "wff", "class", "setvar") else tokens
        n = len(body)
        for i in range(n):
            for j in range(i + 1, min(n, i + 24) + 1):
                span = body[i:j]
                for tc in self.types:
                    bucket = self.pool.setdefault(tc, set())
                    if len(bucket) >= self.config.term_pool_cap_per_type or span in bucket:
                        continue
                    if self.syntax.valid((tc,) + span):
                        bucket.add(span)
                        changed = True
        return changed

    def observe(self, statement: tuple[str, ...]) -> None:
        self._add_spans(statement)

    def _definition_expand(self, rounds: int) -> None:
        for _ in range(max(0, rounds)):
            changed = False
            class_terms = list(self.pool.get("class", ()))
            for a in self.definitions:
                try:
                    eq = a.statement.index("=", 1)
                except ValueError:
                    continue
                left = tuple(a.statement[1:eq])
                right = tuple(a.statement[eq + 1:])
                if not left or not right:
                    continue
                vars_ = a.mandatory_variables
                tmap = a.variable_type_map
                for term in class_terms:
                    for src, dst in ((left, right), (right, left)):
                        for m in match_pattern(src, term, vars_, tmap, max_matches=4):
                            subst = m.as_dict()
                            if any(v in dst and v not in subst for v in vars_):
                                continue
                            proposal = apply_substitution(dst, subst, self.db.variables)
                            if self.syntax.valid(("class",) + proposal):
                                bucket = self.pool.setdefault("class", set())
                                if proposal not in bucket and len(bucket) < self.config.term_pool_cap_per_type:
                                    bucket.add(proposal)
                                    changed = True
                                changed = self._add_spans(("class",) + proposal) or changed
            if not changed:
                break

    def terms(self, typecode: str, goal: tuple[str, ...], limit: int = 24) -> tuple[tuple[str, ...], ...]:
        self.observe(goal)
        # One cheap definition update allows newly observed goal subterms to trade.
        self._definition_expand(1)
        terms = self.pool.get(typecode, set())
        gset = set(goal)
        ranked = sorted(
            terms,
            key=lambda t: (-len(set(t) & gset), len(t), t),
        )
        return tuple(ranked[:limit])


class PartialCredit:
    @staticmethod
    def value(state: SearchState) -> float:
        if not state.open_goals:
            return 1.0
        mass = sum(len(g.statement) for g in state.open_goals)
        return 1.0 / (1.0 + 0.9 * len(state.open_goals) + 0.012 * mass)


class Scout:
    @staticmethod
    def successor_score(parent: SearchState, child: SearchState) -> float:
        return 12.0 * PartialCredit.value(child) - 0.02 * child.depth - 0.005 * len(child.open_goals)


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


def _complete_substitutions(
    assertion: Assertion,
    base: dict[str, tuple[str, ...]],
    term_scout: TermScout,
    goal: tuple[str, ...],
    cap: int,
) -> tuple[dict[str, tuple[str, ...]], ...]:
    missing = [v for v in sorted(assertion.mandatory_variables) if v not in base]
    if not missing:
        return (dict(base),)
    pools: list[tuple[tuple[str, ...], ...]] = []
    tmap = assertion.variable_type_map
    for v in missing:
        terms = term_scout.terms(tmap.get(v, "class"), goal, limit=16)
        if not terms:
            return ()
        pools.append(terms)
    out: list[dict[str, tuple[str, ...]]] = []
    for values in itertools.product(*pools):
        s = dict(base)
        s.update(zip(missing, values))
        out.append(s)
        if len(out) >= cap:
            break
    return tuple(out)


def _linearize(root_gid: int, derivations: dict[int, Derivation]) -> tuple[str, ...]:
    out: list[str] = []
    visiting: set[int] = set()

    def walk(gid: int) -> None:
        if gid in visiting:
            raise RuntimeError("cycle in derivation")
        d = derivations[gid]
        visiting.add(gid)
        for premise in d.premises:
            if isinstance(premise, int):
                walk(premise)
            else:
                out.extend(premise)
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
    syntax = SyntaxOracle(db, target, legal_assertions)
    term_scout = TermScout(db, target, legal_assertions, syntax, config)
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
        term_scout.observe(goal.statement)
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
                for subst in _complete_substitutions(
                    cand, match.as_dict(), term_scout, goal.statement,
                    config.free_var_completion_cap,
                ):
                    if not _dv_ok(cand, subst, target, db.variables):
                        continue
                    if state.depth + 1 > config.max_depth:
                        continue

                    premise_refs: list[object] = []
                    new_goals: list[Goal] = []
                    ngid = state.next_gid
                    ok = True
                    for h in cand.mandatory_hypotheses:
                        inst = apply_substitution(h.statement, subst, db.variables)
                        if h.kind == "$f":
                            syntax_proof = syntax.prove(inst)
                            if syntax_proof is None:
                                ok = False
                                break
                            premise_refs.append(syntax_proof)
                        else:
                            premise_refs.append(ngid)
                            new_goals.append(Goal(ngid, inst))
                            ngid += 1
                    if not ok or len(rest) + len(new_goals) > config.max_open_goals:
                        continue

                    deriv = dict(state.derivations)
                    deriv[goal.gid] = Derivation(cand.label, tuple(premise_refs))
                    child = SearchState(tuple(new_goals) + rest, deriv, ngid,
                                        state.depth + 1, last_action=cand.label)
                    child.score = Scout.successor_score(state, child)
                    heapq.heappush(frontier, (-child.score, next(counter), child))
                    generated += 1
                    admitted_here += 1
                    historian.append({"actor": "Scout", "action": "score_successor",
                                      "expansion": expansions, "candidate": cand.label,
                                      "score": child.score, "child_open_goals": len(child.open_goals),
                                      "free_vars_completed": len(cand.mandatory_variables - match.as_dict().keys())})
                    historian.append({"actor": "Professor", "action": "admit_successor",
                                      "expansion": expansions, "candidate": cand.label})
        if admitted_here == 0 and hyp_label is None:
            historian.append({"actor": "Quicksand", "action": "no_legal_successor",
                              "expansion": expansions, "goal": " ".join(goal.statement)})

    elapsed = time.monotonic() - start
    return SearchResult("UNKNOWN", expansions, generated, elapsed_s=elapsed,
                        reason="frontier_exhausted", historian=historian)
