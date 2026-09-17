import unittest

from stlt_artifact.energy import EnergyModel
from stlt_artifact.policy import AnelaPolicy, SatelliteState
from stlt_artifact.profiles import SplitPoint


class AnelaPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.energy = EnergyModel(
            joules_per_flop=1.0,
            joules_per_bit=1.0,
            computation_s=10,
            contact_s=2,
            rate_bits_per_s=10,
            eo_budget_j=100,
        )
        self.points = (
            SplitPoint(layer=0, work_flops=0, payload_bits=9),
            SplitPoint(layer=1, work_flops=4, payload_bits=2),
        )

    def test_selects_minimum_energy_feasible_candidate(self) -> None:
        policy = AnelaPolicy(self.points, self.energy)
        state = SatelliteState(100, 1, 0, 0, 0, 0)
        decision = policy.decide(state)
        self.assertEqual(decision.split, self.points[1])
        self.assertEqual(decision.energy_j, 6)

    def test_capacity_filter_changes_selection(self) -> None:
        policy = AnelaPolicy(self.points, self.energy)
        state = SatelliteState(100, 1, 0, 0, 15, 0)
        decision = policy.decide(state)
        self.assertEqual(decision.split, self.points[1])

    def test_rejects_when_full_task_energy_exceeds_budget(self) -> None:
        policy = AnelaPolicy((self.points[1],), self.energy)
        state = SatelliteState(5, 1, 100, 0, 0, 0)
        decision = policy.decide(state)
        self.assertIsNone(decision.split)
        self.assertEqual(decision.reason, "full_task_energy_constraint")


if __name__ == "__main__":
    unittest.main()

