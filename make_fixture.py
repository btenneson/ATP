#!/usr/bin/env python3
r"""
make_fixture.py -- build a validation database for bench_p71.py.

Emits a Metamath file over set.mm's real propositional core

    ax-1  ( ph -> ( ps -> ph ) )
    ax-2  ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) )
    ax-3  ( ( -. ph -> -. ps ) -> ( ps -> ph ) )
    ax-mp

with negation actually in the language -- which predator71.SELFTEST does not
have.  SELFTEST declares `$c wff |- ( ) -> /\` and only ax1/ax2/ax-mp, so
every target mentioning `-.` was not unprovable on it, it was UNSTATABLE.

Theorems are derived by FORWARD saturation (condensed detachment).  Each
derived theorem carries a fully instantiated proof TREE, not just a formula:
at every detachment the most-general unifier is applied to the whole tree, so
each node records the instance actually used.  That is what makes the emitted
Metamath proofs correct.

Forward saturation is a different algorithm from Predator's backward
metavariable search, so grading targets by these proofs is not circular.

    python make_fixture.py --out fixture.mm --rounds 4
"""
from __future__ import annotations
import argparse, itertools, sys

sys.setrecursionlimit(20000)

VARS = ["ph", "ps", "ch", "th", "ta"]
FLAB = {"ph": "wph", "ps": "wps", "ch": "wch", "th": "wth", "ta": "wta"}
_ctr = itertools.count(1)


def fresh():
    return ("v", "$%d" % next(_ctr))


# --------------------------------------------------------------------------
# formulas: ('v', name) | ('-.', a) | ('->', a, b)
# --------------------------------------------------------------------------
def walk(t, s):
    while t[0] == "v" and t[1] in s:
        t = s[t[1]]
    return t


def occurs(v, t, s):
    t = walk(t, s)
    return t[1] == v if t[0] == "v" else any(occurs(v, k, s) for k in t[1:])


def unify(a, b, s):
    if s is None:
        return None
    a, b = walk(a, s), walk(b, s)
    if a[0] == "v":
        if a == b:
            return s
        if occurs(a[1], b, s):
            return None
        s = dict(s)
        s[a[1]] = b
        return s
    if b[0] == "v":
        return unify(b, a, s)
    if a[0] != b[0]:
        return None
    for x, y in zip(a[1:], b[1:]):
        s = unify(x, y, s)
        if s is None:
            return None
    return s


def app(t, s):
    t = walk(t, s)
    return t if t[0] == "v" else (t[0],) + tuple(app(k, s) for k in t[1:])


def size(t):
    return 1 if t[0] == "v" else 1 + sum(size(k) for k in t[1:])


def canon(t, m=None):
    if m is None:
        m = {}
    if t[0] == "v":
        return ("v", m.setdefault(t[1], "#%d" % len(m)))
    return (t[0],) + tuple(canon(k, m) for k in t[1:])


def show(t):
    if t[0] == "v":
        return t[1]
    if t[0] == "-.":
        return "-. " + show(t[1])
    return "( %s -> %s )" % (show(t[1]), show(t[2]))


# --------------------------------------------------------------------------
# proof trees:  ('ax', label, formula) | ('mp', minor, major, formula)
# --------------------------------------------------------------------------
def concl(n):
    return n[-1]


def tree_apply(n, s):
    if n[0] == "ax":
        return ("ax", n[1], app(n[2], s))
    return ("mp", tree_apply(n[1], s), tree_apply(n[2], s), app(n[3], s))


def tree_rename(n, m):
    def r(t):
        if t[0] == "v":
            return m.setdefault(t[1], fresh())
        return (t[0],) + tuple(r(k) for k in t[1:])
    if n[0] == "ax":
        return ("ax", n[1], r(n[2]))
    return ("mp", tree_rename(n[1], m), tree_rename(n[2], m), r(n[3]))


def tree_vars(n, acc):
    def g(t):
        if t[0] == "v":
            acc.add(t[1])
        else:
            for k in t[1:]:
                g(k)
    g(concl(n))
    if n[0] == "mp":
        tree_vars(n[1], acc)
        tree_vars(n[2], acc)
    return acc


def logic_steps(n):
    return 1 if n[0] == "ax" else 1 + logic_steps(n[1]) + logic_steps(n[2])


AX = {
    "ax-1": ("->", ("v", "a"), ("->", ("v", "b"), ("v", "a"))),
    "ax-2": ("->", ("->", ("v", "a"), ("->", ("v", "b"), ("v", "c"))),
             ("->", ("->", ("v", "a"), ("v", "b")),
              ("->", ("v", "a"), ("v", "c")))),
    "ax-3": ("->", ("->", ("-.", ("v", "a")), ("-.", ("v", "b"))),
             ("->", ("v", "b"), ("v", "a"))),
}


def match_one_way(pat, t, s):
    """Is `t` a substitution instance of `pat`?  Only pat's vars may bind."""
    if s is None:
        return None
    if pat[0] == "v":
        if pat[1] in s:
            return s if s[pat[1]] == t else None
        s = dict(s)
        s[pat[1]] = t
        return s
    if t[0] != pat[0]:
        return None
    for x, y in zip(pat[1:], t[1:]):
        s = match_one_way(x, y, s)
        if s is None:
            return None
    return s


def is_axiom_instance(f):
    """A target that some axiom matches outright is provable in ONE step and
    measures nothing.  Condensed detachment produces these -- ax-1 with
    ph := ( a -> a ) is not alpha-equivalent to ax-1 so dedup keeps it, but
    any prover closes it immediately."""
    return any(match_one_way(ax, f, {}) is not None for ax in AX.values())


def saturate(rounds, cap, maxvars):
    nodes = [("ax", lab, f) for lab, f in AX.items()]
    seen = {canon(concl(n)) for n in nodes}
    frontier = set(range(len(nodes)))
    for _ in range(rounds):
        new = []
        for j, maj in enumerate(nodes):
            if concl(maj)[0] != "->":
                continue
            for i, minor in enumerate(nodes):
                if i not in frontier and j not in frontier:
                    continue
                A = tree_rename(minor, {})
                B = tree_rename(maj, {})
                s = unify(concl(A), concl(B)[1], {})
                if s is None:
                    continue
                res = app(concl(B)[2], s)
                if size(res) > cap:
                    continue
                c = canon(res)
                if c in seen:
                    continue
                node = ("mp", tree_apply(A, s), tree_apply(B, s), res)
                if len(tree_vars(node, set())) > maxvars:
                    continue
                seen.add(c)
                new.append(node)
        if not new:
            break
        base = len(nodes)
        nodes.extend(new)
        frontier = set(range(base, len(nodes)))
    return nodes


# --------------------------------------------------------------------------
# emit
# --------------------------------------------------------------------------
HEADER = """$( Validation fixture for bench_p71.py -- set.mm's propositional core with
   negation, theorems derived by forward condensed detachment.
   Generated by make_fixture.py. $)

$c wff |- ( ) -> -. $.
$v ph ps ch th ta $.
wph $f wff ph $.
wps $f wff ps $.
wch $f wff ch $.
wth $f wff th $.
wta $f wff ta $.
wi $a wff ( ph -> ps ) $.
wn $a wff -. ph $.
ax-1 $a |- ( ph -> ( ps -> ph ) ) $.
ax-2 $a |- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) $.
ax-3 $a |- ( ( -. ph -> -. ps ) -> ( ps -> ph ) ) $.
${
  min $e |- ph $.
  maj $e |- ( ph -> ps ) $.
  ax-mp $a |- ps $.
$}
"""


def wff_rpn(t, out):
    if t[0] == "v":
        out.append(FLAB[t[1]])
    elif t[0] == "-.":
        wff_rpn(t[1], out)
        out.append("wn")
    else:
        wff_rpn(t[1], out)
        wff_rpn(t[2], out)
        out.append("wi")


def proof_rpn(n, out):
    """Mandatory hypotheses come in declaration order: the $f's for the
    variables the assertion mentions, then its $e's."""
    if n[0] == "ax":
        f, lab = n[2], n[1]
        if lab == "ax-1":            # ph, ps
            wff_rpn(f[1], out); wff_rpn(f[2][1], out)
        elif lab == "ax-2":          # ph, ps, ch
            wff_rpn(f[1][1], out); wff_rpn(f[1][2][1], out)
            wff_rpn(f[1][2][2], out)
        elif lab == "ax-3":          # ph, ps  (conclusion is ( ps -> ph ))
            wff_rpn(f[1][1][1], out); wff_rpn(f[1][2][1], out)
        out.append(lab)
        return
    _, minor, major, f = n
    wff_rpn(concl(minor), out)       # wph
    wff_rpn(f, out)                  # wps
    proof_rpn(minor, out)            # min
    proof_rpn(major, out)            # maj
    out.append("ax-mp")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fixture.mm")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--cap", type=int, default=13)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--maxvars", type=int, default=5)
    a = ap.parse_args()

    nodes = saturate(a.rounds, a.cap, a.maxvars)
    derived = [n for n in nodes if n[0] == "mp"]
    print("saturation derived %d theorems (%d total nodes)"
          % (len(derived), len(nodes)))
    trivial = [n for n in derived if is_axiom_instance(concl(n))]
    derived = [n for n in derived if not is_axiom_instance(concl(n))]
    print("dropped %d that are one-step axiom instances; %d remain"
          % (len(trivial), len(derived)))

    derived.sort(key=lambda n: (logic_steps(n), size(concl(n))))
    derived = derived[:a.limit]

    lines, count = [HEADER], 0
    for n in derived:
        vs = sorted(tree_vars(n, set()))
        if len(vs) > len(VARS):
            continue
        sub = {v: ("v", VARS[k]) for k, v in enumerate(vs)}
        node = tree_apply(n, sub)
        out = []
        try:
            proof_rpn(node, out)
        except (KeyError, IndexError, RecursionError):
            continue
        count += 1
        lines.append("$( logic steps: %d $)\nth%03d $p |- %s $= %s $."
                     % (logic_steps(node), count, show(concl(node)),
                        " ".join(out)))

    with open(a.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s with %d theorems" % (a.out, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
