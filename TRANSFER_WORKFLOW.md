# Predator_5 Transfer Workflow

Train on the condensed-detachment fragment, test on set.mm theorems.

## The Idea

The learned ranker is trained on a tiny implicational fragment (287 states, 63 targets). The hypothesis is that the learned policy transfers to **full ZFC** in set.mm. That is:

1. Train a ranker on the CD fragment (Predator_5)
2. Extract symbol-agnostic features that work on any set.mm formula
3. Apply the ranker to real set.mm theorems
4. Measure: do on-geodesic steps rank higher than off-geodesic ones?

## Files

- `predator5.py` — trains ranker on CD fragment
- `predator5_transfer.py` — parses set.mm, extracts theorems
- `predator5_bridge.py` — applies trained ranker to set.mm theorems

## Setup

**1. Download set.mm** (one-time)

```
mkdir set.mm_repo
cd set.mm_repo
git clone https://github.com/metamath/set.mm.git
```

Or download directly:
```
curl -o set.mm https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm
```

Place `set.mm` in your working directory (`C:\google drive\Automated Theorem Proving`).

**2. Install dependencies** (one-time)

```powershell
python -m pip install scikit-learn numpy
```

## The Workflow

### Stage 1: Train on CD Fragment

```powershell
# See ground truth targets
python predator5.py harvest --depth 4 --edge-cap 15 --max-size 14

# Train both logistic and forest
python predator5.py train --model logistic --depth 4 --seed 0
python predator5.py train --model forest --depth 4 --seed 0 --n-estimators 60 --max-depth 8

# Compare on held-out targets (produces ranker.json)
python predator5.py compare --depth 4 --edge-cap 12 --max-size 14 \
    --budget 150 --lam 0.5 -k 4 --test-frac 0.35 \
    --n-estimators 60 --max-depth 8 --out ranker.json
```

This saves `ranker.json` with the trained logistic ranker.

### Stage 2: Parse set.mm

```powershell
# Extract theorems (takes ~1–2 minutes for 1000 theorems)
python predator5_transfer.py load-set-mm

# Label on/off-geodesic steps (based on written proofs)
python predator5_transfer.py label-proofs
```

This produces `theorems_setmm.json`.

### Stage 3: Transfer Evaluation

```powershell
# Apply the ranker to set.mm theorems
python predator5_bridge.py evaluate --ranker ranker.json --theorems theorems_setmm.json
```

Produces output like:

```
  TRANSFER RESULTS
    theorems scored: 847
    mean rank of on-geodesic step: 12.3
    fraction in top 10: 45%
    mean score (on-geodesic): 0.612
    mean score (off-geodesic): 0.408
```

**Interpretation:**

- If mean rank is **low** (1–5) and **top-10 fraction is high** (70%+), transfer succeeded.
- If mean rank is **high** (50+) and **top-10 fraction is low** (<30%), transfer failed.
- Mid-range results (ranks 10–30, top-10 ~40%) suggest partial transfer.

## Expected Results

**If transfer works:**
- On-geodesic steps rank in top 5–10 on average
- ~60–80% of on-geodesic steps in top-10 scored
- Significant gap between on-geodesic and off-geodesic scores

**If transfer fails:**
- On-geodesic steps rank ~50th or lower
- <30% of on-geodesic steps in top-10
- Scores for on- vs off-geodesic are similar

## Debugging

**No theorems scored:**
- Check `theorems_setmm.json` exists and is valid JSON
- Verify proofs are not empty: `cat theorems_setmm.json | grep -o '"proof": \[[^]]*\]' | head`

**Ranker not found:**
- Run `python predator5.py compare` first to generate `ranker.json`
- Verify the file: `cat ranker.json | jq '.[] | .ranker.model'` (should be "logistic")

**Empty results:**
- Theorems may have empty proofs in set.mm. This is expected; the code skips them.
- Try a smaller theorem set first: edit `predator5_transfer.py`, change `limit=1000` to `limit=100`

## Next Steps

1. **Run the full pipeline** and collect results in a CSV.
2. **Sweep hyperparameters:** try λ ∈ {0.1, 0.5, 1, 2} and report which transfers best.
3. **If transfer works:** measure speedup on set.mm theorem search using the ranked policy.
4. **If transfer fails:** analyze which features are most predictive in set.mm; retrain with new features.

## Theory

See `predator5.pdf` for the full theory. Key points:

- **Proof-covering:** ordering edges preserves completeness; truncating does not.
- **Shortest-path principle:** BFS on the novelty state graph finds true geodesics (used for training labels).
- **Symbol-agnostic features:** size, variable overlap, subterm overlap, and constructor matching work on any formula, not just implications.

## References

- Predator_5 paper: `predator5.pdf`
- set.mm: https://github.com/metamath/set.mm
- Metamath: https://metamath.org/
