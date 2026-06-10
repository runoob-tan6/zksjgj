from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .models import TEST_SUFFIX_NAMES, Borehole, TestRecord
from .ui_tree_helpers import EditableTreeMixin

COLUMN_TITLES = {
    "e": ("深度", "岩芯获得率"),
    "f": ("深度", "RQD值"),
    "m": ("起始深度", "终止深度", "透水率"),
    "n": ("起始深度", "终止深度", "渗透系数"),
    "o": ("起始深度", "终止深度", "样品编号"),
    "q": ("起始深度", "终止深度", "标贯击数"),
    "l": ("稳定水位", "观测日期", "备注"),
}


class TestSection(EditableTreeMixin, ttk.LabelFrame):
    def __init__(self, master, suffix: str, on_change: Callable[[str], None], begin_change: Callable | None = None, end_change: Callable | None = None, sync_depth: Callable[[str, int, str], None] | None = None):
        title = f".-{suffix} {TEST_SUFFIX_NAMES[suffix]}"
        super().__init__(master, text=title, padding=10)
        self.suffix = suffix
        self.on_change = on_change
        self.begin_change = begin_change
        self.end_change = end_change
        self.sync_depth = sync_depth
        self.borehole: Borehole | None = None
        self._drag_source_index: int | None = None
        self.context_row_index: int | None = None
        self._active_editor: ttk.Entry | None = None
        self._active_commit = None
        self._build()

    def _build(self) -> None:
        tree_wrap = ttk.Frame(self)
        tree_wrap.pack(fill="x", expand=False)
        columns = tuple(f"v{index}" for index in range(1, len(COLUMN_TITLES[self.suffix]) + 1))
        self.tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=8)
        for col, text in zip(columns, COLUMN_TITLES[self.suffix]):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=110, anchor="center", stretch=True)
        self.tree.pack(side="left", fill="x", expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.edit_cell)
        self.tree.bind("<ButtonPress-1>", self.start_drag)
        self.tree.bind("<ButtonRelease-1>", self.finish_drag)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Enter>", self._bind_mousewheel)
        self.tree.bind("<Leave>", self._unbind_mousewheel)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="在上方添加行", command=self.add_record_above_context)
        self.context_menu.add_command(label="在下方添加行", command=self.add_record_below_context)
        self.context_menu.add_command(label="删除行", command=self.delete_context_record)

    def _bind_mousewheel(self, _event=None) -> None:
        self.tree.bind_all("<MouseWheel>", self._on_mousewheel)
        self.tree.bind_all("<Shift-MouseWheel>", self._on_parent_mousewheel)
        self.tree.bind_all("<Button-4>", self._on_mousewheel)
        self.tree.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None) -> None:
        self.tree.unbind_all("<MouseWheel>")
        self.tree.unbind_all("<Shift-MouseWheel>")
        self.tree.unbind_all("<Button-4>")
        self.tree.unbind_all("<Button-5>")

    def _on_mousewheel(self, event) -> str:
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = int(-1 * (event.delta / 120))
        first, last = self.tree.yview()
        if (direction < 0 and first <= 0) or (direction > 0 and last >= 1):
            self._scroll_parent(direction)
        else:
            self.tree.yview_scroll(direction, "units")
        return "break"

    def _on_parent_mousewheel(self, event) -> str:
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = int(-1 * (event.delta / 120))
        self._scroll_parent(direction)
        return "break"

    def _scroll_parent(self, direction: int) -> None:
        parent = self.master
        while parent is not None:
            if hasattr(parent, "scroll_page"):
                parent.scroll_page(direction)
                return
            parent = getattr(parent, "master", None)

    def empty_record_values(self) -> list[str]:
        return [""] * len(COLUMN_TITLES[self.suffix])

    def load_borehole(self, borehole: Borehole | None) -> None:
        self.borehole = borehole
        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.borehole:
            return
        column_count = len(COLUMN_TITLES[self.suffix])
        for record in self.borehole.tests.setdefault(self.suffix, []):
            values = list(record.values[:column_count])
            while len(values) < column_count:
                values.append("")
            self.tree.insert("", "end", values=values)

    def add_record(self) -> None:
        if not self.borehole:
            return
        token = self.begin_change(self.borehole, f"新增试验数据 .-{self.suffix} 行") if self.begin_change else None
        self.borehole.tests.setdefault(self.suffix, []).append(TestRecord(values=self.empty_record_values()))
        self.on_change(self.suffix)
        self.refresh()
        if self.end_change:
            self.end_change(token)
        children = self.tree.get_children()
        if children:
            last = children[-1]
            self.tree.selection_set(last)
            self.tree.focus(last)
            self.tree.see(last)

    def delete_record(self) -> None:
        if not self.borehole:
            return
        selection = self.tree.selection()
        if not selection:
            return
        index = self.tree.index(selection[0])
        records = self.borehole.tests.setdefault(self.suffix, [])
        if 0 <= index < len(records):
            token = self.begin_change(self.borehole, f"删除试验数据 .-{self.suffix} 行") if self.begin_change else None
            del records[index]
            self.on_change(self.suffix)
            self.refresh()
            if self.end_change:
                self.end_change(token)

    def select_record(self, index: int) -> None:
        self.select_row(index)

    def add_record_above_context(self) -> None:
        if not self.borehole or self.context_row_index is None:
            return
        records = self.borehole.tests.setdefault(self.suffix, [])
        token = self.begin_change(self.borehole, f"在上方添加试验数据 .-{self.suffix} 行") if self.begin_change else None
        insert_index = max(0, self.context_row_index) if self.context_row_index >= 0 else len(records)
        records.insert(insert_index, TestRecord(values=self.empty_record_values()))
        self.on_change(self.suffix)
        self.refresh()
        self.select_record(insert_index)
        if self.end_change:
            self.end_change(token)

    def add_record_below_context(self) -> None:
        if not self.borehole or self.context_row_index is None:
            return
        records = self.borehole.tests.setdefault(self.suffix, [])
        token = self.begin_change(self.borehole, f"在下方添加试验数据 .-{self.suffix} 行") if self.begin_change else None
        insert_index = min(self.context_row_index + 1, len(records)) if self.context_row_index >= 0 else len(records)
        records.insert(insert_index, TestRecord(values=self.empty_record_values()))
        self.on_change(self.suffix)
        self.refresh()
        self.select_record(insert_index)
        if self.end_change:
            self.end_change(token)

    def delete_context_record(self) -> None:
        if not self.borehole or self.context_row_index is None:
            return
        records = self.borehole.tests.setdefault(self.suffix, [])
        if 0 <= self.context_row_index < len(records):
            token = self.begin_change(self.borehole, f"删除试验数据 .-{self.suffix} 行") if self.begin_change else None
            del records[self.context_row_index]
            self.on_change(self.suffix)
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
        records = self.borehole.tests.setdefault(self.suffix, [])
        if source_index == target_index:
            return
        if not (0 <= source_index < len(records) and 0 <= target_index < len(records)):
            return
        token = self.begin_change(self.borehole, f"调整试验数据 .-{self.suffix} 行顺序") if self.begin_change else None
        record = records.pop(source_index)
        records.insert(target_index, record)
        self.on_change(self.suffix)
        self.refresh()
        self.select_record(target_index)
        if self.end_change:
            self.end_change(token)

    def show_context_menu(self, event) -> None:
        if not self.borehole:
            return
        self.set_context_row_from_event(event)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def edit_cell(self, event) -> None:
        if not self.borehole:
            return
        row_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if not row_id or not column_id:
            return
        bbox = self.tree.bbox(row_id, column_id)
        if not bbox:
            return
        col_index = int(column_id[1:]) - 1
        x, y, width, height = bbox
        old_value = self.tree.item(row_id, "values")[col_index]
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
            row_index = self.tree.index(row_id)
            records = self.borehole.tests.setdefault(self.suffix, [])
            if row_index >= len(records):
                return
            record = records[row_index]
            while len(record.values) <= col_index:
                record.values.append("")
            if record.values[col_index] == value:
                self.refresh()
                return
            token = self.begin_change(self.borehole, f"修改试验数据 .-{self.suffix} 第 {row_index + 1} 行") if self.begin_change else None
            record.values[col_index] = value
            self.on_change(self.suffix)
            if self.sync_depth and self.suffix in ("e", "f") and col_index == 0:
                self.sync_depth(self.suffix, row_index, value)
            self.refresh()
            if self.end_change:
                self.end_change(token)

        self._active_commit = commit
        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)


class TestDataFrame(ttk.Frame):
    def __init__(self, master, on_change: Callable[[str], None], begin_change: Callable | None = None, end_change: Callable | None = None):
        super().__init__(master)
        self.on_change = on_change
        self.begin_change = begin_change
        self.end_change = end_change
        self.borehole: Borehole | None = None
        self.sections: dict[str, TestSection] = {}
        self._build()

    def _build(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#F7F8FC")
        self.page_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.page_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.page_scroll.grid(row=0, column=1, sticky="ns")
        self.container = ttk.Frame(self.canvas, padding=14)
        self.window_id = self.canvas.create_window((0, 0), window=self.container, anchor="nw")
        self.container.bind("<Configure>", self._on_container_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_page_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_page_mousewheel)
        header = ttk.Frame(self.container)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(header, text="试验数据", style="Title.TLabel").pack(side="left")
        self.grid_area = ttk.Frame(self.container)
        self.grid_area.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.columnconfigure(1, weight=1)
        for col in range(2):
            self.grid_area.columnconfigure(col, weight=1, uniform="test_cols", minsize=300)

    def _on_container_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _bind_page_mousewheel(self, _event=None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_page_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_page_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_page_mousewheel)

    def _unbind_page_mousewheel(self, _event=None) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_page_mousewheel(self, event) -> str:
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = int(-1 * (event.delta / 120))
        self.scroll_page(direction)
        return "break"

    def scroll_page(self, direction: int) -> None:
        self.canvas.yview_scroll(direction, "units")

    def load_borehole(self, borehole: Borehole | None) -> None:
        self.borehole = borehole
        if not borehole:
            for child in self.grid_area.winfo_children():
                child.destroy()
            for row in range(12):
                self.grid_area.rowconfigure(row, weight=0, minsize=0)
            self.sections.clear()
            ttk.Label(self.grid_area, text="暂无钻孔数据。", style="Hint.TLabel").grid(row=0, column=0, sticky="nw", pady=12)
            return
        suffixes = borehole.available_test_suffixes()
        if list(self.sections) == suffixes:
            for section in self.sections.values():
                section.load_borehole(borehole)
            return
        for child in self.grid_area.winfo_children():
            child.destroy()
        for row in range(12):
            self.grid_area.rowconfigure(row, weight=0, minsize=0)
        self.sections.clear()
        row_count = max(1, (len(suffixes) + 1) // 2)
        for row in range(row_count):
            self.grid_area.rowconfigure(row, weight=0, minsize=0)
        for index, suffix in enumerate(suffixes):
            row = index // 2
            col = index % 2
            section = TestSection(self.grid_area, suffix, self.handle_section_change, self.begin_change, self.end_change, self.sync_ef_depth)
            section.grid(row=row, column=col, sticky="new", padx=6, pady=6, ipadx=2, ipady=2)
            section.load_borehole(borehole)
            self.sections[suffix] = section

    def handle_section_change(self, suffix: str) -> None:
        self.on_change(suffix)

    def sync_ef_depth(self, source_suffix: str, row_index: int, depth: str) -> None:
        if not self.borehole or source_suffix not in ("e", "f"):
            return
        target_suffix = "f" if source_suffix == "e" else "e"
        records = self.borehole.tests.setdefault(target_suffix, [])
        while len(records) <= row_index:
            records.append(TestRecord(values=["", ""]))
        target = records[row_index]
        while len(target.values) < 2:
            target.values.append("")
        if target.values[0] != depth:
            target.values[0] = depth
            self.on_change(target_suffix)
        target_section = self.sections.get(target_suffix)
        if target_section:
            target_section.refresh()
            target_section.select_record(row_index)

    def commit_active_edit(self) -> None:
        for section in self.sections.values():
            section.commit_active_edit()
