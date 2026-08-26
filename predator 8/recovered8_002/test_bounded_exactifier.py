import unittest

from bounded_exactifier import (
    bounded_bfs_exactify,
    IntervalSuccessor,
    interval_optimal_lock,
)
from settlement_authority import HorizonInterval


GRAPH = {
    "A": ["B", "C"],
    "B": ["S"],
    "C": ["D"],
    "D": ["S"],
    "S": [],
}


def succ(x):
    return GRAPH[x]


def settled(x):
    return x == "S"


class ExactifierTests(unittest.TestCase):
    def test_finds_exact_shortest_shell(self):
        r = bounded_bfs_exactify(
            "A",
            all_successors=succ,
            is_settled=settled,
            key=lambda x: x,
            max_depth=4,
            completeness_evidence="toy graph enumerates all edges",
        )
        self.assertEqual(r.exact_h, 2)
        self.assertEqual(r.interval().lower, 2)
        self.assertEqual(r.interval().upper, 2)

    def test_exhausted_radius_gives_lower_bound(self):
        r = bounded_bfs_exactify(
            "A",
            all_successors=succ,
            is_settled=settled,
            key=lambda x: x,
            max_depth=1,
            completeness_evidence="toy graph enumerates all edges",
        )
        self.assertIsNone(r.exact_h)
        self.assertEqual(r.lower_bound, 2)

    def test_interrupted_probe_keeps_only_safe_lower_bound(self):
        r = bounded_bfs_exactify(
            "A",
            all_successors=succ,
            is_settled=settled,
            key=lambda x: x,
            max_depth=4,
            max_expansions=0,
            completeness_evidence="toy graph enumerates all edges",
        )
        self.assertFalse(r.complete_to_requested_depth)
        self.assertEqual(r.lower_bound, 1)

    def test_interval_dominance_can_lock_without_exactifying_every_successor(self):
        d = interval_optimal_lock([
            IntervalSuccessor(
                "good", HorizonInterval(2, 2, "exact BFS shell")
            ),
            IntervalSuccessor(
                "other", HorizonInterval(3, float("inf"), "exhausted radius 2")
            ),
        ])
        self.assertEqual(d.stage, 2)
        self.assertEqual(d.selected_keys, ("good",))

    def test_overlapping_intervals_deny_lock(self):
        d = interval_optimal_lock([
            IntervalSuccessor("a", HorizonInterval(2, 4, "sound")),
            IntervalSuccessor("b", HorizonInterval(3, 5, "sound")),
        ])
        self.assertEqual(d.stage, 1)


if __name__ == "__main__":
    unittest.main()
