from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import ThumbnailDetector


@dataclass
class DummyFileInfo:
    size_bytes: int
    resolution: Optional[Tuple[int, int]]
    path: Path = Path("test.jpg")
    file_type: str = "IMAGE"


def test_thumbnail_rule_a() -> None:
    detector = ThumbnailDetector(ConfigManager())
    file_info = DummyFileInfo(size_bytes=120 * 1000, resolution=(640, 480))
    assert detector.is_thumbnail(file_info) is True


def test_thumbnail_rule_b() -> None:
    detector = ThumbnailDetector(ConfigManager())
    file_info = DummyFileInfo(size_bytes=999 * 1000, resolution=(320, 240))
    assert detector.is_thumbnail(file_info) is True


def test_thumbnail_no_resolution() -> None:
    detector = ThumbnailDetector(ConfigManager())
    file_info = DummyFileInfo(size_bytes=10 * 1000, resolution=None)
    assert detector.is_thumbnail(file_info) is False


def test_thumbnail_classify_files() -> None:
    detector = ThumbnailDetector(ConfigManager())
    files = [
        DummyFileInfo(size_bytes=120 * 1000, resolution=(640, 480)),
        DummyFileInfo(size_bytes=5 * 1000, resolution=(4000, 3000)),
    ]
    keepers, thumbnails = detector.classify_files(files)
    assert len(keepers) == 1
    assert len(thumbnails) == 1


def test_thumbnail_video_and_other_are_keepers() -> None:
    detector = ThumbnailDetector(ConfigManager())
    files = [
        DummyFileInfo(size_bytes=10 * 1000, resolution=(320, 240), file_type="VIDEO"),
        DummyFileInfo(size_bytes=10 * 1000, resolution=(320, 240), file_type="OTHER"),
    ]

    keepers, thumbnails = detector.classify_files(files)
    assert len(keepers) == 2
    assert len(thumbnails) == 0
