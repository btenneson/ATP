"""Nested training-shell experiment for the settlement compass.

Shells are cumulative: the 20-DAG shell contains the original 10-DAG shell;
the 40-DAG shell contains the 20-DAG shell; and the 80-DAG shell contains the
40-DAG shell. All shells are evaluated on the same frozen 20 theorem targets.
This remains a retrospective proof-DAG navigation diagnostic, not an end-to-end
ATP settlement race.
"""
import re, random, json, csv, os
from collections import defaultdict, deque
from pathlib import Path
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, roc_auc_score
from scipy.stats import spearmanr

SETMM=Path(os.environ.get('SETMM_PATH','set.mm'))
OUT_JSON=Path(os.environ.get('COMPASS_RESULTS_JSON','shells_10_20_40_80.json'))
OUT_CSV=Path(os.environ.get('COMPASS_RESULTS_CSV','shells_10_20_40_80_rows.csv'))
SEED_TEST20=20260817
SEED_EXTEND=20260818
SEED_MODEL=20260819

BASE10=['pwidg','axreplem','f1ores','fiinf2g','eqop','frpomin','rabab','rabun2','eusn','elun2']
# Preserve the exact 10 extra roots from Experiment 002.
EXTRA10=['pm4.72','resindi','simp112','anandi3','nlim1','equs5','diffi','dfpss2','axextg','sbal1']
BASE20=BASE10+EXTRA10
ORIGINAL49=['naddov','fiuni','el2xptp0','naddss1','f1opwfi','recsval','ordfin','inficl','oelim','oesuc','oaword2','nnmcl','releldmdifi','odi','om1','wfi','oeworde','omordi','unifi2','oen0','f1finf1o','naddoa','fiss','dftpos4','imafi2','naddword2','nnawordi','rdgsucg','naddssim','onfin','oa0','naddass','wfr3g','fnsuppeq0','oecl','oalim','unxpwdom','oe0','isores3','f1imacnv','omxpen','nnsdomo','oaabs2','nnaword1','nnm2','nnesuc','tz6.26','rdgsuc','unbnn2']

text=SETMM.read_text(encoding='utf-8',errors='ignore')
clean=re.sub(r'\$\((?:.|\n)*?\$\)', ' ', text)
tokens=clean.split(); ths=[]; scopes=[[]]; i=0
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
        active_hyps=sum(len(s) for s in scopes)
        ths.append({'label':label,'stmt':' '.join(expr),'deps':deps,'pos':i,'hyps':active_hyps})
        i=j+1; continue
    i+=1
emap={t['label']:t for t in ths}
inf0_pos=emap['inf0']['pos']
pre=[t for t in ths if t['pos']<inf0_pos]
pre_labels={t['label'] for t in pre}

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
    nodes={root}|closure(root); rev=defaultdict(list)
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

def pair_text(root,node): return 'ROOT '+emap[root]['stmt']+' CAND '+emap[node]['stmt']

# Freeze 20 theorem targets from the original 49, once, and use them for all shells.
rng=random.Random(SEED_TEST20)
TEST20=sorted(rng.sample(ORIGINAL49,20))
TESTSET=set(TEST20)

# Eligible new training roots must be pre-Infinity, closed statements, non-OLD,
# not test roots, and must not contain a test root in their transitive dependency closure.
def eligible_training(t):
    lab=t['label']
    if t['pos']>=inf0_pos or t['hyps']!=0 or 'OLD' in lab or lab in TESTSET or lab in BASE20:
        return False
    d=distances(lab)
    if len(d)<12 or (max(d.values()) if d else 0)<3:
        return False
    if closure(lab) & TESTSET:
        return False
    return True

pool=[t['label'] for t in pre if eligible_training(t)]
rng=random.Random(SEED_EXTEND)
rng.shuffle(pool)
need60=pool[:60]
SHELL40=BASE20+need60[:20]
SHELL80=SHELL40+need60[20:60]
SHELLS={10:BASE10,20:BASE20,40:SHELL40,80:SHELL80}


def fit_and_eval(train_roots, shell_n):
    rng=random.Random(SEED_MODEL+shell_n)
    X_cls=[]; y_cls=[]; X_reg=[]; y_reg=[]
    for root in train_roots:
        d=distances(root); pos_nodes=[n for n in d if n!=root]
        for n in pos_nodes:
            X_cls.append(pair_text(root,n)); y_cls.append(1)
            X_reg.append(pair_text(root,n)); y_reg.append(d[n])
        negpool=list(pre_labels-set(d)-{root}-TESTSET)
        k=min(max(50,len(pos_nodes)),len(negpool))
        for n in rng.sample(negpool,k):
            X_cls.append(pair_text(root,n)); y_cls.append(0)
    clf=Pipeline([
      ('vec',TfidfVectorizer(tokenizer=str.split,token_pattern=None,lowercase=False,ngram_range=(1,2),min_df=2,max_features=30000,sublinear_tf=True)),
      ('lr',LogisticRegression(max_iter=500,class_weight='balanced',C=2.0,random_state=SEED_MODEL))])
    clf.fit(X_cls,y_cls)
    reg=Pipeline([
      ('vec',TfidfVectorizer(tokenizer=str.split,token_pattern=None,lowercase=False,ngram_range=(1,2),min_df=2,max_features=30000,sublinear_tf=True)),
      ('ridge',Ridge(alpha=5.0))])
    reg.fit(X_reg,y_reg)
    rows=[]; rr=random.Random(20260820)
    for root in TEST20:
        d=distances(root); positives=[n for n in d if n!=root]; direct={n for n,v in d.items() if v==1}
        negpool=list(pre_labels-set(d)-{root}-set(train_roots))
        nneg=min(max(100,5*len(positives)),len(negpool)); negs=rr.sample(negpool,nneg)
        cands=positives+negs; texts=[pair_text(root,n) for n in cands]
        probs=clf.predict_proba(texts)[:,1]; dpred=reg.predict(texts)
        scale=max(1.0,np.std(dpred)); scores=probs-0.10*(dpred/scale); order=np.argsort(-scores)
        random_order=list(range(len(cands))); rr.shuffle(random_order)
        direct_idx={i for i,n in enumerate(cands) if n in direct}; proof_idx={i for i,n in enumerate(cands) if n in d}
        def first_rank(ordr,idxs):
            for rank,ix in enumerate(ordr,1):
                if ix in idxs: return rank
        pos_text=[pair_text(root,n) for n in positives]; pred_pos=reg.predict(pos_text); true_pos=np.array([d[n] for n in positives])
        rho=float(spearmanr(pred_pos,true_pos).statistic) if len(set(true_pos))>1 else float('nan')
        yy=np.array([1]*len(positives)+[0]*len(negs)); auc=float(roc_auc_score(yy,probs))
        k=min(10,len(cands)); p10=sum(i in proof_idx for i in order[:k])/k
        rows.append({'shell':shell_n,'target':root,'auc':auc,'spearman_distance':rho,'mae_distance':float(mean_absolute_error(true_pos,pred_pos)),'compass_rank_first_dag':first_rank(order,proof_idx),'random_rank_first_dag':first_rank(random_order,proof_idx),'compass_rank_first_direct_parent':first_rank(order,direct_idx),'random_rank_first_direct_parent':first_rank(random_order,direct_idx),'precision_at_10':p10})
    agg={
      'n_train':shell_n,'n_test':len(rows),
      'mean_auc':float(np.mean([r['auc'] for r in rows])),
      'mean_spearman_distance':float(np.nanmean([r['spearman_distance'] for r in rows])),
      'mean_mae_distance':float(np.mean([r['mae_distance'] for r in rows])),
      'median_compass_rank_first_dag':float(np.median([r['compass_rank_first_dag'] for r in rows])),
      'median_compass_rank_first_direct_parent':float(np.median([r['compass_rank_first_direct_parent'] for r in rows])),
      'mean_precision_at_10':float(np.mean([r['precision_at_10'] for r in rows])),
      'compass_beats_random_direct_parent':sum(r['compass_rank_first_direct_parent']<r['random_rank_first_direct_parent'] for r in rows),
      'random_beats_compass_direct_parent':sum(r['compass_rank_first_direct_parent']>r['random_rank_first_direct_parent'] for r in rows)
    }
    return agg,rows

aggregates=[]; allrows=[]
for n in [10,20,40,80]:
    agg,rows=fit_and_eval(SHELLS[n],n); aggregates.append(agg); allrows.extend(rows); print(n,json.dumps(agg,indent=2))

result={'protocol':'nested training shells 10/20/40/80 on same frozen 20 theorem proof-DAG targets; NOT an ATP proof race','test20':TEST20,'shells':{str(k):v for k,v in SHELLS.items()},'aggregates':aggregates,'rows':allrows}
OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_JSON.write_text(json.dumps(result,indent=2))
with OUT_CSV.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=allrows[0].keys()); w.writeheader(); w.writerows(allrows)
