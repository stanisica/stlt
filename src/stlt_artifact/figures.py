"""Paper figure rendering from machine-readable experiment summaries."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MODELS = (
    "squeezenet1_1",
    "swin_v2_t",
    "efficientnet_b4",
    "resnet50",
    "densenet169",
)
LABELS = ("SqueezeNet", "Swin-T", "EfficientNet-B4", "ResNet50", "DenseNet169")
POLICIES = ("STLT", "SLICE", "TOBC", "TOGC", "RAND")
COLORS = {
    "STLT": "#e76f51",
    "SLICE": "#2a6f97",
    "TOBC": "#6a994e",
    "TOGC": "#9c6644",
    "RAND": "#8d6cab",
}


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
        axes[1].set_ylabel("Delivered tasks (%)")
        axes[1].set_xticks(x, LABELS)
        axes[1].set_ylim(bottom=0)
        for axis in axes:
            axis.grid(axis="y", alpha=0.3)
        axes[0].legend(ncol=5, loc="upper center", frameon=False)
        figure.tight_layout()
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, bbox_inches="tight")
        plt.close(figure)


def figure8(rows: list[dict[str, object]], output: Path) -> None:
    """Render the rho and downlink-rate sensitivity facets."""

    lookup = {
        (row["model"], row["axis"], float(row["value"])): row for row in rows
    }
    grids = (("rho", (0.008, 0.012, 0.016, 0.020, 0.024, 0.032)), ("rate", (5.0, 10.0, 20.0, 40.0, 80.0)))
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
                            if next(p for p in item["policies"] if p["policy"] == policy)["status"] == "NF"
                            else next(p for p in item["policies"] if p["policy"] == policy)["mean_delivered"]
                            for item in selected
                        ],
                        dtype=float,
                    )
                axis.plot(x, series["STLT"], "-o", color=COLORS["STLT"], label="STLT")
                axis.plot(x, series["SLICE"], "--s", color=COLORS["SLICE"], markerfacecolor="white", label="SLICE")
                for value, item in zip(x, selected):
                    slc = next(p for p in item["policies"] if p["policy"] == "SLICE")
                    if slc["status"] == "NF":
                        axis.text(value, 0.04, "NF", transform=axis.get_xaxis_transform(), ha="center")
                if axis_name == "rate":
                    axis.set_xscale("log")
                axis.set_xticks(x, [f"{value:g}" for value in values])
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
