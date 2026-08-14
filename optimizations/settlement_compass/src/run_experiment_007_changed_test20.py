"""Experiment 007: change WHICH 20 test theorems while sharing one trained compass.

Design:
  * cohort A is exactly the Experiment-004 frozen test20;
  * cohort B is a second disjoint frozen random 20;
  * all 40 are sealed before training-root selection, negative sampling, and
    vocabulary construction;
  * each training shell is fit once and evaluated on A, B, and pooled A+B;
  * shells are 320, 640, 1280, 2560.

This avoids the confound of training one model against A and another against B.
It remains a retrospective proof-DAG navigation diagnostic, not a controller
and not an end-to-end ATP race.
"""
from __future__ import annotations

import json
import runpy
import tempfile
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

source_path = Path(__file__).with_name("compass_navigation_clean_shells_max.py")
source = source_path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Experiment 007 patch expected one occurrence, found {count}: {old}")
    source = source.replace(old, new, 1)


replace_once(
    'MANIFEST_PATH = OUT_DIR / "experiment_004_manifest.json"',
    'MANIFEST_PATH = OUT_DIR / "experiment_007_manifest_full.json"',
)
replace_once(
    'RESULTS_PATH = OUT_DIR / "experiment_004_shell_results.json"',
    'RESULTS_PATH = OUT_DIR / "experiment_007_changed_test20_raw.json"',
)
replace_once(
    'ROWS_PATH = OUT_DIR / "experiment_004_rows.csv"',
    'ROWS_PATH = OUT_DIR / "experiment_007_changed_test20_rows.csv"',
)
replace_once(
    'SEED_TEST = 2026081301',
    'SEED_TEST = 2026081301\nSEED_TEST_B = 2026081401',
)
replace_once(
    'rng = random.Random(SEED_TEST)\ntest20 = sorted(rng.sample(base_pool, TEST_N))\ntestset = set(test20)',
    'rng = random.Random(SEED_TEST)\n'
    'test20 = sorted(rng.sample(base_pool, TEST_N))\n'
    'remaining_for_b = [lab for lab in base_pool if lab not in set(test20)]\n'
    'test20_b = sorted(random.Random(SEED_TEST_B).sample(remaining_for_b, TEST_N))\n'
    'test_all = test20 + test20_b\n'
    'testset = set(test_all)',
)
replace_once(
    'shell_sizes = [n for n in (10, 20, 40, 80, 160) if len(train_pool) >= n]',
    'shell_sizes = [n for n in (320, 640, 1280, 2560) if len(train_pool) >= n]',
)
replace_once(
    'for idx, root in enumerate(test20):',
    'for idx, root in enumerate(test_all):',
)
replace_once(
    'for root in test20:',
    'for root in test_all:',
)
replace_once(
    'SEED_TEST_CAND + 100000 + test20.index(root)',
    'SEED_TEST_CAND + 100000 + test_all.index(root)',
)
replace_once(
    'ordered_labels = [str(n) for n in shell_sizes] + ["MAX"]',
    'ordered_labels = [str(n) for n in shell_sizes]',
)
replace_once(
    '"protocol": "Experiment 004 clean shells; retrospective proof-DAG navigation diagnostic; not ATP race",',
    '"protocol": "Experiment 007 changed-test20 A/B cohorts with joint 40-target sealing; retrospective proof-DAG navigation diagnostic; not ATP race",',
)
replace_once(
    '"test": SEED_TEST,',
    '"test": SEED_TEST,\n        "test_b": SEED_TEST_B,',
)

# Add B/all cohort labels to both the manifest and result payload occurrences.
needle = '"test20": test20,'
count = source.count(needle)
if count != 2:
    raise SystemExit(f"Experiment 007 expected two test20 payload occurrences, found {count}")
source = source.replace(
    needle,
    '"test20": test20,\n    "test20_b": test20_b,\n    "test_all": test_all,',
)

with tempfile.TemporaryDirectory(prefix="compass_exp007_") as td:
    patched = Path(td) / "experiment_007_runtime.py"
    patched.write_text(source, encoding="utf-8")
    runpy.run_path(str(patched), run_name="__main__")

# Compact cohort-level summary from the raw per-target rows.
out_dir = Path(__import__('os').environ.get('COMPASS_RESULTS_DIR', 'optimizations/settlement_compass/results'))
manifest = json.loads((out_dir / 'experiment_007_manifest_full.json').read_text())
raw = json.loads((out_dir / 'experiment_007_changed_test20_raw.json').read_text())
A = set(manifest['test20'])
B = set(manifest['test20_b'])


def cohort_aggregate(rows, pooled):
    if not rows:
        return None
    return {
        'n_test': len(rows),
        'mean_auc': float(np.mean([r['auc'] for r in rows])),
        'mean_spearman_distance': float(np.nanmean([r['spearman_distance'] for r in rows])),
        'mean_mae_distance': float(np.mean([r['mae_distance'] for r in rows])),
        'median_compass_rank_first_dag': float(np.median([r['compass_rank_first_dag'] for r in rows])),
        'median_compass_rank_first_direct_parent': float(np.median([r['compass_rank_first_direct_parent'] for r in rows])),
        'mean_precision_at_10': float(np.mean([r['precision_at_10'] for r in rows])),
        'compass_beats_random_direct_parent': int(sum(
            r['compass_rank_first_direct_parent'] < r['random_rank_first_direct_parent'] for r in rows
        )),
        'random_beats_compass_direct_parent': int(sum(
            r['compass_rank_first_direct_parent'] > r['random_rank_first_direct_parent'] for r in rows
        )),
        'n_train': pooled['n_train'],
        'n_training_classifier_examples': pooled['n_training_classifier_examples'],
        'n_training_regression_examples': pooled['n_training_regression_examples'],
    }

cohorts = []
for pooled in raw['aggregates']:
    shell = str(pooled['shell'])
    rows = [r for r in raw['rows'] if str(r['shell']) == shell]
    rows_a = [r for r in rows if r['target'] in A]
    rows_b = [r for r in rows if r['target'] in B]
    agg_a = cohort_aggregate(rows_a, pooled)
    agg_b = cohort_aggregate(rows_b, pooled)
    agg_all = cohort_aggregate(rows, pooled)
    cohorts.append({
        'shell': shell,
        'A_original20': agg_a,
        'B_new20': agg_b,
        'pooled40': agg_all,
        'B_minus_A': {
            'mean_auc': agg_b['mean_auc'] - agg_a['mean_auc'],
            'mean_spearman_distance': agg_b['mean_spearman_distance'] - agg_a['mean_spearman_distance'],
            'mean_mae_distance': agg_b['mean_mae_distance'] - agg_a['mean_mae_distance'],
            'mean_precision_at_10': agg_b['mean_precision_at_10'] - agg_a['mean_precision_at_10'],
            'median_direct_parent_rank': (
                agg_b['median_compass_rank_first_direct_parent'] -
                agg_a['median_compass_rank_first_direct_parent']
            ),
        },
    })

summary = {
    'experiment': 7,
    'protocol': manifest['protocol'],
    'test20_A': manifest['test20'],
    'test20_B': manifest['test20_b'],
    'test40_jointly_sealed': manifest['test_all'],
    'test_seed_A': SEED_TEST,
    'test_seed_B': SEED_TEST_B,
    'training_shells': [320, 640, 1280, 2560],
    'max_training_roots_after_joint40_seal': manifest['max_n'],
    'setmm_sha256': manifest['setmm_sha256'],
    'vocabulary_sha256': manifest['vocabulary_sha256'],
    'cohort_results': cohorts,
    'interpretation_guardrail': (
        'A and B share the same fitted compass within each shell. This tests theorem-mix sensitivity; '
        'it does not convert the compass into a learned closed-loop controller.'
    ),
}
(out_dir / 'experiment_007_changed_test20_summary.json').write_text(
    json.dumps(summary, indent=2, sort_keys=True) + '\n'
)
