from __future__ import annotations

from dataclasses import dataclass

from .error import ErrorVector
from .knobs import CreativityVector


KNOB_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "exploration",
        ("search_breadth", "divergence", "risk_tolerance", "abstraction_level"),
    ),
    (
        "guidance",
        ("heuristic_weighting", "goal_selection", "node_selection", "lemma_direction", "term_ordering"),
    ),
    (
        "commitment",
        ("search_depth", "resource_bias"),
    ),
)


@dataclass
class Trial:
    knob: str
    group: str
    mode: str
    before: CreativityVector
    baseline_loss: float
    start_expansion: int
    end_expansion: int


class ChildKnobPlayer:
    """Reversible local experimentation over the 11 creativity knobs.

    Ordinary play is fine tuning: one coordinate moves by a small bounded
    amount for a short trial window.  Under extreme sustained stagnation,
    one coordinate may instead receive the centered additive-group inverse.

    For c in [0,1], embed x = 2c - 1 in the ambient additive group R, take
    x -> -x, then map back.  The induced knob operation is c -> 1-c.

    A trial is kept only if the observed play loss improves.  Otherwise the
    entire creativity vector is restored to its pre-trial value.  This class
    never certifies a proof and never overrides Sentinel.
    """

    def __init__(
        self,
        *,
        interval: int,
        fine_step: float = 0.06,
        trial_updates: int = 4,
        inverse_after_rejections: int = 8,
    ) -> None:
        self.interval = max(4, int(interval))
        self.fine_step = max(0.01, min(0.12, float(fine_step)))
        self.trial_updates = max(2, int(trial_updates))
        self.inverse_after_rejections = max(4, int(inverse_after_rejections))
        self._cursor = 0
        self._rejections = 0
        self._trial: Trial | None = None

    @property
    def active(self) -> bool:
        return self._trial is not None

    @property
    def rejections(self) -> int:
        return self._rejections

    def _next_knob(self) -> tuple[str, str, int]:
        flat: list[tuple[str, str]] = []
        for group, knobs in KNOB_GROUPS:
            flat.extend((group, knob) for knob in knobs)
        idx = self._cursor
        group, knob = flat[idx % len(flat)]
        self._cursor += 1
        return group, knob, idx

    @staticmethod
    def play_loss(*, partial_credit: float, error: ErrorVector) -> float:
        """Loss for child trials; intentionally excludes absolute frontier.

        Absolute frontier is a safety/backlog variable.  Trial quality should
        respond to current proof-state quality, stagnation, branching and drift.
        """

        pc_loss = max(0.0, min(1.0, 1.0 - float(partial_credit)))
        return (
            0.50 * pc_loss
            + 0.25 * error.stagnation
            + 0.15 * error.branch
            + 0.10 * error.drift
        )

    def maybe_finish(
        self,
        *,
        expansion: int,
        creativity: CreativityVector,
        loss: float,
    ) -> tuple[CreativityVector, dict[str, object] | None]:
        trial = self._trial
        if trial is None or expansion < trial.end_expansion:
            return creativity, None

        improved = loss + 1e-9 < trial.baseline_loss
        if improved:
            after = creativity
            self._rejections = max(0, self._rejections - 1)
            decision = "keep"
        else:
            after = trial.before
            self._rejections += 1
            decision = "rollback"

        event = {
            "actor": "Child",
            "action": "knob_trial_result",
            "expansion": expansion,
            "group": trial.group,
            "knob": trial.knob,
            "mode": trial.mode,
            "decision": decision,
            "baseline_loss": trial.baseline_loss,
            "observed_loss": loss,
            "creativity_after": after.to_dict(),
            "consecutive_rejections": self._rejections,
        }
        self._trial = None
        return after, event

    def maybe_start(
        self,
        *,
        expansion: int,
        creativity: CreativityVector,
        loss: float,
        error: ErrorVector,
    ) -> tuple[CreativityVector, dict[str, object] | None]:
        if self._trial is not None:
            return creativity, None

        # Play is for controlled-but-stagnant search, not active explosions.
        if error.stagnation < 0.75 or error.branch > 0.12:
            return creativity, None

        group, knob, idx = self._next_knob()
        extreme = (
            error.stagnation >= 0.95
            and error.branch <= 0.05
            and self._rejections >= self.inverse_after_rejections
        )

        before = creativity
        if extreme:
            after = creativity.inverted(knob)
            mode = "group_inverse"
            # An inversion is an escape event.  Require another full run of
            # failed fine trials before a subsequent inverse is eligible.
            self._rejections = 0
        else:
            # Deterministic alternating sign preserves reproducibility while
            # still testing both sides of each coordinate.
            sign = 1.0 if ((idx // 11) % 2 == 0) else -1.0
            after = creativity.moved(**{knob: sign * self.fine_step})
            mode = "fine_tune"

        self._trial = Trial(
            knob=knob,
            group=group,
            mode=mode,
            before=before,
            baseline_loss=loss,
            start_expansion=expansion,
            end_expansion=expansion + self.trial_updates * self.interval,
        )
        return after, {
            "actor": "Child",
            "action": "knob_trial_start",
            "expansion": expansion,
            "group": group,
            "knob": knob,
            "mode": mode,
            "baseline_loss": loss,
            "trial_end_expansion": self._trial.end_expansion,
            "creativity_before": before.to_dict(),
            "creativity_trial": after.to_dict(),
        }
