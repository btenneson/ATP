#!/usr/bin/env python3
"""Predator 8.037: paired independent revisers with inverse-guided creativity passes.

Design invariants
-----------------
* Two revising agents are independent.  Each agent alone owns and changes its
  parameter vector.  The partner can publish observations, never assignments.
* The pair exchanges a compact community state at pass boundaries.
* Creativity coordinates use the exact 8.036 logit-addition group.  For every
  coordinate c in (0,1), identity e=.5 and inverse c^-1=1-c.
* A revision pass searches only on the agent's own inverse-directed geodesic.
* Admissible settings satisfy V(theta)=1 by construction: frozen target guards,
  proof unavailability, inference legality and verifier semantics are unchanged.
* Among admissible candidates, the local reviser minimizes the ordered pair
  (H, (H')^2) lexicographically.  H' is a finite-difference estimate along the
  inverse geodesic.  No partner score directly sets another agent's parameters.

This is an experimental controller around 8.036, not a new proof authority.
Any emitted certificate is still checked independently by predator8_external_cv.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import predator8_036_inverse_creativity_prcom as INV

VERSION = "8.037-pcir-paired-revisers"
ROOT = Path(__file__).resolve().parent

# Three-point search is intentionally small for the pilot: current, halfway in
# logit space toward the group inverse, and the full group inverse.
LAMBDAS = (0.0, 0.5, 1.0)
H_PATTERNS = [
    re.compile(r"(?:best[_ -]?H|H_best|bestH)\s*[=:]\s*([-+0-9.eE]+)"),
    re.compile(r"\bH\s*[=:]\s*([-+0-9.eE]+)"),
    re.compile(r"\bh\s*[=:]\s*([-+0-9.eE]+)"),
]
EXP_PATTERNS = [
    re.compile(r"(?:expansions?|expanded)\s*[=:]\s*(\d+)", re.I),
    re.compile(r"\bexp\s*[=:]\s*(\d+)", re.I),
]


def logit(c: float) -> float:
    if not 0.0 < c < 1.0:
        raise ValueError("creativity group coordinate must lie in (0,1)")
    return math.log(c / (1.0 - c))


def sigmoid(z: float) -> float:
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def inverse_profile(x: Dict[str, float]) -> Dict[str, float]:
    return {k: 1.0 - float(v) for k, v in x.items()}


def inverse_geodesic(x: Dict[str, float], lam: float) -> Dict[str, float]:
    """Move from x to x^-1 in the logit-addition group.

    logit(x^-1)=-logit(x), hence the geodesic coordinate is
    (1-lam)logit(x)+lam(-logit(x)) = (1-2lam)logit(x).
    """
    return {k: sigmoid((1.0 - 2.0 * lam) * logit(float(v))) for k, v in x.items()}


def v_admissible(x: Dict[str, float]) -> bool:
    """V(theta)=1 parameter/admissibility constraint for this pilot."""
    if set(x) != set(INV.X):
        return False
    try:
        for c in x.values():
            if not 0.0 < float(c) < 1.0:
                return False
        # Audit each coordinate against the inherited group law.
        for c in x.values():
            if abs(INV.group_op(float(c), 1.0 - float(c)) - 0.5) > 1e-12:
                return False
    except Exception:
        return False
    return True


def extract_h(text: str) -> Optional[float]:
    vals: List[float] = []
    for pat in H_PATTERNS:
        for m in pat.finditer(text):
            try:
                v = float(m.group(1))
                if math.isfinite(v):
                    vals.append(v)
            except ValueError:
                pass
    return min(vals) if vals else None


def extract_expansions(text: str) -> Optional[int]:
    vals: List[int] = []
    for pat in EXP_PATTERNS:
        for m in pat.finditer(text):
            try:
                vals.append(int(m.group(1)))
            except ValueError:
                pass
    return max(vals) if vals else None


@dataclass
class Observation:
    agent: str
    pass_no: int
    lam: float
    profile: Dict[str, float]
    v: int
    h: Optional[float]
    hprime2: Optional[float]
    expansions: Optional[int]
    settled: bool
    verified: bool
    rc: int
    log_path: str
    cert_path: str


def worker_run(profile: Dict[str, float], seed: int, budget: int, stem: str) -> Tuple[int, str, str]:
    """Run one frozen 8.036-compatible search with an arbitrary audited profile."""
    if not v_admissible(profile):
        raise RuntimeError("V(theta)=0: inadmissible profile")
    profile_json = json.dumps(profile, sort_keys=True, separators=(",", ":"))
    cmd = [
        sys.executable, str(Path(__file__).resolve()), "--worker",
        "--profile-json", profile_json,
        "--seed", str(seed), "--budget", str(budget), "--stem", stem,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout, str(ROOT / f"{stem}.mm")


def worker_main(ns: argparse.Namespace) -> int:
    profile = json.loads(ns.profile_json)
    if not v_admissible(profile):
        print("[P837-V] 0")
        return 2

    # Fresh process: safely install one custom profile into the inherited 8.036
    # runner.  This changes only soft creativity controls.
    INV.PROFILES["pcir-custom"] = dict(profile)
    print(f"[P837] worker version={VERSION} seed={ns.seed} V=1")
    print("[P837-PROFILE] " + json.dumps(profile, sort_keys=True))
    argv = [
        sys.argv[0], "set.mm", "--engine", "Predator_8.001_FROZEN.py",
        "--model", "prcom_quick_policy.joblib", "--label", "prcom",
        "--seed", str(ns.seed), "--treatment", "pcir-custom",
        "--budget", str(ns.budget), "--brute-reserve", "0",
        "--max-open", "8", "--progress", "10", "--frontier-limit", "120000",
        "--probe-depth", "0", "--probe-cap", "0", "--probe-total-cap", "0",
        "--probe-next-layer", "0", "--out", f"{ns.stem}.mm",
    ]
    old = sys.argv
    sys.argv = argv
    try:
        return int(INV.main() or 0)
    finally:
        sys.argv = old


def verify_certificate(cert: str) -> bool:
    p = Path(cert)
    if not p.exists() or p.stat().st_size == 0:
        return False
    cmd = [sys.executable, "predator8_external_cv.py", "set.mm",
           "--target", "prcom", "--certificate", p.name]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    Path(str(p) + ".cv.log").write_text(proc.stdout, encoding="utf-8")
    return proc.returncode == 0


def finite_difference_h2(points: List[Tuple[float, Optional[float]]]) -> Dict[float, Optional[float]]:
    """Estimate (H')^2 along lambda using neighboring sampled H values."""
    out: Dict[float, Optional[float]] = {}
    usable = [(x, h) for x, h in points if h is not None]
    usable.sort()
    for i, (x, h) in enumerate(usable):
        if len(usable) < 2:
            out[x] = None
            continue
        if i == 0:
            x2, h2 = usable[i + 1]
            d = (h2 - h) / (x2 - x)
        elif i == len(usable) - 1:
            x1, h1 = usable[i - 1]
            d = (h - h1) / (x - x1)
        else:
            x1, h1 = usable[i - 1]
            x2, h2 = usable[i + 1]
            d = (h2 - h1) / (x2 - x1)
        out[x] = d * d
    for x, h in points:
        out.setdefault(x, None)
    return out


def objective_key(o: Observation) -> Tuple[float, float, float, float]:
    """Local choice: V=1 first, then min H, then min H'^2.

    If the engine exposes no numeric H in a candidate log, that candidate is not
    allowed to win merely due to missing telemetry.  Settlement/verification are
    tie-break evidence, never a replacement definition of H.
    """
    if o.v != 1 or o.h is None:
        return (math.inf, math.inf, math.inf, o.lam)
    hp2 = o.hprime2 if o.hprime2 is not None else math.inf
    verify_penalty = 0.0 if o.verified else 1.0
    return (o.h, hp2, verify_penalty, o.lam)


@dataclass
class RevisingAgent:
    name: str
    seed: int
    theta: Dict[str, float]
    history: List[Observation]

    def make_pass(self, pass_no: int, budget: int, community: dict) -> dict:
        # Community is readable context only.  It is logged but does not assign theta.
        print(f"[P837-COMMUNITY-READ] agent={self.name} pass={pass_no} context={json.dumps(community, sort_keys=True)}")
        candidates: List[Observation] = []
        h_points: List[Tuple[float, Optional[float]]] = []
        for lam in LAMBDAS:
            profile = inverse_geodesic(self.theta, lam)
            v = 1 if v_admissible(profile) else 0
            stem = f"p8_037_{self.name}_P{pass_no}_L{str(lam).replace('.', 'p')}_S{self.seed}"
            if not v:
                obs = Observation(self.name, pass_no, lam, profile, 0, None, None,
                                  None, False, False, 2, "", "")
            else:
                rc, text, cert = worker_run(profile, self.seed, budget, stem)
                log_path = ROOT / f"{stem}.log"
                log_path.write_text(text, encoding="utf-8")
                h = extract_h(text)
                exp = extract_expansions(text)
                settled = Path(cert).exists() and Path(cert).stat().st_size > 0
                verified = verify_certificate(cert) if settled else False
                obs = Observation(self.name, pass_no, lam, profile, 1, h, None,
                                  exp, settled, verified, rc, str(log_path), cert)
            candidates.append(obs)
            h_points.append((lam, obs.h))

        hp2 = finite_difference_h2(h_points)
        for obs in candidates:
            obs.hprime2 = hp2.get(obs.lam)
            self.history.append(obs)
            print("[P837-CANDIDATE] " + json.dumps(asdict(obs), sort_keys=True))

        selectable = [o for o in candidates if math.isfinite(objective_key(o)[0])]
        if selectable:
            chosen = min(selectable, key=objective_key)
            # Ownership invariant: only this method on this object mutates self.theta.
            self.theta = dict(chosen.profile)
            choice_reason = "min_lexicographic_H_Hprime2_under_V1"
        else:
            # If H telemetry is absent, do not fake an optimizer.  Make the explicit
            # group-inverse revision requested by the experimental rule and flag it.
            self.theta = inverse_profile(self.theta)
            chosen = None
            choice_reason = "H_telemetry_missing_group_inverse_fallback"

        report = {
            "agent": self.name,
            "pass": pass_no,
            "seed": self.seed,
            "choice_reason": choice_reason,
            "chosen_lambda": None if chosen is None else chosen.lam,
            "chosen_h": None if chosen is None else chosen.h,
            "chosen_hprime2": None if chosen is None else chosen.hprime2,
            "theta": self.theta,
            "partner_wrote_theta": False,
        }
        print("[P837-LOCAL-REVISION] " + json.dumps(report, sort_keys=True))
        return report


def controller_main(ns: argparse.Namespace) -> int:
    INV.audit_group()
    print(f"[P837] version={VERSION} target=prcom agents=2 passes={ns.passes}")
    print("[P837-INVARIANT] each agent alone controls its parameters")
    print("[P837-GROUP] inherited G=((0,1),logit-addition), e=.5, inverse(c)=1-c")
    print("[P837-OBJECTIVE] local lexicographic min (H,(H')^2) subject to V(theta)=1")
    print("[P837-COMMUNITY] partner observations shared; partner assignments forbidden")

    # Distinct initial conditions and seeds preserve genuine independence.
    A = RevisingAgent("PCIR", ns.seed_a, dict(INV.X), [])
    B = RevisingAgent("PARTNER", ns.seed_b, inverse_geodesic(INV.X, 0.25), [])
    community = {"round": 0, "PCIR": None, "PARTNER": None}
    reports = []

    for p in range(1, ns.passes + 1):
        a_report = A.make_pass(p, ns.budget, dict(community))
        # Partner sees PCIR's published report, but PCIR has not and cannot mutate it.
        community_a = {"round": p, "PCIR": a_report, "PARTNER": community.get("PARTNER")}
        b_report = B.make_pass(p, ns.budget, community_a)
        community = {"round": p, "PCIR": a_report, "PARTNER": b_report}
        reports.append(dict(community))
        print("[P837-COMMUNITY-WRITE] " + json.dumps(community, sort_keys=True))

    final = {
        "version": VERSION,
        "passes": ns.passes,
        "budget_per_candidate": ns.budget,
        "PCIR_final": A.theta,
        "PARTNER_final": B.theta,
        "community": reports,
        "ownership_invariant": True,
    }
    Path(ns.summary).write_text(json.dumps(final, indent=2, sort_keys=True), encoding="utf-8")
    print("[P837-FINAL] " + json.dumps(final, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--profile-json")
    ap.add_argument("--stem", default="p8_037_worker")
    ap.add_argument("--seed", type=int, default=2302)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--budget", type=int, default=40)
    ap.add_argument("--seed-a", type=int, default=2302)
    ap.add_argument("--seed-b", type=int, default=2303)
    ap.add_argument("--summary", default="p8_037_pcir_paired_revisers.json")
    return ap.parse_args()


if __name__ == "__main__":
    ns = parse_args()
    if ns.worker:
        if not ns.profile_json:
            raise SystemExit("--worker requires --profile-json")
        raise SystemExit(worker_main(ns))
    raise SystemExit(controller_main(ns))
