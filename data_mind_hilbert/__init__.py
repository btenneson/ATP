"""Experimental Hilbert navigation for DATA MIND.

This package is intentionally separate from the production DATA MIND search
engine.  Experiment 001 changes search ordering only; proof legality and final
Metamath verification remain authoritative outside this package.
"""

from .geometry import (
    address_premise,
    hilbert_distance,
    hilbert_action_key,
)

__all__ = ["address_premise", "hilbert_distance", "hilbert_action_key"]
