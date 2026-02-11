from pathlib import Path

from PIL import Image

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import FileScanner, VisualDeduper


def _create_image(path: Path, size=(100, 100), color=(0, 128, 255)) -> None:
    image = Image.new("RGB", size, color=color)
    image.save(path, "jpeg")


def test_visual_deduper_detects_duplicates(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _create_image(source_dir / "img_a.jpg")
    _create_image(source_dir / "img_b.jpg")

    config = ConfigManager()
    config.set("phash.threshold", 0)

    scanner = FileScanner(config)
    scanned = scanner.scan_directory(source_dir)

    deduper = VisualDeduper(config)
    result = deduper.dedupe(scanned)

    assert len(result.keepers) == 1
    assert len(result.duplicates) == 1
