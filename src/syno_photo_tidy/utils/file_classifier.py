"""檔案類型分類工具。"""

from __future__ import annotations

from ..models import FileInfo


def classify_file_type(file_info: FileInfo, config=None) -> str:
    ext = (file_info.ext or "").lower()

    image_exts = {
        ".jpg",
        ".jpeg",
        ".png",
        ".heic",
        ".heif",
        ".tif",
        ".tiff",
        ".bmp",
        ".gif",
    }
    video_exts = {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".wmv",
        ".flv",
        ".m4v",
        ".3gp",
    }

    if config is not None:
        configured_images = config.get("file_extensions.image", [])
        configured_videos = config.get("file_extensions.video", [])
        image_exts = {str(item).lower() for item in configured_images}
        video_exts = {str(item).lower() for item in configured_videos}

    if ext in image_exts:
        return "IMAGE"
    if ext in video_exts:
        return "VIDEO"
    return "OTHER"
