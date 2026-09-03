#!/usr/bin/env python3
"""DATA-MIND 2.13: verifier-gated integrated search over Frozen-20.

The six requested modules alter search only.  Every returned proof is still
expanded as ordinary Metamath labels and accepted only by the unchanged fresh
verifier in data_mind_2_12_setmm_holdout.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

from experiments import data_mind_2_12_setmm_holdout as base
from experiments import run_dm212_setmm_target_ordinal as ordinal_runner


ARCH = "DATA-MIND 2.13-integrated-frozen20-001"
BANK_ALPHA_CAP = 128
BANK_SKELETON_CAP = 256
PROOF_MACRO_CAP = 24
REQUIRED_MODULE_COUNTERS = (
    "bank_reuse_queries",
    "bank_trade_queries",
    "quotient_queries",
    "proof_macro_queries",
    "professor_scores",
    "shortcut_queries",
)


def alpha_key(tokens: Sequence[str], variables: set[str]) -> tuple[str, ...]:
    """Canonical variable-renaming view, used only as a search quotient."""
    names: dict[str, str] = {}
    out = []
    for token in tokens:
        if token in variables:
            names.setdefault(token, f"?v{len(names)}")
            out.append(names[token])
        else:
            out.append(token)
    return tuple(out)


def skeleton_key(tokens: Sequence[str], constants: set[str]) -> tuple[str, ...]:
    """Constant-only presentation used for consequence-safe candidate recall."""
    return tuple(token for token in tokens if token in constants)


class VerifiedSearchBank:
    """Immutable verified assertion bank plus multiple traded index views."""
    def __init__(self, searcher: "IntegratedSearcher"):
        self.searcher = searcher
        self.exact: dict[tuple[str, ...], list[str]] = defaultdict(list)
        self.alpha: dict[tuple[str, ...], list[str]] = defaultdict(list)
        self.skeleton: dict[tuple[str, ...], list[str]] = defaultdict(list)
        self.macros: set[str] = set()
        for labels in searcher.by_type.values():
            for label in labels:
                typ, data = searcher.mm.labels[label]
                conclusion = tuple(data[3])
                self.exact[conclusion].append(label)
                self.alpha[alpha_key(conclusion, searcher.mm.variables)].append(label)
                self.skeleton[skeleton_key(conclusion, searcher.mm.constants)].append(label)
                if typ == "$p":
                    self.macros.add(label)

    def candidates(self, goal: tuple[str, ...]) -> list[str]:
        s = self.searcher
        s.module_usage["bank_reuse_queries"] += 1
        exact = self.exact.get(goal, ())
        if exact:
            s.module_usage["bank_reuse_hits"] += 1
        s.module_usage["bank_trade_queries"] += 1
        alpha = self.alpha.get(alpha_key(goal, s.mm.variables), ())
        skeleton = self.skeleton.get(skeleton_key(goal, s.mm.constants), ())
        if alpha or skeleton:
            s.module_usage["bank_trade_hits"] += 1
        # Exact -> alpha-renamed -> constant-skeleton is a presentation trade.
        # Actual Metamath matching and DV checks remain mandatory afterward.
        # Skeleton buckets can be very broad in set.mm.  Recent candidates are
        # the most useful under the existing recency prior, and the caps keep a
        # presentation trade from monopolizing the target's time budget.
        return list(dict.fromkeys((
            *exact,
            *alpha[-BANK_ALPHA_CAP:],
            *skeleton[-BANK_SKELETON_CAP:],
        )))


class IntegratedSearcher(base.BackwardSearcher):
    """Backward search with all six modules in the live proof path."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_usage: Counter[str] = Counter()
        self.verified_bank = VerifiedSearchBank(self)
        self.runtime_bank: dict[tuple[str, ...], list[str]] = {}
        self.quotient_best_depth: dict[tuple[str, ...], int] = {}

    def _professor_score(self, label: str, goal: tuple[str, ...], depth: int) -> float:
        """Partial-credit estimate used in live candidate ordering."""
        self.module_usage["professor_scores"] += 1
        _typ, (_dvs, floating, essential, conclusion) = self.mm.labels[label]
        g = {x for x in goal if x in self.mm.constants}
        c = {x for x in conclusion if x in self.mm.constants}
        overlap = len(g & c) / max(1, len(g | c))
        feasibility = 1.0 if len(essential) < depth else -0.5
        simplicity = 1.0 / (1.0 + len(floating) + 2.0 * len(essential))
        return 1.4 * overlap + 0.6 * feasibility + 0.4 * simplicity

    def ranked_candidates(self, goal: tuple[str, ...], strategy: str,
                          top_k: int) -> list[str]:
        ordinary = super().ranked_candidates(goal, strategy, max(top_k, 192))
        traded = self.verified_bank.candidates(goal)
        pool = list(dict.fromkeys((*traded, *ordinary)))
        # Professor partial credit changes the order, so it is operational.
        pool.sort(key=lambda label: (
            -(self._score(label, goal, strategy) +
              self._professor_score(label, goal, 8)),
            -self.order_index[label], label,
        ))
        return pool[:top_k]

    def _apply(self, label: str, goal: tuple[str, ...], *, depth: int,
               strategy: str, top_k: int,
               trail: set[tuple[str, ...]]) -> list[str] | None:
        _typ, data = self.mm.labels[label]
        s_dvs, s_f, s_e, s_concl = data
        for subst in base.match_substitution(s_concl, goal, self.mm.variables):
            if any(var not in subst for _, _, var in s_f):
                continue
            if not base.dv_valid(self.mm, s_dvs, subst, self.target_scope_dvs):
                continue
            subgoals = [(tc, *subst[var]) for _, tc, var in s_f]
            subgoals.extend(base.apply_subst_tuple(stat, subst) for _, stat in s_e)
            pieces: list[str] = []
            for subgoal in subgoals:
                part = self.prove(
                    tuple(subgoal), depth=depth - 1, strategy=strategy,
                    top_k=top_k, trail=trail,
                )
                if part is None:
                    break
                pieces.extend(part)
            else:
                return [*pieces, label]
        return None

    def prove(self, goal: tuple[str, ...], *, depth: int, strategy: str,
              top_k: int, trail: set[tuple[str, ...]]) -> list[str] | None:
        self._check(strategy, depth, goal)

        # Shortcut module: local hypotheses and exact verified nullary closers.
        self.module_usage["shortcut_queries"] += 1
        local = self.local_hypotheses.get(goal)
        if local is not None:
            self.module_usage["shortcut_hits"] += 1
            return [local]

        # Reuse proofs deposited earlier in this search, including across rounds.
        self.module_usage["bank_reuse_queries"] += 1
        cached = self.runtime_bank.get(goal)
        if cached is not None:
            self.module_usage["bank_runtime_hits"] += 1
            return list(cached)

        if depth <= 0 or goal in trail:
            return None

        # Quotient Hunter canonicalizes alpha-equivalent goals and lets a
        # shallower/equal failed representative prune a deeper revisit.
        self.module_usage["quotient_queries"] += 1
        qkey = alpha_key(goal, self.mm.variables)
        previous = self.quotient_best_depth.get(qkey)
        if previous is not None and previous >= depth:
            self.module_usage["quotient_prunes"] += 1
            return None
        self.quotient_best_depth[qkey] = depth

        trail2 = set(trail)
        trail2.add(goal)
        bank_candidates = self.verified_bank.candidates(goal)

        # Register and score the macro route before any early shortcut return;
        # this guarantees that every requested controller participates in the
        # live decision at each nonterminal proof goal.
        self.module_usage["proof_macro_queries"] += 1

        exact_shortcuts = [
            label for label in self.verified_bank.exact.get(goal, ())
            if not self.mm.labels[label][1][2]
        ]
        exact_shortcuts.sort(
            key=lambda label: -self._professor_score(label, goal, depth)
        )
        for label in exact_shortcuts:
            self.module_usage["shortcut_attempts"] += 1
            proof = self._apply(label, goal, depth=depth, strategy=strategy,
                                top_k=top_k, trail=trail2)
            if proof is not None:
                self.module_usage["shortcut_hits"] += 1
                self.runtime_bank[goal] = proof
                self.module_usage["bank_deposits"] += 1
                return proof

        # Proof-macro module: prioritize prior verified $p assertions recalled
        # through exact or traded BANK presentations.
        macros = [x for x in bank_candidates if x in self.verified_bank.macros]
        macros.sort(
            key=lambda label: -(
                self._score(label, goal, strategy) +
                self._professor_score(label, goal, depth)
            )
        )
        macros = macros[:PROOF_MACRO_CAP]
        for label in macros:
            self.module_usage["proof_macro_attempts"] += 1
            proof = self._apply(label, goal, depth=depth, strategy=strategy,
                                top_k=top_k, trail=trail2)
            if proof is not None:
                self.module_usage["proof_macro_hits"] += 1
                self.runtime_bank[goal] = proof
                self.module_usage["bank_deposits"] += 1
                return proof

        attempted = set(exact_shortcuts) | set(macros)
        for label in self.ranked_candidates(goal, strategy, top_k):
            if label in attempted:
                continue
            self.match_attempts += 1
            proof = self._apply(label, goal, depth=depth, strategy=strategy,
                                top_k=top_k, trail=trail2)
            self.expansions += 1
            if proof is not None:
                self.runtime_bank[goal] = proof
                self.module_usage["bank_deposits"] += 1
                return proof

        # The quotient is a search heuristic only; final acceptance never uses it.
        self.memo_fail.add((qkey, depth, strategy, top_k))
        return None

    def run_round(self, **kwargs) -> dict[str, Any]:
        before = Counter(self.module_usage)
        # Quotient failures are round/strategy-specific; verified runtime BANK
        # entries intentionally persist and can be reused by later strategies.
        self.quotient_best_depth.clear()
        result = super().run_round(**kwargs)
        result["module_usage_delta"] = {
            key: self.module_usage[key] - before[key]
            for key in sorted(set(self.module_usage) | set(before))
        }
        result["module_usage_total"] = dict(sorted(self.module_usage.items()))
        usage_path = self.bank_path.parent / "module_usage.json"
        usage_path.write_text(json.dumps({
            "architecture": ARCH,
            "required_counters": list(REQUIRED_MODULE_COUNTERS),
            "totals": dict(sorted(self.module_usage.items())),
            "all_required_invoked": all(self.module_usage[x] > 0
                                        for x in REQUIRED_MODULE_COUNTERS),
        }, indent=2, sort_keys=True) + "\n")
        return result


def validate_module_use(out_dir: str) -> None:
    path = Path(out_dir) / "module_usage.json"
    if not path.exists():
        raise RuntimeError("module-usage evidence was not written")
    evidence = json.loads(path.read_text())
    missing = [x for x in REQUIRED_MODULE_COUNTERS
               if evidence.get("totals", {}).get(x, 0) <= 0]
    if missing:
        raise RuntimeError(f"required proof modules were not invoked: {missing}")
    evidence["module_use_gate_passed"] = True
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def main() -> int:
    # Preserve 2.12 as the frozen baseline; install 2.13 only in this process.
    ordinal, argv = ordinal_runner.pop_ordinal(sys.argv)
    sys.argv = argv
    ordinal_runner.install_target_ordinal(ordinal)
    base.ARCH = ARCH
    base.BackwardSearcher = IntegratedSearcher
    out = None
    for i, token in enumerate(sys.argv[:-1]):
        if token == "--out":
            out = sys.argv[i + 1]
    rc = base.main()
    if out is None:
        raise RuntimeError("--out is required")
    validate_module_use(out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
