from __future__ import annotations

EXPERIMENT_ID = "DATA-MIND-HILBERT-ABLATION-001"
EXPERIMENT_TITLE = "Does Geometric Navigation Improve Verified Settlement?"

# Source/split inherited exactly from DATA-MIND set.mm Frozen-20 Benchmark 001.
SOURCE_SETMM_COMMIT = "f85a8edbb6df20dd5a64a9c159fa22944a3e54de"
SOURCE_SETMM_SHA256 = "19cb1ec229f3f11e36ff439a6381878864d9f2d4906f20fc9401346b309894e3"
CANONICAL_LOCK = "benchmarks/data-mind-3.1-frozen20-001/benchmark_lock.json"

# New deterministic target draw from the already-frozen 5% reverse-citation-leaf holdout.
TARGET_SELECTION_SEED = 314159
TARGET_COUNT = 50
P_TARGETS = 40
R_TARGETS = 10

# Search is deterministic in this pilot: one run per target/arm.  Repeated random
# seeds are intentionally deferred until a stochastic controller is introduced.
ARMS = ("A", "B", "C")
ARM_MODES = {"A": "off", "B": "naive", "C": "structural"}
ARM_DESCRIPTIONS = {
    "A": "matched non-Hilbert search-order control",
    "B": "naive hash-address Hilbert local navigation",
    "C": "structural-address Hilbert local navigation",
}

# Equal normalized search budget.  Wall-clock is a protective tripwire and a
# secondary outcome, not the primary budget definition.
MAX_EXPANSIONS = 20_000
TIMEOUT_S = 300.0
MAX_DEPTH = 24
MAX_OPEN_GOALS = 24
CANDIDATE_CAP = 64
MAX_FRONTIER = 200_000
HILBERT_BITS = 6
HILBERT_WEIGHT = 0.75

PRIMARY_ENDPOINT = "verifier-accepted settlement within 20,000 expansions"
