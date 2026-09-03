from __future__ import annotations

import math
import unittest

from data_mind_3.control.transaction_geometry import (
    DirectedTransactionGraph,
    TransactionEdge,
)


class TransactionGeometryTests(unittest.TestCase):
    def test_directed_shortest_path(self) -> None:
        graph = DirectedTransactionGraph([
            TransactionEdge("A", "B", "r1", 2.0),
            TransactionEdge("B", "P", "r2", 3.0),
            TransactionEdge("A", "P", "expensive", 10.0),
        ])
        path = graph.shortest_path("A", "P")
        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(path.cost, 5.0)
        self.assertEqual(path.transactions, ("r1", "r2"))
        self.assertEqual(path.states, ("A", "B", "P"))

    def test_distance_is_directed(self) -> None:
        graph = DirectedTransactionGraph([
            TransactionEdge("A", "B", "forward", 1.0),
        ])
        self.assertEqual(graph.distance("A", "B"), 1.0)
        self.assertTrue(math.isinf(graph.distance("B", "A")))

    def test_repair_horizon_is_minimum_to_certified_completion(self) -> None:
        graph = DirectedTransactionGraph([
            TransactionEdge("A", "X", "rx", 1.0),
            TransactionEdge("X", "P1", "finish1", 4.0),
            TransactionEdge("A", "Y", "ry", 2.0),
            TransactionEdge("Y", "P2", "finish2", 1.0),
        ])
        H, target, path = graph.repair_horizon("A", ["P1", "P2"])
        self.assertEqual(H, 3.0)
        self.assertEqual(target, "P2")
        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(path.transactions, ("ry", "finish2"))

    def test_unreachable_completion_has_infinite_horizon(self) -> None:
        graph = DirectedTransactionGraph([
            TransactionEdge("A", "B", "r", 1.0),
        ])
        H, target, path = graph.repair_horizon("A", ["P"])
        self.assertTrue(math.isinf(H))
        self.assertIsNone(target)
        self.assertIsNone(path)

    def test_identity_distance_is_zero(self) -> None:
        graph = DirectedTransactionGraph()
        self.assertEqual(graph.distance("A", "A"), 0.0)

    def test_costs_must_be_positive_and_finite(self) -> None:
        with self.assertRaises(ValueError):
            TransactionEdge("A", "B", "bad", 0.0)
        with self.assertRaises(ValueError):
            TransactionEdge("A", "B", "bad", -1.0)
        with self.assertRaises(ValueError):
            TransactionEdge("A", "B", "bad", math.inf)


if __name__ == "__main__":
    unittest.main()
