# metamath.py — a Metamath parser and proof verifier

One file, no dependencies, Python 3.8+.

```powershell
python metamath.py selftest              # verify the verifier, needs no files
python metamath.py verify set.mm         # check every proof in the corpus
python metamath.py show   set.mm sbth    # one theorem: frame, proof, verdict
python metamath.py stats  set.mm         # corpus statistics
```

---

## Why this exists

It replaces `setmm_parser.py`, which was wrong.

In Metamath the **label precedes the keyword**:

```
th1 $p |- t = t $= ...proof... $.
^^^ label            ^^ keyword
```

The old parser skipped past `$p` and read the next token as the theorem name. On
a known-good input file it reported:

```
theorems: 1
|-        proof length: 34      <-- should be "th1"
```

Every theorem in the resulting `theorems_full.json` was named `|-`, with the
conclusion field shifted one position. The file looks plausible — 43,000
entries, correct proof lengths — and nothing downstream can detect the problem.

**If you have `theorems_full.json` or `setmm_parser.py` in the repo, delete
them.** Anything built on that output is built on garbage.

A verifier catches this class of bug immediately: a proof that does not check is
a proof that was not read correctly.

---

## Why verification, not just parsing

The central claim of the project is that membership in a search stage is
theoremhood:

> `w ∈ p_m` means `Γ ⊢ w`.

That holds only if each step really is a substitution instance of a rule. The
verifier is what checks it. Without one, "found a proof" is an assertion; with
one, it is a proof.

---

## What Metamath actually is

Metamath has **one rule**: substitution of symbol sequences for variables. No
built-in logic, no unification, no types beyond what `set.mm` declares. An
assertion is checked by an RPN stack machine:

```
for each label in the proof:
    if it names a hypothesis  -> PUSH its statement
    if it names an assertion  -> POP its mandatory hypotheses,
                                 solve for the substitution they force,
                                 check the $e hypotheses match under it,
                                 check the disjoint-variable conditions,
                                 PUSH the conclusion under it
at the end the stack must hold exactly the statement being proved
```

That smallness is why a verifier fits in a few hundred lines, and why `set.mm`
can be trusted at all.

### Mandatory hypotheses — the part that is easy to get wrong

An assertion's frame is **not** "the hypotheses in scope". It is:

- the `$e` hypotheses in scope, in declaration order, and
- the `$f` hypotheses, in declaration order, for **exactly those variables that
  occur** in the assertion or in one of those `$e` hypotheses, and
- the `$d` disjointness pairs in scope, restricted to those variables.

A `$f` for a variable that does not occur is **not** mandatory and must not be
popped. Include one extra and the whole stack shifts and every proof fails.

### Compressed proofs

`set.mm` stores proofs compressed:

```
$= ( label1 label2 ... ) ABCZDEF $.
```

The letters are base-20/base-5 numbers: `A`–`T` are final digits (1–20), `U`–`Y`
are continuation digits (1–5), and `Z` marks the preceding subproof for reuse. A
decoded number indexes, in order: the mandatory hypotheses, then the
parenthesised labels, then the `Z`-marked backreferences.

Uncompressed proofs are also supported. Proofs containing `?` are incomplete and
are reported separately rather than counted as verified.

---

## The selftest

Run it first. It needs no external files.

```
python metamath.py selftest
```

```
  th1       expect ok          got ok          ok
  th1c      expect ok          got ok          ok
  th1z      expect ok          got ok          ok
  badstack  expect fail        got fail        ok
  badconcl  expect fail        got fail        ok
  incomp    expect incomplete  got incomplete  ok

  three encodings of one proof decode to the same 34 steps  ok

  all checks passed
```

**Three of the six cases must FAIL.** A verifier that accepts everything is
worthless, so the suite is half negative controls:

| case | what it is | must be |
|---|---|---|
| `th1` | the tutorial proof, uncompressed | ok |
| `th1c` | the same proof, compressed | ok |
| `th1z` | the same proof, compressed with `Z` backreferences | ok |
| `badstack` | corrupted final step | **fail** |
| `badconcl` | well-formed, one stack entry, **wrong statement** | **fail** |
| `incomp` | contains `?` | incomplete |

`badconcl` is the sharper of the two negative controls: the proof is
structurally valid and leaves exactly one entry on the stack. Only the final
comparison catches it.

```
FAIL badconcl: proved the wrong statement
  got      |- ( t + 0 ) = t
  expected |- t = t
```

### The cross-encoding check earned its keep

`th1`, `th1c`, and `th1z` are three encodings of one proof, so they must decode
to byte-identical step lists. That check caught a real bug during development:
the backreference list was being grown on *every* step instead of only at `Z`,
so backreference 1 pointed at the first single token rather than the marked
subproof. The `Z` proof decoded to 26 steps instead of 34 and failed with a type
mismatch.

Without that test, thousands of `set.mm` proofs would have failed with no
indication of why.

---

## Running it on set.mm

```powershell
cd "C:\google drive\Automated Theorem Proving"

curl -o set.mm https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm

python metamath.py selftest
python metamath.py verify set.mm --limit 2000
```

Start with `--limit 2000`. Parsing a 50 MB file takes ~30 s, and a problem will
show up in the first few hundred proofs rather than after a long wait.

A clean run:

```
  parsed in 28.4s: 3,000+ axioms, 44,000+ theorems, 1,000+ constants
  verifying 2,000 proofs...
  verified   2,000
  incomplete 0
  FAILED     0
```

`incomplete` may be nonzero — `set.mm` carries some proofs with `?` placeholders.
That is expected.

**`FAILED` must be 0.** `set.mm` is verified continuously upstream, so any
failure means this reader is wrong, not the file.

Then the whole corpus:

```powershell
python metamath.py verify set.mm
```

Budget 10–30 minutes in pure Python. Progress prints every 2000 proofs.

### Worth looking at

```powershell
python metamath.py show set.mm sbth      # Schröder-Bernstein
python metamath.py show set.mm mapdom
python metamath.py show set.mm rpnnen
```

Those three are the endgame of the hyperreal cardinality argument. `show` prints
the mandatory hypotheses, the decompressed proof, and the verdict.

---

## Commands

### `selftest`

Runs the six known-answer cases above. No files needed. Exit code 0 on success.

### `verify [file]`

| flag | meaning |
|---|---|
| `--limit N` | only the first N theorems |
| `--only LABEL ...` | only these labels |
| `--progress N` | print progress every N proofs (default 2000) |
| `--show-failures N` | print at most N failure messages (default 10) |

Exit code 0 if nothing failed, 1 otherwise.

### `show [file] LABEL`

Prints the statement, mandatory `$f` and `$e` hypotheses, disjoint-variable
conditions, the decompressed proof, and the verification verdict. If the label
is not found it suggests near matches.

### `stats [file]`

Corpus size, proof-length distribution, and the most-cited labels — which is the
prior a premise selector is learning.

---

## Next step

The verifier's stack machine **is** the one-step extension relation. Given a
state (a set of proved statements), the admissible next steps are exactly the
assertions whose mandatory hypotheses can be matched against what is already on
the stack. That is the piece `setmm_inference.py` was stubbing with
`return None`.

Building the inference engine on top of a verified reader means every step it
proposes is checkable, and every proof it finds can be handed back to
`verify` for independent confirmation.
