"""日誌顯示區。"""

from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import ttk


class LogViewer(ttk.Frame):
    def __init__(self, master, max_lines: int = 20) -> None:
        super().__init__(master)
        self.max_lines = max_lines
        self.text = tk.Text(self, height=8, wrap="word", state="disabled")
        self.text.pack(fill=tk.BOTH, expand=True)

    def add_line(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        self.text.configure(state="normal")
        self.text.insert(tk.END, line)
        self._trim_lines()
        self.text.configure(state="disabled")
        self.text.see(tk.END)

    def _trim_lines(self) -> None:
        content = self.text.get("1.0", tk.END).splitlines()
        if len(content) <= self.max_lines:
            return
        trimmed = content[-self.max_lines :]
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, "\n".join(trimmed) + "\n")
