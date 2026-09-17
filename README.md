# STLT artifact

This repository is the clean reproduction artifact for the paper **“STLT: A
Novel System for Energy-Aware Distributed Inference in the Edge-Cloud-Space
Continuum.”** It is being assembled from the formula-aligned, 220-segment
evaluation used by the current paper revision.

The artifact has two design rules:

1. Scientific behavior lives in importable modules under `src/stlt_artifact/`.
2. Reviewer commands only orchestrate those modules. They do not patch source
   files, mutate module globals, or encode a second version of an experiment.

## What this artifact reproduces

The artifact implements the complete formula-aligned evaluation behind the
current revision:

- per-orbit task arrivals, `I_k = floor(T_comp / Delta)`;
- ANODA candidate extraction and online STLT/ANELA decisions;
- the offline, fixed-split SLICE planner and telemetry replay;
- attempt-first TOGC, TOBC, and five-seed RAND baselines;
- the 15 main workload settings and 55 resource-sensitivity settings; and
- the machine-readable data and PDFs for Figures 7 and 8.

The clean implementations have been checked row-for-row against the frozen
evaluation outputs on multiple telemetry segments. The full 220-segment run is
validated against `data/expected/paper-results.json` by
`./scripts/validate_results.sh`.

## Intended reviewer interface

```bash
./scripts/create_env.sh
./scripts/check_env.sh
./reproduce_paper_artifacts.sh --archive /path/to/telemetry_all.csv.zip
./scripts/validate_results.sh
```

For a quick execution check, add `--segments 1`. The complete command runs 220
five-orbit segments. Outputs are written under `artifact-output/`, including
per-window CSV files, `paper-results.json`, `figure7.pdf`, and `figure8.pdf`.

The raw BUPT-1 telemetry archive is not redistributed because its upstream
repository has no explicit license file. The release will document the exact
upstream revision, path, and SHA-256 digest.

## Layout

- `src/stlt_artifact/`: scientific implementation.
- `data/model-profiles/`: checked-in DNN profiles used by the paper.
- `data/expected/`: machine-readable paper-result oracle.
- `experiments/`: declarative paper configurations.
- `hardware/jetson/`: optional, preliminary Jetson measurement reruns and
  compact reference metadata.
- `scripts/`: environment and validation entry points.
- `tests/`: tests through the same interfaces used by the experiments.

## Implementation map

- `arrivals.py` owns the orbit-reset arrival formula.
- `profiles.py` owns profile parsing, DNNSplit filtering, and ANODA extraction.
- `planner.py` owns the offline SLICE equations and fixed-split selection.
- `policy.py` owns the online ANELA decision rule.
- `simulator.py` owns one-cycle delivery and energy accounting for all policies.
- `experiments.py` maps declarative settings to those scientific interfaces.
- `figures.py` renders only from the generated machine-readable summaries.

No reproduction step rewrites source files, patches imports, or mutates
process-global scientific constants.

## Telemetry input

Obtain `CommonData-Telemetries/telemetry_all.csv.zip` from commit
`951b41521351d535b7c2354916d9c4991602e8c7` of the upstream
`TiansuanConstellation/MobiCom24-SatelliteCOTS` repository. The reproduction
command refuses an archive whose SHA-256 differs from the evaluated input.

## Release note

A repository license must be selected by the authors before public release.
The telemetry archive is intentionally not redistributed; see
`data/README.md` for its provenance and licensing note.
