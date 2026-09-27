"""Offline fixed-split planner used for the SLICE comparison."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .arrivals import OrbitSchedule


@dataclass(frozen=True)
class SlicePlan:
    model: str
    inference_interval_s: int
    offered_tasks: int
    tasks_by_cycle: tuple[int, ...]
    feasible: bool
    selected_layer: int | None
    selected_target: str | None
    per_task_compute_energy_j: float | None
    per_task_transmission_energy_j: float | None
    per_task_total_energy_j: float | None
    per_task_data_bits: float | None
    workload_total_energy_j: float | None
    workload_total_data_bits: float | None
    workload_latency_s: float | None
    nominal_generated: int | None
    nominal_accepted: int | None
    nominal_delivered: int | None
    infeasibility: str | None


@dataclass(frozen=True)
class _Candidate:
    layer: int
    target: str
    payload_bits: float
    compute_j: float
    transmission_j: float
    total_j: float
    latency_s: float
    solver_feasible: bool
    streaming_feasible: bool


def plan_slice(
    *,
    model: str,
    profile_path: Path,
    interval_s: int,
    kappa_j_per_gflop: float,
    seconds_per_gflop: float,
    rho: float,
    rate_mbps: float,
    beta_j_per_bit: float,
    battery_capacity_j: float = 828_000.0,
    platform_power_w: float = 10.0,
    ground_seconds_per_byte: float = 1e-12,
    schedule: OrbitSchedule = OrbitSchedule(),
) -> SlicePlan:
    if interval_s <= 0 or rate_mbps <= 0:
        raise ValueError("interval and downlink rate must be positive")
    tasks_by_cycle = schedule.tasks_by_cycle(interval_s)
    task_count = sum(tasks_by_cycle)
    rate_bits_per_s = rate_mbps * 1e6
    eo_budget_j = rho * battery_capacity_j
    compute_rate_flops_s = 1e9 / seconds_per_gflop
    payload = json.loads(profile_path.read_text())
    rows = payload["rows"] if isinstance(payload, dict) else payload
    candidates: list[_Candidate] = []

    for row in rows:
        if not row.get("valid_split", True):
            continue
        data_bits = float(row.get("D_cut_bits", 0.0) or 0.0)
        if data_bits <= 0:
            continue
        work_flops = int(float(row.get("W_cumGFLOPs", 0.0) or 0.0) * 1e9)
        per_task_compute_j = work_flops * kappa_j_per_gflop / 1e9
        per_task_transmission_j = data_bits * beta_j_per_bit
        compute_j = task_count * per_task_compute_j
        transmission_j = task_count * per_task_transmission_j
        total_j = compute_j + transmission_j
        workload_bits = task_count * data_bits
        contacts = (
            math.ceil(workload_bits / (rate_bits_per_s * schedule.contact_s))
            if workload_bits > 0
            else 0
        )
        transmission_s = (
            workload_bits / rate_bits_per_s
            + schedule.cycle_s * max(0, contacts - 1)
        )
        latency_s = (
            task_count * work_flops / compute_rate_flops_s
            + transmission_s
            + workload_bits / 8.0 * ground_seconds_per_byte
        )
        supplied_j = eo_budget_j + platform_power_w * schedule.horizon_s
        solver_feasible = (
            total_j <= eo_budget_j + 1e-9
            and transmission_s
            <= (supplied_j - total_j) / platform_power_w + 1e-9
            and latency_s <= schedule.horizon_s + 1e-9
        )
        streaming_feasible = solver_feasible and (
            all(
                count * data_bits
                <= rate_bits_per_s * schedule.contact_s + 1e-9
                for count in tasks_by_cycle
            )
            and work_flops / compute_rate_flops_s <= interval_s + 1e-9
        )
        candidates.append(
            _Candidate(
                layer=int(row["idx"]),
                target=str(row.get("target", f"layer_{row['idx']}")),
                payload_bits=data_bits,
                compute_j=compute_j,
                transmission_j=transmission_j,
                total_j=total_j,
                latency_s=latency_s,
                solver_feasible=solver_feasible,
                streaming_feasible=streaming_feasible,
            )
        )

    feasible = [item for item in candidates if item.streaming_feasible]
    if not feasible:
        reason = (
            "SLICE solver found no feasible split"
            if not any(item.solver_feasible for item in candidates)
            else "no solver-feasible split satisfies natural per-cycle arrivals"
        )
        return SlicePlan(
            model=model,
            inference_interval_s=interval_s,
            offered_tasks=task_count,
            tasks_by_cycle=tasks_by_cycle,
            feasible=False,
            selected_layer=None,
            selected_target=None,
            per_task_compute_energy_j=None,
            per_task_transmission_energy_j=None,
            per_task_total_energy_j=None,
            per_task_data_bits=None,
            workload_total_energy_j=None,
            workload_total_data_bits=None,
            workload_latency_s=None,
            nominal_generated=None,
            nominal_accepted=None,
            nominal_delivered=None,
            infeasibility=reason,
        )

    selected = min(
        feasible, key=lambda item: (item.total_j, item.payload_bits, item.layer)
    )
    return SlicePlan(
        model=model,
        inference_interval_s=interval_s,
        offered_tasks=task_count,
        tasks_by_cycle=tasks_by_cycle,
        feasible=True,
        selected_layer=selected.layer,
        selected_target=selected.target,
        per_task_compute_energy_j=selected.compute_j / task_count,
        per_task_transmission_energy_j=selected.transmission_j / task_count,
        per_task_total_energy_j=selected.total_j / task_count,
        per_task_data_bits=selected.payload_bits,
        workload_total_energy_j=selected.total_j,
        workload_total_data_bits=task_count * selected.payload_bits,
        workload_latency_s=selected.latency_s,
        nominal_generated=task_count,
        nominal_accepted=task_count,
        nominal_delivered=task_count,
        infeasibility=None,
    )
