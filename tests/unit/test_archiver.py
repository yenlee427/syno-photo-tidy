from pathlib import Path

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import Archiver
from syno_photo_tidy.models import FileInfo


def _make_file(path: Path, timestamp: str) -> FileInfo:
    return FileInfo(
        path=path,
        size_bytes=path.stat().st_size,
        ext=path.suffix,
        drive_letter=path.drive or path.anchor,
        resolution=(100, 100),
        exif_datetime_original=None,
        windows_created_time=1700000000.0,
        timestamp_locked=timestamp,
        timestamp_source="exif",
        scan_machine_timezone="UTC+8",
    )


def test_archiver_builds_year_month_paths(tmp_path: Path) -> None:
    file_path = tmp_path / "source.jpg"
    file_path.write_text("a", encoding="utf-8")

    info = _make_file(file_path, "2024-07-15 14:30:00")
    output_root = tmp_path / "Processed_20260211_143015"

    archiver = Archiver(ConfigManager())
    result = archiver.generate_plan([info], output_root)

    assert len(result.plan) == 1
    dst = result.plan[0].dst_path
    assert dst is not None
    assert dst.parts[-3:] == ("2024", "07", "source.jpg")


def test_archiver_uses_unknown_folder(tmp_path: Path) -> None:
    file_path = tmp_path / "source.jpg"
    file_path.write_text("a", encoding="utf-8")

    info = _make_file(file_path, "bad")
    output_root = tmp_path / "Processed_20260211_143015"

    archiver = Archiver(ConfigManager())
    result = archiver.generate_plan([info], output_root)

    dst = result.plan[0].dst_path
    assert dst is not None
    assert dst.parts[-3:] == ("unknown", "unknown", "source.jpg")


def test_archiver_disabled(tmp_path: Path) -> None:
    file_path = tmp_path / "source.jpg"
    file_path.write_text("a", encoding="utf-8")

    info = _make_file(file_path, "2024-07-15 14:30:00")
    output_root = tmp_path / "Processed_20260211_143015"

    config = ConfigManager()
    config.set("archive.enabled", False)
    archiver = Archiver(config)

    result = archiver.generate_plan([info], output_root)

    assert result.plan == []
    assert len(result.skipped) == 1
