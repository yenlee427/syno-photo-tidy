"""報告與 manifest 輸出工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from ..models import ManifestEntry


@dataclass
class SummaryInfo:
    run_time: str
    mode: str
    source_dir: str
    output_dir: str
    total_files: int
    total_size_bytes: int
    format_counts: Dict[str, int]
    thumbnail_count: int
    thumbnail_size_bytes: int
    keeper_count: int
    keeper_size_bytes: int
    planned_move_count: int
    cross_drive_copy: bool
    no_changes_needed: bool


def ensure_report_dir(output_root: Path) -> Path:
    report_dir = output_root / "REPORT"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_manifest(report_dir: Path, entries: Iterable[ManifestEntry]) -> Path:
    manifest_path = report_dir / "manifest.jsonl"
    partial_path = report_dir / "manifest.jsonl.partial"
    with partial_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            data = entry.to_dict()
            handle.write(json.dumps(data, ensure_ascii=True) + "\n")
    partial_path.replace(manifest_path)
    return manifest_path


def write_summary(report_dir: Path, info: SummaryInfo) -> Path:
    summary_path = report_dir / "summary.txt"
    summary_path.write_text(build_summary_text(info), encoding="utf-8")
    return summary_path


def build_summary_text(info: SummaryInfo) -> str:
    lines = [
        "=== syno-photo-tidy 執行摘要 ===",
        f"執行時間: {info.run_time}",
        f"模式: {info.mode}",
        f"來源資料夾: {info.source_dir}",
        f"輸出目錄: {info.output_dir}",
        "",
        "--- 掃描結果 ---",
        f"總檔案數: {info.total_files} 個",
        f"總大小: {format_bytes_gb(info.total_size_bytes)}",
        f"影像格式: {format_ext_counts(info.format_counts)}",
        "",
        "--- 縮圖偵測 ---",
        f"偵測為縮圖: {info.thumbnail_count} 個 ({format_bytes_gb(info.thumbnail_size_bytes)})",
        f"保留為原圖: {info.keeper_count} 個 ({format_bytes_gb(info.keeper_size_bytes)})",
        "",
        "--- 行動計畫 ---",
    ]

    if info.no_changes_needed:
        lines.append("No changes needed")
    else:
        lines.append(f"移動到 TO_DELETE/THUMBNAILS/: {info.planned_move_count} 個檔案")

    if info.cross_drive_copy:
        lines.append("警告: cross_drive_copy=true（跨磁碟操作將以 copy 方式進行，來源保留不動）")

    lines.extend(
        [
            "",
            "--- 節省空間 ---",
            f"預計釋放: {format_bytes_gb(info.thumbnail_size_bytes)}",
            "",
            "--- 下一步 ---",
            "此為 Dry-run，未實際移動任何檔案。",
            "若確認無誤，請點擊 [Execute] 執行實際操作。",
        ]
    )

    return "\n".join(lines) + "\n"


def build_summary_info(
    *,
    mode: str,
    source_dir: Path,
    output_dir: Path,
    total_files: int,
    total_size_bytes: int,
    format_counts: Dict[str, int],
    thumbnail_count: int,
    thumbnail_size_bytes: int,
    keeper_count: int,
    keeper_size_bytes: int,
    planned_move_count: int,
    cross_drive_copy: bool,
    no_changes_needed: bool,
) -> SummaryInfo:
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return SummaryInfo(
        run_time=run_time,
        mode=mode,
        source_dir=str(source_dir),
        output_dir=str(output_dir),
        total_files=total_files,
        total_size_bytes=total_size_bytes,
        format_counts=format_counts,
        thumbnail_count=thumbnail_count,
        thumbnail_size_bytes=thumbnail_size_bytes,
        keeper_count=keeper_count,
        keeper_size_bytes=keeper_size_bytes,
        planned_move_count=planned_move_count,
        cross_drive_copy=cross_drive_copy,
        no_changes_needed=no_changes_needed,
    )


def format_bytes_gb(num_bytes: int) -> str:
    gb_value = num_bytes / (1024 ** 3)
    return f"{gb_value:.1f} GB"


def format_ext_counts(counts: Dict[str, int]) -> str:
    if not counts:
        return "無"
    items = []
    for ext, count in sorted(counts.items()):
        label = ext.upper().lstrip(".") or "UNKNOWN"
        items.append(f"{label}({count})")
    return ", ".join(items)
