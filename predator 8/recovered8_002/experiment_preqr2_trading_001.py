#!/usr/bin/env python3
"""PREQR2 Trading-Theorem experiment 001.

Target: preqr2.

Scientific question
-------------------
Does exposing the already-verified derived theorem ``prcom`` as a direct
search macro materially reduce verifier-gated search cost for ``preqr2``?

All arms share a deliberately controlled search presentation:
  * every assertion strictly before ``prcom`` remains search-visible;
  * ``preqr1`` is exposed as the same fixed verified support lemma in every arm;
  * the target ``preqr2`` and every other downstream assertion remain hidden;
  * traded arms additionally expose ``prcom``;
  * the complete frozen set.mm is still used only as the trust anchor for
    parsing/verification.

Since both ``preqr1`` and ``prcom`` are already verified theorems derivable from
the underlying earlier basis, exposing either as a macro changes operational
proof geometry rather than mathematical consequence.

Arms
----
baseline
    Controlled presentation, no prcom macro.
trading
    Baseline + verified prcom as a direct search macro.
qh
    Baseline + the existing structural-depth quotient heuristic.
trading_qh
    Trading + QH.
trading_qh_bank
    Trading + QH + explicit BANK retrieval priority for prcom.

Every claimed proof must still pass the runner's in-process and independent
Metamath verification gates.
"""
from __future__ import annotations

import argparse
import sys

import predator8_019_target as T
import predator8_028_prcom_quotient_awareness as QH

ARMS = {"baseline", "trading", "qh", "trading_qh", "trading_qh_bank"}
TRADE_LABEL = "prcom"
COMMON_SUPPORT = {"preqr1"}
BANK_BOOST = 8.0


def install_presentation(traded: bool):
    """Install pre-prcom basis + common support, optionally + prcom."""
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
                for label in [TRADE_LABEL, *sorted(COMMON_SUPPORT), "preqr2"]:
                    if label not in mm.order:
                        raise RuntimeError(f"required label not found in theorem order: {label}")
                p = mm.order.index(TRADE_LABEL)
                target_p = mm.order.index("preqr2")
                allowed = set(mm.order[:p])
                allowed.update(COMMON_SUPPORT)
                if traded:
                    allowed.add(TRADE_LABEL)
                allowed.discard("preqr2")
                self._presentation_allowed = allowed
                print(
                    "[PRESENTATION] mode=%s pre_prcom_labels=%d common_support=%s prcom_enabled=%s target_index=%d"
                    % (
                        "TRADED" if traded else "BASELINE",
                        p,
                        ",".join(sorted(COMMON_SUPPORT)),
                        "YES" if traded else "NO",
                        target_p,
                    )
                )

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
    """Bias no-ML ranking toward the verified traded theorem prcom."""
    Base = T.ZeroPolicy

    class BankPriorityPolicy(Base):
        artifact = {
            "metadata": {
                "mode": "no-ml-plus-verified-bank",
                "bank": [TRADE_LABEL],
                "target": "preqr2",
            }
        }

        def __init__(self):
            super().__init__()
            self.bank_retrievals = 0

        def rank(self, goal, candidates):
            scores = [0.0] * len(candidates)
            for j, cand in enumerate(candidates):
                if cand[0] == TRADE_LABEL:
                    scores[j] = BANK_BOOST
                    self.bank_retrievals += 1
                    if self.bank_retrievals <= 8 or self.bank_retrievals % 100 == 0:
                        print(
                            "[BANK-HIT] label=%s retrieval=%d boost=%.1f"
                            % (TRADE_LABEL, self.bank_retrievals, BANK_BOOST)
                        )
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
    print("PREQR2 Trading-Theorem experiment 001 -- arm=%s" % arm)
    print("=" * 78)
    print(
        "[ABLATION] traded=%s qh=%s bank_priority=%s"
        % ("YES" if traded else "NO", "YES" if qh else "NO", "YES" if bank else "NO")
    )
    print("[TRADE] verified derived theorem prcom is the experimental trade")
    print("[CONTROL] preqr1 is fixed search-visible support in every arm")
    print("[TRUST] target proof hidden; full Metamath verifier unchanged")

    install_presentation(traded=traded)
    if qh:
        QH.install_quotient_controller()
        print("[QH] structural-depth dominance quotient ENABLED")
    if bank:
        install_bank_priority()
        print("[BANK] verified prcom receives explicit retrieval priority")

    sys.argv = [sys.argv[0]] + rest
    return T.main()


if __name__ == "__main__":
    raise SystemExit(main())
