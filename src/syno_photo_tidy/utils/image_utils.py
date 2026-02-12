"""影像資訊讀取工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


def _register_heif_opener() -> None:
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:
        return


def get_image_resolution(
    path: Path, logger=None
) -> Optional[Tuple[int, int]]:
    _register_heif_opener()
    try:
        with Image.open(path) as image:
            return image.size
    except Exception as exc:
        if logger is not None:
            logger.warning(f"無法讀取解析度: {path} ({exc})")
        return None


def get_exif_datetime_original(path: Path, logger=None) -> Optional[str]:
    _register_heif_opener()
    try:
        with Image.open(path) as image:
            exif_bytes = image.info.get("exif")
            if not exif_bytes:
                return None
        import piexif

        exif_dict = piexif.load(exif_bytes)
        exif_ifd = exif_dict.get("Exif", {})
        value = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return str(value)
    except Exception as exc:
        if logger is not None:
            logger.warning(f"無法讀取 EXIF: {path} ({exc})")
        return None


def get_exif_data_map(path: Path, logger=None) -> dict[str, str]:
    _register_heif_opener()
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return {}
            result: dict[str, str] = {}
            for tag_id, value in exif.items():
                key = str(tag_id)
                if isinstance(value, bytes):
                    text = value.decode("utf-8", errors="ignore")
                else:
                    text = str(value)
                result[key] = text
            return result
    except Exception as exc:
        if logger is not None:
            logger.warning(f"無法讀取 EXIF map: {path} ({exc})")
        return {}


def compute_phash(path: Path, logger=None):
    _register_heif_opener()
    try:
        import imagehash

        with Image.open(path) as image:
            return imagehash.phash(image)
    except ImportError as exc:
        if logger is not None:
            logger.warning(f"imagehash 未安裝，無法計算 pHash: {exc}")
        return None
    except Exception as exc:
        if logger is not None:
            logger.warning(f"無法計算 pHash: {path} ({exc})")
        return None
