"""主窗口 - 应用入口 UI。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..application.project_service import (
    copy_borehole,
    create_empty_project,
    create_new_borehole,
    is_borehole_prefix,
    is_profile_prefix,
    load_project,
    next_borehole_prefix,
    next_profile_name,
)
from ..application.undo_manager import BoreholeSnapshot, CompositeUndoAction, UndoAction, UndoManager, copy_layers, copy_tests
from ..domain.enums import HoleType
from ..domain.models import BasicLayer, Borehole, ProfileFile, ProjectData, MAIN_FIELD_NAMES
from ..domain.validators import validate_project
from ..infrastructure.file_writer import generate_dirty_boreholes, backup_existing_file
from ..infrastructure.settings import load_last_project, save_last_project
from ..infrastructure.table_importer import import_from_table
from ..infrastructure.xlsx_export import export_layer_test_summary
from .info_pages import RawTextPage, ValidationPage, EditableTextPage
from .main_file_page import MainFilePage
from .spt_analysis_page import SPTAnalysisPage
from .test_data_page import TestDataPage


class _WorkerThread(QThread):
    """通用后台工作线程。"""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """钻孔数据编辑工具主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("钻孔数据编辑工具 v3")
        self.setMinimumSize(980, 640)
        self.resize(1180, 760)

        self._project: ProjectData = create_empty_project()
        self._current_borehole: Borehole | None = None
        self._undo_managers: dict[int, UndoManager] = {}
        self._busy = False
        self._refreshing_list = False
        self._syncing = False

        self.setAcceptDrops(True)

        self._build_menu()
        self._build_ui()
        self._build_statusbar()
        self._center_window()
        self._load_last_project()

    # ── 布局 ────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction("选择项目...", self._choose_project, QKeySequence("Ctrl+O"))
        file_menu.addAction("重新加载", self._reload_project, QKeySequence("Ctrl+R"))
        file_menu.addAction("打开文件夹", self._open_project_folder)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close, QKeySequence("Ctrl+Q"))

        edit_menu = menubar.addMenu("编辑(&E)")
        self._undo_action = QAction("撤销", self)
        self._undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self._undo_action.triggered.connect(self._undo)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("恢复", self)
        self._redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        self._redo_action.triggered.connect(self._redo)
        edit_menu.addAction(self._redo_action)

        tool_menu = menubar.addMenu("工具(&T)")
        tool_menu.addAction("新增钻孔", self._add_borehole)
        tool_menu.addAction("新增剖面文件", self._add_profile)
        tool_menu.addAction("校验项目", self._validate_project)
        tool_menu.addAction("导出试验汇总...", self._export_layer_tests)
        tool_menu.addSeparator()
        tool_menu.addAction("保存数据", self._save_data, QKeySequence("Ctrl+S"))

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧 - 钻孔列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("钻孔列表")
        lbl.setProperty("class", "title")
        left_layout.addWidget(lbl)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAlternatingRowColors(True)
        self._tree.setStyleSheet("""
            QTreeWidget::item {
                padding: 6px 4px;
                min-height: 28px;
            }
            QTreeWidget::item:selected {
                background: #C7D0FE;
                border-left: 3px solid #6C63FF;
                font-weight: bold;
            }
            QTreeWidget::item:hover {
                background: #E8ECFF;
            }
        """)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.currentItemChanged.connect(self._on_borehole_selected)
        left_layout.addWidget(self._tree)

        splitter.addWidget(left_panel)

        # 右侧 - Tab 编辑区
        self._tabs = QTabWidget()
        self._main_file_page = MainFilePage(self._begin_borehole_change, self._end_borehole_change)
        self._test_data_page = TestDataPage(self._begin_borehole_change, self._end_borehole_change)
        self._spt_analysis_page = SPTAnalysisPage()
        self._raw_text_page = RawTextPage()
        self._validation_page = ValidationPage()
        self._extra_text_page = EditableTextPage()
        self._current_extra_borehole = None
        self._current_extra_profile = None
        self._current_extra_suffix = None

        self._tabs.addTab(self._main_file_page, "基本信息")
        self._tabs.addTab(self._test_data_page, "试验数据")
        self._tabs.addTab(self._spt_analysis_page, "标贯分析")
        self._tabs.addTab(self._extra_text_page, "数据文件")
        self._tabs.addTab(self._raw_text_page, "原始文本")
        self._tabs.addTab(self._validation_page, "校验结果")

        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([120, 1060])

        # 信号连接
        self._main_file_page.field_changed.connect(self._on_field_changed)
        self._main_file_page.hole_id_changed.connect(self._on_hole_id_changed)
        self._main_file_page.layer_changed.connect(self._on_layer_changed)
        self._main_file_page.description_changed.connect(self._sync_description)
        self._test_data_page.data_changed.connect(self._on_test_changed)

    def _build_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("准备就绪")
        self._statusbar.addWidget(self._status_label)
        self._summary_label = QLabel("")
        self._statusbar.addPermanentWidget(self._summary_label)

    def _center_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    # ── 项目操作 ────────────────────────────────────────────────────

    def _load_last_project(self) -> None:
        last = load_last_project()
        if last and last.exists():
            self._load_project_path(last)
        else:
            self._set_empty_project("未加载项目。请选择项目文件夹。")

    def _choose_project(self) -> None:
        if self._busy:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择钻孔项目文件夹")
        if folder:
            self._load_project_path(Path(folder))

    def _reload_project(self) -> None:
        if self._busy:
            return
        if self._project.folder:
            self._load_project_path(self._project.folder)

    def _open_project_folder(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "当前没有加载项目。")
            return
        if self._project.folder.exists():
            os.startfile(self._project.folder)

    def _check_unsaved_changes(self) -> bool:
        """检查是否有未保存的修改，提示用户。返回 True 表示可以继续。"""
        dirty = self._project.dirty_boreholes() or self._project.deleted_boreholes
        dirty_profiles = [p for p in self._project.profile_files.values() if p.modified]
        dirty_project = [p for p in self._project.project_files.values() if p.modified]
        if not dirty and not dirty_profiles and not dirty_project:
            return True
        reply = QMessageBox.question(
            self, "未保存的修改",
            '存在未保存的数据修改，是否先保存？\n\n点击"是"保存后继续，点击"否"放弃修改。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Yes:
            if not self._save_data_sync():
                return False
        return True

    def _save_data_sync(self) -> bool:
        """同步保存数据（用于切换项目前）。返回是否保存成功。"""
        from ..infrastructure.file_writer import generate_dirty_boreholes
        dirty = self._project.dirty_boreholes()
        deleted = list(self._project.deleted_boreholes)
        dirty_profiles = [p for p in self._project.profile_files.values() if p.modified]
        deleted_profiles = list(self._project.deleted_profiles)
        dirty_project_files = [p for p in self._project.project_files.values() if p.modified]
        if not dirty and not deleted and not dirty_profiles and not deleted_profiles and not dirty_project_files:
            return True
        try:
            generated = generate_dirty_boreholes(self._project)
            # 保存剖面文件
            for profile in dirty_profiles:
                if profile.path:
                    profile.path.parent.mkdir(parents=True, exist_ok=True)
                    self._write_file_with_backup(profile.path, profile.content)
                for suffix, content in profile.extra_files.items():
                    ext_path = profile.path.parent / f"{profile.name}.-{suffix}"
                    self._write_file_with_backup(ext_path, content)
                for suffix in profile.deleted_extra_files:
                    ext_path = profile.path.parent / f"{profile.name}.-{suffix}"
                    if ext_path.exists():
                        backup_existing_file(ext_path, ext_path.parent / "tmp")
                        ext_path.unlink()
                profile.deleted_extra_files.clear()
                profile.modified = False
            # 删除剖面文件
            for name, profile in list(self._project.deleted_profiles.items()):
                if profile.path and profile.path.exists():
                    backup_existing_file(profile.path, profile.path.parent / "tmp")
                    profile.path.unlink()
                for suffix in profile.extra_files:
                    ext_path = profile.path.parent / f"{name}.-{suffix}"
                    if ext_path.exists():
                        backup_existing_file(ext_path, ext_path.parent / "tmp")
                        ext_path.unlink()
            self._project.deleted_profiles.clear()
            # 保存项目配置文件
            for pf in dirty_project_files:
                for suffix, content in pf.extra_files.items():
                    ext_path = (self._project.folder or Path.cwd()) / f"{pf.name}.-{suffix}"
                    self._write_file_with_backup(ext_path, content)
                for suffix in pf.deleted_extra_files:
                    ext_path = (self._project.folder or Path.cwd()) / f"{pf.name}.-{suffix}"
                    if ext_path.exists():
                        backup_existing_file(ext_path, (self._project.folder or Path.cwd()) / "tmp")
                        ext_path.unlink()
                pf.deleted_extra_files.clear()
                pf.modified = False
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存数据时出错：{e}")
            return False

    def _write_file_with_backup(self, path: Path, content: str) -> None:
        """写入文件，自动检测编码并备份。"""
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        encoding = "utf-8"
        if path.exists():
            for enc in ("utf-8", "gbk", "ansi"):
                try:
                    path.read_text(encoding=enc)
                    encoding = enc
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            backup_existing_file(path, path.parent / "tmp")
        path.write_text(content, encoding=encoding)

    def _load_project_path(self, folder: Path) -> None:
        if self._busy:
            return
        if not self._check_unsaved_changes():
            return
        self._set_busy(True)
        self._status_label.setText(f"正在加载：{folder.name}...")

        self._worker = _WorkerThread(load_project, folder)
        self._worker.finished.connect(lambda p: self._finish_load(folder, p))
        self._worker.error.connect(lambda e: self._on_load_error(e))
        self._worker.start()

    def _on_load_error(self, error: str) -> None:
        self._set_busy(False)
        self._set_empty_project(f"加载失败：{error}")

    def _finish_load(self, folder: Path, project: ProjectData) -> None:
        self._set_busy(False)
        if project.load_error:
            self._set_empty_project(project.load_error)
            return
        self._project = project
        self._undo_managers.clear()
        self._current_borehole = None
        save_last_project(folder)
        self._refresh_borehole_list()
        first = project.sorted_boreholes()[0] if project.boreholes else None
        self._load_current_borehole(first)
        if first:
            self._select_in_tree(first.prefix)
        self._update_summary()
        self._status_label.setText(f"已加载 {len(project.boreholes)} 个钻孔。")

    def _set_empty_project(self, message: str) -> None:
        self._project = create_empty_project()
        self._current_borehole = None
        self._undo_managers.clear()
        self._status_label.setText(message)
        self._refresh_borehole_list()
        self._load_current_borehole(None)
        self._update_summary()

    # ── 钻孔列表 ────────────────────────────────────────────────────

    def _refresh_borehole_list(self) -> None:
        # 保存当前树中实际选中的项目（可能是钻孔、剖面文件或配置文件）
        current_item = self._tree.currentItem()
        current_prefix = None
        if current_item:
            current_prefix = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not current_prefix and self._current_borehole:
            current_prefix = self._current_borehole.prefix
        self._refreshing_list = True
        try:
            self._tree.clear()
            bold_font = self._tree.font()
            bold_font.setBold(True)

            zk_node = QTreeWidgetItem(self._tree, ["岩钻孔 ZK"])
            zk_node.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            zk_node.setFont(0, bold_font)
            zk_node.setExpanded(True)
            nzk_node = QTreeWidgetItem(self._tree, ["土钻孔 NZK"])
            nzk_node.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            nzk_node.setFont(0, bold_font)
            nzk_node.setExpanded(True)

            for borehole in self._project.sorted_boreholes():
                parent = nzk_node if borehole.hole_type == HoleType.NZK else zk_node
                bh_item = QTreeWidgetItem(parent, [borehole.display_name()])
                bh_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                bh_item.setData(0, Qt.ItemDataRole.UserRole, borehole.prefix)
                # 额外数据文件
                for suffix in sorted(borehole.extra_files.keys()):
                    ext_item = QTreeWidgetItem(bh_item, [f".-{suffix}"])
                    ext_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                    ext_item.setData(0, Qt.ItemDataRole.UserRole, f"extra:{borehole.prefix}:{suffix}")

            # 剖面及柱状图
            if self._project.profile_files:
                profile_node = QTreeWidgetItem(self._tree, ["剖面及柱状图"])
                profile_node.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                profile_node.setFont(0, bold_font)
                profile_node.setExpanded(True)
                for name in sorted(self._project.profile_files.keys()):
                    profile = self._project.profile_files[name]
                    item = QTreeWidgetItem(profile_node, [name])
                    item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                    item.setData(0, Qt.ItemDataRole.UserRole, f"profile:{name}")
                    # 剖面文件的附属数据文件
                    for suffix in sorted(profile.extra_files.keys()):
                        ext_item = QTreeWidgetItem(item, [f".-{suffix}"])
                        ext_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                        ext_item.setData(0, Qt.ItemDataRole.UserRole, f"profile_extra:{name}:{suffix}")

            # 项目配置文件（0nzk.-zkt、0yzk.-zkt 等）
            if self._project.project_files:
                proj_node = QTreeWidgetItem(self._tree, ["项目配置文件"])
                proj_node.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                proj_node.setFont(0, bold_font)
                proj_node.setExpanded(True)
                for name in sorted(self._project.project_files.keys()):
                    pf = self._project.project_files[name]
                    for suffix in sorted(pf.extra_files.keys()):
                        ext_item = QTreeWidgetItem(proj_node, [f"{name}.-{suffix}"])
                        ext_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                        ext_item.setData(0, Qt.ItemDataRole.UserRole, f"project_file:{name}:{suffix}")

            if current_prefix:
                self._select_in_tree(current_prefix)
        finally:
            self._refreshing_list = False

    def _select_in_tree(self, prefix: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            parent = self._tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == prefix:
                    self._tree.setCurrentItem(child)
                    self._tree.scrollToItem(child)
                    return
                # 搜索子节点
                for k in range(child.childCount()):
                    sub = child.child(k)
                    if sub.data(0, Qt.ItemDataRole.UserRole) == prefix:
                        self._tree.setCurrentItem(sub)
                        self._tree.scrollToItem(sub)
                        return

    def _on_borehole_selected(self, current: QTreeWidgetItem, _previous) -> None:
        if not current or self._refreshing_list:
            return
        prefix = current.data(0, Qt.ItemDataRole.UserRole)
        if not prefix:
            return
        # 剖面文件主文件（可编辑）
        if prefix.startswith("profile:") and not prefix.startswith("profile_extra:"):
            name = prefix[8:]
            profile = self._project.profile_files.get(name)
            if profile:
                self._flush_active_editors()
                self._current_extra_profile = profile
                self._current_extra_suffix = None
                self._extra_text_page.set_content(
                    name, profile.content,
                    on_save=self._on_profile_main_changed,
                )
                self._tabs.setCurrentWidget(self._extra_text_page)
            return
        # 剖面文件的附属数据文件
        if prefix.startswith("profile_extra:"):
            parts = prefix.split(":")
            profile_name = parts[1]
            suffix = parts[2]
            profile = self._project.profile_files.get(profile_name)
            if profile and suffix in profile.extra_files:
                self._flush_active_editors()
                self._current_extra_profile = profile
                self._current_extra_suffix = suffix
                self._extra_text_page.set_content(
                    f"{profile_name}.-{suffix}",
                    profile.extra_files[suffix],
                    on_save=self._on_profile_extra_changed,
                )
                self._tabs.setCurrentWidget(self._extra_text_page)
            return
        # 项目配置文件
        if prefix.startswith("project_file:"):
            parts = prefix.split(":")
            file_name = parts[1]
            suffix = parts[2]
            pf = self._project.project_files.get(file_name)
            if pf and suffix in pf.extra_files:
                self._flush_active_editors()
                self._current_extra_profile = pf
                self._current_extra_suffix = suffix
                self._extra_text_page.set_content(
                    f"{file_name}.-{suffix}",
                    pf.extra_files[suffix],
                    on_save=self._on_project_file_changed,
                )
                self._tabs.setCurrentWidget(self._extra_text_page)
            return
        # 额外数据文件
        if prefix.startswith("extra:"):
            parts = prefix.split(":")
            bh_prefix = parts[1]
            suffix = parts[2]
            borehole = self._project.boreholes.get(bh_prefix)
            if borehole and suffix in borehole.extra_files:
                self._flush_active_editors()
                self._current_extra_borehole = borehole
                self._current_extra_suffix = suffix
                self._extra_text_page.set_content(
                    f"{bh_prefix}.-{suffix}",
                    borehole.extra_files[suffix],
                    on_save=self._on_extra_file_changed,
                )
                self._tabs.setCurrentWidget(self._extra_text_page)
            return
        if prefix not in self._project.boreholes:
            return
        borehole = self._project.boreholes[prefix]
        if self._current_borehole is borehole:
            return
        self._flush_active_editors()
        self._load_current_borehole(borehole)

    def _flush_active_editors(self) -> None:
        """提交所有活跃的编辑，防止切换钻孔时丢失数据。"""
        self._main_file_page._commit_field_edit()
        self._test_data_page.commit_active_edit()

    def _show_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        prefix = item.data(0, Qt.ItemDataRole.UserRole)
        self._tree.setCurrentItem(item)

        menu = QMenu(self)
        # 分类节点（无 UserRole 数据）
        if not prefix:
            item_text = item.text(0)
            if item_text == "剖面及柱状图":
                menu.addAction("新增剖面文件", self._add_profile)
                menu.exec(self._tree.viewport().mapToGlobal(pos))
            elif item_text == "项目配置文件":
                menu.addAction("新增配置文件", self._add_project_file)
                menu.exec(self._tree.viewport().mapToGlobal(pos))
            return
        # 钻孔
        if prefix in self._project.boreholes:
            menu.addAction("复制钻孔", self._copy_borehole)
            menu.addAction("新增附属文件", lambda: self._add_extra_file(prefix))
            menu.addSeparator()
            menu.addAction("删除钻孔", self._delete_borehole)
        # 剖面文件主文件
        elif prefix.startswith("profile:") and not prefix.startswith("profile_extra:"):
            name = prefix[8:]
            menu.addAction("复制剖面文件", lambda: self._copy_profile(name))
            menu.addSeparator()
            menu.addAction("删除剖面文件", lambda: self._delete_profile(name))
        # 剖面文件附属数据文件
        elif prefix.startswith("profile_extra:"):
            parts = prefix.split(":")
            profile_name = parts[1]
            suffix = parts[2]
            menu.addAction(f"删除 .-{suffix}", lambda: self._delete_profile_extra(profile_name, suffix))
        # 项目配置文件
        elif prefix.startswith("project_file:"):
            parts = prefix.split(":")
            file_name = parts[1]
            suffix = parts[2]
            menu.addAction(f"删除 {file_name}.-{suffix}", lambda: self._delete_project_file(file_name, suffix))
        # 钻孔附属数据文件
        elif prefix.startswith("extra:"):
            parts = prefix.split(":")
            bh_prefix = parts[1]
            suffix = parts[2]
            menu.addAction(f"删除 .-{suffix}", lambda: self._delete_extra_file(bh_prefix, suffix))
        else:
            return
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ── 钻孔 CRUD ──────────────────────────────────────────────────

    def _add_borehole(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "请先选择项目文件夹。")
            return
        from PySide6.QtWidgets import QInputDialog

        prefix, ok = QInputDialog.getText(self, "新增钻孔", "请输入钻孔编号，例如 ZK8 或 NZK13：")
        if not ok or not prefix.strip():
            return
        prefix = prefix.strip().upper()
        if not is_borehole_prefix(prefix):
            QMessageBox.warning(self, "提示", "钻孔编号格式不正确。")
            return
        if prefix in self._project.boreholes:
            QMessageBox.warning(self, "提示", f"钻孔 {prefix} 已存在。")
            return
        borehole = create_new_borehole(self._project, prefix)
        self._get_undo_manager(borehole)
        self._refresh_borehole_list()
        self._load_current_borehole(borehole)
        self._select_in_tree(prefix)
        self._update_summary()

    def _copy_borehole(self) -> None:
        if not self._current_borehole:
            return
        source = self._current_borehole
        default_prefix = next_borehole_prefix(self._project, source.prefix)
        from PySide6.QtWidgets import QInputDialog

        new_prefix, ok = QInputDialog.getText(self, "复制钻孔", "请输入新钻孔编号：", text=default_prefix)
        if not ok or not new_prefix.strip():
            return
        new_prefix = new_prefix.strip().upper()
        if not is_borehole_prefix(new_prefix):
            QMessageBox.warning(self, "提示", "钻孔编号格式不正确。")
            return
        if new_prefix in self._project.boreholes:
            QMessageBox.warning(self, "提示", f"钻孔 {new_prefix} 已存在。")
            return
        borehole = copy_borehole(self._project, source, new_prefix)
        self._get_undo_manager(borehole)
        self._refresh_borehole_list()
        self._load_current_borehole(borehole)
        self._select_in_tree(new_prefix)
        self._update_summary()

    def _delete_borehole(self) -> None:
        if not self._current_borehole:
            return
        prefix = self._current_borehole.prefix
        reply = QMessageBox.question(
            self, "删除钻孔", f"确定删除钻孔 {prefix}？\n\n点击保存数据后，会备份并删除该钻孔的所有原始文件。"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        borehole = self._project.boreholes.pop(prefix, None)
        if borehole and not borehole.is_new:
            self._project.deleted_boreholes[prefix] = borehole
        self._undo_managers.pop(id(borehole), None)
        next_bh = self._project.sorted_boreholes()[0] if self._project.boreholes else None
        self._refresh_borehole_list()
        self._load_current_borehole(next_bh)
        if next_bh:
            self._select_in_tree(next_bh.prefix)
        self._status_label.setText(f"已删除钻孔 {prefix}。")
        self._update_summary()

    def _copy_profile(self, name: str) -> None:
        profile = self._project.profile_files.get(name)
        if not profile:
            return
        # 生成默认新名称（H1 → H2 等）
        default_name = next_profile_name(self._project, name[0])
        from PySide6.QtWidgets import QInputDialog

        new_name, ok = QInputDialog.getText(self, "复制剖面文件", "请输入新文件名（格式如 H3 或 Z1）：", text=default_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if not is_profile_prefix(new_name):
            QMessageBox.warning(self, "提示", "文件名格式不正确，应为 H1、Z2 等格式。")
            return
        if new_name in self._project.profile_files:
            QMessageBox.warning(self, "提示", f"剖面文件 {new_name} 已存在。")
            return
        # 深拷贝剖面文件
        folder = self._project.folder or Path.cwd()
        new_profile = ProfileFile(
            name=new_name,
            path=folder / new_name,
            content=profile.content,
            extra_files=dict(profile.extra_files),
            modified=True,
        )
        self._project.profile_files[new_name] = new_profile
        self._refresh_borehole_list()
        self._select_in_tree(f"profile:{new_name}")
        self._status_label.setText(f"已复制剖面文件 {name} → {new_name}。")

    def _add_profile(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "请先选择项目文件夹。")
            return
        default_name = next_profile_name(self._project)
        from PySide6.QtWidgets import QInputDialog

        new_name, ok = QInputDialog.getText(self, "新增剖面文件", "请输入文件名（格式如 H3 或 Z1）：", text=default_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if not is_profile_prefix(new_name):
            QMessageBox.warning(self, "提示", "文件名格式不正确，应为 H1、Z2 等格式。")
            return
        if new_name in self._project.profile_files:
            QMessageBox.warning(self, "提示", f"剖面文件 {new_name} 已存在。")
            return
        folder = self._project.folder
        new_profile = ProfileFile(
            name=new_name,
            path=folder / new_name,
            content="",
            modified=True,
        )
        self._project.profile_files[new_name] = new_profile
        self._refresh_borehole_list()
        self._select_in_tree(f"profile:{new_name}")
        self._status_label.setText(f"已新增剖面文件 {new_name}。")

    def _delete_profile(self, name: str) -> None:
        profile = self._project.profile_files.get(name)
        if not profile:
            return
        reply = QMessageBox.question(
            self, "删除剖面文件", f"确定删除剖面文件 {name}？\n\n点击保存数据后，会备份并删除该文件。"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._project.deleted_profiles[name] = profile
        del self._project.profile_files[name]
        self._current_extra_profile = None
        self._current_extra_suffix = None
        self._refresh_borehole_list()
        self._load_current_borehole(self._current_borehole)
        self._status_label.setText(f"已删除剖面文件 {name}。")

    def _delete_profile_extra(self, profile_name: str, suffix: str) -> None:
        profile = self._project.profile_files.get(profile_name)
        if not profile or suffix not in profile.extra_files:
            return
        reply = QMessageBox.question(
            self, "删除附属文件", f"确定删除 {profile_name}.-{suffix}？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del profile.extra_files[suffix]
        profile.deleted_extra_files.add(suffix)
        profile.modified = True
        self._current_extra_profile = None
        self._current_extra_suffix = None
        self._refresh_borehole_list()
        self._status_label.setText(f"已删除 {profile_name}.-{suffix}。")

    def _add_project_file(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "请先选择项目文件夹。")
            return
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "新增配置文件", "请输入文件名前缀（如 0nzk、0yzk）：")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.startswith("0"):
            QMessageBox.warning(self, "提示", "配置文件名应以 0 开头，如 0nzk、0yzk。")
            return
        suffix, ok = QInputDialog.getText(self, "新增配置文件", "请输入文件后缀（如 zkt）：", text="zkt")
        if not ok or not suffix.strip():
            return
        suffix = suffix.strip().lstrip(".-")
        full_key = f"{name}.-{suffix}"
        if name in self._project.project_files and suffix in self._project.project_files[name].extra_files:
            QMessageBox.warning(self, "提示", f"{full_key} 已存在。")
            return
        folder = self._project.folder
        if name not in self._project.project_files:
            pf = ProfileFile(name=name, path=folder / name, modified=True)
            self._project.project_files[name] = pf
        else:
            pf = self._project.project_files[name]
            pf.modified = True
        pf.extra_files[suffix] = ""
        self._refresh_borehole_list()
        self._select_in_tree(f"project_file:{name}:{suffix}")
        self._status_label.setText(f"已新增配置文件 {full_key}。")

    def _delete_project_file(self, file_name: str, suffix: str) -> None:
        pf = self._project.project_files.get(file_name)
        if not pf or suffix not in pf.extra_files:
            return
        reply = QMessageBox.question(
            self, "删除配置文件", f"确定删除 {file_name}.-{suffix}？\n\n点击保存数据后，会备份并删除该文件。"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del pf.extra_files[suffix]
        pf.deleted_extra_files.add(suffix)
        pf.modified = True
        self._current_extra_profile = None
        self._current_extra_suffix = None
        self._refresh_borehole_list()
        self._status_label.setText(f"已删除 {file_name}.-{suffix}。")

    def _delete_extra_file(self, bh_prefix: str, suffix: str) -> None:
        borehole = self._project.boreholes.get(bh_prefix)
        if not borehole or suffix not in borehole.extra_files:
            return
        reply = QMessageBox.question(
            self, "删除附属文件", f"确定删除 {bh_prefix}.-{suffix}？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del borehole.extra_files[suffix]
        borehole.deleted_extra_files.add(suffix)
        borehole.mark_dirty(suffix)
        self._current_extra_borehole = None
        self._current_extra_suffix = None
        self._refresh_borehole_list()
        self._status_label.setText(f"已删除 {bh_prefix}.-{suffix}。")

    def _add_extra_file(self, bh_prefix: str) -> None:
        borehole = self._project.boreholes.get(bh_prefix)
        if not borehole:
            return
        from PySide6.QtWidgets import QInputDialog

        suffix, ok = QInputDialog.getText(self, "新增附属文件", "请输入文件后缀（如 zkt、d0）：")
        if not ok or not suffix.strip():
            return
        suffix = suffix.strip().lstrip(".-")
        if suffix in borehole.extra_files:
            QMessageBox.warning(self, "提示", f"{bh_prefix}.-{suffix} 已存在。")
            return
        borehole.extra_files[suffix] = ""
        borehole.mark_dirty(suffix)
        self._refresh_borehole_list()
        self._select_in_tree(f"extra:{bh_prefix}:{suffix}")
        self._status_label.setText(f"已新增 {bh_prefix}.-{suffix}。")

    def _load_current_borehole(self, borehole: Borehole | None) -> None:
        self._current_borehole = borehole
        self._current_extra_borehole = None
        self._current_extra_profile = None
        self._current_extra_suffix = None
        self._main_file_page.load_borehole(borehole)
        self._test_data_page.load_borehole(borehole)
        self._spt_analysis_page.load_project(self._project)
        self._raw_text_page.load_borehole(borehole)
        self._validation_page.load_borehole(borehole)
        if borehole:
            if self._tabs.currentWidget() == self._extra_text_page:
                self._tabs.setCurrentWidget(self._main_file_page)
            self._status_label.setText(f"当前钻孔：{borehole.prefix}")

    def _on_extra_file_changed(self, name: str, content: str) -> None:
        if self._current_extra_borehole and self._current_extra_suffix:
            self._current_extra_borehole.extra_files[self._current_extra_suffix] = content
            self._current_extra_borehole.mark_dirty(self._current_extra_suffix)
            self._update_summary()
            prefix = self._current_extra_borehole.prefix
            self._status_label.setText(f"{prefix}.-{self._current_extra_suffix} 已修改。")
        self._update_undo_controls()

    def _on_profile_extra_changed(self, name: str, content: str) -> None:
        if self._current_extra_profile and self._current_extra_suffix:
            self._current_extra_profile.extra_files[self._current_extra_suffix] = content
            self._current_extra_profile.modified = True
            profile_name = self._current_extra_profile.name
            self._status_label.setText(f"{profile_name}.-{self._current_extra_suffix} 已修改。")

    def _on_profile_main_changed(self, name: str, content: str) -> None:
        if self._current_extra_profile:
            self._current_extra_profile.content = content
            self._current_extra_profile.modified = True
            self._status_label.setText(f"{self._current_extra_profile.name} 已修改。")

    def _on_project_file_changed(self, name: str, content: str) -> None:
        if self._current_extra_profile and self._current_extra_suffix:
            self._current_extra_profile.extra_files[self._current_extra_suffix] = content
            self._current_extra_profile.modified = True
            file_name = self._current_extra_profile.name
            self._status_label.setText(f"{file_name}.-{self._current_extra_suffix} 已修改。")

    # ── Dirty 标记 ──────────────────────────────────────────────────

    def _on_field_changed(self, _index: int, _old: str, _new: str) -> None:
        self._mark_dirty("main")

    def _on_hole_id_changed(self, old_prefix: str, new_prefix: str) -> None:
        if old_prefix == new_prefix:
            self._mark_dirty("main")
            return
        if not is_borehole_prefix(new_prefix):
            QMessageBox.warning(self, "提示", "钻孔编号格式不正确。")
            self._main_file_page.set_hole_id(old_prefix)
            return
        if new_prefix in self._project.boreholes:
            QMessageBox.warning(self, "提示", f"钻孔编号 {new_prefix} 已存在。")
            self._main_file_page.set_hole_id(old_prefix)
            return
        borehole = self._project.boreholes.pop(old_prefix)
        borehole.old_prefix = old_prefix
        borehole.mark_dirty("main")
        borehole.prefix = new_prefix
        borehole.hole_type = HoleType.NZK if new_prefix.upper().startswith("NZK") else HoleType.ZK
        self._project.boreholes[new_prefix] = borehole
        self._current_borehole = borehole
        self._refresh_borehole_list()
        self._select_in_tree(new_prefix)
        self._status_label.setText(f"当前钻孔：{new_prefix}")
        self._update_summary()

    def _on_layer_changed(self, suffix: str) -> None:
        self._mark_dirty(suffix)

    def _on_test_changed(self, suffix: str) -> None:
        self._mark_dirty(suffix)

    def _mark_dirty(self, suffix: str | None = None) -> None:
        if self._current_borehole:
            self._current_borehole.mark_dirty(suffix)
            self._update_summary()
            prefix = self._current_borehole.prefix
            self._refresh_borehole_list()
            self._select_in_tree(prefix)
            self._status_label.setText(f"{prefix} 已修改。")

    def _sync_description(self, description: str, lithology_code: str, formation: str, weathering: str) -> None:
        """将岩性描述同步到所有匹配 (岩性代号, 地层时代, 风化程度) 的其他钻孔。"""
        if self._syncing or not self._current_borehole:
            return
        self._syncing = True
        try:
            affected: list[tuple[Borehole, BasicLayer]] = []
            for prefix, bh in self._project.boreholes.items():
                if bh is self._current_borehole:
                    continue
                for layer in bh.layers:
                    if (layer.lithology_code == lithology_code
                            and layer.weathering == weathering
                            and (not formation or layer.formation == formation)
                            and not layer.description):
                        affected.append((bh, layer))

            if not affected:
                return

            actions: list[UndoAction] = []
            # 为每个受影响的钻孔拍快照
            affected_boreholes: dict[int, tuple[Borehole, BoreholeSnapshot]] = {}
            for bh, layer in affected:
                key = id(bh)
                if key not in affected_boreholes:
                    affected_boreholes[key] = (bh, BoreholeSnapshot.capture(bh))
                layer.description = description
                bh.mark_dirty("h")

            for key, (bh, before) in affected_boreholes.items():
                after = BoreholeSnapshot.capture(bh)
                if not before.same_content(after):
                    actions.append(UndoAction(borehole=bh, label="同步岩性描述", before=before, after=after))

            if actions:
                manager = self._get_undo_manager(self._current_borehole)
                if manager:
                    if len(actions) == 1:
                        manager.push(actions[0])
                    else:
                        manager.push_composite(CompositeUndoAction(actions=actions, label="同步岩性描述"))
                self._update_undo_controls()

            count = len(affected_boreholes)
            if count > 0:
                self._status_label.setText(f"已同步岩性描述到 {count} 个钻孔。")
        finally:
            self._syncing = False

    # ── 撤销/重做 ──────────────────────────────────────────────────

    def _begin_borehole_change(self, borehole: Borehole | None, label: str):
        if not borehole:
            return None
        return {"borehole": borehole, "label": label, "before": BoreholeSnapshot.capture(borehole)}

    def _end_borehole_change(self, token) -> None:
        if not token:
            return
        borehole = token["borehole"]
        before = token["before"]
        after = BoreholeSnapshot.capture(borehole)
        if before.same_content(after):
            return
        manager = self._get_undo_manager(borehole)
        if manager:
            manager.push(UndoAction(borehole=borehole, label=token["label"], before=before, after=after))
        self._update_undo_controls()

    def _get_undo_manager(self, borehole: Borehole | None) -> UndoManager | None:
        if not borehole:
            return None
        key = id(borehole)
        if key not in self._undo_managers:
            self._undo_managers[key] = UndoManager()
        return self._undo_managers[key]

    def _undo(self) -> None:
        manager = self._get_undo_manager(self._current_borehole)
        if not manager:
            return
        action = manager.pop_undo()
        if not action:
            return
        if isinstance(action, CompositeUndoAction):
            for a in reversed(action.actions):
                self._apply_snapshot(a.borehole, a.before)
            manager.push_redo(action)
        else:
            self._apply_snapshot(action.borehole, action.before)
            manager.push_redo(action)
        self._status_label.setText(f"已撤销：{action.label}")
        self._update_undo_controls()

    def _redo(self) -> None:
        manager = self._get_undo_manager(self._current_borehole)
        if not manager:
            return
        action = manager.pop_redo()
        if not action:
            return
        if isinstance(action, CompositeUndoAction):
            for a in action.actions:
                self._apply_snapshot(a.borehole, a.after)
            manager.push_undo_without_clearing_redo(action)
        else:
            self._apply_snapshot(action.borehole, action.after)
            manager.push_undo_without_clearing_redo(action)
        self._status_label.setText(f"已恢复：{action.label}")
        self._update_undo_controls()

    def _apply_snapshot(self, borehole: Borehole, snapshot: BoreholeSnapshot) -> None:
        old_key = borehole.prefix
        if old_key in self._project.boreholes and self._project.boreholes[old_key] is borehole:
            del self._project.boreholes[old_key]
        snapshot.restore(borehole)
        borehole.dirty = True
        self._project.boreholes[borehole.prefix] = borehole
        self._current_borehole = borehole
        self._refresh_borehole_list()
        self._load_current_borehole(borehole)
        self._select_in_tree(borehole.prefix)

    def _update_undo_controls(self) -> None:
        manager = self._get_undo_manager(self._current_borehole)
        can_undo = manager.can_undo() if manager else False
        can_redo = manager.can_redo() if manager else False
        if self._busy:
            can_undo = can_redo = False
        self._undo_action.setEnabled(can_undo)
        self._redo_action.setEnabled(can_redo)

    # ── 保存/导出/校验 ──────────────────────────────────────────────

    def _save_data(self) -> None:
        if self._busy:
            return
        dirty = self._project.dirty_boreholes()
        deleted = list(self._project.deleted_boreholes)
        # 检查剖面文件是否有修改
        dirty_profiles = [p for p in self._project.profile_files.values() if p.modified]
        deleted_profiles = list(self._project.deleted_profiles)
        # 检查项目配置文件是否有修改
        dirty_project_files = [p for p in self._project.project_files.values() if p.modified]
        if not dirty and not deleted and not dirty_profiles and not deleted_profiles and not dirty_project_files:
            QMessageBox.information(self, "保存数据", "没有需要保存的数据。")
            return

        parts = []
        if dirty:
            parts.append("将保存钻孔：\n" + "\n".join(b.prefix for b in dirty))
        if deleted:
            parts.append("将删除钻孔：\n" + "\n".join(deleted))
        if dirty_profiles:
            parts.append("将保存剖面文件：\n" + "\n".join(p.name for p in dirty_profiles))
        if deleted_profiles:
            parts.append("将删除剖面文件：\n" + "\n".join(deleted_profiles))
        if dirty_project_files:
            parts.append("将保存项目配置文件：\n" + "\n".join(p.name for p in dirty_project_files))
        prompt = "\n\n".join(parts) + "\n\n是否继续？"

        reply = QMessageBox.question(self, "保存数据", prompt)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True)
        self._status_label.setText("正在保存...")

        def _detect_encoding(path: Path) -> str:
            """检测文件编码，返回编码名称。"""
            if not path.exists():
                return "utf-8"
            for encoding in ("utf-8", "gbk", "ansi"):
                try:
                    path.read_text(encoding=encoding)
                    return encoding
                except (UnicodeDecodeError, UnicodeError):
                    continue
            return "utf-8"

        def _write_if_changed(path: Path, content: str) -> bool:
            """只在内容有变化时写入文件，返回是否实际写入。"""
            encoding = _detect_encoding(path)
            if path.exists():
                try:
                    existing = path.read_text(encoding=encoding)
                    if existing == content:
                        return False
                except (UnicodeDecodeError, UnicodeError):
                    pass
            backup_existing_file(path, path.parent / "tmp")
            path.write_text(content, encoding=encoding)
            return True

        def save_all():
            generated = generate_dirty_boreholes(self._project)
            profile_count = 0
            # 保存剖面文件
            for profile in dirty_profiles:
                if profile.path:
                    profile.path.parent.mkdir(parents=True, exist_ok=True)
                    if _write_if_changed(profile.path, profile.content):
                        profile_count += 1
                profile.modified = False
                for suffix, content in profile.extra_files.items():
                    ext_path = profile.path.parent / f"{profile.name}.-{suffix}"
                    if _write_if_changed(ext_path, content):
                        profile_count += 1
                # 删除标记为删除的剖面附属文件
                for suffix in profile.deleted_extra_files:
                    ext_path = profile.path.parent / f"{profile.name}.-{suffix}"
                    if ext_path.exists():
                        backup_existing_file(ext_path, ext_path.parent / "tmp")
                        ext_path.unlink()
                        profile_count += 1
                profile.deleted_extra_files.clear()
            # 删除剖面文件
            for name, profile in list(self._project.deleted_profiles.items()):
                if profile.path and profile.path.exists():
                    backup_existing_file(profile.path, profile.path.parent / "tmp")
                    profile.path.unlink()
                    profile_count += 1
                for suffix in profile.extra_files:
                    ext_path = profile.path.parent / f"{name}.-{suffix}"
                    if ext_path.exists():
                        backup_existing_file(ext_path, ext_path.parent / "tmp")
                        ext_path.unlink()
                        profile_count += 1
            self._project.deleted_profiles.clear()
            # 保存项目配置文件
            for pf in dirty_project_files:
                for suffix, content in pf.extra_files.items():
                    ext_path = (self._project.folder or Path.cwd()) / f"{pf.name}.-{suffix}"
                    if _write_if_changed(ext_path, content):
                        profile_count += 1
                for suffix in pf.deleted_extra_files:
                    ext_path = (self._project.folder or Path.cwd()) / f"{pf.name}.-{suffix}"
                    if ext_path.exists():
                        backup_existing_file(ext_path, (self._project.folder or Path.cwd()) / "tmp")
                        ext_path.unlink()
                        profile_count += 1
                pf.deleted_extra_files.clear()
                pf.modified = False
            return generated, profile_count

        self._worker = _WorkerThread(save_all)
        self._worker.finished.connect(self._finish_save)
        self._worker.error.connect(lambda e: self._on_save_error(e))
        self._worker.start()

    def _finish_save(self, result: tuple[list[Path], int]) -> None:
        generated, profile_count = result
        self._set_busy(False)
        self._undo_managers.clear()
        # 保存前记录当前编辑状态（_refresh_borehole_list 内部的 _on_borehole_selected 会清除这些状态）
        saved_extra_profile = self._current_extra_profile
        saved_extra_suffix = self._current_extra_suffix
        saved_borehole = self._current_borehole
        self._refresh_borehole_list()
        # 保存后恢复到之前编辑的位置（剖面文件、配置文件或钻孔）
        if saved_extra_profile:
            if saved_extra_suffix:
                self._select_in_tree(f"profile_extra:{saved_extra_profile.name}:{saved_extra_suffix}")
            else:
                self._select_in_tree(f"profile:{saved_extra_profile.name}")
            # 恢复状态（_refresh_borehole_list 内部的 _on_borehole_selected 已清除）
            self._current_extra_profile = saved_extra_profile
            self._current_extra_suffix = saved_extra_suffix
        elif saved_borehole:
            self._select_in_tree(saved_borehole.prefix)
            # 确保钻孔数据被正确加载（_select_in_tree 可能因 item 已选中而不触发 currentItemChanged）
            self._load_current_borehole(saved_borehole)
        self._update_summary()
        self._update_undo_controls()
        total = len(generated) + profile_count
        self._status_label.setText(f"已保存，更新 {total} 个文件（钻孔 {len(generated)}，剖面 {profile_count}）。")
        QMessageBox.information(self, "保存完成", f"实际更新 {total} 个文件。\n\n钻孔文件：{len(generated)} 个\n剖面文件：{profile_count} 个")

    def _on_save_error(self, error: str) -> None:
        self._set_busy(False)
        self._status_label.setText("保存失败。")
        QMessageBox.critical(self, "保存失败", error)

    def _validate_project(self) -> None:
        messages = validate_project(self._project)
        if not messages:
            QMessageBox.information(self, "校验结果", "未发现明显问题。")
            self._status_label.setText("校验完成：无问题。")
        else:
            QMessageBox.warning(self, "校验结果", "\n".join(messages[:20]) + ("\n..." if len(messages) > 20 else ""))
            self._status_label.setText(f"校验完成：{len(messages)} 项问题。")
        self._validation_page.load_borehole(self._current_borehole)

    def _export_layer_tests(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "请先选择项目文件夹。")
            return
        default_name = f"0{self._project.folder.name}_试验汇总.xlsx"
        default_path = str(self._project.folder / default_name)
        path, _ = QFileDialog.getSaveFileName(
            self, "导出试验汇总", default_path, "Excel 工作簿 (*.xlsx);;CSV 文件 (*.csv)"
        )
        if not path:
            return
        self._status_label.setText("正在导出...")
        self._worker = _WorkerThread(export_layer_test_summary, self._project, Path(path))
        self._worker.finished.connect(lambda count: self._finish_export(count, path))
        self._worker.error.connect(lambda e: QMessageBox.critical(self, "导出失败", e))
        self._worker.start()

    def _finish_export(self, count: int, path: str) -> None:
        self._status_label.setText(f"已导出 {count} 行。")
        reply = QMessageBox.question(
            self, "导出完成",
            f"已导出 {count} 行试验数据。\n{path}\n\n是否打开文件？"
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(path)

    # ── 辅助 ────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        # 禁用/启用菜单
        for menu in self.menuBar().actions():
            menu.setEnabled(not busy)
        self._update_undo_controls()

    def _update_summary(self) -> None:
        total_depth = 0.0
        counts = {"o": 0, "q": 0, "n": 0, "m": 0}
        for borehole in self._project.boreholes.values():
            try:
                total_depth += float(borehole.main.depth.strip())
            except (ValueError, AttributeError):
                pass
            for suffix in counts:
                records = borehole.tests.get(suffix, [])
                counts[suffix] += sum(1 for r in records if any(str(v).strip() for v in r.values))
        depth_text = f"{total_depth:g}" if total_depth else "--"
        self._summary_label.setText(
            f"总深度：{depth_text} m | 取样：{counts['o']} | 标贯：{counts['q']} | "
            f"注水：{counts['n']} | 压水：{counts['m']}"
        )

    def closeEvent(self, event) -> None:
        dirty = self._project.dirty_boreholes() or self._project.deleted_boreholes
        dirty_profiles = [p for p in self._project.profile_files.values() if p.modified]
        dirty_project = [p for p in self._project.project_files.values() if p.modified]
        if dirty or dirty_profiles or dirty_project:
            reply = QMessageBox.question(
                self, "关闭确认", "存在未保存的数据修改，确定退出？"
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if self._busy:
            return
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self._load_project_path(path)
                event.acceptProposedAction()
                return
            if path.suffix.lower() in (".xlsx", ".xls", ".csv"):
                self._import_table_file(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def _import_table_file(self, file_path: Path) -> None:
        if self._busy:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择项目保存位置")
        if not folder:
            return
        project_folder = Path(folder)
        self._set_busy(True)
        self._status_label.setText(f"正在从 {file_path.name} 导入...")

        def worker():
            return import_from_table(file_path, project_folder)

        self._worker = _WorkerThread(worker)
        self._worker.finished.connect(lambda p: self._finish_load(project_folder, p))
        self._worker.error.connect(lambda e: self._on_import_error(e))
        self._worker.start()

    def _on_import_error(self, error: str) -> None:
        self._set_busy(False)
        self._status_label.setText("导入失败。")
        QMessageBox.critical(self, "导入失败", error)
