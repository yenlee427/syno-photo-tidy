"""設定檔編輯視窗。"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..config import ConfigManager


class ConfigDialog(tk.Toplevel):
    def __init__(self, master, config: ConfigManager) -> None:
        super().__init__(master)
        self.title("設定檔編輯")
        self.resizable(True, True)
        self.config = config

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_from_config()

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        self.text = tk.Text(container, wrap="none", height=18)
        self.text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(button_frame, text="匯入", command=self._on_import).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="匯出", command=self._on_export).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(button_frame, text="驗證", command=self._on_validate).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="套用", command=self._on_apply).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(button_frame, text="關閉", command=self._on_close).pack(side=tk.RIGHT, padx=(0, 6))

    def _load_from_config(self) -> None:
        data = self.config.to_dict()
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, payload)

    def _read_text_json(self) -> dict[str, object] | None:
        raw = self.text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showerror("設定檔", "內容為空")
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            messagebox.showerror("設定檔", f"JSON 解析失敗: {exc}")
            return None

    def _on_import(self) -> None:
        path = filedialog.askopenfilename(
            title="匯入設定檔",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as exc:
            messagebox.showerror("設定檔", f"讀取失敗: {exc}")
            return
        except json.JSONDecodeError as exc:
            messagebox.showerror("設定檔", f"JSON 解析失敗: {exc}")
            return

        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, json.dumps(data, ensure_ascii=False, indent=2))

    def _on_export(self) -> None:
        path = filedialog.asksaveasfilename(
            title="匯出設定檔",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        data = self._read_text_json()
        if data is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            messagebox.showerror("設定檔", f"寫入失敗: {exc}")

    def _on_validate(self) -> None:
        data = self._read_text_json()
        if data is None:
            return
        errors = self.config.validate_dict(data)
        if errors:
            messagebox.showwarning("設定檔", "\n".join(errors))
        else:
            messagebox.showinfo("設定檔", "驗證通過")

    def _on_apply(self) -> None:
        data = self._read_text_json()
        if data is None:
            return
        errors = self.config.validate_dict(data)
        if errors:
            messagebox.showwarning("設定檔", "\n".join(errors))
            return
        self.config.replace_config(data)
        messagebox.showinfo("設定檔", "已套用設定")

    def _on_close(self) -> None:
        self.destroy()
