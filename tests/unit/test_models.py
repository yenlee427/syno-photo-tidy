from pathlib import Path

from syno_photo_tidy.models import ActionItem, ErrorLevel, FileInfo, ProcessError


def test_file_info_creation() -> None:
    file_info = FileInfo(
        path=Path("test.jpg"),
        size_bytes=12345,
        ext=".jpg",
        drive_letter="D:",
        resolution=(4000, 3000),
        exif_datetime_original="2024:07:15 14:30:00",
        windows_created_time=1700000000.0,
        timestamp_locked="2024-07-15 14:30:00",
        timestamp_source="exif",
        scan_machine_timezone="UTC+8",
    )
    data = file_info.to_dict()
    assert data["ext"] == ".jpg"
    assert data["resolution"] == [4000, 3000]


def test_action_item_serialization() -> None:
    action = ActionItem(
        action="MOVE",
        reason="THUMBNAIL",
        src_path=Path("a.jpg"),
        dst_path=Path("TO_DELETE/THUMBNAILS/a.jpg"),
    )
    data = action.to_dict()
    assert data["action"] == "MOVE"
    assert data["dst_path"] is not None


def test_error_record_levels() -> None:
    error = ProcessError(
        code="W-101",
        level=ErrorLevel.RECOVERABLE,
        message="Permission denied",
        file_path="locked.jpg",
    )
    data = error.to_dict()
    assert data["level"] == "W"
