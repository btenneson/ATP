#!/usr/bin/env python3
from __future__ import annotations

import argparse, importlib.util, sys, time
from dataclasses import dataclass
from pathlib import Path
from bounded_exactifier import bounded_bfs_exactify

@dataclass(eq=False)
class State:
    node: object | None = None
    accepted: bool = False
    closed: object | None = None

class GuardedProofs:
    def __init__(self, source, blocked):
        self.source=source; self.blocked=blocked
    def __getitem__(self,k):
        if k==self.blocked: raise AssertionError('target proof access attempted: '+k)
        return self.source[k]
    def get(self,k,d=None):
        if k==self.blocked: raise AssertionError('target proof access attempted: '+k)
        return self.source.get(k,d)
    def __contains__(self,k): return k in self.source
    def __iter__(self): return (k for k in self.source if k != self.blocked)
    def keys(self): return [k for k in self.source.keys() if k != self.blocked]
    def items(self): return [(k,v) for k,v in self.source.items() if k != self.blocked]
    def __len__(self): return len(self.source)-int(self.blocked in self.source)

def load_engine(path):
    spec=importlib.util.spec_from_file_location('p8_root_exact',str(path))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m

def strict_prefix_grammar(E,mm,cutoff):
    p=type('PrefixMM',(),{})(); p.order=mm.order[:cutoff]; p.labels=mm.labels
    return E.G.build_grammar(p)

def formal_variables(E,mm,cutoff):
    fvar,fallback={},{}
    for lab in mm.order[:cutoff]:
        typ,d=mm.labels[lab]
        if typ=='$f':
            fvar.setdefault(d[1],lab)
            fallback.setdefault(d[0],E.G.Tree(None,d[0],(),d[1]))
    return fvar,fallback

def reconstruct(node):
    root=None
    for parent,ix,st in node.trail:
        if parent is None: root=st
        else: parent.subs[ix]=st
    return root,node.sub

class Context:
    def __init__(self,E,mm,index,target_data,fvar,fallback):
        self.E,self.mm,self.index,self.target_data=E,mm,index,target_data
        self.fvar,self.fallback=fvar,fallback
    def verifies_closed(self,node):
        if node.goals: return False
        try:
            root,sub=reconstruct(node)
            if root is None:return False
            proof=root.emit(sub,self.fvar,self.fallback)
            E=self.E; chk=E.MM()
            chk.labels=dict(self.mm.labels); chk.order=list(self.mm.order)
            chk.proofs={}  # blind: never copy/read stored target proof
            chk.constants,chk.variables=self.mm.constants,self.mm.variables
            chk.scope_dvs=dict(self.mm.scope_dvs)
            chk.labels['__probe__']=('$p',self.target_data)
            chk.proofs['__probe__']=proof
            chk.scope_dvs['__probe__']=self.target_data[0]
            return chk.verify('__probe__')=='ok'
        except Exception:
            return False
    def successors(self,s):
        if s.accepted or s.node is None:return ()
        node=s.node; E=self.E
        if not node.goals:
            return (State(None,True,node),) if self.verifies_closed(node) else ()
        gi=E.pick_goal(node.goals,node.sub)
        gt,slot,hix=node.goals[gi]; rest=node.goals[:gi]+node.goals[gi+1:]
        gt=E.apply_sub(gt,node.sub)
        closers,openers=self.index.candidates(gt)
        out=[]
        for lab,ct,data in closers+openers:
            m={}; c2=E.rename_apart(ct,m); s2=E.unify(c2,gt,node.sub)
            if s2 is None: continue
            _,f_hyps,e_hyps,_=data
            fmap={var:m.get(var,E.fresh(tc)) for _,tc,var in f_hyps}
            for _,tc,var in f_hyps:m.setdefault(var,fmap[var])
            step=E.Step(lab,fmap,data); new=[]; ok=True
            for hj,(_,stat) in enumerate(e_hyps):
                try: ht=E.G.parse(stat[1:],'wff',self.index.by_tc)
                except (RecursionError,E.MMError): ht=None
                if ht is None: ok=False; break
                new.append((E.rename_apart(ht,m),step,hj))
            if ok:
                out.append(State(E.Node(new+rest,s2,node.trail+((slot,hix,step),),node.depth+1)))
        return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('environment'); ap.add_argument('--engine',required=True)
    ap.add_argument('--target',default='prcom'); ap.add_argument('--depth',type=int,default=5)
    ap.add_argument('--budget',type=int,default=30000); ap.add_argument('--out',default='prcom_exactify.mm')
    a=ap.parse_args(); E=load_engine(a.engine)
    t0=time.perf_counter(); mm=E.load(a.environment,say=print)
    cut=mm.order.index(a.target); by_tc=strict_prefix_grammar(E,mm,cut)
    idx=E.Index(mm,by_tc,upto=cut,say=print)
    stat=mm.labels[a.target][1][3]; goal=E.G.parse(stat[1:],'wff',by_tc)
    fvar,fallback=formal_variables(E,mm,cut); target_data=mm.labels[a.target][1]
    original=mm.proofs; mm.proofs=GuardedProofs(original,a.target)
    ctx=Context(E,mm,idx,target_data,fvar,fallback)
    start=E.Node([(goal,None,0)],{},(),0)
    print(f'ROOT EXACTIFY target={a.target} depth<={a.depth} budget={a.budget}')
    try:
        pr=bounded_bfs_exactify(State(start),all_successors=ctx.successors,
            is_settled=lambda s:s.accepted,key=lambda s:s,max_depth=a.depth,
            max_expansions=a.budget,
            completeness_evidence='strict pre-target assertion index; all compatible candidates; actual unification; no cap/ranking/pruning; no history quotient; verifier terminal edge')
    finally:
        mm.proofs=original
    print('PROBE',pr)
    print('elapsed %.1fs'%(time.perf_counter()-t0))
    if pr.exact_h is None:
        print(f'CERTIFIED RESULT: H({a.target} root) >= {pr.lower_bound} in the declared unit proof graph')
        return 1
    w=pr.witness
    root,sub=reconstruct(w.closed)
    proof=root.emit(sub,fvar,fallback)
    out=Path(a.out)
    out.write_text(f'$[ {Path(a.environment).name} $]\nchk $p '+ ' '.join(stat)+' $= '+' '.join(proof)+' $.\n')
    chk=E.MM(); chk.labels=dict(mm.labels); chk.order=list(mm.order); chk.proofs={}
    chk.constants,chk.variables=mm.constants,mm.variables; chk.scope_dvs=dict(mm.scope_dvs)
    chk.labels['__final__']=('$p',target_data); chk.proofs['__final__']=proof; chk.scope_dvs['__final__']=target_data[0]
    verdict=chk.verify('__final__')
    print(f'CERTIFIED RESULT: exact H={pr.exact_h}; proof steps={len(proof)}; CV={verdict}; wrote {out}')
    return 0 if verdict=='ok' else 2

if __name__=='__main__': raise SystemExit(main())
