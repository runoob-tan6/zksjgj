from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .models import BasicLayer, Borehole
from .ui_tree_helpers import EditableTreeMixin

COLUMNS = ("index", "depth", "c", "b", "d", "g", "h")


class BasicDataFrame(EditableTreeMixin, ttk.Frame):
    def __init__(self, master, on_change: Callable[[str], None], begin_change: Callable | None = None, end_change: Callable | None = None):
        super().__init__(master)
        self.on_change = on_change
        self.begin_change = begin_change
        self.end_change = end_change
        self.borehole: Borehole | None = None
        self._drag_source_index: int | None = None
        self.context_row_index: int | None = None
        self._active_editor: ttk.Entry | None = None
        self._active_commit = None
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="基础数据", style="Title.TLabel").pack(side="left")

        self.tree = ttk.Treeview(outer, columns=COLUMNS, show="headings", height=16)
        headings = {
            "index": "层号",
            "depth": "层底深度 .-c",
            "c": "岩性代号 .-c",
            "b": "地层时代 .-b",
            "d": "钻孔结构 .-d",
            "g": "风化 .-g",
            "h": "岩性描述 .-h",
        }
        widths = {"index": 56, "depth": 110, "c": 110, "b": 110, "d": 110, "g": 110, "h": 240}
        for column in COLUMNS:
            self.tree.heading(column, text=headings[column])
            anchor = "w" if column == "h" else "center"
            self.tree.column(column, width=widths[column], anchor=anchor, stretch=column == "h")
        self.tree.pack(fill="both", expand=True, side="left")
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.edit_cell)
        self.tree.bind("<ButtonPress-1>", self.start_drag)
        self.tree.bind("<ButtonRelease-1>", self.finish_drag)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="在上方添加行", command=self.add_layer_above_context)
        self.context_menu.add_command(label="在下方添加行", command=self.add_layer_below_context)
        self.context_menu.add_command(label="删除行", command=self.delete_context_layer)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self.borehole = borehole
        self.refresh()

    def _format_depth_interval(self, top_depth: str, bottom_depth: str) -> str:
        bottom_depth = str(bottom_depth or "").strip()
        top_depth = str(top_depth or "0").strip() or "0"
        if not bottom_depth:
            return ""
        return f"{top_depth}~{bottom_depth}"

    def _extract_bottom_depth(self, value: str) -> str:
        value = value.strip()
        if "~" in value:
            return value.rsplit("~", 1)[1].strip()
        if "-" in value:
            return value.rsplit("-", 1)[1].strip()
        return value

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.borehole:
            return
        for idx, layer in enumerate(self.borehole.layers, start=1):
            self.tree.insert("", "end", values=(idx, layer.bottom_depth, layer.lithology_code, layer.formation, layer.structure, layer.weathering, layer.description))

    def selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        item = self.tree.item(selection[0])
        return int(item["values"][0]) - 1

    def mark_all_basic_dirty(self) -> None:
        for suffix in ("c", "b", "d", "g", "h"):
            self.on_change(suffix)

    def select_inserted_layer(self, insert_index: int) -> None:
        self.select_row(insert_index)

    def add_layer_above_context(self) -> None:
        if not self.borehole or self.context_row_index is None:
            return
        token = self.begin_change(self.borehole, "在上方添加基础数据行") if self.begin_change else None
        insert_index = max(0, self.context_row_index)
        self.borehole.layers.insert(insert_index, BasicLayer())
        self.mark_all_basic_dirty()
        self.refresh()
        self.select_inserted_layer(insert_index)
        if self.end_change:
            self.end_change(token)

    def add_layer_below_context(self) -> None:
        if not self.borehole or self.context_row_index is None:
            return
        token = self.begin_change(self.borehole, "在下方添加基础数据行") if self.begin_change else None
        insert_index = min(self.context_row_index + 1, len(self.borehole.layers))
        self.borehole.layers.insert(insert_index, BasicLayer())
        self.mark_all_basic_dirty()
        self.refresh()
        self.select_inserted_layer(insert_index)
        if self.end_change:
            self.end_change(token)

    def delete_context_layer(self) -> None:
        if not self.borehole or self.context_row_index is None:
            return
        if 0 <= self.context_row_index < len(self.borehole.layers):
            token = self.begin_change(self.borehole, "删除基础数据行") if self.begin_change else None
            del self.borehole.layers[self.context_row_index]
            self.mark_all_basic_dirty()
            self.refresh()
            if self.end_change:
                self.end_change(token)

    def finish_drag(self, event) -> None:
        if not self.borehole or self._drag_source_index is None:
            return
        row_id = self.tree.identify_row(event.y)
        source_index = self._drag_source_index
        self._drag_source_index = None
        if not row_id:
            return
        target_index = self.tree.index(row_id)
        if source_index == target_index:
            return
        if not (0 <= source_index < len(self.borehole.layers) and 0 <= target_index < len(self.borehole.layers)):
            return
        token = self.begin_change(self.borehole, "调整基础数据行顺序") if self.begin_change else None
        layer = self.borehole.layers.pop(source_index)
        self.borehole.layers.insert(target_index, layer)
        self.mark_all_basic_dirty()
        self.refresh()
        if self.end_change:
            self.end_change(token)
        children = self.tree.get_children()
        if 0 <= target_index < len(children):
            self.tree.selection_set(children[target_index])
            self.tree.focus(children[target_index])

    def show_context_menu(self, event) -> None:
        if not self.borehole:
            return
        self.set_context_row_from_event(event)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def edit_cell(self, event) -> None:
        if not self.borehole:
            return
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if not row_id or not column_id:
            return
        col_index = int(column_id[1:]) - 1
        column = COLUMNS[col_index]
        if column == "index":
            return
        bbox = self.tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, width, height = bbox
        values = list(self.tree.item(row_id, "values"))
        old_value = values[col_index]
        if column == "depth":
            row_index = int(values[0]) - 1
            old_value = self.borehole.layers[row_index].bottom_depth
        elif column == "g" and old_value:
            old_value = str(old_value).split(" ", 1)[0]
        entry = ttk.Entry(self.tree)
        entry.insert(0, old_value)
        entry.place(x=x, y=y, width=width, height=height)
        self._active_editor = entry
        entry.focus_set()

        def commit(_event=None):
            if not entry.winfo_exists():
                return
            value = entry.get().strip()
            entry.destroy()
            self._active_editor = None
            self._active_commit = None
            row_index = int(values[0]) - 1
            layer = self.borehole.layers[row_index]
            if column == "depth":
                value = self._extract_bottom_depth(value)
                current_value = layer.bottom_depth
                setter = lambda v: setattr(layer, "bottom_depth", v)
            elif column == "c":
                current_value = layer.lithology_code
                setter = lambda v: setattr(layer, "lithology_code", v)
            elif column == "b":
                current_value = layer.formation
                setter = lambda v: setattr(layer, "formation", v)
            elif column == "d":
                current_value = layer.structure
                setter = lambda v: setattr(layer, "structure", v)
            elif column == "g":
                current_value = layer.weathering
                setter = lambda v: setattr(layer, "weathering", v)
            elif column == "h":
                current_value = layer.description
                setter = lambda v: setattr(layer, "description", v)
            else:
                self.refresh()
                return
            if current_value == value:
                self.refresh()
                return
            token = self.begin_change(self.borehole, f"修改基础数据第 {row_index + 1} 行") if self.begin_change else None
            setter(value)
            if column == "depth":
                self.mark_all_basic_dirty()
            else:
                self.on_change(column)
            if self.end_change:
                self.end_change(token)
            self.refresh()

        self._active_commit = commit
        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)

