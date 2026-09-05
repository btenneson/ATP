from __future__ import annotations

from data_mind_3.control.knobs import CreativityVector
from data_mind_3.control.reflective import ReflectiveP1Controller
from data_mind_3_3.experiments.exp001_config import dreamer_for_arm

EXPERIMENT_ID = "DATA MIND 3.3 Experiment 002 — Professor Actual-Call Throttle Frozen-20"
EXPERIMENT_SEED = 330002
ARMS = ("prof-off", "prof-16", "prof-64", "prof-256")
PROFESSOR_INTERVALS = {
    "prof-off": None,
    "prof-16": 16,
    "prof-64": 64,
    "prof-256": 256,
}
CONTROL_INTERVAL = 16
MAX_EXPANSIONS = 100_000
TIMEOUT_S = 1800.0
CANDIDATE_CAP = 64
MAX_DEPTH = 24
MAX_OPEN_GOALS = 24
MAX_FRONTIER = 200_000


class ProfessorOffController(ReflectiveP1Controller):
    """Experiment-only Professor-OFF arm: never invokes Professor.deliver()."""

    def _professor_due(self, expansion: int) -> bool:
        return False


def controller_for_arm(arm: str) -> ReflectiveP1Controller:
    if arm not in ARMS:
        raise ValueError(arm)
    interval = PROFESSOR_INTERVALS[arm]
    cls = ProfessorOffController if interval is None else ReflectiveP1Controller
    return cls(
        initial=CreativityVector(),
        interval=CONTROL_INTERVAL,
        professor_interval=(256 if interval is None else interval),
        experience=(),
        child_play=False,
    )


def disabled_dreamer():
    """Reuse the frozen EXP001 OFF Dreamer object; execution remains disabled."""
    return dreamer_for_arm("off")
