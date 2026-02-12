from pathlib import Path

from PIL import Image

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import Pipeline


def _create_image(path: Path, size=(1200, 900)) -> None:
    image = Image.new("RGB", size, color=(255, 64, 64))
    image.save(path, "jpeg")


def test_live_photo_workflow_pair_and_manifest_fields(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    image_path = source_dir / "IMG_0001.jpg"
    video_path = source_dir / "IMG_0001.mov"

    _create_image(image_path)
    video_path.write_bytes(b"video")

    output_dir = tmp_path / "Processed_20260212_160000"

    config = ConfigManager()
    config.set("enable_rename", True)

    pipeline = Pipeline(config)
    result = pipeline.run_dry_run(source_dir, output_dir, mode="Full Run (Dry-run)")

    live_entries = [entry for entry in result.manifest_entries if entry.is_live_pair]
    assert len(live_entries) >= 2
    assert all(entry.pair_confidence == "high" for entry in live_entries)
    assert all(entry.pair_id for entry in live_entries)

    rename_actions = [
        action
        for group, actions in result.plan_groups
        if group == "Renaming"
        for action in actions
        if action.dst_path is not None
    ]
    assert len(rename_actions) >= 2

    renamed_targets = {
        action.dst_path.suffix.lower(): action.dst_path.stem
        for action in rename_actions
        if action.dst_path.suffix.lower() in {".jpg", ".mov"}
    }
    assert renamed_targets[".jpg"] == renamed_targets[".mov"]
