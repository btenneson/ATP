from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
import re
import time


HEADER_RE = re.compile(r"^%\s*Ocean benchmark L\*=(\d+) seed=(\d+)\s*$")
START_RE = re.compile(r"^fof\(start,axiom,p\(n(\d+)\)\)\.\s*$")
EDGE_RE = re.compile(r"^fof\(e\d+,axiom,\(p\(n(\d+)\)\s*=>\s*p\(n(\d+)\)\)\)\.\s*$")
GOAL_RE = re.compile(r"^fof\(goal,conjecture,p\(n(\d+)\)\)\.\s*$")


@dataclass(frozen=True)
class OceanProblem:
    source: int
    target: int
    edges: tuple[tuple[int, int], ...]
    declared_depth: int | None = None
    declared_seed: int | None = None


@dataclass
class OceanSearchResult:
    status: str
    path: tuple[int, ...] = ()
    visited_nodes: int = 0
    frontier_peak: int = 0
    elapsed_s: float = 0.0
    historian: list[dict[str, object]] = field(default_factory=list)
    reason: str = ""

    @property
    def certificate_transitions(self) -> int:
        return max(0, len(self.path) - 1)


def parse_ocean_tptp(path: Path) -> OceanProblem:
    source: int | None = None
    target: int | None = None
    declared_depth: int | None = None
    declared_seed: int | None = None
    edges: list[tuple[int, int]] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = HEADER_RE.match(line)
            if m:
                declared_depth = int(m.group(1))
                declared_seed = int(m.group(2))
                continue
            m = START_RE.match(line)
            if m:
                source = int(m.group(1))
                continue
            m = EDGE_RE.match(line)
            if m:
                edges.append((int(m.group(1)), int(m.group(2))))
                continue
            m = GOAL_RE.match(line)
            if m:
                target = int(m.group(1))

    if source is None:
        raise ValueError("Ocean problem is missing start axiom")
    if target is None:
        raise ValueError("Ocean problem is missing goal conjecture")
    if not edges and source != target:
        raise ValueError("Ocean problem has no implication edges")
    return OceanProblem(
        source=source,
        target=target,
        edges=tuple(edges),
        declared_depth=declared_depth,
        declared_seed=declared_seed,
    )


def shortest_path_bfs(
    problem: OceanProblem,
    *,
    timeout_s: float = 1800.0,
    breadcrumb_depth: int = 1000,
) -> OceanSearchResult:
    """Find a shortest Ocean certificate from only the public problem graph.

    This is intentionally plain breadth-first search, not the historical
    specialized Depths-F implementation.  It uses no planted route, generator
    seed, hidden minimum-depth field, or precomputed certificate.  Its purpose
    is to test whether DATA MIND 3.1 can handle and emit a very deep verified
    certificate after PRCOM remains unresolved.
    """

    start_time = time.monotonic()
    if problem.source == problem.target:
        return OceanSearchResult(
            status="PROVED",
            path=(problem.source,),
            visited_nodes=1,
            frontier_peak=1,
            elapsed_s=0.0,
            reason="source_is_target",
        )

    adj: dict[int, list[int]] = defaultdict(list)
    for u, v in problem.edges:
        adj[u].append(v)

    q = deque([problem.source])
    parent: dict[int, int | None] = {problem.source: None}
    depth: dict[int, int] = {problem.source: 0}
    frontier_peak = 1
    historian: list[dict[str, object]] = [{
        "actor": "OceanP1",
        "action": "start_bfs",
        "source": problem.source,
        "target": problem.target,
        "declared_depth": problem.declared_depth,
        "edge_count": len(problem.edges),
        "hidden_route_access": False,
    }]
    last_breadcrumb = 0

    while q:
        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_s:
            historian.append({
                "actor": "Sentinel",
                "action": "stop",
                "reason": "timeout",
                "visited_nodes": len(parent),
                "frontier": len(q),
            })
            return OceanSearchResult(
                status="UNKNOWN",
                visited_nodes=len(parent),
                frontier_peak=frontier_peak,
                elapsed_s=elapsed,
                historian=historian,
                reason="timeout",
            )

        u = q.popleft()
        d = depth[u]
        if breadcrumb_depth > 0 and d >= last_breadcrumb + breadcrumb_depth:
            last_breadcrumb = (d // breadcrumb_depth) * breadcrumb_depth
            historian.append({
                "actor": "Historian",
                "action": "depth_breadcrumb",
                "depth": d,
                "visited_nodes": len(parent),
                "frontier": len(q),
            })

        for v in adj.get(u, ()):
            if v in parent:
                continue
            parent[v] = u
            depth[v] = d + 1
            if v == problem.target:
                rev = [v]
                cur = v
                while parent[cur] is not None:
                    cur = parent[cur]  # type: ignore[assignment]
                    rev.append(cur)
                rev.reverse()
                path = tuple(rev)
                elapsed = time.monotonic() - start_time
                historian.append({
                    "actor": "OceanP1",
                    "action": "candidate_path",
                    "depth": len(path) - 1,
                    "visited_nodes": len(parent),
                    "frontier_peak": max(frontier_peak, len(q)),
                })
                return OceanSearchResult(
                    status="CANDIDATE",
                    path=path,
                    visited_nodes=len(parent),
                    frontier_peak=max(frontier_peak, len(q)),
                    elapsed_s=elapsed,
                    historian=historian,
                    reason="shortest_path_found",
                )
            q.append(v)
        frontier_peak = max(frontier_peak, len(q))

    elapsed = time.monotonic() - start_time
    historian.append({
        "actor": "OceanP1",
        "action": "frontier_exhausted",
        "visited_nodes": len(parent),
    })
    return OceanSearchResult(
        status="UNKNOWN",
        visited_nodes=len(parent),
        frontier_peak=frontier_peak,
        elapsed_s=elapsed,
        historian=historian,
        reason="frontier_exhausted",
    )
