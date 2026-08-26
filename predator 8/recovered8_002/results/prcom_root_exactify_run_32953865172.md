# prcom root exactification — run 32953865172

## Environment

- Target: `prcom`
- Historical `set.mm` commit: `cd577894d8e6bf8b4fe8014c0d525d531507e4b7`
- `set.mm` SHA256: `1016d7edb0508abde0fe240bb5243e588c5067f8cb10ee6e1cc5733fc05acdb5`
- Strict pre-target assertions indexed: **4,643**
- Exact graph: one unit edge per legal assertion application plus one terminal unit edge for verifier acceptance.
- Search inside the probe: no ML ranking, no opener cap, no stochastic ordering, no policy pruning, and no proof-history quotient. All assertion-head-compatible candidates were subjected to actual unification.
- Stored `prcom` proof was guarded from access.

## Safety checks

- Predator base self-test: passed.
- Settlement-authority / exactifier suite: **19/19 passed**.

## Result

The complete BFS fully checked exact settlement shells 0, 1, and 2. While constructing shell 3, the proof-safe next-layer guard fired at 100,000 distinct proof histories. At that point 556 states had been expanded.

Therefore, by bounded-radius exactification,

\[
H_{prcom}(root) \ge 3.
\]

This conclusion remains valid despite the shell-3 memory guard because shells 0 through 2 had already been completely enumerated and checked for settlement before shell 3 construction was interrupted.

No certificate was emitted. Thus this run makes no settlement claim.

With `h_P=1`,

\[
PC_{prcom}(root) \le 2^{-3}=1/8.
\]

If the old heuristic estimator reports approximately `H_hat=2.165` at the initial state, then this certified lower bound implies

\[
|H-H_hat| \ge 3-2.165 = 0.835 > 1/2.
\]

Hence the old estimator cannot satisfy the Half-Gap certification requirement at the root.

## Implementation implication

Root-level exact BFS is too broad: shell 3 already grows to at least 100,000 distinct proof histories. Exactification should therefore be used as a **local alarm-triggered probe** after ML/heuristic navigation has selected a promising basin. Local probes can certify lower bounds, exact shells, or successor intervals for interval-optimal lock while preserving the independent verifier boundary.
