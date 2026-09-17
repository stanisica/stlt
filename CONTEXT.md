# Domain context

## Terms

- **Orbit cycle**: one 5,100 s computation phase followed by one 300 s ground-contact phase.
- **Telemetry segment**: five consecutive orbit cycles, totaling 27,000 s.
- **Task arrival**: an image-capture event generated only during a computation phase. Each orbit contains `floor(T_comp / Delta)` arrivals.
- **DNN profile**: ordered split points with cumulative computation `W` in FLOPs and transmitted representation size `D` in bits.
- **ANODA candidate set**: profile points on the lower convex hull of the `(W, D)` plane.
- **ANELA decision**: admission or rejection plus a split point selected for one task from the ANODA candidate set.
- **EO budget**: the share of modeled satellite energy allocated to inference and downlink.
- **Committed energy**: computation already spent, communication already spent, and communication reserved for queued outputs.
- **One-cycle delivery**: an admitted task must be transmitted in the immediately upcoming contact; no cross-cycle backlog is retained.
- **Policy**: a rule that selects or rejects a split point at a task arrival.
- **Experiment**: a declarative set of workloads, resource settings, telemetry segments, policies, and random seeds.
- **Hardware rerun**: an optional device-dependent measurement that is separate from the deterministic telemetry reproduction.
- **Reference measurement**: preserved output and device metadata from an existing hardware run; it is evidence of execution, not a substitute for reconciling protocol differences.
