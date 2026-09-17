import json
import unittest
from dataclasses import asdict
from pathlib import Path

from stlt_artifact.planner import plan_slice


ROOT = Path(__file__).resolve().parents[1]


class SlicePlannerTest(unittest.TestCase):
    def test_all_saved_paper_plans_are_reproduced(self):
        for suite in ("main", "resource"):
            configs = json.loads((ROOT / "experiments" / f"{suite}.json").read_text())
            for config in configs:
                actual = asdict(
                    plan_slice(
                        model=config["model"],
                        profile_path=ROOT
                        / "data"
                        / "model-profiles"
                        / f"{config['model']}.json",
                        interval_s=config["interval_s"],
                        kappa_j_per_gflop=config["kappa_j_per_gflop"],
                        seconds_per_gflop=config["seconds_per_gflop"],
                        rho=config["rho"],
                        rate_mbps=config["rate_mbps"],
                        beta_j_per_bit=config["beta_j_per_bit"],
                    )
                )
                expected = config["plan"]
                self.assertEqual(actual.keys(), expected.keys(), config["config"])
                for key, value in expected.items():
                    if isinstance(value, float):
                        self.assertAlmostEqual(actual[key], value, places=8)
                    elif isinstance(value, list):
                        self.assertEqual(list(actual[key]), value)
                    else:
                        self.assertEqual(actual[key], value, (config["config"], key))


if __name__ == "__main__":
    unittest.main()
