from pathlib import Path

from PIL import Image, PngImagePlugin

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import Pipeline


def _create_png_with_screenshot_meta(path: Path) -> None:
    image = Image.new("RGB", (1200, 900), color=(255, 255, 255))
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Description", "Screenshot capture")
    image.save(path, pnginfo=meta)


def test_screenshot_workflow_strict_bucket_move(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    screenshot_path = source_dir / "shot.png"
    _create_png_with_screenshot_meta(screenshot_path)

    output_dir = tmp_path / "Processed_20260212_170000"

    config = ConfigManager()
    config.set("group_screenshots", True)
    config.set("enable_rename", False)
    config.set("screenshot_detection_mode", "strict")

    pipeline = Pipeline(config)
    result = pipeline.run_dry_run(source_dir, output_dir, mode="Full Run (Dry-run)")

    move_actions = [
        action for action in result.plan if action.action == "MOVE" and action.reason == "SCREENSHOT"
    ]
    rename_actions = [action for action in result.plan if action.action == "RENAME"]

    assert len(move_actions) == 1
    assert "KEEP" in str(move_actions[0].dst_path)
    assert "Screenshots" in str(move_actions[0].dst_path)
    assert len(rename_actions) == 0

    screenshot_entries = [entry for entry in result.manifest_entries if entry.is_screenshot]
    assert screenshot_entries
    assert screenshot_entries[0].screenshot_evidence is not None
    assert "metadata_keyword_match" in screenshot_entries[0].screenshot_evidence
