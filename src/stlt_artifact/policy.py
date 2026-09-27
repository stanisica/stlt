"""ANELA admission and split selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .energy import EnergyModel
from .profiles import SplitPoint


@dataclass(frozen=True)
class SatelliteState:
    remaining_eo_j: float
    forecast_until_contact_j: float
    forecast_during_contact_j: float
    queued_bits: float
    remaining_contacts: int
    reserved_communication_j: float = 0.0

    def __post_init__(self) -> None:
        if self.remaining_contacts < 0:
            raise ValueError("remaining_contacts must be non-negative")
        if self.queued_bits < 0:
            raise ValueError("queued_bits must be non-negative")
        if self.reserved_communication_j < 0:
            raise ValueError("reserved_communication_j must be non-negative")


@dataclass(frozen=True)
class Decision:
    split: SplitPoint | None
    energy_j: float
    reason: str


class AnelaPolicy:
    def __init__(
        self,
        candidates: Sequence[SplitPoint],
        energy: EnergyModel,
    ) -> None:
        if not candidates:
            raise ValueError("ANELA requires at least one candidate split")
        self._candidates = tuple(candidates)
        self._energy = energy

    def decide(self, state: SatelliteState) -> Decision:
        downlink_reserve_j = self._energy.communication_energy(
            self._energy.downlink_capacity_bits * state.remaining_contacts
        )
        if state.remaining_eo_j <= downlink_reserve_j:
            candidates = (min(self._candidates, key=self._energy.task_energy),)
        else:
            candidates = self._candidates

        feasible: list[tuple[SplitPoint, float]] = []
        passed_first_three = 0
        failed_full_task = 0
        for split in candidates:
            computation_j = self._energy.computation_energy(split.work_flops)
            if state.remaining_eo_j < computation_j:
                continue
            if (
                state.queued_bits + split.payload_bits
                > self._energy.downlink_capacity_bits
            ):
                continue
            projected_j = self._energy.projected_energy(
                state.remaining_eo_j,
                state.reserved_communication_j,
                state.forecast_until_contact_j,
                split,
            )
            required_downlink_j = self._energy.communication_energy(
                state.queued_bits + split.payload_bits
            )
            if projected_j + state.forecast_during_contact_j < required_downlink_j:
                continue
            passed_first_three += 1
            total_j = self._energy.task_energy(split)
            if state.remaining_eo_j < total_j:
                failed_full_task += 1
                continue
            feasible.append((split, total_j))

        if not feasible:
            reason = "no_candidate_satisfies_all_constraints"
            if passed_first_three and passed_first_three == failed_full_task:
                reason = "full_task_energy_constraint"
            return Decision(None, float("inf"), reason)

        split, energy_j = min(feasible, key=lambda item: item[1])
        return Decision(split, energy_j, "minimum_energy_feasible_candidate")
