import unittest

from stlt_artifact.arrivals import OrbitSchedule


class OrbitScheduleTest(unittest.TestCase):
    def test_paper_workloads_use_floor_per_orbit(self) -> None:
        schedule = OrbitSchedule()
        expected = {
            31: 820,
            365: 65,
            119: 210,
            319: 75,
            269: 90,
        }
        self.assertEqual(
            {interval: schedule.offered_tasks(interval) for interval in expected},
            expected,
        )

    def test_arrivals_restart_after_each_contact(self) -> None:
        schedule = OrbitSchedule(computation_s=10, contact_s=2, cycles=2)
        arrivals = [time for time, kind in schedule.events(3) if kind == "arrival"]
        self.assertEqual(arrivals, [3, 6, 9, 15, 18, 21])


if __name__ == "__main__":
    unittest.main()

