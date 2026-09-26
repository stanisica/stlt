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

Shell syntax checks, Python static checks, and `git diff --check` passed. The
source packaging test is recorded below after the reviewed snapshot is committed.

## Environment and measurements

The native host is an Apple M4 Pro with 24 GiB RAM, macOS 26.6.2, and Python
3.12.9. The container uses Debian Bookworm, Linux aarch64, and Python 3.12.9.
Container results describe Linux on Docker Desktop, not an independent
physical Linux workstation. The GitHub workflow targets Ubuntu 22.04 x86_64;
it must run before that platform is described as verified.

Final run measurements are recorded here after full validation completes.

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
