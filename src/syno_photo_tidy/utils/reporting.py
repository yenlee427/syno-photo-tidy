"""報告與 manifest 輸出工具。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable

from ..core.manifest import ManifestContext, ManifestWriter
from ..models import ManifestEntry


REPORT_FIELDNAMES = [
    "op_id",
    "action",
    "src_path",
    "dst_path",
    "status",
    "reason",
    "error_code",
    "error_message",
    "retry_count",
    "elapsed_time_sec",
    "size_bytes",
    "resolution",
    "hash_md5",
    "hash_sha256",
    "timestamp_locked",
    "timestamp_source",
    "file_type",
    "is_live_pair",
    "pair_id",
    "pair_confidence",
    "is_screenshot",
    "screenshot_evidence",
]


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
    exact_duplicate_count: int
    exact_duplicate_size_bytes: int
    visual_duplicate_count: int
    visual_duplicate_size_bytes: int
    planned_thumbnail_move_count: int
    planned_duplicate_move_count: int
    cross_drive_copy: bool
    no_changes_needed: bool


def ensure_report_dir(output_root: Path) -> Path:
    report_dir = output_root / "REPORT"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_manifest(
    report_dir: Path,
    entries: Iterable[ManifestEntry],
    *,
    context: ManifestContext | None = None,
) -> Path:
    if context is None:
        context = ManifestContext(
            run_id="",
            mode="",
            source_dir="",
            output_dir="",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries(entries)
        manifest_path = writer.manifest_path
    return manifest_path


def write_summary(report_dir: Path, info: SummaryInfo) -> Path:
    summary_path = report_dir / "summary.txt"
    summary_path.write_text(build_summary_text(info), encoding="utf-8")
    return summary_path


def write_report_csv(report_dir: Path, entries: Iterable[ManifestEntry]) -> Path:
    report_path = report_dir / "report.csv"
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        for entry in entries:
            payload = entry.to_dict()
            row: dict[str, object] = {}
            for field in REPORT_FIELDNAMES:
                row[field] = payload.get(field)
            writer.writerow(row)
    return report_path


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
        "--- 去重結果 ---",
        f"精確去重: {info.exact_duplicate_count} 個 ({format_bytes_gb(info.exact_duplicate_size_bytes)})",
        f"相似去重: {info.visual_duplicate_count} 個 ({format_bytes_gb(info.visual_duplicate_size_bytes)})",
        "",
        "--- 行動計畫 ---",
    ]

    if info.no_changes_needed:
        lines.append("No changes needed")
    else:
        lines.append(
            f"移動到 TO_DELETE/THUMBNAILS/: {info.planned_thumbnail_move_count} 個檔案"
        )
        lines.append(
            f"移動到 TO_DELETE/DUPLICATES/: {info.planned_duplicate_move_count} 個檔案"
        )

    if info.cross_drive_copy:
        lines.append("警告: cross_drive_copy=true（跨磁碟操作將以 copy 方式進行，來源保留不動）")

    saved_bytes = (
        info.thumbnail_size_bytes
        + info.exact_duplicate_size_bytes
        + info.visual_duplicate_size_bytes
    )
    lines.extend(
        [
            "",
            "--- 節省空間 ---",
            f"預計釋放: {format_bytes_gb(saved_bytes)}",
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
    exact_duplicate_count: int = 0,
    exact_duplicate_size_bytes: int = 0,
    visual_duplicate_count: int = 0,
    visual_duplicate_size_bytes: int = 0,
    planned_thumbnail_move_count: int = 0,
    planned_duplicate_move_count: int = 0,
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
        exact_duplicate_count=exact_duplicate_count,
        exact_duplicate_size_bytes=exact_duplicate_size_bytes,
        visual_duplicate_count=visual_duplicate_count,
        visual_duplicate_size_bytes=visual_duplicate_size_bytes,
        planned_thumbnail_move_count=planned_thumbnail_move_count,
        planned_duplicate_move_count=planned_duplicate_move_count,
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
