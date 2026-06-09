from __future__ import annotations

from tkinter import ttk


class EditableTreeMixin:
    tree: ttk.Treeview
    _drag_source_index: int | None
    context_row_index: int | None
    _active_commit: object | None

    def selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.tree.index(selection[0])

    def select_row(self, index: int) -> None:
        children = self.tree.get_children()
        if 0 <= index < len(children):
            child = children[index]
            self.tree.selection_set(child)
            self.tree.focus(child)
            self.tree.see(child)

    def start_drag(self, event) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            self._drag_source_index = None
            return
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        self._drag_source_index = self.tree.index(row_id)

    def set_context_row_from_event(self, event) -> None:
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            self.context_row_index = self.tree.index(row_id)
        else:
            self.context_row_index = -1

    def commit_active_edit(self) -> None:
        if self._active_commit:
            self._active_commit()
