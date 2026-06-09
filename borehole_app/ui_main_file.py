from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict

from .models import EDITABLE_MAIN_INDICES, MAIN_FIELD_NAMES, Borehole


class MainFileFrame(ttk.Frame):
    def __init__(self, master, on_change: Callable[[], None], on_hole_id_change: Callable[[str, str], None] | None = None, begin_change: Callable | None = None, end_change: Callable | None = None):
        super().__init__(master)
        self.on_change = on_change
        self.on_hole_id_change = on_hole_id_change
        self.begin_change = begin_change
        self.end_change = end_change
        self.borehole: Borehole | None = None
        self.vars: Dict[int, tk.StringVar] = {}
        self.entries: Dict[int, ttk.Entry] = {}
        self._trace_ids: Dict[int, str] = {}
        self._edit_token = None
        self._edit_index: int | None = None
        self._edit_original_value = ""
        self._loading = False
        self._build()

    def _build(self) -> None:
        container = ttk.Frame(self, padding=18)
        container.pack(fill="both", expand=True)
        title = ttk.Label(container, text="主文件", style="Title.TLabel")
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))
        row = 1
        for position, index in enumerate(EDITABLE_MAIN_INDICES):
            label = ttk.Label(container, text=MAIN_FIELD_NAMES[index])
            var = tk.StringVar()
            self._trace_ids[index] = var.trace_add("write", self._on_var_change)
            self.vars[index] = var
            label.grid(row=row, column=(position % 2) * 2, sticky="w", padx=(0, 8), pady=6)
            entry = ttk.Entry(container, textvariable=var, width=26)
            self.entries[index] = entry
            entry.bind("<FocusIn>", lambda _event, idx=index: self.begin_main_edit(idx))
            entry.bind("<FocusOut>", self.commit_active_edit)
            entry.bind("<Return>", self.commit_active_edit)
            entry.grid(row=row, column=(position % 2) * 2 + 1, sticky="ew", padx=(0, 18), pady=6)
            if position % 2 == 1:
                row += 1
        for col in (1, 3):
            container.columnconfigure(col, weight=1)

    def _on_var_change(self, *_args) -> None:
        if self._loading or not self.borehole:
            return
        lines = self.borehole.main.normalized_lines()
        for index, var in self.vars.items():
            lines[index] = var.get()
        if 1 in self.vars:
            lines[12] = self.vars[1].get()
        self.borehole.main.lines = lines

    def begin_main_edit(self, index: int) -> None:
        if self._loading or not self.borehole:
            return
        if self._edit_token is not None and self._edit_index != index:
            self.commit_active_edit()
        self._edit_index = index
        self._edit_original_value = self.vars[index].get()
        self._edit_token = self.begin_change(self.borehole, f"修改主文件：{MAIN_FIELD_NAMES[index]}") if self.begin_change else None

    def commit_active_edit(self, _event=None):
        if self._loading or not self.borehole or self._edit_token is None or self._edit_index is None:
            return None
        index = self._edit_index
        old_value = self._edit_original_value
        new_value = self.vars[index].get().strip()
        token = self._edit_token
        self._edit_token = None
        self._edit_index = None
        self._edit_original_value = ""
        if new_value == old_value:
            return "break"
        if index == 0 and self.on_hole_id_change:
            old_prefix = self.borehole.prefix
            if new_value and new_value != old_prefix:
                self.borehole.main.lines[0] = new_value
                self.on_hole_id_change(old_prefix, new_value)
            else:
                self.on_change()
        else:
            self.on_change()
        if self.end_change:
            self.end_change(token)
        return "break"

    def set_hole_id(self, value: str) -> None:
        if 0 in self.vars:
            self._loading = True
            self.vars[0].set(value)
            if self.borehole:
                lines = self.borehole.main.normalized_lines()
                lines[0] = value
                self.borehole.main.lines = lines
            self._loading = False

    def load_borehole(self, borehole: Borehole | None) -> None:
        self._loading = True
        self.borehole = None
        for var in self.vars.values():
            var.set("")
        if not borehole:
            self._loading = False
            return
        lines = borehole.main.normalized_lines()
        for index, var in self.vars.items():
            var.set(lines[index])
            self.entries[index].icursor(tk.END)
        self.borehole = borehole
        self._loading = False
