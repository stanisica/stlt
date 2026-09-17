"""Task-arrival and contact schedules used by every policy adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

EventKind = Literal["arrival", "contact"]


@dataclass(frozen=True)
class OrbitSchedule:
    """A deterministic sequence of computation and ground-contact phases.

    Arrivals reset at the beginning of every orbit. This implements the paper's
    definition ``I_k = floor(T_comp / Delta)`` exactly. The first capture in an
    orbit occurs at ``Delta``, not at time zero.
    """

    computation_s: int = 5_100
    contact_s: int = 300
    cycles: int = 5

    def __post_init__(self) -> None:
        if self.computation_s <= 0:
            raise ValueError("computation_s must be positive")
        if self.contact_s <= 0:
            raise ValueError("contact_s must be positive")
        if self.cycles <= 0:
            raise ValueError("cycles must be positive")

    @property
    def cycle_s(self) -> int:
        return self.computation_s + self.contact_s

    @property
    def horizon_s(self) -> int:
        return self.cycle_s * self.cycles

    def tasks_per_orbit(self, interval_s: int) -> int:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        return self.computation_s // interval_s

    def tasks_by_cycle(self, interval_s: int) -> tuple[int, ...]:
        return (self.tasks_per_orbit(interval_s),) * self.cycles

    def offered_tasks(self, interval_s: int) -> int:
        return sum(self.tasks_by_cycle(interval_s))

    def events(self, interval_s: int) -> Iterator[tuple[int, EventKind]]:
        """Yield time-ordered arrival and per-second contact events."""

        arrivals = self.tasks_per_orbit(interval_s)
        for cycle in range(self.cycles):
            start = cycle * self.cycle_s
            for number in range(1, arrivals + 1):
                yield start + number * interval_s, "arrival"
            for offset in range(self.computation_s, self.cycle_s):
                yield start + offset, "contact"

