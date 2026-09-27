# STLT

This repository contains the artifact for **STLT: A Novel System for Energy-Aware
Distributed Inference in the Edge-Cloud-Space Continuum**. It provides the source
code, experiment configurations, and scripts to reproduce the main
candidate-analysis, delivery, and energy results.

The portable experiments use recorded model profiles and BUPT-1 telemetry to
reproduce the paper's trace-driven evaluation. Inference and communication
energy are calculated using the analytical model described in the paper.

<details>
<summary>Contents</summary>

- [What Is Reproduced](#what-is-reproduced)
- [Requirements](#requirements)
- [Setup](#setup)
- [Reproduce Paper Results](#reproduce-paper-results)
- [Validate Results](#validate-results)
- [Output Mapping](#output-mapping)
- [Execution Environment](#execution-environment)
- [Linux Environment with Docker](#linux-environment-with-docker)
- [Jetson Measurement Scripts](#jetson-measurement-scripts)
- [File Guide](#file-guide)
- [Source Packaging](#source-packaging)
- [Data and Citation](#data-and-citation)
- [Artifact Evaluation](#artifact-evaluation)
- [License](#license)
- [Contact](#contact)

</details>

## What Is Reproduced

The portable workflow recomputes split candidates, evaluates scheduling
policies, generates figures and tables, and validates the results. It covers
the numerical parameters of Table 1, Table 2, Figures 5–8, Table 4, and the main
delivery, energy, and candidate-selection statistics.

The five deep neural network (DNN) models are SqueezeNet1.1, Swin-V2-T,
EfficientNet-B4, ResNet50, and DenseNet169. Individual candidate-analysis plots
and a combined overview extend the representative Swin analysis in Figure 5.

Execution requires a standard computer. Jetson hardware is required only for
the optional device experiments.

## Requirements

| Component | Requirement |
| --- | --- |
| Runtime | Bash and Python 3.12 with `venv` and `pip` |
| Source tools | Git for packaging and its regression tests |
| Python packages | NumPy 2.2.4 and Matplotlib 3.10.0, with all runtime dependencies pinned in [requirements.txt](requirements.txt) |
| Processor | Standard CPU for sequential experiment execution |
| Memory | 2 GiB RAM recommended |
| Storage | At least 1 GiB for native setup, telemetry, and one output bundle, plus space for package caches or Docker images |
| Network | Required during dependency installation and telemetry download. Experiments run locally after setup. |

The portable workflow requires no GPU, pretrained weights, or administrator
access. Docker is optional. The telemetry archive is 77 MiB and is read
directly without extracting its 1.46 GiB CSV. A full output bundle occupies
approximately 13 MiB.

## Setup

Run the following commands from the repository root.

```bash
./scripts/create_env.sh
./scripts/check_env.sh
./scripts/download_data.sh
```

Setup creates `.stlt-venv` and installs the pinned dependencies. If installation
is interrupted, rerun the setup command to complete it. Set
`PYTHON=/path/to/python3.12` if Python 3.12 is not on `PATH`.

The environment check verifies dependencies, input hashes, candidate sets,
and unit and regression tests. The download script retrieves the telemetry
from a fixed upstream revision, verifies its SHA-256, and stores it in
`datasets/telemetry_all.csv.zip`.

## Reproduce Paper Results

Begin with the smoke test to check the environment and experiment execution.

```bash
./scripts/smoke_test.sh
```

The smoke test evaluates all 70 configurations on one complete telemetry
segment, generates the outputs, and validates 245 experiment rows. It writes
to `artifact-output/smoke/` and takes approximately five seconds after setup.
Successful validation produces the following status.

```text
Status: PASS (smoke)
```

After the smoke test passes, run the complete portable experiment.

```bash
./reproduce_paper_artifacts.sh
```

This command performs experiment execution, data processing, plotting, table
export, provenance recording, and validation. It evaluates 220 independent
five-orbit segments and writes to `artifact-output/full/`. Allow approximately
10 minutes on a recent laptop. Successful validation produces the following
status.

```text
Status: PASS (full)
```

The full run produces 29,700 main-experiment rows and 24,200 resource-sensitivity
rows. The smoke test checks execution and output consistency, while the full
run also compares the generated results with the complete paper reference.

Use `--archive` and `--output-dir` to select an existing telemetry archive or
a different output directory.

```bash
./reproduce_paper_artifacts.sh \
  --archive /path/to/telemetry_all.csv.zip \
  --output-dir /path/to/new-results
```

The output directory must be empty or absent, so use a new directory for each
rerun. Interrupted runs retain their partial outputs and fail validation.

### Experiment Configuration

`experiments/main.json` defines 15 model and workload configurations at nominal,
approximately 75%, and approximately 50% arrival rates for STLT, SLICE, TOBC,
TOGC, and RAND. `experiments/resource.json` defines 55 configurations for
evaluating the inference energy budget and downlink rate with STLT and SLICE.
Both workflows use the same configurations, with one telemetry segment for
the smoke test and all 220 segments for complete reproduction.

### Candidate Analysis

Candidate analysis can also run independently of telemetry replay.

```bash
./scripts/analyze_candidates.sh
./scripts/validate_results.sh --mode candidates
```

This command uses the recorded model profiles and requires only the Python
environment. It writes one CSV, PDF, and PNG per model, together with a combined
overview, to `artifact-output/candidates/`. The plots compare DNNSplit with
the offline analyzer ANODA and identify the pruned layers. The overview uses
separate axis limits for each model. These outputs are also included in the
smoke and full workflows.

## Validate Results

Reproduction commands validate their outputs automatically. The following
commands validate an existing full or smoke output bundle.

```bash
./scripts/validate_results.sh
./scripts/validate_results.sh --mode smoke
```

Use `--output-dir` to validate a full output bundle at a custom location.

```bash
./scripts/validate_results.sh --output-dir /path/to/new-results
```

Validation checks required files, experiment coverage, CSV schemas, numerical
values, task and energy accounting, and source and output hashes. It recomputes
aggregate results from the experiment rows and checks the exported tables.
Full validation also compares all Figure 7 and Figure 8 aggregate values with
the preserved paper reference, using an absolute tolerance of `1e-6` in each
field's native unit. Plot files are checked for structure and integrity.

Validation writes `validation_report.json` to the output directory and returns
exit code 1 for missing, incomplete, or inconsistent results. If the directory
does not exist, the validator reports the error without creating it.

Validate results with the source revision that produced them. Changes to
execution code, dependencies, or experiment inputs invalidate the provenance
check.

## Output Mapping

| Paper item | Generated output | Validation |
| --- | --- | --- |
| Table 1 (constants and workloads) | `table1_parameters.csv` | Parameters match the experiment configurations. |
| Table 2 (split candidates) | `table2_candidates.csv` | Candidate sets are recomputed from the recorded profiles. |
| Figure 5 (Swin candidate analysis) | `figure5.pdf`, `figure5_points.csv` | Coordinates match the candidate analysis. |
| Figure 6 (search-space reduction) | `figure6.pdf`, `figure6_reduction.csv` | Counts and reductions match the profile-derived candidate sets. |
| Figure 7 (energy and delivery) | `figure7.pdf`, `main-per-window.csv` | Full-run aggregates match the paper reference. |
| Figure 8 (resource sensitivity) | `figure8.pdf`, `resource-per-window.csv` | Full-run aggregates match the paper reference. |
| Table 4 (task outcomes) | `table4_task_outcomes.csv` | Task counts match the nominal-workload aggregates. |
| Numerical claims | `paper_claims.csv` | Comparisons and selection statistics match the computed aggregates. |
| Supplemental candidate analysis | `candidates-MODEL.csv`, `.pdf`, `.png` and `candidate-analysis.pdf`, `.png` | Coordinates and plot files cover all five models. |
| Aggregates and provenance | `paper-results.json`, `metadata.json`, `MANIFEST.md` | Results, execution scope, source hashes, and output hashes are checked. |
| Validation report | `validation_report.json` | Records individual checks and the final status. |

Matplotlib renders the figures from the generated numerical results, while
the CSV files retain unrounded values. Figure typography may differ from the
paper. The smoke test uses the same output names for its one-segment results.

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
plan, for which the numeric result fields are empty. RAND task counts may be
fractional because they are averaged across seeds. Figure 7 delivery error
bars represent one sample standard deviation.

## Execution Environment

The complete portable experiment takes approximately 10 minutes on an Apple
M4 Pro with Python 3.12. Execution time depends on the host system. The
following measurements exclude setup, telemetry download, and final validation.

| Environment | Python | Full-run time | Peak process memory through export |
| --- | --- | ---: | ---: |
| macOS 26.6.2, Apple M4 Pro, ARM64 | 3.12.9 | Approximately 10 minutes | Approximately 190 MiB |

Execution metadata and source hashes are retained in
[verification.json](docs/verification.json) and
[candidate-verification.json](docs/candidate-verification.json).
The [GitHub workflow](.github/workflows/portable.yml) defines environment checks
and smoke tests for Ubuntu 22.04 x86_64, with complete reproduction available
through manual selection.

## Linux Environment with Docker

The Docker environment provides the same setup, execution, and validation
commands as the native installation. The [Dockerfile](Dockerfile) pins Python
and the base image digest. After downloading the telemetry, build and run the
image from the repository root.

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
The build requires internet access, while experiment execution uses the
mounted telemetry with container networking disabled. The dataset mount is
read-only, and generated files are written to the host output directory.
On Linux, those files may be owned by the container user.

## Jetson Measurement Scripts

The `hardware/jetson/` directory contains supplementary measurement scripts
and recorded results for DNN prefix energy and controller overhead. Running
these experiments requires NVIDIA Jetson Orin Nano hardware. The measurements
associated with Figure 2, Table 3, and Figure 9 therefore use a separate
workflow from the automated portable reproduction.

<details>
<summary>Device requirements and recorded measurement settings</summary>

The recorded device is an NVIDIA Jetson Orin Nano Engineering Reference
Developer Kit Super, running L4T R36.4.4 and aarch64 Python 3.10.12. The
prefix-energy environment uses Torch 2.12.0+cpu and torchvision 0.27.0+cpu.
Device configuration requires administrator access, and power is sampled
with `tegrastats`.

| Setting | Prefix energy | Controller overhead |
| --- | --- | --- |
| Power mode | MAXN SUPER, identifier 2 | 25 W, identifier 1 |
| CPU | One Torch thread on core 5 at 1,497,600 kHz | Frequency setting not recorded |
| Power rail | `VDD_CPU_GPU_CV`, with `VDD_IN` and `VDD_SOC` also recorded | Whole-board `VDD_IN` |
| Sampling interval | 100 ms | 20 ms |
| Repetitions | Three randomized repeats per prefix | Five repeats, each lasting at least 20 s |
| Measurement window | 12 s load between two 4 s idle windows | Automatically repeated controller execution |
| Energy accounting | Dynamic energy after adjacent-idle subtraction | Gross and idle-subtracted dynamic energy |

The controller ANELA is measured using 850 seeded satellite states per
repetition with ALL, DNNSplit, and ANODA candidate sets. A separate scaling
experiment uses 5, 10, 20, 100, 500, and 1,000 candidates over ten synthetic
orbits with decisions every 60 s. Reported controller energy uses gross
`VDD_IN` measurements.

The recorded overhead configuration uses `gamma=2e-26`, `alpha=32`,
`beta=3.8e-7`, and `Rmax=10 Mbps`. Prefix measurements use 224 × 224 inputs,
whereas portable replay uses recorded 4096 × 4096 profiles. The device and
portable configurations are therefore recorded separately. Measurement CSV
files and metadata are retained in `hardware/jetson/reference-results/`.

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

Create the source package from a clean, committed working tree.

```bash
./scripts/package_artifact.sh
```

The command writes a source archive, SHA-256 checksum, and commit record to
`dist/`. It includes committed files and excludes virtual environments,
downloaded telemetry, generated results, and caches. The extracted archive
supports the same setup and reproduction commands as the repository.

Packaging uses `PYTHON` when set. Otherwise, it selects `.stlt-venv/bin/python`
or falls back to `python3.12`. The command preserves existing package files.

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

Retain the downloaded archive for offline use. Before execution, the simulator
verifies its digest and reads the recorded battery energy and solar generation.
Solar samples later in each segment provide the projected energy input for
admission decisions.

`data/model-profiles/` contains five recorded 4096 × 4096 TorchFX profiles.
Rows identify graph positions, valid splits, cumulative FLOPs, and deduplicated
live-tensor cuts. The float32 raw input contains
`3 × 4096 × 4096 × 32 = 1,610,612,736` bits.

The portable workflow reads the recorded profiles and configured energy
coefficients without repeating model profiling or device calibration. It
recomputes the experimental results, using `data/expected/paper-results.json`
and `data/reference-results/` as comparison records. Experiment configurations
preserve the evaluated precision of constants rounded in Table 1. Input and
configuration checksums are stored in `data/SHA256SUMS` and
`experiments/SHA256SUMS`.

</details>

## Artifact Evaluation

The requested badges are Artifacts Available, Artifacts Functional, and
Results Reproduced. The evaluation scope is the portable workflow described
above.

## License

STLT source code is distributed under the [MIT License](LICENSE).
Third-party telemetry and dependencies retain their respective terms.

## Contact

For questions about the software or reproduction procedures, contact the
authors at [a.stanisic@dsg.tuwien.ac.at](mailto:a.stanisic@dsg.tuwien.ac.at).
