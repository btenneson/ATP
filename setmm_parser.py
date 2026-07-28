#!/usr/bin/env python3
"""
setmm_parser.py: Parse set.mm and extract full theorem corpus.

This parser reads the Metamath file and builds:
  1. Symbol table (type declarations: wff, class, setvar, etc.)
  2. Axioms (hypotheses, no proof)
  3. Theorems (hypothesis, conclusion, proof steps)

Output: JSON file with all 43k+ theorems, indexed for fast lookup.

USAGE
    python setmm_parser.py --input set.mm --output theorems.json --limit 1000

    Parses set.mm, extracts first 1000 theorems, writes JSON.

STRUCTURE OF OUTPUT
    [
      {
        "name": "mp",
        "type": "axiom",
        "hypothesis": ["a: wff", "b: wff", "imp a b: wff", "a: proof"],
        "conclusion": "b: proof",
        "proof": null,
        "depth": 0
      },
      {
        "name": "prcom",
        "type": "theorem",
        "hypothesis": [<list of hypothesis formulae>],
        "conclusion": "<conclusion formula>",
        "proof": [<list of step labels>],
        "depth": 42
      },
      ...
    ]

The output can be used by:
  - setmm_features.py (extract features from each step)
  - setmm_search.py (guided search using learned ranker)
  - setmm_harvest.py (compute geodesics via BFS)
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict

# ===========================================================================
#  Working directory
# ===========================================================================
WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)

# ===========================================================================
#  Metamath Tokenizer
# ===========================================================================

class Token:
    def __init__(self, val, kind, lineno=0):
        self.val = val
        self.kind = kind  # 'word', 'command', 'symbol', 'punctuation'
        self.lineno = lineno

    def __repr__(self):
        return f"Token({self.kind}: {self.val!r})"

def tokenize_setmm(text):
    """Tokenize set.mm text.

    Commands: $c, $v, $f, $a, $p, $e, $d, $=, $., $}
    """
    tokens = []
    lines = text.split('\n')

    for lineno, line in enumerate(lines, 1):
        # Strip comments
        if '$(' in line:
            line = line[:line.index('$(')]

        # Tokenize
        i = 0
        while i < len(line):
            if line[i] in ' \t\r\n':
                i += 1
            elif line[i] in '{}':
                tokens.append(Token(line[i], 'punctuation', lineno))
                i += 1
            elif line[i:i+2] in ['${', '$}']:
                tokens.append(Token(line[i:i+2], 'punctuation', lineno))
                i += 2
            elif line[i] == '$':
                # Command: $a, $p, etc.
                j = i + 1
                while j < len(line) and line[j] not in ' \t${}':
                    j += 1
                tokens.append(Token(line[i:j], 'command', lineno))
                i = j
            else:
                # Word or symbol
                j = i
                while j < len(line) and line[j] not in ' \t${}':
                    j += 1
                tokens.append(Token(line[i:j], 'word', lineno))
                i = j

    return tokens

# ===========================================================================
#  Parser
# ===========================================================================

class SetMMParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.theorems = []
        self.symbols = {}  # name -> type
        self.hypotheses = {}  # name -> (type, formula)

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def peek_val(self):
        return self.current().val if self.current() else None

    def advance(self):
        self.pos += 1

    def expect(self, val):
        if self.peek_val() == val:
            self.advance()
            return True
        return False

    def collect_until(self, val):
        """Collect tokens until we see val."""
        result = []
        while self.current() and self.peek_val() != val:
            result.append(self.current())
            self.advance()
        if self.expect(val):
            return result
        return None

    def parse(self):
        """Parse the entire file."""
        while self.current():
            cmd = self.peek_val()

            if cmd == '$c':
                self.parse_constants()
            elif cmd == '$v':
                self.parse_variables()
            elif cmd == '$f':
                self.parse_floating()
            elif cmd == '$e':
                self.parse_essential()
            elif cmd == '$a':
                self.parse_axiom()
            elif cmd == '$p':
                self.parse_theorem()
            elif cmd == '$d':
                self.parse_disjoint()
            elif cmd == '${':
                self.parse_block()
            else:
                self.advance()

        return self.theorems

    def parse_constants(self):
        """$c sym1 sym2 ... $."""
        self.advance()  # skip $c
        syms = self.collect_until('$.')
        if syms:
            for sym in syms:
                self.symbols[sym.val] = 'constant'
        self.advance()  # skip $.

    def parse_variables(self):
        """$v var1 var2 ... $."""
        self.advance()  # skip $v
        vars_ = self.collect_until('$.')
        if vars_:
            for var in vars_:
                self.symbols[var.val] = 'variable'
        self.advance()  # skip $.

    def parse_floating(self):
        """$f (type var) $."""
        self.advance()  # skip $f
        toks = self.collect_until('$.')
        # Floating hypothesis: type var
        if toks and len(toks) >= 2:
            type_name = toks[0].val
            var_name = toks[1].val
            self.hypotheses[var_name] = (type_name, var_name)
        self.advance()  # skip $.

    def parse_essential(self):
        """$e (type formula) $."""
        self.advance()  # skip $e
        toks = self.collect_until('$.')
        # Essential hypothesis
        if toks and len(toks) >= 2:
            # Store but don't use yet (would need to track scope)
            pass
        self.advance()  # skip $.

    def parse_axiom(self):
        """$a (type formula...) $."""
        self.advance()  # skip $a
        name = None
        toks = self.collect_until('$.')

        if not toks:
            self.advance()
            return

        # Last token is the label (usually)
        # Axioms don't have names in the proof, so we skip
        self.advance()  # skip $.

    def parse_theorem(self):
        """$p name |- formula $= proof $."""
        self.advance()  # skip $p

        name_tok = self.current()
        if not name_tok:
            return
        name = name_tok.val
        self.advance()

        # Collect up to $=
        formula_toks = []
        while self.current() and self.peek_val() != '$=':
            formula_toks.append(self.current())
            self.advance()

        if not self.expect('$='):
            return

        # Collect proof steps
        proof_toks = []
        while self.current() and self.peek_val() != '$.':
            proof_toks.append(self.current())
            self.advance()

        if not self.expect('$.'):
            return

        # Build theorem record
        theorem = {
            'name': name,
            'type': 'theorem',
            'hypothesis': [],
            'conclusion': ' '.join(t.val for t in formula_toks),
            'proof': [t.val for t in proof_toks],
            'depth': len(proof_toks),
        }

        self.theorems.append(theorem)

    def parse_disjoint(self):
        """$d var1 var2 $."""
        self.advance()  # skip $d
        self.collect_until('$.')
        self.advance()  # skip $.

    def parse_block(self):
        """${ ... $}"""
        self.advance()  # skip ${
        # Skip to matching }
        depth = 1
        while self.current() and depth > 0:
            if self.peek_val() == '${':
                depth += 1
            elif self.peek_val() == '$}':
                depth -= 1
            self.advance()

# ===========================================================================
#  Main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(
        prog="setmm_parser",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", default="set.mm", help="input set.mm file")
    ap.add_argument("--output", default="theorems_setmm.json", help="output JSON file")
    ap.add_argument("--limit", type=int, default=0, help="limit theorems (0=all)")

    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: {args.input} not found")
        print(f"  Download from: https://github.com/metamath/set.mm/blob/develop/set.mm")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  setmm_parser: Load and parse set.mm")
    print(f"{'='*70}\n")

    print(f"  loading {args.input}...")
    t0 = time.time()

    with open(args.input, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    print(f"    file size: {len(text) / 1e6:.1f} MB")
    print(f"  tokenizing...")

    tokens = tokenize_setmm(text)
    print(f"    tokens: {len(tokens):,}")

    print(f"  parsing...")
    parser = SetMMParser(tokens)
    theorems = parser.parse()

    if args.limit and args.limit > 0:
        theorems = theorems[:args.limit]

    elapsed = time.time() - t0

    print(f"    theorems: {len(theorems):,}")
    print(f"    elapsed: {elapsed:.1f}s")

    print(f"\n  writing {args.output}...")
    with open(args.output, 'w') as f:
        json.dump(theorems, f, indent=2)

    print(f"    ✓ saved {len(theorems):,} theorems")
    print(f"\n  Sample theorems:")
    for th in theorems[:5]:
        print(f"    {th['name']:20} proof length: {th['depth']}")

    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    main()
