#!/usr/bin/env python3
import argparse, csv, json, os, re, statistics, subprocess, time
from pathlib import Path

TIME_LIMIT=60
SOLVERS={
 'Vampire': lambda p: [os.environ.get('VAMPIRE_BIN','vampire'),'--input_syntax','tptp','-t',str(TIME_LIMIT),'-p','tptp',str(p)],
 'E': lambda p: [os.environ.get('EPROVER_BIN','eprover'),'--auto',f'--cpu-limit={TIME_LIMIT}','--proof-object',str(p)],
 'SPASS': lambda p: ['SPASS','-TPTP=2',f'-TimeLimit={TIME_LIMIT}','-DocProof=1',str(p)],
 'Prover9': lambda p: [os.environ.get('PROVER9_BIN','prover9'),'-t',str(TIME_LIMIT),'-f',str(p)],
}

def status_from_output(name,text,rc,timed_out):
    if timed_out: return 'TIMEOUT'
    if re.search(r'SZS status\s+(Theorem|Unsatisfiable)',text,re.I): return 'PROVED'
    if name=='SPASS' and re.search(r'Proof found',text,re.I): return 'PROVED'
    if re.search(r'SZS status\s+(GaveUp|Unknown|Timeout|ResourceOut|MemoryOut)',text,re.I): return 'BOUNDED_UNKNOWN'
    if rc!=0: return 'FAULT'
    return 'UNKNOWN_OUTPUT'

def native_inference_count(text):
    return len(re.findall(r'\binference\s*\(',text))

def run_one(name,p,outdir):
    cmd=SOLVERS[name](p)
    t0=time.perf_counter(); timed=False
    try:
        cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=TIME_LIMIT,stdin=subprocess.DEVNULL)
        rc=cp.returncode; text=cp.stdout
    except subprocess.TimeoutExpired as e:
        timed=True; rc=124
        text=e.stdout if isinstance(e.stdout,str) else ''
    wall=time.perf_counter()-t0
    od=outdir/name; od.mkdir(parents=True,exist_ok=True)
    (od/(p.stem+'.out')).write_text(text,encoding='utf-8',errors='replace')
    return {'solver':name,'file':p.name,'status':status_from_output(name,text,rc,timed),'wall_s':wall,'returncode':rc,'native_inference_records':native_inference_count(text),'time_limit_s':TIME_LIMIT}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--problems',default='benchmarks/ocean/generated')
    ap.add_argument('--out',default='benchmarks/ocean/results/professional')
    a=ap.parse_args(); probs=Path(a.problems); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    manifest={x['file']:x for x in json.loads((probs/'manifest.json').read_text())}
    rows=[]
    for p in sorted(probs.glob('ocean_L*_seed*.p')):
        for name in SOLVERS:
            r=run_one(name,p,out/'proofs')
            r.update({'Lstar':manifest[p.name]['Lstar'],'seed':manifest[p.name]['seed']})
            rows.append(r)
            print(name,p.name,r['status'],f"{r['wall_s']:.6f}s",flush=True)
    with open(out/'rows.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    summary=[]
    lengths=sorted({r['Lstar'] for r in rows})
    for L in lengths:
        for name in SOLVERS:
            rr=[r for r in rows if r['Lstar']==L and r['solver']==name]
            ok=[r for r in rr if r['status']=='PROVED']
            summary.append({'Lstar':L,'solver':name,'proved':len(ok),'n':len(rr),'median_wall_s':statistics.median([r['wall_s'] for r in ok]) if ok else None,'median_native_inference_records':statistics.median([r['native_inference_records'] for r in ok]) if ok else None,'timeouts':sum(r['status']=='TIMEOUT' for r in rr),'faults':sum(r['status']=='FAULT' for r in rr),'unknown_output':sum(r['status']=='UNKNOWN_OUTPUT' for r in rr),'time_limit_s':TIME_LIMIT})
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
