"""資料夾選擇器。"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk


class FileSelector(ttk.Frame):
    def __init__(self, master, label_text: str) -> None:
        super().__init__(master)
        ttk.Label(self, text=f"{label_text}:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.path_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        self.button = ttk.Button(self, text="瀏覽", command=self._browse)
        self.button.pack(side=tk.LEFT)

    def _browse(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            self.path_var.set(selected)
