#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path

ARMS=("prof-off","prof-16","prof-64","prof-256")

def stat(xs):
    return {"n":len(xs),"mean":statistics.fmean(xs) if xs else None,"median":statistics.median(xs) if xs else None}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    rows=[]
    for p in Path(a.root).rglob('result.json'):
        try: rows.append(json.loads(p.read_text()))
        except Exception: pass
    per={}
    for arm in ARMS:
        rs=[r for r in rows if r.get('arm')==arm]
        verified=[r for r in rs if r.get('status')=='PROVED' and isinstance(r.get('verification'),dict) and r['verification'].get('accepted') is True]
        per[arm]={
            'records':len(rs),'verified_settlements':len(verified),'unknown_or_not_verified':len(rs)-len(verified),
            'actual_professor_calls_total':sum(r['controller']['actual_professor_calls'] for r in rs),
            'expansions_all':stat([r['expansions'] for r in rs]),
            'wall_time_all_s':stat([r['elapsed_search_s'] for r in rs]),
            'accounted_units_all':stat([r['resource_accounting']['accounted_units'] for r in rs]),
        }
    targets={}
    for r in rows: targets.setdefault(r.get('target'),{})[r.get('arm')]=r
    paired={}
    base='prof-256'
    for arm in ('prof-off','prof-16','prof-64'):
        gain=[]; loss=[]; common=[]
        for t,m in targets.items():
            if arm not in m or base not in m: continue
            va=m[arm].get('status')=='PROVED' and m[arm].get('verification',{}).get('accepted') is True
            vb=m[base].get('status')=='PROVED' and m[base].get('verification',{}).get('accepted') is True
            if va and not vb: gain.append(t)
            if vb and not va: loss.append(t)
            if va and vb: common.append(t)
        paired[arm]={'gain_targets':gain,'loss_targets':loss,'net_verified_settlement_gain':len(gain)-len(loss),'common_verified_targets':len(common)}
    out={'experiment':'DATA MIND 3.3 Experiment 002 — Professor Actual-Call Throttle Frozen-20','summary_policy':'verifier-first; workflow success is not theorem success','primary_endpoint':'verified_settlements per arm','expected_records':80,'records_found':len(rows),'complete':len(rows)==80,'per_arm':per,'paired_vs_prof256':paired}
    Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
