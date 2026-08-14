"""Retrospective theorem-landmark navigation diagnostic.

This is intentionally NOT scored as an ATP proof race. It tests whether
geometry learned from ten solved dependency DAGs transfers to held-out proof
DAGs and helps rank proof-relevant landmarks among distractors.
"""
import re, random, json, csv
from collections import defaultdict, deque
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, roc_auc_score
from scipy.stats import spearmanr
import os

SETMM=Path(os.environ.get("SETMM_PATH","set.mm"))
SEED_TRAIN=20260813
SEED_TEST=20260816
TRAIN_ROOTS=['pwidg','axreplem','f1ores','fiinf2g','eqop','frpomin','rabab','rabun2','eusn','elun2']
TEST_ROOTS=['naddov','fiuni','el2xptp0','naddss1','f1opwfi','recsval','ordfin','inficl','oelim','oesuc','oaword2','nnmcl','releldmdifi','odi','om1','wfi','oeworde','omordi','unifi2','oen0','f1finf1o','naddoa','fiss','dftpos4','imafi2','naddword2','nnawordi','rdgsucg','naddssim','onfin','oa0','naddass','wfr3g','fnsuppeq0','oecl','oalim','unxpwdom','oe0','isores3','f1imacnv','omxpen','nnsdomo','oaabs2','nnaword1','nnm2','nnesuc','tz6.26','rdgsuc','unbnn2']

text=SETMM.read_text(encoding='utf-8',errors='ignore')
clean=re.sub(r'\$\((?:.|\n)*?\$\)', ' ', text)
tokens=clean.split()
ths=[]; scopes=[[]]; i=0
while i<len(tokens):
    tok=tokens[i]
    if tok=='${': scopes.append([]); i+=1; continue
    if tok=='$}': scopes.pop(); i+=1; continue
    if tok in ('$c','$v','$d'):
        j=i+1
        while tokens[j] != '$.': j+=1
        i=j+1; continue
    if tok=='$[':
        j=i+1
        while tokens[j] != '$]': j+=1
        i=j+1; continue
    label=tok
    if i+1>=len(tokens): break
    typ=tokens[i+1]
    if typ in ('$f','$e','$a'):
        j=i+2; expr=[]
        while tokens[j] != '$.': expr.append(tokens[j]); j+=1
        if typ=='$e': scopes[-1].append((label,' '.join(expr)))
        i=j+1; continue
    if typ=='$p':
        j=i+2; expr=[]
        while tokens[j] != '$=': expr.append(tokens[j]); j+=1
        proof=[]; j+=1
        while tokens[j] != '$.': proof.append(tokens[j]); j+=1
        if proof and proof[0]=='(':
            try: close=proof.index(')'); deps=proof[1:close]
            except ValueError: deps=[]
        else: deps=[x for x in proof if x!='?']
        ths.append({'label':label,'stmt':' '.join(expr),'deps':deps,'pos':i})
        i=j+1; continue
    i+=1
emap={t['label']:t for t in ths}
inf0_pos=emap['inf0']['pos']
pre=[t for t in ths if t['pos']<inf0_pos]
pre_labels={t['label'] for t in pre}

from functools import lru_cache
@lru_cache(None)
def closure_tuple(root):
    seen=set(); stack=[root]
    while stack:
        lab=stack.pop(); t=emap.get(lab)
        if not t: continue
        for d in t['deps']:
            if d in emap and d not in seen:
                seen.add(d); stack.append(d)
    return tuple(seen)

def closure(root): return set(closure_tuple(root))

def distances(root):
    nodes={root}|closure(root)
    rev=defaultdict(list)
    for lab in nodes:
        for d in emap[lab]['deps']:
            if d in nodes: rev[lab].append(d)
    dist={root:0}; q=deque([root])
    while q:
        x=q.popleft()
        for d in rev[x]:
            if d not in dist:
                dist[d]=dist[x]+1; q.append(d)
    return dist

def pair_text(root,node):
    return 'ROOT '+emap[root]['stmt']+' CAND '+emap[node]['stmt']

rng=random.Random(SEED_TRAIN)
X_cls=[]; y_cls=[]; X_reg=[]; y_reg=[]; train_stats=[]
for root in TRAIN_ROOTS:
    d=distances(root); pos_nodes=[n for n in d if n!=root]
    train_stats.append((root,len(d),max(d.values()) if d else 0))
    for n in pos_nodes:
        X_cls.append(pair_text(root,n)); y_cls.append(1)
        X_reg.append(pair_text(root,n)); y_reg.append(d[n])
    negpool=list(pre_labels-set(d)-{root})
    k=min(max(50,len(pos_nodes)), len(negpool))
    for n in rng.sample(negpool,k):
        X_cls.append(pair_text(root,n)); y_cls.append(0)

print('train stats',train_stats)
print('classification examples',len(y_cls),'positives',sum(y_cls),'reg',len(y_reg))

clf=Pipeline([
    ('vec',TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False, ngram_range=(1,2), min_df=2, max_features=30000, sublinear_tf=True)),
    ('lr',LogisticRegression(max_iter=500,class_weight='balanced',C=2.0,random_state=SEED_TRAIN))])
clf.fit(X_cls,y_cls)
reg=Pipeline([
    ('vec',TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False, ngram_range=(1,2), min_df=2,max_features=30000,sublinear_tf=True)),
    ('ridge',Ridge(alpha=5.0))])
reg.fit(X_reg,y_reg)

rng=random.Random(SEED_TEST)
rows=[]
for root in TEST_ROOTS:
    d=distances(root); positives=[n for n in d if n!=root]
    if not positives: continue
    direct={n for n,v in d.items() if v==1}
    negpool=list(pre_labels-set(d)-{root}-set(TRAIN_ROOTS))
    nneg=min(max(100,5*len(positives)),len(negpool))
    negs=rng.sample(negpool,nneg)
    cands=positives+negs
    texts=[pair_text(root,n) for n in cands]
    probs=clf.predict_proba(texts)[:,1]
    dpred=reg.predict(texts)
    scale=max(1.0,np.std(dpred))
    scores=probs - 0.10*(dpred/scale)
    order=np.argsort(-scores)
    random_order=list(range(len(cands))); rng.shuffle(random_order)
    direct_idx={i for i,n in enumerate(cands) if n in direct}
    proof_idx={i for i,n in enumerate(cands) if n in d}
    def first_rank(ordr, idxs):
        for rank,i in enumerate(ordr,1):
            if i in idxs: return rank
        return None
    comp_direct=first_rank(order,direct_idx)
    base_direct=first_rank(random_order,direct_idx)
    comp_proof=first_rank(order,proof_idx)
    base_proof=first_rank(random_order,proof_idx)
    k=min(10,len(cands))
    p10=sum(i in proof_idx for i in order[:k])/k
    pos_text=[pair_text(root,n) for n in positives]
    pred_pos=reg.predict(pos_text)
    true_pos=np.array([d[n] for n in positives])
    rho=float(spearmanr(pred_pos,true_pos).statistic) if len(set(true_pos))>1 else float('nan')
    mae=float(mean_absolute_error(true_pos,pred_pos))
    yy=np.array([1]*len(positives)+[0]*len(negs))
    auc=float(roc_auc_score(yy,probs))
    rows.append(dict(target=root,dag_nodes=len(d),direct_parents=len(direct),distractors=len(negs),auc=auc,spearman_distance=rho,mae_distance=mae,compass_rank_first_dag=comp_proof,baseline_rank_first_dag=base_proof,compass_rank_first_direct_parent=comp_direct,baseline_rank_first_direct_parent=base_direct,precision_at_10=p10))

valid_direct=[r for r in rows if r['compass_rank_first_direct_parent'] and r['baseline_rank_first_direct_parent']]
agg={
 'n_targets':len(rows),
 'mean_auc':float(np.mean([r['auc'] for r in rows])),
 'median_auc':float(np.median([r['auc'] for r in rows])),
 'mean_spearman_distance':float(np.nanmean([r['spearman_distance'] for r in rows])),
 'median_spearman_distance':float(np.nanmedian([r['spearman_distance'] for r in rows])),
 'mean_mae_distance':float(np.mean([r['mae_distance'] for r in rows])),
 'median_compass_rank_first_dag':float(np.median([r['compass_rank_first_dag'] for r in rows])),
 'median_baseline_rank_first_dag':float(np.median([r['baseline_rank_first_dag'] for r in rows])),
 'median_compass_rank_first_direct_parent':float(np.median([r['compass_rank_first_direct_parent'] for r in valid_direct])),
 'median_baseline_rank_first_direct_parent':float(np.median([r['baseline_rank_first_direct_parent'] for r in valid_direct])),
 'mean_precision_at_10':float(np.mean([r['precision_at_10'] for r in rows])),
 'compass_beats_random_direct_parent':sum(r['compass_rank_first_direct_parent']<r['baseline_rank_first_direct_parent'] for r in valid_direct),
 'random_beats_compass_direct_parent':sum(r['compass_rank_first_direct_parent']>r['baseline_rank_first_direct_parent'] for r in valid_direct),
 'ties_direct_parent':sum(r['compass_rank_first_direct_parent']==r['baseline_rank_first_direct_parent'] for r in valid_direct),
}
print(json.dumps(agg,indent=2))
Path(os.environ.get('COMPASS_RESULTS_JSON','compass_diag_results.json')).write_text(json.dumps({'protocol':'retrospective theorem-landmark navigation diagnostic; NOT an ATP proof race','training_roots':TRAIN_ROOTS,'test_roots':TEST_ROOTS,'aggregate':agg,'rows':rows},indent=2))
with open(os.environ.get('COMPASS_RESULTS_CSV','compass_diag_rows.csv'),'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
