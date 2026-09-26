# Artifact requirements and release checklist

Reviewed on 26 September 2026. Sources:

- [Middleware 2026 call for artifacts](https://middleware-conf.github.io/2026/calls/call-for-artifacts/)
- [Systems Research Artifacts packaging guide](https://sysartifacts.github.io/packaging-guide)

## Venue requirements

Name every requested badge in the submission abstract. The committee evaluates
only the requested badges. The README must state the contents, requirements,
setup, execution, result mapping, and output interpretation. Explain omitted
results and how the included experiments evaluate the main claims.

Automate data acquisition, execution, processing, and plotting where possible.
Test the documented procedure in a fresh environment. State hardware needs and
expected resource use. Provide a build recipe for any distributed container.
Record failures as well as successes. Document any manual step.

The submission deadline is 27 September, AoE. The notification date is
3 November. Authors should be available for clarification during evaluation.

## Implementation rules for this branch

- Keep scientific behavior in importable modules. Shell scripts orchestrate it.
- Use the same execution path for smoke and full runs; change only segment count.
- Treat profiles and calibrated constants as recorded inputs.
- Recompute experimental results. Do not copy reference results into output.
- Reject missing, incomplete, inconsistent, or altered bundles.
- Record exact inputs, dependencies, source hashes, and output hashes.
- Use concise instructions, explicit units, and consistent names.
- Keep Jetson execution outside the portable workflow.
- Do not merge into `main` before author review.

## Release checklist

- [x] Separate input, smoke, and full validation.
- [x] Pin dependencies and telemetry revision; verify input hashes.
- [x] Automate portable experiment execution, tables, plots, and validation.
- [x] Document supported results and exclusions.
- [x] Provide environment checks and failure regression tests.
- [x] Provide a container recipe and a source packaging command.
- [x] Record final clean-environment results in `VERIFICATION.md`.
- [x] Review the generated plots and documentation against the submitted PDF.
- [ ] Select a source-code license.
- [ ] Archive the reviewed release and record its permanent URL and checksum.
- [ ] Name requested badges in the submission abstract and submit the package.

## Deferred measurement work

Reconcile Figure 2 and Table 3 with their generating records. Check the relation
between the current controller and the preserved overhead measurements. Define
and test the Figure 9 rerun protocol. If remote hardware is offered, arrange
reviewer access without requiring personal identifying information and reserve
an uncontended measurement window. These tasks do not run in this branch's
portable workflow.
