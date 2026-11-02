from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_experience(path: Path | None) -> list[dict[str, object]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def save_experience(path: Path | None, rows: Iterable[dict[str, object]]) -> None:
    if path is None:
        return
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
