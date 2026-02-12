from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .config import ConfigManager
from .core import ManifestContext, Pipeline, PlanExecutor, RollbackRunner
from .gui import MainWindow
from .utils import reporting, time_utils


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    print(f"syno-photo-tidy v{__version__}")
    if args.command in {None, "gui"}:
        app = MainWindow()
        app.run()
        return

    config = ConfigManager(Path(args.config) if args.config else None)
    if args.command == "dry-run":
        _run_dry_run(args, config)
    elif args.command == "execute":
        _run_execute(args, config)
    elif args.command == "rollback":
        _run_rollback(args, config)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="syno_photo_tidy")
    parser.add_argument("--config", help="Path to config file", default=None)

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("gui", help="Launch GUI")

    dry_run = subparsers.add_parser("dry-run", help="Run dry-run scan")
    dry_run.add_argument("--source", required=True, help="Source folder")
    dry_run.add_argument("--output", help="Output folder")

    execute = subparsers.add_parser("execute", help="Run execute flow")
    execute.add_argument("--source", required=True, help="Source folder")
    execute.add_argument("--output", help="Output folder")

    rollback = subparsers.add_parser("rollback", help="Rollback a processed run")
    rollback.add_argument("--processed", required=True, help="Processed_* folder")

    return parser


def _resolve_output_root(source_path: Path, output_value: str | None) -> Path:
    if output_value:
        return Path(output_value)
    timestamp = time_utils.get_timestamp_for_folder()
    return source_path / f"Processed_{timestamp}"


def _run_dry_run(args: argparse.Namespace, config: ConfigManager) -> None:
    source_path = Path(args.source)
    output_root = _resolve_output_root(source_path, args.output)

    pipeline = Pipeline(config)
    pipeline_result = pipeline.run_dry_run(
        source_path,
        output_root,
        mode="Full Run (Dry-run)",
        stage_callback=lambda message: print(message),
        log_callback=lambda message: print(message),
    )

    reporting.write_summary(pipeline_result.report_dir, pipeline_result.summary_info)
    manifest_context = ManifestContext.from_run(
        run_id=output_root.name,
        mode="Full Run (Dry-run)",
        source_dir=source_path,
        output_dir=output_root,
    )
    reporting.write_manifest(
        pipeline_result.report_dir,
        pipeline_result.manifest_entries,
        context=manifest_context,
    )

    if pipeline_result.summary_info.no_changes_needed:
        print("No changes needed")
    else:
        print(f"Report written to: {pipeline_result.report_dir}")


def _run_execute(args: argparse.Namespace, config: ConfigManager) -> None:
    source_path = Path(args.source)
    output_root = _resolve_output_root(source_path, args.output)

    pipeline = Pipeline(config)
    pipeline_result = pipeline.run_dry_run(
        source_path,
        output_root,
        mode="Full Run (Dry-run)",
        stage_callback=lambda message: print(message),
        log_callback=lambda message: print(message),
    )

    reporting.write_summary(pipeline_result.report_dir, pipeline_result.summary_info)
    manifest_context = ManifestContext.from_run(
        run_id=output_root.name,
        mode="Full Run (Dry-run)",
        source_dir=source_path,
        output_dir=output_root,
    )
    reporting.write_manifest(
        pipeline_result.report_dir,
        pipeline_result.manifest_entries,
        context=manifest_context,
    )

    if pipeline_result.summary_info.no_changes_needed:
        print("No changes needed")
        return

    executor = PlanExecutor()
    executed_entries = []
    failed_entries = []
    manifest_path = pipeline_result.report_dir / "manifest.jsonl"
    for label, plan in pipeline_result.plan_groups:
        if not plan:
            continue
        print(f"Executing: {label}")
        result = executor.execute_plan(plan, manifest_path=manifest_path)
        executed_entries.extend(result.executed_entries)
        failed_entries.extend(result.failed_entries)

    print(f"Execute done. Success: {len(executed_entries)}, Failed: {len(failed_entries)}")


def _run_rollback(args: argparse.Namespace, config: ConfigManager) -> None:
    processed_dir = Path(args.processed)
    runner = RollbackRunner()
    result = runner.rollback(processed_dir)
    print(
        "Rollback done. "
        f"Rolled back: {len(result.rolled_back)}, "
        f"Trashed: {len(result.trashed)}, "
        f"Conflicts: {len(result.conflicts)}, "
        f"Skipped: {len(result.skipped)}, "
        f"Failed: {len(result.failed)}"
    )
