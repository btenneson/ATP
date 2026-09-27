#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "Predator_8.001_FROZEN.py")
SETMM = os.path.join(HERE, "set.mm")

TARGET = "prcom"
BUDGET = 30000
SEED = 2301
CREATIVITY = 0.55
MAX_DEPTH = 12
MAX_OPEN = 8
OPENER_CAP = 48

spec = importlib.util.spec_from_file_location("predator8_frozen", ENGINE)
p8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p8)


class RankStats:
    def __init__(self):
        self.calls = 0
        self.items = 0
        self.unify_ok = 0
        self.unify_fail = 0


def make_board_ranker(by_tc, stats):
    """
    GBG+ M=1 interpretation:
      P0 = board = ATP.

    The board sees only current-state information:
      * current open goal,
      * candidate conclusion,
      * declared essential hypotheses,
      * residual obligation structure after current unification.

    It does not read TARGET's stored proof and does not use future labels.
    """
    meta_cache = {}

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
        rec = (len(e_hyps), htrees, set(ct.tokens()))
        meta_cache[lab] = rec
        return rec

    def rank(goal, items):
        stats.calls += 1
        stats.items += len(items)
        gset = set(goal.tokens())
        scores = []

        for lab, ct, data in items:
            ne, htrees, cset = metadata(lab, ct, data)

            mapping = {}
            c2 = p8.rename_apart(ct, mapping)
            sub = p8.unify(c2, goal, {})
            if sub is None:
                stats.unify_fail += 1
                scores.append(-9.0)
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
                hset = set(hs.tokens())
                hyp_overlap_sum += len(hset & gset) / max(1, len(hset | gset))
                hyp_count += 1

            mean_hyp_overlap = hyp_overlap_sum / max(1, hyp_count)

            # Transparent, non-learned target/obligation information score.
            score = (
                2.20 * direct
                + 0.80 * conclusion_overlap
                + 0.28 * grounded
                + 0.18 * mean_hyp_overlap
                - 0.28 * ne
                - 0.012 * residual_size
                - 0.10 * residual_metas
            )
            scores.append(score)

        return scores

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
    print("=" * 78)
    print("GBG+ BOARD-ONLY PRCOM 001")
    print("M=1, N=0, P0 = board = ATP")
    print("=" * 78)

    print("Loading frozen set.mm ...", flush=True)
    mm = p8.load(SETMM)
    by_tc = p8.G.build_grammar(mm)

    if TARGET not in mm.labels:
        raise RuntimeError("missing target " + TARGET)

    stat = mm.labels[TARGET][1][3]
    cut = mm.order.index(TARGET)

    # Strict pre-target environment; target proof is never read.
    print("Indexing assertions strictly before target ...", flush=True)
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
        "Running single-player board ATP: "
        f"budget={BUDGET} seed={SEED} max_depth={MAX_DEPTH} "
        f"max_open={MAX_OPEN} creativity={CREATIVITY} opener_cap={OPENER_CAP}",
        flush=True,
    )

    t0 = time.perf_counter()
    res, exp, winner = p8.prove_population(
        goal,
        idx,
        BUDGET,
        MAX_DEPTH,
        agents=1,
        creativity=CREATIVITY,
        seed=SEED,
        rank=rank,
        say=print,
        progress=250,
        max_open=MAX_OPEN,
        opener_cap=OPENER_CAP,
    )
    dt = time.perf_counter() - t0

    row = {
        "target": TARGET,
        "architecture": "GBG+ M=1; N=0; P0=board=ATP",
        "engine": "Predator_8.001_FROZEN proof semantics",
        "scheduler": "online target/obligation board ranker",
        "budget": BUDGET,
        "seed": SEED,
        "max_depth": MAX_DEPTH,
        "max_open": MAX_OPEN,
        "creativity": CREATIVITY,
        "opener_cap": OPENER_CAP,
        "expansions": exp,
        "search_seconds": dt,
        "verified_internal": False,
        "proof_steps": None,
        "winner": winner,
        "rank_calls": stats.calls,
        "rank_items": stats.items,
        "rank_unify_ok": stats.unify_ok,
        "rank_unify_fail": stats.unify_fail,
        "outcome": "UNKNOWN",
    }

    if res is not None:
        root, sub = res
        proof = root.emit(sub, fvar, fallback)
        row["proof_steps"] = len(proof)
        row["verified_internal"] = internal_verify(mm, TARGET, proof) == "ok"
        row["outcome"] = "CANDIDATE_VERIFIED_INTERNAL" if row["verified_internal"] else "CANDIDATE_INTERNAL_REJECT"

        cert = os.path.join(HERE, "prcom_gbg_board_001.mm")
        with open(cert, "w", encoding="utf-8") as f:
            f.write("$( GBG+ board-only prcom experiment: M=1, N=0, P0=board=ATP $)\n")
            f.write("$[ set.mm $]\n")
            f.write("chk $p %s $= %s $.\n" % (" ".join(stat), " ".join(proof)))
        row["certificate"] = cert

    with open("gbg_board_prcom_001_result.json", "w", encoding="utf-8") as f:
        json.dump(row, f, indent=2, sort_keys=True)

    with open("gbg_board_prcom_001_result.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)

    print("RESULT_JSON " + json.dumps(row, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
