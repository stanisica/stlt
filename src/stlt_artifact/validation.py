"""Input integrity, bundle completeness, and numerical result validation."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .arrivals import OrbitSchedule
from .candidate_analysis import CANDIDATE_OUTPUTS, candidate_tables
from .bundle import (
    COUNT_FIELDS,
    ENERGY_FIELDS,
    OUTPUTS,
    SEGMENTS,
    digest,
    source_hashes,
)
from .experiments import RAND_SEEDS, summarize_main, summarize_resource
from .exports import tables
from .profiles import ModelProfile
from .telemetry import BUPT1_SHA256


@dataclass
class ValidationReport:
    mode: str
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def check(self, condition: bool, name: str) -> None:
        (self.passed if condition else self.failed).append(name)

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict:
        return {
            "status": "PASS" if self.ok else "FAIL",
            "mode": self.mode,
            "passed": len(self.passed),
            "failed": len(self.failed),
            "checks": self.passed,
            "failures": self.failed,
        }


def equivalent(actual: object, expected: object, tolerance: float = 1e-6) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isfinite(actual) and abs(actual - expected) <= tolerance
    if isinstance(expected, dict) and isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            equivalent(actual[key], expected[key], tolerance) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(actual) == len(expected) and all(
            equivalent(left, right, tolerance) for left, right in zip(actual, expected)
        )
    return actual == expected


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def equivalent_rows(
    actual: list[dict], expected: list[dict], keys: tuple[str, ...]
) -> bool:
    actual_index = {tuple(row[key] for key in keys): row for row in actual}
    expected_index = {tuple(row[key] for key in keys): row for row in expected}
    return (
        len(actual_index) == len(actual)
        and len(expected_index) == len(expected)
        and equivalent(actual_index, expected_index)
    )


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames or []
        _require(
            bool(names) and len(names) == len(set(names)),
            "missing or duplicate CSV columns",
        )
        rows = list(reader)
    _require(bool(rows), "empty CSV")
    _require(
        all(None not in row and None not in row.values() for row in rows),
        "malformed CSV row",
    )
    return rows


def _inputs(root: Path, report: ValidationReport) -> None:
    for directory in ("data", "experiments"):
        for line in (root / directory / "SHA256SUMS").read_text().splitlines():
            if not line.strip():
                continue
            expected, relative = line.split(maxsplit=1)
            path = root / directory / relative
            report.check(path.is_file(), f"input exists: {directory}/{relative}")
            if path.is_file():
                report.check(
                    digest(path) == expected, f"input digest: {directory}/{relative}"
                )
    expected = {
        "squeezenet1_1": [0, 4, 19, 34, 65],
        "swin_v2_t": [0, 112, 327],
        "efficientnet_b4": [0, 40, 102, 164, 502],
        "resnet50": [0, 175],
        "densenet169": [0, 140, 599],
    }
    profiles = {
        model: ModelProfile.from_torchfx(
            model, root / "data/model-profiles" / f"{model}.json"
        )
        for model in expected
    }
    for model, layers in expected.items():
        report.check(
            [p.layer for p in profiles[model].anoda_candidates()] == layers,
            f"ANODA candidates: {model}",
        )
    for suite, count in (("main", 15), ("resource", 55)):
        configs = json.loads((root / "experiments" / f"{suite}.json").read_text())
        report.check(
            len(configs) == count and len({c["config"] for c in configs}) == count,
            f"{suite}: configuration coverage",
        )
        for config in configs:
            actual = [
                {"layer_index": p.layer, "W": p.work_flops, "D": p.payload_bits}
                for p in profiles[config["model"]].anoda_candidates()
            ]
            report.check(
                equivalent(config["candidates"], actual),
                f"candidate inputs: {config['config']}",
            )


def _rows(root: Path, output: Path, suite: str, count: int) -> list[dict]:
    configs = {
        c["config"]: c
        for c in json.loads((root / "experiments" / f"{suite}.json").read_text())
    }
    variants = [("STLT", ""), ("SLICE", "")]
    if suite == "main":
        variants += [("TOBC", ""), ("TOGC", "")] + [
            ("RAND", str(s)) for s in RAND_SEEDS
        ]
    expected = {
        (str(w), c, p, s) for w in range(count) for c in configs for p, s in variants
    }
    rows = _csv(output / f"{suite}-per-window.csv")
    keys = [(r["window"], r["config"], r["policy"], r["seed"]) for r in rows]
    _require(len(keys) == len(set(keys)), "duplicate experiment rows")
    _require(
        set(keys) == expected,
        "incomplete or unexpected segment/configuration/policy/seed coverage",
    )
    base = {
        "window",
        "config",
        "model",
        "level",
        "power_w",
        "multiplier",
        "interval_s",
        "policy",
        "seed",
        "slice_layer",
        "slice_feasible",
        "status",
        "selected_layers",
        "attempted_layers",
    }
    extra = (
        {"axis", "value", "rho", "rate_mbps", "beta_j_per_bit", "eo_budget_j"}
        if suite == "resource"
        else set()
    )
    _require(
        set(rows[0]) == base | extra | set(COUNT_FIELDS) | set(ENERGY_FIELDS),
        "CSV schema mismatch",
    )
    schedule = OrbitSchedule()
    for index, row in enumerate(rows, start=2):
        try:
            config = configs[row["config"]]
            for key in ("model", "level", "axis"):
                if key in row:
                    _require(
                        row[key] == str(config[key]), f"configuration mismatch: {key}"
                    )
            for key in (
                "power_w",
                "multiplier",
                "interval_s",
                "value",
                "rho",
                "rate_mbps",
                "beta_j_per_bit",
                "eo_budget_j",
            ):
                if key in row:
                    _require(
                        float(row[key]) == float(config[key]),
                        f"configuration mismatch: {key}",
                    )
            plan = config["plan"]
            _require(
                row["slice_feasible"] == str(plan["feasible"]),
                "SLICE feasibility mismatch",
            )
            layer = (
                "" if plan["selected_layer"] is None else str(plan["selected_layer"])
            )
            _require(row["slice_layer"] == layer, "SLICE layer mismatch")
            infeasible = row["policy"] == "SLICE" and not plan["feasible"]
            _require(
                row["status"] == ("NF" if infeasible else "ok"), "invalid result status"
            )
            if infeasible:
                _require(
                    all(row[key] == "" for key in COUNT_FIELDS + ENERGY_FIELDS),
                    "NF row contains numeric results",
                )
                _require(
                    row["selected_layers"] == row["attempted_layers"] == "{}",
                    "NF row contains layer counts",
                )
                continue
            values = {key: float(row[key]) for key in COUNT_FIELDS + ENERGY_FIELDS}
            _require(
                all(math.isfinite(v) and v >= 0 for v in values.values()),
                "negative or non-finite value",
            )
            _require(
                all(values[key].is_integer() for key in COUNT_FIELDS),
                "noninteger task count",
            )
            _require(
                values["offered"] == schedule.offered_tasks(config["interval_s"]),
                "wrong offered task count",
            )
            _require(
                values["offered"] == values["admitted"] + values["not_started"],
                "offered task accounting",
            )
            _require(
                values["admitted"]
                == values["delivered"] + values["admitted_not_delivered"],
                "admitted task accounting",
            )
            for total, left, right in (
                ("energy_j", "compute_energy_j", "communication_energy_j"),
                ("wasted_energy_j", "wasted_compute_j", "wasted_communication_j"),
            ):
                _require(
                    abs(values[total] - values[left] - values[right]) <= 1e-6,
                    f"{total} accounting",
                )
            for waste, total in (
                ("wasted_energy_j", "energy_j"),
                ("wasted_compute_j", "compute_energy_j"),
                ("wasted_communication_j", "communication_energy_j"),
                ("partial_computation_waste_j", "wasted_compute_j"),
            ):
                _require(
                    values[waste] <= values[total] + 1e-6, f"{waste} exceeds {total}"
                )
            valid_layers = {str(c["layer_index"]) for c in config["candidates"]}
            if row["policy"] == "SLICE":
                valid_layers.add(layer)
            for key in ("selected_layers", "attempted_layers"):
                histogram = json.loads(row[key])
                _require(
                    isinstance(histogram, dict) and set(histogram) <= valid_layers,
                    f"invalid {key}",
                )
                _require(
                    all(type(v) is int and v >= 0 for v in histogram.values()),
                    f"invalid counts in {key}",
                )
                if key == "selected_layers":
                    _require(
                        sum(histogram.values()) == values["admitted"],
                        "selected layer count differs from admissions",
                    )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"CSV line {index}: {error}") from error
    return rows


def _table_matches(actual: list[dict], expected: list[dict]) -> bool:
    if len(actual) != len(expected):
        return False
    for left, right in zip(actual, expected):
        if left.keys() != right.keys():
            return False
        for key, value in right.items():
            if isinstance(value, (int, float)):
                if not equivalent(float(left[key]), value):
                    return False
            elif left[key] != str(value):
                return False
    return True


def validate(
    root: Path, output_dir: Path | None = None, mode: str = "full"
) -> ValidationReport:
    report = ValidationReport(mode)
    if mode not in {"inputs", "candidates", *SEGMENTS}:
        report.check(False, f"unknown validation mode: {mode}")
        return report
    try:
        _inputs(root, report)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.check(False, f"invalid inputs: {error}")
    if mode == "inputs" or not report.ok:
        return report
    output = output_dir or root / "artifact-output" / mode
    outputs = CANDIDATE_OUTPUTS if mode == "candidates" else OUTPUTS
    for name in (*outputs, "metadata.json"):
        path = output / name
        report.check(
            path.is_file() and path.stat().st_size > 0, f"required output: {name}"
        )
    if not report.ok:
        return report
    try:
        metadata = json.loads((output / "metadata.json").read_text())
        report.check(metadata["status"] == "complete", "run completed")
        report.check(metadata["mode"] == mode, "run mode")
        report.check(
            metadata["source_sha256"] == source_hashes(root),
            "source and input provenance",
        )
        report.check(
            math.isfinite(metadata["elapsed_s"]) and metadata["elapsed_s"] > 0,
            "recorded runtime",
        )
        report.check(
            bool(metadata["python"])
            and bool(metadata["platform"])
            and bool(metadata["dependencies"]),
            "recorded environment",
        )
        report.check(set(metadata["outputs"]) == set(outputs), "manifest file coverage")
        for name in outputs:
            report.check(
                metadata["outputs"].get(name) == digest(output / name),
                f"output digest: {name}",
            )
            if name.endswith(".pdf"):
                content = (output / name).read_bytes()
                report.check(
                    content.startswith(b"%PDF-") and b"%%EOF" in content[-1024:],
                    f"PDF structure: {name}",
                )
            elif name.endswith(".png"):
                content = (output / name).read_bytes()
                report.check(
                    content.startswith(b"\x89PNG\r\n\x1a\n")
                    and content[12:16] == b"IHDR"
                    and int.from_bytes(content[16:20], "big") > 0
                    and int.from_bytes(content[20:24], "big") > 0,
                    f"PNG structure: {name}",
                )
        if mode == "candidates":
            for name, expected_rows in candidate_tables(root).items():
                report.check(
                    _table_matches(_csv(output / name), expected_rows),
                    f"derived table: {name}",
                )
            return report
        result = json.loads((output / "paper-results.json").read_text())
        count = SEGMENTS[mode]
        report.check(metadata["segments"] == count, "segment count")
        report.check(result["segments"] == count, "summary segment count")
        report.check(
            result["archive_sha256"] == metadata["telemetry_sha256"] == BUPT1_SHA256,
            "telemetry provenance",
        )
        recomputed = {"segments": count, "archive_sha256": BUPT1_SHA256}
        for suite, key, summarize in (
            ("main", "figure7", summarize_main),
            ("resource", "figure8", summarize_resource),
        ):
            rows = _rows(root, output, suite, count)
            report.check(
                True,
                f"{suite}: schema, coverage, configuration, task and energy accounting ({len(rows)} rows)",
            )
            recomputed[key] = summarize(rows)
            report.check(
                equivalent(result[key], recomputed[key]),
                f"{suite}: summary recomputed from CSV",
            )
        for name, expected_rows in tables(root, recomputed).items():
            report.check(
                _table_matches(_csv(output / name), expected_rows),
                f"derived table: {name}",
            )
        if mode == "full":
            expected = json.loads(
                (root / "data/expected/paper-results.json").read_text()
            )
            for key in ("figure7", "figure8"):
                actual_values = (
                    recomputed[key]["rows"] if key == "figure7" else recomputed[key]
                )
                expected_values = (
                    expected[key]["rows"] if key == "figure7" else expected[key]
                )
                report.check(
                    equivalent_rows(
                        actual_values,
                        expected_values,
                        ("model", "level", "policy")
                        if key == "figure7"
                        else ("model", "axis", "value"),
                    ),
                    f"paper numerical oracle: {key} (absolute tolerance 1e-6)",
                )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        ZeroDivisionError,
        OverflowError,
    ) as error:
        report.check(False, f"invalid result bundle: {error}")
    return report
