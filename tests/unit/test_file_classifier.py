from pathlib import Path

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.models import FileInfo
from syno_photo_tidy.utils.file_classifier import classify_file_type


def _make_file_info(path: Path, ext: str) -> FileInfo:
    return FileInfo(
        path=path,
        size_bytes=1,
        ext=ext,
        drive_letter="C:",
        resolution=None,
        exif_datetime_original=None,
        windows_created_time=0.0,
        timestamp_locked="2024-01-01 00:00:00",
        timestamp_source="fs",
        scan_machine_timezone="UTC+8",
    )


def test_classify_image_video_other() -> None:
    image_file = _make_file_info(Path("photo.jpg"), ".jpg")
    video_file = _make_file_info(Path("video.mp4"), ".mp4")
    other_file = _make_file_info(Path("doc.pdf"), ".pdf")

    assert classify_file_type(image_file) == "IMAGE"
    assert classify_file_type(video_file) == "VIDEO"
    assert classify_file_type(other_file) == "OTHER"


def test_classify_with_config() -> None:
    config = ConfigManager()
    image_file = _make_file_info(Path("photo.jpg"), ".jpg")
    video_file = _make_file_info(Path("video.mp4"), ".mp4")

    assert classify_file_type(image_file, config) == "IMAGE"
    assert classify_file_type(video_file, config) == "VIDEO"
