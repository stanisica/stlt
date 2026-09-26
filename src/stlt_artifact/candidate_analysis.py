"""Candidate coordinates derived from the recorded model profiles."""

from pathlib import Path

from .profiles import ModelProfile

MODELS = ("squeezenet1_1", "swin_v2_t", "efficientnet_b4", "resnet50", "densenet169")
CANDIDATE_OUTPUTS = tuple(
    f"candidates-{model}.{extension}"
    for model in MODELS
    for extension in ("csv", "pdf", "png")
) + ("candidate-analysis.pdf", "candidate-analysis.png")


def candidate_tables(root: Path) -> dict[str, list[dict]]:
    output = {}
    for model in MODELS:
        profile = ModelProfile.from_torchfx(
            model, root / "data/model-profiles" / f"{model}.json"
        )
        output[f"candidates-{model}.csv"] = [
            {
                "method": method,
                "layer": point.layer,
                "work_gflops": point.work_flops / 1e9,
                "payload_mbit": point.payload_bits / 1e6,
            }
            for method, points in (
                ("DNNSplit", profile.dnnsplit_candidates()),
                ("ANODA", profile.anoda_candidates()),
            )
            for point in points
        ]
    return output
