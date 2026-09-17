# Artifact inputs

## Model profiles

`model-profiles/` contains the five 4096 × 4096 TorchFX profiles used by the
formula-aligned paper evaluation. Each row records a graph position, whether it
is a valid split, cumulative computation, and the deduplicated live tensor cut.
The raw-input row uses an uncompressed float32 tensor:
`3 × 4096 × 4096 × 32 = 1,610,612,736` bits.

Swin-V2-T uses the corrected profile that attributes attention computation. It
is intentionally different from the older profile whose metadata states that
functional-operation computation was not attributed.

## Telemetry

The raw telemetry archive is not redistributed because no explicit license was
found at the evaluated upstream revision.

- Upstream: `https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS.git`
- Evaluated commit: `951b41521351d535b7c2354916d9c4991602e8c7`
- Relative path: `CommonData-Telemetries/telemetry_all.csv.zip`
- SHA-256: `5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa`
- Raw rows: `10,117,299`
- Complete non-overlapping 27,000 s segments used: `220`
- Rows in those segments: `5,940,000` (`58.71%` of raw rows)

The replay checks this digest before executing the paper experiments.

## Expected and reference results

`expected/paper-results.json` contains the exact values used to refresh the
paper's figures and numerical claims. `reference-results/` contains aggregate
outputs from the independently verified formula-aligned run. They are
regression oracles, not substitutes for rerunning the simulator.

