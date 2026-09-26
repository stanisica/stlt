"""Reviewer commands for input acquisition, reproduction, and validation."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import resource
import sys
import time
import urllib.request
from pathlib import Path

from .bundle import OUTPUTS, SEGMENTS, digest, source_hashes
from .experiments import run_suite, summarize_main, summarize_resource
from .exports import export
from .telemetry import BUPT1_SHA256
from .validation import ValidationReport, validate

TELEMETRY_URL = (
    "https://raw.githubusercontent.com/TiansuanConstellation/MobiCom24-SatelliteCOTS/"
    "951b41521351d535b7c2354916d9c4991602e8c7/CommonData-Telemetries/telemetry_all.csv.zip"
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="stlt-artifact")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="verify bundled input integrity")
    download = commands.add_parser(
        "download", help="download and verify the upstream telemetry"
    )
    download.add_argument("--archive", type=Path)
    for name in ("reproduce", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--mode", choices=tuple(SEGMENTS), default="full")
        command.add_argument("--output-dir", type=Path)
        if name == "reproduce":
            command.add_argument("--archive", type=Path)
    return result


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def _report(report: ValidationReport, output: Path | None = None) -> None:
    if output is not None and output.is_dir():
        _write_json(output / "validation_report.json", report.as_dict())
    print(f"Status: {'PASS' if report.ok else 'FAIL'} ({report.mode})")
    print(f"Checks: {len(report.passed)} passed, {len(report.failed)} failed")
    for failure in report.failed:
        print(f"FAIL: {failure}")
    if not report.ok:
        raise SystemExit(1)


def download(archive: Path) -> None:
    if archive.exists():
        if digest(archive) != BUPT1_SHA256:
            raise ValueError(f"existing archive has the wrong SHA-256: {archive}")
        print(f"Telemetry verified: {archive}")
        return
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(".zip.part")
    print(f"Downloading 77 MiB from {TELEMETRY_URL}", flush=True)
    with (
        urllib.request.urlopen(TELEMETRY_URL, timeout=60) as response,
        temporary.open("wb") as stream,
    ):
        while block := response.read(1024 * 1024):
            stream.write(block)
    if digest(temporary) != BUPT1_SHA256:
        raise ValueError(f"download SHA-256 mismatch; inspect {temporary}")
    temporary.replace(archive)
    print(f"Telemetry verified: {archive}")


def reproduce(root: Path, archive: Path, output: Path, mode: str) -> None:
    if not archive.is_file():
        raise ValueError(
            "telemetry is missing; run ./scripts/download_data.sh or supply --archive PATH"
        )
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            f"output directory is not empty: {output}; select a new --output-dir"
        )
    started = time.monotonic()
    if digest(archive) != BUPT1_SHA256:
        raise ValueError("telemetry archive SHA-256 mismatch")
    _report(validate(root, mode="inputs"))
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "status": "running",
        "mode": mode,
        "segments": SEGMENTS[mode],
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
        "telemetry_sha256": BUPT1_SHA256,
        "source_sha256": source_hashes(root),
    }
    _write_json(output / "metadata.json", metadata)
    try:
        result = {"segments": SEGMENTS[mode], "archive_sha256": BUPT1_SHA256}
        for suite, key, summarize in (
            ("main", "figure7", summarize_main),
            ("resource", "figure8", summarize_resource),
        ):
            rows = run_suite(
                root,
                archive,
                suite,
                output / f"{suite}-per-window.csv",
                segment_count=SEGMENTS[mode],
            )
            result[key] = summarize(rows)
        _write_json(output / "paper-results.json", result)
        export(root, output, result, mode)
        metadata.update(
            status="complete",
            elapsed_s=time.monotonic() - started,
            peak_memory_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * (1 if sys.platform == "darwin" else 1024),
            outputs={name: digest(output / name) for name in OUTPUTS},
        )
        _write_json(output / "metadata.json", metadata)
    except (Exception, KeyboardInterrupt) as error:
        metadata.update(
            status="failed", elapsed_s=time.monotonic() - started, error=str(error)
        )
        _write_json(output / "metadata.json", metadata)
        raise
    _report(validate(root, output, mode), output)
    print(f"Reproduction outputs: {output}")
    print(f"Execution time: {metadata['elapsed_s']:.2f} s (excludes validation)")
    if mode == "smoke":
        print("Smoke test passed. Full paper totals have not been checked.")


def main() -> None:
    args = parser().parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        if args.command == "check":
            _report(validate(root, mode="inputs"))
        elif args.command == "download":
            download(args.archive or root / "datasets/telemetry_all.csv.zip")
        else:
            output = args.output_dir or root / "artifact-output" / args.mode
            if args.command == "validate":
                _report(validate(root, output, args.mode), output)
            else:
                reproduce(
                    root,
                    args.archive or root / "datasets/telemetry_all.csv.zip",
                    output,
                    args.mode,
                )
    except (OSError, ValueError) as error:
        raise SystemExit(f"ERROR: {error}") from error


if __name__ == "__main__":
    main()
