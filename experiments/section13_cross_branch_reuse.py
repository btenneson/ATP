#!/usr/bin/env python3
"""
Section 13 pilot: measure cross-branch lemma reuse on real set.mm.

This implements the measurement requested by Section 13 of
"Predator 7.1 Documentation and Cross-Branch Reuse Rate Theory".

Protocol:
  * one parsed chronological set.mm prefix per target;
  * two independent backward-search frontiers, A for c and B for not-c;
  * alternate exactly one frontier expansion A,B,A,B,...;
  * substitutions/metavariables are branch-local (?A1,... versus ?B1,...);
  * when a completed proof subtree is ground with respect to search
    metavariables, deposit its conclusion in a shared lemma bank;
  * shared lemmas are nullary derived-rule candidates for either branch;
  * log lemma origin, cross-availability, and cross-use;
  * stop when either root target closes.

The search controller intentionally mirrors Predator_7.1's policy shape:
most-constrained open goal, all closers, capped openers, bounded depth/open
goals, and best-first priority by depth.  The extra proof-tree bookkeeping is
only to detect when an internal subgoal has become a closed lemma.

Important pilot limitation: this run measures proof-search reuse with
branch-local unification and verifier-backed source assertions, but it does
not yet replay every dynamically deposited derived lemma through an exported
standalone Metamath certificate.  Therefore the JSON labels the result
"pilot" rather than "certified-final".  No substitutions are shared across
branches.
"""
from __future__ import annotations

import argparse
import csv
import heapq
import itertools
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from metamath import load, MMError, classify
import setmm_grammar as G


# ---------------------------------------------------------------------------
# Unification: same two-namespace idea as Predator_7.1, but branch-qualified.
# ---------------------------------------------------------------------------
COUNTERS = {"A": itertools.count(1), "B": itertools.count(1), "X": itertools.count(1)}


def fresh(tc, branch):
    return G.Tree(None, tc, (), "?%s%d" % (branch, next(COUNTERS[branch])))


def is_meta(t):
    return t.var is not None and t.var.startswith("?")


def rename_apart(t, mapping, branch):
    if t.var is not None:
        if t.var not in mapping:
            mapping[t.var] = fresh(t.typecode, branch)
        return mapping[t.var]
    return G.Tree(t.label, t.typecode, [rename_apart(k, mapping, branch) for k in t.kids])


def walk(t, sub):
    while is_meta(t) and t.var in sub:
        t = sub[t.var]
    return t


def apply_sub(t, sub):
    t = walk(t, sub)
    if t.var is not None:
        return t
    return G.Tree(t.label, t.typecode, [apply_sub(k, sub) for k in t.kids])


def occurs(v, t, sub):
    t = walk(t, sub)
    if t.var is not None:
        return t.var == v
    return any(occurs(v, k, sub) for k in t.kids)


def unify(a, b, sub):
    a, b = walk(a, sub), walk(b, sub)
    if a is b:
        return sub
    if is_meta(a):
        if is_meta(b) and a.var == b.var:
            return sub
        if a.typecode != b.typecode or occurs(a.var, b, sub):
            return None
        s = dict(sub)
        s[a.var] = b
        return s
    if is_meta(b):
        return unify(b, a, sub)
    if a.var is not None or b.var is not None:
        return sub if (a.var == b.var and a.typecode == b.typecode) else None
    if a.label != b.label or len(a.kids) != len(b.kids):
        return None
    for x, y in zip(a.kids, b.kids):
        sub = unify(x, y, sub)
        if sub is None:
            return None
    return sub


def has_meta(t, sub):
    t = walk(t, sub)
    if t.var is not None:
        return is_meta(t)
    return any(has_meta(k, sub) for k in t.kids)


def tree_key(t, sub):
    return " ".join(apply_sub(t, sub).tokens())


def n_metas(t, sub, acc=None):
    if acc is None:
        acc = set()
    t = walk(t, sub)
    if t.var is not None:
        if is_meta(t):
            acc.add(t.var)
        return acc
    for k in t.kids:
        n_metas(k, sub, acc)
    return acc


def pick_goal(goals, sub):
    best, bi = None, 0
    for i, g in enumerate(goals):
        gg = walk(g.tree, sub)
        bare = 1 if (gg.var is not None and is_meta(gg)) else 0
        key = (bare, len(n_metas(gg, sub)), -gg.size())
        if best is None or key < best:
            best, bi = key, i
    return bi


# ---------------------------------------------------------------------------
# Base chronological index.
# ---------------------------------------------------------------------------
class IncIndex:
    def __init__(self, mm, by_tc):
        self.mm = mm
        self.by_tc = by_tc
        self.closers = defaultdict(list)
        self.openers = defaultdict(list)
        self.n = 0
        self.pos = 0

    def advance_to(self, cut):
        for lab in self.mm.order[self.pos:cut]:
            typ, data = self.mm.labels[lab]
            if typ not in ("$a", "$p"):
                continue
            concl = data[3]
            if not concl or concl[0] != "|-" or len(concl) < 2:
                continue
            try:
                t = G.parse(concl[1:], "wff", self.by_tc)
            except (RecursionError, MMError):
                t = None
            if t is None:
                continue
            self.n += 1
            head = None if t.var is not None else t.label
            (self.closers if not data[2] else self.openers)[head].append((lab, t, data))
        self.pos = cut

    def candidates(self, goal):
        def grab(d):
            if goal.var is not None:
                return [x for b in d.values() for x in b]
            return d.get(goal.label, []) + d.get(None, [])
        return grab(self.closers), grab(self.openers)


# ---------------------------------------------------------------------------
# Immutable-ish proof plan per search node.  Each open goal is identified by a
# path in a nested plan.  Updating a path copies only the plan structure.
# ---------------------------------------------------------------------------
@dataclass
class Plan:
    goal: Any
    source: str | None = None          # base label or shared lemma id
    children: list["Plan"] = field(default_factory=list)

    def copy(self):
        return Plan(self.goal, self.source, [c.copy() for c in self.children])

    def closed(self):
        return self.source is not None and all(c.closed() for c in self.children)

    def steps(self):
        if self.source is None:
            return 0
        return 1 + sum(c.steps() for c in self.children)


def plan_at(root, path):
    p = root
    for i in path:
        p = p.children[i]
    return p


def ancestor_paths(path):
    return [path[:i] for i in range(len(path), -1, -1)]


@dataclass
class GoalRef:
    tree: Any
    path: tuple[int, ...]


@dataclass
class SearchNode:
    goals: list[GoalRef]
    sub: dict
    plan: Plan
    depth: int


@dataclass
class Lemma:
    lid: str
    tree: Any
    origin: str
    proof_steps: int
    stage: int
    available_crossed: bool = False
    use_crossed: bool = False


class SharedBank:
    def __init__(self):
        self.lemmas: dict[str, Lemma] = {}
        self.by_head = defaultdict(list)
        self._n = 0

    def deposit(self, tree, origin, proof_steps, stage):
        key = " ".join(tree.tokens())
        if key in self.lemmas:
            return self.lemmas[key]
        self._n += 1
        lem = Lemma("L%06d" % self._n, tree, origin, proof_steps, stage)
        self.lemmas[key] = lem
        head = None if tree.var is not None else tree.label
        self.by_head[head].append(lem)
        return lem

    def candidates(self, goal):
        if goal.var is not None:
            return list(self.lemmas.values())
        return self.by_head.get(goal.label, []) + self.by_head.get(None, [])


class Branch:
    def __init__(self, name, goal, index, bank, opener_cap, max_depth, max_open):
        self.name = name
        self.index = index
        self.bank = bank
        self.opener_cap = opener_cap
        self.max_depth = max_depth
        self.max_open = max_open
        root = Plan(goal)
        self.frontier = [(0.0, 0, SearchNode([GoalRef(goal, ())], {}, root, 0))]
        self.tie = 0
        self.expansions = 0
        self.seen = set()
        self.solved = False
        self.closed_ground = 0
        self.deposited = 0
        self.cross_uses = 0

    def _base_has_direct_closer(self, tree):
        closers, _ = self.index.candidates(tree)
        for _lab, ct, _data in closers:
            m = {}
            c2 = rename_apart(ct, m, "X")
            if unify(c2, tree, {}) is not None:
                return True
        return False

    def _harvest_closed(self, plan, changed_path, sub, stage):
        # A subtree is newly useful only if closed, ground w.r.t. search metas,
        # and not just a one-step citation already available from the base.
        for ap in ancestor_paths(changed_path):
            p = plan_at(plan, ap)
            if not p.closed():
                continue
            inst = apply_sub(p.goal, sub)
            if has_meta(inst, sub):
                continue
            self.closed_ground += 1
            steps = p.steps()
            # Deposit all closed ground lemmas for the Section-13 denominator.
            before = len(self.bank.lemmas)
            lem = self.bank.deposit(inst, self.name, steps, stage)
            if len(self.bank.lemmas) > before:
                self.deposited += 1
            # ancestor closure may imply higher ancestors are also closed;
            # continue so each distinct closed result can enter Lambda.

    def expand_one(self, stage):
        if self.solved or not self.frontier:
            return False
        _, _, node = heapq.heappop(self.frontier)
        self.expansions += 1
        if not node.goals:
            self.solved = True
            return True
        if node.depth >= self.max_depth or len(node.goals) > self.max_open:
            return False

        gi = pick_goal(node.goals, node.sub)
        gr = node.goals[gi]
        rest = node.goals[:gi] + node.goals[gi + 1:]
        gt = apply_sub(gr.tree, node.sub)
        key = (node.depth, tree_key(gt, node.sub), tuple(sorted(tree_key(g.tree, node.sub) for g in rest)))
        if key in self.seen:
            return False
        self.seen.add(key)

        # Shared lemma availability is measured before choosing/using one.
        shared_matches = []
        for lem in self.bank.candidates(gt):
            if lem.origin == self.name:
                continue
            m = {}
            c2 = rename_apart(lem.tree, m, self.name)
            s2 = unify(c2, gt, node.sub)
            if s2 is not None:
                lem.available_crossed = True
                shared_matches.append((lem, s2))

        # A compiled shared lemma is tried first iff its stored proof took >1
        # logical step.  Otherwise an ordinary base closer is equally cheap.
        for lem, s2 in shared_matches:
            if lem.proof_steps <= 1:
                continue
            plan = node.plan.copy()
            leaf = plan_at(plan, gr.path)
            leaf.source = "shared:" + lem.lid
            leaf.children = []
            lem.use_crossed = True
            self.cross_uses += 1
            self._harvest_closed(plan, gr.path, s2, stage)
            self.tie += 1
            nn = SearchNode(rest, s2, plan, node.depth + 1)
            if not rest:
                self.solved = True
                return True
            heapq.heappush(self.frontier, (nn.depth, self.tie, nn))

        closers, openers = self.index.candidates(gt)
        pick = list(closers) + list(openers[: self.opener_cap])
        for lab, ct, data in pick:
            m = {}
            c2 = rename_apart(ct, m, self.name)
            s2 = unify(c2, gt, node.sub)
            if s2 is None:
                continue
            _, f_hyps, e_hyps, _ = data
            for _fl, tc, var in f_hyps:
                m.setdefault(var, fresh(tc, self.name))
            newrefs = []
            childplans = []
            ok = True
            for hj, (_el, stat) in enumerate(e_hyps):
                try:
                    ht = G.parse(stat[1:], "wff", self.index.by_tc)
                except (RecursionError, MMError):
                    ht = None
                if ht is None:
                    ok = False
                    break
                htree = rename_apart(ht, m, self.name)
                childplans.append(Plan(htree))
                newrefs.append(GoalRef(htree, gr.path + (hj,)))
            if not ok:
                continue
            plan = node.plan.copy()
            leaf = plan_at(plan, gr.path)
            leaf.source = lab
            leaf.children = childplans
            self._harvest_closed(plan, gr.path, s2, stage)
            self.tie += 1
            nn = SearchNode(newrefs + rest, s2, plan, node.depth + 1)
            if not nn.goals:
                self.solved = True
                return True
            heapq.heappush(self.frontier, (nn.depth, self.tie, nn))
        return False


def direct_one_step(index, goal):
    closers, _ = index.candidates(goal)
    for _lab, ct, _data in closers:
        m = {}
        c2 = rename_apart(ct, m, "X")
        if unify(c2, goal, {}) is not None:
            return True
    return False


def logic_depth(mm, kind, lab):
    try:
        proof = mm.decompress(lab, mm.proofs[lab])
    except Exception:
        return None
    if "?" in proof:
        return None
    return sum(1 for x in proof if kind.get(x) == "logic")


def select_negative_targets(mm, by_tc, kind, scan, min_logic, max_logic):
    out = []
    thms = [l for l in mm.order if mm.labels[l][0] == "$p"]
    if scan:
        thms = thms[:scan]
    for lab in thms:
        stat = mm.labels[lab][1][3]
        if len(stat) < 3 or stat[0] != "|-" or stat[1] != "-.":
            continue
        d = logic_depth(mm, kind, lab)
        if d is None or not (min_logic <= d <= max_logic):
            continue
        try:
            neg = G.parse(stat[1:], "wff", by_tc)
            pos = G.parse(stat[2:], "wff", by_tc)
        except (MMError, RecursionError):
            continue
        if neg is not None and pos is not None:
            out.append((mm.order.index(lab), lab, d, pos, neg))
    out.sort()
    return out


def run(args):
    t0 = time.time()
    mm = load(args.db)
    by_tc = G.build_grammar(mm)
    kind = classify(mm)
    candidates = select_negative_targets(mm, by_tc, kind, args.scan, args.min_logic, args.max_logic)
    print("negative candidates in scan:", len(candidates))

    idx = IncIndex(mm, by_tc)
    rows = []
    measured = 0
    for cut, lab, human_logic, pos, neg in candidates:
        if measured >= args.targets:
            break
        idx.advance_to(cut)
        # Section 13 requires removing duplicate/lookup contamination.
        if direct_one_step(idx, neg) or direct_one_step(idx, pos):
            continue

        measured += 1
        bank = SharedBank()
        A = Branch("A", pos, idx, bank, args.opener_cap, args.max_depth, args.max_open)
        B = Branch("B", neg, idx, bank, args.opener_cap, args.max_depth, args.max_open)
        stage = 0
        winner = None
        while stage < args.stage_budget and (A.frontier or B.frontier):
            stage += 1
            br = A if stage % 2 == 1 else B
            if not br.frontier:
                br = B if br is A else A
                if not br.frontier:
                    break
            if br.expand_one(stage):
                winner = br.name
                break

        all_lemmas = list(bank.lemmas.values())
        nontrivial = [x for x in all_lemmas if x.proof_steps > 1]
        av = [x for x in all_lemmas if x.available_crossed]
        us = [x for x in all_lemmas if x.use_crossed]
        av_nt = [x for x in nontrivial if x.available_crossed]
        us_nt = [x for x in nontrivial if x.use_crossed]
        row = dict(
            label=lab,
            human_logic_steps=human_logic,
            base_assertions=idx.n,
            stages=stage,
            winner=winner or "none",
            A_expansions=A.expansions,
            B_expansions=B.expansions,
            lambda_size=len(all_lemmas),
            lambda_nontrivial=len(nontrivial),
            available_crossed=len(av),
            use_crossed=len(us),
            kappa_av=(len(av) / len(all_lemmas)) if all_lemmas else 0.0,
            kappa_us=(len(us) / len(all_lemmas)) if all_lemmas else 0.0,
            kappa_av_nontrivial=(len(av_nt) / len(nontrivial)) if nontrivial else 0.0,
            kappa_us_nontrivial=(len(us_nt) / len(nontrivial)) if nontrivial else 0.0,
        )
        rows.append(row)
        print(json.dumps(row, sort_keys=True))

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "section13_kappa_rows.csv")
    if rows:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    total_L = sum(r["lambda_size"] for r in rows)
    total_av = sum(r["available_crossed"] for r in rows)
    total_us = sum(r["use_crossed"] for r in rows)
    total_nt = sum(r["lambda_nontrivial"] for r in rows)
    total_av_nt = sum(round(r["kappa_av_nontrivial"] * r["lambda_nontrivial"]) for r in rows)
    total_us_nt = sum(round(r["kappa_us_nontrivial"] * r["lambda_nontrivial"]) for r in rows)
    summary = dict(
        status="pilot",
        protocol="Section 13 alternating two-branch backward search with branch-local substitutions",
        database=args.db,
        targets_requested=args.targets,
        targets_measured=len(rows),
        settled=sum(1 for r in rows if r["winner"] != "none"),
        total_shared_lemmas=total_L,
        total_available_crossed=total_av,
        total_use_crossed=total_us,
        pooled_kappa_av=(total_av / total_L) if total_L else 0.0,
        pooled_kappa_us=(total_us / total_L) if total_L else 0.0,
        total_nontrivial_shared_lemmas=total_nt,
        pooled_kappa_av_nontrivial=(total_av_nt / total_nt) if total_nt else 0.0,
        pooled_kappa_us_nontrivial=(total_us_nt / total_nt) if total_nt else 0.0,
        search=dict(stage_budget=args.stage_budget, max_depth=args.max_depth,
                    max_open=args.max_open, opener_cap=args.opener_cap,
                    scan=args.scan, min_logic=args.min_logic, max_logic=args.max_logic),
        limitations=[
            "dynamic derived lemmas are not yet exported and replayed as standalone Metamath certificates",
            "search controller is a Section-13 pilot modeled on Predator_7.1, not the historical predator71.py binary",
            "only negative theorems surviving a direct-one-step closer filter are measured",
        ],
        elapsed_seconds=round(time.time() - t0, 3),
        rows=rows,
    )
    with open(os.path.join(args.out, "section13_kappa_results.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print("SUMMARY", json.dumps({k: summary[k] for k in ["targets_measured","settled","total_shared_lemmas","total_use_crossed","pooled_kappa_us","pooled_kappa_us_nontrivial","elapsed_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="set.mm")
    ap.add_argument("--out", default="experiments/section13_results")
    ap.add_argument("--targets", type=int, default=8)
    ap.add_argument("--scan", type=int, default=12000)
    ap.add_argument("--min-logic", type=int, default=2)
    ap.add_argument("--max-logic", type=int, default=5)
    ap.add_argument("--stage-budget", type=int, default=6000)
    ap.add_argument("--max-depth", type=int, default=7)
    ap.add_argument("--max-open", type=int, default=6)
    ap.add_argument("--opener-cap", type=int, default=24)
    run(ap.parse_args())
