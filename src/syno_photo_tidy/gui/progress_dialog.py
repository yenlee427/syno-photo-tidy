"""進階進度視窗。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import time
from typing import Callable, Optional

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
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self._cancel_callback = cancel_callback
        self._allow_cancel = allow_cancel
        self._start_time = time.time()

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        self.stage_label = ttk.Label(container, text="階段: 準備中")
        self.stage_label.pack(fill=tk.X, pady=(0, 8))

        self.detail_label = ttk.Label(container, text="")
        self.detail_label.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ProgressBar(container)
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(container, text="日誌:").pack(anchor=tk.W)
        self.log_viewer = LogViewer(container, max_lines=60)
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

    def add_line(self, message: str) -> None:
        self.log_viewer.add_line(message)

    def close(self) -> None:
        if self.winfo_exists():
            self.destroy()

    def _on_cancel(self) -> None:
        if self._allow_cancel and self._cancel_callback is not None:
            self._cancel_callback()

    def _on_close(self) -> None:
        self._on_cancel()
        self.close()

    def _update_elapsed(self) -> None:
        elapsed = int(time.time() - self._start_time)
        self.elapsed_var.set(f"耗時: {elapsed}s")
