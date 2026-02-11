"""進階設定面板。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..config import ConfigManager
from .config_dialog import ConfigDialog


class SettingsPanel(ttk.Frame):
    def __init__(self, master, config: ConfigManager) -> None:
        super().__init__(master)
        self.config = config
        self._is_open = tk.BooleanVar(value=False)

        self.toggle_button = ttk.Button(
            self, text="進階設定 ▼", command=self._toggle
        )
        self.toggle_button.pack(anchor=tk.W)

        self.body = ttk.Frame(self, padding=(12, 8, 12, 8))
        self._build_body()

    def _build_body(self) -> None:
        max_size = self.config.get("thumbnail.max_size_kb")
        max_dimension = self.config.get("thumbnail.max_dimension_px")
        min_dimension = self.config.get("thumbnail.min_dimension_px")
        phash_threshold = self.config.get("phash.threshold")

        size_frame = ttk.Frame(self.body)
        size_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(size_frame, text="縮圖判定: 大小").pack(side=tk.LEFT)
        self.max_size_var = tk.StringVar(value=str(max_size))
        ttk.Entry(size_frame, textvariable=self.max_size_var, width=8).pack(
            side=tk.LEFT, padx=(6, 2)
        )
        ttk.Label(size_frame, text="KB").pack(side=tk.LEFT)

        dimension_frame = ttk.Frame(self.body)
        dimension_frame.pack(fill=tk.X)
        ttk.Label(dimension_frame, text="解析度").pack(side=tk.LEFT)
        self.max_dimension_var = tk.StringVar(value=str(max_dimension))
        ttk.Entry(dimension_frame, textvariable=self.max_dimension_var, width=8).pack(
            side=tk.LEFT, padx=(6, 2)
        )
        ttk.Label(dimension_frame, text="px").pack(side=tk.LEFT)

        min_dimension_frame = ttk.Frame(self.body)
        min_dimension_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(min_dimension_frame, text="極小圖").pack(side=tk.LEFT)
        self.min_dimension_var = tk.StringVar(value=str(min_dimension))
        ttk.Entry(min_dimension_frame, textvariable=self.min_dimension_var, width=8).pack(
            side=tk.LEFT, padx=(6, 2)
        )
        ttk.Label(min_dimension_frame, text="px").pack(side=tk.LEFT)

        phash_frame = ttk.Frame(self.body)
        phash_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(phash_frame, text="相似門檻").pack(side=tk.LEFT)
        self.phash_threshold_var = tk.StringVar(value=str(phash_threshold))
        ttk.Entry(phash_frame, textvariable=self.phash_threshold_var, width=8).pack(
            side=tk.LEFT, padx=(6, 2)
        )

        button_frame = ttk.Frame(self.body)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(button_frame, text="設定檔編輯", command=self._open_config_dialog).pack(
            side=tk.LEFT
        )
        ttk.Button(button_frame, text="套用設定", command=self._apply_settings).pack(
            side=tk.RIGHT
        )

    def _toggle(self) -> None:
        if self._is_open.get():
            self.body.pack_forget()
            self.toggle_button.configure(text="進階設定 ▼")
            self._is_open.set(False)
        else:
            self.body.pack(fill=tk.X, pady=(6, 0))
            self.toggle_button.configure(text="進階設定 ▲")
            self._is_open.set(True)

    def _apply_settings(self) -> None:
        try:
            max_size = int(self.max_size_var.get())
            max_dimension = int(self.max_dimension_var.get())
            min_dimension = int(self.min_dimension_var.get())
            phash_threshold = int(self.phash_threshold_var.get())
        except ValueError:
            messagebox.showerror("設定", "請輸入有效的整數")
            return

        self.config.set("thumbnail.max_size_kb", max_size)
        self.config.set("thumbnail.max_dimension_px", max_dimension)
        self.config.set("thumbnail.min_dimension_px", min_dimension)
        self.config.set("phash.threshold", phash_threshold)

        errors = self.config.validate_config()
        if errors:
            messagebox.showwarning("設定", "\n".join(errors))
        else:
            messagebox.showinfo("設定", "設定已套用")

    def _open_config_dialog(self) -> None:
        ConfigDialog(self, self.config)
