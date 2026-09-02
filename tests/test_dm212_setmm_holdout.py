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
import data_mind_2_12_setmm_holdout as dm


TOY = r"""
$c wff |- ( ) -> $.
$v ph ps $.
wph $f wff ph $.
wps $f wff ps $.
wi $a wff ( ph -> ps ) $.
ax-1 $a |- ( ph -> ( ps -> ph ) ) $.
th $p |- ( ph -> ( ph -> ph ) ) $= wph wph ax-1 $.
"""


class DataMind212SetMMTests(unittest.TestCase):
    def test_match_substitution_repeated_variable(self):
        variables = {"ph", "ps"}
        pattern = ["|-", "(", "ph", "->", "(", "ps", "->", "ph", ")", ")"]
        goal = ["|-", "(", "ph", "->", "(", "ph", "->", "ph", ")", ")"]
        rows = dm.match_substitution(pattern, goal, variables)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["ph"], ("ph",))
        self.assertEqual(rows[0]["ps"], ("ph",))

    def test_backward_search_finds_verifiable_toy_proof(self):
        mm = metamath.MM()
        mm.read(metamath.Toks(TOY))
        self.assertEqual(mm.verify("th"), "ok")
        mm.proofs["th"] = ["?"]
        model = {
            "trained_theorems": 0,
            "training_steps_processed": 0,
            "final_counts": Counter(),
            "premise_counts": Counter(),
            "token_final": defaultdict(Counter),
        }
        with tempfile.TemporaryDirectory() as td:
            crumbs = dm.Breadcrumbs(Path(td) / "crumbs.jsonl")
            searcher = dm.BackwardSearcher(
                mm,
                target="th",
                holdout={"th"},
                model=model,
                deadline=time.monotonic() + 5,
                breadcrumbs=crumbs,
                bank_path=Path(td) / "bank.jsonl",
            )
            proof = searcher.prove(
                tuple(mm.labels["th"][1][3]),
                depth=3,
                strategy="simple",
                top_k=16,
                trail=set(),
            )
            self.assertEqual(proof, ["wph", "wph", "ax-1"])
            mm.proofs["th"] = proof
            self.assertEqual(mm.verify("th"), "ok")
            self.assertTrue(crumbs.verify())

    def test_holdout_proof_redaction_detection(self):
        self.assertTrue(dm.raw_proof_complete(["a", "b", "c"]))
        self.assertFalse(dm.raw_proof_complete(["(", "a", ")", "AB?C"]))


if __name__ == "__main__":
    unittest.main()
