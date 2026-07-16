from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .models import Borehole
from .validation import validate_borehole


class RawTextFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.text = tk.Text(self, wrap="none", relief="flat", padx=12, pady=12)
        self.text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

    def load_borehole(self, borehole: Borehole | None) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if borehole:
            for name, content in borehole.raw_texts.items():
                self.text.insert("end", f"===== {name} =====\n")
                self.text.insert("end", content)
                if not content.endswith("\n"):
                    self.text.insert("end", "\n")
                self.text.insert("end", "\n")
        self.text.configure(state="disabled")


class ValidationFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.text = tk.Text(self, wrap="word", relief="flat", padx=12, pady=12)
        self.text.pack(fill="both", expand=True)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not borehole:
            self.text.insert("end", "暂无钻孔数据。")
        else:
            messages = validate_borehole(borehole)
            if not messages:
                self.text.insert("end", "当前钻孔未发现明显问题。")
            else:
                for message in messages:
                    self.text.insert("end", f"- {message}\n")
        self.text.configure(state="disabled")
