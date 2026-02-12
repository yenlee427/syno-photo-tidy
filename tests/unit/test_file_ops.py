from pathlib import Path
from unittest.mock import patch

from syno_photo_tidy.utils import file_ops


def test_move_or_copy_move(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "nested" / "dest.txt"
    src.write_text("hello", encoding="utf-8")

    result = file_ops.move_or_copy(src, dst, cross_drive_copy=False)

    assert result == "MOVED"
    assert dst.exists()
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "hello"


def test_move_or_copy_copy(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "nested" / "dest.txt"
    src.write_text("hello", encoding="utf-8")

    result = file_ops.move_or_copy(src, dst, cross_drive_copy=True)

    assert result == "COPIED"
    assert dst.exists()
    assert src.exists()
    assert dst.read_text(encoding="utf-8") == "hello"


def test_rename_file(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "renamed.txt"
    src.write_text("hello", encoding="utf-8")

    result = file_ops.rename_file(src, dst)

    assert result == "RENAMED"
    assert dst.exists()
    assert not src.exists()


def test_safe_copy2_retry_success(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "dest.txt"
    src.write_text("hello", encoding="utf-8")

    with patch("syno_photo_tidy.utils.file_ops.time.sleep", return_value=None), patch(
        "syno_photo_tidy.utils.file_ops.shutil.copy2",
        side_effect=[OSError("Network error"), OSError("Network error"), None],
    ):
        result = file_ops.safe_copy2(
            src,
            dst,
            max_retries=5,
            backoff_base_sec=0.01,
            backoff_cap_sec=0.01,
        )

    assert result.success is True
    assert result.retry_count == 2


def test_safe_copy2_retry_failed(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "dest.txt"
    src.write_text("hello", encoding="utf-8")

    with patch("syno_photo_tidy.utils.file_ops.time.sleep", return_value=None), patch(
        "syno_photo_tidy.utils.file_ops.shutil.copy2",
        side_effect=OSError("Network error"),
    ):
        result = file_ops.safe_copy2(
            src,
            dst,
            max_retries=2,
            backoff_base_sec=0.01,
            backoff_cap_sec=0.01,
        )

    assert result.success is False
    assert result.retry_count == 2
    assert result.error_message is not None
    assert "Network error" in result.error_message
