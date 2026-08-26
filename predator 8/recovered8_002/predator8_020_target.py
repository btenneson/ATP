#!/usr/bin/env python3
"""Target-generic launcher for Predator 8.020 C5 control-awareness ablation."""
from __future__ import annotations

import predator8_019_target as T
import predator8_020_c5_control as C

# Reuse the complete 8.019 target-generic runner and certificate protocol,
# replacing only its controller module with the C5 ablation controller.
T.S = C
T.VERSION = "8.020-C5-control-ablation-target-generic"

if __name__ == "__main__":
    raise SystemExit(T.main())
