"""One-cycle telemetry replay with reservation-correct ANELA accounting."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import random
from typing import Deque

from .arrivals import OrbitSchedule
from .energy import EnergyModel
from .policy import AnelaPolicy, SatelliteState
from .profiles import SplitPoint
from .telemetry import TelemetryTrace


@dataclass
class _QueuedTask:
    remaining_bits: float
    layer: int
    computation_j: float
    communication_spent_j: float = 0.0


@dataclass(frozen=True)
class SimulationResult:
    offered: int
    admitted: int
    delivered: int
    not_started: int
    admitted_not_delivered: int
    energy_j: float
    wasted_energy_j: float
    compute_energy_j: float
    communication_energy_j: float
    selected_layers: dict[str, int]
    rejection_reasons: dict[str, int]
    max_accounting_error_j: float
    wasted_compute_j: float = 0.0
    wasted_communication_j: float = 0.0
    failed_computation_attempts: int = 0
    partial_computation_attempts: int = 0
    zero_energy_failed_attempts: int = 0
    partial_computation_waste_j: float = 0.0
    attempted_layers: dict[str, int] | None = None


class TelemetrySimulator:
    """Replay a policy against one trace using the paper's delivery semantics."""

    def __init__(self, schedule: OrbitSchedule, energy: EnergyModel, rho: float) -> None:
        if not 0 <= rho <= 1:
            raise ValueError("rho must lie in [0, 1]")
        if abs(schedule.computation_s - energy.computation_s) > 1e-9:
            raise ValueError("schedule and energy computation durations differ")
        if abs(schedule.contact_s - energy.contact_s) > 1e-9:
            raise ValueError("schedule and energy contact durations differ")
        self.schedule = schedule
        self.energy = energy
        self.rho = rho

    def run_anela(
        self,
        trace: TelemetryTrace,
        interval_s: int,
        policy: AnelaPolicy,
    ) -> SimulationResult:
        self._check_trace(trace)
        forecast = trace.solar_forecast()
        arrivals = {
            time for time, kind in self.schedule.events(interval_s) if kind == "arrival"
        }
        queue: Deque[_QueuedTask] = deque()
        offered = admitted = delivered = rejected = admitted_not_delivered = 0
        computation_spent = communication_spent = 0.0
        wasted_computation = wasted_communication = 0.0
        committed = 0.0
        max_error = 0.0
        selected: Counter[str] = Counter()
        rejection_reasons: Counter[str] = Counter()
        previous_in_contact = False
        initial_battery = float(trace.battery_energy_j[0])

        for index in range(len(trace.elapsed_s)):
            time_s = int(trace.elapsed_s[index])
            cycle_position = time_s % self.schedule.cycle_s
            in_contact = cycle_position >= self.schedule.computation_s
            cap = self._cap(trace, index, initial_battery)

            if previous_in_contact and not in_contact and queue:
                admitted_not_delivered += len(queue)
                committed -= self.energy.communication_energy(
                    sum(task.remaining_bits for task in queue)
                )
                for task in queue:
                    wasted_computation += task.computation_j
                    wasted_communication += task.communication_spent_j
                queue.clear()

            if in_contact and queue:
                available_bits = self.energy.rate_bits_per_s
                while queue and available_bits > 0:
                    task = queue[0]
                    actual_spent = computation_spent + communication_spent
                    physical_margin = cap - actual_spent
                    energy_limited_bits = (
                        max(0.0, physical_margin) / self.energy.joules_per_bit
                        if self.energy.joules_per_bit > 0
                        else float("inf")
                    )
                    sent = min(task.remaining_bits, available_bits, energy_limited_bits)
                    if sent <= 1e-12:
                        break
                    spent = self.energy.communication_energy(sent)
                    task.remaining_bits -= sent
                    task.communication_spent_j += spent
                    communication_spent += spent
                    available_bits -= sent
                    if task.remaining_bits <= 1e-9:
                        queue.popleft()
                        delivered += 1

            if time_s in arrivals:
                offered += 1
                remaining = max(0.0, cap - committed)
                remaining_to_contact = self.schedule.computation_s - cycle_position
                now = float(forecast.battery_energy_j[index])
                at_contact = forecast.energy_at_offset(index, remaining_to_contact)
                after_contact = forecast.energy_at_offset(
                    index, remaining_to_contact + self.schedule.contact_s
                )
                decision = policy.decide(
                    SatelliteState(
                        remaining_eo_j=remaining,
                        time_in_computation_s=cycle_position,
                        forecast_until_contact_j=self.rho * (at_contact - now),
                        forecast_during_contact_j=self.rho
                        * (after_contact - at_contact),
                        queued_bits=sum(task.remaining_bits for task in queue),
                        remaining_contacts=self.schedule.cycles
                        - time_s // self.schedule.cycle_s,
                        reserved_communication_j=self.energy.communication_energy(
                            sum(task.remaining_bits for task in queue)
                        ),
                    )
                )
                if decision.split is None:
                    rejected += 1
                    rejection_reasons[decision.reason] += 1
                else:
                    computation_j = self.energy.computation_energy(
                        decision.split.work_flops
                    )
                    computation_spent += computation_j
                    committed += decision.energy_j
                    queue.append(
                        _QueuedTask(
                            remaining_bits=decision.split.payload_bits,
                            layer=decision.split.layer,
                            computation_j=computation_j,
                        )
                    )
                    admitted += 1
                    selected[str(decision.split.layer)] += 1

            reserved = self.energy.communication_energy(
                sum(task.remaining_bits for task in queue)
            )
            error = abs(
                committed
                - (computation_spent + communication_spent + reserved)
            )
            max_error = max(max_error, error)
            previous_in_contact = in_contact

        if queue:
            admitted_not_delivered += len(queue)
            committed -= self.energy.communication_energy(
                sum(task.remaining_bits for task in queue)
            )
            for task in queue:
                wasted_computation += task.computation_j
                wasted_communication += task.communication_spent_j
            queue.clear()

        actual_spent = computation_spent + communication_spent
        max_error = max(max_error, abs(committed - actual_spent))
        if offered != admitted + rejected:
            raise AssertionError("offered-task accounting failed")
        if admitted != delivered + admitted_not_delivered:
            raise AssertionError("admitted-task accounting failed")
        return SimulationResult(
            offered=offered,
            admitted=admitted,
            delivered=delivered,
            not_started=rejected,
            admitted_not_delivered=admitted_not_delivered,
            energy_j=actual_spent,
            wasted_energy_j=wasted_computation + wasted_communication,
            compute_energy_j=computation_spent,
            communication_energy_j=communication_spent,
            selected_layers=dict(selected),
            rejection_reasons=dict(rejection_reasons),
            max_accounting_error_j=max_error,
            wasted_compute_j=wasted_computation,
            wasted_communication_j=wasted_communication,
        )

    def run_fixed_split(
        self,
        trace: TelemetryTrace,
        interval_s: int,
        split: SplitPoint,
    ) -> SimulationResult:
        """Replay the frozen split selected offline by SLICE.

        SLICE checks only whether the current EO margin can pay the task's
        computation. It does not reserve its future communication energy.
        Undelivered tasks expire at the next orbit boundary.
        """

        self._check_trace(trace)
        queue: Deque[_QueuedTask] = deque()
        offered = admitted = delivered = rejected = expired = 0
        computation_spent = communication_spent = 0.0
        wasted_computation = wasted_communication = 0.0
        selected: Counter[str] = Counter()
        initial_battery = float(trace.battery_energy_j[0])
        current_cycle = 0

        for time_s, kind in self.schedule.events(interval_s):
            cycle = time_s // self.schedule.cycle_s
            cap = self._cap(trace, time_s, initial_battery)

            if cycle != current_cycle and queue:
                expired += len(queue)
                for task in queue:
                    wasted_computation += task.computation_j
                    wasted_communication += task.communication_spent_j
                queue.clear()
            current_cycle = cycle

            if kind == "contact" and queue:
                available_bits = self.energy.rate_bits_per_s
                while queue and available_bits > 0:
                    task = queue[0]
                    margin = cap - computation_spent - communication_spent
                    energy_limited_bits = (
                        max(0.0, margin) / self.energy.joules_per_bit
                        if self.energy.joules_per_bit > 0
                        else float("inf")
                    )
                    sent = min(task.remaining_bits, available_bits, energy_limited_bits)
                    if sent <= 1e-12:
                        break
                    spent = self.energy.communication_energy(sent)
                    task.remaining_bits -= sent
                    task.communication_spent_j += spent
                    communication_spent += spent
                    available_bits -= sent
                    if task.remaining_bits <= 1e-9:
                        queue.popleft()
                        delivered += 1

            if kind == "arrival":
                offered += 1
                computation_j = self.energy.computation_energy(split.work_flops)
                margin = cap - computation_spent - communication_spent
                if margin >= computation_j:
                    computation_spent += computation_j
                    admitted += 1
                    selected[str(split.layer)] += 1
                    queue.append(
                        _QueuedTask(
                            remaining_bits=split.payload_bits,
                            layer=split.layer,
                            computation_j=computation_j,
                        )
                    )
                else:
                    rejected += 1

        if queue:
            expired += len(queue)
            for task in queue:
                wasted_computation += task.computation_j
                wasted_communication += task.communication_spent_j

        return self._result(
            offered=offered,
            admitted=admitted,
            delivered=delivered,
            rejected=rejected,
            expired=expired,
            computation_spent=computation_spent,
            communication_spent=communication_spent,
            wasted_computation=wasted_computation,
            wasted_communication=wasted_communication,
            selected=selected,
        )

    def run_attempt_first(
        self,
        trace: TelemetryTrace,
        interval_s: int,
        candidates: tuple[SplitPoint, ...],
        policy: str,
        *,
        seed: int | None = None,
    ) -> SimulationResult:
        """Replay TOGC, TOBC, or RAND with partial-computation waste."""

        self._check_trace(trace)
        if policy not in {"TOGC", "TOBC", "RAND"}:
            raise ValueError(f"unknown static baseline: {policy}")
        if not candidates:
            raise ValueError("a baseline requires at least one split candidate")
        rng = random.Random(seed)
        queue: Deque[_QueuedTask] = deque()
        spent_compute = spent_communication = 0.0
        wasted_compute = wasted_communication = 0.0
        offered = admitted = delivered = failed = 0
        partial = empty = 0
        partial_j = 0.0
        selected: Counter[str] = Counter()
        attempted: Counter[str] = Counter()
        initial_battery = float(trace.battery_energy_j[0])
        current_cycle = 0

        def discard() -> int:
            nonlocal wasted_compute, wasted_communication
            count = len(queue)
            for task in queue:
                wasted_compute += task.computation_j
                wasted_communication += task.communication_spent_j
            queue.clear()
            return count

        for time_s, kind in self.schedule.events(interval_s):
            cycle = time_s // self.schedule.cycle_s
            if cycle != current_cycle:
                discard()
                current_cycle = cycle
            cap = self._cap(trace, time_s, initial_battery)
            margin = cap - spent_compute - spent_communication
            if kind == "contact":
                available_bits = self.energy.rate_bits_per_s
                while queue and available_bits > 0:
                    task = queue[0]
                    available_j = max(
                        0.0, cap - spent_compute - spent_communication
                    )
                    energy_limited_bits = (
                        available_j / self.energy.joules_per_bit
                        if self.energy.joules_per_bit > 0
                        else float("inf")
                    )
                    sent = min(task.remaining_bits, available_bits, energy_limited_bits)
                    if sent <= 1e-12:
                        break
                    spent = self.energy.communication_energy(sent)
                    task.remaining_bits -= sent
                    task.communication_spent_j += spent
                    spent_communication += spent
                    available_bits -= sent
                    if task.remaining_bits <= 1e-9:
                        queue.popleft()
                        delivered += 1
                continue

            offered += 1
            if policy == "TOGC":
                split = min(candidates, key=lambda item: item.layer)
            elif policy == "TOBC":
                split = max(candidates, key=lambda item: item.layer)
            else:
                split = rng.choice(candidates)
            attempted[str(split.layer)] += 1
            required = self.energy.computation_energy(split.work_flops)
            available = max(0.0, margin)
            if available >= required:
                spent_compute += required
                admitted += 1
                selected[str(split.layer)] += 1
                queue.append(
                    _QueuedTask(split.payload_bits, split.layer, required)
                )
            else:
                failed += 1
                spent_compute += available
                wasted_compute += available
                partial_j += available
                partial += int(available > 0)
                empty += int(available == 0)

        expired = discard()
        result = self._result(
            offered=offered,
            admitted=admitted,
            delivered=delivered,
            rejected=failed,
            expired=admitted - delivered,
            computation_spent=spent_compute,
            communication_spent=spent_communication,
            wasted_computation=wasted_compute,
            wasted_communication=wasted_communication,
            selected=selected,
            attempted=attempted,
            failed=failed,
            partial=partial,
            empty=empty,
            partial_j=partial_j,
        )
        if expired > result.admitted_not_delivered:
            raise AssertionError("terminal queue accounting failed")
        return result

    def _check_trace(self, trace: TelemetryTrace) -> None:
        if len(trace.elapsed_s) != self.schedule.horizon_s:
            raise ValueError(
                f"trace has {len(trace.elapsed_s)} samples; "
                f"expected {self.schedule.horizon_s}"
            )

    def _cap(
        self, trace: TelemetryTrace, index: int, initial_battery: float
    ) -> float:
        return max(
            0.0,
            min(
                self.energy.eo_budget_j,
                self.energy.eo_budget_j
                + self.rho * (float(trace.battery_energy_j[index]) - initial_battery),
            ),
        )

    @staticmethod
    def _result(
        *,
        offered: int,
        admitted: int,
        delivered: int,
        rejected: int,
        expired: int,
        computation_spent: float,
        communication_spent: float,
        wasted_computation: float,
        wasted_communication: float,
        selected: Counter[str],
        attempted: Counter[str] | None = None,
        failed: int = 0,
        partial: int = 0,
        empty: int = 0,
        partial_j: float = 0.0,
    ) -> SimulationResult:
        if offered != admitted + rejected:
            raise AssertionError("offered-task accounting failed")
        if admitted != delivered + expired:
            raise AssertionError("admitted-task accounting failed")
        return SimulationResult(
            offered=offered,
            admitted=admitted,
            delivered=delivered,
            not_started=rejected,
            admitted_not_delivered=expired,
            energy_j=computation_spent + communication_spent,
            wasted_energy_j=wasted_computation + wasted_communication,
            compute_energy_j=computation_spent,
            communication_energy_j=communication_spent,
            selected_layers=dict(selected),
            rejection_reasons={},
            max_accounting_error_j=0.0,
            wasted_compute_j=wasted_computation,
            wasted_communication_j=wasted_communication,
            failed_computation_attempts=failed,
            partial_computation_attempts=partial,
            zero_energy_failed_attempts=empty,
            partial_computation_waste_j=partial_j,
            attempted_layers=dict(attempted) if attempted is not None else None,
        )
