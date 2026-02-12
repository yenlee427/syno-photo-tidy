from pathlib import Path

from syno_photo_tidy.core import LivePhotoMatcher
from syno_photo_tidy.models import FileInfo


def _make_file(path: Path, file_type: str, ext: str, timestamp: str) -> FileInfo:
    return FileInfo(
        path=path,
        size_bytes=1,
        ext=ext,
        drive_letter="C:",
        resolution=(100, 100),
        exif_datetime_original=None,
        windows_created_time=0.0,
        timestamp_locked=timestamp,
        timestamp_source="exif",
        scan_machine_timezone="UTC+8",
        file_type=file_type,
    )


def test_live_photo_pair_success() -> None:
    matcher = LivePhotoMatcher()
    image = _make_file(Path("C:/A/IMG_1234.heic"), "IMAGE", ".heic", "2024-07-15 14:30:00")
    video = _make_file(Path("C:/A/IMG_1234.mov"), "VIDEO", ".mov", "2024-07-15 14:30:01")

    pairs = matcher.find_live_pairs([image, video])

    assert len(pairs) == 1
    assert pairs[0].image == image
    assert pairs[0].video == video
    assert image.is_live_pair is True
    assert video.is_live_pair is True
    assert image.pair_id == video.pair_id
    assert image.pair_confidence == "high"


def test_live_photo_pair_fail_time_too_far() -> None:
    matcher = LivePhotoMatcher()
    image = _make_file(Path("C:/A/IMG_1234.heic"), "IMAGE", ".heic", "2024-07-15 14:30:00")
    video = _make_file(Path("C:/A/IMG_9999.mov"), "VIDEO", ".mov", "2024-07-15 14:31:00")

    pairs = matcher.find_live_pairs([image, video])

    assert pairs == []


def test_live_photo_pair_stable_result() -> None:
    matcher = LivePhotoMatcher()
    files = [
        _make_file(Path("C:/A/IMG_0002.heic"), "IMAGE", ".heic", "2024-07-15 14:30:02"),
        _make_file(Path("C:/A/IMG_0001.heic"), "IMAGE", ".heic", "2024-07-15 14:30:00"),
        _make_file(Path("C:/A/VID_0002.mov"), "VIDEO", ".mov", "2024-07-15 14:30:03"),
        _make_file(Path("C:/A/VID_0001.mov"), "VIDEO", ".mov", "2024-07-15 14:30:01"),
    ]

    pairs1 = matcher.find_live_pairs(files)

    files2 = [
        _make_file(Path("C:/A/IMG_0002.heic"), "IMAGE", ".heic", "2024-07-15 14:30:02"),
        _make_file(Path("C:/A/IMG_0001.heic"), "IMAGE", ".heic", "2024-07-15 14:30:00"),
        _make_file(Path("C:/A/VID_0002.mov"), "VIDEO", ".mov", "2024-07-15 14:30:03"),
        _make_file(Path("C:/A/VID_0001.mov"), "VIDEO", ".mov", "2024-07-15 14:30:01"),
    ]
    pairs2 = matcher.find_live_pairs(files2)

    assert [(p.image.path, p.video.path) for p in pairs1] == [
        (p.image.path, p.video.path) for p in pairs2
    ]
