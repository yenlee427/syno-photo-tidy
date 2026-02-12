from pathlib import Path

from PIL import Image, PngImagePlugin

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import ScreenshotDetector
from syno_photo_tidy.models import FileInfo


def _make_file(path: Path, ext: str) -> FileInfo:
    return FileInfo(
        path=path,
        size_bytes=1,
        ext=ext,
        drive_letter="C:",
        resolution=(100, 100),
        exif_datetime_original=None,
        windows_created_time=0.0,
        timestamp_locked="2024-07-15 14:30:00",
        timestamp_source="exif",
        scan_machine_timezone="UTC+8",
        file_type="IMAGE",
    )


def test_screenshot_detector_strict_metadata(tmp_path: Path) -> None:
    file_path = tmp_path / "photo.png"
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Description", "Screenshot capture")
    image.save(file_path, pnginfo=meta)

    config = ConfigManager()
    detector = ScreenshotDetector(config)

    is_screenshot, evidence = detector.is_screenshot(_make_file(file_path, ".png"), mode="strict")
    assert is_screenshot is True
    assert evidence is not None
    assert "metadata" in evidence


def test_screenshot_detector_strict_no_metadata(tmp_path: Path) -> None:
    file_path = tmp_path / "Screenshot_20240715.png"
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    image.save(file_path)

    config = ConfigManager()
    detector = ScreenshotDetector(config)

    is_screenshot, evidence = detector.is_screenshot(_make_file(file_path, ".png"), mode="strict")
    assert is_screenshot is False
    assert evidence is None


def test_screenshot_detector_relaxed_filename(tmp_path: Path) -> None:
    file_path = tmp_path / "Screenshot_20240715.png"
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    image.save(file_path)

    config = ConfigManager()
    config.set("screenshot_filename_patterns", ["Screenshot*", "*螢幕截圖*"])
    detector = ScreenshotDetector(config)

    is_screenshot, evidence = detector.is_screenshot(_make_file(file_path, ".png"), mode="relaxed")
    assert is_screenshot is True
    assert evidence is not None
    assert "filename" in evidence
