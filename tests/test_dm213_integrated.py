from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

import metamath
import data_mind_2_12_setmm_holdout as base
import data_mind_2_13_integrated as dm


TOY = r"""
$c wff |- ( ) -> $.
$v ph ps $.
wph $f wff ph $.
wps $f wff ps $.
wi $a wff ( ph -> ps ) $.
ax-1 $a |- ( ph -> ( ps -> ph ) ) $.
prior $p |- ( ph -> ( ph -> ph ) ) $= wph wph ax-1 $.
target $p |- ( ph -> ( ph -> ph ) ) $= wph prior $.
"""


class DataMind213Tests(unittest.TestCase):
    def searcher(self, directory: str):
        mm = metamath.MM()
        mm.read(metamath.Toks(TOY))
        self.assertEqual(mm.verify("target"), "ok")
        mm.proofs["target"] = ["?"]
        model = {
            "trained_theorems": 1,
            "training_steps_processed": 3,
            "final_counts": Counter({"prior": 1}),
            "premise_counts": Counter({"prior": 1, "ax-1": 1}),
            "token_final": defaultdict(Counter),
        }
        return mm, dm.IntegratedSearcher(
            mm, target="target", holdout={"target"}, model=model,
            deadline=time.monotonic() + 5,
            breadcrumbs=base.Breadcrumbs(Path(directory) / "crumbs.jsonl"),
            bank_path=Path(directory) / "failure_bank.jsonl",
        )

    def test_all_requested_modules_are_in_live_proof_path(self):
        with tempfile.TemporaryDirectory() as td:
            mm, searcher = self.searcher(td)
            result = searcher.run_round(strategy="learned", depth=5,
                                        top_k=48, seconds=3)
            self.assertTrue(result["proof_found"])
            mm.proofs["target"] = result["proof"]
            self.assertEqual(mm.verify("target"), "ok")
            for counter in dm.REQUIRED_MODULE_COUNTERS:
                self.assertGreater(searcher.module_usage[counter], 0, counter)
            self.assertGreater(searcher.module_usage["shortcut_hits"], 0)
            dm.validate_module_use(td)

    def test_bank_trade_and_quotient_keys_ignore_variable_names(self):
        variables = {"ph", "ps"}
        a = ("|-", "(", "ph", "->", "ps", ")")
        b = ("|-", "(", "ps", "->", "ph", ")")
        self.assertEqual(dm.alpha_key(a, variables), dm.alpha_key(b, variables))


if __name__ == "__main__":
    unittest.main()
