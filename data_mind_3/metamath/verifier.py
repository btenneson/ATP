from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import tempfile


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    returncode: int
    stdout: str
    stderr: str
    verifier: str


def replace_target_proof(source_text: str, label: str, proof_labels: tuple[str, ...]) -> str:
    """Replace only the target proof after search has produced a candidate."""
    pat = re.compile(rf"(\b{re.escape(label)}\s+\$p\s+.*?\$=)(.*?)(\$\.)", re.S)
    m = pat.search(source_text)
    if not m:
        raise ValueError(f"target theorem not found for proof replacement: {label}")
    replacement = m.group(1) + "\n  " + " ".join(proof_labels) + "\n" + m.group(3)
    return source_text[:m.start()] + replacement + source_text[m.end():]


def verify_with_brian_metamath(
    source_path: str | Path,
    target_label: str,
    proof_labels: tuple[str, ...],
    verifier_script: str | Path,
    *,
    timeout_s: float = 600.0,
) -> VerificationResult:
    source_path = Path(source_path)
    text = source_path.read_text(encoding="utf-8")
    candidate = replace_target_proof(text, target_label, proof_labels)
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "candidate.mm"
        db_path.write_text(candidate, encoding="utf-8")
        proc = subprocess.run(
            ["python", str(verifier_script), "verify", str(db_path)],
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
    combined = proc.stdout + "\n" + proc.stderr
    accepted = proc.returncode == 0 and "No errors" in combined
    return VerificationResult(
        accepted,
        proc.returncode,
        proc.stdout,
        proc.stderr,
        "btenneson/metamath.py independent verifier",
    )
