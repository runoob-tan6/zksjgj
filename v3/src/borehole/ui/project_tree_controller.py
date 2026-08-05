"""Project tree rendering and selection."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from ..domain.enums import HoleType
from ..domain.models import Borehole, ProjectData
from ..domain.sorting import profile_sort_key


class ProjectTreeController:
    def __init__(self, tree: QTreeWidget) -> None:
        self.tree = tree

    def refresh(self, project: ProjectData, current_borehole: Borehole | None) -> None:
        current_key = self.current_key()
        if current_key is None and current_borehole is not None:
            current_key = current_borehole.prefix
        self.tree.clear()
        bold_font = self.tree.font()
        bold_font.setBold(True)

        zk_node = self._group("岩钻孔 ZK", bold_font)
        nzk_node = self._group("土钻孔 NZK", bold_font)
        for borehole in project.sorted_boreholes():
            parent = nzk_node if borehole.hole_type == HoleType.NZK else zk_node
            item = self._item(parent, borehole.display_name(), borehole.prefix)
            for suffix in sorted(borehole.extra_files):
                self._item(item, f".-{suffix}", f"extra:{borehole.prefix}:{suffix}")

        if project.profile_files:
            profile_node = self._group("剖面图", bold_font)
            for name in sorted(project.profile_files, key=profile_sort_key):
                profile = project.profile_files[name]
                item = self._item(profile_node, name, f"profile:{name}")
                for suffix in sorted(profile.extra_files):
                    self._item(item, f".-{suffix}", f"profile_extra:{name}:{suffix}")

        if project.project_files:
            chart_node = self._group("柱状图", bold_font)
            for name in sorted(project.project_files):
                project_file = project.project_files[name]
                for suffix in sorted(project_file.extra_files):
                    self._item(chart_node, f"{name}.-{suffix}", f"project_file:{name}:{suffix}")

        if current_key is not None:
            self.select(current_key)

    def current_key(self) -> str | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def select(self, key: str) -> bool:
        for index in range(self.tree.topLevelItemCount()):
            found = self._find(self.tree.topLevelItem(index), key)
            if found is not None:
                self.tree.setCurrentItem(found)
                self.tree.scrollToItem(found)
                return True
        return False

    def update_borehole_label(self, prefix: str, label: str) -> bool:
        for index in range(self.tree.topLevelItemCount()):
            item = self._find(self.tree.topLevelItem(index), prefix)
            if item is not None:
                item.setText(0, label)
                return True
        return False

    def _group(self, label: str, font: QFont) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self.tree, [label])
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        item.setFont(0, font)
        item.setExpanded(True)
        return item

    @staticmethod
    def _item(parent: QTreeWidgetItem, label: str, key: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent, [label])
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        return item

    @classmethod
    def _find(cls, item: QTreeWidgetItem | None, key: str) -> QTreeWidgetItem | None:
        if item is None:
            return None
        if item.data(0, Qt.ItemDataRole.UserRole) == key:
            return item
        for index in range(item.childCount()):
            found = cls._find(item.child(index), key)
            if found is not None:
                return found
        return None
