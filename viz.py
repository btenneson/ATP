import sys, time, random, os
sys.path.insert(0,'.')
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ml_sic_atp import PropositionalSIC
import predator as P

plt.rcParams.update({'font.size':9,'font.family':'serif','figure.dpi':150,
                     'axes.spines.top':False,'axes.spines.right':False})
OUT = sys.argv[1] if len(sys.argv)>1 else '.'
os.makedirs(OUT, exist_ok=True)

sic = PropositionalSIC(max_depth=6, cap=2000, seed=0)
g,_ = sic.run()
gamma=[nd.statement for nd in g.nodes.values() if nd.kind=="axiom"]
th=sorted([nd for nd in g.nodes.values() if nd.kind=="theorem"],key=lambda n:n.order)
train=th[:int(len(th)*0.7)]; test=th[int(len(th)*0.7):]
d=g.closure_depth()
t0=time.perf_counter()
pred=P.Predator(beam=8,seed=0)
pred.train(g,[nd.name for nd in train],sic.size,split_imp=sic.split_imp)
TRAIN_SEC=time.perf_counter()-t0

# ---------- measure by target depth -----------------------------------------
rng=random.Random(0); by_depth={}
for dep in sorted({int(d[n.name]) for n in test if d[n.name]!=float('inf') and d[n.name]>=2}):
    pool=[n for n in test if d[n.name]==dep]
    if len(pool)<3: continue
    sel=rng.sample(pool,min(12,len(pool)))
    rows=[]
    for nd in sel:
        a=time.perf_counter(); rb=P.brute_force_search(sic,gamma,nd.statement,60000); tb=time.perf_counter()-a
        a=time.perf_counter(); rp=P.predator_search(sic,gamma,nd.statement,pred,60000); tp=time.perf_counter()-a
        if rb["found"] and rp["found"]:
            rows.append((rb["expansions"],rp["expansions"],tb,tp))
    if rows:
        A=np.array(rows,float)
        by_depth[dep]=dict(bf_e=A[:,0].mean(),pr_e=A[:,1].mean(),
                           bf_t=A[:,2].mean(),pr_t=A[:,3].mean(),n=len(rows))
print("depth  bf_exp  pr_exp  ratio   bf_ms   pr_ms   n")
for k,v in by_depth.items():
    print(f"{k:>5d} {v['bf_e']:>7.0f} {v['pr_e']:>7.0f} {v['pr_e']/v['bf_e']:>6.3f} "
          f"{1e3*v['bf_t']:>7.1f} {1e3*v['pr_t']:>7.1f} {v['n']:>3d}")

deps=sorted(by_depth)
bf_e=[by_depth[k]['bf_e'] for k in deps]; pr_e=[by_depth[k]['pr_e'] for k in deps]
bf_t=[by_depth[k]['bf_t'] for k in deps]; pr_t=[by_depth[k]['pr_t'] for k in deps]

# ============ FIG 1: what each prover explores ==============================
fig,axes=plt.subplots(1,2,figsize=(7.2,3.0))
tgt=[n for n in test if d[n.name]==max(deps)][0].statement
for ax,mode in zip(axes,["brute","predator"]):
    state={f:0 for f in gamma}; sizes=[]
    for stage in range(1,7):
        new=[f for f in P._consequences(sic,list(state)) if f not in state]
        if not new: break
        if mode=="predator" and tgt not in new:
            F=np.array([pred.features(tgt,f,stage,sic.size,sic.split_imp) for f in new])
            new=[new[i] for i in np.argsort(-pred.score(F))[:pred.beam]]
        for f in new: state[f]=stage
        sizes.append(len(new))
        if tgt in state: break
    ax.bar(range(1,len(sizes)+1),sizes,
           color='#b0b0b0' if mode=="brute" else '#2166A8',width=0.62)
    ax.set_yscale('log'); ax.set_xlabel('stage'); ax.set_ylim(0.7,2000)
    ax.set_title(("brute force: keeps all of $D_F$" if mode=="brute"
                  else f"Predator: keeps top {pred.beam}"),fontsize=9)
    ax.set_ylabel('formulas adjoined at this stage' if mode=="brute" else '')
    for i,s in enumerate(sizes): ax.text(i+1,s*1.25,str(s),ha='center',fontsize=7)
fig.suptitle('What each prover materialises on the way to one target',fontsize=9.5,y=1.0)
fig.tight_layout(); fig.savefig(f'{OUT}/fig_frontier.pdf'); plt.close(fig)

# ============ FIG 2: scaling with target depth ==============================
fig,(a1,a2)=plt.subplots(1,2,figsize=(7.2,2.9))
a1.plot(deps,bf_e,'o-',color='#b0b0b0',label='brute force',ms=4)
a1.plot(deps,pr_e,'s-',color='#2166A8',label='Predator',ms=4)
a1.set_yscale('log'); a1.set_xlabel('closure depth of target')
a1.set_ylabel('expansions'); a1.legend(frameon=False,fontsize=8)
a1.set_title('expansions grow with depth',fontsize=9)
a2.plot(deps,[1e3*t for t in bf_t],'o-',color='#b0b0b0',label='brute force',ms=4)
a2.plot(deps,[1e3*t for t in pr_t],'s-',color='#2166A8',label='Predator',ms=4)
a2.set_xlabel('closure depth of target'); a2.set_ylabel('milliseconds')
a2.legend(frameon=False,fontsize=8); a2.set_title('wall clock: the gap narrows',fontsize=9)
fig.tight_layout(); fig.savefig(f'{OUT}/fig_scaling.pdf'); plt.close(fig)

# ============ FIG 3: what the model learned =================================
names=['bias','token overlap','goal covers cand','cand in goal','size mismatch',
       'cand size','cand depth','cand $\\leq$ goal','IS goal antecedent',
       'detaches TO goal','goal in consequent','IS goal consequent']
w=pred.w
fig,ax=plt.subplots(figsize=(7.2,2.9))
cols=['#2166A8' if v>0 else '#B03030' for v in w]
ax.barh(range(len(w)),w,color=cols)
ax.set_yticks(range(len(w))); ax.set_yticklabels(names,fontsize=7.5)
ax.axvline(0,color='k',lw=0.8); ax.invert_yaxis()
ax.set_xlabel('learned weight (standardised features)')
ax.set_title('What Predator learned: surface features (top 8) vs structural (bottom 4)',fontsize=9)
ax.axhline(7.5,color='0.5',ls=':',lw=1)
fig.tight_layout(); fig.savefig(f'{OUT}/fig_weights.pdf'); plt.close(fig)

# ============ FIG 4: amortisation ==========================================
bf_per=np.mean(bf_t); pr_per=np.mean(pr_t)
N=np.arange(0,401)
fig,ax=plt.subplots(figsize=(7.2,2.9))
ax.plot(N,N*bf_per,color='#b0b0b0',lw=1.6,label='brute force: $N\\,t_{bf}$')
ax.plot(N,TRAIN_SEC+N*pr_per,color='#2166A8',lw=1.6,
        label=f'Predator: $t_{{train}}+N\\,t_{{pr}}$  ($t_{{train}}$={TRAIN_SEC:.2f}s)')
ax.set_xlabel('number of theorems proved, $N$'); ax.set_ylabel('total seconds')
ax.legend(frameon=False,fontsize=8,loc='upper left')
if pr_per < bf_per:
    Nb=TRAIN_SEC/(bf_per-pr_per)
    ax.axvline(Nb,color='k',ls='--',lw=1)
    ax.text(Nb*1.03,ax.get_ylim()[1]*0.35,f'break-even\n$N={Nb:.0f}$',fontsize=8)
    ax.set_title('Training amortises: Predator overtakes brute force at $N^*$',fontsize=9)
else:
    ax.set_title('Training never amortises at this scale: the lines diverge',fontsize=9)
fig.tight_layout(); fig.savefig(f'{OUT}/fig_amortise.pdf'); plt.close(fig)

print(f"\nmean per-proof: brute {1e3*bf_per:.1f} ms   predator {1e3*pr_per:.1f} ms")
print(f"training {TRAIN_SEC:.3f}s")
print("break-even N =", f"{TRAIN_SEC/(bf_per-pr_per):.0f}" if pr_per<bf_per else "never (Predator slower per proof)")
print("figures:", sorted(f for f in os.listdir(OUT) if f.endswith('.pdf')))
