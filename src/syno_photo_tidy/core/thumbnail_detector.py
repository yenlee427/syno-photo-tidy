"""縮圖判定邏輯。"""

from __future__ import annotations

from typing import Optional, Tuple

from ..config import ConfigManager
from ..utils.logger import get_logger


class ThumbnailDetector:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)
        self.max_size_kb = int(config.get("thumbnail.max_size_kb"))
        self.max_dimension_px = int(config.get("thumbnail.max_dimension_px"))
        self.min_dimension_px = int(config.get("thumbnail.min_dimension_px"))

    def is_thumbnail(self, file_info) -> bool:
        resolution: Optional[Tuple[int, int]] = getattr(file_info, "resolution", None)
        if resolution is None:
            path = getattr(file_info, "path", "(unknown)")
            self.logger.warning(f"CANNOT_DETERMINE_RESOLUTION: {path}")
            return False

        width, height = resolution
        max_dimension = max(width, height)

        if max_dimension <= self.min_dimension_px:
            return True

        size_bytes = int(getattr(file_info, "size_bytes", 0))
        if size_bytes <= self.max_size_kb * 1000 and max_dimension <= self.max_dimension_px:
            return True

        return False

    def classify_files(self, files: list) -> tuple[list, list]:
        keepers = []
        thumbnails = []
        for item in files:
            if self.is_thumbnail(item):
                thumbnails.append(item)
            else:
                keepers.append(item)
        return keepers, thumbnails
