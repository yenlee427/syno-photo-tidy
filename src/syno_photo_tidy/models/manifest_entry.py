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
    op_id: Optional[str] = None
    reason: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    elapsed_time_sec: float = 0.0
    size_bytes: Optional[int] = None
    resolution: Optional[Tuple[int, int]] = None
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    timestamp_locked: Optional[str] = None
    timestamp_source: Optional[str] = None
    file_type: Optional[str] = None
    is_live_pair: bool = False
    pair_id: Optional[str] = None
    pair_confidence: Optional[str] = None
    is_screenshot: bool = False
    screenshot_evidence: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "op_id": self.op_id,
            "action": self.action,
            "src_path": self.src_path,
            "dst_path": self.dst_path,
            "status": self.status,
            "reason": self.reason,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "elapsed_time_sec": self.elapsed_time_sec,
            "size_bytes": self.size_bytes,
            "resolution": list(self.resolution) if self.resolution else None,
            "hash_md5": self.hash_md5,
            "hash_sha256": self.hash_sha256,
            "timestamp_locked": self.timestamp_locked,
            "timestamp_source": self.timestamp_source,
            "file_type": self.file_type,
            "is_live_pair": self.is_live_pair,
            "pair_id": self.pair_id,
            "pair_confidence": self.pair_confidence,
            "is_screenshot": self.is_screenshot,
            "screenshot_evidence": self.screenshot_evidence,
        }
