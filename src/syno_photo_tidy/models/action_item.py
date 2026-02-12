"""Dry-run 行動計畫項目。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .file_info import FileInfo


@dataclass
class ActionItem:
    action: str
    reason: str
    src_path: Path
    dst_path: Optional[Path] = None
    new_name: Optional[str] = None
    rename_base: Optional[str] = None
    src_file: Optional[FileInfo] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "src_path": str(self.src_path),
            "dst_path": str(self.dst_path) if self.dst_path else None,
            "new_name": self.new_name,
            "rename_base": self.rename_base,
        }
