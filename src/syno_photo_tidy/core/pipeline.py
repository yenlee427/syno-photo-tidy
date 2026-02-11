"""Pipeline coordinator for dry-run planning."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, List, Optional

from ..config import ConfigManager
from ..models import ActionItem, FileInfo, ManifestEntry
from ..utils import path_utils, reporting
from ..utils.logger import get_logger
from .action_planner import ActionPlanner
from .archiver import Archiver
from .exact_deduper import ExactDeduper
from .renamer import Renamer
from .scanner import FileScanner
from .thumbnail_detector import ThumbnailDetector
from .visual_deduper import VisualDeduper


@dataclass
class PipelineResult:
    plan: List[ActionItem]
    plan_groups: list[tuple[str, list[ActionItem]]]
    summary_info: reporting.SummaryInfo
    report_dir: Path
    manifest_entries: List[ManifestEntry]


class Pipeline:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)
        self.scanner = FileScanner(config, self.logger)
        self.thumbnail_detector = ThumbnailDetector(config, self.logger)
        self.exact_deduper = ExactDeduper(config, self.logger)
        self.visual_deduper = VisualDeduper(config, self.logger)
        self.renamer = Renamer(config, self.logger)
        self.archiver = Archiver(config, self.logger)
        self.action_planner = ActionPlanner(config, self.logger)

    def run_dry_run(
        self,
        source_path: Path,
        output_root: Path,
        *,
        mode: str,
        cancel_event=None,
        progress_callback: Optional[Callable[[int], None]] = None,
        stage_callback: Optional[Callable[[str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        detail_callback: Optional[Callable[[str], None]] = None,
    ) -> PipelineResult:
        stage_callback = stage_callback or (lambda _message: None)
        log_callback = log_callback or (lambda _message: None)
        detail_callback = detail_callback or (lambda _message: None)

        weights = {
            "scan": 40,
            "thumb": 10,
            "exact": 15,
            "visual": 15,
            "rename": 10,
            "archive": 10,
        }
        total_weight = 0

        def update_weighted_progress(weight: int, current: int, total: int) -> None:
            if progress_callback is None:
                return
            total_value = max(1, total)
            percent = total_weight + int(weight * current / total_value)
            progress_callback(min(99, percent))

        stage_callback("階段: Pre-scan...")
        total_files = self.scanner.count_files(
            source_path,
            cancel_event=cancel_event,
        )
        detail_callback(f"預估檔案數量: {total_files}")
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Cancelled")

        stage_callback("階段: Scanning...")
        processed_scan = 0
        results = self.scanner.scan_directory(
            source_path,
            cancel_event=cancel_event,
            progress_callback=lambda count: (
                update_weighted_progress(weights["scan"], count, total_files),
                detail_callback(f"已掃描 {count}/{total_files}"),
            ),
        )
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Cancelled")
        total_weight += weights["scan"]
        if progress_callback is not None:
            progress_callback(min(99, total_weight))

        log_callback(f"掃描完成，共 {len(results)} 個檔案")
        stage_callback("階段: Thumbnail detection...")
        keepers, thumbnails = self.thumbnail_detector.classify_files(results)
        total_weight += weights["thumb"]
        if progress_callback is not None:
            progress_callback(min(99, total_weight))
        log_callback(f"偵測到 {len(thumbnails)} 個縮圖")

        stage_callback("階段: Exact hash dedupe...")
        dedupe_result = self.exact_deduper.dedupe(
            keepers,
            progress_callback=lambda count: update_weighted_progress(
                weights["exact"],
                count,
                len(keepers),
            ),
        )
        keepers = dedupe_result.keepers
        exact_duplicates = dedupe_result.duplicates
        total_weight += weights["exact"]
        if progress_callback is not None:
            progress_callback(min(99, total_weight))
        log_callback(f"偵測到 {len(exact_duplicates)} 個精確重複檔案")

        stage_callback("階段: Visual hash dedupe...")
        visual_result = self.visual_deduper.dedupe(
            keepers,
            progress_callback=lambda count: update_weighted_progress(
                weights["visual"],
                count,
                len(keepers),
            ),
        )
        keepers = visual_result.keepers
        visual_duplicates = visual_result.duplicates
        total_weight += weights["visual"]
        if progress_callback is not None:
            progress_callback(min(99, total_weight))
        log_callback(f"偵測到 {len(visual_duplicates)} 個相似重複檔案")

        stage_callback("階段: Renaming...")
        rename_result = self.renamer.generate_plan(
            keepers,
            progress_callback=lambda count: update_weighted_progress(
                weights["rename"],
                count,
                len(keepers),
            ),
        )
        log_callback(f"計畫重新命名 {len(rename_result.plan)} 個檔案")
        total_weight += weights["rename"]
        if progress_callback is not None:
            progress_callback(min(99, total_weight))

        rename_map = {
            item.src_path: item.dst_path
            for item in rename_result.plan
            if item.dst_path is not None
        }
        renamed_keepers = [
            replace(item, path=rename_map.get(item.path, item.path)) for item in keepers
        ]

        stage_callback("階段: Archiving...")
        archive_result = self.archiver.generate_plan(
            renamed_keepers,
            output_root,
            progress_callback=lambda count: update_weighted_progress(
                weights["archive"],
                count,
                len(renamed_keepers),
            ),
        )
        log_callback(f"計畫封存 {len(archive_result.plan)} 個檔案")
        total_weight += weights["archive"]
        if progress_callback is not None:
            progress_callback(min(99, total_weight))

        duplicates_with_reason = (
            [(item, "DUPLICATE_HASH") for item in exact_duplicates]
            + [(item, "DUPLICATE_PHASH") for item in visual_duplicates]
        )
        plan_result = self.action_planner.generate_plan(
            keepers,
            thumbnails,
            source_root=source_path,
            output_root=output_root,
            duplicates_with_reason=duplicates_with_reason,
        )

        full_plan = rename_result.plan + archive_result.plan + plan_result.plan
        plan_groups = [
            ("Renaming", rename_result.plan),
            ("Archiving", archive_result.plan),
            ("Moving", plan_result.plan),
        ]

        total_size = sum(item.size_bytes for item in results)
        thumbnail_size = sum(item.size_bytes for item in thumbnails)
        keeper_size = sum(item.size_bytes for item in keepers)
        exact_duplicate_size = sum(item.size_bytes for item in exact_duplicates)
        visual_duplicate_size = sum(item.size_bytes for item in visual_duplicates)
        format_counts: dict[str, int] = {}
        for item in results:
            format_counts[item.ext] = format_counts.get(item.ext, 0) + 1

        summary_info = reporting.build_summary_info(
            mode=mode,
            source_dir=source_path,
            output_dir=output_root,
            total_files=len(results),
            total_size_bytes=total_size,
            format_counts=format_counts,
            thumbnail_count=len(thumbnails),
            thumbnail_size_bytes=thumbnail_size,
            keeper_count=len(keepers),
            keeper_size_bytes=keeper_size,
            exact_duplicate_count=len(exact_duplicates),
            exact_duplicate_size_bytes=exact_duplicate_size,
            visual_duplicate_count=len(visual_duplicates),
            visual_duplicate_size_bytes=visual_duplicate_size,
            planned_thumbnail_move_count=len(thumbnails),
            planned_duplicate_move_count=len(exact_duplicates) + len(visual_duplicates),
            cross_drive_copy=path_utils.is_cross_drive(source_path, output_root),
            no_changes_needed=self.action_planner.is_no_changes_needed(full_plan),
        )

        report_dir = reporting.ensure_report_dir(output_root)
        rename_entries = self.action_planner.build_manifest_entries(rename_result.plan, keepers)
        archive_entries = self.action_planner.build_manifest_entries(archive_result.plan, renamed_keepers)
        manifest_entries = rename_entries + archive_entries + plan_result.manifest_entries

        return PipelineResult(
            plan=full_plan,
            plan_groups=plan_groups,
            summary_info=summary_info,
            report_dir=report_dir,
            manifest_entries=manifest_entries,
        )
