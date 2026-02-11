from pathlib import Path

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import ActionPlanner
from syno_photo_tidy.models import FileInfo


def _make_file(path: Path) -> FileInfo:
    return FileInfo(
        path=path,
        size_bytes=120 * 1000,
        ext=path.suffix,
        drive_letter=path.drive or path.anchor,
        resolution=(640, 480),
        exif_datetime_original=None,
        windows_created_time=1700000000.0,
        timestamp_locked="2024-07-15 14:30:00",
        timestamp_source="exif",
        scan_machine_timezone="UTC+8",
    )


def test_action_planner_generate_plan(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "Processed_20260211_143015"
    file_path = source_root / "thumb.jpg"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("x", encoding="utf-8")

    planner = ActionPlanner(ConfigManager())
    plan_result = planner.generate_plan(
        keepers=[],
        thumbnails=[_make_file(file_path)],
        source_root=source_root,
        output_root=output_root,
    )

    assert len(plan_result.plan) == 1
    assert "TO_DELETE" in str(plan_result.plan[0].dst_path)
    assert len(plan_result.manifest_entries) == 1


def test_action_planner_no_changes() -> None:
    planner = ActionPlanner(ConfigManager())
    assert planner.is_no_changes_needed([]) is True
