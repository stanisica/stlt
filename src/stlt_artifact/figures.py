"""Paper figure rendering from machine-readable experiment summaries."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from .candidate_analysis import MODELS

LABELS = ("SqueezeNet1.1", "Swin-V2-T", "EfficientNet-B4", "ResNet50", "DenseNet169")
POLICIES = ("STLT", "SLICE", "TOBC", "TOGC", "RAND")
COLORS = {
    "STLT": "#e76f51",
    "SLICE": "#2a6f97",
    "TOBC": "#6a994e",
    "TOGC": "#9c6644",
    "RAND": "#8d6cab",
}


def _candidate_panel(axis, rows: list[dict], label: str) -> None:
    selected = {
        method: [r for r in rows if r["method"] == method]
        for method in ("DNNSplit", "ANODA")
    }
    for method, color, style, marker in (
        ("DNNSplit", "#333333", "--", "o"),
        ("ANODA", "#d55e00", "-", "x"),
    ):
        points = selected[method]
        axis.plot(
            [r["work_gflops"] for r in points],
            [r["payload_mbit"] for r in points],
            color=color,
            linestyle=style,
            marker=marker,
            markerfacecolor="white",
            markersize=6,
            label=method,
        )
    retained = {r["layer"] for r in selected["ANODA"]}
    pruned = [r["layer"] for r in selected["DNNSplit"] if r["layer"] not in retained]
    detail = (
        "Pruned layers: " + ", ".join(map(str, pruned))
        if pruned
        else "No additional pruning"
    )
    axis.set_title(
        f"{label}\nDNNSplit: {len(selected['DNNSplit'])}; ANODA: {len(retained)}",
        fontsize=10,
    )
    axis.set(
        xlabel="Cumulative computation (GFLOPs)", ylabel="Intermediate data (Mbit)"
    )
    axis.text(
        0.98, 0.92, detail, transform=axis.transAxes, ha="right", va="top", fontsize=9
    )
    axis.grid(alpha=0.25)
    axis.set_axisbelow(True)


def candidate_figures(generated: dict[str, list[dict]], output: Path) -> None:
    with plt.rc_context({"font.size": 9, "pdf.fonttype": 42}):
        overview, axes = plt.subplots(2, 3, figsize=(15, 8), layout="constrained")
        for model, label, axis in zip(MODELS, LABELS, axes.flat):
            rows = generated[f"candidates-{model}.csv"]
            _candidate_panel(axis, rows, label)
            figure, single = plt.subplots(figsize=(7.2, 4.5), layout="constrained")
            _candidate_panel(single, rows, label)
            single.legend(
                loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False
            )
            for extension in ("pdf", "png"):
                figure.savefig(output / f"candidates-{model}.{extension}", dpi=180)
            plt.close(figure)
        legend = axes.flat[-1]
        legend.axis("off")
        handles, labels = axes.flat[0].get_legend_handles_labels()
        legend.legend(handles, labels, loc="center", frameon=False)
        legend.text(
            0.5,
            0.27,
            "Recorded 4096 × 4096 float32 profiles\nEach panel uses its own axis limits.\nPruning is relative to DNNSplit.",
            ha="center",
            va="center",
            transform=legend.transAxes,
            linespacing=1.6,
        )
        for extension in ("pdf", "png"):
            overview.savefig(output / f"candidate-analysis.{extension}", dpi=180)
        plt.close(overview)


def figure5(rows: list[dict], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 3.5), layout="constrained")
    for method, style, color in (
        ("DNNSplit", "--o", "black"),
        ("ANODA", "-o", "#e76f51"),
    ):
        selected = [row for row in rows if row["method"] == method]
        axis.plot(
            [r["work_gflops"] for r in selected],
            [r["payload_mbit"] for r in selected],
            style,
            color=color,
            label=method,
        )
    pruned = next(row for row in rows if row["layer"] == 271)
    axis.annotate(
        "Layer 271 (pruned)",
        (pruned["work_gflops"], pruned["payload_mbit"]),
        xytext=(-15, 15),
        textcoords="offset points",
        ha="center",
        fontsize=9,
    )
    axis.set(
        xlabel="Cumulative computation (GFLOPs)", ylabel="Intermediate data (Mbit)"
    )
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    figure.savefig(output)
    plt.close(figure)


def figure6(rows: list[dict], output: Path) -> None:
    lookup = {row["model"]: row for row in rows}
    rows = [lookup[model] for model in MODELS]
    x = np.arange(len(rows))
    figure, axes = plt.subplots(1, 2, figsize=(9.4, 3.8), layout="constrained")
    for method, shift, color in (
        ("dnnsplit", -0.17, "black"),
        ("anoda", 0.17, "#e76f51"),
    ):
        label = "DNNSplit" if method == "dnnsplit" else "ANODA"
        axes[0].scatter(
            x + shift, [r[f"{method}_count"] for r in rows], color=color, label=label
        )
        axes[1].bar(
            x + shift,
            [r[f"{method}_graph_reduction_pct"] for r in rows],
            width=0.32,
            color=color,
            label=label,
        )
    for axis in axes:
        axis.set_xticks(x, LABELS, rotation=30, ha="right", fontsize=9)
        axis.grid(axis="y", alpha=0.25)
        axis.set_axisbelow(True)
        axis.legend(frameon=False)
    axes[0].set(ylabel="Candidate split points", ylim=(0, 8))
    axes[1].set(ylabel="Reduction of graph positions (%)", ylim=(90, 100))
    figure.savefig(output)
    plt.close(figure)


def figure7(summary: dict[str, object], output: Path) -> None:
    """Render nominal energy and delivery results for all five policies."""

    lookup = {
        (row["model"], row["policy"]): row
        for row in summary["rows"]
        if row["level"] == "nominal"
    }
    x = np.arange(len(MODELS), dtype=float)
    width = 0.15
    with plt.rc_context(
        {
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.axisbelow": True,
            "pdf.fonttype": 42,
        }
    ):
        figure, axes = plt.subplots(2, 1, figsize=(8.2, 5.8), sharex=True)
        for number, policy in enumerate(POLICIES):
            rows = [lookup[model, policy] for model in MODELS]
            position = x + (number - 2) * width
            effective = np.asarray([row["effective_per_offered_j"] for row in rows])
            wasted = np.asarray([row["wasted_per_offered_j"] for row in rows])
            axes[0].bar(
                position,
                effective,
                width,
                color=COLORS[policy],
                label=policy,
            )
            axes[0].bar(
                position,
                wasted,
                width,
                bottom=effective,
                color=COLORS[policy],
                alpha=0.35,
                hatch="//",
            )
            delivery = np.asarray([row["delivery_pct"] for row in rows])
            deviation = np.asarray([row["delivery_std_pct"] for row in rows])
            axes[1].bar(position, delivery, width, color=COLORS[policy])
            axes[1].errorbar(
                position,
                delivery,
                yerr=deviation,
                fmt="none",
                ecolor="black",
                elinewidth=0.8,
                capsize=2,
            )
        axes[0].set_ylabel("EO energy / offered task (J)")
        axes[0].set_yscale("log")
        axes[1].set_ylabel("Delivered tasks (%)")
        axes[1].set_xticks(x, LABELS)
        axes[1].set_ylim(bottom=0)
        for axis in axes:
            axis.grid(axis="y", alpha=0.3)
        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(handles, labels, ncol=5, loc="upper center", frameon=False)
        axes[0].legend(
            handles=[
                Patch(facecolor="gray", label="Effective"),
                Patch(facecolor="lightgray", hatch="//", label="Wasted"),
            ],
            ncol=2,
            loc="upper right",
            frameon=False,
        )
        figure.tight_layout(rect=(0, 0, 1, 0.94))
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, bbox_inches="tight")
        plt.close(figure)


def figure8(rows: list[dict[str, object]], output: Path) -> None:
    """Render the rho and downlink-rate sensitivity facets."""

    lookup = {(row["model"], row["axis"], float(row["value"])): row for row in rows}
    grids = (
        ("rho", (0.008, 0.012, 0.016, 0.020, 0.024, 0.032)),
        ("rate", (5.0, 10.0, 20.0, 40.0, 80.0)),
    )
    with plt.rc_context(
        {
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.axisbelow": True,
            "pdf.fonttype": 42,
        }
    ):
        figure, axes = plt.subplots(2, 5, figsize=(15, 4.6))
        for row_number, (axis_name, values) in enumerate(grids):
            x = np.asarray(values, dtype=float)
            for column, model in enumerate(MODELS):
                axis = axes[row_number, column]
                selected = [lookup[model, axis_name, value] for value in values]
                series = {}
                for policy in ("STLT", "SLICE"):
                    series[policy] = np.asarray(
                        [
                            np.nan
                            if next(
                                p for p in item["policies"] if p["policy"] == policy
                            )["status"]
                            == "NF"
                            else next(
                                p for p in item["policies"] if p["policy"] == policy
                            )["mean_delivered"]
                            for item in selected
                        ],
                        dtype=float,
                    )
                axis.plot(x, series["STLT"], "-o", color=COLORS["STLT"], label="STLT")
                axis.plot(
                    x,
                    series["SLICE"],
                    "--s",
                    color=COLORS["SLICE"],
                    markerfacecolor="white",
                    label="SLICE",
                )
                for value, item in zip(x, selected):
                    slc = next(p for p in item["policies"] if p["policy"] == "SLICE")
                    if slc["status"] == "NF":
                        axis.text(
                            value,
                            0.04,
                            "NF",
                            transform=axis.get_xaxis_transform(),
                            ha="center",
                        )
                if axis_name == "rate":
                    axis.set_xscale("log")
                axis.axvline(
                    0.016 if axis_name == "rho" else 20, color="gray", linestyle=":"
                )
                axis.fill_between(
                    x, series["STLT"], series["SLICE"], alpha=0.1, color=COLORS["STLT"]
                )
                axis.set_xticks(x, [f"{value:g}" for value in values])
                axis.tick_params(
                    axis="x", labelsize=8, rotation=30 if axis_name == "rho" else 0
                )
                axis.grid(alpha=0.3)
                if row_number == 0:
                    axis.set_title(LABELS[column])
                if column == 0:
                    axis.set_ylabel("Mean deliveries")
                axis.set_xlabel("rho" if axis_name == "rho" else "Rmax (Mbps)")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        figure.legend(handles, labels, ncol=2, loc="upper center", frameon=False)
        figure.tight_layout(rect=(0, 0, 1, 0.95))
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, bbox_inches="tight")
        plt.close(figure)
