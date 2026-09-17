"""Load the artifact profiles and derive the two measured candidate sets."""

from __future__ import annotations

import json
from pathlib import Path


def load_profile_rows(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text())
    rows = payload["rows"] if isinstance(payload, dict) else payload
    return [
        row
        for row in rows
        if bool(row.get("valid_split", True))
        and float(row.get("D_cut_bits", 0.0) or 0.0) > 0
    ]


def dnnsplit_layers(rows: list[dict[str, object]]) -> set[int]:
    selected: list[dict[str, object]] = [rows[0]]
    minimum = float(rows[0]["D_cut_bits"])
    for row in rows[1:]:
        payload = float(row["D_cut_bits"])
        if payload < minimum:
            selected.append(row)
            minimum = payload
    return {int(row["idx"]) for row in selected}


def _cross(
    origin: dict[str, object],
    left: dict[str, object],
    right: dict[str, object],
) -> float:
    ox, oy = float(origin["W_cumGFLOPs"]), float(origin["D_cut_bits"])
    ax, ay = float(left["W_cumGFLOPs"]), float(left["D_cut_bits"])
    bx, by = float(right["W_cumGFLOPs"]), float(right["D_cut_bits"])
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def anoda_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    retained = [row for row in rows if int(row["idx"]) in dnnsplit_layers(rows)]
    retained.sort(
        key=lambda row: (
            float(row["W_cumGFLOPs"]),
            float(row["D_cut_bits"]),
            int(row["idx"]),
        )
    )
    hull: list[dict[str, object]] = []
    for row in retained:
        while len(hull) >= 2 and _cross(hull[-2], hull[-1], row) <= 0:
            hull.pop()
        hull.append(row)
    return sorted(hull, key=lambda row: int(row["idx"]))


def anoda_layers(rows: list[dict[str, object]]) -> set[int]:
    return {int(row["idx"]) for row in anoda_rows(rows)}
