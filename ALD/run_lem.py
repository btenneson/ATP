from ald.benchmark_lem import run_classical_lem


if __name__ == "__main__":
    result = run_classical_lem()
    print(f"status={result.status.value}")
    print(f"settlement={result.settlement.value if result.settlement else None}")
    print(f"expansions={result.expansions}")
    print(f"activations={result.activations}")
    print(f"environment_hash={result.environment_hash}")
    print(f"target_hash={result.target_hash}")
    for line in result.log:
        print(line)
