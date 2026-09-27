#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Predator_8.001_FROZEN.py")

spec = importlib.util.spec_from_file_location("predator8_frozen", ENGINE)
p8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p8)


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
    Board-ATP 0.2.

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
    stem = args.out_prefix or f"{target}_gbg_board02"

    print("=" * 78)
    print("GBG+ BOARD-ATP 0.2")
    print("M=1, N=0, P0 = board = ATP")
    print("=" * 78)

    print("Loading frozen set.mm ...", flush=True)
    mm = p8.load(args.setmm)
    by_tc = p8.G.build_grammar(mm)

    if target not in mm.labels:
        raise RuntimeError("missing target " + target)

    stat = mm.labels[target][1][3]
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
        "Running Board-ATP 0.2: "
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
        "version": "Board-ATP 0.2",
        "engine": "Predator_8.001_FROZEN proof semantics",
        "scheduler": "cached legality-first target/obligation board ranker",
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
        "outcome": "UNKNOWN",
    }

    if res is not None:
        root, sub = res
        proof = root.emit(sub, fvar, fallback)
        row["proof_steps"] = len(proof)
        row["verified_internal"] = internal_verify(mm, target, proof) == "ok"
        row["outcome"] = "CANDIDATE_VERIFIED_INTERNAL" if row["verified_internal"] else "CANDIDATE_INTERNAL_REJECT"

        cert = os.path.join(HERE, stem + ".mm")
        with open(cert, "w", encoding="utf-8") as f:
            f.write("$( GBG+ Board-ATP 0.2: M=1, N=0, P0=board=ATP $)\n")
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
