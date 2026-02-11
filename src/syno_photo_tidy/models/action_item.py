"""Dry-run 行動計畫項目。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ActionItem:
    action: str
    reason: str
    src_path: Path
    dst_path: Optional[Path] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "src_path": str(self.src_path),
            "dst_path": str(self.dst_path) if self.dst_path else None,
        }
