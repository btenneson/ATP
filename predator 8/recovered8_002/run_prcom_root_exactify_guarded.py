#!/usr/bin/env python3
"""Run the blind-safe prcom root exactifier with a proof-safe layer-size guard."""
import prcom_root_exactify as P

_original = P.bounded_bfs_exactify

def _guarded(*args, **kwargs):
    kwargs.setdefault("max_next_layer", 100000)
    return _original(*args, **kwargs)

P.bounded_bfs_exactify = _guarded

if __name__ == "__main__":
    raise SystemExit(P.main())
