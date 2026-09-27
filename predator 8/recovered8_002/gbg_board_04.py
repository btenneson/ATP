#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import heapq
import importlib.util
import json
import math
import os
import random
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Predator_8.001_FROZEN.py")

spec = importlib.util.spec_from_file_location("predator8_frozen", ENGINE)
p8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p8)


# ---------------------------------------------------------------------------
# Board-ATP 0.4 generic Metamath DV legality gate.
#
# This is not sbth-specific guidance.  It closes a soundness/engineering gap
# exposed by the first sbth transfer run: Board 0.2 reached a syntactically
# closed candidate, but deterministic grounding made a $d obligation illegal.
# 0.3 keeps the 0.2 ranking unchanged and continues the SAME frontier past
# terminal candidates that cannot survive Metamath DV verification.
# ---------------------------------------------------------------------------
_TARGET_SCOPE_DVS = None
_GROUND_DOMAINS = {}


def set_target_scope_dvs(dvs):
    global _TARGET_SCOPE_DVS
    _TARGET_SCOPE_DVS = set(dvs) if dvs is not None else None


def set_ground_domains(vars_by_type):
    global _GROUND_DOMAINS
    _GROUND_DOMAINS = {tc: tuple(vs) for tc, vs in vars_by_type.items()}


def _rigid_vars(t, sub, acc=None):
    if acc is None:
        acc = set()
    t = p8.walk(t, sub)
    if t.var is not None:
        if not p8.is_meta(t):
            acc.add(t.var)
        return acc
    for k in t.kids:
        _rigid_vars(k, sub, acc)
    return acc


def _dv_obligations(data, mapping):
    out = []
    for x, y in data[0]:
        tx, ty = mapping.get(x), mapping.get(y)
        if tx is not None and ty is not None:
            out.append((tx, ty, x, y))
    return tuple(out)


def _dv_ok(obligations, sub):
    allowed = _TARGET_SCOPE_DVS
    for tx, ty, _x, _y in obligations:
        xs = _rigid_vars(tx, sub)
        ys = _rigid_vars(ty, sub)
        for a in xs:
            for b in ys:
                if a == b:
                    return False
                if allowed is not None and (min(a, b), max(a, b)) not in allowed:
                    return False
    return True


def _emission_fallback_from_grammar():
    fallback = {}
    for var, tc in p8.G.VARTYPE.items():
        fallback.setdefault(tc, p8.G.Tree(None, tc, (), var))
    return fallback


def _terminal_dv_ok(obligations, sub):
    fallback = _emission_fallback_from_grammar()
    grounded = []
    try:
        for tx, ty, x, y in obligations:
            gx = p8.ground(tx, sub, fallback)
            gy = p8.ground(ty, sub, fallback)
            grounded.append((gx, gy, x, y))
    except KeyError:
        return False
    return _dv_ok(tuple(grounded), {})


def _meta_vars(t, sub, out=None):
    """Collect unresolved search metavariables occurring in a tree."""
    if out is None:
        out = {}
    t = p8.walk(t, sub)
    if t.var is not None:
        if p8.is_meta(t):
            out.setdefault(t.var, t.typecode)
        return out
    for k in t.kids:
        _meta_vars(k, sub, out)
    return out


def _terminal_dv_completion(obligations, sub):
    """Try a legal assignment for unresolved DV-relevant metavariables.

    Board 0.2/0.3 used the engine's single per-type fallback variable.  That
    can manufacture a DV collision even when the terminal proof skeleton still
    has freedom to choose distinct ordinary variables.  0.4 solves only this
    finite legality CSP.  It does not inspect the target proof and it does not
    alter the proof-search ranking.

    Return an extended substitution if a verifier-compatible variable
    assignment is found; otherwise return None.
    """
    metas = {}
    for tx, ty, _x, _y in obligations:
        _meta_vars(tx, sub, metas)
        _meta_vars(ty, sub, metas)

    if not metas:
        return dict(sub) if _terminal_dv_ok(obligations, sub) else None

    degree = {m: 0 for m in metas}
    for tx, ty, _x, _y in obligations:
        seen = {}
        _meta_vars(tx, sub, seen)
        _meta_vars(ty, sub, seen)
        for m in seen:
            if m in degree:
                degree[m] += 1

    domains = {}
    for m, tc in metas.items():
        vs = _GROUND_DOMAINS.get(tc, ())
        if not vs:
            return None
        domains[m] = tuple(p8.G.Tree(None, tc, (), v) for v in vs)

    order = sorted(metas, key=lambda m: (len(domains[m]), -degree[m], m))
    base = dict(sub)

    def dfs(i, cur):
        if i == len(order):
            return cur if _terminal_dv_ok(obligations, cur) else None
        m = order[i]
        for tree in domains[m]:
            nxt = dict(cur)
            nxt[m] = tree
            if _dv_ok(obligations, nxt):
                ans = dfs(i + 1, nxt)
                if ans is not None:
                    return ans
        return None

    return dfs(0, base)


class DVStats:
    partial_rejects = 0
    terminal_rejects = 0


def prove_board_dv(goal_tree, index, budget, max_depth, rank=None, say=print,
                   progress=2000, max_open=6, profile=None, seed=0,
                   shared_use=None, agent_name=None):
    """Predator 8.001 search order + Board ranking + exact DV continuation gate."""
    if profile is None:
        profile = p8.Profile("deterministic", 0.0, 0.0, 0.0, 0.0,
                             0.0, 48, 1.0)
    rng = random.Random(seed)
    local_use = defaultdict(int)
    if shared_use is None:
        shared_use = defaultdict(int)
    agent_name = agent_name or profile.name

    start = p8.Node([(goal_tree, None, 0)], {}, (), 0)
    frontier = [(0.0, 0, start)]
    dv_by_node = {start: ()}
    exp = tie = 0
    seen = set()
    t0 = time.perf_counter()

    while frontier and exp < budget:
        priority, _, node = heapq.heappop(frontier)
        node_dv = dv_by_node.pop(node, ())
        exp += 1

        if not _dv_ok(node_dv, node.sub):
            DVStats.partial_rejects += 1
            continue

        if progress and say and exp % progress == 0:
            say("      [%s] %s expansions, %d open goals, %.0fs, dvrej=%s, dvfinal=%s"
                % (agent_name, f"{exp:,}", len(node.goals),
                   time.perf_counter() - t0,
                   f"{DVStats.partial_rejects:,}",
                   f"{DVStats.terminal_rejects:,}"))

        if not node.goals:
            completed_sub = _terminal_dv_completion(node_dv, node.sub)
            if completed_sub is None:
                DVStats.terminal_rejects += 1
                if say and (DVStats.terminal_rejects <= 5 or
                            DVStats.terminal_rejects in {10,25,50,100,250,500,1000}):
                    say("      [%s] terminal DV rejection #%s after CSP grounding; continuing frontier"
                        % (agent_name, f"{DVStats.terminal_rejects:,}"))
                continue

            root = None
            for parent, ix, st in node.trail:
                if parent is None:
                    root = st
                else:
                    parent.subs[ix] = st
            return (root, completed_sub), exp

        if node.depth >= max_depth or len(node.goals) > max_open:
            continue

        gi = p8.pick_goal(node.goals, node.sub)
        gt, slot, hix = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = p8.apply_sub(gt, node.sub)

        key = (node.depth, " ".join(gt.tokens()),
               tuple(sorted(" ".join(p8.apply_sub(g, node.sub).tokens())
                            for g, _, _ in rest)))
        if key in seen:
            continue
        seen.add(key)

        closers, openers = index.candidates(gt)
        sc_c = rank(gt, closers) if rank else [0.0] * len(closers)
        sc_o = rank(gt, openers) if rank else [0.0] * len(openers)
        ranked_c = p8._candidate_scores(gt, closers, sc_c, profile, rng,
                                        local_use, shared_use)
        ranked_o = p8._candidate_scores(gt, openers, sc_o, profile, rng,
                                        local_use, shared_use)
        pick = ranked_c + p8._counterfactual_slice(
            ranked_o, profile.opener_cap, profile.exploration, rng)

        for candidate_score, (lab, ct, data) in pick:
            m = {}
            c2 = p8.rename_apart(ct, m)
            s2 = p8.unify(c2, gt, node.sub)
            if s2 is None:
                continue

            _dvs, f_hyps, e_hyps, _ = data
            fmap = {var: m.get(var, p8.fresh(tc)) for _, tc, var in f_hyps}
            for _, tc, var in f_hyps:
                m.setdefault(var, fmap[var])

            successor_dv = node_dv + _dv_obligations(data, m)
            if not _dv_ok(successor_dv, s2):
                DVStats.partial_rejects += 1
                continue

            step = p8.Step(lab, fmap, data)
            newgoals = []
            ok = True
            for hj, (_, stat) in enumerate(e_hyps):
                try:
                    ht = p8.G.parse(stat[1:], "wff", index.by_tc)
                except (RecursionError, p8.MMError):
                    ht = None
                if ht is None:
                    ok = False
                    break
                newgoals.append((p8.rename_apart(ht, m), step, hj))
            if not ok:
                continue

            local_use[lab] += 1
            shared_use[lab] += 1
            tie += 1
            guide = math.tanh(candidate_score / 2.0)
            edge_cost = (0.25 if not e_hyps else 1.0) - 0.20 * guide
            state_cost = 0.02 * len(newgoals + rest)
            successor = p8.Node(
                newgoals + rest, s2,
                node.trail + ((slot, hix, step),),
                node.depth + 1)
            dv_by_node[successor] = successor_dv
            heapq.heappush(
                frontier,
                (priority + edge_cost + state_cost, tie, successor))

    return None, exp



class RankStats:
    def __init__(self):
        self.calls = 0
        self.items = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.unify_ok = 0
        self.unify_fail = 0


def make_board_ranker(by_tc, stats):
    """
    Board-ATP 0.4.

    GBG+ interpretation:
      M=1, N=0, P0 = board = ATP.

    Search authority is still the Metamath legality/verifier layer.  The Board
    uses only online current-state information and never reads the stored proof
    of the target.

    0.2 change from 0.1:
      - memoize the expensive goal/candidate legality-and-obligation analysis;
      - precompute assertion metadata once;
      - compute the rich score only once per (goal,candidate) pair.

    This preserves the 0.1 ranking function while attacking controller overhead.
    """
    meta_cache = {}
    score_cache = {}

    def metadata(lab, ct, data):
        rec = meta_cache.get(lab)
        if rec is not None:
            return rec
        _, _f_hyps, e_hyps, _ = data
        htrees = []
        for _, stat in e_hyps:
            try:
                htrees.append(p8.G.parse(stat[1:], "wff", by_tc))
            except Exception:
                htrees.append(None)
        rec = (len(e_hyps), htrees, frozenset(ct.tokens()))
        meta_cache[lab] = rec
        return rec

    def goal_key(goal):
        return tuple(goal.tokens())

    def rank(goal, items):
        stats.calls += 1
        stats.items += len(items)
        gkey = goal_key(goal)
        gset = frozenset(gkey)
        scores = []

        for lab, ct, data in items:
            key = (gkey, lab)
            cached = score_cache.get(key)
            if cached is not None:
                stats.cache_hits += 1
                scores.append(cached)
                continue

            stats.cache_misses += 1
            ne, htrees, cset = metadata(lab, ct, data)

            # Legality-relevant first gate: if the assertion conclusion cannot
            # unify with the current goal, it is never awarded rich target score.
            mapping = {}
            c2 = p8.rename_apart(ct, mapping)
            sub = p8.unify(c2, goal, {})
            if sub is None:
                stats.unify_fail += 1
                score = -9.0
                score_cache[key] = score
                scores.append(score)
                continue

            stats.unify_ok += 1
            direct = 1.0 if ne == 0 else 0.0
            conclusion_overlap = len(cset & gset) / max(1, len(cset | gset))

            residual_size = 0
            residual_metas = 0
            grounded = 0
            hyp_overlap_sum = 0.0
            hyp_count = 0

            for ht in htrees:
                if ht is None:
                    continue
                h2 = p8.rename_apart(ht, mapping)
                hs = p8.apply_sub(h2, sub)
                residual_size += hs.size()
                nm = len(p8.n_metas(hs, sub))
                residual_metas += nm
                grounded += int(nm == 0)
                hset = frozenset(hs.tokens())
                hyp_overlap_sum += len(hset & gset) / max(1, len(hset | gset))
                hyp_count += 1

            mean_hyp_overlap = hyp_overlap_sum / max(1, hyp_count)
            score = (
                2.20 * direct
                + 0.80 * conclusion_overlap
                + 0.28 * grounded
                + 0.18 * mean_hyp_overlap
                - 0.28 * ne
                - 0.012 * residual_size
                - 0.10 * residual_metas
            )
            score_cache[key] = score
            scores.append(score)

        return scores

    rank.cache_size = lambda: len(score_cache)
    rank.meta_size = lambda: len(meta_cache)
    return rank


def internal_verify(mm, label, proof):
    chk = p8.MM()
    chk.labels = dict(mm.labels)
    chk.order = list(mm.order)
    chk.proofs = dict(mm.proofs)
    chk.constants = mm.constants
    chk.variables = mm.variables
    chk.scope_dvs = dict(mm.scope_dvs)

    dvs, f_hyps, e_hyps, stat = mm.labels[label][1]
    chk.labels["__gbg_board_chk__"] = ("$p", (dvs, f_hyps, e_hyps, stat))
    chk.proofs["__gbg_board_chk__"] = proof
    chk.scope_dvs["__gbg_board_chk__"] = mm.scope_dvs.get(label, dvs)
    return chk.verify("__gbg_board_chk__")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("setmm")
    ap.add_argument("--label", required=True)
    ap.add_argument("--budget", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=2301)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--max-open", type=int, default=8)
    ap.add_argument("--creativity", type=float, default=0.55)
    ap.add_argument("--opener-cap", type=int, default=48)
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--out-prefix", default=None)
    args = ap.parse_args()

    target = args.label
    stem = args.out_prefix or f"{target}_gbg_board04"

    print("=" * 78)
    print("GBG+ BOARD-ATP 0.4")
    print("M=1, N=0, P0 = board = ATP")
    print("=" * 78)

    print("Loading frozen set.mm ...", flush=True)
    mm = p8.load(args.setmm)
    by_tc = p8.G.build_grammar(mm)

    if target not in mm.labels:
        raise RuntimeError("missing target " + target)

    stat = mm.labels[target][1][3]
    target_dvs = mm.scope_dvs.get(target, mm.labels[target][1][0])
    set_target_scope_dvs(target_dvs)

    # Legal grounding domain: target mandatory variables plus variables named
    # in active target-scope $d pairs, grouped by grammar typecode.
    active_vars = set()
    for _flab, _tc, var in mm.labels[target][1][1]:
        active_vars.add(var)
    for a, b in target_dvs:
        active_vars.add(a)
        active_vars.add(b)
    vars_by_type = {}
    for var in sorted(active_vars):
        tc = p8.G.VARTYPE.get(var)
        if tc is not None:
            vars_by_type.setdefault(tc, []).append(var)
    set_ground_domains(vars_by_type)

    p8.prove = prove_board_dv
    cut = mm.order.index(target)

    print(f"Target={target}; declaration index={cut}; indexing strict pre-target prefix ...", flush=True)
    idx = p8.Index(mm, by_tc, upto=cut, say=print)
    goal = p8.G.parse(stat[1:], "wff", by_tc)
    if goal is None:
        raise RuntimeError("target did not parse")

    fvar = {}
    fallback = {}
    for lab in mm.order:
        typ, d = mm.labels[lab]
        if typ == "$f":
            fvar.setdefault(d[1], lab)
            fallback.setdefault(d[0], p8.G.Tree(None, d[0], (), d[1]))

    stats = RankStats()
    rank = make_board_ranker(by_tc, stats)

    print(
        "Running Board-ATP 0.4: "
        f"budget={args.budget} seed={args.seed} max_depth={args.max_depth} "
        f"max_open={args.max_open} creativity={args.creativity} opener_cap={args.opener_cap}",
        flush=True,
    )

    t0 = time.perf_counter()
    res, exp, winner = p8.prove_population(
        goal,
        idx,
        args.budget,
        args.max_depth,
        agents=1,
        creativity=args.creativity,
        seed=args.seed,
        rank=rank,
        say=print,
        progress=args.progress,
        max_open=args.max_open,
        opener_cap=args.opener_cap,
    )
    dt = time.perf_counter() - t0

    row = {
        "target": target,
        "architecture": "GBG+ M=1; N=0; P0=board=ATP",
        "version": "Board-ATP 0.4",
        "engine": "Predator_8.001_FROZEN proof semantics",
        "scheduler": "cached target/obligation board ranker + generic DV legality gate + legal terminal grounding CSP",
        "budget": args.budget,
        "seed": args.seed,
        "max_depth": args.max_depth,
        "max_open": args.max_open,
        "creativity": args.creativity,
        "opener_cap": args.opener_cap,
        "expansions": exp,
        "search_seconds": dt,
        "verified_internal": False,
        "proof_steps": None,
        "winner": winner,
        "rank_calls": stats.calls,
        "rank_items": stats.items,
        "rank_cache_hits": stats.cache_hits,
        "rank_cache_misses": stats.cache_misses,
        "rank_cache_size": rank.cache_size(),
        "rank_meta_size": rank.meta_size(),
        "rank_unify_ok": stats.unify_ok,
        "rank_unify_fail": stats.unify_fail,
        "dv_partial_rejects": DVStats.partial_rejects,
        "dv_terminal_rejects": DVStats.terminal_rejects,
        "outcome": "UNKNOWN",
    }

    if res is not None:
        root, sub = res
        proof = root.emit(sub, fvar, fallback)
        row["proof_steps"] = len(proof)
        try:
            row["verified_internal"] = internal_verify(mm, target, proof) == "ok"
        except Exception as exc:
            row["verified_internal"] = False
            row["verify_error"] = repr(exc)
        row["outcome"] = "CANDIDATE_VERIFIED_INTERNAL" if row["verified_internal"] else "CANDIDATE_INTERNAL_REJECT"

        cert = os.path.join(HERE, stem + ".mm")
        with open(cert, "w", encoding="utf-8") as f:
            f.write("$( GBG+ Board-ATP 0.4: M=1, N=0, P0=board=ATP $)\n")
            f.write("$[ set.mm $]\n")
            f.write("chk $p %s $= %s $.\n" % (" ".join(stat), " ".join(proof)))
        row["certificate"] = cert

    with open(stem + "_result.json", "w", encoding="utf-8") as f:
        json.dump(row, f, indent=2, sort_keys=True)
    with open(stem + "_result.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)

    print("RESULT_JSON " + json.dumps(row, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
