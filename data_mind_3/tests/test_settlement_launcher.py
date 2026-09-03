from __future__ import annotations

import unittest

from experiments.dm31_settle_frozen20_target import (
    ALL_AGENTS,
    validate_result,
)


def activity(initialized: bool = True) -> dict[str, dict[str, object]]:
    return {
        name: {"initialized": initialized, "activations": 0}
        for name in ALL_AGENTS
    }


class SettlementLauncherTests(unittest.TestCase):
    def test_unknown_with_all_eight_accounted_is_schema_valid(self) -> None:
        result = {
            "target": "example",
            "status": "UNKNOWN",
            "agent_activity": activity(),
            "silent_component_substitution": False,
        }
        validate_result(result, "example")

    def test_missing_agent_is_rejected(self) -> None:
        a = activity()
        a.pop("C2")
        with self.assertRaises(RuntimeError):
            validate_result(
                {
                    "target": "example",
                    "status": "UNKNOWN",
                    "agent_activity": a,
                },
                "example",
            )

    def test_uninitialized_agent_is_rejected(self) -> None:
        a = activity()
        a["I1"]["initialized"] = False
        with self.assertRaises(RuntimeError):
            validate_result(
                {
                    "target": "example",
                    "status": "UNKNOWN",
                    "agent_activity": a,
                },
                "example",
            )

    def test_component_substitution_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_result(
                {
                    "target": "example",
                    "status": "PROVED",
                    "agent_activity": activity(),
                    "silent_component_substitution": True,
                },
                "example",
            )

    def test_wrong_target_or_status_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_result(
                {"target": "wrong", "status": "UNKNOWN", "agent_activity": activity()},
                "example",
            )
        with self.assertRaises(RuntimeError):
            validate_result(
                {"target": "example", "status": "MAYBE", "agent_activity": activity()},
                "example",
            )


if __name__ == "__main__":
    unittest.main()
