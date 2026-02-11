import shutil
from pathlib import Path

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import ExactDeduper
from syno_photo_tidy.models import FileInfo


def _make_file_info(path: Path, size_bytes: int) -> FileInfo:
    return FileInfo(
        path=path,
        size_bytes=size_bytes,
        ext=path.suffix,
        drive_letter=path.drive or path.anchor,
        resolution=(4000, 3000),
        exif_datetime_original=None,
        windows_created_time=1700000000.0,
        timestamp_locked="2024-07-15 14:30:00",
        timestamp_source="exif",
        scan_machine_timezone="UTC+8",
    )


def test_exact_deduper_groups_duplicates(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    original = source_dir / "photo_a.jpg"
    duplicate = source_dir / "photo_b.jpg"
    original.write_bytes(b"duplicate-bytes")
    shutil.copy2(original, duplicate)

    file_a = _make_file_info(original, original.stat().st_size)
    file_b = _make_file_info(duplicate, duplicate.stat().st_size)

    deduper = ExactDeduper(ConfigManager())
    result = deduper.dedupe([file_a, file_b])

    assert len(result.keepers) == 1
    assert len(result.duplicates) == 1
    assert result.duplicates[0].hash_sha256 is not None
    assert result.keepers[0].hash_sha256 == result.duplicates[0].hash_sha256
    assert result.groups[0].keeper.path == original
