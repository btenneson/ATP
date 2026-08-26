#!/usr/bin/env python3
import unittest

import predator8_016_prcom_exactify as P
import predator8_017_fullgraph_exactify as F


class FakeTree:
    def __init__(self, name):
        self.name = name


class FakeStep:
    def __init__(self, label, fmap, data):
        self.label = label


class FakeNode:
    def __init__(self, goals, sub, trail, depth):
        self.goals = goals
        self.sub = sub
        self.trail = trail
        self.depth = depth


class FakeG:
    @staticmethod
    def parse(tokens, tc, by_tc):
        return FakeTree(tokens)


class FakeE:
    MMError = RuntimeError
    G = FakeG
    Step = FakeStep
    Node = FakeNode

    @staticmethod
    def apply_sub(g, sub):
        return g

    @staticmethod
    def rename_apart(t, m):
        return t

    @staticmethod
    def unify(a, b, sub):
        return dict(sub) if a.name == b.name else None

    @staticmethod
    def fresh(tc):
        return FakeTree("fresh")


class FakeIndex:
    by_tc = {}

    def candidates(self, goal):
        # One legal closer unique to each goal.
        data = (None, [], [], None)
        return ([("close_" + goal.name, FakeTree(goal.name), data)], [])


class FullGoalEnumerationTests(unittest.TestCase):
    def test_probe_branches_over_every_open_goal(self):
        ctx = F.FullGraphProbeContext(
            E=FakeE(), index=FakeIndex(), mm=None,
            target_data=(), fvar={}, fallback={})
        node = FakeNode(
            goals=[(FakeTree("g0"), None, 0), (FakeTree("g1"), None, 1)],
            sub={}, trail=(), depth=0)
        succ = list(ctx.all_successors(P.ProbeState(node=node)))
        self.assertEqual(len(succ), 2)
        # Each successor solved a different selected goal.
        remaining = sorted(child.node.goals[0][0].name for child in succ)
        self.assertEqual(remaining, ["g0", "g1"])


if __name__ == "__main__":
    unittest.main()
