"""時間戳處理工具。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple


def format_exif_time(value: str) -> Optional[str]:
    try:
        parsed = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def lock_timestamp(
    exif_datetime_original: Optional[str],
    windows_created_time: float,
) -> Tuple[str, str]:
    if exif_datetime_original:
        formatted = format_exif_time(exif_datetime_original)
        if formatted:
            return formatted, "exif"

    if windows_created_time:
        dt = datetime.fromtimestamp(windows_created_time)
        return dt.strftime("%Y-%m-%d %H:%M:%S"), "created_time"

    return "1970-01-01 00:00:00", "unknown"


def get_scan_timezone() -> str:
    now = datetime.now().astimezone()
    offset = now.utcoffset() or timezone.utc.utcoffset(now)
    if offset is None:
        return "UTC+0"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours = abs(total_minutes) // 60
    return f"UTC{sign}{hours}"


def get_timestamp_for_folder() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
