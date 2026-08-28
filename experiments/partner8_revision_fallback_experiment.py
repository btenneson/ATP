#!/usr/bin/env python3
"""Controlled 8.038 mechanism experiment.

This is an architecture-level test of the universal revision fallback. It does
not claim a new theorem settlement. The existing four-pair AMLD smoke test is
run separately in CI to ensure the underlying eight-agent architecture still
passes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RECOVERED = ROOT / "predator 8" / "recovered8_002"
sys.path.insert(0, str(RECOVERED))

import predator8_038_eight_agent_revision_fallback as R

OUT = Path("p8_038_revision_fallback_record.json")


def verifier(z):
    return int(z["V"])


def failure_diagnostic(trajectory):
    """Failure score for minimization: progress low, stagnation/regression high."""
    if len(trajectory) < 2:
        return 0.0
    prev = float(trajectory[-2]["objective"])
    curr = float(trajectory[-1]["objective"])
    scale = max(1.0, abs(prev))
    improvement = prev - curr
    if improvement > 1e-12:
        return max(0.0, 0.5 - min(0.5, improvement / scale))
    if abs(improvement) <= 1e-12:
        return 0.75
    return min(1.0, 0.75 + (-improvement) / scale)


def logistic(x):
    if x >= 0:
        e = math.exp(-x)
        return 1.0 / (1.0 + e)
    e = math.exp(x)
    return e / (1.0 + e)


def gradient_optimizer(trajectory, vector):
    """One ordinary minimization step in logit coordinates."""
    grad = trajectory[-1]["gradient"]
    lr = 0.20
    out = {}
    for key, value in vector.items():
        x = float(value)
        logit = math.log(x / (1.0 - x))
        out[key] = logistic(logit - lr * float(grad[key]))
    return out


def make_policy(agent):
    return R.AgentRevisionPolicy(
        agent=agent,
        threshold=0.5,
        diagnostic=failure_diagnostic,
        optimizer=gradient_optimizer,
        groups={
            "exploration": R.GroupCoordinate.logit("exploration"),
            "novelty": R.GroupCoordinate.logit("novelty"),
            "reuse": R.GroupCoordinate.logit("reuse"),
        },
        verifier=verifier,
        min_post_revision_steps=1,
    )


def event(objective, g1, g2, g3, V=1):
    return {
        "V": V,
        "objective": float(objective),
        "gradient": {
            "exploration": float(g1),
            "novelty": float(g2),
            "reuse": float(g3),
        },
    }


def main():
    policies = {a: make_policy(a) for a in R.AGENTS}
    federation = R.EightAgentRevisionFallback(policies)

    initial = {
        a: {
            "exploration": 0.30 + 0.02 * i,
            "novelty": 0.70 - 0.02 * i,
            "reuse": 0.45 + 0.01 * i,
        }
        for i, a in enumerate(R.AGENTS)
    }

    # Partner 1 of each P/R/I/C role is making measurable progress.
    # Partner 2 is flat: D(T)=0.75 > tau and must use inverse revision.
    trajectories_1 = {}
    for a in R.AGENTS:
        if a.endswith("1"):
            trajectories_1[a] = [
                event(100.0, 0.8, -0.4, 0.2),
                event(92.0, 0.6, -0.3, 0.1),
            ]
        else:
            trajectories_1[a] = [
                event(100.0, -0.2, 0.5, -0.1),
                event(100.0, -0.2, 0.5, -0.1),
            ]

    vectors_1, decisions_1 = federation.step_all(trajectories_1, initial)

    for a in R.AGENTS:
        assert decisions_1[a]["V"] == 1
        expected = "optimization" if a.endswith("1") else "revision"
        assert decisions_1[a]["mode"] == expected, (a, decisions_1[a])

    # After the fallback, all eight receive a newly verified improving state.
    # Revision is a fallback, not a permanent mode; all resume optimization.
    trajectories_2 = {
        a: [
            event(100.0, 0.4, -0.2, 0.1),
            event(88.0, 0.3, -0.1, 0.05),
        ]
        for a in R.AGENTS
    }
    vectors_2, decisions_2 = federation.step_all(trajectories_2, vectors_1)
    for a in R.AGENTS:
        assert decisions_2[a]["V"] == 1
        assert decisions_2[a]["mode"] == "optimization", (a, decisions_2[a])

    # Negative control: V(z)=0 must be rejected before D(T) is consulted.
    rejected_unverified = False
    try:
        federation.step_agent(
            "P1",
            [event(10.0, 0.0, 0.0, 0.0), event(10.0, 0.0, 0.0, 0.0, V=0)],
            vectors_2["P1"],
        )
    except ValueError as exc:
        rejected_unverified = "V(z)=0" in str(exc)
    assert rejected_unverified

    record = {
        "version": "8.038-eight-agent-revision-fallback",
        "scientific_scope": "architecture-level mechanism test",
        "agents": list(R.AGENTS),
        "verifier_invariant": "V(z)=1 throughout",
        "threshold": 0.5,
        "pass1": {
            "decisions": decisions_1,
            "vectors": vectors_1,
        },
        "pass2": {
            "decisions": decisions_2,
            "vectors": vectors_2,
        },
        "negative_control_unverified_rejected": rejected_unverified,
        "checks": {
            "all_eight_present": len(decisions_1) == 8,
            "all_partner2_revision": all(
                decisions_1[a]["mode"] == "revision"
                for a in R.AGENTS if a.endswith("2")
            ),
            "all_partner1_optimization": all(
                decisions_1[a]["mode"] == "optimization"
                for a in R.AGENTS if a.endswith("1")
            ),
            "all_resume_optimization_after_verified_progress": all(
                decisions_2[a]["mode"] == "optimization" for a in R.AGENTS
            ),
            "V_equals_1_on_all_admitted_decisions": all(
                d["V"] == 1
                for block in (decisions_1, decisions_2)
                for d in block.values()
            ),
        },
    }
    assert all(record["checks"].values())
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    print("[P8.038] V(z)=1 throughout")
    for a in R.AGENTS:
        print(
            "[P8.038] agent=%s pass1 D(T)=%.6f tau=%.3f mode=%s pass2=%s"
            % (
                a,
                decisions_1[a]["D(T)"],
                decisions_1[a]["threshold"],
                decisions_1[a]["mode"],
                decisions_2[a]["mode"],
            )
        )
    print("[P8.038] negative-control V=0 rejected=%s" % rejected_unverified)
    print("[P8.038] ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
