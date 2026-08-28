#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_ocean_tptp import bfs_distance, make_ocean, write_tptp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    g = make_ocean(args.length, args.seed)
    d = bfs_distance(g)
    if d != args.length:
        raise RuntimeError(
            f"ground-truth failure L={args.length} seed={args.seed}: BFS distance={d}"
        )
    name = f"ocean_L{args.length}_seed{args.seed}.p"
    write_tptp(g, args.out / name)
    rec = {
        "file": name,
        "Lstar": args.length,
        "seed": args.seed,
        "vertices": len(g["nodes"]),
        "edges": len(g["edges"]),
        "source": g["source"],
        "target": g["target"],
        "bfs_verified_Lstar": d,
    }
    (args.out / "manifest.json").write_text(
        json.dumps([rec], indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
