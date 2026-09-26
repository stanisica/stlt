"""Portable bundle schema and provenance."""

from __future__ import annotations

import hashlib
from pathlib import Path

SEGMENTS = {"smoke": 1, "full": 220}
COUNT_FIELDS = (
    "offered",
    "admitted",
    "delivered",
    "not_started",
    "admitted_not_delivered",
    "failed_computation_attempts",
    "partial_computation_attempts",
    "zero_energy_failed_attempts",
)
ENERGY_FIELDS = (
    "energy_j",
    "wasted_energy_j",
    "compute_energy_j",
    "communication_energy_j",
    "wasted_compute_j",
    "wasted_communication_j",
    "partial_computation_waste_j",
)
OUTPUTS = (
    "main-per-window.csv",
    "resource-per-window.csv",
    "paper-results.json",
    "table1_parameters.csv",
    "table2_candidates.csv",
    "table4_task_outcomes.csv",
    "figure5_points.csv",
    "figure6_reduction.csv",
    "paper_claims.csv",
    "figure5.pdf",
    "figure6.pdf",
    "figure7.pdf",
    "figure8.pdf",
    "MANIFEST.md",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def source_hashes(root: Path) -> dict[str, str]:
    paths = [root / "pyproject.toml", root / "requirements.txt"]
    for directory, pattern in (
        ("src", "*.py"),
        ("experiments", "*.json"),
        ("data", "*.json"),
        ("scripts", "*.sh"),
    ):
        paths.extend((root / directory).rglob(pattern))
    paths.append(root / "reproduce_paper_artifacts.sh")
    return {str(path.relative_to(root)): digest(path) for path in sorted(paths)}
