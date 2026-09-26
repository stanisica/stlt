# STLT artifact

This repository contains the artifact for **STLT: A Novel System for Energy-Aware
Distributed Inference in the Edge-Cloud-Space Continuum**. The portable workflow
reproduces the offline candidate analysis and the main trace-driven simulation.
It uses the five recorded DNN profiles and the BUPT-1 telemetry archive.

The workflow runs on a standard computer. It requires no VPN, Jetson, GPU,
pretrained weights, or administrator access. Internet access is required for
initial dependency installation and telemetry download. Execution is local
after setup.

The target badges are **Artifacts Available**, **Artifacts Functional**, and
**Results Reproduced**, with the scope stated below. These are submission
targets, not awarded badges. See [OVERVIEW.md](OVERVIEW.md) for the evaluation
scope and [docs/ARTIFACT_RULES.md](docs/ARTIFACT_RULES.md) for the release checklist.

## Requirements

- Bash and Python 3.12 with `venv` and `pip`.
- NumPy and Matplotlib, with runtime dependencies pinned in `requirements.txt`.
- A working directory with at least 1 GiB of free space for native setup,
  telemetry, and one output bundle. Allow additional space for package caches
  or Docker images.
- A standard CPU. The experiments execute sequentially.
- 2 GiB RAM is recommended. Measured process memory is recorded below.

The telemetry ZIP is 77 MiB. It is read directly; its 1.46 GiB CSV does not need
to be extracted. A complete output bundle is approximately 13 MiB.
See [docs/VERIFICATION.md](docs/VERIFICATION.md) for tested platforms and measured
resource use. Docker is optional.

## Setup

Run these commands from the repository root:

```bash
./scripts/create_env.sh
./scripts/check_env.sh
./scripts/download_data.sh
```

Setup creates `.stlt-venv` and installs the pinned dependencies. It can be rerun
to complete an interrupted installation. Set `PYTHON=/path/to/python3.12` if
Python 3.12 is not on `PATH`.

The environment check verifies dependencies, input hashes, candidate sets, and
the unit and regression tests. It does not claim to reproduce paper results.

The download command obtains the telemetry from a fixed upstream commit and
checks its SHA-256. It stores the archive in `datasets/telemetry_all.csv.zip`.
An existing archive can be used directly with `--archive /path/to/telemetry_all.csv.zip`.
See [data/README.md](data/README.md) for provenance and distribution limits.

## Quick functional check

To inspect candidate pruning for all five models without downloading telemetry:

```bash
./scripts/analyze_candidates.sh
```

This writes `artifact-output/candidates/` with one CSV, PDF, and PNG per model,
plus `candidate-analysis.pdf` and `candidate-analysis.png` as a combined overview.
Each plot compares DNNSplit with ANODA and lists the pruned layers. Overlapping
candidates use distinct markers. SqueezeNet1.1 has no additional ANODA pruning.
The overview uses independent axis limits for each model.

These are supplemental analyses from the recorded profiles. The Swin plot
remains the paper's Figure 5. The smoke and full workflows also generate all
supplemental plots automatically. Candidate analysis requires setup but no
telemetry, VPN, or Jetson. To validate its outputs separately:

```bash
./scripts/validate_results.sh --mode candidates
```

To exercise the telemetry replay as well:

```bash
./scripts/smoke_test.sh
```

This runs all 70 configurations on the first complete telemetry segment. It
generates the tables and four plots, then validates 245 experiment rows. The
output directory is `artifact-output/smoke/`. Expect a few seconds after setup.

The final status must be `PASS (smoke)`. This checks execution, output structure,
and accounting. It does not establish agreement with the full paper totals.
The generated manifest identifies the one-segment scope.

## Full portable reproduction

```bash
./reproduce_paper_artifacts.sh
```

The command runs the full experiment, processes the data, renders the plots,
exports the tables, records provenance, and validates the results. It evaluates
220 independent five-orbit segments. The main suite uses 15 workload settings
and nine policy/seed combinations. The resource suite uses 55 settings and two
policies. The two CSV files contain 29,700 and 24,200 rows, respectively.

Outputs are written to `artifact-output/full/`. Allow approximately 10 minutes
on a recent laptop; runtime depends on the computer. Progress is printed after
the first segment and every ten segments. A complete run ends with `PASS (full)`.

For an existing archive or a different destination:

```bash
./reproduce_paper_artifacts.sh \
  --archive /path/to/telemetry_all.csv.zip \
  --output-dir /path/to/new-results
```

The destination must be empty or absent. A run refuses to overwrite an existing
bundle. Choose a new destination for a rerun. Interrupted runs retain their
partial files and cannot pass validation.

## Validate existing results

```bash
./scripts/validate_results.sh
./scripts/validate_results.sh --mode smoke
./scripts/validate_results.sh --output-dir /path/to/new-results
```

Validation checks required files, exact experiment coverage, CSV schemas,
configuration values, finite nonnegative results, task and energy accounting,
layer-selection counts, and source and output hashes. It recomputes summaries
from the per-window CSV files and checks the derived tables. Full validation
also compares all Figure 7 and Figure 8 numerical values with the preserved
paper oracle, using an absolute tolerance of `1e-6` in each field's native unit.
PDF files are checked for basic structure and manifest integrity; their bytes
are not compared with the paper PDFs.

Validate a bundle with the source revision that produced it. Changes to source,
scripts, dependencies, or experiment inputs invalidate its provenance check.
Use a new output directory when reproducing results from a changed revision.

Missing or incomplete results return exit code 1. The report is written to
`validation_report.json` when the output directory exists. A missing directory
is reported on the terminal and is not created. Input checks, smoke validation,
and full validation are distinct operations.

## Paper-to-output map

| Paper item | Generated files | Interpretation |
| --- | --- | --- |
| Table 1: constants and workloads | `table1_parameters.csv` | Exact simulation constants and nominal workloads. Solar power comes from the telemetry; the paper's descriptive 0–50 W range is not imposed as a simulation limit. |
| Table 2: split candidates | `table2_candidates.csv` | DNNSplit and ANODA sets recomputed from the recorded profiles. |
| Figure 5: Swin candidate plane | `figure5.pdf`, `figure5_points.csv` | ANODA removes layer 271 from the DNNSplit set. |
| Supplemental candidate planes: all models | `candidates-MODEL.csv`, `.pdf`, `.png`; `candidate-analysis.pdf`, `.png` | Candidate coordinates, individual plots, and a combined overview. These extend the paper's representative Swin analysis. |
| Figure 6: search-space reduction | `figure6.pdf`, `figure6_reduction.csv` | Candidate counts and reductions, normalized by all graph positions as in the paper. |
| Figure 7: energy and delivery | `figure7.pdf`, `main-per-window.csv` | Nominal workloads; logarithmic energy axis; delivery whiskers show one sample standard deviation. |
| Figure 8: resource sensitivity | `figure8.pdf`, `resource-per-window.csv` | Mean deliveries for the EO-budget and downlink-rate sweeps. |
| Table 4: task outcomes | `table4_task_outcomes.csv` | Offered, started, delivered, and undelivered tasks under nominal workloads. |
| Numerical claims | `paper_claims.csv` | Aggregate delivery and energy comparisons and candidate-selection statistics. |
| Aggregates and provenance | `paper-results.json`, `metadata.json`, `MANIFEST.md` | Aggregate values, source/input/output hashes, environment, runtime, and output mapping. |

The plots reproduce the numerical results with Matplotlib. Their typography
and layout may differ from the paper. The CSV files retain unrounded values.

Expected results for the full run:

| Quantity | Expected value |
| --- | ---: |
| Nominal tasks offered per policy | 277,200 |
| STLT deliveries | 256,778 |
| SLICE deliveries | 230,426 |
| STLT delivery increase | 11.4362% |
| STLT modeled energy reduction | 8.7768% |
| Mean candidate reduction relative to DNNSplit | 30.7143% |
| STLT admissions using the minimum-energy split | 39.3433% |

## Interpretation and limits

Each replay window is an independent 27,000 s segment with five orbit cycles.
Task arrivals restart in each computation phase. Tasks must be delivered in
the next contact window. `admitted` means STLT admission or a baseline
computation start. `admitted_not_delivered` counts started tasks that do not
reach the ground. `NF` means SLICE has no feasible complete-workload plan;
its result fields are empty, not zero.

RAND uses seeds 7, 19, 42, 73, and 101. RAND delivery rates are averaged within
each segment before the standard deviation across segments is calculated.
RAND aggregate task counts can therefore be fractional.

Energy is simulated from cumulative FLOPs and transmitted bits. It is not a
new physical power measurement. The replay uses recorded solar generation as
a perfect forecast. It does not test forecast error, radio protocol overhead,
cross-cycle queues, or application accuracy. SLICE uses the evaluated
two-node fixed-split specialization; this runner is not the branch-and-bound
overhead benchmark from Table 3.

This phase does not reproduce Figure 2, Table 3, or Figure 9. Those results
require measurement-protocol and provenance work. Their exclusion does not
prevent evaluating the candidate analysis or the main simulated delivery and
energy claims. Figures 1, 3, and 4 are explanatory diagrams. The profiles are
recorded inputs; this workflow does not rerun TorchFX model profiling.

## Optional Linux container

The Dockerfile pins Python and the base image digest. Build it from the
repository root, after downloading the telemetry:

```bash
docker build -t stlt-artifact:portable .
mkdir -p artifact-output
docker run --rm --network none \
  --mount type=bind,source="$PWD/datasets",target=/artifact/datasets,readonly \
  --mount type=bind,source="$PWD/artifact-output",target=/artifact/artifact-output \
  stlt-artifact:portable ./scripts/smoke_test.sh --output-dir /artifact/artifact-output/linux-smoke
docker run --rm --network none \
  --mount type=bind,source="$PWD/datasets",target=/artifact/datasets,readonly \
  --mount type=bind,source="$PWD/artifact-output",target=/artifact/artifact-output \
  stlt-artifact:portable ./reproduce_paper_artifacts.sh --output-dir /artifact/artifact-output/linux-full
```

On Linux, bind-mounted outputs may belong to the container user. Native Python
setup avoids this issue. The container build requires internet access; the two
execution commands disable container networking.

## File guide

- `src/stlt_artifact/`: profile analysis, planning, policies, replay, exports,
  validation, and command-line interface.
- `experiments/`: pinned declarative configurations and checksums.
- `data/`: recorded profiles, expected results, and input provenance.
- `scripts/`: setup, input acquisition, smoke test, validation, and packaging.
- `tests/`: scientific interface tests and validation failure cases.
- `docs/`: verification record and submission checklist.
- `hardware/jetson/`: preliminary measurement material outside this workflow.

The GitHub workflow checks setup and smoke reproduction on Ubuntu 22.04. A
manual workflow run can select full reproduction. Local verification is
documented separately; adding a workflow is not evidence that it has run.

## Release packaging

After reviewing and committing the source, run:

```bash
./scripts/package_artifact.sh
```

This produces a source archive, checksum, and commit record in `dist/`. It
requires a clean working tree and includes committed files only. Virtual
environments, downloaded telemetry, generated results, and caches are excluded.
The extracted source supports the same commands as the checkout.

A repository license and a permanent archive URL must be selected before the
public artifact release. The telemetry remains an external upstream input.
