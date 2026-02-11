"""進度條元件。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ProgressBar(ttk.Frame):
    def __init__(self, master) -> None:
        super().__init__(master)
        self.percent_var = tk.StringVar(value="0%")
        self.bar = ttk.Progressbar(self, length=400, mode="determinate", maximum=100)
        self.bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.label = ttk.Label(self, textvariable=self.percent_var, width=6)
        self.label.pack(side=tk.LEFT, padx=(6, 0))

    def update_progress(self, value: int) -> None:
        value = max(0, min(100, value))
        self.bar["value"] = value
        self.percent_var.set(f"{value}%")
