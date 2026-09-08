from __future__ import annotations

"""Experimental search-order ablation built on the DATA MIND Metamath kernel.

The implementation mirrors ``data_mind_3.metamath.search.search_target`` and
changes only a bounded successor-priority term.  Mode ``off`` is retained as a
within-module control so a smoke test can establish equivalence with the
production baseline on the same fixture.
"""

import heapq
import itertools
import time
from typing import Callable

from data_mind_3.metamath.matcher import apply_substitution, match_statement
from data_mind_3.metamath.parser import Database
from data_mind_3.metamath.search import (
    Derivation,
    Goal,
    PartialCredit,
    Scout,
    SearchConfig,
    SearchResult,
    SearchState,
    Sentinel,
    StructuralLibrarian,
    SyntaxOracle,
    TermScout,
    _complete_substitutions,
    _dv_ok,
    _linearize,
)

from .geometry import DEFAULT_BITS, address_premise, hilbert_action_key


HILBERT_WEIGHT = 0.75


def _hilbert_bonus(
    *,
    goal_statement: tuple[str, ...],
    premise_statements: tuple[tuple[str, ...], ...],
    variables: set[str],
    mode: str,
    bits: int,
) -> tuple[float, dict]:
    """Return a bounded local-Hilbert priority bonus and diagnostic record.

    The current goal provides a local structural anchor.  A k-premise action is
    compared with the k-fold anchor point along the finite k-dimensional
    Hilbert traversal.  This is navigation metadata only; it cannot make an
    illegal inference legal or turn a candidate into a proof.
    """
    k = len(premise_statements)
    if mode == "off" or k == 0:
        return 0.0, {"arity": k, "bonus": 0.0}
    if mode not in {"naive", "structural"}:
        raise ValueError(f"unknown Hilbert mode: {mode}")

    h_action, point = hilbert_action_key(
        premise_statements, variables, mode=mode, bits=bits
    )
    anchor_scalar = address_premise(goal_statement, variables, mode=mode, bits=bits)
    anchor_point = tuple(anchor_scalar for _ in range(k))
    from .geometry import hilbert_distance
    h_anchor = hilbert_distance(anchor_point, bits)

    volume = 1 << (bits * k)
    raw = abs(h_action - h_anchor)
    circular = min(raw, volume - raw)
    half = max(1, volume // 2)
    closeness = max(0.0, 1.0 - circular / half)
    bonus = HILBERT_WEIGHT * closeness
    return bonus, {
        "arity": k,
        "point": list(point),
        "anchor_point": list(anchor_point),
        "hilbert_index": h_action,
        "anchor_index": h_anchor,
        "circular_distance": circular,
        "closeness": closeness,
        "bonus": bonus,
    }


def search_target_geometric(
    db: Database,
    target_label: str,
    config: SearchConfig,
    *,
    mode: str,
    verify_candidate: Callable[[tuple[str, ...]], tuple[bool, dict]] | None = None,
    bits: int = DEFAULT_BITS,
) -> SearchResult:
    """Search a target with the frozen Experiment-001 navigation mode."""
    if mode not in {"off", "naive", "structural"}:
        raise ValueError("mode must be off, naive, or structural")

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
            historian.append({
                "actor": "Sentinel", "action": "stop", "reason": sstate,
                "expansions": expansions, "frontier": len(frontier),
            })
            return SearchResult(
                "UNKNOWN", expansions, generated, elapsed_s=elapsed,
                reason=sstate, historian=historian,
            )

        _, _, state = heapq.heappop(frontier)
        signature = tuple(g.statement for g in state.open_goals)
        prev = best_seen.get(signature)
        if prev is not None and prev <= state.depth:
            historian.append({
                "actor": "Quicksand", "action": "duplicate_state_discard",
                "depth": state.depth, "open_goals": len(state.open_goals),
            })
            continue
        best_seen[signature] = state.depth

        if not state.open_goals:
            proof = _linearize(0, state.derivations)
            if verify_candidate is None:
                return SearchResult(
                    "CANDIDATE", expansions, generated, proof, elapsed,
                    "terminal_candidate", historian,
                )
            accepted, verification = verify_candidate(proof)
            historian.append({
                "actor": "Verifier", "action": "candidate_check",
                "accepted": accepted, "expansions": expansions,
                "proof_labels": len(proof),
            })
            if accepted:
                return SearchResult(
                    "PROVED", expansions, generated, proof, elapsed,
                    "verifier_accepted", historian, verification,
                )
            continue

        expansions += 1
        goal = state.open_goals[0]
        rest = state.open_goals[1:]
        term_scout.observe(goal.statement)
        state_pc = PartialCredit.value(state)
        historian.append({
            "actor": "Search", "action": "expand", "expansion": expansions,
            "goal": " ".join(goal.statement), "open_goals": len(state.open_goals),
            "pc": state_pc, "navigation_mode": mode,
        })

        hyp_label = target_hyp_by_stmt.get(goal.statement)
        if hyp_label is not None:
            deriv = dict(state.derivations)
            deriv[goal.gid] = Derivation(hyp_label, ())
            child = SearchState(rest, deriv, state.next_gid, state.depth, last_action=hyp_label)
            child.score = Scout.successor_score(state, child)
            heapq.heappush(frontier, (-child.score, next(counter), child))
            generated += 1

        shelf = librarian.shelf(
            goal.statement,
            config.candidate_cap,
            target=target.statement,
            lemma_direction=0.0,
        )
        historian.append({
            "actor": "Librarian", "action": "retrieve", "expansion": expansions,
            "goal": " ".join(goal.statement), "shelf_size": len(shelf),
            "shelf_labels": [a.label for a in shelf],
            "effective_candidate_cap": config.candidate_cap,
        })

        admitted_here = 0
        for cand in shelf:
            for match in match_statement(
                cand,
                goal.statement,
                db.variables,
                max_matches=config.match_cap_per_candidate,
                max_sequence_len=config.max_sequence_len,
            ):
                for subst in _complete_substitutions(
                    cand,
                    match.as_dict(),
                    term_scout,
                    goal.statement,
                    config.free_var_completion_cap,
                    term_limit=16,
                    target_statement=target.statement,
                    term_ordering=0.5,
                    definition_rounds=1,
                ):
                    if not _dv_ok(cand, subst, target, db.variables):
                        continue
                    if state.depth + 1 > config.max_depth:
                        continue

                    premise_refs: list[object] = []
                    logical_premises: list[tuple[str, ...]] = []
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
                            logical_premises.append(inst)
                            new_goals.append(Goal(ngid, inst))
                            ngid += 1
                    if not ok or len(rest) + len(new_goals) > config.max_open_goals:
                        continue

                    deriv = dict(state.derivations)
                    deriv[goal.gid] = Derivation(cand.label, tuple(premise_refs))
                    child = SearchState(
                        tuple(new_goals) + rest,
                        deriv,
                        ngid,
                        state.depth + 1,
                        last_action=cand.label,
                    )
                    base_score = Scout.successor_score(state, child)
                    bonus, geometry = _hilbert_bonus(
                        goal_statement=goal.statement,
                        premise_statements=tuple(logical_premises),
                        variables=db.variables,
                        mode=mode,
                        bits=bits,
                    )
                    child.score = base_score + bonus
                    heapq.heappush(frontier, (-child.score, next(counter), child))
                    generated += 1
                    admitted_here += 1
                    historian.append({
                        "actor": "HilbertNavigator" if mode != "off" else "Scout",
                        "action": "score_successor",
                        "expansion": expansions,
                        "candidate": cand.label,
                        "base_score": base_score,
                        "score": child.score,
                        "child_open_goals": len(child.open_goals),
                        "free_vars_completed": len(cand.mandatory_variables - match.as_dict().keys()),
                        "geometry": geometry,
                    })

        if admitted_here == 0 and hyp_label is None:
            historian.append({
                "actor": "Quicksand", "action": "no_legal_successor",
                "expansion": expansions, "goal": " ".join(goal.statement),
            })

    elapsed = time.monotonic() - start
    return SearchResult(
        "UNKNOWN", expansions, generated, elapsed_s=elapsed,
        reason="frontier_exhausted", historian=historian,
    )
