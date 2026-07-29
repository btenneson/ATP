#!/usr/bin/env python3
"""
metamath.py -- a real Metamath parser and PROOF VERIFIER.

Brian Tenneson.  One file, no dependencies.

    python metamath.py verify demo0.mm          verify every proof in a file
    python metamath.py stats   set.mm           corpus statistics
    python metamath.py show    set.mm sbth      one theorem, in full

WHY A VERIFIER AND NOT JUST A PARSER
------------------------------------
The earlier setmm_parser.py did not verify anything, and it had a bug that only
a verifier would have caught: in Metamath the LABEL PRECEDES THE KEYWORD,

    th1 $p |- t = t $= ...proof... $.
    ^^^ label            ^^ keyword

so a parser that skips '$p' and reads the next token gets '|-' as the name of
every theorem in the file.  It produces a plausible-looking JSON of 43,000
entries all named '|-'.  Nothing downstream can detect this.  A verifier can:
a proof that does not check is a proof that was not read correctly.

This matters for the central question of the project.  "w is in stage m of M"
means w is a theorem -- but only if the steps really are instances of the rules.
Verification is what makes stage-membership a proof rather than an assertion.

WHAT METAMATH ACTUALLY IS
-------------------------
Metamath has ONE rule: substitution of symbol sequences for variables.  There is
no built-in logic, no unification, no types beyond what set.mm declares.  An
assertion is verified by an RPN stack machine:

    for each label in the proof:
        if it names a hypothesis, PUSH its statement
        if it names an assertion, POP its mandatory hypotheses, solve for the
            substitution they force, check the $e hypotheses match under that
            substitution, check the disjoint-variable conditions, and PUSH the
            conclusion under that substitution
    at the end the stack must hold exactly the statement being proved

The substitution is on VARIABLES -> SYMBOL SEQUENCES.  That is the whole system.
Its smallness is why a verifier is a few hundred lines and why set.mm can be
trusted at all.

MANDATORY HYPOTHESES (the part that is easy to get wrong)
---------------------------------------------------------
An assertion's frame is not "the hypotheses in scope".  It is:

  * the $e hypotheses in scope, in declaration order, and
  * the $f hypotheses, in declaration order, for exactly those variables that
    occur in the assertion or in one of those $e hypotheses,
  * the $d disjointness pairs in scope restricted to those variables.

$f hypotheses for variables that do NOT occur are not mandatory and must not be
popped.  Getting this wrong shifts the whole stack and every proof fails.

COMPRESSED PROOFS
-----------------
set.mm stores proofs compressed:

    $= ( label1 label2 ... ) ABCZDEF $.

The letters are base-20/base-5 numbers: A-T are final digits (1..20), U-Y are
continuation digits (1..5), and Z marks the previous step for reuse.  A decoded
number indexes, in order, the mandatory hypotheses, then the parenthesised
labels, then the Z-marked backreferences.  Uncompressed proofs are also
supported.  Proofs containing '?' are incomplete and are reported as such
rather than counted as verified.
"""
from __future__ import annotations
import argparse, itertools, os, sys, time
from collections import defaultdict

VERSION = "1.0"

WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)


class MMError(Exception):
    pass


# ===========================================================================
#  tokenizer:  whitespace-separated, $( ... $) comments, $[ file $] includes
# ===========================================================================
class Toks:
    def __init__(self, text):
        self.toks = text.split()
        self.i = 0

    def next(self):
        """Next token, with comments stripped."""
        while self.i < len(self.toks):
            t = self.toks[self.i]; self.i += 1
            if t == "$(":
                # comments do not nest; scan to the closing $)
                while self.i < len(self.toks) and self.toks[self.i] != "$)":
                    self.i += 1
                self.i += 1
                continue
            return t
        return None

    def readuntil(self, end):
        out = []
        while True:
            t = self.next()
            if t is None:
                raise MMError("unterminated statement, expected %s" % end)
            if t == end:
                return out
            out.append(t)


# ===========================================================================
#  scope frames
# ===========================================================================
class Frame:
    __slots__ = ("v", "d", "f", "e")
    def __init__(self):
        self.v = set()      # active variables
        self.d = set()      # disjoint pairs, stored sorted
        self.f = []         # [(label, typecode, var)] in declaration order
        self.e = []         # [(label, statement)]     in declaration order


class FrameStack(list):
    def push(self):
        self.append(Frame())

    def pop_frame(self):
        self.pop()

    def add_v(self, v):
        self[-1].v.add(v)

    def add_f(self, label, typecode, var):
        if not self.lookup_v(var):
            raise MMError("$f for inactive variable %s" % var)
        self[-1].f.append((label, typecode, var))

    def add_e(self, label, stat):
        self[-1].e.append((label, stat))

    def add_d(self, varlist):
        self[-1].d.update((min(x, y), max(x, y))
                          for x, y in itertools.product(varlist, varlist)
                          if x != y)

    def lookup_v(self, tok):
        return any(tok in fr.v for fr in self)

    def lookup_f(self, var):
        for fr in reversed(self):
            for label, tc, v in fr.f:
                if v == var:
                    return tc
        return None

    def all_dvs(self):
        """EVERY disjoint pair active here, not just those on mandatory vars.

        A theorem's own proof may introduce DUMMY variables -- ones that occur
        nowhere in its statement.  equid proves  |- x = x  using an auxiliary z.
        The DV conditions governing those dummies are active in the scope but
        are filtered out of the mandatory frame, so verifying equid's own proof
        needs this unrestricted set.  Using the mandatory set here rejects
        equid, ax7, exgen, spnfw and spsv -- correct proofs, wrong reader."""
        return {(x, y) for fr in self for (x, y) in fr.d}

    def make_assertion(self, stat):
        """Compute the frame of an assertion: (dvs, f_hyps, e_hyps, stat).

        The dvs here are restricted to mandatory variables, which is what a
        LATER proof must satisfy when it applies this assertion as a step.  It
        is deliberately NOT the set used to check this assertion's own proof --
        see all_dvs above.

        The other subtle part is which $f hypotheses are mandatory: exactly
        those whose variable occurs in the assertion or in an active $e, taken
        in declaration order.  A $f for an unused variable is NOT mandatory."""
        e_hyps = [(lab, s) for fr in self for (lab, s) in fr.e]
        mand_vars = {tok for _, hyp in e_hyps for tok in hyp
                     if self.lookup_v(tok)}
        mand_vars |= {tok for tok in stat if self.lookup_v(tok)}

        dvs = {(x, y) for fr in self for (x, y) in fr.d
               if x in mand_vars and y in mand_vars}

        f_hyps = []
        seen = set()
        for fr in self:                      # outermost first = declaration order
            for label, tc, v in fr.f:
                if v in mand_vars and v not in seen:
                    f_hyps.append((label, tc, v))
                    seen.add(v)
        return (dvs, f_hyps, e_hyps, stat)


# ===========================================================================
#  substitution:  variable -> symbol sequence.  This is the entire rule.
# ===========================================================================
def apply_subst(stat, subst):
    out = []
    for tok in stat:
        s = subst.get(tok)
        if s is None:
            out.append(tok)
        else:
            out.extend(s)
    return out


# ===========================================================================
#  the database
# ===========================================================================
class MM:
    def __init__(self):
        self.constants = set()
        self.variables = set()    # every variable ever declared, for DV checks
        self.fs = FrameStack()
        self.labels = {}          # label -> ('$a'|'$p'|'$f'|'$e', data)
        self.order = []           # labels in file order
        self.proofs = {}          # label -> raw proof token list
        self.scope_dvs = {}       # $p label -> unrestricted DVs at its scope
        self.stats = defaultdict(int)

    # ---------------------------------------------------------------- read
    def read(self, toks):
        self.fs.push()
        label = None
        while True:
            tok = toks.next()
            if tok is None:
                break

            if tok == "$c":
                for c in toks.readuntil("$."):
                    self.constants.add(c)

            elif tok == "$v":
                for v in toks.readuntil("$."):
                    self.fs.add_v(v)
                    self.variables.add(v)

            elif tok == "$f":
                stat = toks.readuntil("$.")
                if label is None:
                    raise MMError("$f with no label")
                if len(stat) != 2:
                    raise MMError("malformed $f %s" % label)
                self.fs.add_f(label, stat[0], stat[1])
                self.labels[label] = ("$f", [stat[0], stat[1]])
                self.order.append(label)
                label = None

            elif tok == "$e":
                stat = toks.readuntil("$.")
                if label is None:
                    raise MMError("$e with no label")
                self.fs.add_e(label, stat)
                self.labels[label] = ("$e", stat)
                self.order.append(label)
                label = None

            elif tok == "$a":
                stat = toks.readuntil("$.")
                if label is None:
                    raise MMError("$a with no label")
                self.labels[label] = ("$a", self.fs.make_assertion(stat))
                self.order.append(label)
                self.stats["axioms"] += 1
                label = None

            elif tok == "$p":
                rest = toks.readuntil("$.")
                if label is None:
                    raise MMError("$p with no label")
                if "$=" not in rest:
                    raise MMError("$p %s has no $=" % label)
                cut = rest.index("$=")
                stat, proof = rest[:cut], rest[cut + 1:]
                self.labels[label] = ("$p", self.fs.make_assertion(stat))
                self.proofs[label] = proof
                # captured at declaration point, while the scope is still open
                self.scope_dvs[label] = self.fs.all_dvs()
                self.order.append(label)
                self.stats["theorems"] += 1
                label = None

            elif tok == "$d":
                self.fs.add_d(toks.readuntil("$."))

            elif tok == "${":
                self.fs.push()

            elif tok == "$}":
                self.fs.pop_frame()

            elif tok == "$[":
                toks.readuntil("$]")      # includes: ignored, set.mm is one file

            elif tok.startswith("$"):
                raise MMError("unknown command %s" % tok)

            else:
                # THE LABEL COMES FIRST.  This is the line the old parser got
                # wrong, and the reason every theorem came out named '|-'.
                label = tok

    # ------------------------------------------------- decompress a proof
    def decompress(self, label, proof):
        """Expand a compressed proof into a flat list of labels."""
        dvs, f_hyps, e_hyps, stat = self.labels[label][1]
        mand = [l for l, _, _ in f_hyps] + [l for l, _ in e_hyps]

        if proof[0] != "(":
            return proof                       # already uncompressed
        end = proof.index(")")
        extra = proof[1:end]
        letters = "".join(proof[end + 1:])

        pool = mand + extra                    # 1-based indexing below
        out, saved, n = [], [], 0
        for ch in letters:
            if ch == "?":
                out.append("?")
                n = 0
            elif "U" <= ch <= "Y":
                n = n * 5 + (ord(ch) - ord("U") + 1)
            elif "A" <= ch <= "T":
                n = n * 20 + (ord(ch) - ord("A") + 1)
                if n <= len(pool):
                    out.append(pool[n - 1])
                else:
                    k = n - len(pool) - 1
                    if k >= len(saved):
                        raise MMError("bad backreference %d in %s (only %d "
                                      "saved)" % (k + 1, label, len(saved)))
                    out.extend(saved[k])
                n = 0
            elif ch == "Z":
                # Z saves the subproof ending at the step just emitted.  The
                # backreference list grows ONLY here -- an earlier version
                # appended on every step, which made backreference 1 the first
                # single token instead of the marked subproof.  The Z test in
                # mmtest/ztest.mm exists to catch exactly that.
                saved.append(self._subproof(out))
            else:
                raise MMError("bad character %r in compressed proof %s"
                              % (ch, label))
        return out

    def _subproof(self, out):
        """The trailing segment of `out` that forms one complete subproof."""
        need, i = 1, len(out)
        while need and i:
            i -= 1
            lab = out[i]
            if lab == "?":
                need -= 1
                continue
            typ, data = self.labels[lab]
            if typ in ("$e", "$f"):
                need -= 1
            else:
                dvs, f_hyps, e_hyps, _ = data
                need += len(f_hyps) + len(e_hyps) - 1
        return out[i:]

    # ------------------------------------------------------------- verify
    def verify(self, label):
        """Verify one $p.  Returns 'ok', 'incomplete', or raises MMError."""
        _mand_dvs, f_hyps, e_hyps, conclusion = self.labels[label][1]
        # check this proof against the UNRESTRICTED scope DVs, so that dummy
        # variables introduced inside the proof are covered
        dvs = self.scope_dvs.get(label, _mand_dvs)
        proof = self.decompress(label, self.proofs[label])
        if "?" in proof:
            return "incomplete"

        stack = []
        for step in proof:
            if step not in self.labels:
                raise MMError("%s: unknown label %s" % (label, step))
            typ, data = self.labels[step]

            if typ in ("$e", "$f"):
                stack.append(list(data))
                continue

            s_dvs, s_f, s_e, s_concl = data
            npop = len(s_f) + len(s_e)
            if npop > len(stack):
                raise MMError("%s: stack underflow at %s" % (label, step))
            base = len(stack) - npop

            # the $f hypotheses determine the substitution
            subst = {}
            for j, (_, tc, var) in enumerate(s_f):
                entry = stack[base + j]
                if entry[0] != tc:
                    raise MMError("%s: type mismatch at %s: %s vs %s"
                                  % (label, step, entry[0], tc))
                subst[var] = entry[1:]

            # the $e hypotheses must then match exactly
            for j, (_, e_stat) in enumerate(s_e):
                entry = stack[base + len(s_f) + j]
                if apply_subst(e_stat, subst) != entry:
                    raise MMError("%s: hypothesis mismatch at %s" % (label, step))

            # disjoint-variable conditions.  Membership is tested against the
            # GLOBAL variable set: by verification time the scope stack has
            # been popped back to the outermost frame, so fs.lookup_v would
            # miss any variable declared inside a ${ ... $} block.
            for x, y in s_dvs:
                sx = [t for t in subst.get(x, ()) if t in self.variables]
                sy = [t for t in subst.get(y, ()) if t in self.variables]
                for a, b in itertools.product(sx, sy):
                    if a == b or (min(a, b), max(a, b)) not in dvs:
                        raise MMError("%s: disjoint-variable violation "
                                      "(%s,%s) -> (%s,%s) at %s"
                                      % (label, x, y, a, b, step))

            del stack[base:]
            stack.append(apply_subst(s_concl, subst))

        if len(stack) != 1:
            raise MMError("%s: proof ends with %d entries on the stack"
                          % (label, len(stack)))
        if stack[0] != conclusion:
            raise MMError("%s: proved the wrong statement\n  got      %s\n"
                          "  expected %s" % (label, " ".join(stack[0]),
                                             " ".join(conclusion)))
        return "ok"


# ===========================================================================
#  loading
# ===========================================================================
def load(path, say=print):
    if not os.path.exists(path):
        raise SystemExit(
            "%s not found in %s\n"
            "  get set.mm with:\n"
            "    curl -o set.mm https://raw.githubusercontent.com/"
            "metamath/set.mm/develop/set.mm" % (path, os.getcwd()))
    t0 = time.time()
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    say("  %s: %.1f MB" % (path, len(text) / 1e6))
    mm = MM()
    mm.read(Toks(text))
    say("  parsed in %.1fs: %s axioms, %s theorems, %s constants"
        % (time.time() - t0, f"{mm.stats['axioms']:,}",
           f"{mm.stats['theorems']:,}", f"{len(mm.constants):,}"))
    return mm


# ===========================================================================
#  commands
# ===========================================================================
def cmd_verify(a):
    print("\n" + "=" * 74)
    print("  metamath.py v%s  --  verify" % VERSION)
    print("=" * 74 + "\n")
    mm = load(a.file)

    names = [l for l in mm.order if mm.labels[l][0] == "$p"]
    if a.limit:
        names = names[:a.limit]
    if a.only:
        names = [l for l in names if l in set(a.only)]

    print("\n  verifying %s proofs..." % f"{len(names):,}")
    t0 = time.time()
    ok = inc = 0
    failures = []
    for i, label in enumerate(names, 1):
        try:
            r = mm.verify(label)
            if r == "ok":
                ok += 1
            else:
                inc += 1
        except MMError as e:
            failures.append(str(e))
            if len(failures) <= a.show_failures:
                print("    FAIL %s" % e)
        except RecursionError:
            failures.append("%s: recursion limit" % label)
        if a.progress and i % a.progress == 0:
            print("    %s/%s  (%.0f/s)"
                  % (f"{i:,}", f"{len(names):,}", i / max(time.time() - t0, 1e-9)))

    dt = time.time() - t0
    print("\n  " + "-" * 70)
    print("  verified   %s" % f"{ok:,}")
    print("  incomplete %s" % f"{inc:,}")
    print("  FAILED     %s" % f"{len(failures):,}")
    print("  elapsed    %.1fs  (%.0f proofs/s)" % (dt, len(names) / max(dt, 1e-9)))
    print("  " + "-" * 70)
    if not failures and ok:
        print("\n  Every proof checked.  Each verified label is a theorem of the")
        print("  system: the stack machine reduced its proof to exactly its")
        print("  statement using only substitution instances of the rules.\n")
    elif failures:
        print("\n  %d failures -- the reader is wrong, or the file is.\n"
              % len(failures))
    return 0 if not failures else 1


def classify(mm):
    """Split every label into 'syntax' or 'logic'.

    The criterion is the TYPECODE -- the first token of the statement.  In
    set.mm a $a whose statement begins with 'wff', 'class' or 'setvar' is a
    grammar rule that builds a formula; only a $a beginning with '|-' asserts
    anything.  So

        wcel $a wff A e. B $.        <- syntax: how to WRITE "A e. B"
        ax-mp $a |- ps $.            <- logic:  an actual rule of inference

    $f hypotheses are variable typings and are syntax by the same token.  This
    is the distinction that raw step counts hide."""
    kind = {}
    for lab, (typ, data) in mm.labels.items():
        if typ == "$f":
            kind[lab] = "syntax"
        elif typ == "$e":
            kind[lab] = "hyp"
        else:
            stat = data[3]
            kind[lab] = "logic" if stat and stat[0] == "|-" else "syntax"
    return kind


def _dist(xs, label, pad=""):
    xs = sorted(xs)
    if not xs:
        return
    print("%s  %-14s median %s, mean %.0f, max %s"
          % (pad, label, f"{xs[len(xs)//2]:,}", sum(xs) / len(xs), f"{xs[-1]:,}"))


def cmd_stats(a):
    print("\n" + "=" * 74)
    print("  metamath.py v%s  --  corpus statistics" % VERSION)
    print("=" * 74 + "\n")
    mm = load(a.file)
    kind = classify(mm)

    thms = [l for l in mm.order if mm.labels[l][0] == "$p"]
    axs = [l for l in mm.order if mm.labels[l][0] == "$a"]

    # ---- what the "axioms" actually are ------------------------------
    ax_syntax = [l for l in axs if kind[l] == "syntax"]
    ax_logic = [l for l in axs if kind[l] == "logic"]
    ax_true = [l for l in ax_logic if l.startswith("ax-")]
    ax_def = [l for l in ax_logic if l.startswith("df-")]
    ax_other = [l for l in ax_logic
                if not l.startswith("ax-") and not l.startswith("df-")]

    print("\n  $a statements   %s" % f"{len(axs):,}")
    print("    syntax rules  %-8s  grammar: how to write a formula"
          % f"{len(ax_syntax):,}")
    print("    definitions   %-8s  df-*" % f"{len(ax_def):,}")
    print("    TRUE AXIOMS   %-8s  ax-*" % f"{len(ax_true):,}")
    if ax_other:
        print("    other |-      %-8s  %s" % (f"{len(ax_other):,}",
                                              ", ".join(ax_other[:5])))
    print("\n    the logical content of ZFC is those %d ax-* statements."
          % len(ax_true))
    print("    %s of the %s are grammar, not mathematics."
          % (f"{len(ax_syntax):,}", f"{len(axs):,}"))
    if ax_true:
        print("    %s" % ", ".join(sorted(ax_true)[:14]))

    if not a.logical:
        print("\n  theorems        %s" % f"{len(thms):,}")
        print("\n  (run with --logical to separate reasoning steps from")
        print("   formula-building steps; it decompresses every proof)\n")
        return

    # ---- per-proof step accounting -----------------------------------
    print("\n  decompressing %s proofs..." % f"{len(thms):,}")
    t0 = time.time()
    total, logic_only = [], []
    cites_all, cites_logic = defaultdict(int), defaultdict(int)
    skipped = 0
    for i, l in enumerate(thms, 1):
        try:
            proof = mm.decompress(l, mm.proofs[l])
        except (MMError, RecursionError, ValueError):
            skipped += 1
            continue
        nl = sum(1 for s in proof if kind.get(s) == "logic")
        total.append(len(proof))
        logic_only.append(nl)
        for s in set(proof):                      # distinct labels per proof
            cites_all[s] += 1
            if kind.get(s) == "logic":
                cites_logic[s] += 1
        if i % 10000 == 0:
            print("    %s/%s" % (f"{i:,}", f"{len(thms):,}"))
    print("    done in %.1fs%s"
          % (time.time() - t0,
             ", %d skipped" % skipped if skipped else ""))

    print("\n  PROOF LENGTH")
    _dist(total, "all steps")
    _dist(logic_only, "logical only")
    st, sl = sum(total), sum(logic_only)
    if st:
        print("\n    %s of %s steps are formula-building: %.0f%%"
              % (f"{st - sl:,}", f"{st:,}", 100 * (st - sl) / st))
        print("    logical steps are %.1fx fewer than the raw count suggests."
              % (st / max(sl, 1)))
        print("\n    A geodesic measured in raw steps is measuring notation.")
        print("    The logical-only column is the length worth minimising.")

    longest = max(zip(total, thms))
    print("\n  longest proof   %s at %s steps"
          % (longest[1], f"{longest[0]:,}"))

    print("\n  MOST-CITED, ALL LABELS  (proofs citing it, of %s)"
          % f"{len(total):,}")
    for lab, n in sorted(cites_all.items(), key=lambda kv: -kv[1])[:10]:
        print("    %-12s %7s   %s" % (lab, f"{n:,}", kind.get(lab, "?")))

    print("\n  MOST-CITED LOGICAL LABELS  <- the real premise-selection prior")
    for lab, n in sorted(cites_logic.items(), key=lambda kv: -kv[1])[:15]:
        print("    %-12s %7s" % (lab, f"{n:,}"))
    print()


def cmd_show(a):
    mm = load(a.file)
    label = a.label
    if label not in mm.labels:
        near = [l for l in mm.labels if l.startswith(label[:4])][:12]
        print("\n  %s not found." % label)
        if near:
            print("  did you mean: %s" % ", ".join(near))
        return 1

    typ, data = mm.labels[label]
    print("\n" + "=" * 74)
    print("  %s   (%s)" % (label, typ))
    print("=" * 74)
    if typ in ("$e", "$f"):
        print("\n  %s\n" % " ".join(data))
        return 0

    dvs, f_hyps, e_hyps, stat = data
    print("\n  statement")
    print("    %s" % " ".join(stat))
    if f_hyps:
        print("\n  mandatory $f hypotheses (%d)" % len(f_hyps))
        for l, tc, v in f_hyps:
            print("    %-10s %s %s" % (l, tc, v))
    if e_hyps:
        print("\n  mandatory $e hypotheses (%d)" % len(e_hyps))
        for l, s in e_hyps:
            print("    %-10s %s" % (l, " ".join(s)))
    if dvs:
        print("\n  disjoint variables")
        print("    %s" % ", ".join("(%s,%s)" % p for p in sorted(dvs)))

    if typ == "$p":
        proof = mm.decompress(label, mm.proofs[label])
        print("\n  proof: %d steps" % len(proof))
        print("    %s" % " ".join(proof[:40]) + (" ..." if len(proof) > 40 else ""))
        t0 = time.time()
        try:
            r = mm.verify(label)
            print("\n  verification: %s  (%.3fs)" % (r.upper(), time.time() - t0))
            if r == "ok":
                print("  -> %s is a theorem: its proof reduces to exactly its"
                      % label)
                print("     statement under the substitution rule.")
        except MMError as e:
            print("\n  verification: FAILED\n    %s" % e)
    print()
    return 0


SELFTEST = r"""
$c 0 + = -> ( ) term wff |- $.
$v t r s P Q $.
tt $f term t $.   tr $f term r $.   ts $f term s $.
wp $f wff P $.    wq $f wff Q $.
tze $a term 0 $.
tpl $a term ( t + r ) $.
weq $a wff t = r $.
wim $a wff ( P -> Q ) $.
a1 $a |- ( t = r -> ( t = s -> r = s ) ) $.
a2 $a |- ( t + 0 ) = t $.
${ min $e |- P $.  maj $e |- ( P -> Q ) $.  mp $a |- Q $. $}

th1 $p |- t = t $=
  tt tze tpl tt weq tt tt weq tt a2 tt tze tpl
  tt weq tt tze tpl tt weq tt tt weq wim tt a2
  tt tze tpl tt tt a1 mp mp $.

th1c $p |- t = t $= ( tze tpl weq a2 wim a1 mp )
  ABCADAADAEABCADABCADAADFAEABCAAGHH $.

th1z $p |- t = t $= ( tze tpl weq a2 wim a1 mp )
  ABCADZAADAEIIAADFAEABCAAGHH $.

badstack $p |- t = t $=
  tt tze tpl tt weq tt tt weq tt a2 tt tze tpl
  tt weq tt tze tpl tt weq tt tt weq wim tt a2
  tt tze tpl tt tt a1 mp tze $.

badconcl $p |- t = t $= tt a2 $.

incomp $p |- t = t $= ? $.

$( ---- disjoint-variable cases ---------------------------------------- $)
$v x y z $.
vx $f term x $.   vy $f term y $.   vz $f term z $.
${ $d x y $.
   axd $a |- x = y $. $}
${ $d x z $.
   hdz   $e |- x = z $.
   elimd $a |- x = x $. $}

$( dummyvar proves |- x = x, whose only variable is x, via a proof that
   introduces z.  z is a DUMMY: it occurs nowhere in the statement, so it is
   absent from the mandatory frame, so the (x,z) condition it needs is absent
   from the mandatory DV set.  Checking the proof against the mandatory set
   rejects this -- which is how equid, ax7, exgen, spnfw and spsv failed. $)
${ $d x z $.
   dummyvar $p |- x = x $= vx vz vx vz axd elimd $. $}

$( dvbad applies axd with x and y both instantiated to x, violating $d x y.
   No $d is in scope.  MUST fail, or the DV check is vacuous. $)
dvbad $p |- x = x $= vx vx axd $.
"""

EXPECTED = {
    "th1":      "ok",          # uncompressed
    "th1c":     "ok",          # same proof, compressed
    "th1z":     "ok",          # same proof, compressed with Z backreferences
    "badstack": "fail",        # corrupted: wrong final step
    "badconcl": "fail",        # well-formed but proves the wrong statement
    "incomp":   "incomplete",  # contains ?
    "dummyvar": "ok",          # proof introduces a variable not in the statement
    "dvbad":    "fail",        # genuine disjoint-variable violation
}


def cmd_selftest(a):
    """Run the verifier against cases with known answers.

    A verifier that accepts everything is worthless, so half of these must
    FAIL.  th1/th1c/th1z are three encodings of one proof and must decode to
    byte-identical step lists -- that is what catches compression bugs."""
    print("\n" + "=" * 74)
    print("  metamath.py v%s  --  selftest" % VERSION)
    print("=" * 74 + "\n")

    mm = MM()
    mm.read(Toks(SELFTEST))

    steps = {}
    bad = 0
    for label, want in EXPECTED.items():
        try:
            got = mm.verify(label)
            steps[label] = len(mm.decompress(label, mm.proofs[label]))
        except MMError as e:
            got = "fail"
            steps[label] = None
        ok = (got == want)
        bad += (not ok)
        print("  %-9s expect %-11s got %-11s %s"
              % (label, want, got, "ok" if ok else "<-- WRONG"))

    n = {steps[k] for k in ("th1", "th1c", "th1z")}
    same = (len(n) == 1)
    print("\n  three encodings of one proof decode to %s"
          % ("the same %d steps  ok" % n.pop() if same
             else "DIFFERENT lengths %s  <-- WRONG" % sorted(x for x in n if x)))
    bad += (not same)

    print("\n  " + ("all checks passed" if not bad
                    else "%d CHECK(S) FAILED" % bad) + "\n")
    return 0 if not bad else 1


def cmd_search(a):
    """Find labels whose statement contains all the given tokens.

    Exists because guessing set.mm label names is unreliable.  Before writing
    'apply sbth here', check that sbth says what you think it says."""
    mm = load(a.file)
    kind = classify(mm)
    want = a.tokens
    hits = []
    for lab in mm.order:
        typ, data = mm.labels[lab]
        if typ in ("$e", "$f"):
            if a.all_types:
                stat = data
            else:
                continue
        else:
            stat = data[3]
        if a.logical_only and kind.get(lab) != "logic":
            continue
        if a.prefix and not lab.startswith(a.prefix):
            continue
        s = " ".join(stat)
        if all(w in s for w in want):
            hits.append((lab, typ, s))

    print("\n  %s match%s%s"
          % (f"{len(hits):,}", "" if len(hits) == 1 else "es",
             " for %s" % " + ".join(repr(w) for w in want) if want else ""))
    if a.prefix:
        print("  (label prefix %r)" % a.prefix)
    print()
    for lab, typ, s in hits[:a.limit]:
        if len(s) > 92:
            s = s[:89] + "..."
        print("    %-14s %-3s %s" % (lab, typ, s))
    if len(hits) > a.limit:
        print("\n    ... %s more (raise --limit)" % f"{len(hits) - a.limit:,}")
    print()


def main():
    ap = argparse.ArgumentParser(prog="metamath", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest", help="verify the verifier (no files needed)")

    q = sub.add_parser("search", help="find labels by statement content")
    q.add_argument("tokens", nargs="*", help="all of these must appear")
    q.add_argument("--file", default="set.mm")
    q.add_argument("--prefix", default=None, help="label starts with this")
    q.add_argument("--limit", type=int, default=40)
    q.add_argument("--logical-only", action="store_true",
                   help="skip grammar rules")
    q.add_argument("--all-types", action="store_true",
                   help="include $e and $f too")

    v = sub.add_parser("verify", help="verify proofs")
    v.add_argument("file", nargs="?", default="set.mm")
    v.add_argument("--limit", type=int, default=0, help="first N theorems")
    v.add_argument("--only", nargs="*", default=None, help="specific labels")
    v.add_argument("--progress", type=int, default=2000)
    v.add_argument("--show-failures", type=int, default=10)

    s = sub.add_parser("stats", help="corpus statistics")
    s.add_argument("file", nargs="?", default="set.mm")
    s.add_argument("--logical", action="store_true",
                   help="separate reasoning steps from formula-building steps "
                        "(decompresses every proof; slower)")

    w = sub.add_parser("show", help="show one theorem in full")
    w.add_argument("file", nargs="?", default="set.mm")
    w.add_argument("label")

    a = ap.parse_args()
    if a.cmd == "selftest": sys.exit(cmd_selftest(a))
    elif a.cmd == "search": cmd_search(a)
    elif a.cmd == "verify":  sys.exit(cmd_verify(a))
    elif a.cmd == "stats": cmd_stats(a)
    elif a.cmd == "show":  sys.exit(cmd_show(a))
    else: ap.print_help()


if __name__ == "__main__":
    sys.setrecursionlimit(20000)
    main()
