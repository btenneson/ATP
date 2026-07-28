# Predator_4 Setup & Run Guide

## Step 1: Download set.mm

**Option A: Using the original predator4.py**
```bash
cd /path/to/your/workspace
python predator4.py fetch set.mm
```

**Option B: Manual download**
Download from: https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm
Save as `set.mm` in your working directory (~40 MB)

**Option C: wget/curl**
```bash
wget https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm
# or
curl -o set.mm https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm
```

---

## Step 2: Verify the download

```bash
ls -lh set.mm
# Should be ~40-45 MB
```

---

## Step 3: Run Predator_4 on Cantor's Theorem

Once you have `set.mm` in your working directory, find the theorem label:

### Find Cantor's theorem label:
```bash
grep "cantor" set.mm | head -20
# or search for "surj", "inj", "onto", etc.
```

Common labels in set.mm for Cantor:
- `noendsurj` — no surjection from set to its powerset
- `cantor` — variant
- `psurjinj` — powerset surjection/injection relations

### Run on a specific theorem (e.g., noendsurj):

**Original Predator_4:**
```bash
python predator4.py prove --label noendsurj --db set.mm -p 0.9 --limit 20000
```

**Enhanced version:**
```bash
python predator4_enhanced.py train --db set.mm -p 0.9 --limit 20000
```

### Expected output:
- Statement of the theorem
- Its true premises (the theorems/axioms its proof actually cites)
- Rank of each premise under:
  - Predator_4 learned ranking
  - Frequency baseline (most-cited premises first)
  - Chronological baseline (most-recent premises first)
  - FUSED ranking (combination of Predator + frequency)
- **EFFORT** — what fraction of the candidate pool you must read to find all premises

---

## Step 4: Interpret the results

**Key metrics:**

- **Rank = 1**: Predator correctly identified this as most likely
- **Rank = 500** (out of pool 3000): Predator ranked it in top 17% but not top 10
- **EFFORT = 0.15**: You need to read 15% of the available statements to have all premises in hand
  - If EFFORT < baseline, Predator wins
  - If EFFORT > baseline, brute force (chronological) is better

---

## Step 5 (Optional): Run scaling experiment

Train on increasing fractions of the corpus:

```bash
python predator4.py scale --db set.mm -p 0.9 \
  --sizes 2000,4000,8000,16000,32000 \
  --limit 0 --figures
```

This trains on 90% of 2000 statements, then 90% of 4000, etc., and measures recall@10 and effort on a fixed test set. Produces PDFs.

---

## Quick test without set.mm (tiny corpus)

```bash
python predator4.py fetch iset.mm  # intuitionistic set theory, 5 MB
python predator4.py stats --db iset.mm --limit 5000
python predator4.py train --db iset.mm -p 0.8 --limit 5000
```

---

## Files provided:

1. **predator4.py** — Original (from your upload)
2. **predator4_enhanced.py** — Enhanced with interactions, hard negative sampling, RankNet loss
3. **predator4_enhanced.py** — Drop-in replacement, same command structure

Both accept `--model logistic` (default, no sklearn needed) or `--model forest` (needs scikit-learn).
