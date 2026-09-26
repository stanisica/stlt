"""Tables and plot data derived from profiles, configurations, and replay."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean

from .arrivals import OrbitSchedule
from .profiles import ModelProfile

MODELS = ("squeezenet1_1", "swin_v2_t", "efficientnet_b4", "resnet50", "densenet169")


def tables(root: Path, results: dict) -> dict[str, list[dict]]:
    configs = json.loads((root / "experiments/main.json").read_text())
    nominal = {row["model"]: row for row in configs if row["level"] == "selected"}
    schedule = OrbitSchedule()
    parameters, candidates, points, reductions = [], [], [], []
    for model in MODELS:
        config = nominal[model]
        path = root / "data/model-profiles" / f"{model}.json"
        profile = ModelProfile.from_torchfx(model, path)
        raw = json.loads(path.read_text())
        graph_rows = raw["rows"] if isinstance(raw, dict) else raw
        dnnsplit = profile.dnnsplit_candidates()
        anoda = profile.anoda_candidates()
        parameters.append(
            {
                "model": model,
                "input_channels": 3,
                "input_height": 4096,
                "input_width": 4096,
                "tensor_bits": 32,
                "gamma_j_s2": config["gamma_eff"],
                "alpha_flops_per_cycle": config["alpha_eff"],
                "frequency_hz": 1e9
                / (config["seconds_per_gflop"] * config["alpha_eff"]),
                "kappa_j_per_gflop": config["kappa_j_per_gflop"],
                "beta_j_per_bit": config["beta_j_per_bit"],
                "interval_s": config["interval_s"],
                "computation_s": schedule.computation_s,
                "contact_s": schedule.contact_s,
                "cycles_per_segment": schedule.cycles,
                "rate_mbps": config["rate_mbps"],
                "rho": config["rho"],
                "battery_capacity_j": config["eo_budget_j"] / config["rho"],
                "eo_budget_j": config["eo_budget_j"],
                "transmission_power_w": config["power_w"],
                "offered_per_segment": schedule.offered_tasks(config["interval_s"]),
            }
        )
        candidates.append(
            {
                "model": model,
                "dnnsplit_layers": json.dumps([p.layer for p in dnnsplit]),
                "anoda_layers": json.dumps([p.layer for p in anoda]),
            }
        )
        reductions.append(
            {
                "model": model,
                "graph_positions": len(graph_rows),
                "valid_splits": len(profile.points),
                "dnnsplit_count": len(dnnsplit),
                "anoda_count": len(anoda),
                "additional_reduction_pct": 100 * (1 - len(anoda) / len(dnnsplit)),
                "dnnsplit_graph_reduction_pct": 100
                * (1 - len(dnnsplit) / len(graph_rows)),
                "anoda_graph_reduction_pct": 100 * (1 - len(anoda) / len(graph_rows)),
            }
        )
        if model == "swin_v2_t":
            for method, selected in (("DNNSplit", dnnsplit), ("ANODA", anoda)):
                points.extend(
                    {
                        "method": method,
                        "layer": point.layer,
                        "work_gflops": point.work_flops / 1e9,
                        "payload_mbit": point.payload_bits / 1e6,
                    }
                    for point in selected
                )
    outcomes = []
    for row in results["figure7"]["rows"]:
        if row["level"] == "nominal" and row["policy"] in ("STLT", "SLICE"):
            outcome = {
                key: row[key]
                for key in (
                    "model",
                    "policy",
                    "offered",
                    "admitted",
                    "delivered",
                    "not_started",
                    "admitted_not_delivered",
                )
            }
            outcome["segments"] = results["segments"]
            for key in (
                "admitted",
                "delivered",
                "not_started",
                "admitted_not_delivered",
            ):
                outcome[f"{key}_pct"] = 100 * row[key] / row["offered"]
            outcomes.append(outcome)
    totals = {}
    for policy in ("STLT", "SLICE"):
        selected = [
            r
            for r in results["figure7"]["rows"]
            if r["level"] == "nominal" and r["policy"] == policy
        ]
        totals[policy] = {
            key: sum(r[key] for r in selected)
            for key in ("offered", "delivered", "energy_j")
        }
    stlt, slc = totals["STLT"], totals["SLICE"]
    minimum_energy_selections = 0.0
    admissions = 0.0
    for row in results["figure7"]["rows"]:
        if row["level"] != "nominal" or row["policy"] != "STLT":
            continue
        config = nominal[row["model"]]
        minimum = min(
            config["candidates"],
            key=lambda p: p["W"] / 1e9 * config["kappa_j_per_gflop"]
            + p["D"] * config["beta_j_per_bit"],
        )
        minimum_energy_selections += row["selected_layers"].get(
            str(minimum["layer_index"]), 0
        )
        admissions += row["admitted"]
    claims = [
        {
            "claim": f"{policy.lower()}_{key}",
            "value": value,
            "unit": "J" if key == "energy_j" else "tasks",
        }
        for policy, values in totals.items()
        for key, value in values.items()
    ]
    claims.extend(
        [
            {
                "claim": "delivery_improvement",
                "value": 100 * (stlt["delivered"] / slc["delivered"] - 1),
                "unit": "%",
            },
            {
                "claim": "energy_reduction",
                "value": 100 * (1 - stlt["energy_j"] / slc["energy_j"]),
                "unit": "%",
            },
            {
                "claim": "mean_candidate_reduction",
                "value": mean(r["additional_reduction_pct"] for r in reductions),
                "unit": "%",
            },
            {
                "claim": "minimum_energy_split_share",
                "value": 100 * minimum_energy_selections / admissions,
                "unit": "%",
            },
        ]
    )
    return {
        "table1_parameters.csv": parameters,
        "table2_candidates.csv": candidates,
        "table4_task_outcomes.csv": outcomes,
        "figure5_points.csv": points,
        "figure6_reduction.csv": reductions,
        "paper_claims.csv": claims,
    }


def export(root: Path, output: Path, results: dict, mode: str) -> None:
    from .figures import figure5, figure6, figure7, figure8

    generated = tables(root, results)
    for name, rows in generated.items():
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    figure5(generated["figure5_points.csv"], output / "figure5.pdf")
    figure6(generated["figure6_reduction.csv"], output / "figure6.pdf")
    figure7(results["figure7"], output / "figure7.pdf")
    figure8(results["figure8"], output / "figure8.pdf")
    if mode == "smoke":
        scope = "Smoke test: one segment. These replay results do not reproduce the paper totals."
    else:
        scope = "Full portable reproduction: 220 independent five-orbit segments."
    (output / "MANIFEST.md").write_text(
        f"# STLT generated results\n\n{scope}\n\n"
        "| Paper item | Output |\n| --- | --- |\n"
        "| Table 1 numerical parameters | table1_parameters.csv |\n"
        "| Table 2 split candidates | table2_candidates.csv |\n"
        "| Figure 5 Swin candidate plane | figure5.pdf, figure5_points.csv |\n"
        "| Figure 6 search-space reduction | figure6.pdf, figure6_reduction.csv |\n"
        "| Figure 7 energy and delivery | figure7.pdf, main-per-window.csv |\n"
        "| Figure 8 resource sensitivity | figure8.pdf, resource-per-window.csv |\n"
        "| Table 4 task outcomes | table4_task_outcomes.csv |\n"
        "| Numerical claims | paper_claims.csv |\n\n"
        "paper-results.json contains the aggregate replay results. metadata.json records "
        "the run state, environment, source hashes, input hashes, and output hashes. "
        "validation_report.json is written by validation.\n\n"
        "Figures 2 and 9 and Table 3 require separate measurement work. "
        "Figures 1, 3, and 4 are explanatory diagrams. They are outside this workflow.\n"
    )
