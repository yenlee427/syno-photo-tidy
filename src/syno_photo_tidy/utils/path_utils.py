"""路徑處理工具。"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path


def should_exclude_path(path: Path, logger=None) -> bool:
    excluded_patterns = [
        "Processed_*",
        "TO_DELETE",
        "KEEP",
        "REPORT",
        "ROLLBACK_TRASH",
        "ROLLBACK_CONFLICTS",
    ]

    for part in path.parts:
        for pattern in excluded_patterns:
            if fnmatch.fnmatch(part, pattern):
                return True

    try:
        if path.is_symlink() or os.path.islink(path):
            if logger is not None:
                logger.info(f"SKIPPED_SYMLINK: {path}")
            return True
    except OSError:
        if logger is not None:
            logger.info(f"SKIPPED_SYMLINK: {path}")
        return True

    return False


def is_cross_drive(src_path: Path, dst_path: Path) -> bool:
    return src_path.anchor.upper() != dst_path.anchor.upper()
