"""Manifest 記錄骨架（v0.2 擴充）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ManifestEntry:
    action: str
    src_path: str
    dst_path: Optional[str]
    status: str
    reason: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    size_bytes: Optional[int] = None
    resolution: Optional[Tuple[int, int]] = None
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    timestamp_locked: Optional[str] = None
    timestamp_source: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "src_path": self.src_path,
            "dst_path": self.dst_path,
            "status": self.status,
            "reason": self.reason,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "size_bytes": self.size_bytes,
            "resolution": list(self.resolution) if self.resolution else None,
            "hash_md5": self.hash_md5,
            "hash_sha256": self.hash_sha256,
            "timestamp_locked": self.timestamp_locked,
            "timestamp_source": self.timestamp_source,
        }
