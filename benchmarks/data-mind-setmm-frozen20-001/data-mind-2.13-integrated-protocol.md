# DATA-MIND 2.13 integrated Frozen-20 protocol

This comparison keeps the Frozen-20 corpus, split, target order, redaction
policy, 1,800-second per-target budget, and fresh-verifier acceptance gate
fixed.  It changes only the proof-search controller.

## Required live modules

Every target run must write `module_usage.json`.  The run fails if any of the
following live-path counters is zero:

| Module | Live proof-search role | Required counter |
|---|---|---|
| BANK reuse | Reuses verified assertions and proof fragments already solved in the current search. | `bank_reuse_queries` |
| Trading within BANK | Recalls earlier verified assertions through exact, alpha-renamed, and constant-skeleton index views. All recalled candidates still undergo ordinary substitution and distinct-variable checks. | `bank_trade_queries` |
| Quotient Hunter | Canonicalizes alpha-equivalent goals and prunes dominated revisits within a search round. It never supplies a proof step. | `quotient_queries` |
| Proof macros | Prior verified `$p` assertions are tried as derived rules before the ordinary candidate list. Successful macros expand to ordinary Metamath labels. | `proof_macro_queries` |
| Professor | Adds a partial-credit score for constant overlap, subgoal feasibility, and rule simplicity to live candidate ordering. | `professor_scores` |
| Shortcut module | Checks local hypotheses, exact verified closers, and exact runtime-BANK entries before general search. | `shortcut_queries` |

Invocation is mandatory; a hit is not.  Hit, attempt, prune, and deposit
counters are also retained so an invoked-but-inapplicable module can be
distinguished from one that materially affected a proof.

## Soundness boundary

These modules propose, recall, rank, cache, or prune search actions.  They do
not change the proof language or acceptance rule.  A target is `SETTLED` only
when a fresh `metamath.py` subprocess verifies the emitted ordinary-label
certificate after all held-out labels have been rejected from that
certificate.

