#!/usr/bin/env python3
"""Full, cached, parallel assertion index for Predator 8.

This module is an engineering replacement for Predator 8.001's eager serial
Index constructor.  It does NOT change which pre-target assertions are
available to proof search and it does not change proof semantics.

Key properties
--------------
* Every logical $a/$p assertion before the target is still indexed.
* Conclusion parsing is parallelised on POSIX/fork platforms.
* A per-formula watchdog prevents one pathological parse from monopolising the
  whole build.  Timed-out formulas are retried with progressively larger
  limits; if any still cannot be parsed, the build FAILS rather than silently
  omitting them.
* A successful full index is pickled atomically and reused on later runs.
* Cache validity is checked against a SHA-256 signature of the exact ordered
  pre-target logical corpus, so a cache from a different database cannot be
  accepted accidentally.
"""
from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import pickle
import signal
import time
from collections import defaultdict

P8 = None
_BY_TC = None


class _ParseTimeout(Exception):
    pass


def configure(p8):
    global P8
    P8 = p8


def _alarm(_signum, _frame):
    raise _ParseTimeout()


def _parse_worker(task):
    """Parse one conclusion in a forked worker with a wall-clock guard."""
    lab, toks, timeout_s = task
    if P8 is None or _BY_TC is None:
        return lab, "error", "worker not configured"
    old_handler = None
    try:
        if hasattr(signal, "SIGALRM") and timeout_s:
            old_handler = signal.signal(signal.SIGALRM, _alarm)
            signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
        t = P8.G.parse(toks, "wff", _BY_TC)
        if t is None:
            return lab, "error", "parse returned None"
        return lab, "ok", t
    except _ParseTimeout:
        return lab, "timeout", None
    except RecursionError:
        return lab, "error", "RecursionError"
    except Exception as e:
        return lab, "error", "%s: %s" % (type(e).__name__, e)
    finally:
        if hasattr(signal, "SIGALRM"):
            try:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
            except Exception:
                pass


def _logical_jobs(mm, upto):
    order = mm.order[:upto] if upto is not None else mm.order
    jobs = []
    for lab in order:
        typ, data = mm.labels[lab]
        if typ not in ("$a", "$p"):
            continue
        concl = data[3]
        if not concl or concl[0] != "|-" or len(concl) < 2:
            continue
        jobs.append((lab, tuple(concl[1:])))
    return jobs


def _corpus_signature(mm, upto):
    h = hashlib.sha256()
    for lab, toks in _logical_jobs(mm, upto):
        h.update(lab.encode("utf-8")); h.update(b"\0")
        h.update(" ".join(toks).encode("utf-8")); h.update(b"\0")
    return h.hexdigest()


def _parallel_pass(pending, timeout_s, workers, say):
    """Return (parsed_dict, timed_out_labels, errors)."""
    if not pending:
        return {}, [], []
    tasks = [(lab, toks, timeout_s) for lab, toks in pending]
    parsed, slow, errors = {}, [], []
    t0 = time.perf_counter()
    done = 0

    # GitHub's Ubuntu runners support fork.  Fork matters here because workers
    # inherit the already-built grammar tables without serialising/rebuilding
    # them for every process.
    ctx = mp.get_context("fork")
    with ctx.Pool(processes=workers, maxtasksperchild=2000) as pool:
        for lab, status, payload in pool.imap_unordered(
                _parse_worker, tasks, chunksize=8):
            done += 1
            if status == "ok":
                parsed[lab] = payload
            elif status == "timeout":
                slow.append(lab)
            else:
                errors.append((lab, payload))
            if say and (done % 2000 == 0 or done == len(tasks)):
                dt = max(time.perf_counter() - t0, 1e-9)
                say("    parsed %s/%s in this pass (%.0f assertions/s; %d deferred)"
                    % (f"{done:,}", f"{len(tasks):,}", done / dt, len(slow)))
    return parsed, slow, errors


def _sequential_pass(pending, timeout_s, say):
    """Portable fallback; also guarded on POSIX."""
    parsed, slow, errors = {}, [], []
    for i, (lab, toks) in enumerate(pending, 1):
        a, status, payload = _parse_worker((lab, toks, timeout_s))
        if status == "ok":
            parsed[a] = payload
        elif status == "timeout":
            slow.append(a)
        else:
            errors.append((a, payload))
        if say and i % 1000 == 0:
            say("    parsed %s/%s in sequential pass" %
                (f"{i:,}", f"{len(pending):,}"))
    return parsed, slow, errors


class CachedParallelIndex:
    """Drop-in replacement for Predator 8.001.Index."""

    CACHE_VERSION = 3

    def __init__(self, mm, by_tc, upto=None, say=None):
        if P8 is None:
            raise RuntimeError("predator_index_cache.configure(P8) was not called")
        self.by_tc = by_tc
        self.closers = defaultdict(list)
        self.openers = defaultdict(list)
        self.n = 0
        self._hyp_cache = {}

        cache_path = os.environ.get("PREDATOR_INDEX_CACHE", "").strip()
        sig = _corpus_signature(mm, upto)
        parsed = None

        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    payload = pickle.load(f)
                if (payload.get("version") == self.CACHE_VERSION and
                        payload.get("signature") == sig):
                    parsed = payload.get("parsed")
                    if say:
                        say("    loaded full cached assertion index: %s"
                            % cache_path)
                elif say:
                    say("    index cache exists but does not match this corpus; rebuilding")
            except Exception as e:
                if say:
                    say("    index cache could not be read (%s); rebuilding" % e)

        jobs = _logical_jobs(mm, upto)
        if parsed is None:
            parsed = self._build_full(jobs, by_tc, say)
            if cache_path:
                parent = os.path.dirname(os.path.abspath(cache_path))
                os.makedirs(parent, exist_ok=True)
                tmp = cache_path + ".tmp.%d" % os.getpid()
                with open(tmp, "wb") as f:
                    pickle.dump({"version": self.CACHE_VERSION,
                                 "signature": sig,
                                 "parsed": parsed},
                                f, protocol=pickle.HIGHEST_PROTOCOL)
                os.replace(tmp, cache_path)
                if say:
                    say("    saved full assertion index cache: %s" % cache_path)

        # Reattach the current database's assertion frames instead of storing
        # them in the cache.  This makes the cache a parse-tree acceleration,
        # not an alternate source of mathematical content.
        pmap = dict(parsed)
        order = mm.order[:upto] if upto is not None else mm.order
        for lab in order:
            t = pmap.get(lab)
            if t is None:
                continue
            typ, data = mm.labels[lab]
            head = None if t.var is not None else t.label
            (self.closers if not data[2] else self.openers)[head].append(
                (lab, t, data))
            self.n += 1

        if self.n != len(jobs):
            raise RuntimeError(
                "index integrity failure: expected %d logical assertions, loaded %d"
                % (len(jobs), self.n))
        if say:
            nc = sum(len(v) for v in self.closers.values())
            say("    %s assertions indexed (%s close a goal outright) [FULL CACHE]"
                % (f"{self.n:,}", f"{nc:,}"))

    def _build_full(self, jobs, by_tc, say):
        global _BY_TC
        _BY_TC = by_tc
        workers = max(1, min(4, os.cpu_count() or 1))
        if say:
            say("    building FULL pre-target index: %s logical assertions"
                % f"{len(jobs):,}")
            say("    parser workers: %d; no assertion will be silently omitted"
                % workers)

        parsed = {}
        pending = list(jobs)
        # The first three guards handle the normal corpus.  set.mm deliberately
        # contains a few enormous parser stress tests; after the exact split-
        # point pruning was installed, quartfull remained the sole outlier just
        # beyond the 90-second guard.  Give any final outlier one bounded
        # 10-minute pass.  This is preprocessing only; it does not consume the
        # declared 50-minute Halo proof-search tranche.
        timeouts = (2.0, 15.0, 90.0, 600.0)
        for pass_no, timeout_s in enumerate(timeouts, 1):
            if not pending:
                break
            if say:
                say("    parse pass %d: %s assertions, %.0fs per-formula guard"
                    % (pass_no, f"{len(pending):,}", timeout_s))
            if os.name == "posix" and workers > 1:
                got, slow, errors = _parallel_pass(
                    pending, timeout_s, workers, say)
            else:
                got, slow, errors = _sequential_pass(
                    pending, timeout_s, say)
            parsed.update(got)
            if errors:
                preview = ", ".join("%s (%s)" % x for x in errors[:8])
                raise RuntimeError("index parse errors: %s" % preview)
            slowset = set(slow)
            pending = [(lab, toks) for lab, toks in pending if lab in slowset]
            if say and pending:
                say("    %s unusually slow assertions deferred to the next pass"
                    % f"{len(pending):,}")

        if pending:
            labs = ", ".join(lab for lab, _ in pending[:20])
            raise RuntimeError(
                "full index build refused to omit %d assertions still exceeding "
                "the 600s final parse guard: %s" % (len(pending), labs))

        # Preserve declaration order exactly.  Search tie behaviour must not
        # depend on multiprocessing completion order.
        out = [(lab, parsed[lab]) for lab, _ in jobs]
        if say:
            say("    full index build complete: %s/%s assertions parsed"
                % (f"{len(out):,}", f"{len(jobs):,}"))
        return out

    def candidates(self, goal):
        def grab(d):
            if goal.var is not None:
                return [x for b in d.values() for x in b]
            return d.get(goal.label, []) + d.get(None, [])
        return grab(self.closers), grab(self.openers)

    def parse_hypothesis(self, stat):
        """Exact memoisation for repeatedly used $e-hypothesis formulas."""
        key = tuple(stat[1:])
        t = self._hyp_cache.get(key)
        if t is None:
            t = P8.G.parse(key, "wff", self.by_tc)
            if t is not None:
                self._hyp_cache[key] = t
        return t
