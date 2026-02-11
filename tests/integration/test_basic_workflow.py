from pathlib import Path

from PIL import Image

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import ActionPlanner, FileScanner, ManifestContext, ThumbnailDetector
from syno_photo_tidy.utils import reporting


def _create_image(path: Path, size=(100, 100)) -> None:
    image = Image.new("RGB", size, color=(0, 128, 255))
    image.save(path, "jpeg")


def test_full_dry_run_workflow(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _create_image(source_dir / "original.jpg", size=(3000, 2000))
    _create_image(source_dir / "thumb.jpg", size=(320, 240))

    output_dir = tmp_path / "Processed_20260211_143015"

    config = ConfigManager()
    scanner = FileScanner(config)
    detector = ThumbnailDetector(config)
    planner = ActionPlanner(config)

    scanned = scanner.scan_directory(source_dir)
    keepers, thumbnails = detector.classify_files(scanned)
    plan_result = planner.generate_plan(keepers, thumbnails, source_dir, output_dir)

    format_counts = {".jpg": 2}
    summary_info = reporting.build_summary_info(
        mode="Full Run (Dry-run)",
        source_dir=source_dir,
        output_dir=output_dir,
        total_files=len(scanned),
        total_size_bytes=sum(item.size_bytes for item in scanned),
        format_counts=format_counts,
        thumbnail_count=len(thumbnails),
        thumbnail_size_bytes=sum(item.size_bytes for item in thumbnails),
        keeper_count=len(keepers),
        keeper_size_bytes=sum(item.size_bytes for item in keepers),
        exact_duplicate_count=0,
        exact_duplicate_size_bytes=0,
        visual_duplicate_count=0,
        visual_duplicate_size_bytes=0,
        planned_thumbnail_move_count=len(thumbnails),
        planned_duplicate_move_count=0,
        cross_drive_copy=False,
        no_changes_needed=False,
    )

    report_dir = reporting.ensure_report_dir(output_dir)
    summary_path = reporting.write_summary(report_dir, summary_info)
    manifest_context = ManifestContext.from_run(
        run_id=output_dir.name,
        mode="Full Run (Dry-run)",
        source_dir=source_dir,
        output_dir=output_dir,
    )
    manifest_path = reporting.write_manifest(
        report_dir,
        plan_result.manifest_entries,
        context=manifest_context,
    )

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Dry-run" in summary_text
    assert "TO_DELETE/THUMBNAILS" in summary_text
    assert manifest_path.exists()


def test_no_changes_needed(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _create_image(source_dir / "original.jpg", size=(4000, 3000))

    output_dir = tmp_path / "Processed_20260211_143015"

    config = ConfigManager()
    scanner = FileScanner(config)
    detector = ThumbnailDetector(config)
    planner = ActionPlanner(config)

    scanned = scanner.scan_directory(source_dir)
    keepers, thumbnails = detector.classify_files(scanned)
    plan_result = planner.generate_plan(keepers, thumbnails, source_dir, output_dir)

    summary_info = reporting.build_summary_info(
        mode="Full Run (Dry-run)",
        source_dir=source_dir,
        output_dir=output_dir,
        total_files=len(scanned),
        total_size_bytes=sum(item.size_bytes for item in scanned),
        format_counts={".jpg": 1},
        thumbnail_count=len(thumbnails),
        thumbnail_size_bytes=sum(item.size_bytes for item in thumbnails),
        keeper_count=len(keepers),
        keeper_size_bytes=sum(item.size_bytes for item in keepers),
        exact_duplicate_count=0,
        exact_duplicate_size_bytes=0,
        visual_duplicate_count=0,
        visual_duplicate_size_bytes=0,
        planned_thumbnail_move_count=len(thumbnails),
        planned_duplicate_move_count=0,
        cross_drive_copy=False,
        no_changes_needed=planner.is_no_changes_needed(plan_result.plan),
    )

    report_dir = reporting.ensure_report_dir(output_dir)
    summary_path = reporting.write_summary(report_dir, summary_info)

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "No changes needed" in summary_text
