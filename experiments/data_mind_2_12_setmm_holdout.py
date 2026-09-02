#!/usr/bin/env python3
"""DATA MIND 2.12 set.mm 95/5 held-out pilot.

Protocol:
- parse the pinned set.mm corpus with the verified metamath.py reader;
- take complete $p theorems as the benchmark population;
- choose the held-out 5% only from citation leaves, so no training proof can
  contain a held-out theorem label;
- randomly select one manageable theorem from that already-frozen holdout;
- train final-step/premise priors on every theorem in the other 95%;
- redact every held-out proof in the searcher's in-memory database;
- search backward in Metamath's actual substitution calculus;
- accept settlement only after a fresh metamath.py subprocess verifies the
  generated uncompressed certificate.

The hidden target proof is used only before redaction to stratify the random
target by a preregistered proof-length window. It is never supplied to the
learner or search.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Sequence

import metamath as mmcore

ARCH = "DATA-MIND 2.12-setmm-95-heldout-001"
DEFAULT_SEED = 271828
DEFAULT_HOLDOUT = 0.05
DEFAULT_SECONDS = 1800
DEFAULT_SOURCE_COMMIT = "f85a8edbb6df20dd5a64a9c159fa22944a3e54de"


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Breadcrumbs:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seq = 0
        self.prev = "0" * 64
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self.seq = max(self.seq, int(row["seq"]) + 1)
                self.prev = row["hash"]

    def add(self, kind: str, payload: Mapping[str, Any]) -> str:
        body = {
            "seq": self.seq,
            "time_unix": time.time(),
            "kind": kind,
            "architecture": ARCH,
            "prev_hash": self.prev,
            "payload": dict(payload),
        }
        digest = sha256_bytes(stable_json(body).encode("utf-8"))
        row = {**body, "hash": digest}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.prev = digest
        self.seq += 1
        return digest

    def verify(self) -> bool:
        prev = "0" * 64
        expect = 0
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("seq") != expect or row.get("prev_hash") != prev:
                return False
            claimed = row["hash"]
            body = {k: v for k, v in row.items() if k != "hash"}
            if sha256_bytes(stable_json(body).encode("utf-8")) != claimed:
                return False
            prev = claimed
            expect += 1
        return True


def raw_proof_complete(proof: Sequence[str]) -> bool:
    return bool(proof) and not any("?" in token for token in proof)


def assertion_statement(mm: mmcore.MM, label: str) -> tuple[str, ...]:
    typ, data = mm.labels[label]
    if typ in ("$a", "$p"):
        return tuple(data[3])
    return tuple(data)


def decompressed(mm: mmcore.MM, label: str) -> list[str]:
    return list(mm.decompress(label, mm.proofs[label]))


def build_split(
    mm: mmcore.MM,
    *,
    seed: int,
    holdout_fraction: float,
    min_target_proof_steps: int,
    max_target_proof_steps: int,
    max_target_statement_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    complete = [
        lab for lab in mm.order
        if mm.labels.get(lab, (None,))[0] == "$p"
        and raw_proof_complete(mm.proofs.get(lab, ()))
    ]
    if not complete:
        raise RuntimeError("no complete theorems found")

    dec: dict[str, list[str]] = {}
    cited_theorems: set[str] = set()
    proof_lengths: dict[str, int] = {}
    for lab in complete:
        steps = decompressed(mm, lab)
        dec[lab] = steps
        proof_lengths[lab] = len(steps)
        for step in steps:
            if mm.labels.get(step, (None,))[0] == "$p":
                cited_theorems.add(step)

    leaves = [lab for lab in complete if lab not in cited_theorems]
    holdout_n = max(1, int(round(len(complete) * holdout_fraction)))
    if len(leaves) < holdout_n:
        raise RuntimeError(
            f"dependency-safe leaf pool too small: {len(leaves)} leaves for "
            f"{holdout_n} held-out theorems"
        )

    rng = random.Random(seed)
    shuffled = list(leaves)
    rng.shuffle(shuffled)
    holdout = shuffled[:holdout_n]
    holdout_set = set(holdout)
    training = [lab for lab in complete if lab not in holdout_set]
    order_index = {lab: i for i, lab in enumerate(mm.order)}

    def target_ok(lab: str, lo: int, hi: int, stat_cap: int) -> bool:
        _dvs, _f, e, stat = mm.labels[lab][1]
        return (
            not e
            and lo <= proof_lengths[lab] <= hi
            and len(stat) <= stat_cap
            and order_index[lab] > 500
        )

    pool = [
        lab for lab in holdout
        if target_ok(lab, min_target_proof_steps, max_target_proof_steps,
                     max_target_statement_tokens)
    ]
    widened = False
    if not pool:
        widened = True
        pool = [
            lab for lab in holdout
            if target_ok(lab, 2, max(80, max_target_proof_steps),
                         max(100, max_target_statement_tokens))
        ]
    if not pool:
        raise RuntimeError("held-out set contains no target satisfying pilot strata")
    target = rng.choice(pool)

    leaking: list[tuple[str, str]] = []
    for lab in training:
        for step in dec[lab]:
            if step in holdout_set:
                leaking.append((lab, step))
                if len(leaking) >= 10:
                    break
        if leaking:
            break
    if leaking:
        raise RuntimeError(f"holdout leakage audit failed: {leaking[:10]}")

    manifest = {
        "architecture": ARCH,
        "seed": seed,
        "holdout_fraction_requested": holdout_fraction,
        "complete_theorem_count": len(complete),
        "training_count": len(training),
        "holdout_count": len(holdout),
        "actual_training_fraction": len(training) / len(complete),
        "leaf_count": len(leaves),
        "holdout_all_reverse_citation_leaves": True,
        "training_proof_mentions_holdout": False,
        "target": target,
        "target_in_training": target in set(training),
        "target_proof_steps_hidden": proof_lengths[target],
        "target_statement_tokens": len(assertion_statement(mm, target)),
        "target_stratum_widened": widened,
    }
    return manifest, {
        "complete": complete,
        "training": training,
        "holdout": holdout,
        "target": target,
        "target_original_steps": dec[target],
        "decompressed": dec,
    }


def train_model(
    mm: mmcore.MM,
    training: Sequence[str],
    dec: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    final_counts: Counter[str] = Counter()
    premise_counts: Counter[str] = Counter()
    token_final: dict[str, Counter[str]] = defaultdict(Counter)
    trained = 0
    step_total = 0
    for lab in training:
        steps = list(dec[lab])
        if not steps:
            continue
        assertion_steps = [
            s for s in steps if mm.labels.get(s, (None,))[0] in ("$a", "$p")
        ]
        if not assertion_steps:
            continue
        final = assertion_steps[-1]
        final_counts[final] += 1
        premise_counts.update(assertion_steps)
        stat = assertion_statement(mm, lab)
        for tok in set(stat):
            if tok in mm.constants:
                token_final[tok][final] += 1
        trained += 1
        step_total += len(steps)

    return {
        "trained_theorems": trained,
        "training_steps_processed": step_total,
        "final_counts": final_counts,
        "premise_counts": premise_counts,
        "token_final": token_final,
    }


def model_summary(model: Mapping[str, Any]) -> dict[str, Any]:
    fc: Counter[str] = model["final_counts"]
    pc: Counter[str] = model["premise_counts"]
    tf: Mapping[str, Counter[str]] = model["token_final"]
    return {
        "trained_theorems": model["trained_theorems"],
        "training_steps_processed": model["training_steps_processed"],
        "distinct_final_assertions": len(fc),
        "distinct_used_assertions": len(pc),
        "token_condition_count": len(tf),
        "top_final_assertions": fc.most_common(25),
        "top_used_assertions": pc.most_common(25),
    }


def is_subsequence(need: Sequence[str], have: Sequence[str]) -> bool:
    pos = 0
    for token in have:
        if pos < len(need) and need[pos] == token:
            pos += 1
    return pos == len(need)


def match_substitution(
    pattern: Sequence[str],
    goal: Sequence[str],
    variables: set[str],
    *,
    max_solutions: int = 6,
) -> list[dict[str, tuple[str, ...]]]:
    out: list[dict[str, tuple[str, ...]]] = []

    def rec(i: int, j: int, subst: dict[str, tuple[str, ...]]) -> None:
        if len(out) >= max_solutions:
            return
        if i == len(pattern):
            if j == len(goal):
                out.append(dict(subst))
            return
        if j > len(goal):
            return
        tok = pattern[i]
        if tok not in variables:
            if j < len(goal) and goal[j] == tok:
                rec(i + 1, j + 1, subst)
            return
        bound = subst.get(tok)
        if bound is not None:
            n = len(bound)
            if n and tuple(goal[j:j+n]) == bound:
                rec(i + 1, j + n, subst)
            return

        remaining_items = len(pattern) - i - 1
        max_len = len(goal) - j - remaining_items
        if max_len < 1:
            return
        next_tok = pattern[i + 1] if i + 1 < len(pattern) else None
        if next_tok is not None and next_tok not in variables:
            lengths: Iterable[int] = [
                n for n in range(1, max_len + 1)
                if j + n < len(goal) and goal[j+n] == next_tok
            ]
        else:
            lengths = range(1, max_len + 1)
        for n in lengths:
            subst[tok] = tuple(goal[j:j+n])
            rec(i + 1, j + n, subst)
            subst.pop(tok, None)
            if len(out) >= max_solutions:
                return

    rec(0, 0, {})
    return out


def apply_subst_tuple(stat: Sequence[str], subst: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    out: list[str] = []
    for tok in stat:
        val = subst.get(tok)
        if val is None:
            out.append(tok)
        else:
            out.extend(val)
    return tuple(out)


def dv_valid(
    mm: mmcore.MM,
    assertion_dvs: Iterable[tuple[str, str]],
    subst: Mapping[str, Sequence[str]],
    target_scope_dvs: set[tuple[str, str]],
) -> bool:
    for x, y in assertion_dvs:
        sx = [t for t in subst.get(x, ()) if t in mm.variables]
        sy = [t for t in subst.get(y, ()) if t in mm.variables]
        for a, b in itertools.product(sx, sy):
            if a == b or (min(a, b), max(a, b)) not in target_scope_dvs:
                return False
    return True


def rss_kib() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


class SearchTimeout(Exception):
    pass


class BackwardSearcher:
    def __init__(
        self,
        mm: mmcore.MM,
        *,
        target: str,
        holdout: set[str],
        model: Mapping[str, Any],
        deadline: float,
        breadcrumbs: Breadcrumbs,
        bank_path: Path,
    ):
        self.mm = mm
        self.target = target
        self.holdout = holdout
        self.model = model
        self.deadline = deadline
        self.breadcrumbs = breadcrumbs
        self.bank_path = bank_path
        self.order_index = {lab: i for i, lab in enumerate(mm.order)}
        self.target_index = self.order_index[target]
        self.target_dvs, target_f, target_e, self.target_statement = mm.labels[target][1]
        self.target_scope_dvs = set(mm.scope_dvs.get(target, self.target_dvs))
        self.local_hypotheses: dict[tuple[str, ...], str] = {}
        for lab, tc, var in target_f:
            self.local_hypotheses[(tc, var)] = lab
        for lab, stat in target_e:
            self.local_hypotheses[tuple(stat)] = lab

        self.by_type: dict[str, list[str]] = defaultdict(list)
        self.const_sig: dict[str, tuple[str, ...]] = {}
        for lab in mm.order[:self.target_index]:
            typ, data = mm.labels[lab]
            if typ not in ("$a", "$p"):
                continue
            if typ == "$p" and lab in holdout:
                continue
            _dvs, _f, _e, concl = data
            if not concl:
                continue
            self.by_type[concl[0]].append(lab)
            self.const_sig[lab] = tuple(t for t in concl if t in mm.constants)

        self.expansions = 0
        self.match_attempts = 0
        self.memo_fail: set[tuple[tuple[str, ...], int, str, int]] = set()
        self.candidate_cache: dict[tuple[tuple[str, ...], str], list[str]] = {}
        self.last_heartbeat = time.monotonic()
        self.peak_rss_kib = rss_kib() or 0

    def _check(self, strategy: str, depth: int, goal: Sequence[str]) -> None:
        now = time.monotonic()
        if now >= self.deadline:
            raise SearchTimeout
        r = rss_kib()
        if r:
            self.peak_rss_kib = max(self.peak_rss_kib, r)
        if now - self.last_heartbeat >= 5.0:
            self.breadcrumbs.add("SEARCH_HEARTBEAT", {
                "strategy": strategy,
                "expansions": self.expansions,
                "match_attempts": self.match_attempts,
                "depth_remaining": depth,
                "goal_tokens": len(goal),
                "rss_kib": r,
            })
            self.last_heartbeat = now

    def _score(self, lab: str, goal: tuple[str, ...], strategy: str) -> float:
        final_counts: Counter[str] = self.model["final_counts"]
        premise_counts: Counter[str] = self.model["premise_counts"]
        token_final: Mapping[str, Counter[str]] = self.model["token_final"]
        _typ, data = self.mm.labels[lab]
        _dvs, f, e, concl = data
        gconst = [t for t in goal if t in self.mm.constants]
        token_support = sum(math.log1p(token_final.get(t, {}).get(lab, 0)) for t in set(gconst))
        global_final = math.log1p(final_counts.get(lab, 0))
        global_use = math.log1p(premise_counts.get(lab, 0))
        recency = self.order_index[lab] / max(1, self.target_index)
        simplicity = -0.18 * (len(f) + 2 * len(e))
        literal = 5.0 if tuple(concl) == goal else 0.0
        if strategy == "learned":
            return literal + 3.0 * token_support + 1.5 * global_final + 0.4 * global_use + 0.5 * recency + simplicity
        if strategy == "frequency":
            return literal + 2.0 * global_final + global_use + 0.2 * token_support + simplicity
        if strategy == "recency":
            return literal + 3.0 * recency + 0.5 * token_support + simplicity
        if strategy == "simple":
            return literal + token_support + 2.0 * simplicity + 0.2 * global_use
        return literal + token_support + global_final + global_use + recency + simplicity

    def ranked_candidates(self, goal: tuple[str, ...], strategy: str, top_k: int) -> list[str]:
        key = (goal, strategy)
        cached = self.candidate_cache.get(key)
        if cached is None:
            if not goal:
                return []
            labels = self.by_type.get(goal[0], ())
            rows: list[tuple[float, str]] = []
            for lab in labels:
                sig = self.const_sig[lab]
                if sig and not is_subsequence(sig, goal):
                    continue
                rows.append((self._score(lab, goal, strategy), lab))
            rows.sort(key=lambda x: (-x[0], -self.order_index[x[1]], x[1]))
            cached = [lab for _, lab in rows]
            self.candidate_cache[key] = cached
        return cached[:top_k]

    def prove(
        self,
        goal: tuple[str, ...],
        *,
        depth: int,
        strategy: str,
        top_k: int,
        trail: set[tuple[str, ...]],
    ) -> list[str] | None:
        self._check(strategy, depth, goal)
        hyp = self.local_hypotheses.get(goal)
        if hyp is not None:
            return [hyp]
        if depth <= 0 or goal in trail:
            return None
        mkey = (goal, depth, strategy, top_k)
        if mkey in self.memo_fail:
            return None

        trail2 = set(trail)
        trail2.add(goal)
        for lab in self.ranked_candidates(goal, strategy, top_k):
            self._check(strategy, depth, goal)
            self.match_attempts += 1
            _typ, data = self.mm.labels[lab]
            s_dvs, s_f, s_e, s_concl = data
            for subst in match_substitution(s_concl, goal, self.mm.variables):
                if any(var not in subst for _, _, var in s_f):
                    continue
                if not dv_valid(self.mm, s_dvs, subst, self.target_scope_dvs):
                    continue
                subgoals: list[tuple[str, ...]] = []
                for _hlab, tc, var in s_f:
                    subgoals.append((tc, *subst[var]))
                for _hlab, estat in s_e:
                    subgoals.append(apply_subst_tuple(estat, subst))

                pieces: list[str] = []
                ok = True
                for sg in subgoals:
                    part = self.prove(
                        sg, depth=depth-1, strategy=strategy,
                        top_k=top_k, trail=trail2,
                    )
                    if part is None:
                        ok = False
                        break
                    pieces.extend(part)
                if ok:
                    self.expansions += 1
                    return [*pieces, lab]
            self.expansions += 1

        self.memo_fail.add(mkey)
        return None

    def run_round(self, *, strategy: str, depth: int, top_k: int, seconds: float) -> dict[str, Any]:
        started = time.monotonic()
        old_deadline = self.deadline
        self.deadline = min(old_deadline, started + seconds)
        before_exp = self.expansions
        before_match = self.match_attempts
        self.memo_fail.clear()
        self.breadcrumbs.add("STRATEGY_START", {
            "strategy": strategy, "depth": depth, "top_k": top_k,
            "slice_seconds": seconds,
        })
        proof = None
        timed_out = False
        try:
            proof = self.prove(
                tuple(self.target_statement), depth=depth,
                strategy=strategy, top_k=top_k, trail=set(),
            )
        except SearchTimeout:
            timed_out = True
        finally:
            self.deadline = old_deadline
        elapsed = time.monotonic() - started
        result = {
            "strategy": strategy,
            "depth": depth,
            "top_k": top_k,
            "elapsed_seconds": elapsed,
            "timed_out": timed_out,
            "proof_found": proof is not None,
            "candidate_proof_steps": len(proof) if proof else None,
            "expansions": self.expansions - before_exp,
            "match_attempts": self.match_attempts - before_match,
            "peak_rss_kib": self.peak_rss_kib,
        }
        self.breadcrumbs.add("STRATEGY_FINISH", result)
        if proof is None:
            self.bank_path.parent.mkdir(parents=True, exist_ok=True)
            with self.bank_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "kind": "failure_trajectory",
                    "target": self.target,
                    **result,
                }, sort_keys=True) + "\n")
        result["proof"] = proof
        return result


def write_candidate_database(original: Path, target: str, proof: Sequence[str], out: Path) -> None:
    text = original.read_text(encoding="utf-8", errors="replace")
    esc = re.escape(target)
    pat = re.compile(r"(?ms)(^|\s)(" + esc + r"\s+\$p\b.*?\$=\s*)(.*?)(\s*\$\.)")
    match = pat.search(text)
    if not match:
        raise RuntimeError(f"could not locate target proof text for {target}")
    replacement = match.group(1) + match.group(2) + " ".join(proof) + match.group(4)
    new_text = text[:match.start()] + replacement + text[match.end():]
    out.write_text(new_text, encoding="utf-8")


def fresh_verify(repo_root: Path, db: Path, target: str, log: Path) -> tuple[bool, int]:
    cp = subprocess.run(
        [sys.executable, str(repo_root / "metamath.py"), "verify", str(db),
         "--only", target, "--progress", "1"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    log.write_text(cp.stdout, encoding="utf-8")
    return cp.returncode == 0, cp.returncode


def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    crumbs = Breadcrumbs(out / "breadcrumbs.jsonl")
    repo_root = Path(__file__).resolve().parents[1]
    source = Path(args.setmm)

    crumbs.add("RUN_STARTED", {
        "source_commit": args.source_commit,
        "source_sha256": sha256_file(source),
        "seed": args.seed,
        "holdout_fraction": args.holdout_fraction,
        "budget_seconds": args.seconds,
    })

    mm = mmcore.load(str(source), say=lambda s: print(s, flush=True))
    manifest, split = build_split(
        mm,
        seed=args.seed,
        holdout_fraction=args.holdout_fraction,
        min_target_proof_steps=args.min_target_proof_steps,
        max_target_proof_steps=args.max_target_proof_steps,
        max_target_statement_tokens=args.max_target_statement_tokens,
    )
    manifest.update({
        "source_commit": args.source_commit,
        "source_sha256": sha256_file(source),
    })
    (out / "split_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "holdout_labels.txt").write_text(
        "\n".join(split["holdout"]) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    crumbs.add("SPLIT_FROZEN", {
        "training_count": manifest["training_count"],
        "holdout_count": manifest["holdout_count"],
        "target": manifest["target"],
        "leakage": manifest["training_proof_mentions_holdout"],
    })

    t_train = time.monotonic()
    model = train_model(mm, split["training"], split["decompressed"])
    training_summary = model_summary(model)
    training_summary["elapsed_seconds"] = time.monotonic() - t_train
    training_summary["target_exposed_to_training"] = False
    training_summary["holdout_proofs_used_for_training"] = False
    (out / "training_summary.json").write_text(
        json.dumps(training_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    crumbs.add("TRAINING_COMPLETE", training_summary)

    target = manifest["target"]
    holdout = set(split["holdout"])
    target_original_steps = list(split["target_original_steps"])

    for lab in holdout:
        mm.proofs[lab] = ["?"]
    del split["decompressed"]
    del split["target_original_steps"]

    if any(lab in model["final_counts"] for lab in holdout):
        raise RuntimeError("training model contains a held-out final label")

    searcher = BackwardSearcher(
        mm,
        target=target,
        holdout=holdout,
        model=model,
        deadline=time.monotonic() + args.seconds,
        breadcrumbs=crumbs,
        bank_path=out / "failure_bank.jsonl",
    )

    portfolio = [
        ("learned", 3, 24),
        ("learned", 5, 48),
        ("simple", 5, 64),
        ("frequency", 6, 80),
        ("recency", 6, 96),
        ("learned", 7, 128),
        ("frequency", 8, 160),
        ("simple", 8, 192),
    ]
    run_started = time.monotonic()
    attempts: list[dict[str, Any]] = []
    candidate: list[str] | None = None
    for i, (strategy, depth, top_k) in enumerate(portfolio):
        elapsed = time.monotonic() - run_started
        remaining = args.seconds - elapsed
        if remaining <= 0:
            break
        slots = len(portfolio) - i
        slice_seconds = max(10.0, remaining / slots)
        result = searcher.run_round(
            strategy=strategy, depth=depth, top_k=top_k,
            seconds=slice_seconds,
        )
        proof = result.pop("proof")
        attempts.append(result)
        if proof is not None:
            candidate = proof
            break

    verifier_gate = False
    verifier_rc: int | None = None
    verifier_log = out / "fresh_verifier.log"
    candidate_sha = None
    if candidate is not None:
        forbidden = [x for x in candidate if x in holdout]
        if forbidden:
            raise RuntimeError(f"candidate illegally references held-out labels: {forbidden[:5]}")
        candidate_text = " ".join(candidate) + "\n"
        (out / "candidate_proof.txt").write_text(candidate_text, encoding="utf-8")
        candidate_sha = sha256_bytes(candidate_text.encode("utf-8"))
        candidate_db = out / "candidate_set.mm"
        write_candidate_database(source, target, candidate, candidate_db)
        verifier_gate, verifier_rc = fresh_verify(
            repo_root, candidate_db, target, verifier_log
        )
        try:
            candidate_db.unlink()
        except OSError:
            pass

    status = "SETTLED" if verifier_gate else "BOUNDED_UNKNOWN"
    result = {
        "architecture": ARCH,
        "status": status,
        "source_commit": args.source_commit,
        "source_sha256": manifest["source_sha256"],
        "seed": args.seed,
        "training_count": manifest["training_count"],
        "holdout_count": manifest["holdout_count"],
        "actual_training_fraction": manifest["actual_training_fraction"],
        "target": target,
        "target_seen_during_training": False,
        "heldout_proof_redaction": True,
        "training_proof_mentions_holdout": False,
        "target_original_proof_steps_for_posthoc_difficulty_only": len(target_original_steps),
        "search_budget_seconds": args.seconds,
        "search_elapsed_seconds": time.monotonic() - run_started,
        "attempts": attempts,
        "candidate_found": candidate is not None,
        "candidate_proof_steps": len(candidate) if candidate else None,
        "candidate_sha256": candidate_sha,
        "fresh_verifier_gate_passed": verifier_gate,
        "fresh_verifier_returncode": verifier_rc,
        "failure_trajectory_count": sum(1 for a in attempts if not a["proof_found"]),
        "breadcrumb_chain_verified": crumbs.verify(),
        "breadcrumb_chain_head": crumbs.prev,
    }
    crumbs.add("RUN_FINISHED", {
        "status": status,
        "target": target,
        "verifier_gate_passed": verifier_gate,
        "attempts": len(attempts),
    })
    result["breadcrumb_chain_verified"] = crumbs.verify()
    result["breadcrumb_chain_head"] = crumbs.prev
    (out / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0 if result["breadcrumb_chain_verified"] else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setmm", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source-commit", default=DEFAULT_SOURCE_COMMIT)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--holdout-fraction", type=float, default=DEFAULT_HOLDOUT)
    ap.add_argument("--seconds", type=int, default=DEFAULT_SECONDS)
    ap.add_argument("--min-target-proof-steps", type=int, default=5)
    ap.add_argument("--max-target-proof-steps", type=int, default=30)
    ap.add_argument("--max-target-statement-tokens", type=int, default=60)
    args = ap.parse_args()
    if not 0 < args.holdout_fraction < 1:
        ap.error("--holdout-fraction must be in (0,1)")
    if args.seconds <= 0:
        ap.error("--seconds must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
