import tempfile
import unittest
import zipfile
from pathlib import Path

from stlt_artifact.telemetry import segments


class TelemetryTest(unittest.TestCase):
    def test_segments_discard_remainders_at_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "trace.zip"
            seconds = [0, 1, 5, 6, 7, 8, 9, 10, 20]
            csv = "Time,Total_U,Total_I\n" + "".join(
                f"2026-01-01 00:00:{second:02d},1000,1000\n" for second in seconds
            )
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("trace.csv", csv)
            traces = list(segments(archive, samples=3))
            self.assertEqual([i for i, _ in traces], [0, 1])
            self.assertEqual(traces[0][1].timestamps[0], "2026-01-01 00:00:05")
            self.assertEqual(traces[1][1].timestamps[-1], "2026-01-01 00:00:10")
            self.assertEqual(
                [i for i, _ in segments(archive, samples=3, wanted={1})], [1]
            )
            self.assertEqual(list(segments(archive, samples=3, wanted=set())), [])

    def test_archive_rejects_multiple_members(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "trace.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("one.csv", "Time\n")
                handle.writestr("two.csv", "Time\n")
            with self.assertRaisesRegex(ValueError, "expected one CSV"):
                list(segments(archive, samples=3))
