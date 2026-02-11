"""Rollback selection dialog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from ..core import read_manifest_records


@dataclass
class RollbackSelection:
    processed_dir: Path


class RollbackDialog(tk.Toplevel):
    def __init__(self, master, candidates: list[Path]) -> None:
        super().__init__(master)
        self.title("Rollback Last Run")
        self.resizable(False, False)
        self._candidates = candidates
        self.selection: RollbackSelection | None = None

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="選擇 Processed_* 目錄：").pack(anchor=tk.W)

        self.listbox = tk.Listbox(container, height=min(8, max(3, len(self._candidates))))
        for item in self._candidates:
            self.listbox.insert(tk.END, item.name)
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=(6, 8))
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.summary_var = tk.StringVar(value="")
        self.summary_label = ttk.Label(container, textvariable=self.summary_var)
        self.summary_label.pack(anchor=tk.W, pady=(0, 8))

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="確定", command=self._on_confirm).pack(side=tk.RIGHT, padx=(0, 8))

    def _on_select(self, _event=None) -> None:
        index = self._get_selected_index()
        if index is None:
            self.summary_var.set("")
            return
        selected = self._candidates[index]
        self.summary_var.set(self._build_summary(selected))

    def _build_summary(self, processed_dir: Path) -> str:
        manifest_path = processed_dir / "REPORT" / "manifest.jsonl"
        records = read_manifest_records(manifest_path)
        run_record = next(
            (record for record in records if record.get("record_type") == "RUN"),
            None,
        )
        actions = [
            record
            for record in records
            if record.get("record_type") == "ACTION"
            and record.get("status") in {"MOVED", "COPIED", "RENAMED"}
        ]
        if not actions:
            return "找不到可回滾的記錄"
        counts = {"MOVED": 0, "COPIED": 0, "RENAMED": 0}
        for record in actions:
            status = str(record.get("status"))
            if status in counts:
                counts[status] += 1
        created_at = run_record.get("created_at") if run_record else "未知"
        return (
            f"Run: {created_at}\n"
            f"可回滾記錄: {len(actions)} "
            f"(MOVED {counts['MOVED']}, COPIED {counts['COPIED']}, RENAMED {counts['RENAMED']})"
        )

    def _on_confirm(self) -> None:
        index = self._get_selected_index()
        if index is None:
            return
        self.selection = RollbackSelection(processed_dir=self._candidates[index])
        self.destroy()

    def _on_cancel(self) -> None:
        self.selection = None
        self.destroy()

    def _get_selected_index(self) -> int | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return int(selection[0])
