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


def test_action_planner_move_other_to_keep(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "Processed_20260211_143015"
    other_path = source_root / "docs" / "a.pdf"
    other_path.parent.mkdir(parents=True)
    other_path.write_text("x", encoding="utf-8")

    other_file = _make_file(other_path)
    other_file.file_type = "OTHER"

    config = ConfigManager()
    config.set("move_other_to_keep", True)
    planner = ActionPlanner(config)
    plan_result = planner.generate_plan(
        keepers=[other_file],
        thumbnails=[],
        source_root=source_root,
        output_root=output_root,
    )

    assert any(
        item.action == "MOVE" and "KEEP" in str(item.dst_path) and "OTHER" in str(item.dst_path)
        for item in plan_result.plan
    )


def test_action_planner_group_screenshots(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "Processed_20260211_143015"
    screenshot_path = source_root / "Screenshot_001.png"
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_text("x", encoding="utf-8")

    screenshot = _make_file(screenshot_path)
    screenshot.file_type = "IMAGE"
    screenshot.is_screenshot = True
    screenshot.screenshot_evidence = "filename_pattern_match:*Screenshot*"

    config = ConfigManager()
    config.set("group_screenshots", True)
    config.set("screenshots_dest", "KEEP/Screenshots/{YYYY}-{MM}/")
    config.set("enable_rename", False)

    planner = ActionPlanner(config)
    result = planner.generate_plan(
        keepers=[screenshot],
        thumbnails=[],
        source_root=source_root,
        output_root=output_root,
    )

    move_actions = [item for item in result.plan if item.action == "MOVE"]
    rename_actions = [item for item in result.plan if item.action == "RENAME"]
    assert len(move_actions) == 1
    assert "KEEP" in str(move_actions[0].dst_path)
    assert "Screenshots" in str(move_actions[0].dst_path)
    assert "2024-07" in str(move_actions[0].dst_path)
    assert len(rename_actions) == 0


def test_action_planner_group_screenshots_with_rename(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "Processed_20260211_143015"
    screenshot_path = source_root / "Screenshot_001.png"
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_text("x", encoding="utf-8")

    screenshot = _make_file(screenshot_path)
    screenshot.file_type = "IMAGE"
    screenshot.is_screenshot = True
    screenshot.screenshot_evidence = "filename_pattern_match:*Screenshot*"

    config = ConfigManager()
    config.set("group_screenshots", True)
    config.set("screenshots_dest", "KEEP/Screenshots/{YYYY}-{MM}/")
    config.set("enable_rename", True)

    planner = ActionPlanner(config)
    result = planner.generate_plan(
        keepers=[screenshot],
        thumbnails=[],
        source_root=source_root,
        output_root=output_root,
    )

    rename_actions = [item for item in result.plan if item.action == "RENAME"]
    assert len(rename_actions) == 1
    assert rename_actions[0].dst_path is not None
    assert rename_actions[0].dst_path.name.startswith("IMG_20240715_")
