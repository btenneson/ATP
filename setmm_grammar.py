#!/usr/bin/env python3
r"""
setmm_grammar.py -- parse set.mm statements into trees, and match them.

    python setmm_grammar.py selftest              no files needed
    python setmm_grammar.py roundtrip set.mm      parse everything, re-serialise
    python setmm_grammar.py tree set.mm canth     show one statement's parse
    python setmm_grammar.py match set.mm canth    what could conclude this goal

WHY THIS IS THE MISSING PIECE
-----------------------------
Predator_5 searches by computing the admissible one-step extensions of a state.
On the condensed-detachment fragment that is easy: unify two implicational
formulas.  On set.mm it is not, because a statement is a FLAT TOKEN SEQUENCE:

    |- ( ( A ~<_ B /\ B ~<_ A ) -> A ~~ B )

Nothing in that string says which tokens group with which.  Matching it against
another statement's conclusion requires knowing that it is an implication whose
antecedent is a conjunction -- that is, it requires a PARSE.

The grammar is already in the file.  Every syntax axiom is a production rule:

    wi  $a wff ( ph -> ps ) $.      <- "a wff may be ( wff -> wff )"
    wcel $a wff A e. B $.           <- "a wff may be class e. class"
    cvv $a class _V $.              <- "a class may be _V"

1,441 such rules in set.mm, against 1,559 that assert something.  Extracting
them and parsing with them turns the corpus from strings into trees, and only
then can a prover ask "which assertions could conclude this goal?"

This is also the two-phase split the corpus statistics pointed at.  95% of proof
STEPS are formula construction, and those steps are deterministic given the
formula -- they are exactly the parse tree, serialised.  A prover that builds
trees directly never searches for them.

THE ROUND-TRIP TEST
-------------------
Grammar extraction is easy to get subtly wrong, and a wrong grammar produces
plausible trees.  So the test is mechanical: parse every statement, serialise
the tree back to tokens, and require the result to equal the input exactly.
`roundtrip` reports the failure count.  It must be zero.

AMBIGUITY
---------
set.mm's syntax is designed to be unambiguous, but this parser does not assume
it.  `roundtrip --ambiguous` reports statements admitting more than one parse.
Any such statement is a place where "the" tree is not well defined and a matcher
built on it would be unsound.
"""
from __future__ import annotations
import argparse, os, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from metamath import MM, Toks, load, MMError
except ImportError:
    raise SystemExit("setmm_grammar.py needs metamath.py in the same folder")

WORKDIR = r"C:\google drive\Automated Theorem Proving"
if os.path.isdir(WORKDIR):
    os.chdir(WORKDIR)

# 30000 without a matching C stack is a segfault waiting to
# happen; _run_with_big_stack below supplies the stack.
sys.setrecursionlimit(8000)


# ===========================================================================
#  trees
# ===========================================================================
class Tree:
    """A parse node: a syntax rule applied to sub-trees, or a bare variable."""
    __slots__ = ("label", "typecode", "kids", "var")

    def __init__(self, label, typecode, kids=(), var=None):
        self.label = label          # syntax-rule label, or None for a variable
        self.typecode = typecode    # 'wff' | 'class' | 'setvar'
        self.kids = list(kids)
        self.var = var              # token, if this node IS a variable

    def tokens(self):
        """Serialise back to the flat token sequence."""
        if self.var is not None:
            return [self.var]
        out, k = [], 0
        for t in RULES[self.label][1]:
            if t in VARTYPE:
                out.extend(self.kids[k].tokens()); k += 1
            else:
                out.append(t)
        return out

    def size(self):
        return 1 + sum(k.size() for k in self.kids)

    def show(self, indent=0):
        pad = "  " * indent
        if self.var is not None:
            return "%s%s : %s\n" % (pad, self.var, self.typecode)
        s = "%s%s : %s\n" % (pad, self.label, self.typecode)
        for k in self.kids:
            s += k.show(indent + 1)
        return s

    def __repr__(self):
        return " ".join(self.tokens())


RULES = {}      # label -> (typecode, pattern tokens)
VARTYPE = {}    # variable token -> typecode
RULEIDX = {}    # (typecode, first constant | None) -> [(label, pat, minlen)]


def build_index(by_tc):
    """Bucket rules by the FIRST token of their pattern.

    Without this the parser tries every rule of a typecode at every span --
    set.mm has roughly a thousand `class` productions, so a forty-token
    statement costs about 1.6 million rule attempts and the corpus takes
    hours.  But a rule beginning with a constant can only match a span
    beginning with that same constant, and most set.mm productions begin with
    a constant such as '(' or a symbol.  Bucketing on it removes almost all of
    the attempts before they are made.

    Rules beginning with a VARIABLE have to be tried at every span and are
    kept in the None bucket.

    minlen is len(pattern): every element -- constant or variable -- consumes
    at least one token, so a span shorter than the pattern cannot match."""
    RULEIDX.clear()
    for tc, rules in by_tc.items():
        for lab, pat in rules:
            if not pat:
                continue
            first = None if pat[0] in VARTYPE else pat[0]
            RULEIDX.setdefault((tc, first), []).append((lab, pat, len(pat)))
    return RULEIDX


# ===========================================================================
#  grammar extraction
# ===========================================================================
def build_grammar(mm):
    """Every $a whose typecode is not '|-' is a production rule.

    A $f hypothesis types a variable.  Together these are a context-free
    grammar whose nonterminals are the typecodes."""
    RULES.clear(); VARTYPE.clear()
    for lab in mm.order:
        typ, data = mm.labels[lab]
        if typ == "$f":
            VARTYPE[data[1]] = data[0]
        elif typ == "$a":
            stat = data[3]
            if stat and stat[0] != "|-":
                RULES[lab] = (stat[0], list(stat[1:]))

    by_tc = defaultdict(list)
    for lab, (tc, pat) in RULES.items():
        by_tc[tc].append((lab, pat))
    build_index(by_tc)          # keep the first-token index in step
    return by_tc


# ===========================================================================
#  parsing
# ===========================================================================
def parse(tokens, typecode, by_tc, memo=None, all_parses=False, cap=4):
    """Parse tokens[0:] entirely as `typecode`.  Returns a Tree, or None.

    Bottom-up over spans with memoisation.  A rule matches a span when its
    constant tokens line up and each of its variables consumes a sub-span of
    that variable's own typecode.  Variables have no fixed width, so every
    split has to be tried; rules carry few variables so this stays cheap."""
    tokens = list(tokens)
    n = len(tokens)
    if memo is None:
        memo = {}

    if not RULEIDX:
        build_index(by_tc)
    vt = VARTYPE
    idx = RULEIDX

    _rf = {}

    def rules_for(tc, tok):
        """Rules that can start here: those beginning with this exact constant,
        plus those beginning with a variable.

        The concatenation is CACHED.  Building it per call was slower than the
        unbucketed scan it replaced -- set.mm's grammar is heavily infix
        (A e. B, A = B, A C_ B all begin with a variable), so the variable
        bucket is large and re-concatenating it at every span dominated."""
        key = (tc, tok)
        r = _rf.get(key)
        if r is None:
            a = idx.get(key) or ()
            b = idx.get((tc, None)) or ()
            r = (a + b) if (a and b) else (a or b or ())
            _rf[key] = r
        return r

    def go(i, j, tc):
        key = (i, j, tc)
        if key in memo:
            return memo[key]
        memo[key] = None                       # cycle guard
        found = []
        span = j - i

        # a single token that IS a variable of this typecode
        if span == 1 and vt.get(tokens[i]) == tc:
            found.append(Tree(None, tc, (), tokens[i]))

        if not (found and not all_parses):
            for lab, pat, minlen in rules_for(tc, tokens[i] if i < j else None):
                if span < minlen:              # every element eats >= 1 token
                    continue
                for kids in match(pat, 0, i, j):
                    found.append(Tree(lab, tc, kids))
                    if not all_parses:
                        break
                if found and not all_parses:
                    break
                if all_parses and len(found) >= cap:
                    break

        memo[key] = found if all_parses else (found[0] if found else None)
        return memo[key]

    def match(pat, p, i, j):
        """Yield lists of child trees for pat[p:] covering tokens[i:j]."""
        np_ = len(pat)
        if p == np_:
            if i == j:
                yield []
            return
        t = pat[p]
        if t not in vt:                         # a constant: must line up
            if i < j and tokens[i] == t:
                for rest in match(pat, p + 1, i + 1, j):
                    yield rest
            return
        tc = vt[t]
        # every remaining element after this one still needs >= 1 token
        tail = np_ - p - 1
        if p == np_ - 1:                        # last element: takes the rest
            sub = go(i, j, tc)
            if sub:
                for s in (sub if isinstance(sub, list) else [sub]):
                    yield [s]
            return
        for m in range(i + 1, j - tail + 1):
            sub = go(i, m, tc)
            if not sub:
                continue
            for s in (sub if isinstance(sub, list) else [sub]):
                for rest in match(pat, p + 1, m, j):
                    yield [s] + rest
                if not isinstance(sub, list):
                    break

    r = go(0, n, typecode)
    if all_parses:
        return r or []
    return r


def parse_statement(stat, by_tc):
    """Parse a full '|- ...' statement: drop the typecode, parse the rest."""
    if not stat:
        return None
    return parse(stat[1:], "wff", by_tc)


# ===========================================================================
#  matching: which assertions could conclude a goal
# ===========================================================================
def match_tree(pat, goal, subst):
    """One-way match: can `pat` (with variables) be instantiated to `goal`?

    Variables in the pattern bind to whole sub-trees of the goal.  A variable
    already bound must bind consistently.  This is matching, not unification:
    the goal is treated as ground."""
    if pat.var is not None:
        if pat.typecode != goal.typecode:
            return False
        prev = subst.get(pat.var)
        if prev is None:
            subst[pat.var] = goal
            return True
        return prev.tokens() == goal.tokens()
    if pat.label != goal.label or len(pat.kids) != len(goal.kids):
        return False
    return all(match_tree(a, b, subst) for a, b in zip(pat.kids, goal.kids))


def candidates(mm, by_tc, goal_tree, cache):
    """Assertions whose conclusion matches the goal.  These are the candidate
    last steps of a backward search, and their count is the branching factor
    that branching.py estimated by prefix indexing."""
    out = []
    for lab in mm.order:
        typ, data = mm.labels[lab]
        if typ not in ("$a", "$p"):
            continue
        stat = data[3]
        if not stat or stat[0] != "|-":
            continue
        t = cache.get(lab, ...)
        if t is ...:
            try:
                t = parse_statement(stat, by_tc)
            except (RecursionError, MMError):
                t = None
            cache[lab] = t
        if t is None:
            continue
        s = {}
        if match_tree(t, goal_tree, s):
            out.append((lab, s))
    return out


# ===========================================================================
#  commands
# ===========================================================================
SELFTEST = r"""
$c wff class |- ( ) -> e. _V $.
$v ph ps A B $.
wph $f wff ph $.
wps $f wff ps $.
cA  $f class A $.
cB  $f class B $.
cvv $a class _V $.
wcel $a wff A e. B $.
wi $a wff ( ph -> ps ) $.
ax1 $a |- ( ph -> ( ps -> ph ) ) $.
th $p |- ( A e. B -> ( _V e. B -> A e. B ) ) $= ? $.
"""


def cmd_selftest(_):
    print("\n" + "=" * 74)
    print("  setmm_grammar.py  --  selftest")
    print("=" * 74 + "\n")
    mm = MM(); mm.read(Toks(SELFTEST))
    by_tc = build_grammar(mm)
    print("  grammar: %d rules, %d typed variables" % (len(RULES), len(VARTYPE)))

    bad = 0
    cases = ["wcel", "wi", "ax1", "th"]
    for lab in cases:
        typ, data = mm.labels[lab]
        stat = data[3]
        tc = stat[0]
        t = parse_statement(stat, by_tc) if tc == "|-" else \
            parse(stat[1:], tc, by_tc)
        ok = t is not None and t.tokens() == list(stat[1:])
        bad += (not ok)
        print("  %-6s %-5s %-40s %s"
              % (lab, tc, " ".join(stat[1:])[:40], "ok" if ok else "<-- FAILED"))

    # matching: ax1's conclusion should match th's, binding ph and ps
    pat = parse_statement(mm.labels["ax1"][1][3], by_tc)
    goal = parse_statement(mm.labels["th"][1][3], by_tc)
    s = {}
    m = match_tree(pat, goal, s)
    print("\n  match ax1's conclusion against th's statement: %s"
          % ("ok" if m else "<-- FAILED"))
    if m:
        for v, t in sorted(s.items()):
            print("      %-4s := %s" % (v, " ".join(t.tokens())))
    bad += (not m)

    # a NON-match must be rejected
    s2 = {}
    bad_match = match_tree(goal, pat, s2)
    print("  reverse direction correctly rejected: %s"
          % ("ok" if not bad_match else "<-- FAILED, matcher is too permissive"))
    bad += bool(bad_match)

    print("\n  %s\n" % ("all checks passed" if not bad
                        else "%d CHECK(S) FAILED" % bad))
    return 0 if not bad else 1


def cmd_roundtrip(a):
    print("\n" + "=" * 74)
    print("  setmm_grammar.py  --  round-trip")
    print("=" * 74 + "\n")
    mm = load(a.file)
    by_tc = build_grammar(mm)
    print("\n  grammar: %s production rules, %s typed variables"
          % (f"{len(RULES):,}", f"{len(VARTYPE):,}"))

    labs = [l for l in mm.order
            if mm.labels[l][0] in ("$a", "$p")
            and mm.labels[l][1][3] and mm.labels[l][1][3][0] == "|-"]
    if a.sample:
        # Spread across the WHOLE corpus, not a prefix.  The first few thousand
        # set.mm statements are propositional and exercise a small corner of the
        # grammar; class abstractions, restricted quantifiers and the harder
        # constructors live later.  A prefix of 2,000 can pass while the grammar
        # is still wrong for most of the file.
        step = max(1, len(labs) // a.sample)
        labs = labs[::step][:a.sample]
        print("  sampling every %d-th statement across the corpus" % step)
    elif a.limit:
        labs = labs[:a.limit]
    print("  parsing %s '|-' statements...\n" % f"{len(labs):,}")

    t0 = time.time()
    ok = fail = err = 0
    shown = 0
    for i, lab in enumerate(labs, 1):
        stat = mm.labels[lab][1][3]
        try:
            t = parse_statement(stat, by_tc)
        except (RecursionError, MMError):
            err += 1; continue
        if t is None:
            fail += 1
            if shown < a.show:
                print("    NO PARSE  %-12s %s" % (lab, " ".join(stat[:16])))
                shown += 1
        elif t.tokens() != list(stat[1:]):
            fail += 1
            if shown < a.show:
                print("    MISMATCH  %-12s" % lab)
                print("       in  %s" % " ".join(stat[1:])[:80])
                print("       out %s" % " ".join(t.tokens())[:80])
                shown += 1
        else:
            ok += 1
        if a.progress and i % a.progress == 0:
            print("    %s/%s  (%.0f/s)"
                  % (f"{i:,}", f"{len(labs):,}", i / max(time.time() - t0, 1e-9)))

    dt = time.time() - t0
    print("\n  " + "-" * 70)
    print("  round-tripped %s" % f"{ok:,}")
    print("  FAILED        %s" % f"{fail:,}")
    print("  errored       %s" % f"{err:,}")
    print("  elapsed       %.1fs" % dt)
    print("  " + "-" * 70)
    if not fail and not err:
        print("""
  Every statement parsed and serialised back byte-identically.  The grammar
  extracted from the syntax axioms is therefore the grammar the corpus was
  written in, and the trees can be trusted for matching.
""")
    else:
        print("""
  Failures mean the extracted grammar is not the corpus's grammar.  Trees built
  with it would be wrong in ways a matcher cannot detect, so fix this before
  building anything on top.
""")
    return 0 if not (fail or err) else 1


def cmd_tree(a):
    mm = load(a.file)
    by_tc = build_grammar(mm)
    if a.label not in mm.labels:
        print("\n  %s not found\n" % a.label); return 1
    stat = mm.labels[a.label][1][3]
    print("\n  %s\n    %s\n" % (a.label, " ".join(stat)))
    t = parse_statement(stat, by_tc)
    if t is None:
        print("  NO PARSE\n"); return 1
    print(t.show(2))
    print("  tree size %d nodes, round-trip %s\n"
          % (t.size(), "ok" if t.tokens() == list(stat[1:]) else "FAILED"))
    return 0


def cmd_match(a):
    mm = load(a.file)
    by_tc = build_grammar(mm)
    if a.label not in mm.labels:
        print("\n  %s not found\n" % a.label); return 1
    stat = mm.labels[a.label][1][3]
    goal = parse_statement(stat, by_tc)
    if goal is None:
        print("\n  goal does not parse\n"); return 1

    print("\n" + "=" * 74)
    print("  BACKWARD CANDIDATES for %s" % a.label)
    print("=" * 74)
    print("\n  goal: %s\n" % " ".join(stat))
    print("  scanning %s assertions..." % f"{len(mm.order):,}")
    t0 = time.time()
    cands = candidates(mm, by_tc, goal, {})
    print("  %.1fs\n" % (time.time() - t0))
    print("  %d assertions could conclude this goal\n" % len(cands))
    for lab, s in cands[:a.limit or 25]:
        print("    %-14s %s" % (lab, " ".join(mm.labels[lab][1][3])[:64]))
    print("""
  That count IS the backward branching factor at this node -- measured by
  matching rather than estimated by prefix indexing.  It is the number a
  goal-directed prover faces, and the number a learned ranker would reorder.
""")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="setmm_grammar", description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest")
    r = sub.add_parser("roundtrip"); r.add_argument("file", nargs="?", default="set.mm")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--sample", type=int, default=0,
                   help="N statements spread across the whole corpus "
                        "(better coverage than a prefix of N)")
    r.add_argument("--show", type=int, default=10)
    r.add_argument("--progress", type=int, default=5000)
    t = sub.add_parser("tree"); t.add_argument("file", nargs="?", default="set.mm")
    t.add_argument("label")
    m = sub.add_parser("match"); m.add_argument("file", nargs="?", default="set.mm")
    m.add_argument("label"); m.add_argument("--limit", type=int, default=25)

    a = ap.parse_args()
    if a.cmd == "selftest":    sys.exit(cmd_selftest(a))
    elif a.cmd == "roundtrip": sys.exit(cmd_roundtrip(a))
    elif a.cmd == "tree":      sys.exit(cmd_tree(a))
    elif a.cmd == "match":     sys.exit(cmd_match(a))
    else:                      ap.print_help()


def _run_with_big_stack(fn):
    """Run fn on a thread with a large stack.

    sys.setrecursionlimit only raises PYTHON's guard; the C stack is a separate
    and much harder limit.  Raising the first without the second converts a
    clean RecursionError into a process-killing stack overflow -- no traceback,
    the shell simply exits.  That is what a deeply nested set.mm statement did
    to this parser.  A 256 MB thread stack makes the raised limit honest."""
    import threading
    try:
        threading.stack_size(256 * 1024 * 1024)
    except (ValueError, RuntimeError):
        try:
            threading.stack_size(64 * 1024 * 1024)
        except Exception:
            pass
    box = {}

    def target():
        try:
            box["rc"] = fn()
        except SystemExit as e:
            box["rc"] = e.code
        except RecursionError:
            print("\n  RecursionError: a statement nested deeper than the "
                  "stack allows.\n  This is the CLEAN failure -- the process "
                  "survived.\n")
            box["rc"] = 2
    t = threading.Thread(target=target, daemon=True)
    t.start()
    # join in slices so Ctrl-C reaches the main thread.  A bare join() blocks
    # uninterruptibly and a non-daemon worker keeps the process alive after it,
    # which is why Ctrl-C did nothing during a long search.
    try:
        while t.is_alive():
            t.join(0.2)
    except KeyboardInterrupt:
        print("\n  interrupted.\n")
        return 130
    return box.get("rc", 0)


if __name__ == "__main__":
    sys.exit(_run_with_big_stack(main) or 0)
