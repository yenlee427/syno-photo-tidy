from pathlib import Path

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import Renamer
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


def test_renamer_generates_unique_names(tmp_path: Path) -> None:
    file_a = tmp_path / "a.jpg"
    file_b = tmp_path / "b.jpg"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")

    timestamp = "2024-07-15 14:30:00"
    files = [_make_file(file_a, timestamp), _make_file(file_b, timestamp)]

    renamer = Renamer(ConfigManager())
    result = renamer.generate_plan(files)

    assert len(result.plan) == 2
    dst_names = {item.dst_path.name for item in result.plan if item.dst_path is not None}
    assert len(dst_names) == 2
    assert all(item.dst_path.parent == tmp_path for item in result.plan)


def test_renamer_skips_same_name(tmp_path: Path) -> None:
    file_path = tmp_path / "20240715_143000.jpg"
    file_path.write_text("a", encoding="utf-8")

    files = [_make_file(file_path, "2024-07-15 14:30:00")]
    renamer = Renamer(ConfigManager())
    result = renamer.generate_plan(files)

    assert result.plan == []
    assert len(result.skipped) == 1


def test_renamer_avoids_existing_conflict(tmp_path: Path) -> None:
    file_path = tmp_path / "source.jpg"
    file_path.write_text("a", encoding="utf-8")
    existing = tmp_path / "20240715_143000.jpg"
    existing.write_text("b", encoding="utf-8")

    files = [_make_file(file_path, "2024-07-15 14:30:00")]
    renamer = Renamer(ConfigManager())
    result = renamer.generate_plan(files)

    assert len(result.plan) == 1
    assert "_001" in result.plan[0].dst_path.name
