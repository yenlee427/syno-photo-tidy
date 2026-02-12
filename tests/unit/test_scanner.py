from pathlib import Path

import pytest
from PIL import Image
import piexif

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import FileScanner


def _create_image(path: Path, size=(100, 100), exif_dt: str | None = None) -> None:
    image = Image.new("RGB", size, color=(255, 0, 0))
    if exif_dt:
        exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: exif_dt.encode("utf-8")}}
        exif_bytes = piexif.dump(exif_dict)
        image.save(path, "jpeg", exif=exif_bytes)
    else:
        image.save(path, "jpeg")


def test_scanner_basic_scan(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.jpg"
    _create_image(image_path)
    (tmp_path / "note.txt").write_text("ok", encoding="utf-8")

    scanner = FileScanner(ConfigManager())
    results = scanner.scan_directory(tmp_path)

    assert len(results) == 2
    assert any(item.path.name == "sample.jpg" for item in results)
    image_item = next(item for item in results if item.path.name == "sample.jpg")
    text_item = next(item for item in results if item.path.name == "note.txt")
    assert image_item.file_type == "IMAGE"
    assert text_item.file_type == "OTHER"


def test_scanner_exclude_processed_dirs(tmp_path: Path) -> None:
    processed_dir = tmp_path / "Processed_20260211_120000"
    processed_dir.mkdir()
    _create_image(processed_dir / "skip.jpg")

    scanner = FileScanner(ConfigManager())
    results = scanner.scan_directory(tmp_path)

    assert all("Processed_" not in str(item.path) for item in results)


def test_scanner_skip_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    _create_image(target / "sample.jpg")

    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("此環境無法建立 symlink")

    scanner = FileScanner(ConfigManager())
    results = scanner.scan_directory(tmp_path)

    assert all("link" not in str(item.path) for item in results)


def test_scanner_timestamp_locking(tmp_path: Path) -> None:
    image_path = tmp_path / "exif.jpg"
    _create_image(image_path, exif_dt="2024:07:15 14:30:00")

    scanner = FileScanner(ConfigManager())
    results = scanner.scan_directory(tmp_path)

    assert len(results) == 1
    assert results[0].timestamp_source == "exif"
    assert results[0].timestamp_locked == "2024-07-15 14:30:00"
