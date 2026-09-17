"""Energy model shared by profile analysis, policies, and replay."""

from __future__ import annotations

from dataclasses import dataclass

from .profiles import SplitPoint


@dataclass(frozen=True)
class EnergyModel:
    """Paper energy coefficients without process-global mutable state."""

    joules_per_flop: float
    joules_per_bit: float
    computation_s: float = 5_100.0
    contact_s: float = 300.0
    rate_bits_per_s: float = 20e6
    eo_budget_j: float = 13_248.0

    def __post_init__(self) -> None:
        for name in (
            "joules_per_flop",
            "joules_per_bit",
            "computation_s",
            "contact_s",
            "rate_bits_per_s",
            "eo_budget_j",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")

    @property
    def downlink_capacity_bits(self) -> float:
        return self.contact_s * self.rate_bits_per_s

    def computation_energy(self, work_flops: float) -> float:
        return self.joules_per_flop * work_flops

    def communication_energy(self, payload_bits: float) -> float:
        return self.joules_per_bit * payload_bits

    def task_energy(self, split: SplitPoint) -> float:
        return self.computation_energy(split.work_flops) + self.communication_energy(
            split.payload_bits
        )

    def projected_energy(
        self,
        remaining_j: float,
        reserved_communication_j: float,
        forecast_until_contact_j: float,
        split: SplitPoint,
    ) -> float:
        """Projected physical EO energy at the start of contact.

        ``remaining_j`` excludes queued communication reservations. They are
        restored for this projection because the corresponding queued payloads
        appear on the transmission requirement side of the feasibility check.
        """

        projected = (
            remaining_j
            + reserved_communication_j
            + forecast_until_contact_j
            - self.computation_energy(split.work_flops)
        )
        return min(self.eo_budget_j, projected)

