#!/usr/bin/env python3
"""ANELA per-decision overhead versus candidate-set size |L*| on a Jetson.

Jetson port of the search-space overhead experiment (Figure 9 in the current
paper revision).
Same sweep design: L* is the ResNet50 ANODA candidate set padded with seeded
random points to |L*|, and the decision list covers 10 orbital cycles with one
decision every 60 s of computation phase. States are constant and favorable,
so every candidate passes all filters and each decision evaluates the full set.

Power follows the Table 4 harness (anela_replay_benchmark.py): board VDD_IN from
tegrastats, integrated over the measured loop. Idle VDD_IN is also recorded.
Constants follow the paper's Table 3.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from tegrastats_power import PowerSample, TegraStatsPowerSampler, integrate_energy_j
from profile_points import anoda_rows, load_profile_rows

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import stlt_utils as utils  # noqa: E402
from stlt_algorithm import adaptive_selection_algorithm  # noqa: E402

PAPER_CONSTANTS = dict(GAMMA=2.0e-26, F=1.5e9, ALPHA=32.0, BETA=3.8e-7, T_COMP=5100.0,
                       T_COMM=300.0, R_MAX=10e6, P_SUN=40.0, E_MAX=8.28e5)


def build_L_star(predictions: List[dict], n: int, seed: int) -> List[Any]:
    ws = [float(p["cumulative_gflops"]) for p in predictions]
    ds = [float(p["output_data_mb"]) for p in predictions]
    rng = random.Random(seed + n)
    pts = [utils.SplitPoint(layer_index=int(p.get("layer_index", i)),
                            W=float(p["cumulative_gflops"]) * 1e9,
                            D=float(p["output_data_mb"]) * 1024 * 1024 * 8.0)
           for i, p in enumerate(predictions[:n])]
    while len(pts) < n:
        pts.append(utils.SplitPoint(layer_index=len(pts),
                                    W=rng.uniform(min(ws), max(ws)) * 1e9,
                                    D=rng.uniform(min(ds), max(ds)) * 1024 * 1024 * 8.0))
    pts.sort(key=lambda p: p.W)
    return pts


def decisions_over_orbits(orbits: int, interval_s: float) -> int:
    cycle = PAPER_CONSTANTS["T_COMP"] + PAPER_CONSTANTS["T_COMM"]
    count, since = 0, 0.0
    for step in range(int(orbits * cycle) + 1):
        if step % cycle >= PAPER_CONSTANTS["T_COMP"]:
            continue
        since += 1.0
        if since >= interval_s:
            count, since = count + 1, 0.0
    return count


def measure_power(sampler: TegraStatsPowerSampler, body):
    samples: List[PowerSample] = []

    def loop():
        for s in sampler.samples():
            samples.append(s)

    sampler.start()
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    time.sleep(0.5)
    t0 = time.monotonic()
    result = body()
    t1 = time.monotonic()
    time.sleep(0.2)
    sampler.stop()
    th.join(timeout=2.0)
    energy, n = integrate_energy_j([s for s in samples if t0 <= s.t_monotonic <= t1])
    return result, energy, t1 - t0, n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="resnet50")
    p.add_argument(
        "--profile-dir",
        default=str(SCRIPT_DIR.parents[2] / "data" / "model-profiles"),
    )
    p.add_argument("--points", default="5,10,20,100,500,1000")
    p.add_argument("--orbits", type=int, default=10)
    p.add_argument("--interval-s", type=float, default=60.0)
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--min-seconds", type=float, default=20.0)
    p.add_argument("--power-interval-ms", type=int, default=20)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--output-dir", default=str(SCRIPT_DIR / "search_space_sweep"))
    args = p.parse_args()

    for k, v in PAPER_CONSTANTS.items():
        setattr(utils, k, v)
    profile = Path(args.profile_dir) / f"{args.model}.json"
    predictions = [
        {
            "layer_index": row["idx"],
            "cumulative_gflops": row["W_cumGFLOPs"],
            "output_data_mb": float(row["D_cut_bits"]) / (1024 * 1024 * 8),
        }
        for row in anoda_rows(load_profile_rows(profile))
    ]
    decisions = decisions_over_orbits(args.orbits, args.interval_s)
    state = utils.SatelliteState(E_current=1e9, t=0.0, theta=0.0, delta_E_until_comm_j=0.0,
                                 delta_E_during_comm_j=0.0, accumulated_data=0.0)
    sampler = TegraStatsPowerSampler(interval_ms=args.power_interval_ms)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    _, idle_e, idle_t, _ = measure_power(sampler, lambda: time.sleep(10.0))
    idle_w = idle_e / idle_t
    print(f"decisions per {args.orbits} orbits = {decisions}, idle VDD_IN = {idle_w:.3f} W", flush=True)

    rows = []
    for n in [int(x) for x in args.points.split(",")]:
        L_star = build_L_star(predictions, n, args.seed)
        assert all(adaptive_selection_algorithm(L_star, state).feasible for _ in range(3))
        # Warm up and size the repeat count so each run lasts at least min_seconds.
        t = time.perf_counter()
        for _ in range(decisions):
            adaptive_selection_algorithm(L_star, state)
        per_list = time.perf_counter() - t
        repeats = max(1, int(args.min_seconds / per_list) + 1)
        for run in range(args.runs):
            def body():
                t0 = time.perf_counter()
                for _ in range(repeats):
                    for _ in range(decisions):
                        adaptive_selection_algorithm(L_star, state)
                return time.perf_counter() - t0
            algo_s, energy_j, wall_s, n_samples = measure_power(sampler, body)
            total = repeats * decisions
            row = dict(num_points=n, run=run, orbits=args.orbits, decisions_per_list=decisions,
                       repeats=repeats, total_decisions=total, algo_time_s=algo_s,
                       latency_ms=1e3 * algo_s / total, energy_j=energy_j, wall_s=wall_s,
                       avg_power_w=energy_j / wall_s, idle_power_w=idle_w,
                       energy_per_decision_mj=1e3 * energy_j / total,
                       dynamic_energy_per_decision_mj=1e3 * (energy_j - idle_w * wall_s) / total,
                       power_samples=n_samples)
            rows.append(row)
            print(f"|L*|={n:>5} run={run} latency={row['latency_ms']:.6f} ms "
                  f"energy={row['energy_per_decision_mj']:.6f} mJ power={row['avg_power_w']:.3f} W "
                  f"samples={n_samples}", flush=True)

    with open(out / f"{run_id}_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = []
    for n in sorted({r["num_points"] for r in rows}):
        rs = [r for r in rows if r["num_points"] == n]
        summary.append({k: statistics.mean(r[k] for r in rs) for k in
                        ["latency_ms", "energy_per_decision_mj", "dynamic_energy_per_decision_mj", "avg_power_w"]}
                       | {"num_points": n, "runs": len(rs),
                          "latency_ms_std": statistics.stdev(r["latency_ms"] for r in rs) if len(rs) > 1 else 0.0,
                          "energy_per_decision_mj_std": statistics.stdev(r["energy_per_decision_mj"] for r in rs) if len(rs) > 1 else 0.0})
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
