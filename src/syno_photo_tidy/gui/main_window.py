"""主視窗與事件處理。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from dataclasses import replace
from pathlib import Path
from typing import Optional

from ..config import ConfigManager
from ..core import (
    ActionPlanner,
    Archiver,
    ExactDeduper,
    FileScanner,
    ManifestContext,
    PlanExecutor,
    Renamer,
    ThumbnailDetector,
    VisualDeduper,
    append_manifest_entries,
)
from ..utils import path_utils, reporting, time_utils
from ..utils.logger import get_logger
from .settings_panel import SettingsPanel
from .widgets.file_selector import FileSelector
from .widgets.log_viewer import LogViewer
from .widgets.progress_bar import ProgressBar


class MainWindow:
    def __init__(self, config: ConfigManager | None = None) -> None:
        self.config = config or ConfigManager()
        self.logger = get_logger(self.__class__.__name__)
        self.scanner = FileScanner(self.config, self.logger)
        self.thumbnail_detector = ThumbnailDetector(self.config, self.logger)
        self.exact_deduper = ExactDeduper(self.config, self.logger)
        self.visual_deduper = VisualDeduper(self.config, self.logger)
        self.action_planner = ActionPlanner(self.config, self.logger)
        self.renamer = Renamer(self.config, self.logger)
        self.archiver = Archiver(self.config, self.logger)
        self.executor = PlanExecutor(self.logger)
        self.root = tk.Tk()
        self.root.title("syno-photo-tidy")
        self.root.geometry("640x520")

        self.queue: queue.Queue[dict[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self._is_running = False
        self._last_plan = []
        self._last_report_dir: Optional[Path] = None

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_queue)

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        self.source_selector = FileSelector(container, label_text="來源資料夾")
        self.source_selector.pack(fill=tk.X, pady=(0, 6))

        self.output_selector = FileSelector(container, label_text="輸出目錄")
        self.output_selector.pack(fill=tk.X, pady=(0, 6))

        mode_frame = ttk.Frame(container)
        mode_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="Full Run")
        self.mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=["Full Run"],
            state="readonly",
            width=20,
        )
        self.mode_combo.pack(side=tk.LEFT, padx=(6, 0))

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(6, 12))
        self.dry_run_button = ttk.Button(
            button_frame, text="Dry-run Scan", command=self._on_dry_run
        )
        self.dry_run_button.pack(side=tk.LEFT)
        self.execute_button = ttk.Button(
            button_frame, text="Execute", state="disabled", command=self._on_execute
        )
        self.execute_button.pack(side=tk.LEFT, padx=(8, 0))

        self.settings_panel = SettingsPanel(container, self.config)
        self.settings_panel.pack(fill=tk.X, pady=(0, 12))

        self.progress_bar = ProgressBar(container)
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))

        self.stage_label = ttk.Label(container, text="階段: 就緒")
        self.stage_label.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(container, text="日誌:").pack(anchor=tk.W)
        self.log_viewer = LogViewer(container)
        self.log_viewer.pack(fill=tk.BOTH, expand=True)

    def _on_close(self) -> None:
        if self._is_running:
            self.cancel_event.set()
        self.root.destroy()

    def _on_dry_run(self) -> None:
        if self._is_running:
            return
        source_value = self.source_selector.path_var.get().strip()
        if not source_value:
            self.log_viewer.add_line("請先選擇來源資料夾")
            return
        source_path = Path(source_value)
        if not source_path.exists():
            self.log_viewer.add_line("來源資料夾不存在")
            return

        self._is_running = True
        self.cancel_event.clear()
        self.dry_run_button.configure(state="disabled")
        self.log_viewer.add_line("開始掃描...")
        self.progress_bar.update_progress(0)
        worker = threading.Thread(target=self._run_scan, args=(source_path,), daemon=True)
        worker.start()

    def _run_scan(self, source_path: Path) -> None:
        self.queue.put({"type": "stage", "message": "階段: Scanning..."})

        def report_progress(count: int) -> None:
            self.queue.put({"type": "stage", "message": f"階段: Scanning... ({count})"})
            self.queue.put({"type": "progress", "value": min(99, count % 100)})

        results = self.scanner.scan_directory(
            source_path,
            cancel_event=self.cancel_event,
            progress_callback=report_progress,
        )

        if self.cancel_event.is_set():
            self.queue.put({"type": "log", "message": "已取消作業"})
            self.queue.put({"type": "stage", "message": "階段: 已取消"})
            self.queue.put({"type": "done"})
            return

        self.queue.put({"type": "log", "message": f"掃描完成，共 {len(results)} 個檔案"})
        self.queue.put({"type": "stage", "message": "階段: Thumbnail detection..."})

        keepers, thumbnails = self.thumbnail_detector.classify_files(results)
        self.queue.put(
            {
                "type": "log",
                "message": f"偵測到 {len(thumbnails)} 個縮圖",
            }
        )

        self.queue.put({"type": "stage", "message": "階段: Exact hash dedupe..."})
        dedupe_result = self.exact_deduper.dedupe(keepers)
        keepers = dedupe_result.keepers
        exact_duplicates = dedupe_result.duplicates
        self.queue.put(
            {
                "type": "log",
                "message": f"偵測到 {len(exact_duplicates)} 個精確重複檔案",
            }
        )

        self.queue.put({"type": "stage", "message": "階段: Visual hash dedupe..."})
        visual_result = self.visual_deduper.dedupe(keepers)
        keepers = visual_result.keepers
        visual_duplicates = visual_result.duplicates
        self.queue.put(
            {
                "type": "log",
                "message": f"偵測到 {len(visual_duplicates)} 個相似重複檔案",
            }
        )

        self.queue.put({"type": "stage", "message": "階段: Renaming..."})
        rename_result = self.renamer.generate_plan(keepers)
        self.queue.put(
            {
                "type": "log",
                "message": f"計畫重新命名 {len(rename_result.plan)} 個檔案",
            }
        )

        rename_map = {
            item.src_path: item.dst_path
            for item in rename_result.plan
            if item.dst_path is not None
        }
        renamed_keepers = [
            replace(item, path=rename_map.get(item.path, item.path)) for item in keepers
        ]

        self.queue.put({"type": "stage", "message": "階段: Archiving..."})
        archive_result = self.archiver.generate_plan(renamed_keepers, output_root)
        self.queue.put(
            {
                "type": "log",
                "message": f"計畫封存 {len(archive_result.plan)} 個檔案",
            }
        )

        output_value = self.output_selector.path_var.get().strip()
        if output_value:
            output_root = Path(output_value)
        else:
            timestamp = time_utils.get_timestamp_for_folder()
            output_root = source_path / f"Processed_{timestamp}"

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
        no_changes = self.action_planner.is_no_changes_needed(full_plan)
        if no_changes:
            self.queue.put({"type": "log", "message": "No changes needed"})

        total_size = sum(item.size_bytes for item in results)
        thumbnail_size = sum(item.size_bytes for item in thumbnails)
        keeper_size = sum(item.size_bytes for item in keepers)
        exact_duplicate_size = sum(item.size_bytes for item in exact_duplicates)
        visual_duplicate_size = sum(item.size_bytes for item in visual_duplicates)
        format_counts: dict[str, int] = {}
        for item in results:
            format_counts[item.ext] = format_counts.get(item.ext, 0) + 1

        cross_drive_copy = path_utils.is_cross_drive(source_path, output_root)
        summary_info = reporting.build_summary_info(
            mode=f"{self.mode_var.get()} (Dry-run)",
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
            cross_drive_copy=cross_drive_copy,
            no_changes_needed=no_changes,
        )

        report_dir = reporting.ensure_report_dir(output_root)
        reporting.write_summary(report_dir, summary_info)
        manifest_context = ManifestContext.from_run(
            run_id=output_root.name,
            mode=f"{self.mode_var.get()} (Dry-run)",
            source_dir=source_path,
            output_dir=output_root,
        )
        rename_entries = self.action_planner.build_manifest_entries(rename_result.plan, keepers)
        archive_entries = self.action_planner.build_manifest_entries(
            archive_result.plan,
            renamed_keepers,
        )
        reporting.write_manifest(
            report_dir,
            rename_entries + archive_entries + plan_result.manifest_entries,
            context=manifest_context,
        )

        self.queue.put({"type": "progress", "value": 100})
        self.queue.put({"type": "stage", "message": "階段: 完成"})
        self.queue.put({"type": "enable_execute", "value": not no_changes})
        self.queue.put({"type": "done"})

        self._last_plan = full_plan
        self._last_report_dir = report_dir

    def _on_execute(self) -> None:
        if self._is_running:
            return
        if not self._last_plan or self._last_report_dir is None:
            self.log_viewer.add_line("請先完成 Dry-run Scan")
            return

        self._is_running = True
        self.cancel_event.clear()
        self.dry_run_button.configure(state="disabled")
        self.execute_button.configure(state="disabled")
        self.log_viewer.add_line("開始執行...")
        self.progress_bar.update_progress(0)
        worker = threading.Thread(target=self._run_execute, daemon=True)
        worker.start()

    def _run_execute(self) -> None:
        self.queue.put({"type": "stage", "message": "階段: Executing..."})
        result = self.executor.execute_plan(self._last_plan, cancel_event=self.cancel_event)
        entries = result.executed_entries + result.failed_entries
        if self._last_report_dir is not None and entries:
            manifest_path = self._last_report_dir / "manifest.jsonl"
            append_manifest_entries(manifest_path, entries, logger=self.logger)

        if result.cancelled:
            self.queue.put({"type": "log", "message": "已取消執行"})
        else:
            self.queue.put(
                {
                    "type": "log",
                    "message": f"執行完成：成功 {len(result.executed_entries)}，失敗 {len(result.failed_entries)}",
                }
            )

        self.queue.put({"type": "enable_execute", "value": False})
        self.queue.put({"type": "progress", "value": 100})
        self.queue.put({"type": "stage", "message": "階段: 完成"})
        self.queue.put({"type": "done"})

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                item_type = item.get("type")
                if item_type == "log":
                    self.log_viewer.add_line(str(item.get("message")))
                elif item_type == "progress":
                    self.progress_bar.update_progress(int(item.get("value", 0)))
                elif item_type == "stage":
                    self.stage_label.configure(text=str(item.get("message")))
                elif item_type == "enable_execute":
                    state = "normal" if item.get("value") else "disabled"
                    self.execute_button.configure(state=state)
                elif item_type == "done":
                    self._is_running = False
                    self.dry_run_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def run(self) -> None:
        self.root.mainloop()
