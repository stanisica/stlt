"""Independent validation of artifact inputs and paper-result oracles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .arrivals import OrbitSchedule
from .profiles import ModelProfile


@dataclass
class ValidationReport:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def check(self, condition: bool, name: str) -> None:
        (self.passed if condition else self.failed).append(name)

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "PASS" if self.ok else "FAIL",
            "passed": len(self.passed),
            "failed": len(self.failed),
            "checks": self.passed,
            "failures": self.failed,
        }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _equivalent(actual: object, expected: object, tolerance: float = 1e-6) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(actual) - float(expected)) <= tolerance
    if isinstance(expected, dict) and isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            _equivalent(actual[key], expected[key], tolerance) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(actual) == len(expected) and all(
            _equivalent(left, right, tolerance)
            for left, right in zip(actual, expected)
        )
    return actual == expected


def validate(root: Path, output_dir: Path | None = None) -> ValidationReport:
    report = ValidationReport()
    data = root / "data"

    for line in (data / "SHA256SUMS").read_text().splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        path = data / relative
        report.check(path.is_file(), f"input exists: {relative}")
        if path.is_file():
            report.check(_digest(path) == expected, f"input digest: {relative}")

    jetson = root / "hardware" / "jetson"
    for line in (jetson / "SHA256SUMS").read_text().splitlines():
        if not line.strip():
            continue
        expected_digest, relative = line.split(maxsplit=1)
        path = jetson / relative
        report.check(path.is_file(), f"Jetson bundle exists: {relative}")
        if path.is_file():
            report.check(
                _digest(path) == expected_digest,
                f"Jetson bundle digest: {relative}",
            )

    candidate_sets = {
        "squeezenet1_1": [0, 4, 19, 34, 65],
        "swin_v2_t": [0, 112, 327],
        "efficientnet_b4": [0, 40, 102, 164, 502],
        "resnet50": [0, 175],
        "densenet169": [0, 140, 599],
    }
    for model, expected in candidate_sets.items():
        profile = ModelProfile.from_torchfx(
            model, data / "model-profiles" / f"{model}.json"
        )
        actual = [point.layer for point in profile.anoda_candidates()]
        report.check(actual == expected, f"ANODA candidates: {model}")

    main = json.loads((root / "experiments" / "main.json").read_text())
    selected = {row["model"]: row for row in main if row["level"] == "selected"}
    expected_workloads = {
        "squeezenet1_1": (31, 820),
        "swin_v2_t": (365, 65),
        "efficientnet_b4": (119, 210),
        "resnet50": (319, 75),
        "densenet169": (269, 90),
    }
    schedule = OrbitSchedule()
    for model, (interval, offered) in expected_workloads.items():
        row = selected[model]
        report.check(row["interval_s"] == interval, f"nominal interval: {model}")
        report.check(
            schedule.offered_tasks(interval) == offered,
            f"per-orbit offered tasks: {model}",
        )
        report.check(
            row["plan"]["offered_tasks"] == offered,
            f"saved-plan offered tasks: {model}",
        )

    expected = json.loads((data / "expected" / "paper-results.json").read_text())
    nominal = [row for row in expected["figure7"]["rows"] if row["level"] == "nominal"]
    stlt = [row for row in nominal if row["policy"] == "STLT"]
    slice_rows = [row for row in nominal if row["policy"] == "SLICE"]
    offered = sum(row["offered"] for row in stlt)
    stlt_delivered = sum(row["delivered"] for row in stlt)
    slice_delivered = sum(row["delivered"] for row in slice_rows)
    stlt_energy = sum(row["energy_j"] for row in stlt)
    slice_energy = sum(row["energy_j"] for row in slice_rows)
    report.check(offered == 277_200, "headline offered tasks")
    report.check(stlt_delivered == 256_778, "headline STLT deliveries")
    report.check(slice_delivered == 230_426, "headline SLICE deliveries")
    report.check(stlt_delivered - slice_delivered == 26_352, "headline delivery delta")
    report.check(abs(stlt_energy - 11_837_993.26680931) < 1e-6, "headline STLT energy")
    report.check(abs(slice_energy - 12_976_960.527449504) < 1e-6, "headline SLICE energy")
    report.check(len(expected["figure8"]) == 55, "resource-sensitivity configurations")

    reproduced_path = (output_dir or root / "artifact-output") / "paper-results.json"
    if reproduced_path.is_file():
        reproduced = json.loads(reproduced_path.read_text())
        if reproduced.get("segments") == 220:
            expected_rows = {
                (row["model"], row["level"], row["policy"]): row
                for row in expected["figure7"]["rows"]
            }
            actual_rows = {
                (row["model"], row["level"], row["policy"]): row
                for row in reproduced.get("figure7", {}).get("rows", [])
            }
            report.check(
                actual_rows.keys() == expected_rows.keys(),
                "reproduced Figure 7 row set",
            )
            if actual_rows.keys() == expected_rows.keys():
                report.check(
                    all(
                        _equivalent(actual_rows[key], expected_rows[key])
                        for key in expected_rows
                    ),
                    "reproduced Figure 7 values",
                )
            expected_resource = {
                (row["model"], row["axis"], float(row["value"])): row
                for row in expected["figure8"]
            }
            actual_resource = {
                (row["model"], row["axis"], float(row["value"])): row
                for row in reproduced.get("figure8", [])
            }
            report.check(
                actual_resource.keys() == expected_resource.keys(),
                "reproduced Figure 8 row set",
            )
            if actual_resource.keys() == expected_resource.keys():
                report.check(
                    all(
                        _equivalent(actual_resource[key], expected_resource[key])
                        for key in expected_resource
                    ),
                    "reproduced Figure 8 values",
                )
    return report
