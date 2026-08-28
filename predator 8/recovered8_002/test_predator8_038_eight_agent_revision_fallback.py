#!/usr/bin/env python3
from __future__ import annotations
import unittest

import predator8_038_eight_agent_revision_fallback as R


def verifier(z):
    return int(z["V"])


def identity_optimizer(_trajectory, vector):
    return dict(vector)


def low_D(_trajectory):
    return 0.25


def high_D(_trajectory):
    return 0.75


class RevisionFallbackTests(unittest.TestCase):
    def make_policy(self, agent, diagnostic, refractory=0):
        return R.AgentRevisionPolicy(
            agent=agent,
            threshold=0.5,
            diagnostic=diagnostic,
            optimizer=identity_optimizer,
            groups={
                "c1": R.GroupCoordinate.logit("c1"),
                "c2": R.GroupCoordinate.logit("c2"),
            },
            verifier=verifier,
            min_post_revision_steps=refractory,
        )

    def test_logit_inverse_is_group_inverse(self):
        g = R.GroupCoordinate.logit("c")
        for x in (0.1, 0.2, 0.37, 0.5, 0.8, 0.93):
            inv = g.invert(x)
            self.assertAlmostEqual(inv, 1.0 - x, places=12)
            self.assertAlmostEqual(g.compose(x, inv), 0.5, places=12)

    def test_low_d_uses_optimizer(self):
        p = self.make_policy("P1", low_D)
        nxt, info = p.step([{"V": 1}], {"c1": 0.2, "c2": 0.7})
        self.assertEqual(info["mode"], "optimization")
        self.assertEqual(info["V"], 1)
        self.assertEqual(nxt, {"c1": 0.2, "c2": 0.7})

    def test_high_d_uses_full_inverse(self):
        p = self.make_policy("R2", high_D)
        nxt, info = p.step([{"V": 1}], {"c1": 0.2, "c2": 0.7})
        self.assertEqual(info["mode"], "revision")
        self.assertAlmostEqual(nxt["c1"], 0.8)
        self.assertAlmostEqual(nxt["c2"], 0.3)

    def test_v_zero_is_rejected_before_diagnostic(self):
        called = {"d": False}
        def diagnostic(_trajectory):
            called["d"] = True
            return 1.0
        p = self.make_policy("I1", diagnostic)
        with self.assertRaisesRegex(ValueError, "V\\(z\\)=0"):
            p.step([{"V": 1}, {"V": 0}], {"c1": 0.2, "c2": 0.7})
        self.assertFalse(called["d"])

    def test_all_eight_are_mandatory(self):
        policies = {a: self.make_policy(a, low_D) for a in R.AGENTS[:-1]}
        with self.assertRaisesRegex(ValueError, "all eight agents"):
            R.EightAgentRevisionFallback(policies)

    def test_all_eight_decide_and_preserve_v(self):
        policies = {
            a: self.make_policy(a, high_D if a.endswith("2") else low_D)
            for a in R.AGENTS
        }
        federation = R.EightAgentRevisionFallback(policies)
        trajectories = {a: [{"V": 1}] for a in R.AGENTS}
        vectors = {a: {"c1": 0.2, "c2": 0.7} for a in R.AGENTS}
        next_vectors, decisions = federation.step_all(trajectories, vectors)
        self.assertEqual(set(decisions), set(R.AGENTS))
        for a in R.AGENTS:
            self.assertEqual(decisions[a]["V"], 1)
            want = "revision" if a.endswith("2") else "optimization"
            self.assertEqual(decisions[a]["mode"], want)
        for a in ("P2", "R2", "I2", "C2"):
            self.assertAlmostEqual(next_vectors[a]["c1"], 0.8)
            self.assertAlmostEqual(next_vectors[a]["c2"], 0.3)

    def test_refractory_step_prevents_immediate_pingpong(self):
        p = self.make_policy("C1", high_D, refractory=1)
        first, info1 = p.step([{"V": 1}], {"c1": 0.2, "c2": 0.7})
        second, info2 = p.step([{"V": 1}], first)
        third, info3 = p.step([{"V": 1}], second)
        self.assertEqual(info1["mode"], "revision")
        self.assertEqual(info2["mode"], "optimization")
        self.assertEqual(info3["mode"], "revision")


if __name__ == "__main__":
    unittest.main(verbosity=2)
