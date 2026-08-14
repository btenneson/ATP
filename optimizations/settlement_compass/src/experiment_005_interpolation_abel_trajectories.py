"""Experiment 005: large-shell interpolation with executed retrospective DAG trajectories.

Extends Experiment 004 without changing its sealed test targets or ordered training pool.
Shells: 160, 320, 640, 1280, 2560, MAX (where available).

For each test theorem, the learned controller starts from several deep nodes of the
known proof DAG and repeatedly chooses a reverse-DAG predecessor toward the theorem
from a frozen action set containing all true reverse predecessors plus frozen
non-DAG distractors. Choosing a distractor leaves the known proof DAG and fails the
trajectory. This is a retrospective controlled-DAG diagnostic, NOT a live ATP proof race.

Recorded quantities include exact Bellman distance V*=d on the known reverse DAG,
learned value Vhat, true and learned Abel increments, drift, variance, Abel residual,
hitting time, success rate, and static navigation metrics.
"""
from __future__ import annotations

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
BASE_MANIFEST = OUT_DIR / "experiment_004_manifest.json"
OUT = OUT_DIR / "experiment_005_interpolation_abel_trajectories.json"
EXPECTED_SETMM_SHA256 = "7b70cd8cca88aeb72a8dd97029d0b506015fb0325afec581cdc9add8ca0c8547"
STARTS_PER_TARGET = 5
DISTRACTORS_PER_STEP = 20
MAX_TRAJECTORY_STEPS = 100
SEED_TRAJ = 2026081401

VEC_PARAMS = dict(tokenizer=str.split, token_pattern=None, lowercase=False,
                  ngram_range=(1, 2), min_df=2, max_features=30000,
                  sublinear_tf=True)
CLF_PARAMS = dict(max_iter=500, class_weight="balanced", C=2.0,
                  random_state=2026081305)
REG_PARAMS = dict(alpha=5.0)


def py(x):
    if isinstance(x, np.generic): return x.item()
    if isinstance(x, dict): return {str(k): py(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [py(v) for v in x]
    return x


def atomic_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(py(obj), indent=2, sort_keys=True))
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


if sha256_file(SETMM) != EXPECTED_SETMM_SHA256:
    raise SystemExit("set.mm hash mismatch")
if not BASE_MANIFEST.exists():
    raise SystemExit("Experiment 004 manifest missing; Experiment 005 must reuse its frozen split")
base = json.loads(BASE_MANIFEST.read_text())
test20 = base["test20"]
train_pool = base["ordered_training_roots"]
frozen_negatives = base["frozen_negatives"]
frozen_test_negs = base["frozen_test_negatives"]

# Parse frozen set.mm snapshot identically to Experiment 004.
text = SETMM.read_text(encoding="utf-8", errors="ignore")
clean = re.sub(r"\$\((?:.|\n)*?\$\)", " ", text)
tokens = clean.split(); ths=[]; scopes=[[]]; i=0
while i < len(tokens):
    tok=tokens[i]
    if tok=="${": scopes.append([]); i+=1; continue
    if tok=="$}": scopes.pop(); i+=1; continue
    if tok in ("$c","$v","$d"):
        j=i+1
        while tokens[j]!="$.": j+=1
        i=j+1; continue
    if tok=="$[":
        j=i+1
        while tokens[j]!="$]": j+=1
        i=j+1; continue
    label=tok
    if i+1>=len(tokens): break
    typ=tokens[i+1]
    if typ in ("$f","$e","$a"):
        j=i+2; expr=[]
        while tokens[j]!="$.": expr.append(tokens[j]); j+=1
        if typ=="$e": scopes[-1].append((label," ".join(expr)))
        i=j+1; continue
    if typ=="$p":
        j=i+2; expr=[]
        while tokens[j]!="$=": expr.append(tokens[j]); j+=1
        proof=[]; j+=1
        while tokens[j]!="$.": proof.append(tokens[j]); j+=1
        if proof and proof[0]=="(":
            try: deps=proof[1:proof.index(")")]
            except ValueError: deps=[]
        else: deps=[x for x in proof if x!="?"]
        ths.append({"label":label,"stmt":" ".join(expr),"deps":deps,"pos":i,
                    "hyps":sum(len(s) for s in scopes)})
        i=j+1; continue
    i+=1
emap={t["label"]:t for t in ths}
inf0_pos=emap["inf0"]["pos"]
pre=[t for t in ths if t["pos"]<inf0_pos]
pre_labels={t["label"] for t in pre}

@lru_cache(None)
def closure_tuple(root):
    seen=set(); stack=[root]
    while stack:
        lab=stack.pop(); t=emap.get(lab)
        if not t: continue
        for d in t["deps"]:
            if d in emap and d not in seen:
                seen.add(d); stack.append(d)
    return tuple(sorted(seen))

def closure(root): return set(closure_tuple(root))

@lru_cache(None)
def distance_items(root):
    nodes={root}|closure(root); dist={root:0}; q=deque([root])
    while q:
        x=q.popleft()
        for d in emap[x]["deps"]:
            if d in nodes and d not in dist:
                dist[d]=dist[x]+1; q.append(d)
    return tuple(sorted(dist.items()))

def distances(root): return dict(distance_items(root))

def pair_text(root,node): return "ROOT "+emap[root]["stmt"]+" CAND "+emap[node]["stmt"]

# Rebuild the exact MAX-only feature coordinate system.
vocab_text=[]
for root in train_pool:
    d=distances(root)
    for node in d:
        if node!=root: vocab_text.append(pair_text(root,node))
    for node in frozen_negatives[root]: vocab_text.append(pair_text(root,node))
vocab_vectorizer=TfidfVectorizer(**VEC_PARAMS); vocab_vectorizer.fit(vocab_text)
frozen_vocab={str(k):int(v) for k,v in vocab_vectorizer.vocabulary_.items()}
vocab_hash=hashlib.sha256(json.dumps(frozen_vocab,sort_keys=True).encode()).hexdigest()
if vocab_hash != base["vocabulary_sha256"]:
    raise SystemExit("vocabulary mismatch with Experiment 004")

def make_vec(): return TfidfVectorizer(vocabulary=frozen_vocab, **VEC_PARAMS)

shell_ns=[n for n in (160,320,640,1280,2560) if len(train_pool)>=n]
shells={str(n):train_pool[:n] for n in shell_ns}; shells["MAX"]=train_pool
ordered=[str(n) for n in shell_ns]+["MAX"]

# Freeze start nodes and action distractors independently of shell size.
start_nodes={}; distractor_cache={}
for ti,root in enumerate(test20):
    d=distances(root)
    candidates=[x for x,v in d.items() if v>=3]
    candidates.sort(key=lambda x:(-d[x],x))
    # choose spread across deepest available nodes deterministically
    if len(candidates)<=STARTS_PER_TARGET: starts=candidates
    else:
        idxs=np.linspace(0,len(candidates)-1,STARTS_PER_TARGET,dtype=int)
        starts=[candidates[int(j)] for j in idxs]
    start_nodes[root]=starts
    for node in d:
        pool=[x for x in frozen_test_negs[root] if x in emap and x!=node]
        rr=random.Random(SEED_TRAJ + ti*1000003 + sum(ord(c) for c in node))
        k=min(DISTRACTORS_PER_STEP,len(pool))
        distractor_cache[(root,node)]=sorted(rr.sample(pool,k)) if k else []


def fit_models(roots):
    Xc=[]; yc=[]; Xr=[]; yr=[]
    for root in roots:
        d=distances(root)
        for node,dv in d.items():
            if node==root: continue
            txt=pair_text(root,node); Xc.append(txt); yc.append(1); Xr.append(txt); yr.append(dv)
        for node in frozen_negatives[root]: Xc.append(pair_text(root,node)); yc.append(0)
    vc=make_vec(); mc=vc.fit_transform(Xc); clf=LogisticRegression(**CLF_PARAMS).fit(mc,yc)
    vr=make_vec(); mr=vr.fit_transform(Xr); reg=Ridge(**REG_PARAMS).fit(mr,yr)
    return vc,clf,vr,reg,len(Xc),len(Xr)


def reverse_parents(root):
    nodes={root}|closure(root); parents=defaultdict(list)
    for p in nodes:
        for child in emap[p]["deps"]:
            if child in nodes: parents[child].append(p)
    return {k:sorted(v) for k,v in parents.items()}


def score_actions(root, actions, vc,clf,vr,reg):
    texts=[pair_text(root,a) for a in actions]
    probs=clf.predict_proba(vc.transform(texts))[:,1]
    pred=reg.predict(vr.transform(texts)); scale=max(1.0,float(np.std(pred)))
    score=probs - 0.10*(pred/scale)
    return score,pred


def run_trajectory(root,start,vc,clf,vr,reg):
    d=distances(root); parents=reverse_parents(root)
    cur=start; steps=[]; visited={cur}
    vhat_cur=float(reg.predict(vr.transform([pair_text(root,cur)]))[0])
    for t in range(MAX_TRAJECTORY_STEPS):
        if cur==root:
            return {"success":True,"tau":t,"start":start,"start_Vstar":d[start],"steps":steps}
        true_actions=parents.get(cur,[])
        if not true_actions:
            return {"success":False,"tau":None,"failure":"no_reverse_parent","start":start,"start_Vstar":d[start],"steps":steps}
        distract=distractor_cache.get((root,cur),[])
        actions=true_actions+distract
        scores,preds=score_actions(root,actions,vc,clf,vr,reg)
        best=int(np.argmax(scores)); nxt=actions[best]; vhat_next=float(preds[best])
        if nxt not in d:
            steps.append({"t":t,"state":cur,"chosen":nxt,"off_dag":True,
                          "Vstar":d[cur],"Vhat":vhat_cur})
            return {"success":False,"tau":None,"failure":"distractor_selected","start":start,"start_Vstar":d[start],"steps":steps}
        true_delta=float(d[cur]-d[nxt])
        learned_delta=float(vhat_cur-vhat_next)
        steps.append({"t":t,"state":cur,"chosen":nxt,"off_dag":False,
                      "Vstar":d[cur],"Vstar_next":d[nxt],"Vhat":vhat_cur,
                      "Vhat_next":vhat_next,"true_abel_increment":true_delta,
                      "learned_abel_increment":learned_delta,
                      "true_abel_residual":abs(true_delta-1.0),
                      "learned_abel_residual":abs(learned_delta-1.0)})
        cur=nxt; vhat_cur=vhat_next
        if cur in visited and cur!=root:
            return {"success":False,"tau":None,"failure":"cycle","start":start,"start_Vstar":d[start],"steps":steps}
        visited.add(cur)
    return {"success":False,"tau":None,"failure":"step_cap","start":start,"start_Vstar":d[start],"steps":steps}


def static_eval(vc,clf,vr,reg):
    rows=[]
    for root in test20:
        d=distances(root); pos=[n for n in d if n!=root]; neg=frozen_test_negs[root]; cands=pos+neg
        texts=[pair_text(root,n) for n in cands]
        probs=clf.predict_proba(vc.transform(texts))[:,1]; pred=reg.predict(vr.transform(texts))
        yy=np.array([1]*len(pos)+[0]*len(neg))
        true=np.array([d[n] for n in pos]); predpos=reg.predict(vr.transform([pair_text(root,n) for n in pos]))
        rho=float(spearmanr(predpos,true).statistic) if len(set(true))>1 else float("nan")
        rows.append({"auc":float(roc_auc_score(yy,probs)),"rho":rho,
                     "mae":float(mean_absolute_error(true,predpos))})
    return {"mean_auc":float(np.mean([r["auc"] for r in rows])),
            "mean_spearman_distance":float(np.nanmean([r["rho"] for r in rows])),
            "mean_mae_distance":float(np.mean([r["mae"] for r in rows]))}

results=[]
for label in ordered:
    t0=time.perf_counter(); vc,clf,vr,reg,nc,nr=fit_models(shells[label]); train_s=time.perf_counter()-t0
    trajectories=[]
    for root in test20:
        for start in start_nodes[root]: trajectories.append({"target":root,**run_trajectory(root,start,vc,clf,vr,reg)})
    onsteps=[s for tr in trajectories for s in tr["steps"] if not s.get("off_dag")]
    learned_inc=[s["learned_abel_increment"] for s in onsteps]
    true_inc=[s["true_abel_increment"] for s in onsteps]
    succ=[tr for tr in trajectories if tr["success"]]
    static=static_eval(vc,clf,vr,reg)
    agg={"shell":label,"n_train":len(shells[label]),"train_seconds":train_s,
         "n_training_classifier_examples":nc,"n_training_regression_examples":nr,
         "n_trajectories":len(trajectories),"trajectory_success_rate":len(succ)/max(1,len(trajectories)),
         "mean_hitting_time_success":float(np.mean([tr["tau"] for tr in succ])) if succ else None,
         "median_hitting_time_success":float(np.median([tr["tau"] for tr in succ])) if succ else None,
         "mean_start_Vstar":float(np.mean([tr["start_Vstar"] for tr in trajectories])) if trajectories else None,
         "true_drift_mu":float(np.mean(true_inc)) if true_inc else None,
         "true_increment_variance_sigma2":float(np.var(true_inc)) if true_inc else None,
         "mean_true_abel_residual":float(np.mean([abs(x-1.0) for x in true_inc])) if true_inc else None,
         "learned_drift_mu":float(np.mean(learned_inc)) if learned_inc else None,
         "learned_increment_variance_sigma2":float(np.var(learned_inc)) if learned_inc else None,
         "mean_learned_abel_residual":float(np.mean([abs(x-1.0) for x in learned_inc])) if learned_inc else None,
         "bellman_value_mae_on_executed_states":float(np.mean([abs(s["Vhat"]-s["Vstar"]) for s in onsteps])) if onsteps else None,
         **static}
    results.append({"aggregate":agg,"trajectories":trajectories})
    atomic_json(OUT,{"protocol":"Experiment 005 interpolation + retrospective executed DAG control trajectories; not live ATP race",
                     "experiment_004_vocabulary_sha256":vocab_hash,"test20":test20,"start_nodes":start_nodes,
                     "shell_order":ordered,"results":results})
    print(json.dumps(py(agg),indent=2))
