#!/usr/bin/env python3
"""Predator 8.031 generalized ML pilot. prcom is strictly held out.
Protected goal for model selection: minimize VERIFIED expansions N; proof length is secondary.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,random,statistics,time
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.preprocessing import StandardScaler
import prcom_root_exactify as RX

VERSION='8.031-generalized-heldout-prcom'
PF=['log_goal_nodes','log_cand_nodes','log_size_gap','same_head','closer','e_hyps','f_hyps','dv_pairs','is_theorem','log_known_logic','order_fraction','token_jaccard','goal_vars','cand_vars','depth_gap']
VF=['log_nodes','tree_depth','var_count','log_tokens','e_hyps','f_hyps','dv_pairs','log_candidates','log_closers','log_openers']

def sha256(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def depth(t):
 if t is None or getattr(t,'var',None) is not None:return 1
 return 1+max([depth(k) for k in getattr(t,'kids',())] or [0])

def vars_(t,a=None):
 a=set() if a is None else a
 if t is None:return a
 v=getattr(t,'var',None)
 if v is not None:a.add(v)
 else:
  for k in getattr(t,'kids',()):vars_(k,a)
 return a

def size(t):
 try:return int(t.size())
 except:return 1

def head(t):return None if t is None or getattr(t,'var',None) is not None else getattr(t,'label',None)

def toks(t):
 try:return set(t.tokens())
 except:return set()

def logical_steps(mm,p):return sum(1 for x in p if x in mm.labels and mm.labels[x][0] in ('$a','$p'))

def proof_meta(mm,cut):
 pos={x:i for i,x in enumerate(mm.order[:cut])}; out={}
 for x in mm.order[:cut]:
  typ,_=mm.labels[x]
  if typ=='$a':out[x]=(1.0,pos[x]/max(1,cut))
  elif typ=='$p':
   try:
    p=mm.decompress(x,mm.proofs[x])
    if '?' not in p:out[x]=(float(logical_steps(mm,p)),pos[x]/max(1,cut))
   except:pass
 return out

def feat(g,it,mm,meta):
 lab,ct,data=it; dvs,fh,eh,_=data; gs,cs=size(g),size(ct); a,b=toks(g),toks(ct); u=a|b; km,fr=meta.get(lab,(0.0,0.0))
 return np.array([math.log1p(gs),math.log1p(cs),math.log1p(abs(gs-cs)),float(head(g)==head(ct)),float(not eh),len(eh),len(fh),len(dvs),float(mm.labels.get(lab,(None,))[0]=='$p'),math.log1p(km),fr,len(a&b)/max(1,len(u)),len(vars_(g)),len(vars_(ct)),abs(depth(g)-depth(ct))],float)

def vfeat(goal,data,index):
 dvs,fh,eh,st=data;c,o=index.candidates(goal)
 return np.array([math.log1p(size(goal)),depth(goal),len(vars_(goal)),math.log1p(max(0,len(st)-1)),len(eh),len(fh),len(dvs),math.log1p(len(c)+len(o)),math.log1p(len(c)),math.log1p(len(o))],float)

@dataclass
class T:
 label:str;order:int;steps:int;logic:int;split:str='train';exact_h:int|None=None;lower:int|None=None;exact_steps:int|None=None

@dataclass
class Ctx:
 label:str;cut:int;by_tc:object;index:object;goal:object;data:object;vf:np.ndarray

def context(E,mm,lab):
 cut=mm.order.index(lab);by=RX.strict_prefix_grammar(E,mm,cut);idx=E.Index(mm,by,upto=cut,say=None);data=mm.labels[lab][1];goal=E.G.parse(data[3][1:],'wff',by)
 if goal is None:raise RuntimeError('parse failed '+lab)
 return Ctx(lab,cut,by,idx,goal,data,vfeat(goal,data,idx))

def select(mm,hold,n,gap,seed):
 h=mm.order.index(hold);ps=[i for i,x in enumerate(mm.order[:h]) if mm.labels[x][0]=='$p'];blocked=set(ps[-gap:]) if gap else set();pool=[]
 for i in ps:
  if i in blocked:continue
  x=mm.order[i]
  try:
   p=mm.decompress(x,mm.proofs[x]);st=mm.labels[x][1][3]
   if p and '?' not in p and st and st[0]=='|-':
    q=logical_steps(mm,p)
    if 1<=q<=64:pool.append(T(x,i,len(p),q))
  except:pass
 rng=random.Random(seed);bins=[(1,2),(3,4),(5,8),(9,16),(17,32),(33,64)];out=[];k=max(1,math.ceil(n/len(bins)))
 for lo,hi in bins:
  b=[z for z in pool if lo<=z.logic<=hi];rng.shuffle(b);out+=b[:k]
 if len(out)<n:
  used={z.label for z in out};r=[z for z in pool if z.label not in used];rng.shuffle(r);out+=r[:n-len(out)]
 out=sorted(out[:n],key=lambda z:z.order)
 for z in out:
  q=int(hashlib.sha256((z.label+str(seed)).encode()).hexdigest()[:8],16);z.split='validation' if q%5==0 else 'train'
 if sum(z.split=='validation' for z in out)<4:
  for z in out[-4:]:z.split='validation'
 return out

def final_action(mm,lab):
 p=mm.decompress(lab,mm.proofs[lab])
 for x in reversed(p):
  if x in mm.labels and mm.labels[x][0] in ('$a','$p'):return x
 return None

def dataset(E,mm,targets,meta,seed):
 rng=random.Random(seed+7);X=[];y=[];vg=[];ctxs={};rows={}
 for j,z in enumerate(targets,1):
  print(f'[DATA] {j}/{len(targets)} {z.label} {z.split} logic={z.logic}')
  try:c=context(E,mm,z.label);ctxs[z.label]=c;act=final_action(mm,z.label);cl,op=c.index.candidates(c.goal);items=cl+op;pos=next((it for it in items if it[0]==act),None)
  except Exception as e:print('[DATA] skip',z.label,e);continue
  if pos is None:continue
  neg=[it for it in items if it[0]!=act];rng.shuffle(neg);neg=neg[:24];xp=feat(c.goal,pos,mm,meta);rows[z.label]={'candidates':len(items),'action':act}
  if z.split=='train':
   for it in neg:
    d=xp-feat(c.goal,it,mm,meta);X+=[d,-d];y+=[1,0]
  else:vg.append({'theorem':z.label,'goal':c.goal,'items':items,'positive':act})
 return np.vstack(X),np.array(y,int),vg,ctxs,rows

def fit_rank(X,y,C):
 s=StandardScaler(with_mean=False);Xs=s.fit_transform(X);m=LogisticRegression(C=C,fit_intercept=False,max_iter=1000,solver='liblinear',random_state=0).fit(Xs,y);return m.coef_[0]/np.where(s.scale_==0,1,s.scale_)

class Rank:
 def __init__(self,w,mm,meta):self.w,self.mm,self.meta=w,mm,meta
 def scores(self,g,items):return [float(np.dot(self.w,feat(g,it,self.mm,self.meta))) for it in items]
 def __call__(self,g,items):return self.scores(g,items)

def rmetrics(groups,R):
 rr=[]
 for g in groups:
  sc=R.scores(g['goal'],g['items']);order=sorted(range(len(sc)),key=lambda i:sc[i],reverse=True);pi=next((i for i,it in enumerate(g['items']) if it[0]==g['positive']),None)
  if pi is not None:rr.append(order.index(pi)+1)
 return {'groups':len(rr),'top1':sum(x==1 for x in rr)/max(1,len(rr)),'top5':sum(x<=5 for x in rr)/max(1,len(rr)),'mrr':sum(1/x for x in rr)/max(1,len(rr)),'median_rank':statistics.median(rr) if rr else None}

def exact(E,mm,c,dep,bud):
 fv,fb=RX.formal_variables(E,mm,c.cut);pc=RX.Context(E,mm,c.index,c.data,fv,fb);start=E.Node([(c.goal,None,0)],{},(),0);orig=mm.proofs;mm.proofs=RX.GuardedProofs(orig,c.label)
 try:pr=RX.bounded_bfs_exactify(RX.State(start),all_successors=pc.successors,is_settled=lambda s:bool(s.accepted),key=lambda s:s,max_depth=dep,max_expansions=bud,completeness_evidence='strict prefix; all compatible assertions; actual unification; no ranking/cap; verifier terminal edge')
 finally:mm.proofs=orig
 ps=None
 if pr.exact_h is not None and pr.witness and pr.witness.closed is not None:
  root,sub=RX.reconstruct(pr.witness.closed);ps=len(root.emit(sub,fv,fb))
 return pr.exact_h,int(pr.lower_bound),ps,int(pr.expanded)

def verify_result(E,mm,c,res):
 if res is None:return None
 root,sub=res;fv,fb=RX.formal_variables(E,mm,c.cut)
 try:
  p=root.emit(sub,fv,fb);chk=E.MM();chk.labels=dict(mm.labels);chk.order=list(mm.order);chk.proofs={};chk.constants,chk.variables=mm.constants,mm.variables;chk.scope_dvs=dict(mm.scope_dvs);k='__p8_031__';chk.labels[k]=('$p',c.data);chk.proofs[k]=p;chk.scope_dvs[k]=c.data[0]
  return (len(p),logical_steps(chk,p)) if chk.verify(k)=='ok' else None
 except:return None

def run_search(E,mm,c,bud,R):
 prof=E.Profile('det-eval',0,0,0,0,0,64,1);res,n=E.prove(c.goal,c.index,bud,max_depth=12,rank=None if R is None else R,say=None,progress=0,max_open=8,profile=prof,seed=0);q=verify_result(E,mm,c,res)
 return {'verified':q is not None,'expansions':int(n),'proof_steps':None if q is None else q[0],'logical_steps':None if q is None else q[1]}

def eval_search(E,mm,infos,ctxs,bud,R):
 rows=[]
 for z in infos:
  c=ctxs.get(z.label) or context(E,mm,z.label);ctxs[z.label]=c;r=run_search(E,mm,c,bud,R);r['theorem']=z.label;rows.append(r)
 key=(sum(not r['verified'] for r in rows),sum(r['expansions'] if r['verified'] else bud for r in rows),sum(r['proof_steps'] or 10**6 for r in rows))
 return rows,key

def value_heads(targets,ctxs):
 rows=[(z,ctxs[z.label]) for z in targets if z.label in ctxs];X=np.array([c.vf for z,c in rows]);yp=np.log1p(np.array([z.logic for z,c in rows],float));s=StandardScaler().fit(X);m=Ridge(alpha=1).fit(s.transform(X),yp);out={'features':VF,'proof_proxy':{'mean':s.mean_.tolist(),'scale':s.scale_.tolist(),'coef':m.coef_.tolist(),'intercept':float(m.intercept_),'target':'log1p(known verified logical proof steps; not claimed shortest)'}}
 ex=[(z,c) for z,c in rows if z.exact_h is not None]
 if len(ex)>=5:
  Xe=np.array([c.vf for z,c in ex]);ye=np.array([z.exact_h for z,c in ex],float);se=StandardScaler().fit(Xe);me=Ridge(alpha=.5).fit(se.transform(Xe),ye);out['exact_h']={'n':len(ex),'mean':se.mean_.tolist(),'scale':se.scale_.tolist(),'coef':me.coef_.tolist(),'intercept':float(me.intercept_),'target':'certified exact root H'}
 else:out['exact_h']={'n':len(ex),'status':'insufficient exact labels'}
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('environment');ap.add_argument('--engine',required=True);ap.add_argument('--holdout',default='prcom');ap.add_argument('--holdout-gap',type=int,default=32);ap.add_argument('--targets',type=int,default=64);ap.add_argument('--exact-targets',type=int,default=12);ap.add_argument('--exact-depth',type=int,default=4);ap.add_argument('--exact-budget',type=int,default=4000);ap.add_argument('--search-eval',type=int,default=6);ap.add_argument('--search-budget',type=int,default=1500);ap.add_argument('--seed',type=int,default=2301);ap.add_argument('--out',default='p8_031_generalized_model.json');ap.add_argument('--report',default='p8_031_training_report.json');ap.add_argument('--csv',default='p8_031_training_theorems.csv');a=ap.parse_args();t0=time.perf_counter()
 E=RX.load_engine(a.engine);mm=E.load(a.environment,say=print);hold=mm.order.index(a.holdout);print(f'[GUARD] holdout={a.holdout}; proof_used=False downstream=False gap={a.holdout_gap}');meta=proof_meta(mm,hold);ts=select(mm,a.holdout,a.targets,a.holdout_gap,a.seed);print('[SELECT]',len(ts),'train',sum(z.split=='train' for z in ts),'val',sum(z.split=='validation' for z in ts));X,y,vg,ctxs,drows=dataset(E,mm,ts,meta,a.seed);print('[PAIRS]',len(y),'policy parameters',len(PF))
 for i,z in enumerate(sorted(ts,key=lambda q:(q.logic,q.order))[:a.exact_targets],1):
  try:c=ctxs.get(z.label) or context(E,mm,z.label);ctxs[z.label]=c;z.exact_h,z.lower,z.exact_steps,n=exact(E,mm,c,a.exact_depth,a.exact_budget);print(f'[EXACT] {i} {z.label} exact_h={z.exact_h} H>={z.lower} expanded={n}')
  except Exception as e:print('[EXACT] fail',z.label,e)
 vals=sorted([z for z in ts if z.split=='validation'],key=lambda q:(q.logic,q.order))[:a.search_eval];base,bkey=eval_search(E,mm,vals,ctxs,a.search_budget,None);print('[BASELINE]',bkey,base);best=None;cands=[]
 for C in [.05,.2,1.,5.]:
  w=fit_rank(X,y,C);R=Rank(w,mm,meta);rm=rmetrics(vg,R);sr,key=eval_search(E,mm,vals,ctxs,a.search_budget,R);print('[MODEL]',C,'protected',key,'rank',rm);rec={'C':C,'weights':w.tolist(),'ranking':rm,'search':sr,'protected_key':list(key)};cands.append(rec)
  if best is None or key<best[0]:best=(key,C,w,rm,sr)
 key,C,w,rm,sr=best;vh=value_heads(ts,ctxs);model={'version':VERSION,'protected_goal':'minimize verified expansions N; V=1 hard constraint','environment_sha256':sha256(a.environment),'holdout':{'label':a.holdout,'target_proof_used':False,'downstream_used':False,'excluded_preceding_theorems':a.holdout_gap},'policy':{'kind':'linear_pairwise_structural_ranker','features':PF,'weights':w.tolist(),'n_parameters':len(w),'C':C,'validation_ranking':rm,'validation_protected_key':list(key)},'value_heads':vh};Path(a.out).write_text(json.dumps(model,indent=2,sort_keys=True)+'\n')
 rep={'version':VERSION,'elapsed_seconds':time.perf_counter()-t0,'targets':[z.__dict__ for z in ts],'training_pairs':len(y),'validation_groups':len(vg),'baseline_search':base,'baseline_protected_key':list(bkey),'candidates':cands,'selected_C':C,'selected_protected_key':list(key),'selected_search':sr,'weights':dict(zip(PF,map(float,w))),'exact_labels':sum(z.exact_h is not None for z in ts),'environment_sha256':sha256(a.environment)};Path(a.report).write_text(json.dumps(rep,indent=2,sort_keys=True)+'\n')
 with open(a.csv,'w',newline='') as f:
  cw=csv.writer(f);cw.writerow(['label','split','known_steps','known_logical_steps','exact_h','lower_bound','exact_proof_steps','root_candidates','final_action'])
  for z in ts:
   d=drows.get(z.label,{});cw.writerow([z.label,z.split,z.steps,z.logic,z.exact_h,z.lower,z.exact_steps,d.get('candidates'),d.get('action')])
 print('[SELECTED] C',C,'protected',key);print('[DONE]',a.out,a.report,a.csv);[print(f'  {n:36s}{v:+.8f}') for n,v in zip(PF,w)]
 return 0
if __name__=='__main__':raise SystemExit(main())
