#!/usr/bin/env python3
"""Reproduce AMLD Settlement Compass Benchmark 001 from a frozen set.mm snapshot.

This script creates 10 training proof-dependency DAGs and 50 sealed targets:
49 downstream theorem targets plus one withheld Axiom-of-Infinity formula.
It does not itself certify independence; the I target requires a separate
metatheoretic/model certificate in the declared no-Infinity base theory.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, random, re
from collections import defaultdict, deque
from pathlib import Path

TRAINING_LABELS = [
    "pwidg","axreplem","f1ores","fiinf2g","eqop",
    "frpomin","rabab","rabun2","eusn","elun2",
]
TARGET_LABELS = [
    "naddov","fiuni","el2xptp0","naddss1","f1opwfi","recsval","ordfin","inficl","oelim","oesuc",
    "oaword2","nnmcl","releldmdifi","odi","om1","wfi","oeworde","omordi","unifi2","oen0","f1finf1o",
    "naddoa","fiss","dftpos4","imafi2","naddword2","nnawordi","rdgsucg","naddssim","onfin","oa0",
    "naddass","wfr3g","fnsuppeq0","oecl","oalim","unxpwdom","oe0","isores3","f1imacnv","omxpen",
    "nnsdomo","oaabs2","nnaword1","nnm2","nnesuc","tz6.26","rdgsuc","unbnn2",
]
SHUFFLE_SEED = 20260815
EXPECTED_SETMM_SHA256 = "7b70cd8cca88aeb72a8dd97029d0b506015fb0325afec581cdc9add8ca0c8547"


def parse_setmm(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    clean = re.sub(r"\$\((?:.|\n)*?\$\)", " ", text)
    tokens = clean.split()
    theorems, scopes = [], [[]]
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "${": scopes.append([]); i += 1; continue
        if tok == "$}": scopes.pop(); i += 1; continue
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
            j, expr = i + 2, []
            while tokens[j] != "$.": expr.append(tokens[j]); j += 1
            if typ == "$e": scopes[-1].append((label, " ".join(expr)))
            i = j + 1; continue
        if typ == "$p":
            j, expr = i + 2, []
            while tokens[j] != "$=": expr.append(tokens[j]); j += 1
            proof = []; j += 1
            while tokens[j] != "$.": proof.append(tokens[j]); j += 1
            if proof and proof[0] == "(":
                close = proof.index(")")
                deps = proof[1:close]
            else:
                deps = [x for x in proof if x != "?"]
            hyps = [item for scope in scopes for item in scope]
            theorems.append({"label": label, "stmt": " ".join(expr), "deps": deps, "pos": i, "hyps": hyps})
            i = j + 1; continue
        i += 1
    return clean, theorems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setmm", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--allow-hash-mismatch", action="store_true")
    args = ap.parse_args()
    got = hashlib.sha256(args.setmm.read_bytes()).hexdigest()
    if got != EXPECTED_SETMM_SHA256 and not args.allow_hash_mismatch:
        raise SystemExit(f"set.mm hash mismatch: got {got}, expected {EXPECTED_SETMM_SHA256}")
    clean, ths = parse_setmm(args.setmm)
    emap = {t["label"]: t for t in ths}
    out = args.out; dags = out / "training_dags"; dags.mkdir(parents=True, exist_ok=True)

    def closure(root):
        seen, stack = set(), [root]
        while stack:
            lab = stack.pop(); t = emap.get(lab)
            if not t: continue
            for d in t["deps"]:
                if d in emap and d not in seen:
                    seen.add(d); stack.append(d)
        return seen

    def theorem_graph(root):
        reachable = {root} | closure(root)
        edges, leaves = [], set()
        for lab in reachable:
            for d in emap[lab]["deps"]:
                if d in emap: edges.append((d, lab))
                else: leaves.add(d)
        rev = defaultdict(list)
        for a, b in edges: rev[b].append(a)
        dist, q = {root: 0}, deque([root])
        while q:
            b = q.popleft()
            for a in rev[b]:
                if a not in dist:
                    dist[a] = dist[b] + 1; q.append(a)
        return reachable, edges, sorted(leaves), dist

    summary = []
    for label in TRAINING_LABELS:
        t = emap[label]; nodes, edges, leaves, dist = theorem_graph(label)
        obj = {
            "root_theorem": label, "assertion": t["stmt"], "essential_hypotheses": t["hyps"],
            "theorem_nodes": sorted(nodes), "edges_dependency_to_dependent": [list(e) for e in edges],
            "non_theorem_leaf_references": leaves, "exact_distance_to_training_settlement": dist,
            "node_count": len(nodes), "edge_count": len(edges),
        }
        (dags / f"{label}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")
        summary.append({"label": label, "assertion": t["stmt"], "nodes": len(nodes), "edges": len(edges)})
    (out / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    m = re.search(r"ax-inf\s+\$a\s+(.*?)\s+\$\.", clean, re.S)
    if not m: raise SystemExit("ax-inf statement not found")
    inf_stmt = " ".join(m.group(1).split())
    trainset = set(TRAINING_LABELS)
    rows = []
    for label in TARGET_LABELS:
        t = emap[label]
        rows.append({"source_label": label, "formula": t["stmt"], "class": "P", "training_landmarks": sorted(trainset & closure(label))})
    rows.append({"source_label": "ax-inf", "formula": inf_stmt, "class": "I", "training_landmarks": []})
    random.Random(SHUFFLE_SEED).shuffle(rows)
    public, truth = [], []
    for j, r in enumerate(rows, 1):
        wid = f"W{j:03d}"
        public.append({"target_id": wid, "formula": r["formula"]})
        truth.append({"target_id": wid, "ground_truth_class": r["class"], "source_label_for_audit": r["source_label"], "training_landmarks_for_audit": r["training_landmarks"]})
    (out / "sealed_targets.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
    (out / "ground_truth_DO_NOT_GIVE_TO_NAVIGATOR.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    with (out / "audit_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target_id","ground_truth_class","source_label_for_audit","training_landmarks_for_audit"]); w.writeheader()
        for r in truth:
            rr = dict(r); rr["training_landmarks_for_audit"] = ";".join(rr["training_landmarks_for_audit"]); w.writerow(rr)
    (out / "FROZEN_SOURCE_SHA256.txt").write_text(got + "\n", encoding="utf-8")
    print(f"Generated {out}; set.mm sha256={got}")

if __name__ == "__main__": main()
