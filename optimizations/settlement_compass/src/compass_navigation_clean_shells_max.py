"""Experiment 004: clean settlement-compass learning curve with MAX training case.

The experiment freezes the test targets, per-root negative samples, per-target
candidate pools, feature coordinates, model settings, and random draws before
comparing nested positive proof-DAG shells. Each shell is fit from scratch.

This is a retrospective proof-DAG navigation diagnostic, not an end-to-end ATP
proof race.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, roc_auc_score

SETMM = Path(os.environ.get("SETMM_PATH", "set.mm"))
OUT_DIR = Path(os.environ.get("COMPASS_RESULTS_DIR", "optimizations/settlement_compass/results"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST_PATH = OUT_DIR / "experiment_004_manifest.json"
RESULTS_PATH = OUT_DIR / "experiment_004_shell_results.json"
ROWS_PATH = OUT_DIR / "experiment_004_rows.csv"

EXPECTED_SETMM_SHA256 = "7b70cd8cca88aeb72a8dd97029d0b506015fb0325afec581cdc9add8ca0c8547"
SEED_TEST = 2026081301
SEED_ORDER = 2026081302
SEED_NEG = 2026081303
SEED_TEST_CAND = 2026081304
SEED_MODEL = 2026081305
TEST_N = 20
NEG_CAP = 200
TEST_NEG_MULT = 5
TEST_NEG_MIN = 100

VEC_PARAMS = dict(
    tokenizer=str.split,
    token_pattern=None,
    lowercase=False,
    ngram_range=(1, 2),
    min_df=2,
    max_features=30000,
    sublinear_tf=True,
)
CLF_PARAMS = dict(max_iter=500, class_weight="balanced", C=2.0, random_state=SEED_MODEL)
REG_PARAMS = dict(alpha=5.0)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True))
    tmp.replace(path)


actual_hash = sha256_file(SETMM)
if actual_hash != EXPECTED_SETMM_SHA256:
    raise SystemExit(f"set.mm hash mismatch: {actual_hash}")

text = SETMM.read_text(encoding="utf-8", errors="ignore")
clean = re.sub(r"\$\((?:.|\n)*?\$\)", " ", text)
tokens = clean.split()
ths = []
scopes = [[]]
i = 0
while i < len(tokens):
    tok = tokens[i]
    if tok == "${":
        scopes.append([]); i += 1; continue
    if tok == "$}":
        scopes.pop(); i += 1; continue
    if tok in ("$c", "$v", "$d"):
        j = i + 1
        while tokens[j] != "$.": j += 1
        i = j + 1; continue
    if tok == "$[":
        j = i + 1
        while tokens[j] != "$]": j += 1
        i = j + 1; continue
    label = tok
    if i + 1 >= len(tokens): break
    typ = tokens[i + 1]
    if typ in ("$f", "$e", "$a"):
        j = i + 2
        expr = []
        while tokens[j] != "$.": expr.append(tokens[j]); j += 1
        if typ == "$e": scopes[-1].append((label, " ".join(expr)))
        i = j + 1; continue
    if typ == "$p":
        j = i + 2
        expr = []
        while tokens[j] != "$=": expr.append(tokens[j]); j += 1
        proof = []
        j += 1
        while tokens[j] != "$.": proof.append(tokens[j]); j += 1
        if proof and proof[0] == "(":
            try:
                close = proof.index(")")
                deps = proof[1:close]
            except ValueError:
                deps = []
        else:
            deps = [x for x in proof if x != "?"]
        active_hyps = sum(len(s) for s in scopes)
        ths.append({"label": label, "stmt": " ".join(expr), "deps": deps, "pos": i, "hyps": active_hyps})
        i = j + 1; continue
    i += 1

emap = {t["label"]: t for t in ths}
inf0_pos = emap["inf0"]["pos"]
pre = [t for t in ths if t["pos"] < inf0_pos]
pre_labels = {t["label"] for t in pre}


@lru_cache(None)
def closure_tuple(root: str):
    seen = set()
    stack = [root]
    while stack:
        lab = stack.pop()
        t = emap.get(lab)
        if not t: continue
        for d in t["deps"]:
            if d in emap and d not in seen:
                seen.add(d); stack.append(d)
    return tuple(sorted(seen))


def closure(root: str):
    return set(closure_tuple(root))


@lru_cache(None)
def distance_items(root: str):
    nodes = {root} | closure(root)
    rev = defaultdict(list)
    for lab in nodes:
        for d in emap[lab]["deps"]:
            if d in nodes:
                rev[lab].append(d)
    dist = {root: 0}
    q = deque([root])
    while q:
        x = q.popleft()
        for d in rev[x]:
            if d not in dist:
                dist[d] = dist[x] + 1
                q.append(d)
    return tuple(sorted(dist.items()))


def distances(root: str):
    return dict(distance_items(root))


def pair_text(root: str, node: str) -> str:
    return "ROOT " + emap[root]["stmt"] + " CAND " + emap[node]["stmt"]


# Universe candidates before sealing test targets.
def base_eligible(t):
    lab = t["label"]
    if t["pos"] >= inf0_pos or t["hyps"] != 0 or "OLD" in lab:
        return False
    d = distances(lab)
    if len(d) < 12:
        return False
    if max(d.values(), default=0) < 3:
        return False
    return True

base_pool = sorted(t["label"] for t in pre if base_eligible(t))
if len(base_pool) < TEST_N + 80:
    raise SystemExit("not enough eligible roots for clean shell experiment")

rng = random.Random(SEED_TEST)
test20 = sorted(rng.sample(base_pool, TEST_N))
testset = set(test20)

# Strict anti-leakage: no training root may depend transitively on any test root.
train_pool = [lab for lab in base_pool if lab not in testset and not (closure(lab) & testset)]
rng = random.Random(SEED_ORDER)
rng.shuffle(train_pool)

shell_sizes = [n for n in (10, 20, 40, 80, 160) if len(train_pool) >= n]
shells = {str(n): train_pool[:n] for n in shell_sizes}
shells["MAX"] = list(train_pool)

# Freeze negative examples for every possible training root.
frozen_negatives = {}
for idx, root in enumerate(train_pool):
    d = distances(root)
    negpool = sorted(pre_labels - set(d) - {root} - testset)
    k = min(max(50, min(NEG_CAP, max(1, len(d) - 1))), len(negpool))
    rr = random.Random(SEED_NEG + idx)
    frozen_negatives[root] = sorted(rr.sample(negpool, k)) if k else []

# Freeze test candidate pools, independent of shell size.
frozen_test_negs = {}
for idx, root in enumerate(test20):
    d = distances(root)
    positives = [n for n in d if n != root]
    negpool = sorted(pre_labels - set(d) - {root} - testset)
    k = min(max(TEST_NEG_MIN, TEST_NEG_MULT * len(positives)), len(negpool))
    rr = random.Random(SEED_TEST_CAND + idx)
    frozen_test_negs[root] = sorted(rr.sample(negpool, k)) if k else []

# Freeze one feature coordinate system from MAX training-universe text only.
# No test labels, test candidates, or test outcomes are used here.
vocab_text = []
for root in train_pool:
    d = distances(root)
    for node in d:
        if node != root:
            vocab_text.append(pair_text(root, node))
    for node in frozen_negatives[root]:
        vocab_text.append(pair_text(root, node))

vocab_vectorizer = TfidfVectorizer(**VEC_PARAMS)
vocab_vectorizer.fit(vocab_text)
frozen_vocab = dict(vocab_vectorizer.vocabulary_)
vocab_hash = hashlib.sha256(json.dumps(frozen_vocab, sort_keys=True).encode()).hexdigest()

manifest = {
    "protocol": "Experiment 004 clean shells; retrospective proof-DAG navigation diagnostic; not ATP race",
    "setmm_sha256": actual_hash,
    "seeds": {
        "test": SEED_TEST,
        "order": SEED_ORDER,
        "negative": SEED_NEG,
        "test_candidates": SEED_TEST_CAND,
        "model": SEED_MODEL,
    },
    "test20": test20,
    "ordered_training_roots": train_pool,
    "shells": shells,
    "max_n": len(train_pool),
    "frozen_negatives": frozen_negatives,
    "frozen_test_negatives": frozen_test_negs,
    "vectorizer_params": {k: str(v) if callable(v) else v for k, v in VEC_PARAMS.items()},
    "vocabulary_sha256": vocab_hash,
    "vocabulary_size": len(frozen_vocab),
    "classifier_params": CLF_PARAMS,
    "regressor_params": REG_PARAMS,
}
atomic_json(MANIFEST_PATH, manifest)


def make_vectorizer():
    return TfidfVectorizer(vocabulary=frozen_vocab, **VEC_PARAMS)


def fit_and_eval(train_roots, shell_label):
    t0 = time.perf_counter()
    X_cls, y_cls, X_reg, y_reg = [], [], [], []
    for root in train_roots:
        d = distances(root)
        for n, dv in d.items():
            if n == root: continue
            txt = pair_text(root, n)
            X_cls.append(txt); y_cls.append(1)
            X_reg.append(txt); y_reg.append(dv)
        for n in frozen_negatives[root]:
            X_cls.append(pair_text(root, n)); y_cls.append(0)

    vec_cls = make_vectorizer()
    Xc = vec_cls.fit_transform(X_cls)
    clf = LogisticRegression(**CLF_PARAMS)
    clf.fit(Xc, y_cls)

    vec_reg = make_vectorizer()
    Xr = vec_reg.fit_transform(X_reg)
    reg = Ridge(**REG_PARAMS)
    reg.fit(Xr, y_reg)
    train_seconds = time.perf_counter() - t0

    rows = []
    t1 = time.perf_counter()
    for root in test20:
        d = distances(root)
        positives = [n for n in d if n != root]
        direct = {n for n, v in d.items() if v == 1}
        negs = frozen_test_negs[root]
        cands = positives + negs
        texts = [pair_text(root, n) for n in cands]
        probs = clf.predict_proba(vec_cls.transform(texts))[:, 1]
        dpred = reg.predict(vec_reg.transform(texts))
        scale = max(1.0, float(np.std(dpred)))
        scores = probs - 0.10 * (dpred / scale)
        order = np.argsort(-scores)

        rr = random.Random(SEED_TEST_CAND + 100000 + test20.index(root))
        random_order = list(range(len(cands)))
        rr.shuffle(random_order)

        direct_idx = {i for i, n in enumerate(cands) if n in direct}
        proof_idx = {i for i, n in enumerate(cands) if n in d}

        def first_rank(ordr, idxs):
            for rank, ix in enumerate(ordr, 1):
                if ix in idxs:
                    return rank
            return None

        pos_texts = [pair_text(root, n) for n in positives]
        pred_pos = reg.predict(vec_reg.transform(pos_texts))
        true_pos = np.array([d[n] for n in positives])
        rho = float(spearmanr(pred_pos, true_pos).statistic) if len(set(true_pos)) > 1 else float("nan")
        yy = np.array([1] * len(positives) + [0] * len(negs))
        auc = float(roc_auc_score(yy, probs))
        k10 = min(10, len(cands))
        p10 = sum(i in proof_idx for i in order[:k10]) / k10 if k10 else float("nan")
        rows.append({
            "shell": shell_label,
            "n_train_roots": len(train_roots),
            "target": root,
            "candidate_count": len(cands),
            "auc": auc,
            "spearman_distance": rho,
            "mae_distance": float(mean_absolute_error(true_pos, pred_pos)),
            "compass_rank_first_dag": first_rank(order, proof_idx),
            "random_rank_first_dag": first_rank(random_order, proof_idx),
            "compass_rank_first_direct_parent": first_rank(order, direct_idx),
            "random_rank_first_direct_parent": first_rank(random_order, direct_idx),
            "precision_at_10": float(p10),
        })
    eval_seconds = time.perf_counter() - t1

    agg = {
        "shell": shell_label,
        "n_train": len(train_roots),
        "n_training_classifier_examples": len(X_cls),
        "n_training_regression_examples": len(X_reg),
        "n_test": len(rows),
        "mean_auc": float(np.mean([r["auc"] for r in rows])),
        "mean_spearman_distance": float(np.nanmean([r["spearman_distance"] for r in rows])),
        "mean_mae_distance": float(np.mean([r["mae_distance"] for r in rows])),
        "median_compass_rank_first_dag": float(np.median([r["compass_rank_first_dag"] for r in rows])),
        "median_compass_rank_first_direct_parent": float(np.median([r["compass_rank_first_direct_parent"] for r in rows])),
        "mean_precision_at_10": float(np.mean([r["precision_at_10"] for r in rows])),
        "compass_beats_random_direct_parent": int(sum(r["compass_rank_first_direct_parent"] < r["random_rank_first_direct_parent"] for r in rows)),
        "random_beats_compass_direct_parent": int(sum(r["compass_rank_first_direct_parent"] > r["random_rank_first_direct_parent"] for r in rows)),
        "train_seconds": float(train_seconds),
        "eval_seconds": float(eval_seconds),
    }
    return agg, rows


# Resume safely from any previously completed shells if manifest-compatible results exist.
completed = {}
allrows = []
if RESULTS_PATH.exists():
    prior = json.loads(RESULTS_PATH.read_text())
    if prior.get("manifest_vocabulary_sha256") == vocab_hash and prior.get("test20") == test20:
        completed = {str(a["shell"]): a for a in prior.get("aggregates", [])}
        allrows = prior.get("rows", [])

ordered_labels = [str(n) for n in shell_sizes] + ["MAX"]
for shell_label in ordered_labels:
    if shell_label in completed:
        print(f"resume: skipping completed shell {shell_label}")
        continue
    roots = shells[shell_label]
    agg, rows = fit_and_eval(roots, shell_label)
    completed[shell_label] = agg
    allrows.extend(rows)
    payload = {
        "protocol": manifest["protocol"],
        "manifest_vocabulary_sha256": vocab_hash,
        "test20": test20,
        "aggregates": [completed[k] for k in ordered_labels if k in completed],
        "rows": allrows,
    }
    atomic_json(RESULTS_PATH, payload)
    print(json.dumps(agg, indent=2))

# Final CSV, regenerated from the recoverable JSON rows.
if allrows:
    tmp = ROWS_PATH.with_suffix(ROWS_PATH.suffix + ".tmp")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=allrows[0].keys())
        w.writeheader(); w.writerows(allrows)
    tmp.replace(ROWS_PATH)
