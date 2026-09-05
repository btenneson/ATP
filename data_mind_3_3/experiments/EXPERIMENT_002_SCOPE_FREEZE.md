# DATA MIND 3.3 Experiment 002 Scope Freeze

Frozen before launch.

- Benchmark: DATA-MIND set.mm Frozen-20 Benchmark 001.
- Dreamer: OFF in all arms.
- Child play: OFF in all arms.
- Controller observation/update interval: 16 in all arms.
- Manipulated variable only: actual Professor-call cadence: OFF, 16, 64, 256 expansions.
- Search limits: 100000 expansions, 1800 s, candidate cap 64, max depth 24, max open goals 24, max frontier 200000.
- Independent Metamath verifier required for every PROVED result.
- Proof-redacted held-out protocol identical to Experiment 001.
- Primary endpoint: verifier-accepted settlements per arm.
- No silent parameter changes after launch.

Frozen implementation blobs at preparation time:
- benchmark lock: `2725ae80c22bf0dd74a38ed1ba4ffb21a7ad7b9c`
- ReflectiveP1Controller actual-call implementation: `5227de6409f0008257f6eb11a579d387ae261df6`
- Experiment 002 config: `bd94d6ea144d03dcd875cf410e7151f4dfd3e8b3`
- Experiment 002 lane: `1b9ac235666ed05a3948737b739d123d4e39056c`
