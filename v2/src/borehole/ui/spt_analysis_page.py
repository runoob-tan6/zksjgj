"""标贯分析结果页面 - 全项目按地层统计。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import ProjectData
from ..infrastructure.spt_analysis import (
    compute_layer_stats,
    correct_spt_records,
)


class SPTAnalysisPage(QWidget):
    """标贯杆长修正 + 全项目分层统计页面。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectData | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("标贯分析（全项目按地层统计）")
        title.setProperty("class", "title")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上部：修正明细表（全部钻孔）
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("杆长修正明细（全部钻孔）"))

        self._detail_table = QTableWidget()
        self._detail_table.setColumnCount(7)
        self._detail_table.setHorizontalHeaderLabels([
            "钻孔编号", "起始深度", "终止深度", "杆长(m)", "实测N", "修正系数α", "修正N'"
        ])
        self._detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._detail_table.setAlternatingRowColors(True)
        top_layout.addWidget(self._detail_table)
        splitter.addWidget(top)

        # 下部：分层统计
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(QLabel("分层统计参数"))

        self._stats_table = QTableWidget()
        self._stats_table.setColumnCount(9)
        self._stats_table.setHorizontalHeaderLabels([
            "地层", "样本数n", "最小值", "最大值", "平均值Φm",
            "标准差σf", "变异系数δ", "统计修正系数γs", "标准值Φk"
        ])
        self._stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._stats_table.setAlternatingRowColors(True)
        bottom_layout.addWidget(self._stats_table)

        self._warnings_text = QTextEdit()
        self._warnings_text.setReadOnly(True)
        self._warnings_text.setMaximumHeight(120)
        bottom_layout.addWidget(self._warnings_text)

        splitter.addWidget(bottom)
        layout.addWidget(splitter)

    def load_project(self, project: ProjectData | None) -> None:
        self._project = project
        self._detail_table.setRowCount(0)
        self._stats_table.setRowCount(0)
        self._warnings_text.clear()

        if not project:
            return

        # 修正明细：全部钻孔的标贯记录
        all_rows: list[tuple[str, object]] = []
        for borehole in project.sorted_boreholes():
            corrected = correct_spt_records(borehole)
            for rec in corrected:
                all_rows.append((borehole.prefix, rec))

        self._detail_table.setRowCount(len(all_rows))
        for row, (prefix, rec) in enumerate(all_rows):
            self._detail_table.setItem(row, 0, QTableWidgetItem(prefix))
            self._detail_table.setItem(row, 1, QTableWidgetItem(rec.start_depth))
            self._detail_table.setItem(row, 2, QTableWidgetItem(rec.end_depth))
            self._detail_table.setItem(row, 3, QTableWidgetItem(f"{rec.rod_length:.1f}"))
            self._detail_table.setItem(row, 4, QTableWidgetItem(f"{rec.raw_n:g}"))
            alpha_text = f"{rec.alpha:.2f}" if rec.alpha is not None else "—"
            self._detail_table.setItem(row, 5, QTableWidgetItem(alpha_text))
            corrected_text = f"{rec.corrected_n:g}" if rec.corrected_n is not None else "—"
            item = QTableWidgetItem(corrected_text)
            if rec.warning:
                item.setBackground(Qt.GlobalColor.yellow)
                item.setToolTip(rec.warning)
            self._detail_table.setItem(row, 6, item)

        # 分层统计：全项目按地层分组
        stats = compute_layer_stats(project)
        self._stats_table.setRowCount(len(stats))
        all_warnings: list[str] = []
        for row, s in enumerate(stats):
            self._stats_table.setItem(row, 0, QTableWidgetItem(s.layer_name))
            self._stats_table.setItem(row, 1, QTableWidgetItem(str(s.count)))
            self._stats_table.setItem(row, 2, QTableWidgetItem(f"{s.min_val:g}" if s.count else ""))
            self._stats_table.setItem(row, 3, QTableWidgetItem(f"{s.max_val:g}" if s.count else ""))
            self._stats_table.setItem(row, 4, QTableWidgetItem(f"{s.mean:g}" if s.count else ""))
            self._stats_table.setItem(row, 5, QTableWidgetItem(f"{s.std_dev:g}" if s.count >= 2 else ""))
            self._stats_table.setItem(row, 6, QTableWidgetItem(f"{s.cov:g}" if s.count >= 2 else ""))
            self._stats_table.setItem(row, 7, QTableWidgetItem(f"{s.gamma_s:g}" if s.count >= 2 else ""))

            if s.has_standard_value and s.count >= 3:
                val_item = QTableWidgetItem(f"{s.standard_value:g}")
            elif s.count >= 2:
                val_item = QTableWidgetItem(f"{s.standard_value:g}*")
                val_item.setToolTip("n<6，仅供参考")
            else:
                val_item = QTableWidgetItem("样本不足")
            self._stats_table.setItem(row, 8, val_item)

            for w in s.warnings:
                all_warnings.append(f"[{s.layer_name}] {w}")

        if all_warnings:
            self._warnings_text.setPlainText("\n".join(all_warnings))
        else:
            self._warnings_text.setPlainText("无警告信息。")
