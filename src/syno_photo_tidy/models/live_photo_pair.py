"""Live Photo 配對資料模型。"""

from __future__ import annotations

from dataclasses import dataclass

from .file_info import FileInfo


@dataclass
class LivePhotoPair:
    image: FileInfo
    video: FileInfo
    pair_id: str
    confidence: str
    time_diff_sec: float
