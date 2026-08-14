"""Experiment 002: same frozen 50 targets, same ZF-minus-Infinity base, 10 vs 20 training DAGs.

The original 10 training roots are preserved. Ten additional true pre-Infinity theorem DAGs
are drawn reproducibly, excluding every frozen test theorem and excluding any candidate
whose transitive proof closure contains a frozen test theorem (anti-leakage).

The proof-DAG navigation metric is necessarily defined on the 49 P targets. The 50th
sealed target (W036 = ax-inf in the audit file) is retained in the benchmark manifest but
has no proof DAG in the weakened theory, so it is reported separately and is NOT silently
dropped or scored as a theorem-navigation case.
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
OUT=Path(os.environ.get('COMPASS_RESULTS_JSON','experiment_002_20dag_comparison.json'))
CSVOUT=Path(os.environ.get('COMPASS_RESULTS_CSV','experiment_002_20dag_rows.csv'))
SEED_ORIGINAL=20260813
SEED_EXTRA=20260817
SEED_EVAL=20260816
ORIGINAL=['pwidg','axreplem','f1ores','fiinf2g','eqop','frpomin','rabab','rabun2','eusn','elun2']
TEST=['naddov','fiuni','el2xptp0','naddss1','f1opwfi','recsval','ordfin','inficl','oelim','oesuc','oaword2','nnmcl','releldmdifi','odi','om1','wfi','oeworde','omordi','unifi2','oen0','f1finf1o','naddoa','fiss','dftpos4','imafi2','naddword2','nnawordi','rdgsucg','naddssim','onfin','oa0','naddass','wfr3g','fnsuppeq0','oecl','oalim','unxpwdom','oe0','isores3','f1imacnv','omxpen','nnsdomo','oaabs2','nnaword1','nnm2','nnesuc','tz6.26','rdgsuc','unbnn2']

text=SETMM.read_text(encoding='utf-8',errors='ignore')
clean=re.sub(r'\$\((?:.|\n)*?\$\)', ' ', text)
tokens=clean.split(); ths=[]; scopes=[[]]; i=0
while i<len(tokens):
    tok=tokens[i]
    if tok=='${': scopes.append([]); i+=1; continue
    if tok=='$}': scopes.pop(); i+=1; continue
    if tok in ('$c','$v','$d'):
        j=i+1
        while tokens[j]!='$.' : j+=1
        i=j+1; continue
    if tok=='$[':
        j=i+1
        while tokens[j]!='$]': j+=1
        i=j+1; continue
    label=tok
    if i+1>=len(tokens): break
    typ=tokens[i+1]
    if typ in ('$f','$e','$a'):
        j=i+2; expr=[]
        while tokens[j]!='$.' : expr.append(tokens[j]); j+=1
        if typ=='$e': scopes[-1].append((label,' '.join(expr)))
        i=j+1; continue
    if typ=='$p':
        hyps=[x for s in scopes for x in s]
        j=i+2; expr=[]
        while tokens[j]!='$=': expr.append(tokens[j]); j+=1
        proof=[]; j+=1
        while tokens[j]!='$.' : proof.append(tokens[j]); j+=1
        if proof and proof[0]=='(':
            try: close=proof.index(')'); deps=proof[1:close]
            except ValueError: deps=[]
        else: deps=[x for x in proof if x!='?']
        ths.append({'label':label,'stmt':' '.join(expr),'deps':deps,'pos':i,'hyps':hyps})
        i=j+1; continue
    i+=1
emap={t['label']:t for t in ths}; inf0_pos=emap['inf0']['pos']
pre=[t for t in ths if t['pos']<inf0_pos]; pre_labels={t['label'] for t in pre}

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
            if d not in dist: dist[d]=dist[x]+1; q.append(d)
    return dist

def eligible_extra(t):
    if t['label'] in ORIGINAL or t['label'] in TEST: return False
    if 'OLD' in t['label'] or t['hyps']: return False
    d=distances(t['label'])
    if len(d)<12 or max(d.values(),default=0)<3: return False
    if set(TEST) & closure(t['label']): return False
    return True

pool=[t['label'] for t in pre if eligible_extra(t)]
rng=random.Random(SEED_EXTRA); EXTRA=rng.sample(pool,10); TWENTY=ORIGINAL+EXTRA

def pair_text(root,node): return 'ROOT '+emap[root]['stmt']+' CAND '+emap[node]['stmt']

def train_model(roots):
    rng=random.Random(SEED_ORIGINAL+len(roots))
    Xc=[]; yc=[]; Xr=[]; yr=[]
    for root in roots:
        d=distances(root); pos=[n for n in d if n!=root]
        for n in pos:
            Xc.append(pair_text(root,n)); yc.append(1); Xr.append(pair_text(root,n)); yr.append(d[n])
        negpool=list(pre_labels-set(d)-{root}-set(TEST))
        k=min(max(50,len(pos)),len(negpool))
        for n in rng.sample(negpool,k): Xc.append(pair_text(root,n)); yc.append(0)
    clf=Pipeline([('vec',TfidfVectorizer(tokenizer=str.split,token_pattern=None,lowercase=False,ngram_range=(1,2),min_df=2,max_features=30000,sublinear_tf=True)),('lr',LogisticRegression(max_iter=500,class_weight='balanced',C=2.0,random_state=SEED_ORIGINAL))])
    reg=Pipeline([('vec',TfidfVectorizer(tokenizer=str.split,token_pattern=None,lowercase=False,ngram_range=(1,2),min_df=2,max_features=30000,sublinear_tf=True)),('ridge',Ridge(alpha=5.0))])
    clf.fit(Xc,yc); reg.fit(Xr,yr); return clf,reg

def evaluate(roots):
    clf,reg=train_model(roots); rng=random.Random(SEED_EVAL); rows=[]
    for root in TEST:
        d=distances(root); positives=[n for n in d if n!=root]; direct={n for n,v in d.items() if v==1}
        negpool=list(pre_labels-set(d)-{root}-set(roots)-set(TEST)); nneg=min(max(100,5*len(positives)),len(negpool)); negs=rng.sample(negpool,nneg)
        cands=positives+negs; texts=[pair_text(root,n) for n in cands]
        probs=clf.predict_proba(texts)[:,1]; dpred=reg.predict(texts); scale=max(1.0,np.std(dpred)); scores=probs-0.10*(dpred/scale)
        order=np.argsort(-scores); random_order=list(range(len(cands))); rng.shuffle(random_order)
        direct_idx={i for i,n in enumerate(cands) if n in direct}; proof_idx={i for i,n in enumerate(cands) if n in d}
        def first_rank(ordr,idxs):
            for rank,j in enumerate(ordr,1):
                if j in idxs: return rank
        pos_text=[pair_text(root,n) for n in positives]; pred_pos=reg.predict(pos_text); true_pos=np.array([d[n] for n in positives])
        yy=np.array([1]*len(positives)+[0]*len(negs)); k=min(10,len(cands))
        rows.append({'target':root,'auc':float(roc_auc_score(yy,probs)),'spearman_distance':float(spearmanr(pred_pos,true_pos).statistic) if len(set(true_pos))>1 else float('nan'),'mae_distance':float(mean_absolute_error(true_pos,pred_pos)),'compass_rank_first_dag':first_rank(order,proof_idx),'random_rank_first_dag':first_rank(random_order,proof_idx),'compass_rank_first_direct_parent':first_rank(order,direct_idx),'random_rank_first_direct_parent':first_rank(random_order,direct_idx),'precision_at_10':sum(j in proof_idx for j in order[:k])/k})
    valid=[r for r in rows if r['compass_rank_first_direct_parent'] and r['random_rank_first_direct_parent']]
    agg={'n_proof_dag_targets':len(rows),'mean_auc':float(np.mean([r['auc'] for r in rows])),'mean_spearman_distance':float(np.nanmean([r['spearman_distance'] for r in rows])),'mean_mae_distance':float(np.mean([r['mae_distance'] for r in rows])),'median_compass_rank_first_dag':float(np.median([r['compass_rank_first_dag'] for r in rows])),'median_compass_rank_first_direct_parent':float(np.median([r['compass_rank_first_direct_parent'] for r in valid])),'mean_precision_at_10':float(np.mean([r['precision_at_10'] for r in rows])),'compass_beats_random_direct_parent':sum(r['compass_rank_first_direct_parent']<r['random_rank_first_direct_parent'] for r in valid),'random_beats_compass_direct_parent':sum(r['compass_rank_first_direct_parent']>r['random_rank_first_direct_parent'] for r in valid)}
    return agg,rows

agg10,rows10=evaluate(ORIGINAL); agg20,rows20=evaluate(TWENTY)
comparison={k:agg20[k]-agg10[k] for k in ['mean_auc','mean_spearman_distance','mean_mae_distance','median_compass_rank_first_dag','median_compass_rank_first_direct_parent','mean_precision_at_10']}
result={'protocol':'Experiment 002: same frozen 50-target benchmark; compare 10 vs 20 training DAGs; proof-navigation statistics on the same 49 P targets; W036/ax-inf retained separately for I-agent evaluation','base_theory':'ZF minus Infinity (operational pre-Infinity set.mm fragment)','frozen_target_count':50,'proof_dag_target_count':49,'independence_target':{'target_id':'W036','audit_source':'ax-inf','ground_truth':'I','included_in_frozen_test_set':True,'proof_navigation_metric':'not_applicable','classification_status':'requires I-agent independence certificate; not inferred from P/R failure'},'original_training_roots':ORIGINAL,'extra_seed':SEED_EXTRA,'extra_training_roots':EXTRA,'twenty_training_roots':TWENTY,'ten_dag':{'aggregate':agg10,'rows':rows10},'twenty_dag':{'aggregate':agg20,'rows':rows20},'delta_20_minus_10':comparison}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2))
with CSVOUT.open('w',newline='') as f:
    fields=['target']+[k for k in rows10[0] if k!='target']
    w=csv.DictWriter(f,fieldnames=['training_dags']+fields); w.writeheader()
    for tag,rows in [('10',rows10),('20',rows20)]:
        for r in rows: w.writerow({'training_dags':tag,**r})
print('EXTRA',EXTRA); print('10',json.dumps(agg10,indent=2)); print('20',json.dumps(agg20,indent=2)); print('DELTA',json.dumps(comparison,indent=2))
