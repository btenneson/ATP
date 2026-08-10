#!/usr/bin/env python3
import argparse, json, random
from collections import defaultdict, deque
from pathlib import Path

def make_ocean(L, seed, dead_factor=18):
    rng=random.Random(seed)
    lens=[L,L+3,L+7,L+11]
    source=0; next_id=1; routes=[]; edges=[]
    for ln in lens:
        route=[source]
        for _ in range(ln-1):
            route.append(next_id); next_id+=1
        routes.append(route)
    target=next_id; next_id+=1
    for route,ln in zip(routes,lens):
        route.append(target)
        edges.extend(zip(route[:-1],route[1:]))
    for ridx,route in enumerate(routes):
        burden=[1.0,1.25,1.45,1.65][ridx]
        for u in route[1:-1]:
            k=rng.randint(0,max(1,int(2*burden)))
            for _ in range(k):
                prev=u
                for _ in range(rng.randint(1,4)):
                    z=next_id; next_id+=1; edges.append((prev,z)); prev=z
                    if rng.random()<0.22:
                        z2=next_id; next_id+=1; edges.append((prev,z2))
    desired=dead_factor*L
    while next_id < target+1+desired:
        route=routes[rng.randrange(len(routes))]
        u=route[rng.randrange(0,len(route)-1)]
        z=next_id; next_id+=1; edges.append((u,z))
        if rng.random()<0.35 and next_id < target+1+desired:
            z2=next_id; next_id+=1; edges.append((z,z2))
    nodes=list(range(next_id)); perm=nodes[:]; rng.shuffle(perm)
    mp=dict(zip(nodes,perm))
    E=[(mp[u],mp[v]) for u,v in edges]
    s=mp[source]; t=mp[target]
    planted=[mp[x] for x in routes[0]]
    adj=defaultdict(list)
    for u,v in E: adj[u].append(v)
    for u in list(adj): rng.shuffle(adj[u])
    return {'Lstar':L,'seed':seed,'source':s,'target':t,'edges':E,'nodes':nodes,'planted':planted,'adj':dict(adj)}

def bfs_distance(g):
    s,t=g['source'],g['target']; q=deque([(s,0)]); seen={s}
    while q:
        u,d=q.popleft()
        if u==t: return d
        for v in g['adj'].get(u,[]):
            if v not in seen:
                seen.add(v); q.append((v,d+1))
    return None

def write_tptp(g,path):
    with open(path,'w',encoding='utf-8') as f:
        f.write(f"% Ocean benchmark L*={g['Lstar']} seed={g['seed']}\n")
        f.write("% Frozen implication encoding. One graph edge = one benchmark resolution inference.\n")
        f.write("% prover9: assign(max_seconds, 300).\n")
        f.write(f"fof(start,axiom,p(n{g['source']})).\n")
        for i,(u,v) in enumerate(g['edges']):
            f.write(f"fof(e{i},axiom,(p(n{u}) => p(n{v}))).\n")
        f.write(f"fof(goal,conjecture,p(n{g['target']})).\n")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='benchmarks/ocean/generated')
    ap.add_argument('--seeds',type=int,default=20)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for L in (20,100):
        for seed in range(1,args.seeds+1):
            g=make_ocean(L,seed)
            d=bfs_distance(g)
            if d != L:
                raise RuntimeError(f'ground-truth failure L={L} seed={seed}: BFS distance={d}')
            name=f'ocean_L{L}_seed{seed}.p'
            write_tptp(g,out/name)
            manifest.append({'file':name,'Lstar':L,'seed':seed,'vertices':len(g['nodes']),'edges':len(g['edges']),'source':g['source'],'target':g['target'],'bfs_verified_Lstar':d})
    with open(out/'manifest.json','w',encoding='utf-8') as f: json.dump(manifest,f,indent=2)
    print(f'generated {len(manifest)} instances; all BFS-verified at declared L*')
if __name__=='__main__': main()
