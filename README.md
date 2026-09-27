# STLT

This repository contains the artifact for **STLT: A Novel System for Energy-Aware
Distributed Inference in the Edge-Cloud-Space Continuum**. It provides the source
code, experiment configurations, and scripts to reproduce the main
candidate-analysis, delivery, and energy results.

The portable experiments use recorded model profiles and BUPT-1 telemetry to
reproduce the paper's trace-driven evaluation. Inference and communication
energy are calculated using the analytical model described in the paper.

[Setup](#setup) · [Reproduction](#reproduce-paper-results) ·
[Outputs](#output-mapping) · [Jetson experiments](#optional-jetson-experiments)

## What Is Reproduced

The portable workflow recomputes split candidates, evaluates scheduling
policies, generates figures and tables, and validates the results. It covers
the numerical parameters of Table 1, Table 2, Figures 5–8, Table 4, and the main
delivery, energy, and candidate-selection statistics.

The five models are SqueezeNet1.1, Swin-V2-T, EfficientNet-B4, ResNet50, and
DenseNet169. Individual candidate-analysis plots and a combined overview extend
the representative Swin analysis in Figure 5.

Execution requires a standard computer. Jetson hardware is required only for
the optional device experiments.

## Requirements

| Component | Requirement |
| --- | --- |
| Runtime | Bash and Python 3.12 with `venv` and `pip` |
| Python packages | NumPy 2.2.4 and Matplotlib 3.10.0; all runtime dependencies are pinned in [requirements.txt](requirements.txt) |
| Processor | Standard CPU; experiments execute sequentially |
| Memory | 2 GiB RAM recommended |
| Storage | At least 1 GiB for native setup, telemetry, and one output bundle; additional space for package caches or Docker images |
| Network | Required for dependency installation and telemetry download; execution is local after setup |

The portable workflow requires no GPU, pretrained weights, or administrator
access. Docker is optional. The telemetry archive is 77 MiB and is read
directly without extracting its 1.46 GiB CSV. A full output bundle occupies
approximately 13 MiB.

## Setup

Run from the repository root:

```bash
./scripts/create_env.sh
./scripts/check_env.sh
./scripts/download_data.sh
```

Setup creates `.stlt-venv` and installs the pinned dependencies. Rerun it to
complete an interrupted installation. Set `PYTHON=/path/to/python3.12` if
Python 3.12 is not on `PATH`.

The environment check verifies dependencies, input hashes, candidate sets,
and unit and regression tests. The download script retrieves the telemetry
from a fixed upstream revision, verifies its SHA-256, and stores it in
`datasets/telemetry_all.csv.zip`.

## Reproduce Paper Results

First, run the short functional check:

```bash
./scripts/smoke_test.sh
```

The smoke test evaluates all 70 configurations on one complete telemetry
segment, generates the outputs, and validates 245 experiment rows. It writes
to `artifact-output/smoke/` and takes approximately five seconds after setup.
Successful validation prints:

```text
Status: PASS (smoke)
```

Run the complete portable experiment:

```bash
./reproduce_paper_artifacts.sh
```

This command performs experiment execution, data processing, plotting, table
export, provenance recording, and validation. It evaluates 220 independent
five-orbit segments and writes to `artifact-output/full/`. Allow approximately
10 minutes on a recent laptop. Successful validation prints:

```text
Status: PASS (full)
```

The full run produces 29,700 main-experiment rows and 24,200 resource-sensitivity
rows. The smoke test checks execution and output consistency; comparison with
the complete paper results requires the full run.

To use an existing telemetry archive or a different output directory:

```bash
./reproduce_paper_artifacts.sh \
  --archive /path/to/telemetry_all.csv.zip \
  --output-dir /path/to/new-results
```

The output directory must be empty or absent. Use a new directory for each
rerun. Interrupted runs retain their partial outputs and fail validation.

### Candidate Analysis

To generate candidate-analysis plots independently of telemetry replay:

```bash
./scripts/analyze_candidates.sh
./scripts/validate_results.sh --mode candidates
```

This requires the Python environment but no telemetry download. Outputs are
written to `artifact-output/candidates/`: one CSV, PDF, and PNG per model, plus
a combined overview. The plots compare DNNSplit and ANODA candidates and
identify the pruned layers. The overview uses separate axis limits for each
model. These outputs are also included in the smoke and full workflows.

## Validate Results

Reproduction commands validate their outputs automatically. To validate an
existing full or smoke bundle:

```bash
./scripts/validate_results.sh
./scripts/validate_results.sh --mode smoke
```

For a full bundle at a custom location:

```bash
./scripts/validate_results.sh --output-dir /path/to/new-results
```

Validation checks required files, experiment coverage, CSV schemas, numerical
values, task and energy accounting, and source and output hashes. It recomputes
aggregate results from the experiment rows and checks the exported tables.
Full validation also compares all Figure 7 and Figure 8 aggregate values with
the preserved paper reference, using an absolute tolerance of `1e-6` in each
field's native unit. Plot files are checked for structure and integrity.

The report is stored as `validation_report.json` in the output directory.
Missing, incomplete, or inconsistent results return exit code 1. A missing
directory is reported on the terminal without creating it.

Validate results with the source revision that produced them. Changes to
execution code, dependencies, or experiment inputs invalidate the provenance
check.

## Output Mapping

| Paper item | Generated output | Validation |
| --- | --- | --- |
| Table 1: constants and workloads | `table1_parameters.csv` | Parameters match the experiment configurations. |
| Table 2: split candidates | `table2_candidates.csv` | Candidate sets are recomputed from the recorded profiles. |
| Figure 5: Swin candidate analysis | `figure5.pdf`, `figure5_points.csv` | Coordinates match the candidate analysis; ANODA removes layer 271. |
| Figure 6: search-space reduction | `figure6.pdf`, `figure6_reduction.csv` | Counts and reductions match the profile-derived candidate sets. |
| Figure 7: energy and delivery | `figure7.pdf`, `main-per-window.csv` | Full-run aggregates match the paper reference. |
| Figure 8: resource sensitivity | `figure8.pdf`, `resource-per-window.csv` | Full-run aggregates match the paper reference. |
| Table 4: task outcomes | `table4_task_outcomes.csv` | Task counts match the nominal-workload aggregates. |
| Numerical claims | `paper_claims.csv` | Comparisons and selection statistics match the computed aggregates. |
| Supplemental candidate analysis | `candidates-MODEL.csv`, `.pdf`, `.png`; `candidate-analysis.pdf`, `.png` | Coordinates and plot files cover all five models. |
| Aggregates and provenance | `paper-results.json`, `metadata.json`, `MANIFEST.md` | Results, execution scope, source hashes, and output hashes are checked. |
| Validation report | `validation_report.json` | Records individual checks and the final status. |

Matplotlib renders the figures from the generated numerical results. Typography
may differ from the paper; CSV files retain unrounded values. The smoke test
uses the same output names for its one-segment results.

### Expected Results

| Quantity | Full-run value |
| --- | ---: |
| Nominal tasks offered per policy | 277,200 |
| STLT deliveries | 256,778 |
| SLICE deliveries | 230,426 |
| STLT delivery increase over SLICE | 11.4362% |
| STLT modeled energy reduction relative to SLICE | 8.7768% |
| Mean candidate reduction relative to DNNSplit | 30.7143% |
| STLT admissions using the minimum-energy split | 39.3433% |

In the CSV files, `admitted` denotes an STLT admission or a baseline computation
start. `admitted_not_delivered` counts started tasks that do not reach the
ground. `NF` identifies a SLICE configuration with no feasible complete-workload
plan; its result fields are empty. RAND task counts may be fractional because
they are averaged across seeds. Figure 7 delivery error bars represent one
sample standard deviation.

<details>
<summary>Experiment configuration and interpretation</summary>

`experiments/main.json` defines 15 model/workload configurations at nominal,
approximately 75%, and approximately 50% arrival rates. It evaluates STLT,
SLICE, TOBC, TOGC, and RAND. `experiments/resource.json` defines 55 EO-budget
and downlink-rate configurations for STLT and SLICE. Both workflows use these
same configurations; the smoke test selects one segment and the full run
selects 220. SLICE plans are recomputed and checked against the saved plans
before replay.

Each segment contains five orbit cycles, each with 5,100 s of computation and
300 s of ground contact. Task arrivals restart each cycle at the configured
arrival interval, yielding `floor(computation_s / interval_s)` tasks per cycle.
Tasks must be delivered during the next contact; no cross-cycle queue is
retained. The EO budget is the share of satellite energy allocated to inference
and downlink. Committed energy includes computation and communication already
spent and communication reserved for queued outputs.

ANODA retains the lower convex hull of the DNNSplit running-payload-minimum
candidates after invalid graph cuts are removed. ANELA selects or rejects a
split for each arriving task. When the remaining EO budget does not exceed
the maximum downlink energy of the remaining contacts, it evaluates only the
minimum-energy candidate. This restriction does not establish that all other
candidates are infeasible. The contact-energy projection restores queued
communication reservations before checking the queued transmission demand.

SLICE uses the evaluated two-node fixed-split planner. During replay, a task
starts when its computation fits the current EO margin; future communication
energy is not reserved. Its replay is separate from the Table 3 overhead
benchmark.

The replay uses recorded solar generation as a perfect forecast. The paper's
descriptive 0–50 W range is not imposed as a limit. Forecast error, radio
protocol overhead, and application accuracy are outside the simulation model.
RAND uses seeds 7, 19, 42, 73, and 101; delivery rates are averaged within each
segment before calculating the sample standard deviation across segments.
Figure 7 uses a logarithmic energy axis. Figure 6 normalizes candidate counts
by all graph positions.

</details>

## Verified Platforms

| Environment | Python | Full-run time | Peak process memory through export |
| --- | --- | ---: | ---: |
| macOS 26.6.2, Apple M4 Pro, ARM64, current portable source | 3.12.9 | 619.1 s | 189.9 MiB |
| macOS 26.6.2, Apple M4 Pro, ARM64, revision `48ba0a8` | 3.12.9 | 618.4 s | 171.2 MiB |
| Debian Bookworm container, ARM64, revision `48ba0a8`, Docker Desktop on the same host | 3.12.9 | 602.8 s | 131.8 MiB |

The current portable source passed 202 full validation checks. Its execution
and test hashes are recorded in [verification.json](docs/verification.json),
together with the earlier full runs at revision `48ba0a8`. Times exclude setup,
download, and final validation. Earlier standalone candidate and smoke
verification is recorded in
[candidate-verification.json](docs/candidate-verification.json).

<details>
<summary>Verification procedure and scope</summary>

The native host has 24 GiB RAM. The Linux container was built from a clean
Python 3.12.9 image and executed with networking disabled and telemetry mounted
read-only. Each earlier full run passed 150 checks and included 2,640 infeasible SLICE
rows in the resource experiment. Both used identical execution and input hashes.
The measurements describe two environments on one host, not independent
hardware benchmarks. Peak memory is measured before final validation.

The source archive from `48ba0a8` was extracted into a new directory. Setup,
27 tests, and the smoke run passed; smoke validation passed 148 checks in
3.672 s of execution. The archive contained 193,320 bytes.

The all-model plotting extension passed 30 tests, 155 candidate checks, and
200 smoke checks. Its Figure 5 coordinates matched the earlier output exactly.
Candidate execution took 1.259 s and smoke execution took 4.275 s. Plot layouts
were inspected visually. These runs did not repeat the full replay or verify
profile generation, device calibration, or hardware measurements.

Regression tests cover schedules, candidate extraction, saved SLICE plans,
policy decisions, telemetry gaps, energy reservations, validation, and source
packaging. Missing files, incomplete or duplicate rows, inconsistent attempt
counts, malformed metadata, non-finite values, wrong seeds, inconsistent
aggregates, interrupted runs, and altered hashes fail validation. Full
validation rejects smoke bundles.

After portable validation and packaging corrections on 27 September 2026,
all 45 tests and 97 input checks passed. The smoke run passed 200 checks in
4.26 s; the full run passed 202 checks in 619.1 s. All 53,900 experiment rows
and eight numerical CSV files shared with the earlier full run were
byte-identical. The complete results summary was unchanged. Packaging was
verified in isolated Git repositories; the release archive remains to be
built from the reviewed, committed source.

</details>

The [GitHub workflow](.github/workflows/portable.yml) defines setup and smoke
checks for Ubuntu 22.04 x86_64, with full reproduction available by manual
selection. That platform has not yet been verified.

## Optional Linux Container

The [Dockerfile](Dockerfile) pins Python and the base image digest. After
downloading the telemetry, build and run from the repository root:

```bash
docker build -t stlt-artifact:portable .
mkdir -p artifact-output
docker run --rm --network none \
  --mount type=bind,source="$PWD/datasets",target=/artifact/datasets,readonly \
  --mount type=bind,source="$PWD/artifact-output",target=/artifact/artifact-output \
  stlt-artifact:portable ./reproduce_paper_artifacts.sh \
  --output-dir /artifact/artifact-output/linux-full
```

For a short check, replace the final command and its argument with
`./scripts/smoke_test.sh --output-dir /artifact/artifact-output/linux-smoke`.
The build requires internet access; experiment execution disables container
networking. On Linux, output files may be owned by the container user.

## Optional Jetson Experiments

`hardware/jetson/` contains device experiments for DNN prefix energy and ANELA
execution overhead. They are independent of portable reproduction. Figure 2,
Table 3, and Figure 9 remain outside the verified reproduction workflow;
verification of their measurement procedures and generating records is pending.
Figures 1, 3, and 4 are explanatory diagrams.

<details>
<summary>Device requirements and recorded measurement protocols</summary>

The recorded device is an NVIDIA Jetson Orin Nano Engineering Reference
Developer Kit Super, running L4T R36.4.4 and aarch64 Python 3.10.12. The
prefix-energy record lists Torch 2.12.0+cpu and torchvision 0.27.0+cpu. Device
configuration requires administrator access; power measurement uses
`tegrastats`.

| Setting | Prefix energy | Controller overhead |
| --- | --- | --- |
| Power mode | MAXN SUPER, identifier 2 | 25 W, identifier 1 |
| CPU | One Torch thread on core 5 at 1,497,600 kHz | Historical frequency pinning is not established |
| Power rail | `VDD_CPU_GPU_CV`, with `VDD_IN` and `VDD_SOC` also recorded | Whole-board `VDD_IN` |
| Sampling interval | 100 ms | 20 ms |
| Repetitions | Three randomized repeats per prefix | Five repeats, each lasting at least 20 s |
| Measurement window | 12 s load between two 4 s idle windows | Automatically repeated controller execution |
| Energy accounting | Dynamic energy after adjacent-idle subtraction | Gross and idle-subtracted dynamic energy |

The candidate-set experiment uses 850 seeded satellite states per repetition
and compares ALL, DNNSplit, and ANODA sets. The scaling experiment uses 5, 10,
20, 100, 500, and 1,000 candidates over ten synthetic orbits with 60 s decisions.
Reported controller energy uses gross `VDD_IN` measurements.

The preserved overhead implementation uses earlier constants:
`gamma=2e-26`, `alpha=32`, `beta=3.8e-7`, and `Rmax=10 Mbps`. These differ from
the portable evaluation configuration. Prefix measurements use 224 × 224
inputs, whereas portable replay uses recorded 4096 × 4096 profiles. These
protocol differences require reconciliation before claiming hardware
reproduction of the paper results.

Recorded CSV files and metadata are retained in
`hardware/jetson/reference-results/`. The 14 September scaling run corresponds
to the recorded Figure 9 points. The direct candidate-set measurements do not
reproduce every Table 3 cell; the separate SLICE benchmark also requires
verification. Device records are evidence of earlier execution, not a verified
rerun of the current artifact.

</details>

<details>
<summary>Device setup and measurement commands</summary>

Copy or clone the complete repository onto the Jetson. From the repository
root:

```bash
cd hardware/jetson
./setup_python_env.sh
sudo ./setup_device.sh status
sudo ./setup_device.sh pin
```

The pin command saves the current power mode, governor, frequency range, and
fan state, then selects MAXN SUPER, the userspace governor, 1,497,600 kHz, and
maximum fan cooling. This produces a new protocol variant for overhead runs
whose historical frequency setting was not recorded.

Run the required measurements from `hardware/jetson/`:

```bash
./run_on_device.sh prefix-energy
./run_on_device.sh analyze-prefix results/prefix-energy/RUN_ID
./run_on_device.sh candidate-sets
./run_on_device.sh scaling
```

Replace `RUN_ID` with the directory created by the prefix-energy command.
Additional arguments are passed to the underlying Python program; its `--help`
lists controls for models, repetitions, states, and candidate counts. Outputs
are written under `hardware/jetson/results/` and excluded from version control.
The analysis command remains subject to the pending hardware-workflow review.

Restore the device configuration after measurement, including after a failed
run:

```bash
sudo ./setup_device.sh restore
```

</details>

## File Guide

| Path | Purpose |
| --- | --- |
| `reproduce_paper_artifacts.sh` | Complete portable reproduction and validation |
| `scripts/create_env.sh`, `scripts/check_env.sh` | Environment setup and checks |
| `scripts/download_data.sh` | Telemetry acquisition and integrity verification |
| `scripts/smoke_test.sh` | One-segment functional check |
| `scripts/analyze_candidates.sh` | Independent candidate analysis |
| `scripts/validate_results.sh` | Existing-result validation |
| `scripts/package_artifact.sh` | Source archive, checksum, and commit record |
| `src/stlt_artifact/` | Profiles, planning, policies, replay, exports, and validation |
| `experiments/main.json`, `experiments/resource.json` | Main and resource-sensitivity configurations |
| `data/` | Recorded profiles, reference results, and provenance |
| `tests/` | Scientific interface and validation regression tests |
| `hardware/jetson/` | Device measurement scripts and recorded results |
| `docs/` | Machine-readable verification records |

## Source Packaging

From a clean, committed working tree:

```bash
./scripts/package_artifact.sh
```

The command writes a source archive, SHA-256 checksum, and commit record to
`dist/`. It includes committed files and excludes virtual environments,
downloaded telemetry, generated results, and caches. The extracted archive
supports the same setup and reproduction commands as the repository.

Packaging uses `PYTHON` when set, then `.stlt-venv/bin/python`, then
`python3.12`. Existing package files are preserved. The archive and its records
are prepared in a temporary directory before publication.

## Data and Citation

The BUPT-1 telemetry is provided by Xing et al. in
[Deciphering the Enigma of Satellite Computing with COTS Devices: Measurement
and Analysis](https://doi.org/10.1145/3636534.3649371), ACM MobiCom 2024,
pp. 420–435.

The download script retrieves the archive from the authors'
[dataset repository](https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS).
The telemetry is acquired separately and is not included in the source archive.
No explicit dataset licence was found at the evaluated upstream revision.

<details>
<summary>Input provenance and telemetry checksum</summary>

| Property | Value |
| --- | --- |
| Upstream commit | `951b41521351d535b7c2354916d9c4991602e8c7` |
| Archive path | `CommonData-Telemetries/telemetry_all.csv.zip` |
| SHA-256 | `5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa` |
| Raw rows | 10,117,299 |
| Selected segments | 220 non-overlapping, gap-free segments of 27,000 s |
| Selected rows | 5,940,000 (58.71%) |

The replay checks the archive digest before execution. Retain the downloaded
archive for offline use.

`data/model-profiles/` contains five recorded 4096 × 4096 TorchFX profiles.
Rows identify graph positions, valid splits, cumulative FLOPs, and deduplicated
live-tensor cuts. The float32 raw input contains
`3 × 4096 × 4096 × 32 = 1,610,612,736` bits. Swin-V2-T includes attention
computation that was absent from the earlier profile.

Profile generation and energy calibration are not rerun by the portable
workflow. `data/expected/paper-results.json` and `data/reference-results/`
provide comparison values; the simulator recomputes experimental results.
Experiment configurations preserve the evaluated precision of constants rounded
in Table 1. Input and configuration checksums are stored in `data/SHA256SUMS`
and `experiments/SHA256SUMS`.

</details>

<details>
<summary>Telemetry citation (BibTeX)</summary>

```bibtex
@inproceedings{10.1145/3636534.3649371,
  author = {Xing, Ruolin and Xu, Mengwei and Zhou, Ao and Li, Qing and
            Zhang, Yiran and Qian, Feng and Wang, Shangguang},
  title = {Deciphering the Enigma of Satellite Computing with COTS Devices:
           Measurement and Analysis},
  year = {2024},
  booktitle = {Proceedings of the 30th Annual International Conference on
               Mobile Computing and Networking},
  pages = {420--435},
  publisher = {Association for Computing Machinery},
  address = {New York, NY, USA},
  doi = {10.1145/3636534.3649371},
  url = {https://doi.org/10.1145/3636534.3649371},
  series = {ACM MobiCom '24}
}
```

</details>

## Artifact Evaluation

Requested badges: Artifacts Available, Artifacts Functional, and Results
Reproduced. The evaluation scope is the portable workflow described above.

## License

STLT source code is distributed under the [MIT License](LICENSE). This licence
does not apply to third-party telemetry or dependencies; their respective
terms apply.

## Contact

For questions about the software or reproduction procedures, contact the
authors at [a.stanisic@dsg.tuwien.ac.at](mailto:a.stanisic@dsg.tuwien.ac.at).
