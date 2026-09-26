# Portable verification record

Date: 26 September 2026. Branch: `artifact/portable-reproduction`.

## Procedure

The native environment was created through `scripts/create_env.sh`. The
telemetry was downloaded through `scripts/download_data.sh` and its SHA-256
matched the evaluated input. A separate Docker build installed dependencies
from a clean Python 3.12.9 image. The container execution used `--network none`
with telemetry mounted read-only.

The environment check passed 27 tests. Tests cover the arrival schedule,
candidate extraction, all 70 saved SLICE plans, policy filters, telemetry gaps,
and validation failures. Deliberately damaged bundles fail for missing files,
missing or duplicate experiment rows, incorrect task counts, non-finite energy,
wrong seeds, invalid NF rows, inconsistent aggregates, interrupted run status,
and changed output hashes. Full validation rejects smoke results.
Oracle rows are matched by experiment identity; their order may differ.

Shell syntax checks, Python static checks, and `git diff --check` passed.

The source archive from commit `48ba0a8` was extracted into a new directory.
Setup, all 27 tests, and the real-data smoke test passed there. The archive is
193,320 bytes and excludes environments, downloaded telemetry, generated
results, and caches. Later documentation updates do not change the tested
execution source. The packaging command writes a checksum and commit sidecar
for each archive.

## Environment and measurements

The native host is an Apple M4 Pro with 24 GiB RAM, macOS 26.6.2, and Python
3.12.9. The container uses Debian Bookworm, Linux aarch64, and Python 3.12.9.
Container results describe Linux on Docker Desktop, not an independent
physical Linux workstation. The GitHub workflow targets Ubuntu 22.04 x86_64;
it must run before that platform is described as verified.

| Run | Execution time | Peak memory through export | Validation |
| --- | ---: | ---: | --- |
| Native macOS, full | 618.429 s | 171.2 MiB | 150 passed, 0 failed |
| Clean Linux container, full | 602.846 s | 131.8 MiB | 150 passed, 0 failed |
| Extracted source archive, smoke | 3.672 s | 120.4 MiB | 148 passed, 0 failed |

Each full run produced 29,700 main-suite rows and 24,200 resource-suite rows.
The resource suite contains 2,640 explicitly infeasible SLICE rows. Each full
bundle occupies approximately 13.0 MiB. Both runs used identical execution
source and input hashes.

The nominal results are 256,778 STLT deliveries and 230,426 SLICE deliveries
from 277,200 offered tasks per policy. STLT improves delivery by 11.4362% and
reduces modeled energy by 8.7768%. The minimum-energy split accounts for
39.3433% of STLT admissions. The full oracle comparison also checks every other
aggregate Figure 7 and Figure 8 value.

The machine-readable record is [verification.json](verification.json). It
includes exact times, byte counts, runtime versions, result counts, claims,
and the execution source hashes.

## Scope of this evidence

The tests establish the portable workflow from recorded profiles and calibrated
constants. They do not validate the profile-generation procedure or the
measurement protocols. No Jetson access or hardware experiment is part of this
verification. Numerical plot data is checked by validation; PDF layout is
reviewed visually.

Runtime excludes environment installation and telemetry download. The runner's
`elapsed_s` includes telemetry checksum verification, replay, tables, and plots;
it excludes the final validation. Its `peak_memory_bytes` is the process peak
through the export stage, measured before validation. Both full runs share one
host, so their runtimes are observations rather than isolated benchmarks.
