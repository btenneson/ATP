"""Compatibility launcher for Experiment 004.

This deliberately leaves the frozen experiment protocol unchanged.  It only
teaches json.dumps how to serialize NumPy scalar values emitted by the current
scikit-learn/NumPy stack, then executes the already-committed Experiment 004
script verbatim.
"""
from __future__ import annotations

import json
import runpy
from pathlib import Path

import numpy as np

_original_dumps = json.dumps


def _numpy_default(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _safe_dumps(obj, *args, **kwargs):
    user_default = kwargs.pop("default", None)
    if user_default is None:
        kwargs["default"] = _numpy_default
    else:
        def combined(value):
            try:
                return _numpy_default(value)
            except TypeError:
                return user_default(value)
        kwargs["default"] = combined
    return _original_dumps(obj, *args, **kwargs)


json.dumps = _safe_dumps

script = Path(__file__).with_name("compass_navigation_clean_shells_max.py")
runpy.run_path(str(script), run_name="__main__")
