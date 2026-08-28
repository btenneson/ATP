# L*=10 Professional ATP Smoke Test — Official E Build

This branch triggers the frozen 20-instance L*=10 professional ATP benchmark after replacing Ubuntu's crashing DEBUG E package with a pinned build from E's official repository.

All prover invocations have a hard 60-second wall-clock breakpoint. Generated instances are BFS-verified at L*=10 before execution. Raw outputs and exact environment/version data are retained as artifacts.
