#!/usr/bin/env python3
"""Measure on-board computation energy of DNN head submodules on Jetson CPU.

Tests Equation 2 of the STLT paper, E_comp(l) = (gamma * f^2 / alpha) * W(l),
which predicts that prefix energy is proportional to cumulative FLOPs with a
single device constant. For each split point l the head submodule (nodes 0..l,
see fx_prefix.py) is executed in a sustained loop on one pinned CPU core while
tegrastats samples the board rails. Idle windows bracket every load window, so
the reported energy is dynamic energy, i.e. static draw of the platform removed.

CPU only. The GPU is never touched, so VDD_CPU_GPU_CV is read as the CPU rail.

Writes one JSON record per measurement to <out>/records.jsonl as it goes, plus
<out>/meta.json describing the device and the split sets.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import fx_prefix  # noqa: E402
from tegrastats_rails import (  # noqa: E402
    RailSampler,
    busy_core_mhz,
    max_temp_c,
    mean_power_w,
    trapezoid_energy_j,
)

RAILS = ["VDD_IN", "VDD_CPU_GPU_CV", "VDD_SOC"]


class NullSampler:
    """Stand-in when tegrastats is absent, so the harness can be dry-run off
    device. Timing is still measured; every power field comes out null."""

    def start(self):
        pass

    def stop(self):
        pass

    def window(self, t0, t1):
        return []


def read_sys(path, default=None):
    try:
        return Path(path).read_text().strip()
    except Exception:
        return default


def device_meta():
    cpu0 = "/sys/devices/system/cpu/cpu0/cpufreq"
    return {
        "hostname": platform.node(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "l4t": read_sys("/etc/nv_tegra_release"),
        "board": read_sys("/proc/device-tree/model", "").replace("\x00", ""),
        "nvpmodel": read_sys("/var/lib/nvpmodel/status"),
        "governor": read_sys(f"{cpu0}/scaling_governor"),
        "scaling_min_khz": read_sys(f"{cpu0}/scaling_min_freq"),
        "scaling_max_khz": read_sys(f"{cpu0}/scaling_max_freq"),
        "cpuinfo_max_khz": read_sys(f"{cpu0}/cpuinfo_max_freq"),
        "fan_pwm": read_sys("/sys/class/hwmon/hwmon0/pwm1"),
        "loadavg": read_sys("/proc/loadavg"),
    }


def select_splits(gm, w_macs, d_bits, n_target):
    """Split points to measure: ANODA hull points, the extremes, then a spread
    that covers the W axis evenly so the linearity fit is not index-biased."""
    valid = fx_prefix.valid_split_indices(gm)
    hull_local = fx_prefix.lower_hull_idx(
        [w_macs[i] for i in valid], [d_bits[i] for i in valid]
    )
    hull = [valid[i] for i in hull_local]

    picks = set(hull) | {valid[0], valid[-1]}
    w_max = w_macs[valid[-1]]
    if w_max > 0 and n_target > len(picks):
        remaining = n_target - len(picks)
        targets = [w_max * (j + 1) / (remaining + 1) for j in range(remaining)]
        for t in targets:
            cand = min(
                (i for i in valid if i not in picks),
                key=lambda i: abs(w_macs[i] - t),
                default=None,
            )
            if cand is not None:
                picks.add(cand)
    return sorted(picks), sorted(hull)


def time_iterations(fn, n):
    t0 = time.monotonic()
    with torch.no_grad():
        for _ in range(n):
            fn()
    return time.monotonic() - t0


def measure(sampler, head, x, load_s, idle_s, min_iters, probe_iters=3):
    """Bracketed idle / load / idle measurement of one head submodule."""

    def run_once():
        head(x)

    # Warm caches and estimate per-iteration cost.
    with torch.no_grad():
        run_once()
    probe_n = max(1, probe_iters)
    probe_t = time_iterations(run_once, probe_n)
    t_iter = max(probe_t / probe_n, 1e-9)
    n_iters = max(min_iters, int(load_s / t_iter) + 1)
    n_iters = min(n_iters, 5_000_000)

    idle0_t0 = time.monotonic()
    time.sleep(idle_s)
    idle0_t1 = time.monotonic()

    load_t0 = time.monotonic()
    load_wall = time_iterations(run_once, n_iters)
    load_t1 = time.monotonic()

    idle1_t0 = time.monotonic()
    time.sleep(idle_s)
    idle1_t1 = time.monotonic()

    # Drop the first and last sampling period of each window: tegrastats
    # reports over the interval preceding the print, so edge samples straddle
    # the transition.
    guard = 0.25
    load = sampler.window(load_t0 + guard, load_t1 - guard)
    idle0 = sampler.window(idle0_t0 + guard, idle0_t1 - guard)
    idle1 = sampler.window(idle1_t0 + guard, idle1_t1 - guard)

    rec = {
        "n_iters": n_iters,
        "load_wall_s": load_wall,
        "t_iter_s": load_wall / n_iters,
        "probe_t_iter_s": t_iter,
        "n_samples_load": len(load),
        "n_samples_idle": len(idle0) + len(idle1),
        "busy_core_mhz_load": busy_core_mhz(load),
        "cpu_temp_max_c_load": max_temp_c(load, "cpu"),
        "cpu_temp_max_c_idle": max_temp_c(idle0 + idle1, "cpu"),
    }
    for rail in RAILS:
        p_load = mean_power_w(load, rail)
        p_i0 = mean_power_w(idle0, rail)
        p_i1 = mean_power_w(idle1, rail)
        idles = [p for p in (p_i0, p_i1) if p is not None]
        p_idle = sum(idles) / len(idles) if idles else None
        rec[f"{rail}_p_load_w"] = p_load
        rec[f"{rail}_p_idle_pre_w"] = p_i0
        rec[f"{rail}_p_idle_post_w"] = p_i1
        rec[f"{rail}_p_idle_w"] = p_idle
        if p_load is not None and p_idle is not None:
            p_dyn = p_load - p_idle
            rec[f"{rail}_p_dyn_w"] = p_dyn
            rec[f"{rail}_e_dyn_per_infer_j"] = p_dyn * load_wall / n_iters
            rec[f"{rail}_e_total_per_infer_j"] = p_load * load_wall / n_iters
        else:
            rec[f"{rail}_p_dyn_w"] = None
            rec[f"{rail}_e_dyn_per_infer_j"] = None
            rec[f"{rail}_e_total_per_infer_j"] = None
        rec[f"{rail}_e_trapz_load_j"] = trapezoid_energy_j(load, rail)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=fx_prefix.MODELS)
    ap.add_argument("--splits-per-model", type=int, default=25)
    ap.add_argument("--load-seconds", type=float, default=12.0)
    ap.add_argument("--idle-seconds", type=float, default=4.0)
    ap.add_argument("--min-iters", type=int, default=5)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--pin-core", type=int, default=5)
    ap.add_argument("--input-size", type=int, default=224)
    ap.add_argument("--profile-size", type=int, default=None,
                    help="Resolution for graph tracing / FLOP+D_cut profiling "
                         "(default: --input-size). Set small (e.g. 224) when "
                         "the measured resolution would OOM during profiling; "
                         "reported W and D_cut are rescaled to --input-size.")
    ap.add_argument("--probe-iters", type=int, default=3,
                    help="Timing-probe forwards before the load window. Lower "
                         "for very slow (high-resolution) prefixes.")
    ap.add_argument("--only-indices", type=int, nargs="+", default=None,
                    help="Measure exactly these split indices instead of the "
                         "auto-selected spread. Applied to every listed model.")
    ap.add_argument("--interval-ms", type=int, default=100)
    ap.add_argument("--pretrained", action="store_true",
                    help="use torchvision pretrained weights (downloads ~500MB)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    affinity = "unsupported"
    if hasattr(os, "sched_setaffinity"):
        if args.pin_core is not None and args.pin_core >= 0:
            os.sched_setaffinity(0, {args.pin_core})
        affinity = sorted(os.sched_getaffinity(0))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shape = (1, 3, args.input_size, args.input_size)
    # Profiling (ShapeProp + FLOP counting) runs full-resolution forwards that
    # retain intermediate tensors; at very high resolution that OOMs. Since
    # graph structure is resolution-independent and FLOPs / feature-map areas
    # scale exactly with input pixel count, profile at a small resolution and
    # rescale to the measured resolution. Measured energy is still metered at
    # the true --input-size.
    prof_size = args.profile_size or args.input_size
    pshape = (1, 3, prof_size, prof_size)
    scale = (args.input_size / prof_size) ** 2

    print(f"[setup] torch {torch.__version__} threads={torch.get_num_threads()} "
          f"affinity={affinity} input={shape} profile={pshape} scale={scale:.3f}",
          flush=True)

    graphs, splits, profile = {}, {}, {}
    for name in args.models:
        print(f"[trace] {name}", flush=True)
        weights = "DEFAULT" if args.pretrained else None
        gm = fx_prefix.build_traced(name, pshape, weights=weights)
        w_macs_prof = fx_prefix.cumulative_flops(gm, pshape)
        w_macs = [int(round(w * scale)) for w in w_macs_prof]
        valid = fx_prefix.valid_split_indices(gm)
        d_bits = {i: fx_prefix.d_cut_bits(gm, i, spatial_scale=scale)
                  for i in valid}
        d_full = [d_bits.get(i, 0) for i in range(len(w_macs))]
        picks, hull = select_splits(gm, w_macs, d_full, args.splits_per_model)
        if args.only_indices is not None:
            want = [i for i in args.only_indices if i in valid]
            missing = [i for i in args.only_indices if i not in valid]
            if missing:
                print(f"[trace] {name}: skipping invalid indices {missing}",
                      flush=True)
            picks = sorted(set(want))
        graphs[name] = gm
        splits[name] = picks
        profile[name] = {
            "n_nodes": len(fx_prefix.indexed_nodes(gm)),
            "n_valid_splits": len(valid),
            "hull_indices": hull,
            "measured_indices": picks,
            "W_macs": {str(i): w_macs[i] for i in picks},
            "W_gflops": {str(i): 2.0 * w_macs[i] / 1e9 for i in picks},
            "D_cut_bits": {str(i): d_full[i] for i in picks},
        }
        print(f"[trace] {name}: {len(fx_prefix.indexed_nodes(gm))} nodes, "
              f"{len(valid)} valid, hull={len(hull)}, measuring {len(picks)}", flush=True)

    meta = {
        "device": device_meta(),
        "args": vars(args),
        "profile": profile,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    jobs = [(r, m, k) for r in range(args.repeats) for m in args.models for k in splits[m]]
    rng = random.Random(args.seed)
    by_rep = {}
    for j in jobs:
        by_rep.setdefault(j[0], []).append(j)
    ordered = []
    for r in sorted(by_rep):
        block = by_rep[r][:]
        rng.shuffle(block)  # decorrelate thermal drift from W
        ordered.extend(block)

    if RailSampler.available():
        sampler = RailSampler(interval_ms=args.interval_ms)
    else:
        print("[warn] tegrastats not found: timing only, no power", flush=True)
        sampler = NullSampler()
    sampler.start()
    time.sleep(2.0)

    rec_path = out / "records.jsonl"
    t_start = time.monotonic()
    try:
        with rec_path.open("a") as fh:
            for n, (rep, model, k) in enumerate(ordered, 1):
                head, cut = fx_prefix.prefix_module(graphs[model], k)
                x = torch.randn(*shape)
                rec = measure(sampler, head, x, args.load_seconds,
                              args.idle_seconds, args.min_iters,
                              probe_iters=args.probe_iters)
                rec.update({
                    "repeat": rep,
                    "model": model,
                    "split_index": k,
                    "cut_producers": cut,
                    "W_macs": profile[model]["W_macs"][str(k)],
                    "W_gflops": profile[model]["W_gflops"][str(k)],
                    "D_cut_bits": profile[model]["D_cut_bits"][str(k)],
                    "wall_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                del head, x
                gc.collect()
                elapsed = time.monotonic() - t_start
                eta = elapsed / n * (len(ordered) - n)
                pdyn = rec["VDD_CPU_GPU_CV_p_dyn_w"]
                edyn = rec["VDD_CPU_GPU_CV_e_dyn_per_infer_j"]
                print(f"[{n}/{len(ordered)}] {model} k={k} rep={rep} "
                      f"W={rec['W_gflops']:.3f} GFLOP "
                      f"t={rec['t_iter_s'] * 1e3:.1f} ms "
                      f"Pdyn={'n/a' if pdyn is None else f'{pdyn:.3f} W'} "
                      f"E={'n/a' if edyn is None else f'{edyn:.4f} J'} "
                      f"f={rec['busy_core_mhz_load']} MHz "
                      f"| ETA {eta / 60:.0f} min", flush=True)
    finally:
        sampler.stop()

    print(f"[done] {rec_path}", flush=True)


if __name__ == "__main__":
    main()
