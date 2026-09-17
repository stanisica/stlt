#!/usr/bin/env python3
"""Direct Jetson measurement of the ANELA rows in Table 3.

Each cell runs ANELA on the real 4096x4096 torch.fx D_cut candidate set of one
model (ALL valid split points, DNNSplit set, ANODA set). Satellite states follow
synthetic_state() from anela_replay_benchmark.py, but they are generated before
the measured window, so latency and energy cover only the ANELA calls.

Power is board VDD_IN from tegrastats, integrated over the measured loop, as in
anela_search_space_sweep.py (Figure 10). Constants follow the paper's Table 3.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tegrastats_power import TegraStatsPowerSampler
from profile_points import anoda_layers, dnnsplit_layers, load_profile_rows

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import stlt_utils as utils  # noqa: E402
from stlt_algorithm import adaptive_selection_algorithm  # noqa: E402
from measure_scaling import PAPER_CONSTANTS, measure_power  # noqa: E402

MODELS = ["squeezenet1_1", "swin_v2_t", "efficientnet_b4", "resnet50", "densenet169"]


def synthetic_state(decision_idx: int, seed: int):
    # Same generator as anela_replay_benchmark.synthetic_state.
    rng = random.Random(seed + decision_idx * 1009)
    e_max, t_comp, t_comm = utils.E_MAX, utils.T_COMP, utils.T_COMM
    d_max = utils.R_MAX * t_comm
    return utils.SatelliteState(
        E_current=rng.uniform(0.25 * e_max, 0.95 * e_max),
        t=rng.uniform(0.0, t_comp + t_comm),
        theta=rng.uniform(0.0, math.pi / 2.0),
        delta_E_until_comm_j=rng.uniform(-0.05 * e_max, 0.05 * e_max),
        delta_E_during_comm_j=rng.uniform(-0.02 * e_max, 0.02 * e_max),
        accumulated_data=rng.uniform(0.0, max(1.0, 0.35 * d_max)),
    )


def load_sets(profile_dir: Path):
    sets = {}
    for model in MODELS:
        rows = load_profile_rows(profile_dir / f"{model}.json")
        pts = [utils.SplitPoint(layer_index=int(r["idx"]), W=float(r["W_cumGFLOPs"]) * 1e9, D=float(r["D_cut_bits"]))
               for r in rows]
        sets[(model, "all")] = pts
        selected = {
            "dnnsplit": dnnsplit_layers(rows),
            "anoda": anoda_layers(rows),
        }
        for name, layers in selected.items():
            sets[(model, name)] = [p for p in pts if p.layer_index in layers]
            assert len(sets[(model, name)]) == len(layers), (model, name)
    return sets


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--profile-dir",
        default=str(SCRIPT_DIR.parents[2] / "data" / "model-profiles"),
    )
    p.add_argument("--states", type=int, default=850)
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--min-seconds", type=float, default=20.0)
    p.add_argument("--power-interval-ms", type=int, default=20)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--output-dir", default=str(SCRIPT_DIR / "table4_benchmark"))
    args = p.parse_args()

    for k, v in PAPER_CONSTANTS.items():
        setattr(utils, k, v)
    sets = load_sets(Path(args.profile_dir))
    states = [synthetic_state(i, args.seed) for i in range(args.states)]
    sampler = TegraStatsPowerSampler(interval_ms=args.power_interval_ms)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    _, idle_e, idle_t, _ = measure_power(sampler, lambda: time.sleep(10.0))
    idle_w = idle_e / idle_t
    print(f"states={len(states)} idle VDD_IN={idle_w:.3f} W", flush=True)

    rows = []
    for model in MODELS:
        for name in ("all", "dnnsplit", "anoda"):
            L_star = sets[(model, name)]
            feasible = sum(adaptive_selection_algorithm(L_star, s).feasible for s in states)
            t = time.perf_counter()
            for s in states:
                adaptive_selection_algorithm(L_star, s)
            repeats = max(1, int(args.min_seconds / (time.perf_counter() - t)) + 1)
            for run in range(args.runs):
                def body():
                    t0 = time.perf_counter()
                    for _ in range(repeats):
                        for s in states:
                            adaptive_selection_algorithm(L_star, s)
                    return time.perf_counter() - t0
                algo_s, energy_j, wall_s, n_samples = measure_power(sampler, body)
                total = repeats * len(states)
                row = dict(model=model, candidate_set=name, candidates=len(L_star), run=run,
                           states=len(states), feasible_states=feasible, repeats=repeats,
                           total_decisions=total, algo_time_s=algo_s, latency_us=1e6 * algo_s / total,
                           energy_j=energy_j, wall_s=wall_s, avg_power_w=energy_j / wall_s,
                           idle_power_w=idle_w, energy_per_decision_uj=1e6 * energy_j / total,
                           dynamic_energy_per_decision_uj=1e6 * (energy_j - idle_w * wall_s) / total,
                           power_samples=n_samples)
                rows.append(row)
                print(f"{model:16s} {name:8s} k={len(L_star):3d} run={run} lat={row['latency_us']:.2f} us "
                      f"E={row['energy_per_decision_uj']:.1f} uJ P={row['avg_power_w']:.3f} W", flush=True)

    with open(out / f"{run_id}_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = []
    for model in MODELS:
        for name in ("all", "dnnsplit", "anoda"):
            rs = [r for r in rows if r["model"] == model and r["candidate_set"] == name]
            summary.append(dict(model=model, candidate_set=name, candidates=rs[0]["candidates"],
                                feasible_states=rs[0]["feasible_states"], runs=len(rs),
                                **{k: statistics.mean(r[k] for r in rs) for k in
                                   ("latency_us", "energy_per_decision_uj", "dynamic_energy_per_decision_uj", "avg_power_w")},
                                latency_us_std=statistics.stdev(r["latency_us"] for r in rs),
                                energy_per_decision_uj_std=statistics.stdev(r["energy_per_decision_uj"] for r in rs)))
    meta = dict(run_id=run_id, host=__import__("socket").gethostname(), python=sys.version,
                constants=PAPER_CONSTANTS, args=vars(args), idle_power_w=idle_w,
                device_model=Path("/proc/device-tree/model").read_text().strip("\x00\n")
                if Path("/proc/device-tree/model").exists() else None,
                power_mode=__import__("subprocess").run(["nvpmodel", "-q"], capture_output=True, text=True).stdout)
    json.dump(dict(meta=meta, summary=summary), open(out / f"{run_id}_summary.json", "w"), indent=2)
    for s in summary:
        print(json.dumps(s), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
