from pathlib import Path

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
