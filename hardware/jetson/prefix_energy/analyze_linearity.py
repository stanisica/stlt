#!/usr/bin/env python3
"""Fit the measured Jetson CPU energy against Equation 2 of the STLT paper.

Equation 2 states E_comp(l) = kappa * W(l) with kappa = gamma * f^2 / alpha, a
single device constant. This script tests that claim three ways:

  1. proportionality   -- least squares fit of E on W, per model and pooled,
                          reporting R^2 and the mean absolute percentage error;
  2. constancy of kappa -- the per-split ratio E(l) / W(l), which Equation 2
                          requires to be flat in W;
  3. back-solved constants -- the alpha and gamma implied by the measurement at
                          the pinned frequency, against the current evaluation
                          parameters.

Measurements are joined to `data/model-profiles/<model>.json` by split index,
so the W(l) on the x axis is the same W(l) the paper's results use.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ARTIFACT_ROOT = Path(__file__).resolve().parents[2]
TABLES = ARTIFACT_ROOT / "data" / "model-profiles"

# Current formula-aligned evaluation parameters.
PAPER = {"gamma": 1.6721173078153315e-28, "f": 1.5e9, "alpha": 6.0}
PAPER_KAPPA = PAPER["gamma"] * PAPER["f"] ** 2 / PAPER["alpha"]  # J per FLOP

MODEL_ORDER = ["squeezenet1_1", "swin_v2_t", "efficientnet_b4", "resnet50", "densenet169"]
COLORS = {
    "squeezenet1_1": "#0072B2",
    "swin_v2_t": "#D55E00",
    "efficientnet_b4": "#009E73",
    "resnet50": "#CC79A7",
    "densenet169": "#E69F00",
}


def load_run(run_dir: Path):
    meta = json.loads((run_dir / "meta.json").read_text())
    records = [json.loads(l) for l in (run_dir / "records.jsonl").read_text().splitlines() if l.strip()]
    return meta, records


def table_w_gflops(model: str):
    table = json.loads((TABLES / f"{model}.json").read_text())
    return {r["idx"]: r["W_cumGFLOPs"] for r in table["rows"]}, table["meta"]["n_nodes"]


def aggregate(records, rail, meta):
    """Collapse repeats of the same (model, split) into a median, with spread."""
    by_key = {}
    for r in records:
        e = r.get(f"{rail}_e_dyn_per_infer_j")
        if e is None:
            continue
        by_key.setdefault((r["model"], r["split_index"]), []).append(r)

    rows = []
    for (model, k), group in sorted(by_key.items()):
        w_table, n_nodes = table_w_gflops(model)
        if meta["profile"][model]["n_nodes"] != n_nodes:
            raise SystemExit(
                f"{model}: device traced {meta['profile'][model]['n_nodes']} nodes but the "
                f"stored table has {n_nodes}; split indices are not interchangeable."
            )
        es = [g[f"{rail}_e_dyn_per_infer_j"] for g in group]
        ts = [g["t_iter_s"] for g in group]
        rows.append({
            "model": model,
            "split_index": k,
            "W_gflops": w_table[k],
            "W_flops": w_table[k] * 1e9,
            "n_repeats": len(group),
            "E_j": statistics.median(es),
            "E_spread_pct": (max(es) - min(es)) / statistics.median(es) * 100 if statistics.median(es) else 0.0,
            "t_s": statistics.median(ts),
            "P_dyn_w": statistics.median(g[f"{rail}_p_dyn_w"] for g in group),
            "mhz": statistics.median([g["busy_core_mhz_load"] for g in group if g["busy_core_mhz_load"]] or [0]),
            "on_hull": k in meta["profile"][model]["hull_indices"],
        })
    return rows


def fit(xs, ys, through_origin=False):
    """Least squares. Returns slope, intercept, R^2."""
    n = len(xs)
    if n < 2:
        return None, None, None
    if through_origin:
        sxx = sum(x * x for x in xs)
        slope = sum(x * y for x, y in zip(xs, ys)) / sxx if sxx else 0.0
        inter = 0.0
    else:
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx == 0:
            return None, None, None
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        inter = my - slope * mx
    my = sum(ys) / n
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + inter)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")
    return slope, inter, r2


def mape(xs, ys, slope, inter):
    vals = [abs((slope * x + inter) - y) / y for x, y in zip(xs, ys) if y > 0]
    return 100.0 * sum(vals) / len(vals) if vals else float("nan")


def summarize(rows, f_hz):
    """Per-model and pooled fits, plus the implied alpha and gamma."""
    out = {"per_model": {}, "pooled": {}}

    def block(sel):
        # W = 0 carries no information for a proportional fit and would dominate
        # the ratio statistics, so the zero-work control is reported separately.
        work = [r for r in sel if r["W_flops"] > 0]
        xs = [r["W_flops"] for r in work]
        ys = [r["E_j"] for r in work]
        s_free, i_free, r2_free = fit(xs, ys)
        s_org, _, r2_org = fit(xs, ys, through_origin=True)
        kappas = [r["E_j"] / r["W_flops"] for r in work]
        # alpha = FLOPs per cycle achieved; gamma = dynamic energy per cycle / f^2
        alphas = [r["W_flops"] / (f_hz * r["t_s"]) for r in work if r["t_s"] > 0]
        gammas = [r["P_dyn_w"] / f_hz ** 3 for r in work if r["P_dyn_w"]]
        zero = [r for r in sel if r["W_flops"] == 0]
        return {
            "n_points": len(work),
            "W_range_gflops": [min(r["W_gflops"] for r in work), max(r["W_gflops"] for r in work)],
            "kappa_j_per_flop": s_org,
            "kappa_free_slope": s_free,
            "intercept_j": i_free,
            "r2_through_origin": r2_org,
            "r2_free": r2_free,
            "mape_through_origin_pct": mape(xs, ys, s_org, 0.0),
            "mape_free_pct": mape(xs, ys, s_free, i_free),
            "kappa_ratio_min": min(kappas),
            "kappa_ratio_max": max(kappas),
            "kappa_ratio_median": statistics.median(kappas),
            "kappa_spread_pct": (max(kappas) - min(kappas)) / statistics.median(kappas) * 100,
            "alpha_flops_per_cycle_median": statistics.median(alphas) if alphas else None,
            "alpha_flops_per_cycle_max": max(alphas) if alphas else None,
            "gamma_j_s2_median": statistics.median(gammas) if gammas else None,
            "zero_work_energy_j": [r["E_j"] for r in zero],
        }

    for m in MODEL_ORDER:
        sel = [r for r in rows if r["model"] == m]
        if sel:
            out["per_model"][m] = block(sel)
    out["pooled"] = block(rows)
    out["paper"] = {
        "gamma": PAPER["gamma"], "f": PAPER["f"], "alpha": PAPER["alpha"],
        "kappa_j_per_flop": PAPER_KAPPA,
    }
    return out


def make_figure(rows, summary, out_png, f_hz):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    work = [r for r in rows if r["W_flops"] > 0]

    ax = axes[0]
    for m in MODEL_ORDER:
        sel = [r for r in work if r["model"] == m]
        if not sel:
            continue
        ax.scatter([r["W_gflops"] for r in sel], [r["E_j"] for r in sel],
                   s=26, color=COLORS[m], label=m, alpha=0.85, edgecolors="none")
        hull = [r for r in sel if r["on_hull"]]
        if hull:
            ax.scatter([r["W_gflops"] for r in hull], [r["E_j"] for r in hull],
                       s=90, facecolors="none", edgecolors=COLORS[m], linewidths=1.4)
    k = summary["pooled"]["kappa_j_per_flop"]
    xmax = max(r["W_gflops"] for r in work)
    ax.plot([0, xmax], [0, k * xmax * 1e9], "k--", lw=1.2,
            label=f"pooled fit  {k * 1e9:.3f} J/GFLOP")
    ax.set_xlabel("cumulative FLOPs  $W(l)$  [GFLOP]")
    ax.set_ylabel("measured CPU energy  [J / inference]")
    ax.set_title("(a) measured energy vs $W(l)$")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[1]
    for m in MODEL_ORDER:
        sel = [r for r in work if r["model"] == m]
        if not sel:
            continue
        ax.scatter([r["W_gflops"] for r in sel],
                   [r["E_j"] / r["W_gflops"] for r in sel],
                   s=26, color=COLORS[m], alpha=0.85, edgecolors="none")
    kg = k * 1e9
    ax.axhline(kg, color="k", ls="--", lw=1.2)
    ax.axhspan(kg * 0.9, kg * 1.1, color="k", alpha=0.08, label="pooled $\\kappa$ $\\pm$10%")
    ax.set_xlabel("cumulative FLOPs  $W(l)$  [GFLOP]")
    ax.set_ylabel("$E(l)\\,/\\,W(l)$  [J / GFLOP]")
    ax.set_title("(b) is $\\kappa$ constant?")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[2]
    for m in MODEL_ORDER:
        sel = [r for r in work if r["model"] == m]
        if not sel:
            continue
        ax.scatter([r["W_gflops"] for r in sel],
                   [100.0 * (k * r["W_flops"] - r["E_j"]) / r["E_j"] for r in sel],
                   s=26, color=COLORS[m], alpha=0.85, edgecolors="none")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("cumulative FLOPs  $W(l)$  [GFLOP]")
    ax.set_ylabel("prediction error  [%]")
    ax.set_title("(c) residuals of the proportional model")

    for a in axes:
        a.grid(alpha=0.25, lw=0.5)
        a.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        f"Equation 2 on Jetson Orin Nano CPU, one Cortex-A78AE core at "
        f"{f_hz / 1e9:.4f} GHz, 224$\\times$224 input", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_png, dpi=180)
    print(f"wrote {out_png}")


def markdown(rows, summary, f_hz):
    p = summary["pooled"]
    lines = [
        f"# Equation 2 against measured Jetson CPU energy",
        "",
        f"One Cortex-A78AE core pinned at {f_hz / 1e9:.4f} GHz, 224x224 input, "
        f"{p['n_points']} split points over {len(MODEL_ORDER)} models.",
        "",
        "| model | splits | W range [GFLOP] | kappa [J/GFLOP] | R2 (through origin) | MAPE [%] | kappa spread [%] | alpha [FLOP/cycle] |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for m in MODEL_ORDER:
        b = summary["per_model"].get(m)
        if not b:
            continue
        lo, hi = b["W_range_gflops"]
        lines.append(
            f"| `{m}` | {b['n_points']} | {lo:.3f}-{hi:.3f} | "
            f"{b['kappa_j_per_flop'] * 1e9:.4f} | {b['r2_through_origin']:.4f} | "
            f"{b['mape_through_origin_pct']:.1f} | {b['kappa_spread_pct']:.0f} | "
            f"{b['alpha_flops_per_cycle_median']:.2f} |")
    lo, hi = p["W_range_gflops"]
    lines.append(
        f"| **pooled** | {p['n_points']} | {lo:.3f}-{hi:.3f} | "
        f"{p['kappa_j_per_flop'] * 1e9:.4f} | {p['r2_through_origin']:.4f} | "
        f"{p['mape_through_origin_pct']:.1f} | {p['kappa_spread_pct']:.0f} | "
        f"{p['alpha_flops_per_cycle_median']:.2f} |")
    lines += [
        "",
        f"Paper Table 2: gamma = {PAPER['gamma']:.1e} J.s^2, f = {PAPER['f']:.1e} Hz, "
        f"alpha = {PAPER['alpha']} FLOP, giving kappa = {PAPER_KAPPA * 1e9:.4f} J/GFLOP.",
        f"Measured pooled kappa = {p['kappa_j_per_flop'] * 1e9:.4f} J/GFLOP, a ratio of "
        f"{PAPER_KAPPA / p['kappa_j_per_flop']:.1f}x.",
        f"Implied alpha at the pinned frequency: median "
        f"{p['alpha_flops_per_cycle_median']:.2f}, max {p['alpha_flops_per_cycle_max']:.2f} FLOP/cycle.",
        f"Implied gamma from dynamic power: {p['gamma_j_s2_median']:.3e} J.s^2.",
        f"Zero-work control, W(l) = 0: {[round(v, 6) for v in p['zero_work_energy_j']]} J.",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="measurements/results")
    ap.add_argument("--rail", default="VDD_CPU_GPU_CV",
                    help="VDD_CPU_GPU_CV is the CPU rail; VDD_IN is the whole board")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    run_dir = Path(args.run)
    if not run_dir.is_absolute():
        run_dir = Path(__file__).resolve().parent / run_dir
    out_dir = Path(args.out_dir) if args.out_dir else run_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    meta, records = load_run(run_dir)
    f_hz = float(meta["device"]["scaling_max_khz"]) * 1e3

    rows = aggregate(records, args.rail, meta)
    if not rows:
        raise SystemExit(f"no usable records for rail {args.rail}")
    summary = summarize(rows, f_hz)
    summary["rail"] = args.rail
    summary["f_hz"] = f_hz
    summary["device"] = meta["device"]

    (out_dir / f"summary_{args.rail}.json").write_text(json.dumps(
        {"summary": summary, "points": rows}, indent=2))
    md = markdown(rows, summary, f_hz)
    (out_dir / f"summary_{args.rail}.md").write_text(md + "\n")
    make_figure(rows, summary, out_dir / f"eq2_validation_{args.rail}.png", f_hz)
    print()
    print(md)


if __name__ == "__main__":
    main()
