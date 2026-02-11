"""Manifest 記錄骨架（v0.2 擴充）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ManifestEntry:
    action: str
    src_path: str
    dst_path: Optional[str]
    status: str
    reason: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "src_path": self.src_path,
            "dst_path": self.dst_path,
            "status": self.status,
            "reason": self.reason,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }
