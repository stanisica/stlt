import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackagingTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "scripts").mkdir()
        shutil.copyfile(
            ROOT / "scripts/package_artifact.sh",
            self.root / "scripts/package_artifact.sh",
        )
        (self.root / ".gitignore").write_text("dist/\n.stlt-venv/\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("commit", "-qm", "Fixture")
        self.env = {**os.environ, "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
        self.archive = self.root / "dist/source archive.tar.gz"

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    def package(self):
        return subprocess.run(
            ["/bin/bash", "scripts/package_artifact.sh", str(self.archive)],
            cwd=self.root, env=self.env, capture_output=True, text=True,
        )

    def test_custom_python_creates_complete_package(self):
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        checksum = Path(str(self.archive) + ".sha256").read_text().split()[0]
        self.assertEqual(
            checksum, hashlib.sha256(self.archive.read_bytes()).hexdigest()
        )
        self.assertEqual(
            Path(str(self.archive) + ".commit").read_text().strip(),
            self.git("rev-parse", "HEAD"),
        )
        with tarfile.open(self.archive) as archive:
            self.assertIn(
                "stlt-artifact/scripts/package_artifact.sh", archive.getnames()
            )

    def test_repository_python_is_used_when_no_override_is_set(self):
        self.env.pop("PYTHON")
        directory = self.root / ".stlt-venv/bin"
        directory.mkdir(parents=True)
        (directory / "python").symlink_to(sys.executable)
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_python_leaves_no_package(self):
        self.env["PYTHON"] = str(self.root / "missing-python")
        self.assertNotEqual(self.package().returncode, 0)
        self.assertFalse(self.archive.exists())
        self.assertFalse(Path(str(self.archive) + ".sha256").exists())
        self.assertFalse(Path(str(self.archive) + ".commit").exists())

    def test_existing_sidecar_is_preserved(self):
        self.archive.parent.mkdir()
        sidecar = Path(str(self.archive) + ".sha256")
        sidecar.write_text("existing\n")
        self.assertNotEqual(self.package().returncode, 0)
        self.assertEqual(sidecar.read_text(), "existing\n")
        self.assertFalse(self.archive.exists())

    def test_archive_failure_leaves_no_package(self):
        (self.root / ".gitattributes").write_text("* export-subst\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "Attributes")
        self.git("config", "tar.tar.gz.command", "false")
        self.assertNotEqual(self.package().returncode, 0)
        self.assertEqual(list(self.archive.parent.iterdir()), [])

    def test_dirty_source_is_rejected(self):
        (self.root / "unreviewed.txt").write_text("uncommitted\n")
        self.assertNotEqual(self.package().returncode, 0)
        self.assertFalse(self.archive.exists())
