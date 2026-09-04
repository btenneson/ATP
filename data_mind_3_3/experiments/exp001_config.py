from __future__ import annotations

import hashlib

from data_mind_3.control.agents import EscapeAction
from data_mind_3.control.knobs import CreativityVector
from data_mind_3.control.reflective import ReflectiveP1Controller
from data_mind_3_2.epistemic.oracle_dynamics import OracleFacet
from data_mind_3_3.dreamer import (
    DreamerContext,
    LogicalDreamer,
    OracleAccessMask,
    OracleResponse,
    OracleThrottle,
    PromotionThrottle,
)
from data_mind_3_3.oracles import StrategyAdvice, default_oracle_interfaces


EXPERIMENT_ID = "DATA MIND 3.3 Experiment 001 — Logical Dreamer Frozen-20 Mechanism"
EXPERIMENT_SEED = 330001
ARMS = ("off", "placebo-o3", "o3", "o34", "o1234")
ARM_ACCESS_BITS = {
    "off": (0, 0, 0, 0),
    "placebo-o3": (0, 0, 1, 0),
    "o3": (0, 0, 1, 0),
    "o34": (0, 0, 1, 1),
    "o1234": (1, 1, 1, 1),
}

CONTROL_INTERVAL = 16
PROFESSOR_INTERVAL = 256
# Frozen-20's permanent evaluation protocol gives each target 1800 seconds.
# The expansion cap is a common 3.3 safety cap; the time budget remains the
# canonical scientific budget and is not shortened for convenience.
MAX_EXPANSIONS = 100_000
TIMEOUT_S = 1800.0
CANDIDATE_CAP = 64
MAX_DEPTH = 24
MAX_OPEN_GOALS = 24
MAX_FRONTIER = 200_000

ORACLE_THROTTLES = {
    OracleFacet.O1_ROLE: OracleThrottle(max_calls=128, min_steps_between_calls=64),
    OracleFacet.O2_RESOURCE: OracleThrottle(max_calls=512, min_steps_between_calls=16),
    OracleFacet.O3_STRATEGY: OracleThrottle(max_calls=128, min_steps_between_calls=64),
    OracleFacet.O4_CERTIFICATE: OracleThrottle(max_calls=32, min_steps_between_calls=256),
}
PROMOTION_THROTTLE = PromotionThrottle(max_promotions=64, min_steps_between_promotions=64)

PLACEBO_ACTIONS = (
    EscapeAction.REPAIR,
    EscapeAction.FINE_TUNE,
    EscapeAction.BACKFILL_LEMMA,
    EscapeAction.SWITCH_BASIN,
    EscapeAction.FALLBACK,
)


def placebo_strategy_oracle(context: DreamerContext) -> OracleResponse:
    """Deterministic theorem-independent perturbation control at O3 call sites."""
    material = f"{EXPERIMENT_SEED}|{context.target_id}|{context.step}".encode("utf-8")
    index = int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % len(PLACEBO_ACTIONS)
    advice = StrategyAdvice(
        action=PLACEBO_ACTIONS[index],
        confidence=0.65,
        basis=("deterministic_placebo", "matched_O3_call_surface"),
    )
    return OracleResponse(
        OracleFacet.O3_STRATEGY,
        advice=advice,
        confidence=advice.confidence,
        reported_cost=1.0,
        provenance={
            "adapter": "exp001_deterministic_placebo_o3",
            "seed": EXPERIMENT_SEED,
            "cost_units": "adapter_call",
        },
    )


def controller_for_exp001() -> ReflectiveP1Controller:
    return ReflectiveP1Controller(
        initial=CreativityVector(),
        interval=CONTROL_INTERVAL,
        professor_interval=PROFESSOR_INTERVAL,
        experience=(),
        child_play=False,
    )


def dreamer_for_arm(arm: str) -> LogicalDreamer:
    if arm not in ARMS:
        raise ValueError(arm)
    interfaces = default_oracle_interfaces()
    if arm == "placebo-o3":
        interfaces[OracleFacet.O3_STRATEGY] = placebo_strategy_oracle
    return LogicalDreamer(
        interfaces,
        access=OracleAccessMask.from_bits(ARM_ACCESS_BITS[arm]),
        throttles=ORACLE_THROTTLES,
        promotion_throttle=PROMOTION_THROTTLE,
        source_agent=f"DREAMER-3.3-EXP001-{arm}",
    )
