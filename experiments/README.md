# Paper experiment configurations

- `main.json`: 15 model/workload configurations, comprising the nominal,
  approximately 75%, and approximately 50% arrival-rate workloads.
- `resource.json`: 55 configurations for the EO-budget and maximum-downlink-rate
  sensitivity sweeps.

These are exact declarative snapshots from the verified formula-aligned run.
The runner recomputes the SLICE plans from the checked-in model profiles and
checks them against the saved plan fields before replay. The remaining derived
fields provide an inspectable provenance record and fail-fast drift checks.
