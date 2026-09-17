"""Declarative execution of the paper's main and resource experiments."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean, stdev
from typing import Iterable

from .arrivals import OrbitSchedule
from .energy import EnergyModel
from .planner import SlicePlan, plan_slice
from .policy import AnelaPolicy
from .profiles import ModelProfile, SplitPoint, points_by_layer
from .simulator import SimulationResult, TelemetrySimulator
from .telemetry import TelemetryTrace, segments

RAND_SEEDS = (7, 19, 42, 73, 101)
POLICIES = ("STLT", "SLICE", "TOBC", "TOGC", "RAND")
LEVEL_NAMES = {
    "selected": "nominal",
    "lighter75": "threequarter",
    "lighter50": "half",
}


def _model(root: Path, config: dict[str, object]) -> tuple[EnergyModel, ModelProfile]:
    energy = EnergyModel(
        joules_per_flop=float(config["kappa_j_per_gflop"]) / 1e9,
        joules_per_bit=float(config["beta_j_per_bit"]),
        rate_bits_per_s=float(config["rate_mbps"]) * 1e6,
        eo_budget_j=float(config["eo_budget_j"]),
    )
    name = str(config["model"])
    profile = ModelProfile.from_torchfx(
        name, root / "data" / "model-profiles" / f"{name}.json"
    )
    return energy, profile


def _plan(root: Path, config: dict[str, object]) -> SlicePlan:
    return plan_slice(
        model=str(config["model"]),
        profile_path=root
        / "data"
        / "model-profiles"
        / f"{config['model']}.json",
        interval_s=int(config["interval_s"]),
        kappa_j_per_gflop=float(config["kappa_j_per_gflop"]),
        seconds_per_gflop=float(config["seconds_per_gflop"]),
        rho=float(config["rho"]),
        rate_mbps=float(config["rate_mbps"]),
        beta_j_per_bit=float(config["beta_j_per_bit"]),
    )


def _result_row(
    window: int,
    config: dict[str, object],
    policy: str,
    result: SimulationResult | None,
    plan: SlicePlan,
    seed: int | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "window": window,
        "config": config["config"],
        "model": config["model"],
        "level": config["level"],
        "power_w": config["power_w"],
        "multiplier": config["multiplier"],
        "interval_s": config["interval_s"],
        "policy": policy,
        "seed": "" if seed is None else seed,
        "slice_layer": "" if plan.selected_layer is None else plan.selected_layer,
        "slice_feasible": plan.feasible,
        "status": "ok" if result is not None else "NF",
    }
    if "axis" in config:
        row.update(
            axis=config["axis"],
            value=config["value"],
            rho=config["rho"],
            rate_mbps=config["rate_mbps"],
            beta_j_per_bit=config["beta_j_per_bit"],
            eo_budget_j=config["eo_budget_j"],
        )
    scalar_fields = (
        "offered",
        "admitted",
        "delivered",
        "not_started",
        "admitted_not_delivered",
        "energy_j",
        "wasted_energy_j",
        "compute_energy_j",
        "communication_energy_j",
        "wasted_compute_j",
        "wasted_communication_j",
        "failed_computation_attempts",
        "partial_computation_attempts",
        "zero_energy_failed_attempts",
        "partial_computation_waste_j",
    )
    if result is None:
        row.update({field: "" for field in scalar_fields})
        row.update(selected_layers="{}", attempted_layers="{}")
    else:
        row.update({field: getattr(result, field) for field in scalar_fields})
        row["selected_layers"] = json.dumps(result.selected_layers, sort_keys=True)
        row["attempted_layers"] = json.dumps(
            result.attempted_layers or {}, sort_keys=True
        )
    return row


def _same_plan(actual: dict[str, object], expected: dict[str, object]) -> bool:
    if actual.keys() != expected.keys():
        return False
    for key, value in expected.items():
        observed = actual[key]
        if key == "tasks_by_cycle":
            if tuple(observed) != tuple(value):
                return False
        elif isinstance(value, float):
            if abs(float(observed) - value) > 1e-8:
                return False
        elif observed != value:
            return False
    return True


def evaluate_config(
    root: Path,
    window: int,
    trace: TelemetryTrace,
    config: dict[str, object],
    *,
    include_baselines: bool,
) -> list[dict[str, object]]:
    energy, profile = _model(root, config)
    candidates = points_by_layer(
        profile, [int(item["layer_index"]) for item in config["candidates"]]
    )
    simulation = TelemetrySimulator(OrbitSchedule(), energy, float(config["rho"]))
    interval_s = int(config["interval_s"])
    plan = _plan(root, config)
    expected_plan = config["plan"]
    if not _same_plan(asdict(plan), expected_plan):
        raise AssertionError(f"SLICE plan drift: {config['config']}")

    stlt = simulation.run_anela(trace, interval_s, AnelaPolicy(candidates, energy))
    rows = [_result_row(window, config, "STLT", stlt, plan)]
    if plan.feasible:
        split = points_by_layer(profile, [int(plan.selected_layer)])[0]
        fixed = simulation.run_fixed_split(trace, interval_s, split)
        rows.append(_result_row(window, config, "SLICE", fixed, plan))
    else:
        rows.append(_result_row(window, config, "SLICE", None, plan))

    if include_baselines:
        for policy, seed in (("TOBC", None), ("TOGC", None)):
            result = simulation.run_attempt_first(
                trace, interval_s, candidates, policy, seed=seed
            )
            rows.append(_result_row(window, config, policy, result, plan, seed))
        for seed in RAND_SEEDS:
            result = simulation.run_attempt_first(
                trace, interval_s, candidates, "RAND", seed=seed
            )
            rows.append(_result_row(window, config, "RAND", result, plan, seed))
    return rows


def run_suite(
    root: Path,
    archive: Path,
    suite: str,
    output: Path,
    *,
    segment_count: int = 220,
) -> list[dict[str, object]]:
    if suite not in {"main", "resource"}:
        raise ValueError("suite must be 'main' or 'resource'")
    if not 1 <= segment_count <= 220:
        raise ValueError("segment_count must lie in [1, 220]")
    configs = json.loads((root / "experiments" / f"{suite}.json").read_text())
    rows: list[dict[str, object]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    with output.open("w", newline="") as stream:
        for window, trace in segments(
            archive, wanted=set(range(segment_count))
        ):
            for config in configs:
                chunk = evaluate_config(
                    root,
                    window,
                    trace,
                    config,
                    include_baselines=suite == "main",
                )
                if writer is None:
                    writer = csv.DictWriter(stream, fieldnames=list(chunk[0]))
                    writer.writeheader()
                writer.writerows(chunk)
                rows.extend(chunk)
            stream.flush()
            completed = window + 1
            if completed == 1 or completed % 10 == 0 or completed == segment_count:
                print(f"{suite}: segment {completed}/{segment_count}", flush=True)
    expected = segment_count * len(configs) * (9 if suite == "main" else 2)
    if len(rows) != expected:
        raise AssertionError(f"expected {expected} rows, produced {len(rows)}")
    return rows


def _numeric(row: dict[str, object], name: str) -> float:
    return float(row[name])


def summarize_main(rows: Iterable[dict[str, object]]) -> dict[str, object]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row["model"]), str(row["level"]), str(row["policy"])].append(row)
    output = []
    for model, level, policy in sorted(groups):
        records = groups[model, level, policy]
        seeds = len(RAND_SEEDS) if policy == "RAND" else 1
        by_window: dict[int, list[dict[str, object]]] = defaultdict(list)
        for record in records:
            by_window[int(record["window"])].append(record)
        rates = [
            mean(
                100 * _numeric(record, "delivered") / _numeric(record, "offered")
                for record in window_records
            )
            for window_records in by_window.values()
        ]
        totals = {
            field: sum(_numeric(record, field) for record in records) / seeds
            for field in (
                "offered",
                "admitted",
                "delivered",
                "not_started",
                "admitted_not_delivered",
            )
        }
        energy_j = sum(_numeric(record, "energy_j") for record in records) / seeds
        wasted_j = (
            sum(_numeric(record, "wasted_energy_j") for record in records) / seeds
        )
        selected: Counter[str] = Counter()
        for record in records:
            selected.update(json.loads(str(record["selected_layers"])))
        selected_layers = {key: value / seeds for key, value in selected.items()}
        output.append(
            {
                "model": model,
                "level": LEVEL_NAMES[level],
                "policy": policy,
                **totals,
                "energy_j": energy_j,
                "wasted_energy_j": wasted_j,
                "effective_per_offered_j": (energy_j - wasted_j) / totals["offered"],
                "wasted_per_offered_j": wasted_j / totals["offered"],
                "energy_per_offered_j": energy_j / totals["offered"],
                "delivery_pct": 100 * totals["delivered"] / totals["offered"],
                "delivery_min_pct": min(rates),
                "delivery_max_pct": max(rates),
                "delivery_std_pct": stdev(rates) if len(rates) > 1 else 0.0,
                "selected_layers": selected_layers,
            }
        )
    order = {policy: number for number, policy in enumerate(POLICIES)}
    output.sort(key=lambda row: (row["model"], row["level"], order[row["policy"]]))
    return {
        "rows": output,
        "figure_caption": (
            "Simulated EO energy per offered task and delivery rate across 220 "
            "five-orbit segments. Energy bars separate effective and wasted EO "
            "energy. Delivery bars show means and whiskers show plus or minus one "
            "sample standard deviation across segments. RAND is averaged over five "
            "seeds within each segment before these statistics are calculated."
        ),
    }


def summarize_resource(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, float], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row["model"]), str(row["axis"]), float(row["value"])].append(row)
    output = []
    for (model, axis, value), records in sorted(groups.items()):
        policies = []
        for policy in ("STLT", "SLICE"):
            selected = [row for row in records if row["policy"] == policy]
            if selected[0]["status"] == "NF":
                policies.append(
                    {"policy": policy, "status": "NF", "mean_delivered": None, "delivery_pct": None}
                )
            else:
                delivered = mean(_numeric(row, "delivered") for row in selected)
                offered = mean(_numeric(row, "offered") for row in selected)
                policies.append(
                    {
                        "policy": policy,
                        "status": "ok",
                        "mean_delivered": delivered,
                        "delivery_pct": 100 * delivered / offered,
                    }
                )
        output.append(
            {"model": model, "axis": axis, "value": value, "policies": policies}
        )
    return output
