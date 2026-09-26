"""BUPT-1 telemetry parsing and deterministic five-orbit segmentation."""

from __future__ import annotations

import csv
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping

import numpy as np

BUPT1_SHA256 = "5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa"


@dataclass(frozen=True)
class TelemetryTrace:
    timestamps: tuple[str, ...]
    elapsed_s: np.ndarray
    battery_energy_j: np.ndarray
    is_sunlit: np.ndarray
    solar_power_w: np.ndarray
    total_power_w: np.ndarray
    net_power_w: np.ndarray
    battery_voltage_mv: np.ndarray

    def solar_forecast(self) -> "TelemetryTrace":
        """Perfect recorded-solar forecast used by the evaluated controller."""

        cumulative = np.zeros(len(self.solar_power_w), dtype=float)
        if len(cumulative) > 1:
            delta_s = np.diff(self.elapsed_s)
            cumulative[1:] = np.cumsum(self.solar_power_w[1:] * delta_s)
        battery = float(self.battery_energy_j[0]) + cumulative
        zeros = np.zeros(len(cumulative), dtype=float)
        return TelemetryTrace(
            timestamps=self.timestamps,
            elapsed_s=self.elapsed_s.copy(),
            battery_energy_j=battery,
            is_sunlit=self.is_sunlit.copy(),
            solar_power_w=self.solar_power_w.copy(),
            total_power_w=zeros,
            net_power_w=self.solar_power_w.copy(),
            battery_voltage_mv=self.battery_voltage_mv.copy(),
        )

    def energy_at_offset(self, index: int, offset_s: float) -> float:
        if offset_s <= 0:
            return float(self.battery_energy_j[index])
        target = index + offset_s
        lower = int(np.floor(target))
        fraction = target - lower
        if lower <= 0:
            return float(self.battery_energy_j[0])
        if lower >= len(self.battery_energy_j) - 1:
            return float(self.battery_energy_j[-1])
        e0 = float(self.battery_energy_j[lower])
        e1 = float(self.battery_energy_j[lower + 1])
        return e0 + fraction * (e1 - e0)


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _number(row: Mapping[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value not in ("", None) else 0.0


def derive_sample(row: Mapping[str, str]) -> dict[str, float | int | str]:
    """Derive the exact power quantities used by the paper replay."""

    total_voltage = _number(row, "Total_U")
    total_current = _number(row, "Total_I")
    mppt1_input_voltage = _number(row, "MPPT1_Uin")
    mppt2_input_voltage = _number(row, "MPPT2_Uin")
    solar_current = _number(row, "MPPT1_Iout") + _number(row, "MPPT2_Iout")
    battery_voltage = (_number(row, "BATTERY1_U") + _number(row, "BATTERY2_U")) / 2
    solar_power = solar_current * total_voltage / 1_000_000
    total_power = total_current * total_voltage / 1_000_000
    return {
        "timestamp": row["Time"],
        "solar_power_w": solar_power,
        "total_power_w": total_power,
        "net_power_w": solar_power - total_power,
        "is_sunlit": int(mppt1_input_voltage != 0 and mppt2_input_voltage != 0),
        "battery_voltage_mv": battery_voltage,
    }


def raw_rows(archive: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(archive) as handle:
        members = [item for item in handle.infolist() if not item.is_dir()]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {archive}, found {len(members)}")
        with handle.open(members[0]) as binary:
            text = (line.decode("utf-8", errors="replace") for line in binary)
            yield from csv.DictReader(text)


def segments(
    archive: Path,
    *,
    samples: int = 27_000,
    wanted: set[int] | None = None,
) -> Iterator[tuple[int, TelemetryTrace]]:
    """Yield complete non-overlapping one-Hz segments without crossing gaps."""

    if samples <= 0:
        raise ValueError("samples must be positive")
    if wanted is not None and not wanted:
        return
    stop_after = max(wanted) if wanted is not None else None
    segment_index = 0
    position = 0
    previous: datetime | None = None
    buffer: list[dict[str, float | int | str]] = []
    for row in raw_rows(archive):
        current = parse_timestamp(row["Time"])
        if previous is not None and (current - previous).total_seconds() != 1:
            position = 0
            buffer = []
        if wanted is None or segment_index in wanted:
            buffer.append(derive_sample(row))
        position += 1
        if position == samples:
            if wanted is None or segment_index in wanted:
                yield segment_index, trace_from_samples(buffer)
            segment_index += 1
            position = 0
            buffer = []
            if stop_after is not None and segment_index > stop_after:
                break
        previous = current


def trace_from_samples(
    rows: list[dict[str, float | int | str]],
    *,
    battery_capacity_j: float = 828_000.0,
) -> TelemetryTrace:
    if not rows:
        raise ValueError("cannot construct a telemetry trace without samples")
    net = np.asarray([float(row["net_power_w"]) for row in rows], dtype=float)
    cumulative = np.zeros(len(rows), dtype=float)
    cumulative[1:] = np.cumsum(net[1:])
    initial = np.clip(
        0.5 * battery_capacity_j
        - 0.5 * (float(np.min(cumulative)) + float(np.max(cumulative))),
        -float(np.min(cumulative)),
        battery_capacity_j - float(np.max(cumulative)),
    )
    return TelemetryTrace(
        timestamps=tuple(str(row["timestamp"]) for row in rows),
        elapsed_s=np.arange(len(rows), dtype=float),
        battery_energy_j=initial + cumulative,
        is_sunlit=np.asarray([int(row["is_sunlit"]) for row in rows], dtype=int),
        solar_power_w=np.asarray(
            [float(row["solar_power_w"]) for row in rows], dtype=float
        ),
        total_power_w=np.asarray(
            [float(row["total_power_w"]) for row in rows], dtype=float
        ),
        net_power_w=net,
        battery_voltage_mv=np.asarray(
            [float(row["battery_voltage_mv"]) for row in rows], dtype=float
        ),
    )
