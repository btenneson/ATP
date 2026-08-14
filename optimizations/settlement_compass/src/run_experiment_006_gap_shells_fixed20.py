"""Experiment 006: fill the 160->MAX gap with fixed test-20.

This is deliberately a protocol-preserving extension of Experiment 004.
It executes the committed Experiment 004 source after only these changes:
  * output filenames become experiment_006_*;
  * training shells become 320, 640, 1280, 2560;
  * MAX is retained for the frozen vocabulary/training universe but is not
    re-evaluated in this run;
  * the protocol label records that the test set remains the same frozen 20.

The GitHub Actions workflow separately checks the regenerated frozen objects
against the committed Experiment 004 manifest before accepting results.
"""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

import numpy as np

# Keep the repaired NumPy JSON compatibility behavior used for Experiment 004.
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

source_path = Path(__file__).with_name("compass_navigation_clean_shells_max.py")
source = source_path.read_text(encoding="utf-8")

replacements = {
    'MANIFEST_PATH = OUT_DIR / "experiment_004_manifest.json"':
        'MANIFEST_PATH = OUT_DIR / "experiment_006_manifest_full.json"',
    'RESULTS_PATH = OUT_DIR / "experiment_004_shell_results.json"':
        'RESULTS_PATH = OUT_DIR / "experiment_006_gap_shells_fixed20.json"',
    'ROWS_PATH = OUT_DIR / "experiment_004_rows.csv"':
        'ROWS_PATH = OUT_DIR / "experiment_006_gap_shells_fixed20_rows.csv"',
    'shell_sizes = [n for n in (10, 20, 40, 80, 160) if len(train_pool) >= n]':
        'shell_sizes = [n for n in (320, 640, 1280, 2560) if len(train_pool) >= n]',
    'ordered_labels = [str(n) for n in shell_sizes] + ["MAX"]':
        'ordered_labels = [str(n) for n in shell_sizes]',
    '"protocol": "Experiment 004 clean shells; retrospective proof-DAG navigation diagnostic; not ATP race",':
        '"protocol": "Experiment 006 gap shells 320/640/1280/2560 with Experiment-004 frozen test20; retrospective proof-DAG navigation diagnostic; not ATP race",',
}

for old, new in replacements.items():
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Experiment 006 patch expected one occurrence, found {count}: {old}")
    source = source.replace(old, new, 1)

with tempfile.TemporaryDirectory(prefix="compass_exp006_") as td:
    patched = Path(td) / "experiment_006_runtime.py"
    patched.write_text(source, encoding="utf-8")
    runpy.run_path(str(patched), run_name="__main__")
