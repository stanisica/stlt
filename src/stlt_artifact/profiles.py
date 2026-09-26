"""DNN profile loading and offline split-candidate analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SplitPoint:
    layer: int
    work_flops: float
    payload_bits: float


@dataclass(frozen=True)
class ModelProfile:
    name: str
    points: tuple[SplitPoint, ...]

    @classmethod
    def from_torchfx(cls, name: str, path: Path) -> "ModelProfile":
        payload = json.loads(path.read_text())
        rows = payload["rows"] if isinstance(payload, dict) else payload
        points = tuple(
            SplitPoint(
                layer=int(row["idx"]),
                work_flops=float(row["W_cumGFLOPs"]) * 1e9,
                payload_bits=float(row["D_cut_bits"]),
            )
            for row in rows
            if row.get("valid_split", True)
        )
        if not points:
            raise ValueError(f"empty model profile: {path}")
        if len({point.layer for point in points}) != len(points):
            raise ValueError(f"duplicate layer index in profile: {path}")
        return cls(name=name, points=points)

    def dnnsplit_candidates(self) -> tuple[SplitPoint, ...]:
        """Running payload minima, corresponding to DNNSplit Equation 15."""

        selected = [self.points[0]]
        current = self.points[0].payload_bits
        for point in self.points[1:]:
            if point.payload_bits < current:
                selected.append(point)
                current = point.payload_bits
        return tuple(selected)

    def anoda_candidates(self) -> tuple[SplitPoint, ...]:
        """Lower hull of the running-payload-minimum candidate sequence.

        This is the exact evaluated ANODA pipeline: invalid graph cuts are
        removed, the DNNSplit running-minimum candidates are formed, and ANODA
        retains the lower-hull vertices of that sequence.
        """

        ordered = sorted(
            self.dnnsplit_candidates(),
            key=lambda point: (point.work_flops, point.payload_bits, point.layer),
        )
        hull: list[SplitPoint] = []
        for point in ordered:
            while len(hull) >= 2 and _cross(hull[-2], hull[-1], point) <= 0:
                hull.pop()
            hull.append(point)
        return tuple(sorted(hull, key=lambda point: point.layer))


def _cross(origin: SplitPoint, a: SplitPoint, b: SplitPoint) -> float:
    return (
        (a.work_flops - origin.work_flops)
        * (b.payload_bits - origin.payload_bits)
        - (a.payload_bits - origin.payload_bits)
        * (b.work_flops - origin.work_flops)
    )


def points_by_layer(
    profile: ModelProfile, layers: Iterable[int]
) -> tuple[SplitPoint, ...]:
    index = {point.layer: point for point in profile.points}
    requested = tuple(layers)
    missing = [layer for layer in requested if layer not in index]
    if missing:
        raise KeyError(f"layers not present in {profile.name}: {missing}")
    return tuple(index[layer] for layer in requested)
