"""螢幕截圖判定引擎。"""

from __future__ import annotations

from fnmatch import fnmatch

from PIL import Image

from ..config import ConfigManager
from ..models import FileInfo
from ..utils.logger import get_logger


class ScreenshotDetector:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.config = config
        self.logger = logger or get_logger(self.__class__.__name__)

    def is_screenshot(self, file_info: FileInfo, mode: str | None = None) -> tuple[bool, str | None]:
        resolved_mode = (mode or self.config.get("screenshot_detection_mode", "strict")).lower()

        evidence = self.detect_from_metadata(file_info)
        if evidence:
            return True, evidence

        if resolved_mode == "relaxed":
            evidence = self.detect_from_filename(file_info)
            if evidence:
                return True, evidence

        return False, None

    def detect_from_metadata(self, file_info: FileInfo) -> str | None:
        keywords = [
            str(item).lower() for item in self.config.get("screenshot_metadata_keywords", ["screenshot"])
        ]
        text_parts: list[str] = []

        if file_info.exif_data:
            for key, value in file_info.exif_data.items():
                if value:
                    text_parts.append(f"{key}={value}")

        if file_info.ext.lower() == ".png":
            try:
                with Image.open(file_info.path) as image:
                    info = getattr(image, "info", {}) or {}
                    for key, value in info.items():
                        if value:
                            text_parts.append(f"{key}={value}")
            except Exception as exc:
                self.logger.warning("讀取 PNG metadata 失敗: %s (%s)", file_info.path, exc)

        text_blob = " | ".join(text_parts).lower()
        for keyword in keywords:
            if keyword and keyword in text_blob:
                return f"metadata_keyword_match:{keyword}"
        return None

    def detect_from_filename(self, file_info: FileInfo) -> str | None:
        patterns = self.config.get("screenshot_filename_patterns", ["*Screenshot*", "*螢幕截圖*"])
        name = file_info.path.name
        for pattern in patterns:
            if fnmatch(name.lower(), str(pattern).lower()):
                return f"filename_pattern_match:{pattern}"
        return None
