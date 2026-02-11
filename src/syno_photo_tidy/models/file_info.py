"""掃描階段的檔案資訊模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class FileInfo:
    path: Path
    size_bytes: int
    ext: str
    drive_letter: str
    resolution: Optional[Tuple[int, int]]
    exif_datetime_original: Optional[str]
    windows_created_time: float
    timestamp_locked: str
    timestamp_source: str
    scan_machine_timezone: str
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "ext": self.ext,
            "drive_letter": self.drive_letter,
            "resolution": list(self.resolution) if self.resolution else None,
            "exif_datetime_original": self.exif_datetime_original,
            "windows_created_time": self.windows_created_time,
            "timestamp_locked": self.timestamp_locked,
            "timestamp_source": self.timestamp_source,
            "scan_machine_timezone": self.scan_machine_timezone,
            "hash_md5": self.hash_md5,
            "hash_sha256": self.hash_sha256,
        }
