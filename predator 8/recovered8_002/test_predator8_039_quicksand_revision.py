from __future__ import annotations

import math
import unittest

import predator8_039_quicksand_revision as Q


class Step:
    def __init__(self, lab):
        self.lab = lab


class Node:
    def __init__(self, labels):
        self.trail = tuple((None, None, Step(lab)) for lab in labels)


class QuicksandRevisionTests(unittest.TestCase):
    def test_raw_partial_certificate_bits_are_lossless_and_nonshrinking_on_append(self):
        a = Node(["a"])
        aa = Node(["a", "a"])
        self.assertGreater(Q.partial_certificate_bits(a), 0)
        self.assertGreaterEqual(
            Q.partial_certificate_bits(aa),
            Q.partial_certificate_bits(a),
        )

    def test_log_bit_density_can_improve_even_when_raw_length_grows(self):
        a = Node(["a"])
        aa = Node(["a", "a"])
        self.assertGreater(
            Q.partial_certificate_bits(aa),
            Q.partial_certificate_bits(a),
        )
        self.assertLess(Q.z_length(aa), Q.z_length(a))

    def test_bit_pressure_is_additive_group_inverse(self):
        beta = 0.12
        inv = Q.inverse_bit_pressure(beta)
        self.assertTrue(math.isclose(beta + inv, 0.0, abs_tol=1e-15))
        self.assertTrue(math.isclose(Q.inverse_bit_pressure(inv), beta, abs_tol=1e-15))

    def test_creativity_inverse_is_involution(self):
        c = 0.55
        inv = Q.inverse_creativity(c)
        self.assertTrue(0.0 < inv < 1.0)
        self.assertTrue(math.isclose(Q.inverse_creativity(inv), c, abs_tol=1e-15))

    def test_z_length_is_finite_for_empty_partial_certificate(self):
        self.assertTrue(math.isfinite(Q.z_length(Node([]))))


if __name__ == "__main__":
    unittest.main()
