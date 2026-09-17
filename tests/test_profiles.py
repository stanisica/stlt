import unittest
from pathlib import Path

from stlt_artifact.profiles import ModelProfile, SplitPoint


class ProfileTest(unittest.TestCase):
    def test_candidate_methods(self) -> None:
        profile = ModelProfile(
            "toy",
            (
                SplitPoint(0, 0, 10),
                SplitPoint(1, 1, 8),
                SplitPoint(2, 2, 7.5),
                SplitPoint(3, 3, 2),
            ),
        )
        self.assertEqual(
            [point.layer for point in profile.dnnsplit_candidates()],
            [0, 1, 2, 3],
        )
        self.assertEqual(
            [point.layer for point in profile.anoda_candidates()],
            [0, 3],
        )

    def test_paper_candidate_sets(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "model-profiles"
        expected = {
            "squeezenet1_1": [0, 4, 19, 34, 65],
            "swin_v2_t": [0, 112, 327],
            "efficientnet_b4": [0, 40, 102, 164, 502],
            "resnet50": [0, 175],
            "densenet169": [0, 140, 599],
        }
        actual = {
            model: [
                point.layer
                for point in ModelProfile.from_torchfx(
                    model, root / f"{model}.json"
                ).anoda_candidates()
            ]
            for model in expected
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
