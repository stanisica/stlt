# Paper experiment configurations

- `main.json`: 15 model/workload configurations, comprising the nominal,
  approximately 75%, and approximately 50% arrival-rate workloads.
- `resource.json`: 55 configurations for the EO-budget and maximum-downlink-rate
  sensitivity sweeps.

These are exact declarative snapshots from the verified formula-aligned run.
The runner recomputes the SLICE plans from the checked-in model profiles and
checks them against the saved plan fields before replay. The remaining derived
fields provide an inspectable provenance record and fail-fast drift checks.

The smoke and full commands use these same configurations. They select one
or 220 telemetry segments, respectively. The main suite runs STLT, SLICE,
TOBC, TOGC, and RAND with seeds 7, 19, 42, 73, and 101. The resource suite runs
STLT and SLICE. The runner records an explicit `NF` result if SLICE cannot plan
the complete workload.
