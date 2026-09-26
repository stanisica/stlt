# STLT artifact overview

## Scope

The artifact evaluates candidate pruning and energy-aware scheduling for
satellite-ground DNN inference. The portable workflow reproduces Table 2,
Figures 5–8, Table 4, and the numerical parameters of Table 1. It also exports
the headline delivery, modeled energy, and candidate-selection statistics.

Supplemental candidate-plane plots cover all five models. Run
`./scripts/analyze_candidates.sh` after setup to generate them without telemetry.
The full workflow includes the same per-model CSV, PDF, and PNG files and a
combined overview. The paper's Figure 5 remains the representative Swin plot.

The target badges are Artifacts Available, Artifacts Functional, and Results
Reproduced. The final submission abstract must name each requested badge.

The package contains Python source, shell scripts, experiment configurations,
five recorded 4096 × 4096 model profiles, preserved result oracles, tests, and
documentation. The raw telemetry is acquired from a fixed upstream revision
and verified before execution. The artifact does not redistribute that archive.

## Reviewer procedure

1. Install Python 3.12, or use the provided Dockerfile.
2. Run `./scripts/create_env.sh`.
3. Run `./scripts/check_env.sh`.
4. Run `./scripts/download_data.sh`.
5. Run `./scripts/smoke_test.sh` and check for `PASS (smoke)`.
6. Run `./reproduce_paper_artifacts.sh` and check for `PASS (full)`.
7. Inspect `artifact-output/full/MANIFEST.md`, the plots, and `paper_claims.csv`.

All experiment execution, aggregation, export, plotting, and validation steps
are automated. No VPN or device access is needed. See [README.md](README.md) for
requirements, alternative paths, output interpretation, and troubleshooting.

## Expected findings

The complete run evaluates 220 five-orbit telemetry segments and produces
53,900 per-window result rows. Under the nominal workloads, STLT delivers
256,778 tasks and SLICE delivers 230,426. STLT improves delivery by 11.4362% and
reduces modeled energy by 8.7768%. ANODA reduces candidate-set size by 30.7143%
on average relative to DNNSplit.

The full validator checks the entire aggregate numerical oracle, not only
these headline values. The smoke test checks functionality on one segment.
It cannot substitute for the full result check.

## Exclusions

Figure 2, Table 3, and Figure 9 are outside this portable phase. They require
separate measurement procedures and provenance reconciliation. Preliminary
Jetson material remains in `hardware/jetson/` but is not installed, executed,
or validated by the portable commands. The profile-generation and calibration
procedures are also outside this workflow; their recorded outputs are inputs.

The artifact evaluates analytical inference and communication energy using
telemetry replay. It does not measure a deployed end-to-end satellite inference
system. These limits still permit evaluation of the main candidate-pruning,
delivery, and modeled energy claims.

## Availability

Development repository: <https://github.com/stanisica/stlt>.
The final release requires an author-selected license and a permanent archive
URL. These release tasks are tracked in [docs/ARTIFACT_RULES.md](docs/ARTIFACT_RULES.md).
