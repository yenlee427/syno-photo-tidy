"""進階進度視窗。"""

from __future__ import annotations

from collections import deque
import tkinter as tk
from tkinter import ttk
import time
from typing import Callable, Optional

from ..models import ProgressEvent, ProgressEventType
from .widgets.log_viewer import LogViewer
from .widgets.progress_bar import ProgressBar


class ProgressDialog(tk.Toplevel):
    def __init__(
        self,
        master,
        *,
        title: str = "進度",
        allow_cancel: bool = True,
        cancel_callback: Optional[Callable[[], None]] = None,
        speed_window_sec: float = 5.0,
        hash_progress_workers: int = 4,
        log_max_lines: int = 500,
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self._cancel_callback = cancel_callback
        self._allow_cancel = allow_cancel
        self._start_time = time.time()
        self._speed_window_sec = max(1.0, speed_window_sec)
        self._hash_progress_workers = max(1, hash_progress_workers)
        self._last_update_time = time.time()
        self._speed_samples: deque[tuple[float, int]] = deque()
        self._latest_run_total_bytes = 0

        self._build_layout(log_max_lines=log_max_lines)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self, *, log_max_lines: int) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        self.stage_label = ttk.Label(container, text="階段: 準備中")
        self.stage_label.pack(fill=tk.X, pady=(0, 8))

        self.detail_label = ttk.Label(container, text="")
        self.detail_label.pack(fill=tk.X, pady=(0, 8))

        self.current_file_var = tk.StringVar(value="目前檔案: --")
        self.current_file_label = ttk.Label(container, textvariable=self.current_file_var)
        self.current_file_label.pack(fill=tk.X)

        self.current_op_var = tk.StringVar(value="目前動作: --")
        self.current_op_label = ttk.Label(container, textvariable=self.current_op_var)
        self.current_op_label.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ProgressBar(container)
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        self.speed_var = tk.StringVar(value="速度: -- MB/s")
        self.speed_label = ttk.Label(container, textvariable=self.speed_var)
        self.speed_label.pack(anchor=tk.W)

        self.eta_var = tk.StringVar(value="ETA: --")
        self.eta_label = ttk.Label(container, textvariable=self.eta_var)
        self.eta_label.pack(anchor=tk.W)

        self.heartbeat_var = tk.StringVar(value="Last update: 0.0s ago")
        self.heartbeat_label = ttk.Label(container, textvariable=self.heartbeat_var)
        self.heartbeat_label.pack(anchor=tk.W, pady=(0, 8))

        self.network_warning_var = tk.StringVar(value="")
        self.network_warning_frame = ttk.Frame(container)
        self.network_warning_label = ttk.Label(
            self.network_warning_frame,
            textvariable=self.network_warning_var,
            anchor="w",
            justify="left",
        )
        self.network_warning_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.network_warning_hide_button = ttk.Button(
            self.network_warning_frame,
            text="收合",
            width=6,
            command=self._hide_network_warning,
        )
        self.network_warning_hide_button.pack(side=tk.RIGHT, padx=(8, 0))

        ttk.Label(container, text="日誌:").pack(anchor=tk.W)
        self.log_viewer = LogViewer(container, max_lines=log_max_lines)
        self.log_viewer.pack(fill=tk.BOTH, expand=True)

        self.elapsed_var = tk.StringVar(value="耗時: 0s")
        self.elapsed_label = ttk.Label(container, textvariable=self.elapsed_var)
        self.elapsed_label.pack(anchor=tk.W, pady=(6, 0))

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        self.cancel_button = ttk.Button(
            button_frame,
            text="取消",
            command=self._on_cancel,
            state="normal" if self._allow_cancel else "disabled",
        )
        self.cancel_button.pack(side=tk.RIGHT)

    def update_stage(self, message: str) -> None:
        self.stage_label.configure(text=message)
        self._update_elapsed()

    def update_detail(self, message: str) -> None:
        self.detail_label.configure(text=message)
        self._update_elapsed()

    def update_progress(self, value: int) -> None:
        self.progress_bar.update_progress(value)
        self._update_elapsed()
        self._update_eta(value)

    def add_line(self, message: str) -> None:
        self.log_viewer.add_line(message)

    def set_last_update_time(self, timestamp: float | None = None) -> None:
        self._last_update_time = timestamp if timestamp is not None else time.time()

    def update_heartbeat(self) -> None:
        elapsed = max(0.0, time.time() - self._last_update_time)
        self.heartbeat_var.set(f"Last update: {elapsed:.1f}s ago")

    def show_cancelling(self) -> None:
        self.update_detail("正在取消...")

    def handle_progress_event(self, event: ProgressEvent) -> None:
        self.set_last_update_time(time.time())
        if event.phase_name:
            self.update_stage(f"階段: {event.phase_name}")

        if event.op_type:
            self.current_op_var.set(f"目前動作: {self._friendly_op(event.op_type)}")

        if event.event_type == ProgressEventType.SLOW_NETWORK_WARNING:
            warning_text = event.evidence or "偵測到網路速度偏慢，可能影響處理時間"
            self.network_warning_var.set(f"⚠ 慢速網路警告：{warning_text}")
            self.network_warning_frame.pack(fill=tk.X, pady=(0, 8))

        if event.event_type == ProgressEventType.FILE_START:
            if event.phase_name == "Hashing" and self._hash_progress_workers > 1:
                self.current_file_var.set(f"目前檔案: Hashing ({self._hash_progress_workers} workers)...")
            elif event.file_path:
                self.current_file_var.set(f"目前檔案: {self._truncate_path(event.file_path)}")

        if event.event_type in {ProgressEventType.FILE_PROGRESS, ProgressEventType.FILE_DONE}:
            self._update_progress_from_event(event)
            if event.phase_name == "Hashing" and self._hash_progress_workers > 1:
                self.current_file_var.set(f"目前檔案: Hashing ({self._hash_progress_workers} workers)...")
            elif event.file_path:
                self.current_file_var.set(f"目前檔案: {self._truncate_path(event.file_path)}")

        if event.status and event.event_type in {ProgressEventType.FILE_DONE, ProgressEventType.PHASE_END}:
            self.update_detail(f"狀態: {event.status}")
        if event.event_type == ProgressEventType.PHASE_END and event.evidence:
            self.add_line(f"階段摘要：{event.evidence}")

        self.update_heartbeat()

    def close(self) -> None:
        if self.winfo_exists():
            self.destroy()

    def _on_cancel(self) -> None:
        if self._allow_cancel and self._cancel_callback is not None:
            self.show_cancelling()
            self._cancel_callback()

    def _on_close(self) -> None:
        self._on_cancel()
        self.close()

    def _hide_network_warning(self) -> None:
        self.network_warning_frame.pack_forget()

    def _update_elapsed(self) -> None:
        elapsed = int(time.time() - self._start_time)
        self.elapsed_var.set(f"耗時: {elapsed}s")

    def _update_eta(self, percent: int) -> None:
        if percent <= 0:
            self.eta_var.set("ETA: --")
            return
        elapsed = time.time() - self._start_time
        remaining = int(elapsed * (100 - percent) / percent)
        minutes, seconds = divmod(max(0, remaining), 60)
        if minutes:
            self.eta_var.set(f"ETA: {minutes}m {seconds}s")
        else:
            self.eta_var.set(f"ETA: {seconds}s")

    def _update_progress_from_event(self, event: ProgressEvent) -> None:
        run_total = event.run_total_bytes
        run_processed = event.run_processed_bytes
        if run_total is None or run_processed is None or run_total <= 0:
            return

        self._latest_run_total_bytes = run_total
        progress = int(min(100, max(0, (run_processed * 100) / run_total)))
        self.update_progress(progress)

        now = time.time()
        self._speed_samples.append((now, int(run_processed)))
        while self._speed_samples and now - self._speed_samples[0][0] > self._speed_window_sec:
            self._speed_samples.popleft()

        speed = self._calc_speed_mbps()
        if speed is not None:
            self.speed_var.set(f"速度: {speed:.2f} MB/s")
            remaining_bytes = max(0, run_total - run_processed)
            if speed > 0:
                eta_sec = int(remaining_bytes / (speed * 1024 * 1024))
                minutes, seconds = divmod(eta_sec, 60)
                if minutes:
                    self.eta_var.set(f"ETA: {minutes}m {seconds}s")
                else:
                    self.eta_var.set(f"ETA: {seconds}s")

    def _calc_speed_mbps(self) -> float | None:
        if len(self._speed_samples) < 2:
            return None
        first_ts, first_bytes = self._speed_samples[0]
        last_ts, last_bytes = self._speed_samples[-1]
        elapsed = last_ts - first_ts
        if elapsed <= 0:
            return None
        bytes_delta = max(0, last_bytes - first_bytes)
        return bytes_delta / elapsed / 1024 / 1024

    def _friendly_op(self, op_type: str) -> str:
        labels = {
            "hash": "計算 Hash",
            "copy": "複製",
            "move": "搬移",
            "rename": "重新命名",
            "read-metadata": "讀取中繼資料",
        }
        return labels.get(op_type, op_type)

    def _truncate_path(self, path_value: str, max_length: int = 48) -> str:
        if len(path_value) <= max_length:
            return path_value
        head_len = max_length // 2 - 2
        tail_len = max_length - head_len - 3
        return f"{path_value[:head_len]}...{path_value[-tail_len:]}"
