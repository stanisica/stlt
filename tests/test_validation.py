import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from stlt_artifact.bundle import OUTPUTS, digest, source_hashes
from stlt_artifact.candidate_analysis import CANDIDATE_OUTPUTS
from stlt_artifact.experiments import run_suite, summarize_main, summarize_resource
from stlt_artifact.exports import export
from stlt_artifact.telemetry import BUPT1_SHA256, TelemetryTrace
from stlt_artifact.validation import equivalent_rows, validate

ROOT = Path(__file__).resolve().parents[1]


class OracleTest(unittest.TestCase):
    def test_rows_are_matched_by_identity(self):
        expected = [{"model": "a", "delivered": 3}, {"model": "b", "delivered": 4}]
        self.assertTrue(equivalent_rows(expected[::-1], expected, ("model",)))
        self.assertFalse(
            equivalent_rows(expected + [expected[0]], expected, ("model",))
        )
        changed = [{"model": "a", "delivered": 4}, {"model": "b", "delivered": 3}]
        self.assertFalse(equivalent_rows(changed, expected, ("model",)))


class ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.temporary.name) / "fixture"
        cls.fixture.mkdir()
        ones = np.ones(27000)
        trace = TelemetryTrace(
            tuple("synthetic" for _ in ones),
            np.arange(27000),
            ones * 414000,
            ones.astype(int),
            ones * 10,
            ones * 5,
            ones * 5,
            ones * 8000,
        )
        result = {"segments": 1, "archive_sha256": BUPT1_SHA256}
        for suite, key, summarize in (
            ("main", "figure7", summarize_main),
            ("resource", "figure8", summarize_resource),
        ):
            with patch(
                "stlt_artifact.experiments.segments", return_value=iter([(0, trace)])
            ):
                rows = run_suite(
                    ROOT,
                    Path("unused.zip"),
                    suite,
                    cls.fixture / f"{suite}-per-window.csv",
                    segment_count=1,
                )
            result[key] = summarize(rows)
        (cls.fixture / "paper-results.json").write_text(json.dumps(result))
        export(ROOT, cls.fixture, result, "smoke")
        metadata = {
            "status": "complete",
            "mode": "smoke",
            "segments": 1,
            "telemetry_sha256": BUPT1_SHA256,
            "source_sha256": source_hashes(ROOT),
            "elapsed_s": 1.0,
            "python": "test",
            "platform": "test",
            "dependencies": {"numpy": np.__version__},
            "outputs": {name: digest(cls.fixture / name) for name in OUTPUTS},
        }
        (cls.fixture / "metadata.json").write_text(json.dumps(metadata))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "results"
        shutil.copytree(self.fixture, self.output)

    def report(self, mode="smoke"):
        return validate(ROOT, self.output, mode)

    def rehash(self, name):
        path = self.output / "metadata.json"
        metadata = json.loads(path.read_text())
        metadata["outputs"][name] = digest(self.output / name)
        path.write_text(json.dumps(metadata))

    def edit_rows(self, edit, suite="main"):
        name = f"{suite}-per-window.csv"
        path = self.output / name
        with path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        fields = list(rows[0])
        edit(rows)
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        self.rehash(name)

    def assert_failure(self, text):
        report = self.report()
        self.assertFalse(report.ok)
        self.assertTrue(
            any(text in failure for failure in report.failed), report.failed
        )

    def test_complete_smoke_passes(self):
        report = self.report()
        self.assertTrue(report.ok, report.failed)

    def test_missing_directory_fails_without_creating_it(self):
        missing = self.output / "missing"
        self.assertFalse(validate(ROOT, missing, "smoke").ok)
        self.assertFalse(missing.exists())

    def test_summary_alone_fails(self):
        for name in OUTPUTS:
            if name != "paper-results.json":
                (self.output / name).unlink()
        self.assert_failure("required output")

    def test_missing_plot_fails(self):
        (self.output / "figure7.pdf").unlink()
        self.assert_failure("required output: figure7.pdf")

    def test_missing_supplemental_model_plot_fails(self):
        (self.output / "candidates-resnet50.png").unlink()
        self.assert_failure("required output: candidates-resnet50.png")

    def test_candidate_coordinates_are_checked_after_rehash(self):
        name = "candidates-densenet169.csv"
        path = self.output / name
        with path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["payload_mbit"] = "1"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        self.rehash(name)
        self.assert_failure(f"derived table: {name}")

    def test_candidate_bundle_does_not_require_replay_outputs(self):
        for name in set(OUTPUTS) - set(CANDIDATE_OUTPUTS):
            (self.output / name).unlink()
        path = self.output / "metadata.json"
        metadata = json.loads(path.read_text())
        metadata["mode"] = "candidates"
        metadata.pop("segments")
        metadata.pop("telemetry_sha256")
        metadata["outputs"] = {
            name: metadata["outputs"][name] for name in CANDIDATE_OUTPUTS
        }
        path.write_text(json.dumps(metadata))
        report = self.report("candidates")
        self.assertTrue(report.ok, report.failed)

    def test_truncated_csv_fails_after_rehash(self):
        self.edit_rows(lambda rows: rows.pop())
        self.assert_failure("coverage")

    def test_duplicate_row_fails_after_rehash(self):
        self.edit_rows(lambda rows: rows.append(rows[0].copy()))
        self.assert_failure("duplicate experiment")

    def test_accounting_failure_after_rehash(self):
        self.edit_rows(lambda rows: rows[0].update(delivered="999999"))
        self.assert_failure("admitted task accounting")

    def test_nonfinite_energy_fails(self):
        self.edit_rows(lambda rows: rows[0].update(energy_j="nan"))
        self.assert_failure("non-finite")

    def test_wrong_seed_fails(self):
        self.edit_rows(lambda rows: rows[4].update(seed="99"))
        self.assert_failure("coverage")

    def test_infeasible_result_must_be_empty(self):
        def edit(rows):
            next(row for row in rows if row["status"] == "NF")["delivered"] = "0"

        self.edit_rows(edit, "resource")
        self.assert_failure("NF row contains numeric results")

    def test_aggregate_must_match_csv(self):
        path = self.output / "paper-results.json"
        result = json.loads(path.read_text())
        result["figure7"]["rows"][0]["delivered"] += 1
        path.write_text(json.dumps(result))
        self.rehash(path.name)
        self.assert_failure("summary recomputed")

    def test_corrupt_metadata_fails(self):
        (self.output / "metadata.json").write_text("{")
        self.assert_failure("invalid result bundle")

    def test_interrupted_run_fails(self):
        path = self.output / "metadata.json"
        metadata = json.loads(path.read_text())
        metadata["status"] = "running"
        path.write_text(json.dumps(metadata))
        self.assert_failure("run completed")

    def test_smoke_does_not_pass_full_validation(self):
        self.assertFalse(self.report("full").ok)

    def test_changed_file_fails_digest_check(self):
        with (self.output / "MANIFEST.md").open("a") as stream:
            stream.write("changed")
        self.assert_failure("output digest: MANIFEST.md")

    def test_input_check_is_explicit(self):
        report = validate(ROOT, mode="inputs")
        self.assertTrue(report.ok, report.failed)
        self.assertEqual(report.mode, "inputs")
