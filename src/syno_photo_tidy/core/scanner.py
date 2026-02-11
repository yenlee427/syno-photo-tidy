"""檔案掃描與 metadata 收集。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from ..config import ConfigManager
from ..models import FileInfo
from ..utils import image_utils, path_utils, time_utils
from ..utils.logger import get_logger


class FileScanner:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.config = config
        self.logger = logger or get_logger(self.__class__.__name__)

    def should_exclude_path(self, path: Path) -> bool:
        return path_utils.should_exclude_path(path, self.logger)

    def scan_directory(
        self,
        root: Path,
        cancel_event=None,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> list[FileInfo]:
        results: list[FileInfo] = []
        if not root.exists():
            return results

        processed = 0
        for dirpath, dirnames, filenames in os.walk(root):
            current_dir = Path(dirpath)
            if self.should_exclude_path(current_dir):
                dirnames[:] = []
                continue

            filtered_dirs: list[str] = []
            for name in dirnames:
                candidate = current_dir / name
                if self.should_exclude_path(candidate):
                    continue
                filtered_dirs.append(name)
            dirnames[:] = filtered_dirs

            for name in filenames:
                if cancel_event is not None and cancel_event.is_set():
                    return results

                file_path = current_dir / name
                if self.should_exclude_path(file_path):
                    continue
                if not file_path.is_file():
                    continue

                file_info = self._build_file_info(file_path)
                if file_info is not None:
                    results.append(file_info)

                processed += 1
                if progress_callback:
                    progress_callback(processed)

        return results

    def _build_file_info(self, path: Path) -> Optional[FileInfo]:
        try:
            stat = path.stat()
            size_bytes = stat.st_size
            windows_created_time = stat.st_ctime
        except OSError as exc:
            self.logger.warning(f"無法讀取檔案資訊: {path} ({exc})")
            return None

        ext = path.suffix.lower()
        drive_letter = (path.drive or path.anchor).upper()

        resolution = image_utils.get_image_resolution(path, self.logger)
        exif_datetime_original = image_utils.get_exif_datetime_original(path, self.logger)
        timestamp_locked, timestamp_source = time_utils.lock_timestamp(
            exif_datetime_original, windows_created_time
        )
        scan_machine_timezone = time_utils.get_scan_timezone()

        return FileInfo(
            path=path,
            size_bytes=size_bytes,
            ext=ext,
            drive_letter=drive_letter,
            resolution=resolution,
            exif_datetime_original=exif_datetime_original,
            windows_created_time=windows_created_time,
            timestamp_locked=timestamp_locked,
            timestamp_source=timestamp_source,
            scan_machine_timezone=scan_machine_timezone,
        )
