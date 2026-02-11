"""進階設定面板。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import ConfigManager


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

    def _toggle(self) -> None:
        if self._is_open.get():
            self.body.pack_forget()
            self.toggle_button.configure(text="進階設定 ▼")
            self._is_open.set(False)
        else:
            self.body.pack(fill=tk.X, pady=(6, 0))
            self.toggle_button.configure(text="進階設定 ▲")
            self._is_open.set(True)
