#!/usr/bin/env python3
"""Run DATA MIND 2.12 on another target from the same frozen set.mm 95/5 split.

Target ordinal 0 reproduces the original random target. Ordinals 1,2,... are
subsequent draws without replacement from the same eligible held-out pool,
using the same PRNG state after the frozen holdout shuffle. This changes only
the target, never the 95/5 partition or training corpus.
"""
from __future__ import annotations

import random
import sys

from experiments import data_mind_2_12_setmm_holdout as dm


def pop_ordinal(argv: list[str]) -> tuple[int, list[str]]:
    out = [argv[0]]
    ordinal = None
    i = 1
    while i < len(argv):
        if argv[i] == "--target-ordinal":
            if i + 1 >= len(argv):
                raise SystemExit("--target-ordinal requires an integer")
            ordinal = int(argv[i + 1])
            i += 2
            continue
        out.append(argv[i])
        i += 1
    if ordinal is None:
        raise SystemExit("--target-ordinal is required")
    if ordinal < 0:
        raise SystemExit("--target-ordinal must be nonnegative")
    return ordinal, out


def install_target_ordinal(ordinal: int) -> None:
    original = dm.build_split

    def build_split_ordinal(mm, *, seed, holdout_fraction,
                            min_target_proof_steps, max_target_proof_steps,
                            max_target_statement_tokens):
        manifest, split = original(
            mm,
            seed=seed,
            holdout_fraction=holdout_fraction,
            min_target_proof_steps=min_target_proof_steps,
            max_target_proof_steps=max_target_proof_steps,
            max_target_statement_tokens=max_target_statement_tokens,
        )

        complete = list(split["complete"])
        dec = split["decompressed"]
        holdout = list(split["holdout"])
        cited = set()
        for lab in complete:
            for step in dec[lab]:
                if mm.labels.get(step, (None,))[0] == "$p":
                    cited.add(step)
        leaves = [lab for lab in complete if lab not in cited]

        rng = random.Random(seed)
        shuffled = list(leaves)
        rng.shuffle(shuffled)
        if shuffled[:len(holdout)] != holdout:
            raise RuntimeError("frozen holdout reconstruction mismatch")

        order_index = {lab: i for i, lab in enumerate(mm.order)}
        proof_lengths = {lab: len(dec[lab]) for lab in holdout}

        def target_ok(lab, lo, hi, stat_cap):
            _dvs, _f, e, stat = mm.labels[lab][1]
            return (not e and lo <= proof_lengths[lab] <= hi
                    and len(stat) <= stat_cap and order_index[lab] > 500)

        pool = [lab for lab in holdout
                if target_ok(lab, min_target_proof_steps,
                             max_target_proof_steps,
                             max_target_statement_tokens)]
        widened = False
        if not pool:
            widened = True
            pool = [lab for lab in holdout
                    if target_ok(lab, 2, max(80, max_target_proof_steps),
                                 max(100, max_target_statement_tokens))]
        if ordinal >= len(pool):
            raise RuntimeError(
                f"target ordinal {ordinal} exceeds eligible pool of {len(pool)}"
            )

        available = list(pool)
        draws = []
        for _ in range(ordinal + 1):
            target = rng.choice(available)
            draws.append(target)
            available.remove(target)

        # Ordinal zero must exactly reproduce the original experiment.
        if ordinal == 0 and target != manifest["target"]:
            raise RuntimeError(
                f"ordinal-0 target mismatch: {target} != {manifest['target']}"
            )

        manifest.update({
            "target": target,
            "target_in_training": target in set(split["training"]),
            "target_proof_steps_hidden": proof_lengths[target],
            "target_statement_tokens": len(dm.assertion_statement(mm, target)),
            "target_stratum_widened": widened,
            "target_ordinal": ordinal,
            "target_draw_sequence_through_ordinal": draws,
        })
        split["target"] = target
        split["target_original_steps"] = list(dec[target])
        return manifest, split

    dm.build_split = build_split_ordinal


def main() -> int:
    ordinal, argv = pop_ordinal(sys.argv)
    sys.argv = argv
    install_target_ordinal(ordinal)
    return dm.main()


if __name__ == "__main__":
    raise SystemExit(main())
