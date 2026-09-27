import unittest
from unittest.mock import patch

import numpy as np

from stlt_artifact.arrivals import OrbitSchedule
from stlt_artifact.energy import EnergyModel
from stlt_artifact.policy import AnelaPolicy, Decision
from stlt_artifact.profiles import SplitPoint
from stlt_artifact.simulator import TelemetrySimulator
from stlt_artifact.telemetry import TelemetryTrace


class AccountingTest(unittest.TestCase):
    def setUp(self):
        schedule = OrbitSchedule(computation_s=3, contact_s=2, cycles=1)
        energy = EnergyModel(1, 1, 3, 2, 10, 100)
        self.split = SplitPoint(layer=0, work_flops=2, payload_bits=3)
        self.policy = AnelaPolicy((self.split,), energy)
        self.simulator = TelemetrySimulator(schedule, energy, rho=1)
        ones = np.ones(schedule.horizon_s)
        self.trace = TelemetryTrace(
            tuple("synthetic" for _ in ones), np.arange(len(ones)), ones * 100,
            ones.astype(int), ones * 0, ones * 0, ones * 0, ones * 8000,
        )

    def test_consistent_reservations_preserve_results(self):
        result = self.simulator.run_anela(self.trace, 2, self.policy)
        self.assertEqual((result.offered, result.admitted, result.delivered), (1, 1, 1))
        self.assertEqual(result.energy_j, 5)
        self.assertLessEqual(result.max_accounting_error_j, 1e-6)

    def test_inconsistent_reservations_fail(self):
        for amount in (4, float("nan"), float("inf")):
            with self.subTest(amount=amount), patch.object(
                self.policy, "decide", return_value=Decision(self.split, amount, "test")
            ):
                with self.assertRaisesRegex(
                    AssertionError, "energy reservation accounting"
                ):
                    self.simulator.run_anela(self.trace, 2, self.policy)
