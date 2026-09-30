"""主窗口 - 应用入口 UI。"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from math import isfinite
from pathlib import Path
from typing import Any, TypedDict

from PySide6.QtCore import QPoint, Qt, QThread
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..application.backup_restore import BackupEntry, list_backups, restore_backups
from ..application.column_chart_service import synchronize_column_charts
from ..application.project_file_operations import ProjectFileOperations
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
from ..application.save_service import SaveService
from ..application.task_runner import TaskRunner
from ..application.undo_manager import (
    BoreholeSnapshot,
    CompositeUndoAction,
    UndoAction,
    UndoManager,
)
from ..domain.enums import HoleType
from ..domain.models import BasicLayer, Borehole, ProfileFile, ProjectData
from ..domain.validators import validate_project
from ..infrastructure.settings import load_last_project, save_last_project
from ..infrastructure.table_importer import import_from_table
from ..infrastructure.text_io import read_text_auto
from ..infrastructure.xlsx_export import export_layer_test_summary
from .info_pages import EditableTextPage, RawTextPage, ValidationPage
from .main_file_page import MainFilePage
from .project_tree_controller import ProjectTreeController
from .spt_analysis_page import SPTAnalysisPage
from .test_data_page import TestDataPage
from .undo_controller import UndoController

logger = logging.getLogger(__name__)


class _ChangeToken(TypedDict):
    borehole: Borehole
    label: str
    before: BoreholeSnapshot


class MainWindow(QMainWindow):
    """钻孔数据编辑工具主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("钻孔数据编辑工具 v3.1")
        self.setMinimumSize(980, 640)
        self.resize(1180, 760)

        self._project: ProjectData = create_empty_project()
        self._current_borehole: Borehole | None = None
        self._undo_controller = UndoController()
        self._busy = False
        self._refreshing_list = False
        self._syncing = False
        self._task_runner = TaskRunner(self)
        self._task_runner.finished.connect(self._on_task_finished)
        self._worker: QThread | None = None

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
        file_menu.addAction("恢复备份...", self._restore_backup)
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
        self._tree_controller = ProjectTreeController(self._tree)

        splitter.addWidget(left_panel)

        # 右侧 - Tab 编辑区
        self._tabs = QTabWidget()
        self._main_file_page = MainFilePage(self._begin_borehole_change, self._end_borehole_change)
        self._test_data_page = TestDataPage(self._begin_borehole_change, self._end_borehole_change)
        self._spt_analysis_page = SPTAnalysisPage()
        self._raw_text_page = RawTextPage()
        self._validation_page = ValidationPage()
        self._extra_text_page = EditableTextPage()
        self._current_extra_borehole: Borehole | None = None
        self._current_extra_profile: ProfileFile | None = None
        self._current_extra_suffix: str | None = None

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
        initial_folder = self._project.folder
        if not initial_folder:
            last_project = load_last_project()
            if last_project and last_project.exists():
                initial_folder = last_project
        if not initial_folder:
            initial_folder = Path.home()
        folder = QFileDialog.getExistingDirectory(self, "选择钻孔项目文件夹", str(initial_folder))
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

    def _restore_backup(self) -> None:
        if self._busy:
            return
        folder = self._project.folder
        if not folder:
            QMessageBox.information(self, "恢复备份", "当前没有加载项目。")
            return
        entries = list_backups(folder)
        if not entries:
            QMessageBox.information(self, "恢复备份", "当前项目没有可用的备份文件。")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("恢复备份")
        dialog.setMinimumSize(680, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("请选择要恢复的备份文件（可多选）："))
        preview_layout = QHBoxLayout()
        backups = QListWidget()
        backups.setMinimumWidth(290)
        backups.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for entry in entries:
            item = QListWidgetItem(
                f"{entry.target_name}    {self._format_backup_time(entry.created_at)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry)
            backups.addItem(item)
        preview_layout.addWidget(backups)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        preview_layout.addWidget(preview)
        layout.addLayout(preview_layout)

        def update_preview() -> None:
            selected_items = backups.selectedItems()
            if len(selected_items) != 1:
                preview.setPlainText("请选择一个备份文件预览内容。")
                return
            entry = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if not isinstance(entry, BackupEntry):
                return
            target = folder / entry.target_name
            backup_text = self._read_preview_text(entry.backup)
            current_text = self._read_preview_text(target) if target.exists() else "[当前文件不存在]"
            preview.setPlainText(
                f"目标文件：{target}\n"
                f"备份时间：{self._format_backup_time(entry.created_at)}\n\n"
                "========== 备份内容 ==========\n"
                f"{backup_text}\n"
                "========== 当前内容 ==========\n"
                f"{current_text}"
            )

        backups.itemSelectionChanged.connect(update_preview)
        update_preview()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = [item.data(Qt.ItemDataRole.UserRole) for item in backups.selectedItems()]
        if not selected:
            QMessageBox.information(self, "恢复备份", "请至少选择一个备份文件。")
            return
        selected_entries = [entry for entry in selected if isinstance(entry, BackupEntry)]
        if self._check_unsaved_changes() is False:
            return
        names = "\n".join(f"  {entry.target_name}" for entry in selected_entries)
        reply = QMessageBox.question(
            self,
            "确认恢复",
            f"将恢复以下文件：\n{names}\n\n当前文件会先备份到 tmp，是否继续？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            restored = restore_backups(folder, selected_entries)
        except Exception as error:
            logger.exception("Backup restore failed")
            QMessageBox.critical(self, "恢复失败", f"恢复备份时出错：{error}")
            return
        self._load_project_path(folder)
        self._status_label.setText(f"已恢复 {len(restored)} 个文件，正在重新加载项目。")

    @staticmethod
    def _format_backup_time(value: str) -> str:
        return (
            f"{value[:4]}-{value[4:6]}-{value[6:8]} "
            f"{value[8:10]}:{value[10:12]}:{value[12:14]}"
        )

    @staticmethod
    def _read_preview_text(path: Path) -> str:
        try:
            return read_text_auto(path).text
        except Exception as error:
            return f"[无法读取：{error}]"

    def _check_unsaved_changes(self) -> bool:
        """检查是否有未保存的修改，提示用户。返回 True 表示可以继续。"""
        if not SaveService(self._project).summary().has_changes:
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
        service = SaveService(self._project)
        if not service.summary().has_changes:
            return True
        try:
            service.save()
            return True
        except Exception as error:
            logger.exception("Synchronous save failed")
            QMessageBox.critical(self, "保存失败", f"保存数据时出错：{error}")
            return False

    def _load_project_path(self, folder: Path) -> None:
        if self._busy:
            return
        if not self._check_unsaved_changes():
            return
        self._status_label.setText(f"正在加载：{folder.name}...")
        self._start_task(
            lambda: load_project(folder),
            lambda project: self._finish_load(folder, project),
            self._on_load_error,
        )

    def _on_load_error(self, error: str) -> None:
        self._set_busy(False)
        self._set_empty_project(f"加载失败：{error}")

    def _finish_load(self, folder: Path, project: ProjectData) -> None:
        self._set_busy(False)
        if project.load_error:
            self._set_empty_project(project.load_error)
            return
        self._project = project
        self._undo_controller.clear()
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
        self._undo_controller.clear()
        self._status_label.setText(message)
        self._refresh_borehole_list()
        self._load_current_borehole(None)
        self._update_summary()

    # ── 钻孔列表 ────────────────────────────────────────────────────

    def _refresh_borehole_list(self) -> None:
        self._refreshing_list = True
        try:
            self._tree_controller.refresh(self._project, self._current_borehole)
        finally:
            self._refreshing_list = False

    def _select_in_tree(self, prefix: str) -> None:
        self._tree_controller.select(prefix)

    def _on_borehole_selected(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if not current or self._refreshing_list:
            return
        raw_prefix = current.data(0, Qt.ItemDataRole.UserRole)
        if not raw_prefix:
            return
        prefix = str(raw_prefix)
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
        # 柱状图文件
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
                    on_save=self._on_profile_extra_changed,
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
            # 当前钻孔可能仍相同，但上一次选择的剖面/附属文件会把页签留在“数据文件”。
            self._tabs.setCurrentWidget(self._main_file_page)
            return
        self._flush_active_editors()
        self._load_current_borehole(borehole)

    def _flush_active_editors(self) -> None:
        """提交所有活跃的编辑，防止切换钻孔时丢失数据。"""
        self._main_file_page.commit_active_edit()
        self._test_data_page.commit_active_edit()

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        prefix = item.data(0, Qt.ItemDataRole.UserRole)
        self._tree.setCurrentItem(item)

        menu = QMenu(self)
        # 分类节点（无 UserRole 数据）
        if not prefix:
            item_text = item.text(0)
            if item_text == "剖面图":
                menu.addAction("新增剖面文件", self._add_profile)
                menu.exec(self._tree.viewport().mapToGlobal(pos))
            elif item_text == "柱状图":
                menu.addAction("新增柱状图文件", self._add_project_file)
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
            menu.addAction("重命名剖面文件", lambda: self._rename_profile(name))
            menu.addSeparator()
            menu.addAction("删除剖面文件", lambda: self._delete_profile(name))
        # 剖面文件附属数据文件
        elif prefix.startswith("profile_extra:"):
            parts = prefix.split(":")
            profile_name = parts[1]
            suffix = parts[2]
            menu.addAction(
                "复制附属文件",
                lambda: self._copy_profile_extra(profile_name, suffix),
            )
            menu.addAction(f"删除 .-{suffix}", lambda: self._delete_profile_extra(profile_name, suffix))
        # 柱状图文件
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
        synchronize_column_charts(self._project)
        self._refresh_borehole_list()
        self._load_current_borehole(borehole)
        self._select_in_tree(prefix)
        self._update_summary()

    def _copy_borehole(self) -> None:
        if not self._current_borehole:
            return
        source = self._current_borehole
        default_prefix = next_borehole_prefix(self._project, source.prefix)
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
        synchronize_column_charts(self._project)
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
        self._undo_controller.remove(prefix)
        next_bh = self._project.sorted_boreholes()[0] if self._project.boreholes else None
        synchronize_column_charts(self._project)
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
        new_name, ok = QInputDialog.getText(
            self, "复制剖面文件", "请输入新文件名（格式如 H3 或 Z1）：", text=default_name
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if not is_profile_prefix(new_name):
            QMessageBox.warning(self, "提示", "文件名格式不正确，应为 H1、Z2 等格式。")
            return
        if new_name in self._project.profile_files:
            QMessageBox.warning(self, "提示", f"剖面文件 {new_name} 已存在。")
            return
        ProjectFileOperations(self._project).copy_profile(name, new_name)
        self._refresh_borehole_list()
        self._select_in_tree(f"profile:{new_name}")
        self._status_label.setText(f"已复制剖面文件 {name} → {new_name}。")

    def _rename_profile(self, name: str) -> None:
        profile = self._project.profile_files.get(name)
        if not profile:
            return
        self._flush_active_editors()
        new_name, ok = QInputDialog.getText(
            self, "重命名剖面文件", "请输入新文件名（格式如 H3 或 Z1）：", text=name
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip().upper()
        if new_name == name:
            return
        if not is_profile_prefix(new_name):
            QMessageBox.warning(self, "提示", "文件名格式不正确，应为 H1、Z2 等格式。")
            return
        if new_name in self._project.profile_files:
            QMessageBox.warning(self, "提示", f"剖面文件 {new_name} 已存在。")
            return

        folder = self._project.folder or profile.path.parent
        disk_name = profile.old_name or profile.name
        current_paths = {folder / disk_name}
        current_paths.update(folder / f"{disk_name}.-{suffix}" for suffix in profile.extra_files)
        target_paths = [folder / new_name]
        target_paths.extend(folder / f"{new_name}.-{suffix}" for suffix in profile.extra_files)
        conflict = next((path for path in target_paths if path.exists() and path not in current_paths), None)
        if conflict:
            QMessageBox.warning(self, "提示", f"目标文件已存在：{conflict.name}")
            return

        ProjectFileOperations(self._project).rename_profile(name, new_name)
        self._refresh_borehole_list()
        self._select_in_tree(f"profile:{new_name}")
        self._status_label.setText(f"已重命名剖面文件 {name} → {new_name}。")

    def _add_profile(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "请先选择项目文件夹。")
            return
        default_name = next_profile_name(self._project)
        new_name, ok = QInputDialog.getText(
            self, "新增剖面文件", "请输入文件名（格式如 H3 或 Z1）：", text=default_name
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if not is_profile_prefix(new_name):
            QMessageBox.warning(self, "提示", "文件名格式不正确，应为 H1、Z2 等格式。")
            return
        if new_name in self._project.profile_files:
            QMessageBox.warning(self, "提示", f"剖面文件 {new_name} 已存在。")
            return
        ProjectFileOperations(self._project).create_profile(new_name)
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
        ProjectFileOperations(self._project).delete_profile(name)
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

    def _copy_profile_extra(self, profile_name: str, suffix: str) -> None:
        source = self._project.profile_files.get(profile_name)
        if not source or suffix not in source.extra_files:
            return
        target_name, ok = QInputDialog.getText(
            self,
            "复制附属文件",
            f"请输入目标剖面文件名（例如 H2，将复制为 H2.-{suffix}）：",
        )
        if not ok or not target_name.strip():
            return
        target_name = target_name.strip().upper()
        target = self._project.profile_files.get(target_name)
        if not target:
            QMessageBox.warning(self, "提示", f"剖面文件 {target_name} 不存在。")
            return
        if target_name == profile_name:
            QMessageBox.warning(self, "提示", "目标剖面文件不能与源文件相同。")
            return
        if suffix in target.extra_files:
            QMessageBox.warning(self, "提示", f"{target_name}.-{suffix} 已存在，未覆盖。")
            return
        target.extra_files[suffix] = source.extra_files[suffix]
        target.modified = True
        self._refresh_borehole_list()
        self._select_in_tree(f"profile_extra:{target_name}:{suffix}")
        self._status_label.setText(f"已复制 {profile_name}.-{suffix} → {target_name}.-{suffix}。")

    def _add_project_file(self) -> None:
        if not self._project.folder:
            QMessageBox.information(self, "提示", "请先选择项目文件夹。")
            return
        name, ok = QInputDialog.getText(self, "新增柱状图文件", "请输入文件名前缀（如 0nzk、0yzk）：")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.startswith("0"):
            QMessageBox.warning(self, "提示", "柱状图文件名应以 0 开头，如 0nzk、0yzk。")
            return
        suffix, ok = QInputDialog.getText(self, "新增柱状图文件", "请输入文件后缀（如 zkt）：", text="zkt")
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
        self._status_label.setText(f"已新增柱状图文件 {full_key}。")

    def _delete_project_file(self, file_name: str, suffix: str) -> None:
        pf = self._project.project_files.get(file_name)
        if not pf or suffix not in pf.extra_files:
            return
        reply = QMessageBox.question(
            self, "删除柱状图文件", f"确定删除 {file_name}.-{suffix}？\n\n点击保存数据后，会备份并删除该文件。"
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

    def _load_current_borehole(self, borehole: Borehole | None, *, preserve_editors: bool = False) -> None:
        preserve_editors = preserve_editors and self._current_borehole is borehole
        self._current_borehole = borehole
        self._current_extra_borehole = None
        self._current_extra_profile = None
        self._current_extra_suffix = None
        if not preserve_editors:
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

    def _update_current_profile_text(self, content: str, *, main_file: bool) -> None:
        profile = self._current_extra_profile
        if profile is None:
            return
        if main_file:
            profile.content = content
            display_name = profile.name
        else:
            suffix = self._current_extra_suffix
            if suffix is None:
                return
            profile.extra_files[suffix] = content
            display_name = f"{profile.name}.-{suffix}"
        profile.modified = True
        self._status_label.setText(f"{display_name} 已修改。")

    def _on_profile_extra_changed(self, _name: str, content: str) -> None:
        self._update_current_profile_text(content, main_file=False)

    def _on_profile_main_changed(self, _name: str, content: str) -> None:
        self._update_current_profile_text(content, main_file=True)

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
        self._migrate_undo_manager(old_prefix, new_prefix)
        self._current_borehole = borehole
        synchronize_column_charts(self._project)
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
            self._tree_controller.update_borehole_label(prefix, self._current_borehole.display_name())
            self._status_label.setText(f"{prefix} 已修改。")

    def _sync_description(
        self,
        old_description: str,
        description: str,
        lithology_code: str,
        formation: str,
        weathering: str,
    ) -> None:
        """将岩性描述同步到所有匹配 (岩性代号, 地层时代, 风化程度) 的其他钻孔。"""
        if self._syncing or not self._current_borehole:
            return
        self._syncing = True
        try:
            empty_descriptions: list[tuple[Borehole, BasicLayer]] = []
            same_descriptions: list[tuple[Borehole, BasicLayer]] = []
            for prefix, bh in self._project.boreholes.items():
                if bh is self._current_borehole:
                    continue
                for layer in bh.layers:
                    if (layer.lithology_code == lithology_code
                            and layer.weathering == weathering
                            and layer.formation == formation):
                        if not layer.description:
                            empty_descriptions.append((bh, layer))
                        elif old_description and layer.description == old_description:
                            same_descriptions.append((bh, layer))

            affected = list(empty_descriptions)
            if same_descriptions:
                reply = QMessageBox.question(
                    self,
                    "同步岩性描述",
                    f"发现 {len(same_descriptions)} 处其他钻孔的相同地层描述仍为修改前内容。\n\n"
                    "是否全部同步为新描述？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    affected.extend(same_descriptions)

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
                    manager.push_composite(CompositeUndoAction(actions=actions, label="同步岩性描述"))
                self._update_undo_controls()

            count = len(affected_boreholes)
            if count > 0:
                self._status_label.setText(f"已同步岩性描述到 {count} 个钻孔。")
        finally:
            self._syncing = False

    # ── 撤销/重做 ──────────────────────────────────────────────────

    def _begin_borehole_change(self, borehole: Borehole | None, label: str) -> _ChangeToken | None:
        if not borehole:
            return None
        return {"borehole": borehole, "label": label, "before": BoreholeSnapshot.capture(borehole)}

    def _end_borehole_change(self, token: _ChangeToken | None) -> None:
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
        return self._undo_controller.get(borehole)

    def _migrate_undo_manager(self, old_prefix: str, new_prefix: str) -> None:
        self._undo_controller.migrate(old_prefix, new_prefix)

    def _undo(self) -> None:
        manager = self._get_undo_manager(self._current_borehole)
        if not manager:
            return
        action = manager.pop_undo()
        if not action:
            return
        if isinstance(action, CompositeUndoAction):
            for a in reversed(action.actions):
                self._apply_snapshot(a.borehole, a.before, activate=False)
            self._refresh_borehole_list()
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
                self._apply_snapshot(a.borehole, a.after, activate=False)
            self._refresh_borehole_list()
            manager.push_undo_without_clearing_redo(action)
        else:
            self._apply_snapshot(action.borehole, action.after)
            manager.push_undo_without_clearing_redo(action)
        self._status_label.setText(f"已恢复：{action.label}")
        self._update_undo_controls()

    def _apply_snapshot(
        self, borehole: Borehole, snapshot: BoreholeSnapshot, *, activate: bool = True
    ) -> None:
        preserve_test_view = (
            activate
            and self._current_borehole is borehole
            and self._tabs.currentWidget() is self._test_data_page
        )
        test_view_state = self._test_data_page.capture_view_state() if preserve_test_view else None
        old_key = borehole.prefix
        if old_key in self._project.boreholes and self._project.boreholes[old_key] is borehole:
            del self._project.boreholes[old_key]
        snapshot.restore(borehole)
        borehole.dirty = True
        self._project.boreholes[borehole.prefix] = borehole
        self._migrate_undo_manager(old_key, borehole.prefix)
        if not activate:
            return
        self._current_borehole = borehole
        self._refresh_borehole_list()
        self._load_current_borehole(borehole)
        self._select_in_tree(borehole.prefix)
        if test_view_state is not None:
            self._tabs.setCurrentWidget(self._test_data_page)
            self._test_data_page.restore_view_state(test_view_state)

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
        service = SaveService(self._project)
        summary = service.summary()
        if not summary.has_changes:
            QMessageBox.information(self, "保存数据", "没有需要保存的数据。")
            return

        parts = []
        if summary.dirty_boreholes:
            parts.append("将保存钻孔：\n" + "\n".join(b.prefix for b in summary.dirty_boreholes))
        if summary.deleted_boreholes:
            parts.append("将删除钻孔：\n" + "\n".join(summary.deleted_boreholes))
        if summary.dirty_profiles:
            parts.append("将保存剖面文件：\n" + "\n".join(p.name for p in summary.dirty_profiles))
        if summary.deleted_profiles:
            parts.append("将删除剖面文件：\n" + "\n".join(summary.deleted_profiles))
        if summary.dirty_project_files:
            parts.append("将保存柱状图文件：\n" + "\n".join(p.name for p in summary.dirty_project_files))
        prompt = "\n\n".join(parts) + "\n\n是否继续？"

        reply = QMessageBox.question(self, "保存数据", prompt)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_label.setText("正在保存...")
        self._start_task(lambda: service.save().as_tuple(), self._finish_save, self._on_save_error)

    def _finish_save(self, result: tuple[list[Path], int]) -> None:
        generated, profile_count = result
        self._set_busy(False)
        self._undo_controller.clear()
        # 保存前记录当前编辑状态（_refresh_borehole_list 内部的 _on_borehole_selected 会清除这些状态）
        saved_extra_profile = self._current_extra_profile
        saved_extra_suffix = self._current_extra_suffix
        saved_borehole = self._current_borehole
        self._refresh_borehole_list()
        # 保存后恢复到之前编辑的位置（剖面文件、柱状图文件或钻孔）
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
            # Saving does not replace the in-memory records. Keep the editors
            # alive so focus and scroll never jump behind the completion dialog.
            self._load_current_borehole(saved_borehole, preserve_editors=True)
        self._update_summary()
        self._update_undo_controls()
        total = len(generated) + profile_count
        self._status_label.setText(f"已保存，更新 {total} 个文件（钻孔 {len(generated)}，剖面 {profile_count}）。")
        QMessageBox.information(
            self,
            "保存完成",
            f"实际更新 {total} 个文件。\n\n钻孔文件：{len(generated)} 个\n剖面文件：{profile_count} 个",
        )

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
        if self._busy:
            return
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
        self._start_task(
            lambda: export_layer_test_summary(self._project, Path(path)),
            lambda count: self._finish_export(count, path),
            self._on_export_error,
        )

    def _on_export_error(self, error: str) -> None:
        QMessageBox.critical(self, "导出失败", error)

    def _finish_export(self, count: int, path: str) -> None:
        self._status_label.setText(f"已导出 {count} 行。")
        reply = QMessageBox.question(
            self, "导出完成",
            f"已导出 {count} 行试验数据。\n{path}\n\n是否打开文件？"
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(path)

    # ── 辅助 ────────────────────────────────────────────────────────

    def _start_task(
        self,
        operation: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None],
    ) -> bool:
        if self._busy or self._task_runner.running:
            return False
        self._set_busy(True)
        started = self._task_runner.start(operation, on_success, on_error)
        if not started:
            self._set_busy(False)
            return False
        self._worker = self._task_runner.worker
        return True

    def _on_task_finished(self) -> None:
        self._worker = None
        self._set_busy(False)

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
            depth: float | None = None
            try:
                depth = float(borehole.main.depth.strip())
            except (ValueError, AttributeError):
                pass
            if depth is not None and isfinite(depth):
                total_depth += depth
            for suffix in counts:
                records = borehole.tests.get(suffix, [])
                counts[suffix] += sum(1 for r in records if any(str(v).strip() for v in r.values))
        depth_text = f"{total_depth:g}" if total_depth else "--"
        self._summary_label.setText(
            f"总深度：{depth_text} m | 取样：{counts['o']} | 标贯：{counts['q']} | "
            f"注水：{counts['n']} | 压水：{counts['m']}"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._task_runner.running and not self._task_runner.wait():
            self._status_label.setText("后台任务仍在运行，请稍后再关闭。")
            event.ignore()
            return
        if SaveService(self._project).summary().has_changes:
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
        self._status_label.setText(f"正在从 {file_path.name} 导入...")

        def worker() -> ProjectData:
            return import_from_table(file_path, project_folder)

        self._start_task(worker, lambda project: self._finish_load(project_folder, project), self._on_import_error)

    def _on_import_error(self, error: str) -> None:
        self._set_busy(False)
        self._status_label.setText("导入失败。")
        QMessageBox.critical(self, "导入失败", error)
