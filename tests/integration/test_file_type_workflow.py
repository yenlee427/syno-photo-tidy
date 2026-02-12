from pathlib import Path

from PIL import Image

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import Pipeline
from syno_photo_tidy.utils import reporting


def _create_image(path: Path, size=(1200, 900)) -> None:
    image = Image.new("RGB", size, color=(0, 128, 255))
    image.save(path, "jpeg")


def test_file_type_workflow_writes_report_csv(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    _create_image(source_dir / "photo.jpg")
    (source_dir / "clip.mp4").write_bytes(b"video-bytes")
    (source_dir / "doc.pdf").write_text("doc", encoding="utf-8")

    output_dir = tmp_path / "Processed_20260212_150000"

    config = ConfigManager()
    config.set("enable_rename", True)
    config.set("move_other_to_keep", True)

    pipeline = Pipeline(config)
    result = pipeline.run_dry_run(source_dir, output_dir, mode="Full Run (Dry-run)")

    report_dir = reporting.ensure_report_dir(output_dir)
    report_path = reporting.write_report_csv(report_dir, result.manifest_entries)

    text = report_path.read_text(encoding="utf-8")
    assert "file_type" in text
    assert "pair_id" in text
    assert "screenshot_evidence" in text

    rows_text = [line for line in text.splitlines()[1:] if line.strip()]
    assert any(",IMAGE," in f",{line}," for line in rows_text)
    assert any(",VIDEO," in f",{line}," for line in rows_text)
    assert any(",OTHER," in f",{line}," for line in rows_text)
