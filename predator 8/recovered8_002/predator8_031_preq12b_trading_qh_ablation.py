#!/usr/bin/env python3
"""Predator 8.031: preq12b presentation-trading / QH / BANK ablation.

Target: preq12b.

Arms
----
baseline
    Expanded presentation: search-visible assertions stop immediately before
    prcom.  The target verifier still uses the complete frozen set.mm.
trading
    Same expanded presentation, plus verified theorem prcom promoted back to a
    direct search rule.  Because prcom is derivable entirely from earlier
    assertions, this is a consequence-preserving derived-rule trade.
qh
    Baseline presentation plus the 8.028 structural-depth quotient heuristic.
trading_qh
    Traded presentation plus QH.
trading_qh_bank
    Traded presentation plus QH, with the already-verified prcom BANK entry
    explicitly prioritized whenever it is an applicable candidate.

The target proof itself remains guarded by predator8_019_target.py.  No target
proof or downstream theorem is made search-visible.  Every claimed settlement
must pass both the in-process and independent Metamath verifiers.
"""
from __future__ import annotations

import argparse
import sys

import predator8_019_target as T
import predator8_028_prcom_quotient_awareness as QH

ARMS = {"baseline", "trading", "qh", "trading_qh", "trading_qh_bank"}
BANK_LABEL = "prcom"
BANK_BOOST = 8.0


def install_presentation(traded: bool):
    """Restrict the search index to pre-prcom assertions, optionally + prcom."""
    original_load_engine = T.B.load_engine

    def load_engine_with_presentation(path):
        E = original_load_engine(path)
        BaseIndex = E.Index

        class PresentationIndex(BaseIndex):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if not args:
                    raise RuntimeError("Index constructor did not receive Metamath database")
                mm = args[0]
                if BANK_LABEL not in mm.order:
                    raise RuntimeError("prcom not found in theorem order")
                p = mm.order.index(BANK_LABEL)
                self._presentation_allowed = set(mm.order[:p])
                if traded:
                    self._presentation_allowed.add(BANK_LABEL)
                print("[PRESENTATION] mode=%s pre_prcom_labels=%d prcom_enabled=%s" %
                      ("TRADED" if traded else "EXPANDED",
                       p, "YES" if traded else "NO"))

            def candidates(self, goal):
                closers, openers = super().candidates(goal)
                allow = self._presentation_allowed
                closers = [c for c in closers if c[0] in allow]
                openers = [c for c in openers if c[0] in allow]
                return closers, openers

        E.Index = PresentationIndex
        return E

    T.B.load_engine = load_engine_with_presentation


def install_bank_priority():
    """Bias the no-ML ranking toward the previously verified prcom BANK entry."""
    Base = T.ZeroPolicy

    class BankPriorityPolicy(Base):
        artifact = {"metadata": {"mode": "no-ml-plus-verified-bank", "bank": [BANK_LABEL]}}

        def __init__(self):
            super().__init__()
            self.bank_retrievals = 0

        def rank(self, goal, candidates):
            scores = [0.0] * len(candidates)
            for j, cand in enumerate(candidates):
                if cand[0] == BANK_LABEL:
                    scores[j] = BANK_BOOST
                    self.bank_retrievals += 1
                    if self.bank_retrievals <= 8 or self.bank_retrievals % 100 == 0:
                        print("[BANK-HIT] label=%s retrieval=%d boost=%.1f" %
                              (BANK_LABEL, self.bank_retrievals, BANK_BOOST))
            return scores

    T.ZeroPolicy = BankPriorityPolicy


def main():
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("--arm", choices=sorted(ARMS), required=True)
    ns, rest = gate.parse_known_args()
    arm = ns.arm

    traded = arm in {"trading", "trading_qh", "trading_qh_bank"}
    qh = arm in {"qh", "trading_qh", "trading_qh_bank"}
    bank = arm == "trading_qh_bank"

    print("=" * 78)
    print("Predator 8.031 preq12b Trading/QH/BANK ablation -- arm=%s" % arm)
    print("=" * 78)
    print("[ABLATION] traded=%s qh=%s bank_priority=%s" %
          ("YES" if traded else "NO", "YES" if qh else "NO", "YES" if bank else "NO"))
    print("[TRUST] target proof guarded; full Metamath verifier unchanged")

    install_presentation(traded=traded)
    if qh:
        QH.install_quotient_controller()
        print("[QH] structural-depth dominance quotient ENABLED")
    if bank:
        install_bank_priority()
        print("[BANK] verified prcom entry receives explicit retrieval priority")

    sys.argv = [sys.argv[0]] + rest
    return T.main()


if __name__ == "__main__":
    raise SystemExit(main())
