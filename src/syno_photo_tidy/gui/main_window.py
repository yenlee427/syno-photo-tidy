"""主視窗與事件處理。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Optional

from ..config import ConfigManager
from ..core import (
    ManifestContext,
    Pipeline,
    PlanExecutor,
    RollbackRunner,
    append_manifest_entries,
)
from ..utils import reporting, time_utils
from ..utils.logger import get_logger
from .settings_panel import SettingsPanel
from .progress_dialog import ProgressDialog
from .rollback_dialog import RollbackDialog
from .widgets.file_selector import FileSelector
from .widgets.log_viewer import LogViewer
from .widgets.progress_bar import ProgressBar


class MainWindow:
    def __init__(self, config: ConfigManager | None = None) -> None:
        self.config = config or ConfigManager()
        self.logger = get_logger(self.__class__.__name__)
        self.pipeline = Pipeline(self.config, self.logger)
        self.executor = PlanExecutor(self.logger)
        self.rollback_runner = RollbackRunner(self.logger)
        self.root = tk.Tk()
        self.root.title("syno-photo-tidy")
        self.root.geometry("640x520")

        self.queue: queue.Queue[dict[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self._is_running = False
        self._last_plan = []
        self._last_plan_groups: list[tuple[str, list]] = []
        self._last_report_dir: Optional[Path] = None
        self._progress_dialog: Optional[ProgressDialog] = None

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
        self.rollback_button = ttk.Button(
            button_frame, text="Rollback Last Run", command=self._on_rollback
        )
        self.rollback_button.pack(side=tk.LEFT, padx=(8, 0))

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
        self._open_progress_dialog(title="Dry-run", allow_cancel=True)
        self.log_viewer.add_line("開始掃描...")
        self.progress_bar.update_progress(0)
        worker = threading.Thread(target=self._run_scan, args=(source_path,), daemon=True)
        worker.start()

    def _run_scan(self, source_path: Path) -> None:
        def report_progress(count: int) -> None:
            self.queue.put({"type": "detail", "message": f"已掃描 {count} 個檔案"})
            self.queue.put({"type": "progress", "value": min(99, count % 100)})

        output_value = self.output_selector.path_var.get().strip()
        if output_value:
            output_root = Path(output_value)
        else:
            timestamp = time_utils.get_timestamp_for_folder()
            output_root = source_path / f"Processed_{timestamp}"

        try:
            pipeline_result = self.pipeline.run_dry_run(
                source_path,
                output_root,
                mode=f"{self.mode_var.get()} (Dry-run)",
                cancel_event=self.cancel_event,
                progress_callback=report_progress,
                stage_callback=lambda message: self.queue.put(
                    {"type": "stage", "message": message}
                ),
                log_callback=lambda message: self.queue.put(
                    {"type": "log", "message": message}
                ),
            )
        except RuntimeError:
            self.queue.put({"type": "log", "message": "已取消作業"})
            self.queue.put({"type": "stage", "message": "階段: 已取消"})
            self.queue.put({"type": "done"})
            return

        if pipeline_result.summary_info.no_changes_needed:
            self.queue.put({"type": "log", "message": "No changes needed"})

        reporting.write_summary(pipeline_result.report_dir, pipeline_result.summary_info)
        manifest_context = ManifestContext.from_run(
            run_id=output_root.name,
            mode=f"{self.mode_var.get()} (Dry-run)",
            source_dir=source_path,
            output_dir=output_root,
        )
        reporting.write_manifest(
            pipeline_result.report_dir,
            pipeline_result.manifest_entries,
            context=manifest_context,
        )

        self.queue.put({"type": "progress", "value": 100})
        self.queue.put({"type": "stage", "message": "階段: 完成"})
        self.queue.put(
            {
                "type": "enable_execute",
                "value": not pipeline_result.summary_info.no_changes_needed,
            }
        )
        self.queue.put({"type": "done"})

        self._last_plan = pipeline_result.plan
        self._last_plan_groups = pipeline_result.plan_groups
        self._last_report_dir = pipeline_result.report_dir

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
        self._open_progress_dialog(title="Execute", allow_cancel=True)
        self.log_viewer.add_line("開始執行...")
        self.progress_bar.update_progress(0)
        worker = threading.Thread(target=self._run_execute, daemon=True)
        worker.start()

    def _on_rollback(self) -> None:
        if self._is_running:
            return
        processed_dir = self._select_rollback_dir()
        if processed_dir is None:
            return

        self._is_running = True
        self.cancel_event.clear()
        self.dry_run_button.configure(state="disabled")
        self.execute_button.configure(state="disabled")
        self.rollback_button.configure(state="disabled")
        self._open_progress_dialog(title="Rollback", allow_cancel=False)
        self.log_viewer.add_line("開始回滾...")
        self.progress_bar.update_progress(0)
        worker = threading.Thread(
            target=self._run_rollback,
            args=(processed_dir,),
            daemon=True,
        )
        worker.start()

    def _run_rollback(self, processed_dir: Path) -> None:
        self.queue.put({"type": "stage", "message": "階段: Rolling back..."})
        result = self.rollback_runner.rollback(processed_dir)
        self.queue.put(
            {
                "type": "log",
                "message": (
                    "回滾完成：還原 {rolled}，移入垃圾 {trashed}，衝突 {conflicts}，"
                    "跳過 {skipped}，失敗 {failed}"
                ).format(
                    rolled=len(result.rolled_back),
                    trashed=len(result.trashed),
                    conflicts=len(result.conflicts),
                    skipped=len(result.skipped),
                    failed=len(result.failed),
                ),
            }
        )
        self.queue.put({"type": "progress", "value": 100})
        self.queue.put({"type": "stage", "message": "階段: 完成"})
        self.queue.put({"type": "done"})

    def _run_execute(self) -> None:
        executed_entries = []
        failed_entries = []
        cancelled = False
        for label, plan in self._last_plan_groups:
            if not plan:
                continue
            self.queue.put({"type": "stage", "message": f"階段: {label}..."})
            result = self.executor.execute_plan(plan, cancel_event=self.cancel_event)
            executed_entries.extend(result.executed_entries)
            failed_entries.extend(result.failed_entries)
            if result.cancelled:
                cancelled = True
                break

        entries = executed_entries + failed_entries
        if self._last_report_dir is not None and entries:
            manifest_path = self._last_report_dir / "manifest.jsonl"
            append_manifest_entries(manifest_path, entries, logger=self.logger)

        if cancelled:
            self.queue.put({"type": "log", "message": "已取消執行"})
        else:
            self.queue.put(
                {
                    "type": "log",
                    "message": f"執行完成：成功 {len(executed_entries)}，失敗 {len(failed_entries)}",
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
                    if self._progress_dialog is not None:
                        self._progress_dialog.add_line(str(item.get("message")))
                elif item_type == "progress":
                    self.progress_bar.update_progress(int(item.get("value", 0)))
                    if self._progress_dialog is not None:
                        self._progress_dialog.update_progress(int(item.get("value", 0)))
                elif item_type == "stage":
                    self.stage_label.configure(text=str(item.get("message")))
                    if self._progress_dialog is not None:
                        self._progress_dialog.update_stage(str(item.get("message")))
                elif item_type == "detail":
                    if self._progress_dialog is not None:
                        self._progress_dialog.update_detail(str(item.get("message")))
                elif item_type == "enable_execute":
                    state = "normal" if item.get("value") else "disabled"
                    self.execute_button.configure(state=state)
                elif item_type == "done":
                    self._is_running = False
                    self.dry_run_button.configure(state="normal")
                    self.rollback_button.configure(state="normal")
                    self._close_progress_dialog()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _open_progress_dialog(self, title: str, allow_cancel: bool) -> None:
        self._close_progress_dialog()
        self._progress_dialog = ProgressDialog(
            self.root,
            title=title,
            allow_cancel=allow_cancel,
            cancel_callback=self._on_cancel,
        )
        self._progress_dialog.update_stage("階段: 準備中")

    def _close_progress_dialog(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_cancel(self) -> None:
        self.cancel_event.set()

    def _select_rollback_dir(self) -> Optional[Path]:
        candidates = []
        root = self._default_processed_root()
        if root is not None and root.exists():
            candidates = sorted(root.glob("Processed_*"), key=lambda p: p.name)

        if not candidates:
            selected = filedialog.askdirectory(title="選擇要回滾的 Processed_* 資料夾")
            if not selected:
                return None
            processed_dir = Path(selected)
            if not processed_dir.exists():
                self.log_viewer.add_line("指定的資料夾不存在")
                return None
            return processed_dir

        dialog = RollbackDialog(self.root, candidates)
        self.root.wait_window(dialog)
        if dialog.selection is None:
            return None
        return dialog.selection.processed_dir

    def _default_processed_root(self) -> Optional[Path]:
        output_value = self.output_selector.path_var.get().strip()
        if output_value:
            return Path(output_value).parent
        source_value = self.source_selector.path_var.get().strip()
        if source_value:
            return Path(source_value)
        return None

    def run(self) -> None:
        self.root.mainloop()
