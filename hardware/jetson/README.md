# Optional Jetson Orin Nano reruns

This directory is a preliminary, hardware-conditional bundle of the scripts
used for the paper's Jetson measurements. It is included to expose the executed
measurement code and make a future device rerun possible. It is not invoked by
the trace-driven `reproduce_paper_artifacts.sh` workflow, and the absence of a
Jetson does not prevent reproduction of Figures 7 and 8.

The bundle exposes two measurement modules:

- `prefix_energy/` executes DNN prefixes on one Cortex-A78AE CPU core and
  samples individual power rails. It supports the computation-energy
  calibration evidence.
- `overhead/` measures ANELA over the ALL, DNNSplit, and ANODA candidate sets
  and over synthetic candidate-set sizes. It supports Table 3 and Figure 9.

The overhead module intentionally includes the exact historical ANELA
implementation used by the recorded device harness. The declarative model
profiles are read from `../../data/model-profiles/`; they are not duplicated.
The clean simulator uses `src/stlt_artifact/` and remains the authoritative
implementation for Figures 7 and 8.

## Recorded device conditions

The included metadata records an NVIDIA Jetson Orin Nano Engineering Reference
Developer Kit Super running aarch64 Python 3.10.12.

### Prefix-energy run

- CPU execution only; one Torch thread pinned to core 5.
- CPU frequency fixed at 1,497,600 kHz.
- Recorded power mode: `pmode:0002` (MAXN SUPER).
- Primary rail: `VDD_CPU_GPU_CV`; `VDD_IN` and `VDD_SOC` were also sampled.
- Sampling interval: 100 ms.
- Three randomized repeats per prefix.
- Each measured load targets 12 s and is bracketed by 4 s idle windows.
- Reported dynamic energy subtracts the adjacent idle baseline.
- Recorded software: Python 3.10.12, Torch 2.12.0+cpu, torchvision
  0.27.0+cpu, L4T R36.4.4.

### Controller-overhead runs

- Recorded power mode: 25 W, mode identifier 1.
- Rail: whole-board `VDD_IN` as reported by `tegrastats`.
- Sampling interval: 20 ms.
- Five repetitions, each automatically repeated to last at least 20 s.
- Candidate-set experiment: 850 seeded satellite states per repetition.
- Scaling experiment: candidate counts 5, 10, 20, 100, 500, and 1,000;
  ten synthetic orbits with a 60 s decision interval.
- Gross and idle-subtracted dynamic energy are both recorded. The paper's
  reported per-decision energy follows the gross `VDD_IN` field.

The saved overhead metadata does **not** establish that CPU frequency was
pinned for those historical runs. Do not describe those runs as
frequency-pinned. `setup_device.sh` provides an optional fixed-frequency setup
for a new controlled rerun; using it creates a new protocol variant that must
be reported as such.

The historical overhead scripts also embed the earlier analytical constants
(`gamma=2e-26`, `alpha=32`, `beta=3.8e-7`, and `Rmax=10 Mbps`). These constants
are preserved because they describe the recorded device run; they are not the
formula-aligned constants used by the current Figures 7 and 8. A final hardware
rerun should reconcile this configuration before replacing the reference data.

## Device setup

Copy or clone the complete STLT artifact onto the Jetson. From this directory:

```bash
./setup_python_env.sh
sudo ./setup_device.sh status
sudo ./setup_device.sh pin
```

`setup_device.sh pin` saves the current power mode, governor, frequency range,
and fan state before selecting MAXN SUPER, the userspace governor, 1,497,600
kHz, and maximum fan cooling. Always restore the device after measurements:

```bash
sudo ./setup_device.sh restore
```

## Running measurements

```bash
./run_on_device.sh prefix-energy
./run_on_device.sh analyze-prefix results/prefix-energy/<run-id>
./run_on_device.sh candidate-sets
./run_on_device.sh scaling
```

Additional arguments are passed to the underlying Python program. Use `--help`
on the corresponding program for smoke-test controls such as fewer models,
runs, states, or candidate counts. Outputs default to `hardware/jetson/results/`
and are ignored by Git.

## Important scope note

The recorded prefix dataset uses 224 x 224 execution and supplies calibration
evidence for the analytical computation model. It is not a direct hardware
measurement of every 4096 x 4096 workload used by the trace-driven evaluation.
Any paper or artifact description must preserve this distinction.

`reference-results/` contains compact metadata, run-level CSV files, and
summaries from the existing device sessions. The 14 September search-space run
matches the points currently plotted in Figure 9. The direct candidate-set run
is supporting evidence but does not numerically reproduce every cell of the
current Table 3; that table/source mismatch remains to be reconciled before a
final artifact release.
