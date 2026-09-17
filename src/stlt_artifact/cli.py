"""Reviewer-facing command line interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from .experiments import run_suite, summarize_main, summarize_resource
from .telemetry import BUPT1_SHA256
from .validation import validate


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="stlt-artifact")
    result.add_argument(
        "command",
        choices=("check", "reproduce", "validate"),
        help="artifact workflow stage",
    )
    result.add_argument("--archive", type=Path, help="BUPT-1 telemetry_all.csv.zip")
    result.add_argument("--segments", type=int, default=220)
    result.add_argument(
        "--suite", choices=("all", "main", "resource"), default="all"
    )
    result.add_argument("--output-dir", type=Path)
    return result


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    args = parser().parse_args()
    if args.command == "check":
        print("STLT artifact core modules import successfully")
        return
    if args.command == "validate":
        root = Path(__file__).resolve().parents[2]
        selected_output = args.output_dir or root / "artifact-output"
        report = validate(root, selected_output)
        output = selected_output / "validation_report.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.as_dict(), indent=2) + "\n")
        print(f"Status: {'PASS' if report.ok else 'FAIL'}")
        print(f"Checks: {len(report.passed)} passed, {len(report.failed)} failed")
        if report.failed:
            for failure in report.failed:
                print(f"FAIL: {failure}")
            raise SystemExit(1)
        return
    if args.archive is None or not args.archive.is_file():
        raise SystemExit("reproduce requires --archive /path/to/telemetry_all.csv.zip")
    actual_digest = _digest(args.archive)
    if actual_digest != BUPT1_SHA256:
        raise SystemExit(
            "telemetry archive digest mismatch: "
            f"expected {BUPT1_SHA256}, found {actual_digest}"
        )
    root = Path(__file__).resolve().parents[2]
    output = args.output_dir or root / "artifact-output"
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result: dict[str, object] = {
        "segments": args.segments,
        "archive_sha256": actual_digest,
    }
    if args.suite in {"all", "main"}:
        main_rows = run_suite(
            root,
            args.archive,
            "main",
            output / "main-per-window.csv",
            segment_count=args.segments,
        )
        result["figure7"] = summarize_main(main_rows)
        if args.segments == 220:
            from .figures import figure7

            figure7(result["figure7"], output / "figure7.pdf")
    if args.suite in {"all", "resource"}:
        resource_rows = run_suite(
            root,
            args.archive,
            "resource",
            output / "resource-per-window.csv",
            segment_count=args.segments,
        )
        result["figure8"] = summarize_resource(resource_rows)
        if args.segments == 220:
            from .figures import figure8

            figure8(result["figure8"], output / "figure8.pdf")
    results_path = output / "paper-results.json"
    results_path.write_text(json.dumps(result, indent=2) + "\n")
    output_names = ["paper-results.json"]
    if args.suite in {"all", "main"}:
        output_names.append("main-per-window.csv")
        if args.segments == 220:
            output_names.append("figure7.pdf")
    if args.suite in {"all", "resource"}:
        output_names.append("resource-per-window.csv")
        if args.segments == 220:
            output_names.append("figure8.pdf")
    generated = {
        name: _digest(output / name) for name in output_names if (output / name).is_file()
    }
    metadata = {
        "status": "complete",
        "suite": args.suite,
        "segments": args.segments,
        "elapsed_s": time.monotonic() - started,
        "python": sys.version,
        "platform": platform.platform(),
        "inputs": {
            "telemetry_sha256": actual_digest,
            "main_configuration_sha256": _digest(root / "experiments" / "main.json"),
            "resource_configuration_sha256": _digest(
                root / "experiments" / "resource.json"
            ),
        },
        "outputs": generated,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Reproduction outputs: {output}")


if __name__ == "__main__":
    main()
