"""安全檔案操作（move/copy）。"""

from __future__ import annotations

import shutil
from pathlib import Path

from .logger import get_logger


def move_or_copy(
    src_path: Path,
    dst_path: Path,
    *,
    cross_drive_copy: bool,
    logger=None,
) -> str:
    logger = logger or get_logger("FileOps")
    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if cross_drive_copy:
        shutil.copy2(src_path, dst_path)
        logger.info(f"COPIED: {src_path} -> {dst_path}")
        return "COPIED"

    shutil.move(src_path, dst_path)
    logger.info(f"MOVED: {src_path} -> {dst_path}")
    return "MOVED"


def rename_file(src_path: Path, dst_path: Path, logger=None) -> str:
    logger = logger or get_logger("FileOps")
    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst_path}")
    if src_path.parent != dst_path.parent:
        raise ValueError("Rename must stay in the same directory")

    src_path.rename(dst_path)
    logger.info(f"RENAMED: {src_path} -> {dst_path}")
    return "RENAMED"
